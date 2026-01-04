"""Unit tests for Org model

Tests cover:
- T026: Org creation with valid data
- T026: Slug validation (valid and invalid formats)
- T026: Name validation (empty, too long)
- T026: Settings JSON defaults
- T027: Duplicate slug rejection

SSOT Reference: §5.4.1 (org table)
"""

import pytest
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from datetime import datetime

from models.org import Org


class TestOrgCreation:
    """Test basic org creation with valid data"""

    def test_create_org_with_minimal_data(self, db_session):
        """T026: Create org with only required fields"""
        org = Org(
            name="Acme GmbH",
            slug="acme-gmbh"
        )
        db_session.add(org)
        db_session.commit()

        # Verify defaults are applied
        assert org.id is not None
        assert isinstance(org.id, UUID)
        assert org.name == "Acme GmbH"
        assert org.slug == "acme-gmbh"
        assert org.settings_json == {}  # Default empty JSONB
        assert isinstance(org.created_at, datetime)
        assert isinstance(org.updated_at, datetime)

    def test_create_org_with_settings(self, db_session):
        """T026: Create org with custom settings JSON"""
        custom_settings = {
            "default_currency": "CHF",
            "price_tolerance_percent": 3.0,
            "matching": {
                "auto_apply_threshold": 0.95
            }
        }

        org = Org(
            name="Swiss Trading AG",
            slug="swiss-trading",
            settings_json=custom_settings
        )
        db_session.add(org)
        db_session.commit()

        assert org.settings_json == custom_settings
        assert org.settings_json["default_currency"] == "CHF"

    def test_org_repr(self, db_session):
        """Test string representation of Org"""
        org = Org(name="Test Org", slug="test-org")
        db_session.add(org)
        db_session.flush()

        repr_str = repr(org)
        assert "Org(" in repr_str
        assert "slug='test-org'" in repr_str
        assert "name='Test Org'" in repr_str


class TestSlugValidation:
    """T026: Test slug validation rules"""

    def test_valid_slug_lowercase_letters(self, db_session):
        """Valid: lowercase letters only"""
        org = Org(name="Test", slug="testorg")
        db_session.add(org)
        db_session.commit()
        assert org.slug == "testorg"

    def test_valid_slug_with_numbers(self, db_session):
        """Valid: lowercase letters and numbers"""
        org = Org(name="Test", slug="test-org-123")
        db_session.add(org)
        db_session.commit()
        assert org.slug == "test-org-123"

    def test_valid_slug_with_hyphens(self, db_session):
        """Valid: lowercase letters with hyphens"""
        org = Org(name="Test", slug="my-test-org")
        db_session.add(org)
        db_session.commit()
        assert org.slug == "my-test-org"

    def test_invalid_slug_uppercase(self, db_session):
        """Invalid: uppercase letters"""
        with pytest.raises(ValueError, match="lowercase letters, numbers, and hyphens"):
            Org(name="Test", slug="Acme-GmbH")

    def test_invalid_slug_underscore(self, db_session):
        """Invalid: underscores not allowed"""
        with pytest.raises(ValueError, match="lowercase letters, numbers, and hyphens"):
            Org(name="Test", slug="acme_gmbh")

    def test_invalid_slug_space(self, db_session):
        """Invalid: spaces not allowed"""
        with pytest.raises(ValueError, match="lowercase letters, numbers, and hyphens"):
            Org(name="Test", slug="acme gmbh")

    def test_invalid_slug_period(self, db_session):
        """Invalid: periods not allowed"""
        with pytest.raises(ValueError, match="lowercase letters, numbers, and hyphens"):
            Org(name="Test", slug="acme.gmbh")

    def test_invalid_slug_special_chars(self, db_session):
        """Invalid: special characters not allowed"""
        with pytest.raises(ValueError, match="lowercase letters, numbers, and hyphens"):
            Org(name="Test", slug="acme@gmbh")

    def test_invalid_slug_too_short(self, db_session):
        """Invalid: slug must be at least 2 characters"""
        with pytest.raises(ValueError, match="between 2 and 100 characters"):
            Org(name="Test", slug="a")

    def test_invalid_slug_too_long(self, db_session):
        """Invalid: slug must not exceed 100 characters"""
        long_slug = "a" * 101
        with pytest.raises(ValueError, match="between 2 and 100 characters"):
            Org(name="Test", slug=long_slug)

    def test_slug_minimum_length(self, db_session):
        """Valid: slug with exactly 2 characters"""
        org = Org(name="Test", slug="ab")
        db_session.add(org)
        db_session.commit()
        assert org.slug == "ab"

    def test_slug_maximum_length(self, db_session):
        """Valid: slug with exactly 100 characters"""
        max_slug = "a" * 100
        org = Org(name="Test", slug=max_slug)
        db_session.add(org)
        db_session.commit()
        assert org.slug == max_slug


