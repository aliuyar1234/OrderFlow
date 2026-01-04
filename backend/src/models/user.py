"""User SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, CITEXT, TIMESTAMP
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import text
import re

from .base import Base


class User(Base):
    """User model representing authenticated users in the OrderFlow system.

    Each user belongs to one organization and has a specific role determining
    their permissions. Passwords are hashed using Argon2id.
    """
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    email = Column(CITEXT, nullable=False)
    name = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="ACTIVE")
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org", back_populates="users")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'INTEGRATOR', 'OPS', 'VIEWER')",
            name='ck_user_role'
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED')",
            name='ck_user_status'
        ),
        UniqueConstraint('org_id', 'email', name='uq_user_org_email')
    )

    @validates('email')
    def validate_email(self, key, value):
        """Basic email format validation"""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise ValueError("Invalid email format")
        return value.lower()

    def to_dict(self):
        """Convert user to dictionary representation (excludes password_hash)"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
