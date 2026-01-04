"""Test database table conventions and constraints.

Verifies that all multi-tenant tables follow SSOT §5.1 conventions:
- org_id UUID NOT NULL
- Foreign key constraint to org(id)
- Proper indexing on org_id
- Standard timestamp columns

SSOT Reference: §5.1 (Database Conventions)

NOTE: These tests require PostgreSQL. They are skipped on SQLite.
"""

import pytest
from sqlalchemy import inspect, create_engine
import os
import sys
from pathlib import Path

# Add src to path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

# Setup test database
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///:memory:"
)

# Skip entire module if using SQLite
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL.startswith("sqlite"),
    reason="Table convention tests require PostgreSQL (uses gen_random_uuid, JSONB)"
)


# Tables that MUST have org_id (multi-tenant)
MULTI_TENANT_TABLES = [
    "user",
    "audit_log",
    "document",
    "inbound_message",
    "draft_order",
    "draft_order_line",
    "extraction_run",
    "sku_mapping",
    "product",
    "customer",
    "customer_price",
    "validation_issue",
    "erp_export",
    "ai_call_log",
]

# Global tables that should NOT have org_id
GLOBAL_TABLES = [
    "org",
]

# All tables must have these timestamp columns
REQUIRED_TIMESTAMP_COLUMNS = ["created_at", "updated_at"]

# Tables that are append-only (no updated_at needed)
APPEND_ONLY_TABLES = [
    "audit_log",  # Immutable security log
    "ai_call_log",  # Immutable AI call telemetry
]


@pytest.fixture(scope="module")
def pg_engine():
    """Create PostgreSQL engine and ensure tables exist.

    This fixture only runs if we're on PostgreSQL (skip for SQLite).
    """
    if TEST_DATABASE_URL.startswith("sqlite"):
        pytest.skip("Requires PostgreSQL")

    engine = create_engine(TEST_DATABASE_URL)

    # Import models and create tables
    from models.base import Base
    from models.user import User
    from models.org import Org
    from models.audit_log import AuditLog
    from models.document import Document
    from models.inbound_message import InboundMessage
    from models.draft_order import DraftOrder, DraftOrderLine
    from models.extraction_run import ExtractionRun
    from models.sku_mapping import SkuMapping
    from models.product import Product
    from models.customer import Customer
    from models.customer_price import CustomerPrice
    from models.validation_issue import ValidationIssue
    from models.erp_export import ERPExport
    from models.ai_call_log import AICallLog
    from models.erp_connection import ERPConnection
    from models.erp_push_log import ERPPushLog

    Base.metadata.create_all(bind=engine)

    return engine


class TestMultiTenantTableConventions:
    """Tests for multi-tenant table conventions."""

    def test_multi_tenant_tables_have_org_id(self, pg_engine):
        """Verify all multi-tenant tables have org_id column."""
        inspector = inspect(pg_engine)

        for table_name in MULTI_TENANT_TABLES:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            # Check org_id column exists
            assert "org_id" in columns, \
                f"Table '{table_name}' is missing required org_id column"

            org_id_col = columns["org_id"]

            # Check org_id is UUID type
            assert "uuid" in str(org_id_col["type"]).lower(), \
                f"Table '{table_name}' org_id must be UUID type, got {org_id_col['type']}"

    def test_org_id_not_nullable(self, pg_engine):
        """Verify org_id is NOT NULL on all multi-tenant tables."""
        inspector = inspect(pg_engine)

        for table_name in MULTI_TENANT_TABLES:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            assert "org_id" in columns, f"Table '{table_name}' missing org_id"

            org_id_col = columns["org_id"]

            # Check NOT NULL constraint (nullable=False)
            assert not org_id_col["nullable"], \
                f"Table '{table_name}' org_id must be NOT NULL (currently allows NULL)"

    def test_org_id_foreign_key_constraint(self, pg_engine):
        """Verify org_id has foreign key constraint to org(id)."""
        inspector = inspect(pg_engine)

        for table_name in MULTI_TENANT_TABLES:
            foreign_keys = inspector.get_foreign_keys(table_name)

            # Find org_id foreign key
            org_fk = next(
                (fk for fk in foreign_keys if "org_id" in fk["constrained_columns"]),
                None
            )

            assert org_fk is not None, \
                f"Table '{table_name}' missing foreign key constraint on org_id"

            # Verify it references org(id)
            assert org_fk["referred_table"] == "org", \
                f"Table '{table_name}' org_id must reference 'org' table, got '{org_fk['referred_table']}'"

            assert "id" in org_fk["referred_columns"], \
                f"Table '{table_name}' org_id must reference org.id column"

    def test_org_id_indexed(self, pg_engine):
        """Verify org_id has index for query performance."""
        inspector = inspect(pg_engine)

        for table_name in MULTI_TENANT_TABLES:
            indexes = inspector.get_indexes(table_name)

            # Find index on org_id (may be composite or single-column)
            org_id_indexed = any(
                "org_id" in idx["column_names"]
                for idx in indexes
            )

            assert org_id_indexed, \
                f"Table '{table_name}' should have index on org_id for performance"


