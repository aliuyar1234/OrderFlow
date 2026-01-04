"""Draft order service - Business logic for draft order operations.

SSOT Reference: §6.3 (Ready-Check), §7.8 (Confidence), §5.2.5 (State Machine)
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from ..models.draft_order import DraftOrder, DraftOrderLine
from ..audit.service import create_audit_log
from .status import DraftOrderStatus, validate_transition, StateTransitionError
from .ready_check import run_ready_check, determine_status_from_ready_check
from .confidence import normalize_customer_sku


class DraftOrderService:
    """Service for draft order operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_draft_order(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        include_lines: bool = True
    ) -> Optional[DraftOrder]:
        """Get a draft order by ID with optional lines.

        Args:
            org_id: Organization ID for tenant isolation
            draft_order_id: Draft order ID
            include_lines: Whether to eager-load lines

        Returns:
            DraftOrder instance or None if not found

        Raises:
            ValueError: If cross-tenant access attempted (returns 404)
        """
        query = self.db.query(DraftOrder).filter(
            and_(
                DraftOrder.id == draft_order_id,
                DraftOrder.org_id == org_id,
                DraftOrder.deleted_at.is_(None)  # Exclude soft-deleted
            )
        )

        if include_lines:
            query = query.options(joinedload(DraftOrder.lines))

        draft = query.first()

        # Return 404 for cross-tenant access (§3.1 Multi-Tenant Isolation)
        if draft and draft.org_id != org_id:
            return None

        return draft

    def list_draft_orders(
        self,
        org_id: UUID,
        status: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> Tuple[List[DraftOrder], int]:
        """List draft orders with filtering and pagination.

        Args:
            org_id: Organization ID for tenant isolation
            status: Filter by status (optional)
            customer_id: Filter by customer (optional)
            limit: Maximum results to return
            offset: Number of results to skip
            order_by: Field to order by
            order_desc: Sort descending if True

        Returns:
            Tuple of (list of DraftOrders, total count)
        """
        # Base query with tenant isolation
        query = self.db.query(DraftOrder).filter(
            and_(
                DraftOrder.org_id == org_id,
                DraftOrder.deleted_at.is_(None)
            )
        )

        # Apply filters
        if status:
            query = query.filter(DraftOrder.status == status)

        if customer_id:
            query = query.filter(DraftOrder.customer_id == customer_id)

        # Get total count before pagination
        total = query.count()

        # Apply ordering
        order_field = getattr(DraftOrder, order_by, DraftOrder.created_at)
        if order_desc:
            query = query.order_by(desc(order_field))
        else:
            query = query.order_by(order_field)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        drafts = query.all()

        return drafts, total

    def update_draft_order_header(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        update_data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> DraftOrder:
        """Update draft order header fields.

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID
            update_data: Dict of fields to update
            user_id: User performing the update (for audit log)

        Returns:
            Updated DraftOrder

        Raises:
            ValueError: If draft not found or invalid data
        """
        draft = self.get_draft_order(org_id, draft_order_id, include_lines=False)
        if not draft:
            raise ValueError(f"Draft order {draft_order_id} not found")

        # Track changes for audit log
        before_data = {
            "customer_id": str(draft.customer_id) if draft.customer_id else None,
            "external_order_number": draft.external_order_number,
            "order_date": draft.order_date.isoformat() if draft.order_date else None,
            "currency": draft.currency,
        }

        # Apply updates
        for field, value in update_data.items():
            if hasattr(draft, field):
                setattr(draft, field, value)

        draft.updated_at = datetime.utcnow()

        # Increment version for optimistic locking (FR-022)
        draft.version += 1

        self.db.flush()

        # Create audit log
        after_data = {
            "customer_id": str(draft.customer_id) if draft.customer_id else None,
            "external_order_number": draft.external_order_number,
            "order_date": draft.order_date.isoformat() if draft.order_date else None,
            "currency": draft.currency,
        }

        create_audit_log(
            db=self.db,
            org_id=org_id,
            actor_user_id=user_id,
            action="DRAFT_ORDER_UPDATED",
            entity_type="draft_order",
            entity_id=draft.id,
            before_json=before_data,
            after_json=after_data
        )

        # Trigger ready-check if customer changed (FR-012)
        if "customer_id" in update_data:
            self.run_ready_check_and_update_status(draft, event="customer_selected", user_id=user_id)

        self.db.commit()
        return draft

    def update_draft_order_line(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        line_id: UUID,
        update_data: Dict[str, Any],
        user_id: Optional[UUID] = None
    ) -> DraftOrderLine:
        """Update a draft order line.

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID
            line_id: Line ID to update
            update_data: Dict of fields to update
            user_id: User performing the update

        Returns:
            Updated DraftOrderLine

        Raises:
            ValueError: If line not found or invalid data
        """
        # Verify draft exists and belongs to org
        draft = self.get_draft_order(org_id, draft_order_id, include_lines=False)
        if not draft:
            raise ValueError(f"Draft order {draft_order_id} not found")

        # Get line
        line = self.db.query(DraftOrderLine).filter(
            and_(
                DraftOrderLine.id == line_id,
                DraftOrderLine.draft_order_id == draft_order_id,
                DraftOrderLine.org_id == org_id
            )
        ).first()

        if not line:
            raise ValueError(f"Line {line_id} not found")

        # Track changes for audit
        before_data = {
            "customer_sku_raw": line.customer_sku_raw,
            "internal_sku": line.internal_sku,
            "qty": float(line.qty) if line.qty else None,
        }

        # Apply updates
        for field, value in update_data.items():
            if hasattr(line, field):
                # Normalize customer SKU if updating (§6.1 FR-011)
                if field == "customer_sku_raw" and value:
                    line.customer_sku_raw = value
                    line.customer_sku_norm = normalize_customer_sku(value)
                # Mark as overridden if internal_sku changed manually (FR-010)
                elif field == "internal_sku" and value:
                    line.internal_sku = value
                    line.match_status = "OVERRIDDEN"
                    line.match_method = "manual"
                else:
                    setattr(line, field, value)

        line.updated_at = datetime.utcnow()
        self.db.flush()

        # Create audit log
        after_data = {
            "customer_sku_raw": line.customer_sku_raw,
            "internal_sku": line.internal_sku,
            "qty": float(line.qty) if line.qty else None,
        }

        create_audit_log(
            db=self.db,
            org_id=org_id,
            actor_user_id=user_id,
            action="DRAFT_LINE_UPDATED",
            entity_type="draft_order_line",
            entity_id=line.id,
            before_json=before_data,
            after_json=after_data
        )

        # Trigger ready-check after line update (FR-012)
        self.run_ready_check_and_update_status(draft, event="line_updated", user_id=user_id)

        # Update parent draft's updated_at
        draft.updated_at = datetime.utcnow()
        draft.version += 1

        self.db.commit()
        return line

    def run_ready_check_and_update_status(
        self,
        draft: DraftOrder,
        event: str = "manual",
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Run ready-check and update draft status accordingly.

        Args:
            draft: DraftOrder instance
            event: Event that triggered ready-check
            user_id: User who triggered the check (for audit)

        Returns:
            Ready-check result dict

        SSOT Reference: §6.3 (FR-012, FR-013)
        """
        # Load lines if not already loaded
        if not draft.lines:
            draft = self.db.query(DraftOrder).options(
                joinedload(DraftOrder.lines)
            ).filter(DraftOrder.id == draft.id).first()

        # Get validation issues (ERROR severity, OPEN status)
        # Note: validation_issue table implementation pending
        validation_issues = []  # TODO: Load from validation_issue table

        # Run ready-check (§6.3 FR-005)
        ready_check_result = run_ready_check(
            draft_order=draft,
            lines=draft.lines,
            validation_issues=validation_issues
        )

        # Update ready_check_json field
        draft.ready_check_json = ready_check_result

        # Determine if status should change (§6.3 FR-013)
        new_status = determine_status_from_ready_check(
            current_status=draft.status,
            ready_check_result=ready_check_result
        )

        # Apply status transition if needed
        if new_status and new_status != draft.status:
            try:
                self.transition_status(
                    draft=draft,
                    new_status=new_status,
                    user_id=user_id,
                    reason=f"Ready-check triggered by {event}"
                )
            except StateTransitionError:
                # Status transition not allowed, just update ready_check_json
                pass

        self.db.flush()
        return ready_check_result

    def transition_status(
        self,
        draft: DraftOrder,
        new_status: str,
        user_id: Optional[UUID] = None,
        reason: Optional[str] = None
    ) -> DraftOrder:
        """Transition draft order status with validation.

        Args:
            draft: DraftOrder instance
            new_status: Target status
            user_id: User performing transition
            reason: Reason for transition (for audit log)

        Returns:
            Updated DraftOrder

        Raises:
            StateTransitionError: If transition is invalid

        SSOT Reference: §5.2.5 (State Machine FR-004)
        """
        old_status = draft.status

        # Validate transition (§5.2.5 FR-004)
        validate_transition(
            current_status=DraftOrderStatus(old_status),
            new_status=DraftOrderStatus(new_status)
        )

        # Apply transition
        draft.status = new_status
        draft.updated_at = datetime.utcnow()
        draft.version += 1

        # Set approved_at and approved_by_user_id when transitioning to APPROVED (FR-015)
        if new_status == DraftOrderStatus.APPROVED.value:
            draft.approved_at = datetime.utcnow()
            draft.approved_by_user_id = user_id

        # Set pushed_at when transitioning to PUSHED (FR-016)
        if new_status == DraftOrderStatus.PUSHED.value:
            draft.pushed_at = datetime.utcnow()

        # Create audit log (FR-014)
        create_audit_log(
            db=self.db,
            org_id=draft.org_id,
            actor_user_id=user_id,
            action="DRAFT_STATUS_CHANGED",
            entity_type="draft_order",
            entity_id=draft.id,
            before_json={"status": old_status},
            after_json={"status": new_status, "reason": reason}
        )

        self.db.flush()
        return draft

    def soft_delete_draft_order(
        self,
        org_id: UUID,
        draft_order_id: UUID,
        user_id: Optional[UUID] = None
    ) -> bool:
        """Soft-delete a draft order.

        Args:
            org_id: Organization ID
            draft_order_id: Draft order ID
            user_id: User performing deletion

        Returns:
            True if deleted successfully

        SSOT Reference: FR-023 (Soft Delete Strategy)
        """
        draft = self.get_draft_order(org_id, draft_order_id, include_lines=True)
        if not draft:
            return False

        # Set deleted_at timestamp
        now = datetime.utcnow()
        draft.deleted_at = now

        # Cascade soft-delete to lines (FR-023)
        for line in draft.lines:
            line.deleted_at = now

        # Audit log
        create_audit_log(
            db=self.db,
            org_id=org_id,
            actor_user_id=user_id,
            action="DRAFT_ORDER_DELETED",
            entity_type="draft_order",
            entity_id=draft.id,
            before_json={"status": draft.status},
            after_json={"deleted_at": now.isoformat()}
        )

        self.db.commit()
        return True
