"""Add missing foreign key constraints

Revision ID: 018
Revises: 017
Create Date: 2026-01-04

SSOT Reference: Database audit - adding missing FK constraints for referential integrity
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing foreign key constraints identified in database audit."""

    # 1. draft_order.document_id → document.id
    # SET NULL: Document can be deleted independently, draft_order retains data
    op.create_foreign_key(
        'fk_draft_order_document_id',
        'draft_order', 'document',
        ['document_id'], ['id'],
        ondelete='SET NULL'
    )

    # 2. draft_order.inbound_message_id → inbound_message.id
    # SET NULL: Inbound message can be deleted/archived, draft_order retains data
    op.create_foreign_key(
        'fk_draft_order_inbound_message_id',
        'draft_order', 'inbound_message',
        ['inbound_message_id'], ['id'],
        ondelete='SET NULL'
    )

    # 3. draft_order.extraction_run_id → extraction_run.id
    # SET NULL: Extraction run can be deleted/archived, draft_order retains data
    op.create_foreign_key(
        'fk_draft_order_extraction_run_id',
        'draft_order', 'extraction_run',
        ['extraction_run_id'], ['id'],
        ondelete='SET NULL'
    )

    # 4. draft_order_line.product_id → product.id
    # SET NULL: Product can be inactivated/deleted, line retains internal_sku for reference
    op.create_foreign_key(
        'fk_draft_order_line_product_id',
        'draft_order_line', 'product',
        ['product_id'], ['id'],
        ondelete='SET NULL'
    )

    # 5. erp_export.draft_order_id → draft_order.id
    # RESTRICT: Cannot delete draft_order if it has associated ERP exports
    # This maintains audit trail integrity for ERP transactions
    op.create_foreign_key(
        'fk_erp_export_draft_order_id',
        'erp_export', 'draft_order',
        ['draft_order_id'], ['id'],
        ondelete='RESTRICT'
    )


def downgrade() -> None:
    """Remove foreign key constraints."""

    # Drop constraints in reverse order
    op.drop_constraint('fk_erp_export_draft_order_id', 'erp_export', type_='foreignkey')
    op.drop_constraint('fk_draft_order_line_product_id', 'draft_order_line', type_='foreignkey')
    op.drop_constraint('fk_draft_order_extraction_run_id', 'draft_order', type_='foreignkey')
    op.drop_constraint('fk_draft_order_inbound_message_id', 'draft_order', type_='foreignkey')
    op.drop_constraint('fk_draft_order_document_id', 'draft_order', type_='foreignkey')
