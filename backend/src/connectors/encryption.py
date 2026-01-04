"""
AES-GCM Encryption for ERP Connection Credentials

Provides secure encryption/decryption of connector configuration using AES-256-GCM.
Each encrypted config includes a random IV and authentication tag for integrity.

SSOT Reference: §11.3 (Encryption)
"""

import os
import json
import logging
from typing import Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""
    pass


class EncryptionService:
    """
    Service for encrypting and decrypting ERP connector configurations.

    Uses AES-256-GCM with:
    - 256-bit key from ENCRYPTION_MASTER_KEY environment variable
    - Random 96-bit IV per encryption operation
    - Authentication tag for integrity verification

    Storage format: IV (12 bytes) + ciphertext + auth tag (16 bytes)
    """

    _encryption_key: bytes = None

    @classmethod
    def initialize(cls, master_key_hex: str = None) -> None:
        """
        Initialize the encryption service with the master key.

        Args:
            master_key_hex: 64-character hex string (32 bytes). If None, reads from ENCRYPTION_MASTER_KEY env var.

        Raises:
            EncryptionError: If key is missing or invalid
        """
        if master_key_hex is None:
            master_key_hex = os.environ.get("ENCRYPTION_MASTER_KEY")

        if not master_key_hex:
            raise EncryptionError(
                "ENCRYPTION_MASTER_KEY environment variable is not set. "
                "Generate one with: python -c 'import os; print(os.urandom(32).hex())'"
            )

        try:
            cls._encryption_key = bytes.fromhex(master_key_hex)
        except ValueError as e:
            raise EncryptionError(
                f"ENCRYPTION_MASTER_KEY must be a valid hex string: {e}"
            )

        if len(cls._encryption_key) != 32:
            raise EncryptionError(
                f"ENCRYPTION_MASTER_KEY must be 32 bytes (64 hex chars), "
                f"got {len(cls._encryption_key)} bytes"
            )

        logger.info("Encryption service initialized with AES-256-GCM")

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure the encryption service is initialized."""
        if cls._encryption_key is None:
            cls.initialize()

    @classmethod
    def encrypt_config(cls, config: Dict[str, Any]) -> bytes:
        """
        Encrypt a configuration dictionary.

        Args:
            config: Configuration dictionary to encrypt (will be JSON-serialized)

        Returns:
            Encrypted bytes: IV (12 bytes) + ciphertext + auth tag (16 bytes)

        Raises:
            EncryptionError: If encryption fails

        Example:
            config = {"host": "sftp.example.com", "password": "secret"}
            encrypted = EncryptionService.encrypt_config(config)
        """
        cls._ensure_initialized()

        try:
            # Serialize config to JSON
            plaintext = json.dumps(config, sort_keys=True).encode('utf-8')

            # Generate random IV (96 bits = 12 bytes)
            iv = os.urandom(12)

            # Encrypt with AES-GCM (returns ciphertext + 16-byte auth tag)
            aesgcm = AESGCM(cls._encryption_key)
            ciphertext = aesgcm.encrypt(iv, plaintext, None)

            # Combine IV + ciphertext+tag for storage
            encrypted = iv + ciphertext

            logger.debug(
                f"Encrypted config: {len(plaintext)} bytes plaintext -> "
                f"{len(encrypted)} bytes encrypted"
            )

            return encrypted

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt configuration: {e}")

    @classmethod
    def decrypt_config(cls, encrypted: bytes) -> Dict[str, Any]:
        """
        Decrypt a configuration dictionary.

        Args:
            encrypted: Encrypted bytes (IV + ciphertext + auth tag)

        Returns:
            Decrypted configuration dictionary

        Raises:
            EncryptionError: If decryption fails or authentication tag is invalid

        Example:
            config = EncryptionService.decrypt_config(encrypted_bytes)
            print(config["host"])  # "sftp.example.com"
        """
        cls._ensure_initialized()

        try:
            # Extract IV and ciphertext+tag
            if len(encrypted) < 12:
                raise EncryptionError("Encrypted data is too short (missing IV)")

            iv = encrypted[:12]
            ciphertext = encrypted[12:]

            # Decrypt with AES-GCM (verifies auth tag)
            aesgcm = AESGCM(cls._encryption_key)
            plaintext = aesgcm.decrypt(iv, ciphertext, None)

            # Deserialize JSON
            config = json.loads(plaintext.decode('utf-8'))

            logger.debug(
                f"Decrypted config: {len(encrypted)} bytes encrypted -> "
                f"{len(plaintext)} bytes plaintext"
            )

            return config

        except InvalidTag:
            logger.error("Decryption failed: authentication tag verification failed")
            raise EncryptionError(
                "Decryption failed: data has been tampered with or wrong encryption key"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Decryption failed: invalid JSON after decryption: {e}")
            raise EncryptionError(
                "Decryption failed: decrypted data is not valid JSON"
            )
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt configuration: {e}")

    @classmethod
    def rotate_key(
        cls,
        old_key_hex: str,
        new_key_hex: str,
        encrypted_data: bytes
    ) -> bytes:
        """
        Re-encrypt data with a new key (for key rotation).

        Args:
            old_key_hex: Current encryption key (64-char hex)
            new_key_hex: New encryption key (64-char hex)
            encrypted_data: Data encrypted with old key

        Returns:
            Data re-encrypted with new key

        Raises:
            EncryptionError: If re-encryption fails

        Example:
            new_encrypted = EncryptionService.rotate_key(
                old_key="abc...",
                new_key="def...",
                encrypted_data=old_encrypted
            )
        """
        # Temporarily switch to old key to decrypt
        original_key = cls._encryption_key
        try:
            cls.initialize(old_key_hex)
            decrypted_config = cls.decrypt_config(encrypted_data)

            # Switch to new key to re-encrypt
            cls.initialize(new_key_hex)
            new_encrypted = cls.encrypt_config(decrypted_config)

            return new_encrypted

        finally:
            # Restore original key
            cls._encryption_key = original_key


# Initialize on module import (reads from environment)
# This will raise EncryptionError if ENCRYPTION_MASTER_KEY is not set
# In tests, this can be overridden with EncryptionService.initialize(test_key)
try:
    EncryptionService.initialize()
except EncryptionError as e:
    logger.warning(f"Encryption service not initialized: {e}")
    # Allow application to start even if encryption key is not set
    # (useful for development/testing where encryption might not be needed)
    pass
