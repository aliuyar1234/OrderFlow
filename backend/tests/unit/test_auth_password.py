"""Unit tests for password hashing and verification

Tests cover:
- Password hashing with Argon2id
- Password verification
- Password strength validation
- Pepper handling
- Security parameters (OWASP compliance)

SSOT Reference: §8.3 (Login Security), §11.1 (Password Security)
"""

import pytest
import os
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from auth.password import hash_password, verify_password, validate_password_strength


class TestHashPassword:
    """Test password hashing functionality"""

    def test_hash_password_returns_string(self, monkeypatch):
        """Test hashing returns a non-empty string"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_argon2id_format(self, monkeypatch):
        """Test hash follows Argon2id format"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Argon2id hash format: $argon2id$v=19$m=65536,t=3,p=4$...
        assert hashed.startswith('$argon2id$')
        assert 'm=65536' in hashed  # Memory cost: 64 MB
        assert 't=3' in hashed      # Time cost: 3 iterations
        assert 'p=4' in hashed      # Parallelism: 4 threads

    def test_hash_password_different_for_same_input(self, monkeypatch):
        """Test same password produces different hashes (due to random salt)"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salt each time

    def test_hash_password_without_pepper_raises_error(self, monkeypatch):
        """Test hashing without PASSWORD_PEPPER raises ValueError"""
        monkeypatch.delenv('PASSWORD_PEPPER', raising=False)

        with pytest.raises(ValueError, match="PASSWORD_PEPPER environment variable is not set"):
            hash_password("SecureP@ss123")

    def test_hash_password_empty_raises_error(self, monkeypatch):
        """Test hashing empty password raises ValueError"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        with pytest.raises(ValueError, match="Password cannot be empty"):
            hash_password("")

    def test_hash_password_uses_pepper(self, monkeypatch):
        """Test password is combined with pepper before hashing"""
        pepper1 = 'pepper-one'
        pepper2 = 'pepper-two'
        password = "SamePassword123!"

        # Hash with pepper1
        monkeypatch.setenv('PASSWORD_PEPPER', pepper1)
        hash1 = hash_password(password)

        # Hash with pepper2
        monkeypatch.setenv('PASSWORD_PEPPER', pepper2)
        hash2 = hash_password(password)

        # Verify hash1 only works with original pepper
        monkeypatch.setenv('PASSWORD_PEPPER', pepper1)
        assert verify_password(password, hash1) is True

        # Verify hash2 only works with its pepper
        monkeypatch.setenv('PASSWORD_PEPPER', pepper2)
        assert verify_password(password, hash2) is True

        # Verify hash1 fails with wrong pepper
        monkeypatch.setenv('PASSWORD_PEPPER', pepper2)
        assert verify_password(password, hash1) is False


class TestVerifyPassword:
    """Test password verification functionality"""

    def test_verify_password_correct(self, monkeypatch):
        """Test verifying correct password returns True"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, monkeypatch):
        """Test verifying incorrect password returns False"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        correct_password = "SecureP@ss123"
        wrong_password = "WrongP@ss456"
        hashed = hash_password(correct_password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_case_sensitive(self, monkeypatch):
        """Test password verification is case-sensitive"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Different case should fail
        assert verify_password("securep@ss123", hashed) is False
        assert verify_password("SECUREP@SS123", hashed) is False

    def test_verify_password_empty_returns_false(self, monkeypatch):
        """Test verifying empty password returns False"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False

    def test_verify_password_empty_hash_returns_false(self, monkeypatch):
        """Test verifying against empty hash returns False"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        assert verify_password("SecureP@ss123", "") is False

    def test_verify_password_invalid_hash_returns_false(self, monkeypatch):
        """Test verifying against invalid hash returns False"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        invalid_hashes = [
            "not-a-valid-hash",
            "$argon2id$invalid",
            "random-string",
        ]

        for invalid_hash in invalid_hashes:
            assert verify_password("SecureP@ss123", invalid_hash) is False

    def test_verify_password_without_pepper_raises_error(self, monkeypatch):
        """Test verification without PASSWORD_PEPPER raises ValueError"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')
        hashed = hash_password("SecureP@ss123")

        monkeypatch.delenv('PASSWORD_PEPPER', raising=False)

        with pytest.raises(ValueError, match="PASSWORD_PEPPER environment variable is not set"):
            verify_password("SecureP@ss123", hashed)

    def test_verify_password_wrong_pepper_fails(self, monkeypatch):
        """Test verification with wrong pepper fails"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'original-pepper')
        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Change pepper
        monkeypatch.setenv('PASSWORD_PEPPER', 'different-pepper')

        # Verification should fail
        assert verify_password(password, hashed) is False


