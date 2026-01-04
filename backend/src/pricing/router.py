"""Customer price management API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
import logging

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..models.user import User
from ..models.customer_price import CustomerPrice
from .schemas import (
    CustomerPriceCreate,
    CustomerPriceUpdate,
    CustomerPriceResponse,
    CustomerPriceListResponse,
    PriceImportResult,
    PriceLookupRequest,
    PriceLookupResponse,
)
from .service import PriceService
from .import_service import PriceImportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer-prices", tags=["customer-prices"])


# ============================================================================
# Customer Price CRUD Endpoints
# ============================================================================

@router.post("", response_model=CustomerPriceResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_price(
    price_data: CustomerPriceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Create a new customer price (ADMIN/INTEGRATOR only).

    Args:
        price_data: Customer price creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created customer price
    """
    price = PriceService.create_price(
        db=db,
        org_id=current_user.org_id,
        customer_id=price_data.customer_id,
        internal_sku=price_data.internal_sku,
        currency=price_data.currency,
        uom=price_data.uom,
        unit_price=price_data.unit_price,
        min_qty=price_data.min_qty,
        valid_from=price_data.valid_from,
        valid_to=price_data.valid_to,
        source=price_data.source
    )

    return CustomerPriceResponse.model_validate(price)


@router.get("", response_model=CustomerPriceListResponse)
async def list_customer_prices(
    customer_id: Optional[UUID] = Query(None, description="Filter by customer ID"),
    internal_sku: Optional[str] = Query(None, description="Filter by internal SKU"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(100, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List customer prices with pagination and filters.

    Args:
        customer_id: Filter by customer ID
        internal_sku: Filter by internal SKU
        currency: Filter by currency code
        page: Page number (1-indexed)
        per_page: Items per page (max 500)
        db: Database session
        current_user: Authenticated user

    Returns:
        Paginated list of customer prices
    """
    offset = (page - 1) * per_page

    prices, total = PriceService.get_customer_prices(
        db=db,
        org_id=current_user.org_id,
        customer_id=customer_id,
        internal_sku=internal_sku,
        currency=currency,
        limit=per_page,
        offset=offset
    )

    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    # Convert to response models
    price_responses = [CustomerPriceResponse.model_validate(p) for p in prices]

    return CustomerPriceListResponse(
        items=price_responses,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{price_id}", response_model=CustomerPriceResponse)
async def get_customer_price(
    price_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific customer price by ID.

    Args:
        price_id: Customer price ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Customer price

    Raises:
        HTTPException 404: If price not found
    """
    price = db.query(CustomerPrice).filter(
        CustomerPrice.id == price_id,
        CustomerPrice.org_id == current_user.org_id
    ).first()

    if not price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer price not found"
        )

    return CustomerPriceResponse.model_validate(price)


@router.patch("/{price_id}", response_model=CustomerPriceResponse)
async def update_customer_price(
    price_id: UUID,
    price_data: CustomerPriceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Update an existing customer price (ADMIN/INTEGRATOR only).

    Args:
        price_id: Customer price ID
        price_data: Customer price update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated customer price

    Raises:
        HTTPException 404: If price not found
    """
    price = PriceService.update_price(
        db=db,
        price_id=price_id,
        org_id=current_user.org_id,
        unit_price=price_data.unit_price,
        min_qty=price_data.min_qty,
        valid_from=price_data.valid_from,
        valid_to=price_data.valid_to,
        source=price_data.source
    )

    if not price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer price not found"
        )

    return CustomerPriceResponse.model_validate(price)


@router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_price(
    price_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Delete a customer price (ADMIN/INTEGRATOR only).

    Args:
        price_id: Customer price ID
        db: Database session
        current_user: Authenticated user

    Raises:
        HTTPException 404: If price not found
    """
    deleted = PriceService.delete_price(
        db=db,
        price_id=price_id,
        org_id=current_user.org_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer price not found"
        )


# ============================================================================
# Price Lookup Endpoint
# ============================================================================

@router.post("/lookup", response_model=PriceLookupResponse)
async def lookup_price(
    lookup_request: PriceLookupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lookup the best matching customer price for a given quantity.

    Implements price tier selection algorithm per spec:
    - Filters by customer_id, internal_sku, currency, uom
    - Filters by date range (valid_from/valid_to)
    - Filters tiers where min_qty <= qty
    - Returns tier with highest min_qty (best match)

    Args:
        lookup_request: Price lookup request data
        db: Database session
        current_user: Authenticated user

    Returns:
        Price lookup response with found price or null
    """
    as_of_date = lookup_request.date or date.today()

    price = PriceService.select_price_tier(
        db=db,
        org_id=current_user.org_id,
        customer_id=lookup_request.customer_id,
        internal_sku=lookup_request.internal_sku,
        currency=lookup_request.currency,
        uom=lookup_request.uom,
        qty=lookup_request.qty,
        as_of_date=as_of_date
    )

    if price:
        return PriceLookupResponse(
            found=True,
            unit_price=price.unit_price,
            min_qty=price.min_qty,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            price_id=price.id
        )
    else:
        return PriceLookupResponse(found=False)


# ============================================================================
# CSV Import Endpoint
# ============================================================================

@router.post("/import", response_model=PriceImportResult)
async def import_customer_prices(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Import customer prices from CSV file (ADMIN/INTEGRATOR only).

    CSV format per §8.8:
    - erp_customer_number OR customer_name (one required)
    - internal_sku (required)
    - currency (required)
    - uom (required)
    - unit_price (required)
    - min_qty (optional, default 1.000)
    - valid_from (optional, YYYY-MM-DD)
    - valid_to (optional, YYYY-MM-DD)

    UPSERT behavior:
    - If price exists with same (customer_id, internal_sku, currency, uom, min_qty), update it
    - Otherwise, insert new price

    Args:
        file: CSV file upload
        db: Database session
        current_user: Authenticated user

    Returns:
        Import result with counts and errors

    Raises:
        HTTPException 400: If file is not CSV
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    try:
        # Read file content
        content = await file.read()

        # Import prices
        import_service = PriceImportService(db, current_user.org_id)
        result = import_service.import_prices(content)

        logger.info(
            f"Price import completed: {result.imported} imported, "
            f"{result.updated} updated, {result.failed} failed"
        )

        return result

    except Exception as e:
        logger.exception("Error during price import")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )
