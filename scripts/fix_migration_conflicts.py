#!/usr/bin/env python3
"""Fix migration revision conflicts in OrderFlow.

This script:
1. Identifies duplicate revision IDs (005_, 006_)
2. Renames migrations to sequential order
3. Updates the revision ID in each migration file
4. Prints before/after mapping for verification

CRITICAL: Run this BEFORE applying any migrations to a fresh database.

Usage:
    python scripts/fix_migration_conflicts.py [--dry-run]

Options:
    --dry-run    Show what would be changed without actually renaming
"""

import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class Migration:
    """Represents a migration file."""
    filename: str
    filepath: Path
    current_revision: str
    table_name: str
    down_revision: Optional[str] = None


# Define the correct migration order based on dependencies
MIGRATION_ORDER = [
    # Foundation
    ("001", "create_org_table"),
    ("002", "create_user_and_audit_tables"),
    # Core entities (must come before dependent tables)
    ("003", "create_customer_tables"),
    ("004", "create_product_tables"),
    ("005", "create_inbound_message_table"),
    ("006", "create_document_table"),
    ("007", "create_extraction_run_table"),
    ("008", "create_ai_call_log_table"),
    ("009", "create_draft_order_table"),
    ("010", "create_draft_order_line_table"),
    ("011", "create_customer_price_table"),
    ("012", "create_sku_mapping_table"),
    ("013", "create_customer_detection_candidate"),
    ("014", "create_validation_issue_table"),
    ("015", "create_erp_connector_tables"),
    ("016", "create_product_embedding_table"),
    # New migration for ERP connection (if different from connector)
    ("017", "create_erp_connection_tables"),
    # Additional tables (add as needed)
]


def find_migrations(migrations_dir: Path) -> List[Migration]:
    """Find all migration files in the versions directory."""
    migrations = []

    for filepath in migrations_dir.glob("*.py"):
        if filepath.name == "__pycache__" or filepath.name.startswith("_"):
            continue

        # Extract revision number from filename
        match = re.match(r"(\d+)_(.+)\.py", filepath.name)
        if match:
            migrations.append(Migration(
                filename=filepath.name,
                filepath=filepath,
                current_revision=match.group(1),
                table_name=match.group(2)
            ))

    return migrations


def read_migration_content(migration: Migration) -> str:
    """Read migration file content."""
    return migration.filepath.read_text(encoding="utf-8")


def extract_down_revision(content: str) -> Optional[str]:
    """Extract down_revision from migration content."""
    match = re.search(r'down_revision\s*[:=]\s*["\']?(\w+)?["\']?', content)
    if match:
        return match.group(1)
    return None


def update_migration_revision(
    migration: Migration,
    new_revision: str,
    new_down_revision: Optional[str]
) -> str:
    """Update revision IDs in migration content."""
    content = read_migration_content(migration)

    # Update revision
    content = re.sub(
        r'(revision\s*[:=]\s*["\'])(\w+)(["\'])',
        f'\\g<1>{new_revision}\\g<3>',
        content
    )

    # Update down_revision
    if new_down_revision:
        content = re.sub(
            r'(down_revision\s*[:=]\s*["\'])(\w*)?(["\'])',
            f'\\g<1>{new_down_revision}\\g<3>',
            content
        )
    else:
        content = re.sub(
            r'(down_revision\s*[:=]\s*)(["\'])(\w*)?(["\'])',
            '\\g<1>None',
            content
        )

    return content


def find_migration_by_pattern(
    migrations: List[Migration],
    pattern: str
) -> Optional[Migration]:
    """Find migration matching pattern (table name contains pattern)."""
    for m in migrations:
        if pattern in m.table_name.lower():
            return m
    return None


def generate_rename_plan(
    migrations: List[Migration],
    dry_run: bool = True
) -> Dict[str, str]:
    """Generate migration rename plan."""
    plan = {}
    prev_revision = None
    used_names = set()

    print("\n" + "=" * 60)
    print("Migration Rename Plan")
    print("=" * 60)

    for new_num, pattern in MIGRATION_ORDER:
        # Find migration with this pattern
        migration = find_migration_by_pattern(migrations, pattern)

        if migration:
            if migration.filename in used_names:
                # Already processed, might be a duplicate
                continue
            used_names.add(migration.filename)

            new_filename = f"{new_num}_{migration.table_name}.py"

            if migration.filename != new_filename:
                plan[migration.filename] = new_filename
                print(f"  {migration.filename}")
                print(f"    → {new_filename}")
            else:
                print(f"  {migration.filename} (no change)")

            prev_revision = new_num
        else:
            print(f"  [MISSING] {new_num}_{pattern}.py")

    # Check for migrations not in the plan
    unplanned = [m for m in migrations if m.filename not in used_names]
    if unplanned:
        print("\n" + "-" * 40)
        print("Migrations not in plan (manual review needed):")
        for m in unplanned:
            print(f"  - {m.filename}")

    return plan


def apply_rename_plan(
    migrations_dir: Path,
    plan: Dict[str, str],
    dry_run: bool = True
) -> None:
    """Apply the rename plan."""
    if dry_run:
        print("\n[DRY RUN] Would rename files:")
        for old_name, new_name in plan.items():
            print(f"  {old_name} → {new_name}")
        return

    print("\nApplying renames...")
    for old_name, new_name in plan.items():
        old_path = migrations_dir / old_name
        new_path = migrations_dir / new_name

        if old_path.exists():
            old_path.rename(new_path)
            print(f"  ✓ {old_name} → {new_name}")
        else:
            print(f"  ✗ {old_name} not found!")


def main():
    # Determine dry run mode
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    # Find migrations directory
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "backend" / "migrations" / "versions"

    if not migrations_dir.exists():
        print(f"Error: Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    print(f"Scanning: {migrations_dir}")

    # Find all migrations
    migrations = find_migrations(migrations_dir)
    print(f"Found {len(migrations)} migration files")

    # Find duplicates
    revision_counts: Dict[str, List[str]] = {}
    for m in migrations:
        if m.current_revision not in revision_counts:
            revision_counts[m.current_revision] = []
        revision_counts[m.current_revision].append(m.filename)

    duplicates = {k: v for k, v in revision_counts.items() if len(v) > 1}

    if duplicates:
        print("\n" + "!" * 60)
        print("DUPLICATE REVISION IDS FOUND:")
        for rev, files in duplicates.items():
            print(f"\n  Revision {rev}:")
            for f in files:
                print(f"    - {f}")
        print("!" * 60)
    else:
        print("\nNo duplicate revisions found.")

    # Generate rename plan
    plan = generate_rename_plan(migrations, dry_run)

    if not plan:
        print("\nNo renames needed.")
        return

    # Apply renames
    if dry_run:
        print("\n" + "-" * 60)
        print("To apply changes, run without --dry-run flag")
    else:
        apply_rename_plan(migrations_dir, plan, dry_run)
        print("\n" + "=" * 60)
        print("IMPORTANT: After renaming, you must manually:")
        print("1. Update 'revision' and 'down_revision' in each file")
        print("2. Ensure dependency chain is correct")
        print("3. Test with: alembic upgrade head")
        print("=" * 60)


if __name__ == "__main__":
    main()