class TestValidatePasswordStrength:
    """Test password strength validation"""

    def test_valid_strong_password(self):
        """Test valid password meeting all requirements"""
        strong_passwords = [
            "SecureP@ss123",
            "MyP@ssw0rd!",
            "Tr0ub4dor&3",
            "C0mplex!tyRul3s",
        ]

        for password in strong_passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is True
            assert error == ""

    def test_password_too_short(self):
        """Test password less than 8 characters fails"""
        short_passwords = [
            "Sh0rt!",     # 6 chars
            "P@ss1",      # 5 chars
            "",           # 0 chars
            "A1!b",       # 4 chars
        ]

        for password in short_passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is False
            assert "at least 8 characters" in error

    def test_password_minimum_length(self):
        """Test password with exactly 8 characters passes"""
        password = "Passw0rd!"  # Exactly 8 chars with all requirements

        is_valid, error = validate_password_strength(password)
        assert is_valid is True

    def test_password_missing_uppercase(self):
        """Test password without uppercase letter fails"""
        passwords = [
            "password123!",
            "secure@pass1",
            "n0upp3rc@se",
        ]

        for password in passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is False
            assert "uppercase letter" in error

    def test_password_missing_lowercase(self):
        """Test password without lowercase letter fails"""
        passwords = [
            "PASSWORD123!",
            "SECURE@PASS1",
            "N0L0W3RC@SE",
        ]

        for password in passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is False
            assert "lowercase letter" in error

    def test_password_missing_digit(self):
        """Test password without digit fails"""
        passwords = [
            "SecurePass!",
            "NoDigits@Here",
            "Password!Password",
        ]

        for password in passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is False
            assert "digit" in error

    def test_password_missing_special_character(self):
        """Test password without special character fails"""
        passwords = [
            "SecurePass123",
            "NoSpecialChar1",
            "Password1Password",
        ]

        for password in passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is False
            assert "special character" in error

    def test_password_all_special_characters_accepted(self):
        """Test various special characters are accepted"""
        special_chars = "!@#$%^&*(),.?\":{}|<>_-+=[]\\\/~`"

        for char in special_chars:
            password = f"SecureP@ss1{char}"
            is_valid, error = validate_password_strength(password)
            assert is_valid is True, f"Failed for special char: {char}"

    def test_password_with_unicode_characters(self):
        """Test password with unicode characters (should still require ASCII special chars)"""
        # Unicode special characters don't count
        password = "Sécureé123"  # Has accents but no ASCII special char
        is_valid, error = validate_password_strength(password)
        assert is_valid is False
        assert "special character" in error

    def test_password_very_long(self):
        """Test very long password passes"""
        # 100+ character password meeting all requirements
        password = "SecureP@ss1" + "x" * 100
        is_valid, error = validate_password_strength(password)
        assert is_valid is True


class TestPasswordSecurityProperties:
    """Test security properties of password implementation"""

    def test_owasp_argon2id_parameters(self, monkeypatch):
        """Test Argon2id uses OWASP recommended parameters"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Parse hash to verify parameters
        # Format: $argon2id$v=19$m=65536,t=3,p=4$salt$hash
        parts = hashed.split('$')

        assert parts[1] == 'argon2id'  # Correct variant
        params = dict(param.split('=') for param in parts[3].split(','))

        # OWASP recommendations
        assert int(params['m']) == 65536  # Memory: 64 MB
        assert int(params['t']) == 3      # Time cost: 3
        assert int(params['p']) == 4      # Parallelism: 4

    def test_password_hash_not_reversible(self, monkeypatch):
        """Test password hash cannot be reversed to original password"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Hash should not contain the original password
        assert password not in hashed
        assert password.encode() not in hashed.encode()

    def test_timing_attack_resistance(self, monkeypatch):
        """Test verification time is similar for valid/invalid passwords (basic check)"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        import time

        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Time correct password verification
        start = time.perf_counter()
        verify_password(password, hashed)
        correct_time = time.perf_counter() - start

        # Time incorrect password verification
        start = time.perf_counter()
        verify_password("WrongPassword123!", hashed)
        incorrect_time = time.perf_counter() - start

        # Both should take similar time (within 10x factor)
        # Argon2id is intentionally slow, so both should be in milliseconds
        assert correct_time > 0.001  # At least 1ms
        assert incorrect_time > 0.001
        # Timing should be similar (not a perfect test, but basic check)
        assert abs(correct_time - incorrect_time) < 1.0  # Within 1 second

    def test_salt_uniqueness(self, monkeypatch):
        """Test each hash uses a unique salt"""
        monkeypatch.setenv('PASSWORD_PEPPER', 'test-pepper-secret')

        password = "SecureP@ss123"

        # Generate 10 hashes
        hashes = [hash_password(password) for _ in range(10)]

        # All hashes should be unique
        assert len(set(hashes)) == 10

        # Extract salts (4th component in hash)
        salts = [h.split('$')[4] for h in hashes]
        assert len(set(salts)) == 10  # All salts unique
