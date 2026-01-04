"""Integration tests for multi-tenant isolation

Tests cover:
- Cross-tenant data access prevention
- Org ID filtering on all queries
- 404 (not 403) responses for cross-tenant access
- Tenant isolation in all modules
- Org ID injection prevention

SSOT Reference: §11.2 (Tenant Isolation), §5.1 (Multi-Tenant Database)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from decimal import Decimal

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from models.org import Org
from models.user import User
from models.customer import Customer
from models.product import Product
from models.draft_order import DraftOrder, DraftOrderLine
from models.document import Document
from auth.password import hash_password
from auth.jwt import create_access_token


pytestmark = pytest.mark.integration


class TestDocumentIsolation:
    """Test document access is tenant-isolated"""

    def test_user_cannot_access_other_org_document(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user from org A cannot access document from org B"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create document in org B
        doc_b = Document(
            org_id=org_b.id,
            file_name="order.pdf",
            mime_type="application/pdf",
            sha256="abc123",
            status="STORED",
            s3_bucket="test-bucket",
            s3_key="test/order.pdf"
        )
        db_session.add(doc_b)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to access org B's document
        response = client.get(
            f"/api/v1/documents/{doc_b.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should return 404 (not 403) to prevent org enumeration
        assert response.status_code == 404

    def test_user_can_access_own_org_document(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user can access document from their own org"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create document in org A
        doc_a = Document(
            org_id=org_a.id,
            file_name="order.pdf",
            mime_type="application/pdf",
            sha256="abc123",
            status="STORED",
            s3_bucket="test-bucket",
            s3_key="test/order.pdf"
        )
        db_session.add(doc_a)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Access own org's document
        response = client.get(
            f"/api/v1/documents/{doc_a.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should succeed
        assert response.status_code == 200
        assert response.json()["id"] == str(doc_a.id)

    def test_list_documents_only_returns_own_org(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test listing documents only returns current org's documents"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create documents in both orgs
        doc_a = Document(
            org_id=org_a.id,
            file_name="order_a.pdf",
            mime_type="application/pdf",
            sha256="abc123",
            status="STORED",
            s3_bucket="test-bucket",
            s3_key="test/order_a.pdf"
        )
        doc_b = Document(
            org_id=org_b.id,
            file_name="order_b.pdf",
            mime_type="application/pdf",
            sha256="def456",
            status="STORED",
            s3_bucket="test-bucket",
            s3_key="test/order_b.pdf"
        )
        db_session.add_all([doc_a, doc_b])
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # List documents
        response = client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        documents = response.json()

        # Should only see org A's document
        assert len(documents) == 1
        assert documents[0]["id"] == str(doc_a.id)
        assert documents[0]["file_name"] == "order_a.pdf"


class TestCustomerIsolation:
    """Test customer access is tenant-isolated"""

    def test_user_cannot_access_other_org_customer(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user from org A cannot access customer from org B"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create customer in org B
        customer_b = Customer(
            org_id=org_b.id,
            name="Customer B",
            erp_customer_number="CUST-B-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer_b)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to access org B's customer
        response = client.get(
            f"/api/v1/customers/{customer_b.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should return 404
        assert response.status_code == 404

    def test_list_customers_only_returns_own_org(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test listing customers only returns current org's customers"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create customers in both orgs
        customer_a1 = Customer(
            org_id=org_a.id,
            name="Customer A1",
            erp_customer_number="CUST-A-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        customer_a2 = Customer(
            org_id=org_a.id,
            name="Customer A2",
            erp_customer_number="CUST-A-002",
            default_currency="EUR",
            default_language="de-DE"
        )
        customer_b = Customer(
            org_id=org_b.id,
            name="Customer B",
            erp_customer_number="CUST-B-001",
            default_currency="CHF",
            default_language="de-CH"
        )
        db_session.add_all([customer_a1, customer_a2, customer_b])
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # List customers
        response = client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        customers = response.json()

        # Should only see org A's customers
        assert len(customers) == 2
        customer_ids = {c["id"] for c in customers}
        assert str(customer_a1.id) in customer_ids
        assert str(customer_a2.id) in customer_ids
        assert str(customer_b.id) not in customer_ids


class TestProductIsolation:
    """Test product catalog is tenant-isolated"""

    def test_user_cannot_access_other_org_product(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user from org A cannot access product from org B"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create product in org B
        product_b = Product(
            org_id=org_b.id,
            internal_sku="SKU-B-001",
            name="Product B",
            default_uom="EA"
        )
        db_session.add(product_b)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to access org B's product
        response = client.get(
            f"/api/v1/products/{product_b.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should return 404
        assert response.status_code == 404

    def test_product_search_only_searches_own_org(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test product search only searches within current org"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create products with same name in both orgs
        product_a = Product(
            org_id=org_a.id,
            internal_sku="SKU-A-001",
            name="Widget 2000",
            default_uom="EA"
        )
        product_b = Product(
            org_id=org_b.id,
            internal_sku="SKU-B-001",
            name="Widget 2000",  # Same name
            default_uom="EA"
        )
        db_session.add_all([product_a, product_b])
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Search for "Widget"
        response = client.get(
            "/api/v1/products?search=Widget",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        products = response.json()

        # Should only find org A's product
        assert len(products) == 1
        assert products[0]["id"] == str(product_a.id)
        assert products[0]["internal_sku"] == "SKU-A-001"


class TestDraftOrderIsolation:
    """Test draft order access is tenant-isolated"""

    def test_user_cannot_access_other_org_draft_order(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user from org A cannot access draft order from org B"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create draft order in org B
        draft_b = DraftOrder(
            org_id=org_b.id,
            customer_id=uuid4(),  # Simplified for test
            status="NEW",
            currency="EUR"
        )
        db_session.add(draft_b)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to access org B's draft order
        response = client.get(
            f"/api/v1/drafts/{draft_b.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should return 404
        assert response.status_code == 404

    def test_update_draft_order_cross_tenant_fails(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user cannot update draft order from another org"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create draft order in org B
        draft_b = DraftOrder(
            org_id=org_b.id,
            customer_id=uuid4(),
            status="NEW",
            currency="EUR"
        )
        db_session.add(draft_b)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to update org B's draft
        response = client.patch(
            f"/api/v1/drafts/{draft_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"status": "APPROVED"}
        )

        # Should return 404
        assert response.status_code == 404

        # Verify draft was not updated
        db_session.refresh(draft_b)
        assert draft_b.status == "NEW"


class TestOrgIdInjectionPrevention:
    """Test org_id cannot be injected or manipulated"""

    def test_cannot_create_resource_for_other_org(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user cannot create resource in another org by injecting org_id"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to create customer for org B by injecting org_id
        response = client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "org_id": str(org_b.id),  # Attempt injection
                "name": "Malicious Customer",
                "erp_customer_number": "CUST-MAL-001",
                "default_currency": "EUR",
                "default_language": "de-DE"
            }
        )

        # Should create customer in org A (ignoring injected org_id)
        if response.status_code in [200, 201]:
            customer = db_session.query(Customer).filter(
                Customer.name == "Malicious Customer"
            ).first()

            # Should be created in org A, not org B
            assert customer.org_id == org_a.id
            assert customer.org_id != org_b.id

    def test_cannot_update_org_id_of_existing_resource(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test user cannot change org_id of existing resource"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create customer in org A
        customer_a = Customer(
            org_id=org_a.id,
            name="Customer A",
            erp_customer_number="CUST-A-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer_a)
        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to update customer's org_id to org B
        response = client.patch(
            f"/api/v1/customers/{customer_a.id}",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "org_id": str(org_b.id),  # Attempt to change org
                "name": "Updated Name"
            }
        )

        # Refresh customer
        db_session.refresh(customer_a)

        # org_id should not have changed
        assert customer_a.org_id == org_a.id


class TestCrossOrgStatistics:
    """Test statistics and aggregations are tenant-isolated"""

    def test_document_count_only_counts_own_org(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test document count only includes current org's documents"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create documents: 3 in org A, 5 in org B
        for i in range(3):
            doc_a = Document(
                org_id=org_a.id,
                file_name=f"order_a_{i}.pdf",
                mime_type="application/pdf",
                sha256=f"hash_a_{i}",
                status="STORED",
                s3_bucket="test-bucket",
                s3_key=f"test/order_a_{i}.pdf"
            )
            db_session.add(doc_a)

        for i in range(5):
            doc_b = Document(
                org_id=org_b.id,
                file_name=f"order_b_{i}.pdf",
                mime_type="application/pdf",
                sha256=f"hash_b_{i}",
                status="STORED",
                s3_bucket="test-bucket",
                s3_key=f"test/order_b_{i}.pdf"
            )
            db_session.add(doc_b)

        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Get document stats
        response = client.get(
            "/api/v1/stats/documents",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        stats = response.json()

        # Should only count org A's 3 documents
        assert stats["total_documents"] == 3

    def test_draft_order_stats_only_include_own_org(self, client: TestClient, db_session: Session, multi_org_setup):
        """Test draft order statistics only include current org's orders"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create drafts in org A: 2 NEW, 1 APPROVED
        for _ in range(2):
            draft = DraftOrder(
                org_id=org_a.id,
                customer_id=uuid4(),
                status="NEW",
                currency="EUR"
            )
            db_session.add(draft)

        draft_approved = DraftOrder(
            org_id=org_a.id,
            customer_id=uuid4(),
            status="APPROVED",
            currency="EUR"
        )
        db_session.add(draft_approved)

        # Create drafts in org B: 10 drafts
        for _ in range(10):
            draft = DraftOrder(
                org_id=org_b.id,
                customer_id=uuid4(),
                status="NEW",
                currency="CHF"
            )
            db_session.add(draft)

        db_session.commit()

        # Login as user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=user_a.org_id,
            role=user_a.role,
            email=user_a.email
        )

        # Get draft stats
        response = client.get(
            "/api/v1/stats/drafts",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 200
        stats = response.json()

        # Should only count org A's 3 drafts
        assert stats["total_drafts"] == 3
        assert stats["by_status"]["NEW"] == 2
        assert stats["by_status"]["APPROVED"] == 1


class TestDatabaseLevelIsolation:
    """Test org_id filtering at database query level"""

    def test_all_tables_have_org_id_column(self, db_session: Session):
        """Test all tenant tables include org_id column"""
        from models.base import Base

        # Tables that should have org_id (exclude global tables)
        tenant_tables = [
            "user",
            "customer",
            "customer_contact",
            "customer_price",
            "product",
            "product_embedding",
            "sku_mapping",
            "document",
            "draft_order",
            "draft_order_line",
            "inbound_message",
            "extraction_run",
            "validation_issue",
            "erp_connection",
            "erp_export",
            "erp_push_log",
            "ai_call_log",
            "customer_detection_candidate",
        ]

        # Global tables (no org_id)
        global_tables = ["org", "audit_log"]

        for table_name in tenant_tables:
            table = Base.metadata.tables.get(table_name)
            assert table is not None, f"Table {table_name} not found"
            assert "org_id" in table.columns, f"Table {table_name} missing org_id column"

    def test_query_always_filters_by_org_id(self, db_session: Session, multi_org_setup):
        """Test direct database queries filter by org_id"""
        org_a, org_b, user_a, user_b = multi_org_setup

        # Create customers in both orgs
        customer_a = Customer(
            org_id=org_a.id,
            name="Customer A",
            erp_customer_number="CUST-A-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        customer_b = Customer(
            org_id=org_b.id,
            name="Customer B",
            erp_customer_number="CUST-B-001",
            default_currency="CHF",
            default_language="de-CH"
        )
        db_session.add_all([customer_a, customer_b])
        db_session.commit()

        # Query with org_id filter (mimics API layer)
        customers_org_a = db_session.query(Customer).filter(
            Customer.org_id == org_a.id
        ).all()

        # Should only return org A's customer
        assert len(customers_org_a) == 1
        assert customers_org_a[0].id == customer_a.id

        # Query for org B
        customers_org_b = db_session.query(Customer).filter(
            Customer.org_id == org_b.id
        ).all()

        # Should only return org B's customer
        assert len(customers_org_b) == 1
        assert customers_org_b[0].id == customer_b.id
