"""Integration tests for upload API

Tests the complete upload workflow:
- File upload with validation
- Storage integration
- Database record creation
- Deduplication
- Error handling

SSOT Reference: §8.5 (Upload API)
Spec: 007-document-upload
"""

import io
import pytest
from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.src.models.document import Document, DocumentStatus
from backend.src.models.inbound_message import InboundMessage


class TestUploadAPI:
    """Integration tests for POST /api/v1/uploads endpoint"""

    @pytest.fixture
    def pdf_file(self):
        """Create a mock PDF file for testing"""
        # Minimal valid PDF (just header)
        content = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
        return io.BytesIO(content)

    @pytest.fixture
    def csv_file(self):
        """Create a mock CSV file for testing"""
        content = b"sku,qty,price\nABC123,10,25.50\n"
        return io.BytesIO(content)

    def test_upload_single_pdf(self, client: TestClient, auth_token: str, db: Session, org_id: UUID):
        """Test uploading a single PDF file"""
        # Create PDF file
        pdf_content = b"%PDF-1.4\ntest content\n"
        files = {
            'files': ('order.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }

        # Upload
        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()
        assert len(data['uploaded']) == 1
        assert len(data['failed']) == 0

        uploaded = data['uploaded'][0]
        assert uploaded['file_name'] == 'order.pdf'
        assert uploaded['status'] == 'STORED'
        assert uploaded['is_duplicate'] is False
        assert 'document_id' in uploaded
        assert 'sha256' in uploaded

        # Verify database records
        doc_id = UUID(uploaded['document_id'])
        document = db.query(Document).filter(Document.id == doc_id).first()
        assert document is not None
        assert document.org_id == org_id
        assert document.file_name == 'order.pdf'
        assert document.mime_type == 'application/pdf'
        assert document.status == DocumentStatus.STORED
        assert document.sha256 == uploaded['sha256']

        # Verify inbound_message created
        inbound_msg = db.query(InboundMessage).filter(
            InboundMessage.id == document.inbound_message_id
        ).first()
        assert inbound_msg is not None
        assert inbound_msg.source == 'UPLOAD'
        assert inbound_msg.status == 'STORED'

    def test_upload_multiple_files(self, client: TestClient, auth_token: str, db: Session):
        """Test uploading multiple files in batch"""
        files = [
            ('files', ('order1.pdf', io.BytesIO(b"%PDF-1.4\nfile1\n"), 'application/pdf')),
            ('files', ('order2.csv', io.BytesIO(b"sku,qty\nA,1\n"), 'text/csv')),
        ]

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data['uploaded']) == 2
        assert len(data['failed']) == 0

        # Verify both files have different document IDs
        doc_ids = [UUID(doc['document_id']) for doc in data['uploaded']]
        assert len(set(doc_ids)) == 2

    def test_upload_duplicate_file(self, client: TestClient, auth_token: str, db: Session):
        """Test uploading same file twice (deduplication)"""
        pdf_content = b"%PDF-1.4\nsame content\n"
        files = {
            'files': ('order.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }

        # Upload first time
        response1 = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response1.status_code == 201
        sha256_first = response1.json()['uploaded'][0]['sha256']

        # Upload same file again
        files = {
            'files': ('order.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        response2 = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response2.status_code == 201
        data = response2.json()
        assert len(data['uploaded']) == 1

        uploaded = data['uploaded'][0]
        assert uploaded['sha256'] == sha256_first
        assert uploaded['is_duplicate'] is True

        # Verify two document records exist (dedup only prevents re-upload to storage)
        doc_count = db.query(Document).filter(
            Document.sha256 == sha256_first
        ).count()
        assert doc_count == 2

    def test_upload_unsupported_file_type(self, client: TestClient, auth_token: str):
        """Test uploading unsupported file type (should fail)"""
        files = {
            'files': ('document.docx', io.BytesIO(b"fake docx"), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        # Should still return 201 but with failed list
        assert response.status_code == 201
        data = response.json()
        assert len(data['uploaded']) == 0
        assert len(data['failed']) == 1
        assert 'Unsupported MIME type' in data['failed'][0]['error']

    def test_upload_empty_file(self, client: TestClient, auth_token: str):
        """Test uploading empty file (should fail)"""
        files = {
            'files': ('empty.pdf', io.BytesIO(b""), 'application/pdf')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data['uploaded']) == 0
        assert len(data['failed']) == 1
        assert 'empty' in data['failed'][0]['error'].lower()

    def test_upload_file_too_large(self, client: TestClient, auth_token: str, monkeypatch):
        """Test uploading file exceeding size limit"""
        # Mock MAX_FILE_SIZE to small value for testing
        from backend.src.domain.documents import validation
        monkeypatch.setattr(validation, 'MAX_FILE_SIZE', 1024)  # 1KB limit

        # Create 2KB file
        large_content = b"%PDF-1.4\n" + b"x" * 2048
        files = {
            'files': ('large.pdf', io.BytesIO(large_content), 'application/pdf')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data['uploaded']) == 0
        assert len(data['failed']) == 1
        assert 'exceeds maximum size' in data['failed'][0]['error'].lower()

    def test_upload_without_auth(self, client: TestClient):
        """Test uploading without authentication (should fail with 401)"""
        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = client.post('/api/v1/uploads', files=files)

        assert response.status_code == 401

    def test_upload_with_viewer_role(self, client: TestClient, viewer_token: str):
        """Test uploading as VIEWER role (should fail with 403)"""
        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {viewer_token}'}
        )

        assert response.status_code == 403

    def test_upload_no_files(self, client: TestClient, auth_token: str):
        """Test uploading with no files provided (should fail with 400)"""
        response = client.post(
            '/api/v1/uploads',
            files={},
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 400
        assert 'No files provided' in response.json()['detail']

    def test_upload_too_many_files(self, client: TestClient, auth_token: str, monkeypatch):
        """Test uploading more files than allowed in batch (should fail with 400)"""
        # Mock MAX_BATCH_FILES to small value for testing
        from backend.src.domain.documents import validation
        monkeypatch.setattr(validation, 'MAX_BATCH_FILES', 2)

        # Try to upload 3 files
        files = [
            ('files', ('f1.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')),
            ('files', ('f2.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')),
            ('files', ('f3.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')),
        ]

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 400
        assert 'Too many files' in response.json()['detail']

    def test_upload_filename_sanitization(self, client: TestClient, auth_token: str, db: Session):
        """Test filename is sanitized (path traversal removed)"""
        files = {
            'files': ('../../etc/passwd.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        # Should fail validation due to path traversal
        assert response.status_code == 201
        data = response.json()
        assert len(data['failed']) == 1
        assert 'path traversal' in data['failed'][0]['error'].lower()

    def test_upload_preserves_original_filename(self, client: TestClient, auth_token: str, db: Session):
        """Test original filename is preserved in document record"""
        files = {
            'files': ('My Order 2024.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 201
        data = response.json()
        uploaded = data['uploaded'][0]

        # Verify filename in database
        doc_id = UUID(uploaded['document_id'])
        document = db.query(Document).filter(Document.id == doc_id).first()
        assert document.file_name == 'My_Order_2024.pdf'  # Sanitized but readable

    def test_upload_mixed_success_and_failure(self, client: TestClient, auth_token: str):
        """Test batch upload with both successful and failed files"""
        files = [
            ('files', ('valid.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')),
            ('files', ('invalid.docx', io.BytesIO(b"fake"), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
            ('files', ('valid.csv', io.BytesIO(b"a,b\n1,2\n"), 'text/csv')),
        ]

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data['uploaded']) == 2  # PDF and CSV
        assert len(data['failed']) == 1    # DOCX
        assert data['failed'][0]['file_name'] == 'invalid.docx'

    def test_upload_creates_correct_timestamps(self, client: TestClient, auth_token: str, db: Session):
        """Test upload creates documents with correct timestamps"""
        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 201
        doc_id = UUID(response.json()['uploaded'][0]['document_id'])

        # Verify timestamps
        document = db.query(Document).filter(Document.id == doc_id).first()
        assert document.created_at is not None
        assert document.updated_at is not None
        assert document.created_at <= document.updated_at

    def test_upload_enforces_org_isolation(self, client: TestClient, auth_token: str, auth_token_org2: str, db: Session):
        """Test uploads are isolated by organization"""
        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\norg1\n"), 'application/pdf')
        }

        # Upload as org1
        response1 = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token}'}
        )
        assert response1.status_code == 201
        org1_doc_id = UUID(response1.json()['uploaded'][0]['document_id'])

        # Upload as org2
        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\norg2\n"), 'application/pdf')
        }
        response2 = client.post(
            '/api/v1/uploads',
            files=files,
            headers={'Authorization': f'Bearer {auth_token_org2}'}
        )
        assert response2.status_code == 201
        org2_doc_id = UUID(response2.json()['uploaded'][0]['document_id'])

        # Verify documents belong to different orgs
        doc1 = db.query(Document).filter(Document.id == org1_doc_id).first()
        doc2 = db.query(Document).filter(Document.id == org2_doc_id).first()
        assert doc1.org_id != doc2.org_id
