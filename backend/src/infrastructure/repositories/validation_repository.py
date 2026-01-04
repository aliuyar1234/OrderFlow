"""Validation repository for database operations"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from models.validation_issue import ValidationIssue as ValidationIssueModel
from domain.validation.models import (
    ValidationIssue,
    ValidationIssueStatus,
    ValidationIssueSeverity,
    ValidationIssueType
)


class ValidationRepository:
    """Repository for validation_issue database operations.

    Handles persistence of validation issues, auto-resolution logic,
    and querying issues by draft order.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create_issue(self, issue: ValidationIssue) -> ValidationIssueModel:
        """Persist a validation issue to the database.

        Args:
            issue: Domain ValidationIssue object

        Returns:
            Persisted ValidationIssueModel (SQLAlchemy model)
        """
        db_issue = ValidationIssueModel(
            org_id=issue.org_id,
            draft_order_id=issue.draft_order_id,
            draft_order_line_id=issue.draft_order_line_id,
            type=issue.type.value,
            severity=issue.severity,
            status=issue.status,
            message=issue.message,
            details_json=issue.details
        )

        self.db.add(db_issue)
        self.db.flush()

        return db_issue

    def get_issues_by_draft_order(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        status_filter: Optional[list[ValidationIssueStatus]] = None
    ) -> list[ValidationIssueModel]:
        """Get all validation issues for a draft order.

        Args:
            org_id: Organization ID (multi-tenant isolation)
            draft_order_id: Draft order ID
            status_filter: Optional list of statuses to filter by (e.g., [OPEN])

        Returns:
            List of ValidationIssueModel objects
        """
        query = select(ValidationIssueModel).where(
            and_(
                ValidationIssueModel.org_id == org_id,
                ValidationIssueModel.draft_order_id == draft_order_id
            )
        )

        if status_filter:
            query = query.where(ValidationIssueModel.status.in_(status_filter))

        query = query.order_by(ValidationIssueModel.created_at)

        return self.db.execute(query).scalars().all()

    def get_open_issues_by_draft_order(
        self,
        org_id: UUID,
        draft_order_id: UUID
    ) -> list[ValidationIssueModel]:
        """Get OPEN validation issues for a draft order.

        This is the primary method used for ready-check computation.

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID

        Returns:
            List of OPEN ValidationIssueModel objects
        """
        return self.get_issues_by_draft_order(
            org_id=org_id,
            draft_order_id=draft_order_id,
            status_filter=[ValidationIssueStatus.OPEN]
        )

    def acknowledge_issue(
        self,
        issue_id: UUID,
        org_id: UUID,
        user_id: UUID
    ) -> Optional[ValidationIssueModel]:
        """Acknowledge a validation issue.

        Changes status from OPEN to ACKNOWLEDGED. Does not resolve the issue.
        Per spec.md US3, acknowledgement does not affect READY blocking.

        Args:
            issue_id: Issue ID
            org_id: Organization ID (security check)
            user_id: User performing acknowledgement

        Returns:
            Updated ValidationIssueModel, or None if not found
        """
        issue = self.db.get(ValidationIssueModel, issue_id)

        if not issue or issue.org_id != org_id:
            return None

        if issue.status == ValidationIssueStatus.OPEN:
            issue.status = ValidationIssueStatus.ACKNOWLEDGED
            issue.acknowledged_at = datetime.utcnow()
            issue.acknowledged_by_user_id = user_id
            self.db.flush()

        return issue

    def resolve_issue(
        self,
        issue_id: UUID,
        org_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Optional[ValidationIssueModel]:
        """Resolve a validation issue.

        Changes status to RESOLVED. Used for auto-resolution when underlying
        problem is fixed (spec.md auto-resolution logic).

        Args:
            issue_id: Issue ID
            org_id: Organization ID (security check)
            user_id: User performing resolution (None for auto-resolution)

        Returns:
            Updated ValidationIssueModel, or None if not found
        """
        issue = self.db.get(ValidationIssueModel, issue_id)

        if not issue or issue.org_id != org_id:
            return None

        if issue.status in [ValidationIssueStatus.OPEN, ValidationIssueStatus.ACKNOWLEDGED]:
            issue.status = ValidationIssueStatus.RESOLVED
            issue.resolved_at = datetime.utcnow()
            issue.resolved_by_user_id = user_id
            self.db.flush()

        return issue

    def auto_resolve_by_type_and_line(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        issue_type: ValidationIssueType,
        line_id: Optional[UUID] = None
    ) -> int:
        """Auto-resolve issues of a specific type for a line/header.

        Used when underlying problem is fixed (e.g., SKU is set, so
        MISSING_SKU issues should be auto-resolved).

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID
            issue_type: Type of issue to resolve
            line_id: Line ID (None for header issues)

        Returns:
            Number of issues auto-resolved
        """
        query = select(ValidationIssueModel).where(
            and_(
                ValidationIssueModel.org_id == org_id,
                ValidationIssueModel.draft_order_id == draft_order_id,
                ValidationIssueModel.type == issue_type.value,
                ValidationIssueModel.status.in_([
                    ValidationIssueStatus.OPEN,
                    ValidationIssueStatus.ACKNOWLEDGED
                ])
            )
        )

        if line_id:
            query = query.where(ValidationIssueModel.draft_order_line_id == line_id)
        else:
            query = query.where(ValidationIssueModel.draft_order_line_id.is_(None))

        issues = self.db.execute(query).scalars().all()

        count = 0
        for issue in issues:
            issue.status = ValidationIssueStatus.RESOLVED
            issue.resolved_at = datetime.utcnow()
            issue.resolved_by_user_id = None  # Auto-resolved
            count += 1

        if count > 0:
            self.db.flush()

        return count

    def delete_all_open_issues_for_draft(
        self,
        org_id: UUID,
        draft_order_id: UUID
    ) -> int:
        """Delete all OPEN issues for a draft order.

        Used before running fresh validation (to avoid stale issues).

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID

        Returns:
            Number of issues deleted
        """
        query = select(ValidationIssueModel).where(
            and_(
                ValidationIssueModel.org_id == org_id,
                ValidationIssueModel.draft_order_id == draft_order_id,
                ValidationIssueModel.status == ValidationIssueStatus.OPEN
            )
        )

        issues = self.db.execute(query).scalars().all()
        count = len(issues)

        for issue in issues:
            self.db.delete(issue)

        if count > 0:
            self.db.flush()

        return count
