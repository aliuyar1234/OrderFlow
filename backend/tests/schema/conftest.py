"""Pytest fixtures for schema tests.

Provides database engine and ensures tables are created before schema tests run.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

import sys
import os
from pathlib import Path

# Add src to path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

# Set required environment variables
# Use PostgreSQL - models require PostgreSQL features (gen_random_uuid, JSONB)
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://orderflow:dev_password@localhost:5433/orderflow"

if "PASSWORD_PEPPER" not in os.environ:
    os.environ["PASSWORD_PEPPER"] = "test-pepper-secret-key-32-chars-long"

if "JWT_SECRET" not in os.environ:
    os.environ["JWT_SECRET"] = "test-jwt-secret-key-256-bits-minimum-length-required-for-security"

# Import models to register with Base
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


@pytest.fixture(scope="class")
def engine() -> Engine:
    """Create SQLAlchemy engine and ensure all tables exist."""
    from database import engine as db_engine

    # Create all tables
    Base.metadata.create_all(bind=db_engine)

    return db_engine
