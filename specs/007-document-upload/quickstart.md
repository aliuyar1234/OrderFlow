# Quickstart: Document Upload

**Feature**: 007-document-upload | **Prerequisites**: Backend running, PostgreSQL, MinIO

## Development Setup

### 1. Install Dependencies

```bash
cd backend
pip install python-magic==0.4.27
# Windows: pip install python-magic-bin==0.4.14
```

### 2. Configure Environment

```bash
# .env
MAX_UPLOAD_SIZE_BYTES=104857600  # 100MB
MAX_BATCH_UPLOAD_FILES=10
```

### 3. Start Backend

```bash
cd backend
uvicorn src.main:app --reload --port 8000
```

## Usage Examples

### Upload Single File (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/uploads \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "files=@order.pdf"
```

**Response**:
```json
{
  "uploaded": [
    {
      "document_id": "uuid",
      "file_name": "order.pdf",
      "size_bytes": 123456,
      "sha256": "abc123...",
      "status": "STORED",
      "is_duplicate": false
    }
  ],
  "failed": []
}
```

### Upload Multiple Files (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/uploads \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "files=@order1.pdf" \
  -F "files=@order2.xlsx" \
  -F "files=@order3.csv"
```

### Upload File (Python)

```python
import requests

url = "http://localhost:8000/api/v1/uploads"
headers = {"Authorization": "Bearer YOUR_JWT_TOKEN"}

with open("order.pdf", "rb") as f:
    files = {"files": ("order.pdf", f, "application/pdf")}
    response = requests.post(url, headers=headers, files=files)

print(response.json())
```

### Upload File (JavaScript/Fetch)

```javascript
const formData = new FormData();
formData.append('files', fileInput.files[0]);

fetch('http://localhost:8000/api/v1/uploads', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
})
.then(res => res.json())
.then(data => console.log(data));
```

## Testing

```bash
# Unit tests
pytest tests/unit/uploads/test_mime_validation.py -v
pytest tests/unit/uploads/test_status_transitions.py -v

# Integration tests
pytest tests/integration/uploads/test_upload_api.py -v
pytest tests/integration/uploads/test_batch_upload.py -v

# E2E test
pytest tests/e2e/test_upload_to_draft_flow.py -v
```

### Integration Test Example

```python
# tests/integration/uploads/test_upload_api.py
import pytest
from fastapi.testclient import TestClient

def test_upload_pdf(client: TestClient, auth_token: str):
    """Test uploading a PDF file"""
    with open("tests/fixtures/order.pdf", "rb") as f:
        response = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"files": ("order.pdf", f, "application/pdf")}
        )

    assert response.status_code == 201
    data = response.json()
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["file_name"] == "order.pdf"
    assert data["uploaded"][0]["status"] == "STORED"

def test_upload_invalid_mime_type(client: TestClient, auth_token: str):
    """Test uploading unsupported file type"""
    with open("tests/fixtures/document.docx", "rb") as f:
        response = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"files": ("document.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )

    assert response.status_code == 400
    data = response.json()
    assert "Unsupported MIME type" in data["error"]["message"]
```

## Common Issues

### Upload fails with "File too large"
**Solution**: Increase `MAX_UPLOAD_SIZE_BYTES` or reduce file size

### Upload accepted but extraction never runs
**Solution**: Start Celery worker: `celery -A src.workers worker -l info`

### MIME type validation fails for valid PDF
**Solution**: Install libmagic: `apt-get install libmagic1`

### Upload succeeds but file missing from storage
**Solution**: Check MinIO is running: `docker-compose ps minio`
