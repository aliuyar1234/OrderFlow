# Data Model: Matching Engine

**Feature**: 017-matching-engine
**Date**: 2025-12-27

## SQLAlchemy Model

```python
from sqlalchemy import Column, String, Numeric, Integer, TIMESTAMP, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid

class SkuMapping(Base):
    __tablename__ = 'sku_mapping'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey('customer.id'), nullable=False)
    customer_sku_norm = Column(String(255), nullable=False)  # Normalized customer SKU
    internal_sku = Column(String(255), nullable=False)  # Internal product SKU
    status = Column(String(20), nullable=False)  # CONFIRMED | SUGGESTED | REJECTED | DEPRECATED
    confidence = Column(Numeric(5, 4), nullable=False, default=1.0)  # 0..1
    support_count = Column(Integer, nullable=False, default=1)  # Times confirmed
    reject_count = Column(Integer, nullable=False, default=0)  # Times rejected
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('org_id', 'customer_id', 'customer_sku_norm', name='uq_sku_mapping_active',
                         postgresql_where="status IN ('CONFIRMED', 'SUGGESTED')"),
        Index('idx_sku_mapping_lookup', 'org_id', 'customer_id', 'customer_sku_norm', 'status'),
    )
```

## Match Confidence Calculator

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MatchFeatures:
    S_tri: float  # Trigram similarity (0..1)
    S_tri_sku: float  # SKU trigram
    S_tri_desc: float  # Description trigram
    S_emb: Optional[float]  # Embedding similarity (0..1)
    P_uom: float  # UoM penalty (0.2 | 0.9 | 1.0)
    P_price: float  # Price penalty (0.65 | 0.85 | 1.0)

def calculate_match_confidence(features: MatchFeatures) -> float:
    """
    Calculate match confidence per §7.7.6 formula:
    S_hybrid_raw = max(0.99*S_map, 0.62*S_tri + 0.38*S_emb)
    confidence = clamp(S_hybrid_raw * P_uom * P_price, 0..1)
    """
    # Trigram score
    S_tri = max(features.S_tri_sku, 0.7 * features.S_tri_desc)

    # Hybrid raw score
    if features.S_emb is not None:
        S_hybrid_raw = max(0, 0.62 * S_tri + 0.38 * features.S_emb)
    else:
        S_hybrid_raw = S_tri  # Fallback if embeddings unavailable

    # Apply penalties
    confidence = S_hybrid_raw * features.P_uom * features.P_price

    # Clamp to [0..1]
    return max(0.0, min(1.0, confidence))
```

## UoM Penalty Calculator

```python
def calculate_uom_penalty(line_uom: str, product: Product) -> float:
    """
    Calculate UoM penalty:
    - Compatible (match or convertible): 1.0
    - Missing/unknown: 0.9
    - Incompatible: 0.2
    """
    if not line_uom:
        return 0.9  # Missing

    if line_uom == product.base_uom:
        return 1.0  # Exact match

    if line_uom in (product.uom_conversions_json or {}):
        return 1.0  # Convertible

    return 0.2  # Incompatible
```

## Price Penalty Calculator

```python
def calculate_price_penalty(
    line_price: float,
    expected_price: float,
    tolerance_percent: float = 5.0
) -> float:
    """
    Calculate price penalty:
    - Within tolerance: 1.0
    - Warning (tolerance to 2x tolerance): 0.85
    - Strong mismatch (>2x tolerance): 0.65
    """
    if not line_price or not expected_price:
        return 1.0  # No price to check

    delta_percent = abs(line_price - expected_price) / expected_price * 100

    if delta_percent <= tolerance_percent:
        return 1.0
    elif delta_percent <= 2 * tolerance_percent:
        return 0.85
    else:
        return 0.65
```

## Match Result Schema

```python
@dataclass
class MatchCandidate:
    product_id: UUID
    sku: str
    name: str
    confidence: float
    method: str  # 'exact_mapping' | 'hybrid' | 'trigram' | 'embedding'
    features: MatchFeatures

@dataclass
class MatchResult:
    internal_sku: Optional[str]
    confidence: float
    method: Optional[str]
    status: str  # 'MATCHED' | 'SUGGESTED' | 'UNMATCHED' | 'OVERRIDDEN'
    candidates: List[MatchCandidate]  # Top 5
```

## Relationships

- SkuMapping (many) → (1) Customer
- SkuMapping references Product via internal_sku (soft FK, string-based)
- DraftOrderLine.match_debug_json stores serialized MatchCandidate list
