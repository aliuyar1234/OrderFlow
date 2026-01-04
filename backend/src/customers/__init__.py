"""Customer management module for OrderFlow"""

from .schemas import (
    AddressSchema,
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerContactCreate,
    CustomerContactResponse,
)
from .router import router, import_router

__all__ = [
    "AddressSchema",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerContactCreate",
    "CustomerContactResponse",
    "router",
    "import_router",
]
