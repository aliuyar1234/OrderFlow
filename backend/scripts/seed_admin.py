#!/usr/bin/env python
"""Seed script to create initial admin user.

This script creates the first admin user for an organization. It should be run
once during initial setup. The admin can then create additional users through
the API.

Usage:
    python backend/scripts/seed_admin.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    PASSWORD_PEPPER: Password hashing pepper (required)
    ADMIN_EMAIL: Email for admin user (default: admin@example.com)
    ADMIN_PASSWORD: Password for admin user (default: AdminP@ss123)
    ADMIN_NAME: Display name for admin user (default: System Administrator)
    ORG_ID: Organization UUID (must exist in database)
"""

import os
import sys
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(backend_src))

from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.user import User
from auth.password import hash_password, validate_password_strength


def main():
    """Create initial admin user."""
    # Get configuration from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://orderflow:dev_password@localhost:5432/orderflow"
    )

    org_id_str = os.getenv("ORG_ID")
    if not org_id_str:
        print("ERROR: ORG_ID environment variable is required")
        print("Example: ORG_ID=7c9e6679-7425-40de-944b-e07fc1f90ae7 python seed_admin.py")
        sys.exit(1)

    try:
        org_id = UUID(org_id_str)
    except ValueError:
        print(f"ERROR: Invalid ORG_ID format: {org_id_str}")
        print("ORG_ID must be a valid UUID")
        sys.exit(1)

    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "AdminP@ss123")
    admin_name = os.getenv("ADMIN_NAME", "System Administrator")

    # Validate password strength
    is_valid, error_msg = validate_password_strength(admin_password)
    if not is_valid:
        print(f"ERROR: Password does not meet strength requirements: {error_msg}")
        sys.exit(1)

    # Create database connection
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if user already exists
        existing_user = session.query(User).filter(
            User.org_id == org_id,
            User.email == admin_email.lower()
        ).first()

        if existing_user:
            print(f"ERROR: User with email {admin_email} already exists in organization")
            sys.exit(1)

        # Hash password
        password_hash = hash_password(admin_password)

        # Create admin user
        admin_user = User(
            org_id=org_id,
            email=admin_email.lower(),
            name=admin_name,
            role="ADMIN",
            password_hash=password_hash,
            status="ACTIVE"
        )

        session.add(admin_user)
        session.commit()

        print("SUCCESS: Admin user created")
        print(f"  ID:    {admin_user.id}")
        print(f"  Org:   {admin_user.org_id}")
        print(f"  Email: {admin_user.email}")
        print(f"  Name:  {admin_user.name}")
        print(f"  Role:  {admin_user.role}")

    except Exception as e:
        session.rollback()
        print(f"ERROR: Failed to create admin user: {e}")
        sys.exit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
