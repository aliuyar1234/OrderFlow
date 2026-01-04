"""Hybrid matcher combining confirmed mappings, trigram, and vector search.

SSOT Reference: §7.7.5 (Hybrid Search), §7.7.6 (Scoring Formula)
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from .ports import MatcherPort, MatchInput, MatchResult, MatchCandidate, MatcherError
from .scorer import MatchScorer
from models.sku_mapping import SkuMapping
from models.product import Product


class HybridMatcher(MatcherPort):
    """Hybrid matcher combining confirmed mappings, trigram, and vector search.

    Pipeline:
    1. Check confirmed mappings (sku_mapping WHERE status=CONFIRMED)
    2. If no confirmed mapping: run trigram search (Top 30)
    3. If embeddings enabled: run vector search (Top 30)
    4. Merge candidates (union), calculate match_confidence per §7.7.6
    5. Rank by confidence DESC, store Top 5
    6. Auto-apply if top1.confidence >= threshold AND gap >= auto_apply_gap

    SSOT Reference: §FR-002, §FR-003, §FR-004
    """

    def __init__(self, db: Session):
        """Initialize hybrid matcher.

        Args:
            db: Database session
        """
        self.db = db

    def match(self, input_data: MatchInput) -> MatchResult:
        """Match customer SKU to internal products using hybrid approach.

        Args:
            input_data: Input data for matching

        Returns:
            MatchResult with top match and candidates

        Raises:
            MatcherError: If matching fails due to system error
        """
        try:
            # Step 1: Check confirmed mapping
            confirmed_mapping = self._check_confirmed_mapping(input_data)
            if confirmed_mapping:
                return confirmed_mapping

            # Step 2: Trigram search
            trigram_candidates = self._trigram_search(input_data)

            # Step 3: Vector search (if embeddings available)
            # TODO: Implement vector search when embedding system is ready
            vector_candidates = []

            # Step 4: Merge and score candidates
            all_candidates = self._merge_candidates(trigram_candidates, vector_candidates)
            scored_candidates = self._score_candidates(input_data, all_candidates)

            # Step 5: Rank by confidence DESC
            scored_candidates.sort(key=lambda x: x.confidence, reverse=True)

            # Step 6: Auto-apply?
            return self._create_match_result(input_data, scored_candidates)

        except Exception as e:
            raise MatcherError(f"Matching failed: {str(e)}") from e

    def match_batch(self, inputs: List[MatchInput]) -> List[MatchResult]:
        """Match multiple lines in batch.

        Args:
            inputs: List of input data for matching

        Returns:
            List of match results (same order as inputs)

        Raises:
            MatcherError: If batch matching fails
        """
        results = []
        for input_data in inputs:
            results.append(self.match(input_data))
        return results

    def _check_confirmed_mapping(self, input_data: MatchInput) -> Optional[MatchResult]:
        """Check for confirmed SKU mapping.

        SSOT Reference: §FR-006, §FR-009

        Args:
            input_data: Input data with customer_sku_norm

        Returns:
            MatchResult if confirmed mapping exists, else None
        """
        mapping = self.db.query(SkuMapping).filter(
            and_(
                SkuMapping.org_id == input_data.org_id,
                SkuMapping.customer_id == input_data.customer_id,
                SkuMapping.customer_sku_norm == input_data.customer_sku_norm,
                SkuMapping.status == "CONFIRMED"
            )
        ).first()

        if not mapping:
            return None

        # Get product for mapping
        product = self.db.query(Product).filter(
            and_(
                Product.org_id == input_data.org_id,
                Product.internal_sku == mapping.internal_sku,
                Product.active == True
            )
        ).first()

        if not product:
            # Mapping exists but product not found/inactive
            return None

        # Return confirmed mapping with high confidence
        candidate = MatchCandidate(
            internal_sku=product.internal_sku,
            product_id=product.id,
            product_name=product.name,
            confidence=0.99,
            method="exact_mapping",
            features={
                "S_map": 1.0,
                "S_tri": 0.0,
                "S_emb": 0.0,
                "P_uom": 1.0,
                "P_price": 1.0
            }
        )

        return MatchResult(
            internal_sku=product.internal_sku,
            product_id=product.id,
            confidence=0.99,
            method="exact_mapping",
            status="MATCHED",
            candidates=[candidate]
        )

    def _trigram_search(self, input_data: MatchInput) -> List[Product]:
        """Search products using PostgreSQL pg_trgm similarity.

        SSOT Reference: §FR-010, §FR-011

        Args:
            input_data: Input data with customer_sku_norm and product_description

        Returns:
            List of product candidates
        """
        # SKU search
        sku_query = text("""
            SELECT DISTINCT id
            FROM product
            WHERE org_id = :org_id
              AND active = true
              AND similarity(internal_sku, :sku) > 0.3
            ORDER BY similarity(internal_sku, :sku) DESC
            LIMIT 30
        """)

        sku_results = self.db.execute(
            sku_query,
            {
                "org_id": str(input_data.org_id),
                "sku": input_data.customer_sku_norm
            }
        ).fetchall()

        sku_product_ids = [row[0] for row in sku_results]

        # Description search (if description provided)
        desc_product_ids = []
        if input_data.product_description:
            desc_query = text("""
                SELECT DISTINCT id
                FROM product
                WHERE org_id = :org_id
                  AND active = true
                  AND similarity(name || ' ' || COALESCE(description, ''), :desc) > 0.3
                ORDER BY similarity(name || ' ' || COALESCE(description, ''), :desc) DESC
                LIMIT 30
            """)

            desc_results = self.db.execute(
                desc_query,
                {
                    "org_id": str(input_data.org_id),
                    "desc": input_data.product_description
                }
            ).fetchall()

            desc_product_ids = [row[0] for row in desc_results]

        # Merge product IDs
        all_product_ids = list(set(sku_product_ids + desc_product_ids))

        # Fetch products
        if not all_product_ids:
            return []

        products = self.db.query(Product).filter(
            Product.id.in_(all_product_ids)
        ).all()

        return products

    def _merge_candidates(
        self,
        trigram_candidates: List[Product],
        vector_candidates: List[Product]
    ) -> List[Product]:
        """Merge trigram and vector candidates (union by product_id).

        Args:
            trigram_candidates: Products from trigram search
            vector_candidates: Products from vector search

        Returns:
            Merged list of unique products
        """
        # Merge by product ID
        product_map = {}
        for product in trigram_candidates:
            product_map[product.id] = product
        for product in vector_candidates:
            product_map[product.id] = product

        return list(product_map.values())

    def _score_candidates(
        self,
        input_data: MatchInput,
        candidates: List[Product]
    ) -> List[MatchCandidate]:
        """Score all candidates using hybrid formula.

        Args:
            input_data: Input data for matching
            candidates: List of product candidates

        Returns:
            List of scored match candidates
        """
        scorer = MatchScorer(self.db, input_data.org_id)
        scored = []

        for product in candidates:
            # Calculate trigram scores
            s_tri_sku = self._calculate_trigram_similarity(
                input_data.customer_sku_norm, product.internal_sku
            )
            s_tri_desc = 0.0
            if input_data.product_description:
                product_text = f"{product.name} {product.description or ''}".strip()
                s_tri_desc = self._calculate_trigram_similarity(
                    input_data.product_description, product_text
                )

            # Embedding score (TODO: implement when embeddings ready)
            s_emb = 0.0

            # Mapping score (always 0 here, confirmed mappings handled earlier)
            s_map = 0.0

            # Calculate confidence with penalties
            result = scorer.calculate_confidence(
                product=product,
                s_tri_sku=s_tri_sku,
                s_tri_desc=s_tri_desc,
                s_emb=s_emb,
                s_map=s_map,
                line_uom=input_data.uom,
                line_unit_price=input_data.unit_price,
                line_qty=input_data.qty,
                line_currency=input_data.currency,
                customer_id=input_data.customer_id,
                order_date=input_data.order_date
            )

            scored.append(MatchCandidate(
                internal_sku=product.internal_sku,
                product_id=product.id,
                product_name=product.name,
                confidence=result["confidence"],
                method="hybrid",
                features=result["features"]
            ))

        return scored

    def _calculate_trigram_similarity(self, text1: str, text2: str) -> float:
        """Calculate trigram similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0

        query = text("SELECT similarity(:text1, :text2) AS sim")
        result = self.db.execute(query, {"text1": text1, "text2": text2}).fetchone()
        return float(result[0]) if result else 0.0

    def _create_match_result(
        self,
        input_data: MatchInput,
        scored_candidates: List[MatchCandidate]
    ) -> MatchResult:
        """Create match result with auto-apply logic.

        SSOT Reference: §FR-004

        Args:
            input_data: Input data for matching
            scored_candidates: Scored and ranked candidates

        Returns:
            MatchResult with status and top candidates
        """
        if not scored_candidates:
            return MatchResult(
                internal_sku=None,
                product_id=None,
                confidence=0.0,
                method=None,
                status="UNMATCHED",
                candidates=[]
            )

        top1 = scored_candidates[0]
        top2 = scored_candidates[1] if len(scored_candidates) > 1 else None

        # Get thresholds from org settings
        scorer = MatchScorer(self.db, input_data.org_id)
        auto_apply_threshold = scorer._get_org_setting("matching.auto_apply_threshold", 0.92)
        auto_apply_gap = scorer._get_org_setting("matching.auto_apply_gap", 0.10)

        # Check auto-apply conditions
        if top1.confidence >= auto_apply_threshold:
            gap = top1.confidence - (top2.confidence if top2 else 0.0)
            if gap >= auto_apply_gap:
                return MatchResult(
                    internal_sku=top1.internal_sku,
                    product_id=top1.product_id,
                    confidence=top1.confidence,
                    method=top1.method,
                    status="SUGGESTED",
                    candidates=scored_candidates[:5]
                )

        # No auto-apply
        return MatchResult(
            internal_sku=None,
            product_id=None,
            confidence=top1.confidence,
            method=None,
            status="UNMATCHED",
            candidates=scored_candidates[:5]
        )
