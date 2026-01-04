# Quickstart: ERP Connector Framework Development

**Date**: 2025-12-27

## Setup

```bash
# Generate encryption key
export ENCRYPTION_MASTER_KEY=$(python -c "import os; print(os.urandom(32).hex())")
echo "ENCRYPTION_MASTER_KEY=$ENCRYPTION_MASTER_KEY" >> .env

# Database
cd backend
pip install -r requirements.txt
alembic upgrade head
```

## Test Encryption

```python
def test_encryption_round_trip():
    config = {"host": "sftp.example.com", "password": "secret123"}

    # Encrypt
    encrypted = encrypt_config(config)
    assert len(encrypted) > 28  # IV (12) + ciphertext + tag (16)

    # Decrypt
    decrypted = decrypt_config(encrypted)
    assert decrypted == config
```

## Create Connector via API

```bash
curl -X POST http://localhost:8000/api/v1/connectors/dropzone-json-v1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "sftp",
    "host": "sftp.example.com",
    "port": 22,
    "username": "orderflow",
    "password": "secret123",
    "export_path": "/import/orders",
    "test_on_save": true
  }'
```

## Test Connection

```bash
curl -X POST http://localhost:8000/api/v1/connectors/dropzone-json-v1/test \
  -H "Authorization: Bearer <token>"
```

**Expected Response**:
```json
{
  "success": true,
  "message": "Test file written and cleaned up successfully",
  "latency_ms": 234
}
```

## Unit Test: ConnectorRegistry

```python
def test_connector_registry():
    # Register mock connector
    ConnectorRegistry.register("MOCK", MockConnector)

    # Resolve
    connector = ConnectorRegistry.get("MOCK")
    assert isinstance(connector, MockConnector)

    # Test export
    result = connector.export(draft_order, config={})
    assert result.success is True
```

## Debugging

```sql
-- View connectors for an org
SELECT id, connector_type, status, last_test_at
FROM erp_connection
WHERE org_id = '<uuid>'
ORDER BY created_at DESC;

-- Check encrypted config (should be binary blob, not readable)
SELECT length(config_encrypted), encode(config_encrypted::bytea, 'hex')
FROM erp_connection
WHERE id = '<uuid>';
```