class TestGlobalTableConventions:
    """Tests for global (non-tenant) table conventions."""

    def test_global_tables_no_org_id(self, pg_engine):
        """Verify global tables do NOT have org_id column."""
        inspector = inspect(pg_engine)

        for table_name in GLOBAL_TABLES:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            assert "org_id" not in columns, \
                f"Global table '{table_name}' should NOT have org_id column"


class TestTableStructure:
    """Tests for common table structure conventions."""

    def test_all_tables_have_id_primary_key(self, pg_engine):
        """Verify all tables have id UUID primary key."""
        inspector = inspect(pg_engine)
        all_tables = MULTI_TENANT_TABLES + GLOBAL_TABLES

        for table_name in all_tables:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}
            pk_constraint = inspector.get_pk_constraint(table_name)

            # Check id column exists
            assert "id" in columns, f"Table '{table_name}' missing id column"

            id_col = columns["id"]

            # Check id is UUID type
            assert "uuid" in str(id_col["type"]).lower(), \
                f"Table '{table_name}' id must be UUID type, got {id_col['type']}"

            # Check id is primary key
            assert "id" in pk_constraint["constrained_columns"], \
                f"Table '{table_name}' id must be primary key"

    def test_all_tables_have_timestamps(self, pg_engine):
        """Verify all tables have created_at and updated_at columns."""
        inspector = inspect(pg_engine)
        all_tables = MULTI_TENANT_TABLES + GLOBAL_TABLES

        for table_name in all_tables:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            for timestamp_col in REQUIRED_TIMESTAMP_COLUMNS:
                # Skip updated_at for append-only tables
                if timestamp_col == "updated_at" and table_name in APPEND_ONLY_TABLES:
                    continue

                assert timestamp_col in columns, \
                    f"Table '{table_name}' missing required '{timestamp_col}' column"

                col = columns[timestamp_col]

                # Check it's a timestamp type
                col_type_str = str(col["type"]).lower()
                assert "timestamp" in col_type_str or "datetime" in col_type_str, \
                    f"Table '{table_name}' {timestamp_col} must be TIMESTAMP type, got {col['type']}"

    def test_timestamps_not_nullable(self, pg_engine):
        """Verify created_at and updated_at are NOT NULL."""
        inspector = inspect(pg_engine)
        all_tables = MULTI_TENANT_TABLES + GLOBAL_TABLES

        for table_name in all_tables:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            for timestamp_col in REQUIRED_TIMESTAMP_COLUMNS:
                if timestamp_col in columns:
                    col = columns[timestamp_col]

                    assert not col["nullable"], \
                        f"Table '{table_name}' {timestamp_col} must be NOT NULL"
