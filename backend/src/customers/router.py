"""Customer management API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, and_
from typing import Optional
from uuid import UUID
import logging

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..models.user import User
from ..models.customer import Customer
from ..models.customer_contact import CustomerContact
from .schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerContactCreate,
    CustomerContactResponse,
    ImportResult,
)
from .import_service import CustomerImportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


# ============================================================================
# Customer CRUD Endpoints
# ============================================================================

@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Create a new customer (ADMIN/INTEGRATOR only).

    Args:
        customer_data: Customer creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created customer

    Raises:
        HTTPException 400: If ERP customer number already exists
    """
    # Check if ERP customer number already exists
    if customer_data.erp_customer_number:
        stmt = select(Customer).where(
            Customer.org_id == current_user.org_id,
            Customer.erp_customer_number == customer_data.erp_customer_number
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer with ERP number '{customer_data.erp_customer_number}' already exists"
            )

    # Create customer
    customer = Customer(
        org_id=current_user.org_id,
        name=customer_data.name,
        erp_customer_number=customer_data.erp_customer_number,
        email=customer_data.email,
        default_currency=customer_data.default_currency,
        default_language=customer_data.default_language,
        billing_address=customer_data.billing_address.model_dump() if customer_data.billing_address else None,
        shipping_address=customer_data.shipping_address.model_dump() if customer_data.shipping_address else None,
        notes=customer_data.notes,
        is_active=customer_data.is_active
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    # Convert to response model
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    q: Optional[str] = Query(None, description="Search query for name or ERP number"),
    erp_number: Optional[str] = Query(None, description="Filter by exact ERP number"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List customers with pagination and search/filter.

    Args:
        q: Search query (searches name and ERP number)
        erp_number: Filter by exact ERP number
        page: Page number (1-indexed)
        per_page: Items per page (max 100)
        db: Database session
        current_user: Authenticated user

    Returns:
        Paginated list of customers with contact counts
    """
    # Build base query
    stmt = select(Customer).where(Customer.org_id == current_user.org_id)

    # Apply search filter
    if q:
        search_pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(search_pattern),
                Customer.erp_customer_number.ilike(search_pattern)
            )
        )

    # Apply ERP number filter
    if erp_number:
        stmt = stmt.where(Customer.erp_customer_number == erp_number)

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar()

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.order_by(Customer.name).offset(offset).limit(per_page)

    # Execute query
    customers = db.execute(stmt).scalars().all()

    # Get contact counts for each customer
    customer_ids = [c.id for c in customers]
    if customer_ids:
        contact_counts_stmt = (
            select(
                CustomerContact.customer_id,
                func.count(CustomerContact.id).label('count')
            )
            .where(CustomerContact.customer_id.in_(customer_ids))
            .group_by(CustomerContact.customer_id)
        )
        contact_counts = {row[0]: row[1] for row in db.execute(contact_counts_stmt).all()}
    else:
        contact_counts = {}

    # Convert to response models with contact counts
    items = []
    for customer in customers:
        customer_dict = customer.to_dict()
        customer_dict['contact_count'] = contact_counts.get(customer.id, 0)
        items.append(CustomerResponse.model_validate(customer_dict))

    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single customer by ID with contacts.

    Args:
        customer_id: Customer UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Customer details with contacts

    Raises:
        HTTPException 404: If customer not found or belongs to different org
    """
    stmt = select(Customer).where(
        Customer.id == customer_id,
        Customer.org_id == current_user.org_id
    )
    customer = db.execute(stmt).scalar_one_or_none()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Get contacts
    contacts_stmt = select(CustomerContact).where(
        CustomerContact.customer_id == customer_id
    ).order_by(CustomerContact.is_primary.desc(), CustomerContact.email)
    contacts = db.execute(contacts_stmt).scalars().all()

    # Convert to response model
    customer_dict = customer.to_dict()
    customer_dict['contacts'] = [CustomerContactResponse.model_validate(c) for c in contacts]

    return CustomerResponse.model_validate(customer_dict)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Update a customer (partial update, ADMIN/INTEGRATOR only).

    Args:
        customer_id: Customer UUID
        customer_data: Customer update data (partial)
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated customer

    Raises:
        HTTPException 404: If customer not found
        HTTPException 400: If ERP number conflicts
    """
    # Get customer
    stmt = select(Customer).where(
        Customer.id == customer_id,
        Customer.org_id == current_user.org_id
    )
    customer = db.execute(stmt).scalar_one_or_none()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Check ERP number uniqueness if being updated
    if customer_data.erp_customer_number is not None and \
       customer_data.erp_customer_number != customer.erp_customer_number:
        stmt = select(Customer).where(
            Customer.org_id == current_user.org_id,
            Customer.erp_customer_number == customer_data.erp_customer_number,
            Customer.id != customer_id
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer with ERP number '{customer_data.erp_customer_number}' already exists"
            )

    # Update fields (only if provided)
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ('billing_address', 'shipping_address'):
            # Convert Pydantic model to dict for JSONB
            if value is not None:
                setattr(customer, field, value.model_dump() if hasattr(value, 'model_dump') else value)
            else:
                setattr(customer, field, None)
        else:
            setattr(customer, field, value)

    db.commit()
    db.refresh(customer)

    return CustomerResponse.model_validate(customer)


# ============================================================================
# Customer Contact Endpoints
# ============================================================================

@router.post("/{customer_id}/contacts", response_model=CustomerContactResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_contact(
    customer_id: UUID,
    contact_data: CustomerContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new contact for a customer.

    Args:
        customer_id: Customer UUID
        contact_data: Contact creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created contact

    Raises:
        HTTPException 404: If customer not found
        HTTPException 400: If email already exists for customer
    """
    # Verify customer exists and belongs to user's org
    stmt = select(Customer).where(
        Customer.id == customer_id,
        Customer.org_id == current_user.org_id
    )
    customer = db.execute(stmt).scalar_one_or_none()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Check if email already exists for this customer
    stmt = select(CustomerContact).where(
        CustomerContact.customer_id == customer_id,
        CustomerContact.email == contact_data.email.lower()
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contact with email '{contact_data.email}' already exists for this customer"
        )

    # If setting as primary, unset other primary contacts
    if contact_data.is_primary:
        stmt = select(CustomerContact).where(
            CustomerContact.customer_id == customer_id,
            CustomerContact.is_primary == True
        )
        primary_contacts = db.execute(stmt).scalars().all()
        for contact in primary_contacts:
            contact.is_primary = False

    # Create contact
    contact = CustomerContact(
        org_id=current_user.org_id,
        customer_id=customer_id,
        email=contact_data.email.lower(),
        name=contact_data.name,
        phone=contact_data.phone,
        role=contact_data.role,
        is_primary=contact_data.is_primary
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return CustomerContactResponse.model_validate(contact)


@router.delete("/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_contact(
    customer_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Delete a customer contact (ADMIN/INTEGRATOR only).

    Args:
        customer_id: Customer UUID
        contact_id: Contact UUID
        db: Database session
        current_user: Authenticated user

    Raises:
        HTTPException 404: If contact not found
    """
    # Get contact and verify it belongs to the customer and org
    stmt = select(CustomerContact).where(
        CustomerContact.id == contact_id,
        CustomerContact.customer_id == customer_id,
        CustomerContact.org_id == current_user.org_id
    )
    contact = db.execute(stmt).scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )

    db.delete(contact)
    db.commit()


# ============================================================================
# Import Router (separate prefix for /imports/customers)
# ============================================================================

import_router = APIRouter(prefix="/imports", tags=["imports"])


@import_router.post("/customers", response_model=ImportResult)
async def import_customers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Import customers from CSV file (ADMIN/INTEGRATOR only).

    CSV Format:
    - Required columns: name, default_currency, default_language
    - Optional columns: erp_customer_number, email, notes,
      billing_street, billing_city, billing_postal_code, billing_country,
      shipping_street, shipping_city, shipping_postal_code, shipping_country,
      contact_email, contact_name, contact_phone, contact_is_primary

    Args:
        file: CSV file upload
        db: Database session
        current_user: Authenticated user

    Returns:
        ImportResult with counts and errors
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    # Read file content
    content = await file.read()

    # Import customers
    import_service = CustomerImportService(db, current_user.org_id)
    from io import BytesIO
    result = import_service.import_customers(BytesIO(content))

    return result
