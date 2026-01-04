"""Acknowledgment File Poller - processes ERP acknowledgment files.

This worker polls configured ack_path directories for acknowledgment files
written by ERP systems, updates export status accordingly, and moves processed
files to a 'processed' subdirectory.

SSOT Reference: §12.2 (Ack mechanism), T-606 (Ack poller acceptance criteria)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import re

from sqlalchemy.orm import Session
from celery import Task

from models import ERPConnection, ERPExport, ERPExportStatus
from infrastructure.sftp import SFTPClient, SFTPConfig, SFTPError
from infrastructure.encryption import decrypt_config

logger = logging.getLogger(__name__)


def poll_acks_for_all_connectors(db: Session) -> Dict[str, Any]:
    """Poll acknowledgment files for all active ERP connections.

    This task runs periodically (every 60s by default) and checks for
    acknowledgment files in configured ack_path locations.

    Args:
        db: Database session

    Returns:
        Dict with processing statistics
    """
    stats = {
        'connectors_checked': 0,
        'acks_processed': 0,
        'errors': 0,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    # Get all active connectors with ack_path configured
    connectors = db.query(ERPConnection).filter(
        ERPConnection.active == True
    ).all()

    for connector in connectors:
        stats['connectors_checked'] += 1

        try:
            # Decrypt config using AES-256-GCM
            config = decrypt_config(connector.config_encrypted)
            ack_path = config.get('ack_path')

            if not ack_path:
                logger.debug(f"Connector {connector.id} has no ack_path configured, skipping")
                continue

            # Poll based on mode
            mode = config.get('mode', 'filesystem')
            acks_count = 0

            if mode == 'sftp':
                acks_count = poll_acks_sftp(db, connector, config)
            elif mode == 'filesystem':
                acks_count = poll_acks_filesystem(db, connector, config)
            else:
                logger.warning(f"Unknown mode '{mode}' for connector {connector.id}")

            stats['acks_processed'] += acks_count

        except Exception as e:
            logger.error(f"Error polling acks for connector {connector.id}: {e}", exc_info=True)
            stats['errors'] += 1

    logger.info(f"Ack polling completed: {stats}")
    return stats


def poll_acks_sftp(db: Session, connector: ERPConnection, config: dict) -> int:
    """Poll acknowledgment files from SFTP directory.

    Args:
        db: Database session
        connector: ERP connection
        config: Connector configuration

    Returns:
        Number of ack files processed
    """
    ack_path = config['ack_path']
    acks_processed = 0

    sftp_config = SFTPConfig(
        host=config['host'],
        port=config.get('port', 22),
        username=config['username'],
        password=config.get('password'),
        ssh_key=config.get('ssh_key'),
        export_path=config.get('export_path', '/exports')
    )

    client = SFTPClient(sftp_config)

    try:
        client.connect()

        # List ack files (pattern: ack_*.json or error_*.json)
        ack_files = []
        ack_files.extend(client.list_files(ack_path, pattern='ack_*.json'))
        ack_files.extend(client.list_files(ack_path, pattern='error_*.json'))

        for ack_filename in ack_files:
            try:
                ack_filepath = f"{ack_path}/{ack_filename}"
                content = client.read_file(ack_filepath)
                ack_data = json.loads(content)

                # Process ack
                process_ack_data(db, connector, ack_filename, ack_data)
                acks_processed += 1

                # Move to processed/ subdirectory
                processed_dir = f"{ack_path}/processed"
                client.mkdir(processed_dir)
                processed_path = f"{processed_dir}/{ack_filename}"
                client.move_file(ack_filepath, processed_path)

                logger.info(f"Processed ack file: {ack_filename}")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in ack file {ack_filename}: {e}")
                # Move to error/ subdirectory
                error_dir = f"{ack_path}/error"
                client.mkdir(error_dir)
                client.move_file(ack_filepath, f"{error_dir}/{ack_filename}")

            except Exception as e:
                logger.error(f"Error processing ack file {ack_filename}: {e}", exc_info=True)

    finally:
        client.close()

    return acks_processed


def poll_acks_filesystem(db: Session, connector: ERPConnection, config: dict) -> int:
    """Poll acknowledgment files from local filesystem directory.

    Args:
        db: Database session
        connector: ERP connection
        config: Connector configuration

    Returns:
        Number of ack files processed
    """
    ack_path = Path(config['ack_path'])

    if not ack_path.exists():
        logger.warning(f"Ack path does not exist: {ack_path}")
        return 0

    acks_processed = 0

    # Find ack files
    ack_files = list(ack_path.glob('ack_*.json'))
    ack_files.extend(ack_path.glob('error_*.json'))

    for ack_file in ack_files:
        try:
            content = ack_file.read_text(encoding='utf-8')
            ack_data = json.loads(content)

            # Process ack
            process_ack_data(db, connector, ack_file.name, ack_data)
            acks_processed += 1

            # Move to processed/ subdirectory
            processed_dir = ack_path / 'processed'
            processed_dir.mkdir(exist_ok=True)
            ack_file.rename(processed_dir / ack_file.name)

            logger.info(f"Processed ack file: {ack_file.name}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in ack file {ack_file}: {e}")
            # Move to error/ subdirectory
            error_dir = ack_path / 'error'
            error_dir.mkdir(exist_ok=True)
            ack_file.rename(error_dir / ack_file.name)

        except Exception as e:
            logger.error(f"Error processing ack file {ack_file}: {e}", exc_info=True)

    return acks_processed


def process_ack_data(db: Session, connector: ERPConnection, ack_filename: str, ack_data: dict) -> None:
    """Process acknowledgment data and update export record.

    Args:
        db: Database session
        connector: ERP connection
        ack_filename: Name of ack file
        ack_data: Parsed ack JSON data
    """
    # Extract draft_order_id from filename
    # Pattern: ack_sales_order_{draft_id}_{timestamp}_{uuid}.json
    # or: error_sales_order_{draft_id}_{timestamp}_{uuid}.json
    draft_order_id = extract_draft_order_id(ack_filename)

    if not draft_order_id:
        logger.error(f"Could not extract draft_order_id from filename: {ack_filename}")
        return

    # Find corresponding export (latest for this draft + connector)
    export = db.query(ERPExport).filter(
        ERPExport.erp_connection_id == connector.id,
        ERPExport.draft_order_id == draft_order_id,
        ERPExport.status == ERPExportStatus.SENT.value
    ).order_by(ERPExport.created_at.desc()).first()

    if not export:
        logger.warning(f"No SENT export found for draft_order_id={draft_order_id}, connector={connector.id}")
        return

    # Update export based on ack status
    ack_status = ack_data.get('status')

    if ack_status == 'ACKED':
        export.status = ERPExportStatus.ACKED.value
        export.erp_order_id = ack_data.get('erp_order_id')
        logger.info(f"Export {export.id} acknowledged: erp_order_id={export.erp_order_id}")

    elif ack_status == 'FAILED':
        export.status = ERPExportStatus.FAILED.value
        export.error_json = {
            'error_code': ack_data.get('error_code'),
            'message': ack_data.get('message'),
            'processed_at': ack_data.get('processed_at')
        }
        logger.warning(f"Export {export.id} failed: {export.error_json}")

    else:
        logger.error(f"Unknown ack status: {ack_status}")
        return

    export.updated_at = datetime.now(timezone.utc)
    db.commit()


def extract_draft_order_id(ack_filename: str) -> Optional[str]:
    """Extract draft_order_id from acknowledgment filename.

    Pattern: (ack|error)_sales_order_{draft_id}_{timestamp}_{uuid}.json

    Args:
        ack_filename: Acknowledgment filename

    Returns:
        Draft order ID or None if not found
    """
    # Match pattern: (ack|error)_sales_order_{draft_id}_{timestamp}_{uuid}.json
    pattern = r'^(?:ack|error)_sales_order_([a-f0-9-]+)_\d+_[a-f0-9]+\.json$'
    match = re.match(pattern, ack_filename)

    if match:
        return match.group(1)

    return None
