# Quickstart: Dropzone JSON Connector Development

**Date**: 2025-12-27

## Setup

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/load_fixtures.py --fixture dropzone_connector
```

## Test Export Generation

```python
def test_export_json_generation():
    draft = DraftOrder(
        id=uuid4(),
        org_slug="acme-corp",
        customer=Customer(erp_customer_number="CUST-4711", name="Muster GmbH"),
        approved_at=datetime(2025, 12, 27, 10, 0, 0),
        lines=[
            DraftOrderLine(
                line_no=1,
                internal_sku="SKU-ABC",
                qty=100,
                uom="PCE",
                unit_price=10.50
            )
        ]
    )

    connector = DropzoneJsonV1Connector()
    export_json = connector.generate_export_json(draft)

    assert export_json["export_version"] == "orderflow_export_json_v1"
    assert export_json["org_slug"] == "acme-corp"
    assert len(export_json["lines"]) == 1
```

## Test SFTP Write

```python
def test_sftp_write_atomic_rename(mock_sftp):
    connector = DropzoneJsonV1Connector()
    config = {
        "mode": "sftp",
        "host": "localhost",
        "port": 2222,
        "username": "test",
        "password": "test",
        "export_path": "/import/orders",
        "atomic_write": True
    }

    result = connector.export(draft_order, config)

    assert result.success is True
    assert result.dropzone_path.endswith(".json")
    # Verify .tmp file was deleted
    assert not sftp.exists(result.dropzone_path + ".tmp")
```

## Test Ack Poller

```python
def test_ack_poller_success():
    # Create export
    export = ERPExport(
        draft_order_id=draft.id,
        status="SENT",
        dropzone_path="/import/orders/sales_order_abc_20251227T100000Z.json"
    )
    db.session.add(export)

    # Write ack file
    ack_content = {
        "status": "ACKED",
        "erp_order_id": "SO-2025-000123",
        "processed_at": "2025-12-27T10:10:00Z"
    }
    write_file("/import/acks/ack_sales_order_abc_20251227T100000Z.json", ack_content)

    # Run poller
    process_ack_files()

    # Verify export updated
    db.session.refresh(export)
    assert export.status == "ACKED"
    assert export.erp_order_id == "SO-2025-000123"
```

## Manual Testing

```bash
# Start local SFTP server
docker run -d -p 2222:22 \
  -v /tmp/sftp:/home/test/upload \
  atmoz/sftp test:test:::upload

# Configure connector
curl -X POST http://localhost:8000/api/v1/connectors/dropzone-json-v1 \
  -H "Authorization: Bearer <token>" \
  -d '{
    "mode": "sftp",
    "host": "localhost",
    "port": 2222,
    "username": "test",
    "password": "test",
    "export_path": "/home/test/upload/orders",
    "ack_path": "/home/test/upload/acks"
  }'

# Push draft order
curl -X POST http://localhost:8000/api/v1/draft-orders/<id>/push \
  -H "Authorization: Bearer <token>"

# Check SFTP directory
sftp -P 2222 test@localhost
ls /home/test/upload/orders
# Should see: sales_order_<id>_<timestamp>.json
```

## Snapshot Test

```python
def test_export_json_schema_snapshot(snapshot):
    export_json = generate_export_json(draft_order)

    # Compare against golden snapshot
    snapshot.assert_match(json.dumps(export_json, indent=2, sort_keys=True))
```
