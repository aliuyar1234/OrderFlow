"""Password hashing and verification using Argon2id

This module provides secure password hashing using Argon2id with OWASP-recommended
parameters and a global PASSWORD_PEPPER for additional security.

OWASP Parameters (§11.1):
- Memory cost: 65536 KB (64 MB)
- Time cost: 3 iterations
- Parallelism: 4 threads
"""

import os
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError


# OWASP recommended parameters for Argon2id
# Memory cost: 64 MB, Time cost: 3, Parallelism: 4
_hasher = PasswordHasher(
    memory_cost=65536,  # 64 MB
    time_cost=3,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID  # Argon2id variant
)


def _get_pepper() -> str:
    """Get PASSWORD_PEPPER from environment.

    Returns:
        str: The PASSWORD_PEPPER value

    Raises:
        ValueError: If PASSWORD_PEPPER is not set
    """
    pepper = os.getenv('PASSWORD_PEPPER')
    if not pepper:
        raise ValueError("PASSWORD_PEPPER environment variable is not set")
    return pepper


def hash_password(password: str) -> str:
    """Hash a password using Argon2id with global pepper.

    The password is combined with PASSWORD_PEPPER before hashing to provide
    an additional layer of security. The pepper is server-side only and not
    stored in the database.

    Args:
        password: Plain text password to hash

    Returns:
        str: Argon2id hash string (format: $argon2id$v=19$m=65536,t=3,p=4$...$...)

    Raises:
        ValueError: If PASSWORD_PEPPER is not set or password is empty
    """
    if not password:
        raise ValueError("Password cannot be empty")

    pepper = _get_pepper()
    peppered_password = password + pepper

    return _hasher.hash(peppered_password)


def verify_password(password: str, hash: str) -> bool:
    """Verify a password against an Argon2id hash.

    Args:
        password: Plain text password to verify
        hash: Argon2id hash to verify against

    Returns:
        bool: True if password matches hash, False otherwise

    Raises:
        ValueError: If PASSWORD_PEPPER is not set
    """
    if not password or not hash:
        return False

    pepper = _get_pepper()
    peppered_password = password + pepper

    try:
        _hasher.verify(hash, peppered_password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets strength requirements.

    Requirements (§8.3 Login Security):
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, "explanation of requirements")

    Example:
        >>> validate_password_strength("weak")
        (False, "Password must be at least 8 characters long")
        >>> validate_password_strength("SecureP@ss123")
        (True, "")
    """
    import re

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"

    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
        return False, "Password must contain at least one special character"

    return True, ""
