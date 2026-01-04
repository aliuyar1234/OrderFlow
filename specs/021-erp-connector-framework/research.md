# Research: ERP Connector Framework

**Date**: 2025-12-27

## Key Decisions

### Decision 1: AES-256-GCM for Encryption
**Selected**: AES-GCM with 96-bit random IV per record, AESGCM class from cryptography library

**Rationale**:
- GCM mode provides authenticated encryption (prevents tampering)
- Random IV per record (no IV reuse)
- Standard library, well-tested
- Meets GDPR/SOC2 requirements

**Implementation**:
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTION_KEY = bytes.fromhex(os.environ["ENCRYPTION_MASTER_KEY"])  # 32 bytes

def encrypt_config(config: dict) -> bytes:
    aesgcm = AESGCM(ENCRYPTION_KEY)
    iv = os.urandom(12)  # 96-bit IV
    plaintext = json.dumps(config).encode('utf-8')
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    return iv + ciphertext  # IV (12) + ciphertext + tag (16)

def decrypt_config(encrypted: bytes) -> dict:
    aesgcm = AESGCM(ENCRYPTION_KEY)
    iv = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return json.loads(plaintext.decode('utf-8'))
```

### Decision 2: ConnectorRegistry Pattern
**Selected**: Class-based registry with `register(connector_type, implementation)` and `get(connector_type)`

**Rationale**:
- Decouples connector implementations from PushService
- Enables runtime selection based on org config
- Easy to add new connectors without changing existing code

**Implementation**:
```python
class ConnectorRegistry:
    _connectors: dict[str, type[ERPConnectorPort]] = {}

    @classmethod
    def register(cls, connector_type: str, implementation: type[ERPConnectorPort]):
        cls._connectors[connector_type] = implementation

    @classmethod
    def get(cls, connector_type: str) -> ERPConnectorPort:
        if connector_type not in cls._connectors:
            raise ValueError(f"Unknown connector type: {connector_type}")
        return cls._connectors[connector_type]()

# Register implementations
ConnectorRegistry.register("DROPZONE_JSON_V1", DropzoneJsonV1Connector)
ConnectorRegistry.register("MOCK", MockConnector)
```

### Decision 3: Single Active Connector per Org (MVP)
**Selected**: UNIQUE constraint on (org_id, connector_type) WHERE status='ACTIVE'

**Rationale**:
- Simplifies MVP: no routing logic needed
- Most customers have one ERP system
- Partial index (WHERE status='ACTIVE') allows multiple DISABLED connectors (historical record)

**SQL**:
```sql
CREATE UNIQUE INDEX uq_active_connector
ON erp_connection(org_id, connector_type)
WHERE status = 'ACTIVE';
```

## Best Practices

### Credential Storage
- Never log plaintext credentials
- Never return config_encrypted in API responses
- Use environment variable for ENCRYPTION_MASTER_KEY (not hardcoded)
- Rotate keys periodically (requires re-encryption of all configs)

### Connection Testing
- Test endpoint should write a temporary file and delete it
- Use timeout for network operations (default: 10s)
- Log test latency for monitoring

### Error Handling
```python
try:
    config = decrypt_config(connection.config_encrypted)
except Exception as e:
    logger.error(f"Decryption failed for connection {connection.id}: {e}")
    raise HTTPException(status_code=500, detail="Configuration error")
```

## References
- SSOT §3.5: ERPConnectorPort interface
- SSOT §11.3: Encryption requirements
- OWASP Cryptographic Storage Cheat Sheet
