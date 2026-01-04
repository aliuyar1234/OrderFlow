"""Org model - Root entity for multi-tenant isolation"""

from sqlalchemy import Column, String, Text, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import validates, relationship
from datetime import datetime
import re

from .base import Base, PortableJSONB


class Org(Base):
    """
    Organization model - Root entity for multi-tenant system.

    Each organization represents a distinct tenant with isolated data.
    All other tables (except global system tables) reference org.id via foreign key.

    SSOT Reference: §5.4.1 (org table)
    """
    __tablename__ = "org"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    settings_json = Column(
        PortableJSONB,
        nullable=False,
        server_default=text("'{}'::jsonb")
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()")
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=datetime.utcnow
    )

    # Relationships
    users = relationship("User", back_populates="org")
    customers = relationship("Customer", back_populates="org")
    erp_connections = relationship("ERPConnection", back_populates="org")
    erp_push_logs = relationship("ERPPushLog", back_populates="org")
    inbound_messages = relationship("InboundMessage", back_populates="org")
    documents = relationship("Document", back_populates="org")
    products = relationship("Product", back_populates="org")
    units_of_measure = relationship("UnitOfMeasure", back_populates="org")
    erp_connections = relationship("ERPConnection", back_populates="org")

    @validates('slug')
    def validate_slug(self, key, value):
        """
        Ensure slug is URL-friendly and follows naming conventions.

        Pattern: ^[a-z0-9-]+$
        Valid: acme-gmbh, test-org-123
        Invalid: Acme_GmbH, acme gmbh, acme.gmbh

        Raises:
            ValueError: If slug doesn't match pattern or length requirements
        """
        if not re.match(r'^[a-z0-9-]+$', value):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        if len(value) < 2 or len(value) > 100:
            raise ValueError("Slug must be between 2 and 100 characters")
        return value

    @validates('name')
    def validate_name(self, key, value):
        """
        Ensure organization name is not empty and within length limits.

        Raises:
            ValueError: If name is empty/whitespace or exceeds 200 characters
        """
        if not value or len(value.strip()) == 0:
            raise ValueError("Organization name cannot be empty")
        if len(value) > 200:
            raise ValueError("Organization name cannot exceed 200 characters")
        return value.strip()

    def __repr__(self):
        return f"<Org(id={self.id}, slug='{self.slug}', name='{self.name}')>"
