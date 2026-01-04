"""Security tests for SQL injection prevention

Tests cover:
- SQL injection in search queries
- SQL injection in filters
- SQL injection in sort parameters
- Parameterized query validation
- ORM-level protection

SSOT Reference: §11.1 (Security), §11.2 (Testing Requirements)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from models.org import Org
from models.user import User
from models.customer import Customer
from models.product import Product
from auth.password import hash_password
from auth.jwt import create_access_token


pytestmark = pytest.mark.security


class TestSearchQueryInjection:
    """Test SQL injection attempts in search queries"""

    def test_customer_search_with_sql_injection_attempt(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test customer search with SQL injection payload"""
        # Create test customer
        customer = Customer(
            org_id=test_org.id,
            name="ACME GmbH",
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        # Login
        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection payloads
        sql_injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE customer; --",
            "1' UNION SELECT * FROM user WHERE '1'='1",
            "' OR 1=1 --",
            "admin'--",
            "' OR 'a'='a",
            "1'; DELETE FROM customer WHERE 'a'='a",
        ]

        for payload in sql_injection_payloads:
            response = client.get(
                f"/api/v1/customers?search={payload}",
                headers={"Authorization": f"Bearer {token}"}
            )

            # Should not crash or expose data
            assert response.status_code in [200, 400, 422]

            if response.status_code == 200:
                # Should return empty or safe results, never all customers
                data = response.json()
                # Handle paginated response {"items": [...], ...}
                if isinstance(data, dict) and "items" in data:
                    results = data["items"]
                else:
                    results = data
                assert isinstance(results, list)
                # Should not return more results than exist
                assert len(results) <= 1

        # Verify customer table still exists and data intact
        customer_check = db_session.query(Customer).filter(
            Customer.id == customer.id
        ).first()
        assert customer_check is not None
        assert customer_check.name == "ACME GmbH"

    def test_product_search_with_sql_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test product search with SQL injection payload"""
        # Create test product
        product = Product(
            org_id=test_org.id,
            internal_sku="SKU-001",
            name="Widget",
            base_uom="EA"
        )
        db_session.add(product)
        db_session.commit()

        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection attempt
        response = client.get(
            "/api/v1/products?search=' OR 1=1--",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code in [200, 400, 422]

        # Product table should be intact
        product_check = db_session.query(Product).filter(
            Product.id == product.id
        ).first()
        assert product_check is not None


class TestFilterInjection:
    """Test SQL injection in filter parameters"""

    def test_customer_filter_by_erp_number_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test filtering customers with SQL injection in ERP number"""
        customer = Customer(
            org_id=test_org.id,
            name="ACME GmbH",
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection in filter
        response = client.get(
            "/api/v1/customers?erp_number=' OR '1'='1",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code in [200, 400, 422]

        if response.status_code == 200:
            data = response.json()
            # Handle paginated response {"items": [...], ...}
            if isinstance(data, dict) and "items" in data:
                results = data["items"]
            else:
                results = data
            # Should not return all customers
            assert len(results) <= 1

    def test_date_filter_sql_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test date filter with SQL injection attempt"""
        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection in date filter
        response = client.get(
            "/api/v1/draft-orders?created_after=2024-01-01' OR '1'='1",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should handle safely
        assert response.status_code in [200, 400, 422]


class TestSortParameterInjection:
    """Test SQL injection in sort/order parameters"""

    def test_sort_parameter_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test sort parameter with SQL injection"""
        customer = Customer(
            org_id=test_org.id,
            name="ACME GmbH",
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection in sort parameter
        malicious_sorts = [
            "name; DROP TABLE customer; --",
            "name' OR '1'='1",
            "(SELECT * FROM user)",
        ]

        for sort_param in malicious_sorts:
            response = client.get(
                f"/api/v1/customers?sort={sort_param}",
                headers={"Authorization": f"Bearer {token}"}
            )

            # Should reject or handle safely
            assert response.status_code in [200, 400, 422]

        # Verify customer table still exists
        customer_check = db_session.query(Customer).filter(
            Customer.id == customer.id
        ).first()
        assert customer_check is not None


class TestIDParameterInjection:
    """Test SQL injection in ID parameters"""

    def test_customer_id_sql_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test customer ID endpoint with SQL injection"""
        customer = Customer(
            org_id=test_org.id,
            name="ACME GmbH",
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection in UUID parameter
        malicious_ids = [
            "' OR '1'='1",
            "1 OR 1=1",
            "'; DROP TABLE customer; --",
        ]

        for malicious_id in malicious_ids:
            response = client.get(
                f"/api/v1/customers/{malicious_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

            # Should return 400/422 for invalid UUID format
            assert response.status_code in [400, 422, 404]

        # Verify customer still exists
        customer_check = db_session.query(Customer).filter(
            Customer.id == customer.id
        ).first()
        assert customer_check is not None


class TestBodyParameterInjection:
    """Test SQL injection in request body"""

    def test_create_customer_with_sql_injection_in_name(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test creating customer with SQL injection in name field"""
        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection in customer name
        response = client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "'; DROP TABLE customer; --",
                "erp_customer_number": "CUST-001",
                "default_currency": "EUR",
                "default_language": "de-DE"
            }
        )

        # Should either accept as literal string or reject
        if response.status_code in [200, 201]:
            customer_id = response.json()["id"]

            # Name should be stored as literal string
            customer = db_session.query(Customer).filter(
                Customer.id == customer_id
            ).first()
            assert customer.name == "'; DROP TABLE customer; --"

        # Customer table should still exist
        customers = db_session.query(Customer).all()
        assert customers is not None

    def test_update_customer_with_sql_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test updating customer with SQL injection payload"""
        customer = Customer(
            org_id=test_org.id,
            name="ACME GmbH",
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # SQL injection in update
        response = client.patch(
            f"/api/v1/customers/{customer.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "' OR '1'='1",
                "erp_customer_number": "'; DROP TABLE customer; --"
            }
        )

        if response.status_code in [200, 204]:
            # Values should be stored as literal strings
            db_session.refresh(customer)
            assert customer.name == "' OR '1'='1"
            assert customer.erp_customer_number == "'; DROP TABLE customer; --"


class TestORMProtection:
    """Test ORM-level SQL injection protection"""

    def test_sqlalchemy_parameterized_queries(self, db_session: Session, test_org: Org):
        """Test SQLAlchemy uses parameterized queries (not vulnerable to injection)"""
        # Create customer with potential SQL injection characters
        customer = Customer(
            org_id=test_org.id,
            name="O'Reilly & Sons",  # Contains SQL special chars
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        # Query with filter (should use parameterized query)
        result = db_session.query(Customer).filter(
            Customer.name == "O'Reilly & Sons"
        ).first()

        assert result is not None
        assert result.id == customer.id
        assert result.name == "O'Reilly & Sons"

    def test_like_query_escaping(self, db_session: Session, test_org: Org):
        """Test LIKE queries properly escape special characters"""
        customer = Customer(
            org_id=test_org.id,
            name="100% Discount Store",  # % is LIKE wildcard
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        # LIKE query should escape % character
        result = db_session.query(Customer).filter(
            Customer.name.like("%100\\% Discount%")
        ).first()

        assert result is not None
        assert result.id == customer.id


class TestBlindSQLInjection:
    """Test blind SQL injection attempts"""

    def test_timing_based_blind_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test timing-based blind SQL injection attempts"""
        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # Timing-based injection attempts
        timing_payloads = [
            "'; WAITFOR DELAY '00:00:05'--",  # SQL Server
            "'; SELECT SLEEP(5)--",  # MySQL
            "'; SELECT pg_sleep(5)--",  # PostgreSQL
        ]

        import time

        for payload in timing_payloads:
            start = time.time()

            response = client.get(
                f"/api/v1/customers?search={payload}",
                headers={"Authorization": f"Bearer {token}"}
            )

            elapsed = time.time() - start

            # Should not cause delay (protected against timing attacks)
            assert elapsed < 2.0  # Should respond quickly
            assert response.status_code in [200, 400, 422]

    def test_boolean_based_blind_injection(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test boolean-based blind SQL injection"""
        # Create test data
        customer = Customer(
            org_id=test_org.id,
            name="ACME GmbH",
            erp_customer_number="CUST-001",
            default_currency="EUR",
            default_language="de-DE"
        )
        db_session.add(customer)
        db_session.commit()

        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # Boolean-based payloads
        response_true = client.get(
            "/api/v1/customers?search=' AND '1'='1",
            headers={"Authorization": f"Bearer {token}"}
        )

        response_false = client.get(
            "/api/v1/customers?search=' AND '1'='2",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Responses should be similar (not leak boolean conditions)
        assert response_true.status_code == response_false.status_code


class TestSecondOrderInjection:
    """Test second-order SQL injection (stored payloads)"""

    def test_stored_sql_injection_in_customer_name(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test SQL injection payload stored in database doesn't execute on retrieval"""
        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # Create customer with SQL injection in name
        response = client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "'; DROP TABLE customer; --",
                "erp_customer_number": "CUST-001",
                "default_currency": "EUR",
                "default_language": "de-DE"
            }
        )

        if response.status_code in [200, 201]:
            customer_id = response.json()["id"]

            # Retrieve customer (payload should not execute)
            get_response = client.get(
                f"/api/v1/customers/{customer_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert get_response.status_code == 200

            # Customer table should still exist
            customers = db_session.query(Customer).all()
            assert len(customers) >= 1