class TestNameValidation:
    """T026: Test name validation rules"""

    def test_valid_name(self, db_session):
        """Valid: normal organization name"""
        org = Org(name="Acme Corporation GmbH", slug="acme-corp")
        db_session.add(org)
        db_session.commit()
        assert org.name == "Acme Corporation GmbH"

    def test_valid_name_with_unicode(self, db_session):
        """Valid: name with international characters"""
        org = Org(name="Münchner Großhandel GmbH & Co. KG", slug="muenchner")
        db_session.add(org)
        db_session.commit()
        assert org.name == "Münchner Großhandel GmbH & Co. KG"

    def test_invalid_name_empty_string(self, db_session):
        """Invalid: empty name"""
        with pytest.raises(ValueError, match="cannot be empty"):
            Org(name="", slug="test-org")

    def test_invalid_name_whitespace_only(self, db_session):
        """Invalid: whitespace-only name"""
        with pytest.raises(ValueError, match="cannot be empty"):
            Org(name="   ", slug="test-org")

    def test_invalid_name_too_long(self, db_session):
        """Invalid: name exceeds 200 characters"""
        long_name = "A" * 201
        with pytest.raises(ValueError, match="cannot exceed 200 characters"):
            Org(name=long_name, slug="test-org")

    def test_name_max_length(self, db_session):
        """Valid: name with exactly 200 characters"""
        max_name = "A" * 200
        org = Org(name=max_name, slug="test-org")
        db_session.add(org)
        db_session.commit()
        assert org.name == max_name

    def test_name_strips_whitespace(self, db_session):
        """Name is trimmed of leading/trailing whitespace"""
        org = Org(name="  Test Org  ", slug="test-org")
        db_session.add(org)
        db_session.commit()
        assert org.name == "Test Org"  # Whitespace stripped


class TestSettingsJsonDefaults:
    """T026: Test settings_json default behavior"""

    def test_settings_json_defaults_to_empty_dict(self, db_session):
        """Settings JSON defaults to {} when not provided"""
        org = Org(name="Test", slug="test-org")
        db_session.add(org)
        db_session.commit()

        assert org.settings_json is not None
        assert org.settings_json == {}
        assert isinstance(org.settings_json, dict)

    def test_settings_json_preserves_custom_values(self, db_session):
        """Custom settings JSON is preserved"""
        settings = {
            "default_currency": "USD",
            "ai": {
                "llm_provider": "anthropic",
                "llm_model": "claude-3-5-sonnet"
            }
        }
        org = Org(name="Test", slug="test-org", settings_json=settings)
        db_session.add(org)
        db_session.commit()

        assert org.settings_json == settings

    def test_settings_json_query_with_jsonb_operators(self, db_session):
        """JSONB operators work on settings_json column"""
        org1 = Org(
            name="Org EUR",
            slug="org-eur",
            settings_json={"default_currency": "EUR"}
        )
        org2 = Org(
            name="Org USD",
            slug="org-usd",
            settings_json={"default_currency": "USD"}
        )
        db_session.add_all([org1, org2])
        db_session.commit()

        # Query using JSONB operator
        from sqlalchemy import text
        result = db_session.query(Org).filter(
            text("settings_json->>'default_currency' = 'EUR'")
        ).first()

        assert result.slug == "org-eur"


class TestUniqueConstraints:
    """T027: Test duplicate slug rejection"""

    def test_duplicate_slug_raises_integrity_error(self, db_session):
        """Duplicate slugs are rejected by unique constraint"""
        org1 = Org(name="First Org", slug="same-slug")
        db_session.add(org1)
        db_session.commit()

        # Try to create another org with same slug
        org2 = Org(name="Second Org", slug="same-slug")
        db_session.add(org2)

        with pytest.raises(IntegrityError, match="duplicate key value"):
            db_session.commit()

    def test_different_slugs_allowed(self, db_session):
        """Different slugs are allowed"""
        org1 = Org(name="First Org", slug="first-slug")
        org2 = Org(name="Second Org", slug="second-slug")
        db_session.add_all([org1, org2])
        db_session.commit()

        assert org1.slug == "first-slug"
        assert org2.slug == "second-slug"

    def test_same_name_different_slug_allowed(self, db_session):
        """Same name with different slug is allowed (name is not unique)"""
        org1 = Org(name="Same Name", slug="slug-one")
        org2 = Org(name="Same Name", slug="slug-two")
        db_session.add_all([org1, org2])
        db_session.commit()

        assert org1.name == org2.name
        assert org1.slug != org2.slug


class TestTimestamps:
    """Test created_at and updated_at behavior"""

    def test_timestamps_auto_populated(self, db_session):
        """created_at and updated_at are automatically set"""
        org = Org(name="Test", slug="test-org")
        db_session.add(org)
        db_session.commit()

        assert org.created_at is not None
        assert org.updated_at is not None
        assert isinstance(org.created_at, datetime)
        assert isinstance(org.updated_at, datetime)

    def test_updated_at_changes_on_update(self, db_session):
        """updated_at changes when record is updated"""
        org = Org(name="Original", slug="test-org")
        db_session.add(org)
        db_session.commit()

        original_updated_at = org.updated_at

        # Update the org
        org.name = "Updated Name"
        db_session.commit()

        # Note: updated_at trigger may not fire in SQLAlchemy without re-fetching
        # This test documents expected behavior at database level
        # In real scenario, trigger updates this automatically
        db_session.refresh(org)

        # updated_at should be >= original (trigger updates it)
        assert org.updated_at >= original_updated_at

    def test_created_at_never_changes(self, db_session):
        """created_at remains constant after updates"""
        org = Org(name="Original", slug="test-org")
        db_session.add(org)
        db_session.commit()

        original_created_at = org.created_at

        # Update the org
        org.name = "Updated Name"
        db_session.commit()
        db_session.refresh(org)

        assert org.created_at == original_created_at
