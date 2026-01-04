"""Password policy enforcement for OrderFlow.

Implements NIST SP 800-63B password guidelines:
- Minimum 12 characters (increased from default 8)
- Check against common password lists
- No arbitrary complexity rules (proven ineffective)
- Support for passphrases

SSOT Reference: §8.3 (Authentication Security)
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

# Minimum password length (NIST recommends 8, we require 12 for enterprise)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

# Common passwords to reject (top 100 most common)
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "passw0rd", "shadow", "123123", "654321", "superman",
    "qazwsx", "michael", "football", "password1", "password123", "welcome",
    "welcome1", "admin", "admin123", "root", "toor", "pass", "test", "guest",
    "master123", "changeme", "123qwe", "zxcvbnm", "asdfgh", "1qaz2wsx",
    "qwertyuiop", "1234567890", "password!", "password1!", "letmein1",
    "p@ssw0rd", "p@ssword", "pa$$word", "passw0rd!", "Password1",
    "Password123", "Password!", "P@ssw0rd", "P@ssword1", "Qwerty123",
    "orderflow", "orderflow123", "order123", "flow123",  # Application-specific
}

# Patterns that indicate weak passwords
WEAK_PATTERNS = [
    r"^(.)\1+$",  # All same character (aaaaaa)
    r"^(012|123|234|345|456|567|678|789|890)+$",  # Sequential numbers
    r"^(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)+$",  # Sequential letters
    r"^(qwerty|asdf|zxcv|wasd)+",  # Keyboard patterns
]


class PasswordValidationError(Exception):
    """Exception raised when password doesn't meet policy."""

    def __init__(self, message: str, errors: List[str]):
        self.message = message
        self.errors = errors
        super().__init__(message)


class PasswordPolicy(BaseModel):
    """Password policy configuration."""

    min_length: int = Field(default=MIN_PASSWORD_LENGTH, ge=8, le=128)
    max_length: int = Field(default=MAX_PASSWORD_LENGTH, ge=16, le=256)
    require_uppercase: bool = Field(default=False)  # NIST: Not required
    require_lowercase: bool = Field(default=False)  # NIST: Not required
    require_digit: bool = Field(default=False)  # NIST: Not required
    require_special: bool = Field(default=False)  # NIST: Not required
    check_common_passwords: bool = Field(default=True)
    check_weak_patterns: bool = Field(default=True)


# Default policy follows NIST guidelines
DEFAULT_POLICY = PasswordPolicy()


def validate_password(
    password: str,
    policy: Optional[PasswordPolicy] = None,
    user_context: Optional[List[str]] = None
) -> List[str]:
    """Validate password against policy.

    Args:
        password: Password to validate
        policy: Password policy to use (defaults to NIST-compliant policy)
        user_context: Additional strings to check against (username, email, org name)

    Returns:
        List of validation errors (empty if valid)
    """
    if policy is None:
        policy = DEFAULT_POLICY

    errors = []

    # Length checks
    if len(password) < policy.min_length:
        errors.append(f"Password must be at least {policy.min_length} characters long")

    if len(password) > policy.max_length:
        errors.append(f"Password must be at most {policy.max_length} characters long")

    # Common password check
    if policy.check_common_passwords:
        password_lower = password.lower()
        if password_lower in COMMON_PASSWORDS:
            errors.append("This password is too common. Please choose a more unique password")

        # Check if password contains common words with simple substitutions
        normalized = password_lower.replace("0", "o").replace("1", "i").replace("@", "a").replace("$", "s").replace("3", "e")
        if normalized in COMMON_PASSWORDS:
            errors.append("This password is too common (even with character substitutions)")

    # Weak pattern check
    if policy.check_weak_patterns:
        password_lower = password.lower()
        for pattern in WEAK_PATTERNS:
            if re.match(pattern, password_lower):
                errors.append("Password contains a weak pattern (repeated or sequential characters)")
                break

    # User context check (prevent password containing username/email)
    if user_context:
        password_lower = password.lower()
        for context in user_context:
            if context and len(context) >= 3:
                context_lower = context.lower()
                if context_lower in password_lower or password_lower in context_lower:
                    errors.append("Password cannot contain your username, email, or organization name")
                    break

    # Optional complexity requirements (disabled by default per NIST)
    if policy.require_uppercase and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if policy.require_lowercase and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if policy.require_digit and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    if policy.require_special:
        special_chars = set("!@#$%^&*()_+-=[]{}|;':\",./<>?`~")
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")

    return errors


def check_password_strength(
    password: str,
    user_context: Optional[List[str]] = None
) -> None:
    """Check password strength and raise exception if weak.

    Args:
        password: Password to check
        user_context: Additional strings to check against

    Raises:
        PasswordValidationError: If password doesn't meet policy
    """
    errors = validate_password(password, user_context=user_context)
    if errors:
        raise PasswordValidationError(
            "Password does not meet security requirements",
            errors
        )


def get_password_strength_score(password: str) -> int:
    """Calculate password strength score (0-100).

    Scoring criteria:
    - Length: Up to 40 points (3 points per character over 8)
    - Character diversity: Up to 30 points
    - No common patterns: 20 points
    - No common passwords: 10 points

    Args:
        password: Password to score

    Returns:
        Strength score from 0-100
    """
    score = 0

    # Length score (max 40 points)
    length_score = min(40, max(0, (len(password) - 8) * 3))
    score += length_score

    # Character diversity (max 30 points)
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    diversity_count = sum([has_lower, has_upper, has_digit, has_special])
    score += diversity_count * 7.5  # 7.5 points per character type

    # Pattern penalty
    password_lower = password.lower()
    has_weak_pattern = any(re.match(p, password_lower) for p in WEAK_PATTERNS)
    if not has_weak_pattern:
        score += 20

    # Common password check
    if password_lower not in COMMON_PASSWORDS:
        score += 10

    return min(100, int(score))


class SecurePassword(str):
    """Pydantic-compatible password type with validation.

    Use in Pydantic models:

        class CreateUserRequest(BaseModel):
            email: EmailStr
            password: SecurePassword
    """

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("Password must be a string")

        errors = validate_password(v)
        if errors:
            raise ValueError("; ".join(errors))

        return v

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {
            "type": "string",
            "minLength": MIN_PASSWORD_LENGTH,
            "maxLength": MAX_PASSWORD_LENGTH,
            "description": f"Password ({MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters)"
        }
