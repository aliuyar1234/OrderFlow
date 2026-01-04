"""Match confidence scoring with penalties.

SSOT Reference: §7.7.6 (Concrete Scoring Formula), §7.9 (Match Confidence)
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from ..models.product import Product


class MatchScorer:
    """Calculate match confidence scores with UoM and price penalties.

    Implements the hybrid scoring formula from SSOT §7.7.6:
    - S_tri = max(S_tri_sku, 0.7 * S_tri_desc)
    - S_emb = clamp((cosine_sim + 1) / 2, 0..1)
    - S_hybrid_raw = max(0.99 * S_map, 0.62 * S_tri + 0.38 * S_emb)
    - P_uom = 1.0 (compatible) | 0.9 (missing) | 0.2 (incompatible)
    - P_price = 1.0 (within tolerance) | 0.85 (warning) | 0.65 (strong mismatch)
    - match_confidence = clamp(S_hybrid_raw * P_uom * P_price, 0..1)
    """

    def __init__(self, db: Session, org_id: UUID):
        """Initialize scorer with database session and org context.

        Args:
            db: Database session
            org_id: Organization UUID for settings lookup
        """
        self.db = db
        self.org_id = org_id

    def calculate_confidence(
        self,
        product: Product,
        s_tri_sku: float,
        s_tri_desc: float,
        s_emb: float,
        s_map: float,
        line_uom: Optional[str],
        line_unit_price: Optional[Decimal],
        line_qty: Optional[Decimal],
        line_currency: Optional[str],
        customer_id: UUID,
        order_date: Optional[str]
    ) -> Dict[str, Any]:
        """Calculate final match confidence with all components.

        Args:
            product: Product candidate
            s_tri_sku: Trigram similarity on SKU (0.0-1.0)
            s_tri_desc: Trigram similarity on description (0.0-1.0)
            s_emb: Embedding similarity (0.0-1.0)
            s_map: Mapping score (1.0 if confirmed mapping, else 0.0)
            line_uom: Line UoM code
            line_unit_price: Line unit price
            line_qty: Line quantity
            line_currency: Line currency code
            customer_id: Customer UUID for price lookup
            order_date: Order date for price validity

        Returns:
            Dict with confidence, features, and debug info
        """
        # Calculate trigram score (max of SKU and desc with 0.7 weight)
        s_tri = max(s_tri_sku, 0.7 * s_tri_desc)

        # Calculate hybrid raw score
        if s_map > 0:
            s_hybrid_raw = 0.99 * s_map
        else:
            s_hybrid_raw = max(0.0, 0.62 * s_tri + 0.38 * s_emb)

        # Calculate penalties
        p_uom = self._calculate_uom_penalty(product, line_uom)
        p_price = self._calculate_price_penalty(
            product, line_unit_price, line_qty, line_currency, customer_id, order_date
        )

        # Final confidence
        confidence = max(0.0, min(1.0, s_hybrid_raw * p_uom * p_price))

        return {
            "confidence": confidence,
            "features": {
                "S_tri": s_tri,
                "S_tri_sku": s_tri_sku,
                "S_tri_desc": s_tri_desc,
                "S_emb": s_emb,
                "S_map": s_map,
                "S_hybrid_raw": s_hybrid_raw,
                "P_uom": p_uom,
                "P_price": p_price
            }
        }

    def _calculate_uom_penalty(self, product: Product, line_uom: Optional[str]) -> float:
        """Calculate UoM compatibility penalty.

        SSOT Reference: §FR-017

        Args:
            product: Product with base_uom and uom_conversions_json
            line_uom: Line UoM code

        Returns:
            1.0 (compatible), 0.9 (missing/unknown), 0.2 (incompatible)
        """
        if not line_uom:
            return 0.9  # Missing UoM

        # Check if UoM matches base UoM
        if line_uom == product.base_uom:
            return 1.0  # Compatible

        # Check if UoM is in conversions
        uom_conversions = product.uom_conversions_json or {}
        if line_uom in uom_conversions:
            return 1.0  # Compatible via conversion

        # Incompatible UoM
        return 0.2

    def _calculate_price_penalty(
        self,
        product: Product,
        line_unit_price: Optional[Decimal],
        line_qty: Optional[Decimal],
        line_currency: Optional[str],
        customer_id: UUID,
        order_date: Optional[str]
    ) -> float:
        """Calculate price mismatch penalty.

        SSOT Reference: §FR-018

        Args:
            product: Product candidate
            line_unit_price: Line unit price
            line_qty: Line quantity (for tier lookup)
            line_currency: Line currency code
            customer_id: Customer UUID for price lookup
            order_date: Order date for price validity

        Returns:
            1.0 (within tolerance or no price), 0.85 (warning), 0.65 (strong mismatch)
        """
        if not line_unit_price:
            return 1.0  # No price to check

        # TODO: Implement customer_price lookup when customer_price table exists
        # For now, return 1.0 (no penalty) as customer prices not yet implemented
        # Future implementation:
        # customer_price = self._find_customer_price(
        #     customer_id, product.internal_sku, line_qty, line_currency, order_date
        # )
        # if not customer_price:
        #     return 1.0  # No reference price
        #
        # tolerance = self._get_org_setting("price_tolerance_percent", 5.0) / 100
        # delta = abs(line_unit_price - customer_price.unit_price) / customer_price.unit_price
        #
        # if delta <= tolerance:
        #     return 1.0
        # elif delta <= 2 * tolerance:
        #     return 0.85
        # else:
        #     return 0.65

        return 1.0  # Default: no price penalty until customer_price implemented

    def _get_org_setting(self, key: str, default: Any) -> Any:
        """Get organization setting value.

        Args:
            key: Setting key (dot notation, e.g., "matching.auto_apply_threshold")
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        # TODO: Implement org settings lookup when org settings system exists
        # For now, return defaults
        defaults = {
            "price_tolerance_percent": 5.0,
            "matching.auto_apply_threshold": 0.92,
            "matching.auto_apply_gap": 0.10,
            "matching.reject_threshold": 5
        }
        return defaults.get(key, default)
