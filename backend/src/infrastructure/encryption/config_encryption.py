"""Configuration encryption utilities using AES-256-GCM.

Provides secure encryption/decryption for sensitive configuration data
such as ERP connection credentials, SFTP passwords, and API keys.

Security considerations:
- Uses AES-256-GCM for authenticated encryption
- Derives encryption key from PASSWORD_PEPPER using HKDF
- Each encryption uses a unique random nonce
- Includes associated data binding for context

SSOT Reference: §12.5 (Credential Security)
"""

import base64
import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from config import settings


@dataclass
class EncryptedConfig:
    """Encrypted configuration container.

    Attributes:
        version: Encryption format version (for future upgrades)
        nonce: Base64-encoded nonce used for encryption
        ciphertext: Base64-encoded encrypted data
        context: Optional context string used as associated data
    """
    version: int
    nonce: str
    ciphertext: str
    context: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string for database storage."""
        return json.dumps({
            "v": self.version,
            "n": self.nonce,
            "c": self.ciphertext,
            "ctx": self.context
        })

    @classmethod
    def from_json(cls, data: str) -> "EncryptedConfig":
        """Deserialize from JSON string."""
        parsed = json.loads(data)
        return cls(
            version=parsed["v"],
            nonce=parsed["n"],
            ciphertext=parsed["c"],
            context=parsed.get("ctx")
        )


class ConfigEncryption:
    """AES-256-GCM encryption for configuration data.

    Uses the application's PASSWORD_PEPPER as the base key material,
    deriving the actual encryption key using HKDF with a unique salt
    for config encryption (separate from password hashing keys).

    Example:
        encryptor = ConfigEncryption()

        # Encrypt sensitive config
        config = {"sftp_password": "secret123", "api_key": "key456"}
        encrypted = encryptor.encrypt(config, context="erp_connection:123")

        # Store encrypted.to_json() in database

        # Later, decrypt
        decrypted = encryptor.decrypt(encrypted)
    """

    # HKDF info string for config encryption (different from password keys)
    HKDF_INFO = b"orderflow-config-encryption-v1"

    def __init__(self, pepper: Optional[str] = None):
        """Initialize encryptor with pepper.

        Args:
            pepper: Base key material. Defaults to PASSWORD_PEPPER from settings.
        """
        self._pepper = (pepper or settings.PASSWORD_PEPPER).encode()
        self._key = self._derive_key()

    def _derive_key(self) -> bytes:
        """Derive 256-bit encryption key from pepper using HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=None,  # Using static salt in info
            info=self.HKDF_INFO,
        )
        return hkdf.derive(self._pepper)

    def encrypt(
        self,
        config: Dict[str, Any],
        context: Optional[str] = None
    ) -> EncryptedConfig:
        """Encrypt configuration dictionary.

        Args:
            config: Configuration dictionary to encrypt
            context: Optional context string (e.g., "erp_connection:{uuid}")
                    Used as associated data - must match during decryption

        Returns:
            EncryptedConfig containing encrypted data

        Example:
            encrypted = encryptor.encrypt(
                {"password": "secret"},
                context="erp_connection:abc-123"
            )
        """
        # Serialize config to JSON
        plaintext = json.dumps(config).encode()

        # Generate random nonce (96 bits for GCM)
        nonce = os.urandom(12)

        # Create cipher and encrypt with associated data
        aesgcm = AESGCM(self._key)
        associated_data = context.encode() if context else None
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

        return EncryptedConfig(
            version=1,
            nonce=base64.b64encode(nonce).decode(),
            ciphertext=base64.b64encode(ciphertext).decode(),
            context=context
        )

    def decrypt(self, encrypted: EncryptedConfig) -> Dict[str, Any]:
        """Decrypt configuration.

        Args:
            encrypted: EncryptedConfig to decrypt

        Returns:
            Decrypted configuration dictionary

        Raises:
            ValueError: If decryption fails (wrong key, tampered data, wrong context)
        """
        if encrypted.version != 1:
            raise ValueError(f"Unsupported encryption version: {encrypted.version}")

        nonce = base64.b64decode(encrypted.nonce)
        ciphertext = base64.b64decode(encrypted.ciphertext)
        associated_data = encrypted.context.encode() if encrypted.context else None

        aesgcm = AESGCM(self._key)

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        except Exception as e:
            raise ValueError(f"Decryption failed - invalid key or tampered data: {e}")

        return json.loads(plaintext.decode())

    def decrypt_from_json(self, json_data: str) -> Dict[str, Any]:
        """Convenience method to decrypt from JSON string.

        Args:
            json_data: JSON string from database (EncryptedConfig serialized)

        Returns:
            Decrypted configuration dictionary
        """
        encrypted = EncryptedConfig.from_json(json_data)
        return self.decrypt(encrypted)


# Module-level encryptor instance (lazy initialization)
_encryptor: Optional[ConfigEncryption] = None


def get_encryptor() -> ConfigEncryption:
    """Get or create the module-level encryptor instance."""
    global _encryptor
    if _encryptor is None:
        _encryptor = ConfigEncryption()
    return _encryptor


def encrypt_config(
    config: Dict[str, Any],
    context: Optional[str] = None
) -> str:
    """Encrypt configuration and return JSON string for storage.

    Args:
        config: Configuration dictionary to encrypt
        context: Optional context for associated data binding

    Returns:
        JSON string suitable for database storage
    """
    encryptor = get_encryptor()
    encrypted = encryptor.encrypt(config, context)
    return encrypted.to_json()


def decrypt_config(json_data: str) -> Dict[str, Any]:
    """Decrypt configuration from JSON string.

    Args:
        json_data: JSON string from database

    Returns:
        Decrypted configuration dictionary
    """
    encryptor = get_encryptor()
    return encryptor.decrypt_from_json(json_data)
