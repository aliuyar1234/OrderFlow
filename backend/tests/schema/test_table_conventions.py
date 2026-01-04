"""
Schema verification tests for database table conventions.

Ensures all tables follow OrderFlow's architectural standards:
- Every table has required base columns (id, created_at, updated_at)
- org table is the root entity (no org_id on itself)
- All other tables have org_id foreign key for multi-tenant isolation
- All timestamps use TIMESTAMPTZ
- Foreign key constraints are properly defined

SSOT Reference: §5.1 (Database Conventions), CLAUDE.md (Database Conventions)
"""

import pytest
from sqlalchemy import inspect, MetaData
from sqlalchemy.engine import Engine
from sqlalchemy.types import UUID, DateTime


class TestTableConventions:
    """Verify all tables follow OrderFlow database conventions."""

    @pytest.fixture(scope="class")
    def inspector(self, engine: Engine):
        """Create SQLAlchemy inspector for schema introspection."""
        return inspect(engine)

    @pytest.fixture(scope="class")
    def metadata(self, engine: Engine):
        """Reflect database metadata."""
        meta = MetaData()
        meta.reflect(bind=engine)
        return meta

    @pytest.fixture(scope="class")
    def all_tables(self, inspector):
        """Get list of all tables in the database."""
        # Exclude alembic_version table from checks
        return [t for t in inspector.get_table_names() if t != "alembic_version"]

    def test_org_table_exists(self, all_tables):
        """Verify the org table exists as the root tenant entity."""
        assert "org" in all_tables, "org table must exist as root tenant entity"

    def test_all_tables_have_id_column(self, inspector, all_tables):
        """Verify every table has an 'id' column with UUID type and primary key."""
        for table_name in all_tables:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            assert "id" in columns, f"Table '{table_name}' missing 'id' column"

            id_col = columns["id"]
            assert isinstance(
                id_col["type"], UUID
            ), f"Table '{table_name}' id column must be UUID type, got {type(id_col['type']).__name__}"

            # Check if id is primary key
            pk_constraint = inspector.get_pk_constraint(table_name)
            assert (
                "id" in pk_constraint["constrained_columns"]
            ), f"Table '{table_name}' id column must be primary key"

    def test_all_tables_have_timestamps(self, inspector, all_tables):
        """Verify every table has created_at and updated_at columns with TIMESTAMPTZ."""
        for table_name in all_tables:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            # Check created_at exists
            assert (
                "created_at" in columns
            ), f"Table '{table_name}' missing 'created_at' column"
            created_at = columns["created_at"]
            assert isinstance(
                created_at["type"], DateTime
            ), f"Table '{table_name}' created_at must be DateTime type"
            assert (
                created_at["type"].timezone
            ), f"Table '{table_name}' created_at must be TIMESTAMPTZ (timezone-aware)"
            assert (
                not created_at["nullable"]
            ), f"Table '{table_name}' created_at must be NOT NULL"

            # Check updated_at exists
            assert (
                "updated_at" in columns
            ), f"Table '{table_name}' missing 'updated_at' column"
            updated_at = columns["updated_at"]
            assert isinstance(
                updated_at["type"], DateTime
            ), f"Table '{table_name}' updated_at must be DateTime type"
            assert (
                updated_at["type"].timezone
            ), f"Table '{table_name}' updated_at must be TIMESTAMPTZ (timezone-aware)"
            assert (
                not updated_at["nullable"]
            ), f"Table '{table_name}' updated_at must be NOT NULL"

    def test_org_table_has_no_org_id(self, inspector):
        """Verify org table does NOT have org_id (it's the root entity)."""
        columns = {col["name"] for col in inspector.get_columns("org")}
        assert (
            "org_id" not in columns
        ), "org table must NOT have org_id (it's the root tenant entity)"

    def test_non_org_tables_have_org_id(self, inspector, all_tables):
        """Verify all tables except org have org_id column with NOT NULL constraint."""
        # Exclude org table and any future global system tables
        global_tables = {"org"}
        tenant_tables = [t for t in all_tables if t not in global_tables]

        if not tenant_tables:
            pytest.skip("No tenant-scoped tables exist yet besides org")

        for table_name in tenant_tables:
            columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            assert (
                "org_id" in columns
            ), f"Table '{table_name}' missing 'org_id' column for multi-tenant isolation"

            org_id_col = columns["org_id"]
            assert isinstance(
                org_id_col["type"], UUID
            ), f"Table '{table_name}' org_id must be UUID type, got {type(org_id_col['type']).__name__}"
            assert (
                not org_id_col["nullable"]
            ), f"Table '{table_name}' org_id must be NOT NULL"

    def test_org_id_foreign_key_constraints(self, inspector, all_tables):
        """Verify all org_id columns have foreign key constraint to org.id."""
        global_tables = {"org"}
        tenant_tables = [t for t in all_tables if t not in global_tables]

        if not tenant_tables:
            pytest.skip("No tenant-scoped tables exist yet besides org")

        for table_name in tenant_tables:
            foreign_keys = inspector.get_foreign_keys(table_name)

            # Find org_id foreign key
            org_fks = [
                fk for fk in foreign_keys if "org_id" in fk["constrained_columns"]
            ]

            assert (
                len(org_fks) > 0
            ), f"Table '{table_name}' org_id must have foreign key constraint to org(id)"

            org_fk = org_fks[0]
            assert (
                org_fk["referred_table"] == "org"
            ), f"Table '{table_name}' org_id must reference org table, got {org_fk['referred_table']}"
            assert (
                "id" in org_fk["referred_columns"]
            ), f"Table '{table_name}' org_id must reference org.id column"

    def test_org_table_has_required_columns(self, inspector):
        """Verify org table has all required columns per SSOT §5.4.1."""
        columns = {col["name"] for col in inspector.get_columns("org")}

        required_columns = {
            "id",
            "name",
            "slug",
            "settings_json",
            "created_at",
            "updated_at",
        }

        missing = required_columns - columns
        assert (
            not missing
        ), f"org table missing required columns: {', '.join(missing)}"

    def test_org_slug_has_unique_constraint(self, inspector):
        """Verify org.slug has unique constraint."""
        indexes = inspector.get_indexes("org")
        unique_indexes = inspector.get_unique_constraints("org")

        # Check if slug has unique constraint or unique index
        slug_unique = False

        # Check unique constraints
        for constraint in unique_indexes:
            if "slug" in constraint["column_names"]:
                slug_unique = True
                break

        # Check unique indexes
        for index in indexes:
            if "slug" in index["column_names"] and index.get("unique", False):
                slug_unique = True
                break

        assert slug_unique, "org.slug must have unique constraint"

    def test_no_plain_timestamp_types(self, inspector, all_tables):
        """Verify no tables use plain TIMESTAMP (must use TIMESTAMPTZ)."""
        for table_name in all_tables:
            columns = inspector.get_columns(table_name)

            for col in columns:
                if isinstance(col["type"], DateTime):
                    assert (
                        col["type"].timezone
                    ), f"Table '{table_name}' column '{col['name']}' must use TIMESTAMPTZ, not plain TIMESTAMP"

    def test_table_naming_conventions(self, all_tables):
        """Verify tables follow snake_case naming conventions."""
        for table_name in all_tables:
            # Table names should be lowercase and use underscores
            assert (
                table_name.islower()
            ), f"Table '{table_name}' must use lowercase naming"
            assert (
                " " not in table_name
            ), f"Table '{table_name}' must not contain spaces"
            # Allow underscores and alphanumeric characters
            assert all(
                c.isalnum() or c == "_" for c in table_name
            ), f"Table '{table_name}' must use snake_case (alphanumeric + underscores only)"
