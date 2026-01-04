"""Base SQLAlchemy declarative base for all models"""

from sqlalchemy.orm import declarative_base
from sqlalchemy import TypeDecorator, JSON
from sqlalchemy.dialects.postgresql import JSONB


class PortableJSONB(TypeDecorator):
    """JSON type that works with both PostgreSQL (JSONB) and SQLite (JSON).

    Uses JSONB on PostgreSQL for efficient indexing and querying,
    falls back to JSON on SQLite for testing compatibility.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


Base = declarative_base()
