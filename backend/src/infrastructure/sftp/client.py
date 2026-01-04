"""SFTP Client for dropzone file operations with atomic writes.

This module provides an SFTP client wrapper that supports:
- Atomic write operations (.tmp + rename)
- Connection pooling and reuse
- Graceful error handling
- Both password and key-based authentication

SSOT Reference: §12.1 (Atomic Write), §12.2 (Ack polling)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import paramiko
from io import BytesIO

logger = logging.getLogger(__name__)


class SFTPError(Exception):
    """Base exception for SFTP operations."""
    pass


@dataclass
class SFTPConfig:
    """SFTP connection configuration.

    Attributes:
        host: SFTP server hostname
        port: SFTP server port (default 22)
        username: Username for authentication
        password: Password for authentication (mutually exclusive with ssh_key)
        ssh_key: SSH private key content for authentication (mutually exclusive with password)
        export_path: Base directory for export files
        ack_path: Optional directory for acknowledgment files
        atomic_write: Whether to use atomic write (.tmp + rename)
    """
    host: str
    username: str
    port: int = 22
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    export_path: str = "/dropzone/exports"
    ack_path: Optional[str] = None
    atomic_write: bool = True


class SFTPClient:
    """SFTP client with atomic write support.

    This client provides safe file upload operations to SFTP servers,
    with atomic rename to prevent partial file reads by ERP systems.

    Example:
        config = SFTPConfig(
            host="sftp.example.com",
            username="orderflow",
            password="secret",
            export_path="/exports"
        )

        client = SFTPClient(config)
        try:
            client.connect()
            client.write_file("order.json", json_content)
        finally:
            client.close()
    """

    def __init__(self, config: SFTPConfig):
        """Initialize SFTP client with configuration.

        Args:
            config: SFTP configuration
        """
        self.config = config
        self._ssh_client: Optional[paramiko.SSHClient] = None
        self._sftp_client: Optional[paramiko.SFTPClient] = None

    def connect(self) -> None:
        """Establish SFTP connection.

        Raises:
            SFTPError: If connection fails
        """
        try:
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Prepare authentication
            connect_kwargs = {
                "hostname": self.config.host,
                "port": self.config.port,
                "username": self.config.username,
                "look_for_keys": False,
                "allow_agent": False
            }

            if self.config.ssh_key:
                # Use key-based authentication
                key_file = BytesIO(self.config.ssh_key.encode())
                pkey = paramiko.RSAKey.from_private_key(key_file)
                connect_kwargs["pkey"] = pkey
            elif self.config.password:
                # Use password authentication
                connect_kwargs["password"] = self.config.password
            else:
                raise SFTPError("Either password or ssh_key must be provided")

            logger.info(f"Connecting to SFTP server {self.config.host}:{self.config.port}")
            self._ssh_client.connect(**connect_kwargs)
            self._sftp_client = self._ssh_client.open_sftp()
            logger.info("SFTP connection established")

        except paramiko.AuthenticationException as e:
            raise SFTPError(f"Authentication failed: {e}")
        except paramiko.SSHException as e:
            raise SFTPError(f"SSH connection failed: {e}")
        except Exception as e:
            raise SFTPError(f"Failed to connect to SFTP server: {e}")

    def close(self) -> None:
        """Close SFTP connection."""
        if self._sftp_client:
            self._sftp_client.close()
            self._sftp_client = None
        if self._ssh_client:
            self._ssh_client.close()
            self._ssh_client = None
        logger.info("SFTP connection closed")

    def _ensure_connected(self) -> None:
        """Ensure SFTP connection is active.

        Raises:
            SFTPError: If not connected
        """
        if not self._sftp_client:
            raise SFTPError("Not connected to SFTP server. Call connect() first.")

    def write_file(self, filename: str, content: str) -> str:
        """Write file to SFTP with atomic rename.

        This method writes the content to a temporary file first (.tmp suffix),
        then renames it to the final name. This ensures ERP systems only see
        complete files, never partial writes.

        Args:
            filename: Name of the file to write (without path)
            content: File content as string

        Returns:
            str: Full path where file was written

        Raises:
            SFTPError: If write operation fails
        """
        self._ensure_connected()

        final_path = f"{self.config.export_path}/{filename}"

        try:
            if self.config.atomic_write:
                # Atomic write: .tmp + rename
                tmp_path = f"{final_path}.tmp"

                logger.debug(f"Writing to temporary file: {tmp_path}")
                with self._sftp_client.open(tmp_path, 'w') as remote_file:
                    remote_file.write(content)

                logger.debug(f"Renaming {tmp_path} -> {final_path}")
                self._sftp_client.rename(tmp_path, final_path)
            else:
                # Direct write (no atomic rename)
                logger.debug(f"Writing directly to: {final_path}")
                with self._sftp_client.open(final_path, 'w') as remote_file:
                    remote_file.write(content)

            logger.info(f"Successfully wrote file to SFTP: {final_path}")
            return final_path

        except IOError as e:
            raise SFTPError(f"Failed to write file {filename}: {e}")
        except Exception as e:
            # Clean up tmp file if rename failed
            if self.config.atomic_write:
                try:
                    self._sftp_client.remove(tmp_path)
                except (IOError, OSError):
                    pass  # Ignore cleanup errors - tmp file may not exist
            raise SFTPError(f"Unexpected error writing file {filename}: {e}")

    def list_files(self, directory: Optional[str] = None, pattern: Optional[str] = None) -> List[str]:
        """List files in SFTP directory.

        Args:
            directory: Directory to list (default: export_path)
            pattern: Optional filename pattern (e.g., 'ack_*.json')

        Returns:
            List of filenames (not full paths)

        Raises:
            SFTPError: If listing fails
        """
        self._ensure_connected()

        target_dir = directory or self.config.export_path

        try:
            files = self._sftp_client.listdir(target_dir)

            if pattern:
                import fnmatch
                files = [f for f in files if fnmatch.fnmatch(f, pattern)]

            return files

        except IOError as e:
            raise SFTPError(f"Failed to list directory {target_dir}: {e}")

    def read_file(self, filepath: str) -> str:
        """Read file content from SFTP.

        Args:
            filepath: Full path to file on SFTP server

        Returns:
            File content as string

        Raises:
            SFTPError: If read fails
        """
        self._ensure_connected()

        try:
            with self._sftp_client.open(filepath, 'r') as remote_file:
                content = remote_file.read()
            return content

        except IOError as e:
            raise SFTPError(f"Failed to read file {filepath}: {e}")

    def move_file(self, source_path: str, dest_path: str) -> None:
        """Move/rename file on SFTP server.

        Args:
            source_path: Current file path
            dest_path: Destination file path

        Raises:
            SFTPError: If move fails
        """
        self._ensure_connected()

        try:
            self._sftp_client.rename(source_path, dest_path)
            logger.debug(f"Moved file: {source_path} -> {dest_path}")

        except IOError as e:
            raise SFTPError(f"Failed to move file {source_path}: {e}")

    def delete_file(self, filepath: str) -> None:
        """Delete file from SFTP server.

        Args:
            filepath: Full path to file to delete

        Raises:
            SFTPError: If deletion fails
        """
        self._ensure_connected()

        try:
            self._sftp_client.remove(filepath)
            logger.debug(f"Deleted file: {filepath}")

        except IOError as e:
            raise SFTPError(f"Failed to delete file {filepath}: {e}")

    def mkdir(self, directory: str) -> None:
        """Create directory on SFTP server.

        Args:
            directory: Directory path to create

        Raises:
            SFTPError: If creation fails
        """
        self._ensure_connected()

        try:
            self._sftp_client.mkdir(directory)
            logger.debug(f"Created directory: {directory}")

        except IOError as e:
            # Ignore if directory already exists
            if "File exists" not in str(e):
                raise SFTPError(f"Failed to create directory {directory}: {e}")

    def __enter__(self):
        """Context manager entry - auto-connect."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto-close."""
        self.close()
        return False
