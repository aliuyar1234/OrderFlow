# Data Model: Data Retention & Cleanup

## Retention Configuration

Stored in `organization.settings_json`:

```json
{
  "raw_document_retention_days": 365,
  "ai_log_retention_days": 90,
  "feedback_event_retention_days": 365,
  "audit_log_retention_days": 365  // minimum, not user-configurable
}
```

## Soft-Delete Strategy

**Entities with Soft-Delete**:
- Document (status=DELETED)
- DraftOrder (status=DELETED)

**Schema**:
```python
class Document(Base):
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        nullable=False
    )
    # Status values: ACTIVE, PROCESSING, FAILED, DELETED

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    # Used to track soft-delete timestamp for grace period
```

## Hard-Delete Strategy

**Entities with Hard-Delete**:
- AICallLog (immediate deletion, no soft-delete)
- FeedbackEvent (immediate deletion after retention)
- Document (after 90-day grace period from soft-delete)

## Retention Job Logic

```python
async def retention_cleanup_job():
    for org in get_all_orgs():
        settings = org.settings_json

        # Soft-delete documents
        doc_cutoff = datetime.utcnow() - timedelta(days=settings["raw_document_retention_days"])
        soft_delete_documents(org.id, doc_cutoff)

        # Hard-delete soft-deleted documents (grace period expired)
        grace_cutoff = datetime.utcnow() - timedelta(days=90)
        hard_delete_documents(org.id, grace_cutoff)

        # Hard-delete AI logs
        ai_cutoff = datetime.utcnow() - timedelta(days=settings["ai_log_retention_days"])
        hard_delete_ai_logs(org.id, ai_cutoff)

        # Hard-delete feedback events
        feedback_cutoff = datetime.utcnow() - timedelta(days=settings["feedback_event_retention_days"])
        hard_delete_feedback_events(org.id, feedback_cutoff)
```

## Migration

No schema changes required. Uses existing status fields and timestamps.
