"""Product catalog API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, and_, text
from typing import Optional, List
from uuid import UUID
import logging

from ..database import get_db
from ..dependencies import get_current_user, require_roles
from ..models.user import User
from ..models.product import Product, UnitOfMeasure
from .schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductSearchParams,
    UnitOfMeasureCreate,
    UnitOfMeasureUpdate,
    UnitOfMeasureResponse,
    ProductImportResult,
)
from .import_service import ProductImportService, generate_error_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# ============================================================================
# Product CRUD Endpoints
# ============================================================================

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Create a new product (ADMIN/INTEGRATOR only).

    Args:
        product_data: Product creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created product

    Raises:
        HTTPException 400: If product with same SKU already exists
    """
    # Check if product with same SKU already exists
    stmt = select(Product).where(
        Product.org_id == current_user.org_id,
        Product.internal_sku == product_data.internal_sku
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{product_data.internal_sku}' already exists"
        )

    # Create product
    product = Product(
        org_id=current_user.org_id,
        internal_sku=product_data.internal_sku,
        name=product_data.name,
        description=product_data.description,
        base_uom=product_data.base_uom,
        uom_conversions_json=product_data.uom_conversions_json,
        active=product_data.active,
        attributes_json=product_data.attributes_json
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return ProductResponse.model_validate(product)


@router.get("", response_model=List[ProductResponse])
async def list_products(
    search: Optional[str] = Query(None, description="Search term for SKU, name, or description"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List products with search and pagination.

    Args:
        search: Search term for SKU, name, or description
        active: Filter by active status
        limit: Number of results per page
        offset: Number of results to skip
        db: Database session
        current_user: Authenticated user

    Returns:
        List of products
    """
    # Build query
    query = select(Product).where(Product.org_id == current_user.org_id)

    # Apply active filter
    if active is not None:
        query = query.where(Product.active == active)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Product.internal_sku.ilike(search_term),
                Product.name.ilike(search_term),
                Product.description.ilike(search_term)
            )
        )

    # Apply ordering
    query = query.order_by(Product.name)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = db.execute(query)
    products = result.scalars().all()

    return [ProductResponse.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single product by ID.

    Args:
        product_id: Product UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Product details

    Raises:
        HTTPException 404: If product not found or belongs to different org
    """
    stmt = select(Product).where(
        Product.id == product_id,
        Product.org_id == current_user.org_id
    )
    product = db.execute(stmt).scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR", "OPS"]))
):
    """
    Update a product (ADMIN/INTEGRATOR/OPS only).

    Args:
        product_id: Product UUID
        product_data: Product update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated product

    Raises:
        HTTPException 404: If product not found or belongs to different org
    """
    stmt = select(Product).where(
        Product.id == product_id,
        Product.org_id == current_user.org_id
    )
    product = db.execute(stmt).scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Update fields
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return ProductResponse.model_validate(product)


# ============================================================================
# Product Import Endpoints
# ============================================================================

@router.post("/import", response_model=ProductImportResult)
async def import_products(
    file: UploadFile = File(..., description="CSV file with products"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Import products from CSV file (ADMIN/INTEGRATOR only).

    CSV must have columns:
    - Required: internal_sku, name, base_uom
    - Optional: description, manufacturer, ean, category, uom_conversions (JSON string)

    Args:
        file: CSV file
        db: Database session
        current_user: Authenticated user

    Returns:
        Import result with counts and errors
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV"
        )

    # Read file bytes
    file_bytes = await file.read()

    # Import products
    import_service = ProductImportService(db, current_user.org_id)
    result = import_service.import_from_csv(file_bytes)

    logger.info(
        f"Product import completed for org {current_user.org_id}: "
        f"{result.imported_count} imported, {result.error_count} errors"
    )

    return result


@router.post("/import/errors", response_class=Response)
async def get_import_errors_csv(
    result: ProductImportResult,
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Generate CSV with import errors.

    Args:
        result: Import result with errors
        current_user: Authenticated user

    Returns:
        CSV file with errors
    """
    csv_content = generate_error_csv(result)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=product_import_errors.csv"
        }
    )


# ============================================================================
# Unit of Measure Endpoints
# ============================================================================

@router.post("/uom", response_model=UnitOfMeasureResponse, status_code=status.HTTP_201_CREATED)
async def create_unit_of_measure(
    uom_data: UnitOfMeasureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INTEGRATOR"]))
):
    """
    Create a new unit of measure (ADMIN/INTEGRATOR only).

    Args:
        uom_data: UoM creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created UoM

    Raises:
        HTTPException 400: If UoM with same code already exists
    """
    # Check if UoM with same code already exists
    stmt = select(UnitOfMeasure).where(
        UnitOfMeasure.org_id == current_user.org_id,
        UnitOfMeasure.code == uom_data.code
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unit of measure with code '{uom_data.code}' already exists"
        )

    # Create UoM
    uom = UnitOfMeasure(
        org_id=current_user.org_id,
        code=uom_data.code,
        name=uom_data.name,
        conversion_factor=uom_data.conversion_factor
    )
    db.add(uom)
    db.commit()
    db.refresh(uom)

    return UnitOfMeasureResponse.model_validate(uom)


@router.get("/uom", response_model=List[UnitOfMeasureResponse])
async def list_units_of_measure(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all units of measure for the current organization.

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        List of UoMs
    """
    stmt = select(UnitOfMeasure).where(
        UnitOfMeasure.org_id == current_user.org_id
    ).order_by(UnitOfMeasure.code)

    result = db.execute(stmt)
    uoms = result.scalars().all()

    return [UnitOfMeasureResponse.model_validate(uom) for uom in uoms]
