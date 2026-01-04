"""Matching ports and interfaces for hexagonal architecture.

SSOT Reference: §3.5 (Erweiterungspunkte), §7.7 (Hybrid Search)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from uuid import UUID
from decimal import Decimal


@dataclass
class MatchCandidate:
    """Single product match candidate with scores and features.

    Attributes:
        internal_sku: Product internal SKU
        product_id: Product UUID
        product_name: Product name for display
        confidence: Final match confidence (0.0-1.0)
        method: Matching method (exact_mapping, hybrid, trigram, embedding)
        features: Debug features for match (S_tri, S_emb, P_uom, P_price, etc.)
    """
    internal_sku: str
    product_id: UUID
    product_name: str
    confidence: float
    method: str
    features: dict


@dataclass
class MatchResult:
    """Result of matching operation for a draft line.

    Attributes:
        internal_sku: Top match internal SKU (None if no match)
        product_id: Top match product UUID (None if no match)
        confidence: Top match confidence (0.0 if no match)
        method: Matching method used (None if no match)
        status: Match status (MATCHED, SUGGESTED, UNMATCHED)
        candidates: Top 5 match candidates for UI display
    """
    internal_sku: Optional[str]
    product_id: Optional[UUID]
    confidence: float
    method: Optional[str]
    status: str  # MATCHED, SUGGESTED, UNMATCHED
    candidates: List[MatchCandidate]


@dataclass
class MatchInput:
    """Input data for matching operation.

    Attributes:
        org_id: Organization UUID
        customer_id: Customer UUID
        customer_sku_norm: Normalized customer SKU
        customer_sku_raw: Raw customer SKU from document
        product_description: Product description text
        uom: Unit of measure from line
        unit_price: Unit price from line (optional)
        qty: Quantity from line
        currency: Currency code from line
        order_date: Order date for price validity
    """
    org_id: UUID
    customer_id: UUID
    customer_sku_norm: str
    customer_sku_raw: str
    product_description: Optional[str]
    uom: Optional[str]
    unit_price: Optional[Decimal]
    qty: Optional[Decimal]
    currency: Optional[str]
    order_date: Optional[str]


class MatcherPort(ABC):
    """Port interface for SKU matching strategies.

    Implementations:
    - TrigramMatcher: pg_trgm similarity on SKU and description
    - EmbeddingMatcher: pgvector cosine similarity on embeddings
    - HybridMatcher: Combined trigram + embedding with penalties

    SSOT Reference: §3.5 (MatcherPort), §7.7.5 (Hybrid Search)
    """

    @abstractmethod
    def match(self, input_data: MatchInput) -> MatchResult:
        """Match customer SKU to internal products.

        Args:
            input_data: Input data for matching

        Returns:
            MatchResult with top match and candidates

        Raises:
            MatcherError: If matching fails due to system error
        """
        pass

    @abstractmethod
    def match_batch(self, inputs: List[MatchInput]) -> List[MatchResult]:
        """Match multiple lines in batch (optimized).

        Args:
            inputs: List of input data for matching

        Returns:
            List of match results (same order as inputs)

        Raises:
            MatcherError: If batch matching fails
        """
        pass


class MatcherError(Exception):
    """Exception raised for matching errors."""
    pass
