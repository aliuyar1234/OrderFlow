# Feature Specification: Matching Engine (Hybrid SKU Matching)

**Feature Branch**: `017-matching-engine`
**Created**: 2025-12-27
**Status**: Draft
**Module**: matching, catalog
**SSOT Refs**: §5.4.12 (sku_mapping), §7.7.5-7.7.7 (Hybrid Search), §7.9 (Match Confidence), §7.10.1 (Confirmed Mappings), T-402, T-403, T-404, T-405, T-408

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hybrid Matching (Trigram + Embedding + Mapping) (Priority: P1)

When a draft line is created, the system automatically runs hybrid matching: checks confirmed mappings first, then combines trigram similarity (fast, exact-ish) with vector similarity (slow, semantic), ranks candidates, and auto-applies top match if confidence ≥0.92.

**Why this priority**: Core intelligence of the system. Accurate matching reduces manual work and errors.

**Independent Test**: Draft line with customer_sku="XYZ-999", description="Stromkabel" → system finds confirmed mapping for XYZ-999 → match_confidence=0.99, internal_sku set → else searches trigram+vector → ranks candidates → auto-applies if confidence high.

**Acceptance Scenarios**:

1. **Given** line with customer_sku_norm="ABC123", **When** matching runs, **Then** first checks sku_mapping WHERE customer_sku_norm="ABC123" AND status=CONFIRMED → if found, sets internal_sku, match_confidence=0.99, match_method="exact_mapping", match_status=MATCHED
2. **Given** no confirmed mapping, **When** matching runs, **Then** runs trigram search on (customer_sku_norm vs internal_sku) AND (product_description vs product.name+description) → Top 30 candidates
3. **Given** trigram candidates + vector candidates (Top 30 each), **When** merging, **Then** combines via union, calculates match_confidence per §7.7.6 hybrid formula, ranks by confidence DESC
4. **Given** Top candidate with match_confidence=0.95 and gap to #2 ≥0.10, **When** auto-apply threshold ≥0.92, **Then** sets internal_sku, match_status=SUGGESTED, match_method="hybrid"
5. **Given** Top candidate with match_confidence=0.85 (below threshold), **When** matching completes, **Then** internal_sku remains null, candidates stored in match_debug_json, match_status=UNMATCHED

---

### User Story 2 - Confirmed Mapping Learning Loop (Priority: P1)

When Ops selects a match and clicks "Confirm Mapping", the system creates/updates a CONFIRMED sku_mapping entry, increments support_count, and logs feedback event. Future lines with same customer_sku automatically use the mapping.

**Why this priority**: Learning loop is key differentiator. System gets smarter over time without manual training.

**Independent Test**: Confirm mapping customer_sku="XYZ-999" → internal_sku="PROD-123" → sku_mapping created → next line with XYZ-999 → auto-matched to PROD-123 with confidence=0.99.

**Acceptance Scenarios**:

1. **Given** Ops selects internal_sku for line manually and clicks "Confirm Mapping", **When** confirming, **Then** sku_mapping created/updated with status=CONFIRMED, support_count+=1, last_used_at=now, confidence=1.0
2. **Given** sku_mapping exists with support_count=5, **When** confirming again, **Then** support_count=6, last_used_at updated
3. **Given** sku_mapping confirmed, **When** feedback_event created, **Then** event_type=MAPPING_CONFIRMED, before_json=candidates, after_json=selected_sku
4. **Given** next draft line with same customer_sku_norm, **When** matching runs, **Then** confirmed mapping applied immediately, no trigram/vector search needed

---

### User Story 3 - Match Confidence Calculation with Penalties (Priority: P1)

The system calculates match_confidence using hybrid formula (0.62*trigram + 0.38*embedding) * P_uom * P_price, where penalties reduce confidence for UoM incompatibility or price mismatches.

**Why this priority**: Prevents false positives. UoM/price penalties ensure suggestions are actually viable.

**Independent Test**: Candidate with high semantic similarity but incompatible UoM → P_uom=0.2 → match_confidence drops below threshold → not auto-applied.

**Acceptance Scenarios**:

1. **Given** candidate with S_tri=0.85, S_emb=0.78, **When** calculating hybrid score, **Then** S_hybrid_raw = max(0.99*0, 0.62*0.85 + 0.38*0.78) = 0.8234
2. **Given** line.uom=KAR, product has uom_conversions for KAR, **When** calculating P_uom, **Then** P_uom=1.0 (compatible)
3. **Given** line.uom=KG, product.base_uom=ST, no conversion, **When** calculating P_uom, **Then** P_uom=0.2 (incompatible)
4. **Given** line.unit_price=10.50, customer_price=10.00, tolerance=5%, **When** calculating P_price, **Then** within tolerance → P_price=1.0
5. **Given** line.unit_price=12.00, customer_price=10.00, tolerance=5%, **When** calculating P_price, **Then** mismatch >5% → P_price=0.85 (warning level)
6. **Given** S_hybrid_raw=0.85, P_uom=0.2, P_price=1.0, **When** calculating final confidence, **Then** match_confidence = 0.85 * 0.2 * 1.0 = 0.17 (low, not auto-applied)

---

### User Story 4 - Match Candidates Ranking and Storage (Priority: P2)

For each line, the system stores Top 5 match candidates in match_debug_json with SKU, confidence, method, and match features (trigram scores, embedding similarity, UoM compat, price delta).

**Why this priority**: Transparency for debugging. Ops can see why system suggested a match. Data for future ML improvements.

**Independent Test**: Matching produces 30 candidates → Top 5 stored in match_debug_json → UI displays candidates with confidence breakdown.

**Acceptance Scenarios**:

1. **Given** matching produces candidates, **When** ranking, **Then** sorts by match_confidence DESC, takes Top 5
2. **Given** Top 5 candidates, **When** storing in match_debug_json, **Then** format: `[{"sku":"X","confidence":0.92,"method":"hybrid","features":{"S_tri":0.88,"S_emb":0.85,"P_uom":1.0,"P_price":1.0}}]`
3. **Given** line with match_debug_json populated, **When** Ops views in UI, **Then** dropdown shows candidates with confidence badges and method labels
4. **Given** match_debug_json contains features, **When** debugging match quality, **Then** Admin can query aggregated stats (avg S_tri, S_emb per product)

---

### User Story 5 - Trigram Search for Exact-ish Matching (Priority: P1)

The system uses PostgreSQL pg_trgm extension for trigram similarity on customer_sku vs internal_sku and product_description vs product.name. Fast fallback when embeddings unavailable.

**Why this priority**: Trigram is fast, deterministic, and works well for SKU matching (alphanumeric codes). Critical for non-semantic matches.

**Independent Test**: Line with customer_sku="AB-123-XY" → trigram search finds internal_sku="AB123XY" with similarity=0.85 → ranked high even if semantic description differs.

**Acceptance Scenarios**:

1. **Given** customer_sku_norm="AB123XY", **When** running trigram search, **Then** query: `SELECT internal_sku, similarity(internal_sku, 'AB123XY') AS sim FROM product WHERE org_id=:org AND similarity(internal_sku, 'AB123XY') > 0.3 ORDER BY sim DESC LIMIT 30`
2. **Given** product_description="Cable 3x1.5mm", **When** running trigram on product.name+description, **Then** query: `SELECT internal_sku, similarity(name || ' ' || description, 'Cable 3x1.5mm') AS sim FROM product ... LIMIT 30`
3. **Given** trigram results, **When** calculating S_tri, **Then** S_tri = max(S_tri_sku, 0.7*S_tri_desc) per §7.7.6
4. **Given** pg_trgm index missing, **When** query runs, **Then** performance degrades, system logs warning, Integrator alerted to create index

---

### User Story 6 - Mapping Rejection and Deprecation (Priority: P3)

Ops can reject a suggested mapping (wrong match). System increments reject_count. If reject_count exceeds threshold, mapping is auto-deprecated. Admin can manually deprecate mappings.

**Why this priority**: Prevents bad mappings from persisting. Negative feedback improves quality.

**Independent Test**: Ops rejects mapping 3 times → reject_count=3 → if threshold=3, mapping deprecated → no longer suggested.

**Acceptance Scenarios**:

1. **Given** Ops selects different SKU than suggested, **When** saving, **Then** if suggested mapping exists, increment reject_count, create feedback_event event_type=MAPPING_REJECTED
2. **Given** sku_mapping with reject_count=3 and org threshold=3, **When** checking, **Then** status auto-updated to DEPRECATED
3. **Given** mapping deprecated, **When** matching runs, **Then** deprecated mappings excluded from results
4. **Given** Admin views mappings list, **When** filtering by status, **Then** can view/export deprecated mappings for audit
5. **Given** Admin manually deprecates mapping, **When** saving, **Then** status=DEPRECATED, last_used_at unchanged, support_count unchanged

---

### Edge Cases

- What happens when customer_sku_norm collision (two mappings for same norm but different raw)?
- How does system handle mapping for wrong customer (customer_id mismatch)?
- What happens when product is deactivated but mapping exists (orphaned mapping)?
- How does system handle extremely long product descriptions (>1000 chars, trigram performance)?
- What happens when both trigram and embedding return 0 candidates (no matches)?
- How does system handle concurrent mapping confirmations for same customer_sku (race condition)?
- If no products match query (0 candidates returned): Set line status to UNMATCHED, match_candidates_json=[], match_confidence=0.0. Manual matching required. Do not treat as error - common during initial setup before catalog import.

## Requirements *(mandatory)*

### Functional Requirements

**Hybrid Matching:**
- **FR-001**: System MUST run matching for each draft_order_line after extraction
- **FR-002**: Matching pipeline MUST execute in order:
  1. Check confirmed mappings (sku_mapping WHERE status=CONFIRMED AND customer_sku_norm=X AND customer_id=Y)
  2. If no confirmed mapping: run trigram search (Top 30)
  3. If embeddings enabled: run vector search (Top 30)
  4. Merge candidates (union), calculate match_confidence per §7.7.6
  5. Rank by confidence DESC, store Top 5 in match_debug_json
  6. Auto-apply if top1.confidence ≥ auto_apply_threshold AND gap ≥ auto_apply_gap
- **FR-003**: System MUST calculate match_confidence per §7.7.6 formula:
  - S_tri = max(S_tri_sku, 0.7*S_tri_desc)
  - S_emb = clamp((cosine_sim + 1)/2, 0..1)
  - S_hybrid_raw = max(0.99*S_map, 0.62*S_tri + 0.38*S_emb)
  - P_uom = 1.0 (compatible) | 0.9 (missing) | 0.2 (incompatible)
  - P_price = 1.0 (within tolerance) | 0.85 (warning) | 0.65 (strong mismatch)
  - match_confidence = clamp(S_hybrid_raw * P_uom * P_price, 0..1)
- **FR-004**: System MUST auto-apply match if:
  - match_confidence ≥ org.settings.matching.auto_apply_threshold (default 0.92)
  - top1 - top2 ≥ org.settings.matching.auto_apply_gap (default 0.10)
  - Action: set internal_sku, match_status=SUGGESTED, match_method="hybrid"
- **FR-005**: System MUST create LOW_CONFIDENCE_MATCH issue (WARNING) if match_confidence <0.75

**Confirmed Mappings:**
- **FR-006**: System MUST define sku_mapping entity per §5.4.12 with fields:
  - customer_id, customer_sku_norm, internal_sku, status (CONFIRMED|SUGGESTED|REJECTED|DEPRECATED)
  - confidence (1.0 for CONFIRMED), support_count, reject_count, last_used_at
- **FR-007**: System MUST enforce UNIQUE constraint on (org_id, customer_id, customer_sku_norm) WHERE status IN ('CONFIRMED', 'SUGGESTED')
- **FR-008**: When Ops confirms mapping, system MUST:
  - Upsert sku_mapping: if exists increment support_count, else create with support_count=1
  - Set status=CONFIRMED, confidence=1.0, last_used_at=now
  - Create feedback_event: event_type=MAPPING_CONFIRMED, before_json=candidates, after_json=selected_sku
- **FR-009**: System MUST prioritize confirmed mappings:
  - If confirmed mapping exists, apply immediately with confidence=0.99, skip trigram/vector search
  - Store match_method="exact_mapping", match_status=MATCHED

**Trigram Search:**
- **FR-010**: System MUST use pg_trgm for similarity search:
  - Index: `CREATE INDEX idx_product_trgm ON product USING gin (internal_sku gin_trgm_ops, (name || ' ' || description) gin_trgm_ops)`
  - Query SKU: `SELECT internal_sku, similarity(internal_sku, :customer_sku_norm) AS sim FROM product WHERE org_id=:org AND similarity(internal_sku, :customer_sku_norm) > 0.3 ORDER BY sim DESC LIMIT 30`
  - Query Desc: `SELECT internal_sku, similarity(name || ' ' || description, :product_description) AS sim FROM product WHERE org_id=:org AND similarity(...) > 0.3 ORDER BY sim DESC LIMIT 30`
- **FR-011**: System MUST combine trigram scores: S_tri = max(S_tri_sku, 0.7*S_tri_desc)

**Vector Search:**
- **FR-012**: System MUST generate query embedding from line per §7.7.3
- **FR-013**: System MUST search product_embedding: `ORDER BY embedding <=> :query_vector LIMIT 30`
- **FR-014**: System MUST calculate S_emb = clamp((cosine_sim + 1)/2, 0..1)
- **FR-015**: Matching MUST emit structured debug logs for each candidate scored. Log format: {candidate_sku, S_tri, S_emb, S_map, P_uom, P_price, final_confidence, method}. Logs enable Prometheus/Datadog correlation via orderflow_matching_debug metric. Include trace_id and draft_order_line_id for request correlation.
- **FR-016**: Matching MUST work with trigram search alone if embeddings unavailable or disabled. Embeddings are optimization, not requirement. If EmbeddingProviderPort returns error or org.settings.ai.embedding.enabled=false, use S_emb=0.0 and rely solely on S_tri. Log warning when falling back.

**Penalties:**
- **FR-017**: System MUST calculate P_uom:
  - Compatible (line.uom == product.base_uom OR line.uom in product.uom_conversions): 1.0
  - Missing/unknown: 0.9
  - Incompatible: 0.2
- **FR-018**: System MUST calculate P_price (if customer_prices exist AND line.unit_price present):
  - Find best customer_price tier (max min_qty WHERE min_qty <= line.qty)
  - If abs(line.unit_price - expected) / expected <= tolerance: 1.0
  - If > tolerance AND <= 2*tolerance: 0.85
  - If > 2*tolerance: 0.65
  - If no customer_price: 1.0 (no penalty)

**Match Storage:**
- **FR-019**: System MUST store Top 1 match in draft_order_line:
  - internal_sku, match_confidence, match_method, match_status
- **FR-020**: System MUST store Top 5 candidates in match_debug_json:
  - Format: `[{"sku":"X","name":"Y","confidence":0.92,"method":"hybrid","features":{"S_tri":0.88,"S_emb":0.85,"P_uom":1.0,"P_price":1.0}}]`

**Mapping Rejection:**
- **FR-021**: When Ops selects different SKU than suggested, system MUST:
  - If sku_mapping exists for suggested SKU: increment reject_count
  - Create feedback_event: event_type=MAPPING_REJECTED
- **FR-022**: System MUST auto-deprecate mappings if reject_count ≥ org.settings.matching.reject_threshold (default 5)
- **FR-023**: System MUST exclude deprecated mappings from search results

### Key Entities

- **sku_mapping** (§5.4.12): Learning store for confirmed/rejected mappings
- **draft_order_line.match_debug_json**: Match candidates and features
- **Hybrid Scorer**: Service component calculating match_confidence
- **MappingFeedbackService**: Handles confirm/reject actions

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Hybrid matching achieves ≥85% accuracy on test set (Top 1 is correct match)
- **SC-002**: Confirmed mappings reduce matching latency by ≥80% (skip trigram/vector)
- **SC-003**: Auto-apply threshold (0.92) achieves <2% error rate (wrong auto-applied match)
- **SC-004**: Matching completes in <500ms per line (trigram + vector + scoring)
- **SC-005**: UoM/price penalties prevent ≥90% of incompatible matches from auto-applying
- **SC-006**: Learning loop: after 50 confirmed mappings, ≥70% of repeat SKUs match automatically
- **SC-007**: Trigram search performs in <50ms (with pg_trgm index)
- **SC-008**: Vector search performs in <50ms (with HNSW index)

## Dependencies

- **Depends on**:
  - 015-catalog-products (product entity, customer_prices)
  - 016-embedding-layer (embeddings for vector search)
  - 013-draft-orders-core (draft_order_line entity)
  - PostgreSQL with pg_trgm and pgvector extensions

- **Blocks**:
  - Draft approval workflow (matching must complete before ready-check)
  - Ops productivity (accurate matching reduces manual work)

## Technical Notes

### Implementation Guidance

**Confidence Formula Clarification:** S_map = 1.0 if confirmed mapping exists for (customer_id, customer_sku_norm) → internal_sku, else 0.0. When S_map=1.0: final_confidence = 0.99 (skip hybrid calculation). When S_map=0.0: S_hybrid = 0.62*S_tri + 0.38*S_emb, then apply penalties. This prioritizes confirmed mappings over algorithmic matches.

**Hybrid Matching Service:**
```python
class HybridMatcher:
    def match_line(self, line: DraftOrderLine, customer_id: UUID) -> MatchResult:
        # Step 1: Check confirmed mapping
        mapping = db.query(SkuMapping).filter(
            SkuMapping.org_id == line.org_id,
            SkuMapping.customer_id == customer_id,
            SkuMapping.customer_sku_norm == line.customer_sku_norm,
            SkuMapping.status == "CONFIRMED"
        ).first()

        if mapping:
            return MatchResult(
                internal_sku=mapping.internal_sku,
                confidence=0.99,
                method="exact_mapping",
                status="MATCHED",
                candidates=[]
            )

        # Step 2: Trigram search
        trigram_candidates = self.trigram_search(line)

        # Step 3: Vector search (if enabled)
        vector_candidates = []
        if org_has_embeddings(line.org_id):
            vector_candidates = self.vector_search(line)

        # Step 4: Merge and score
        all_candidates = self.merge_candidates(trigram_candidates, vector_candidates)
        scored_candidates = [self.score_candidate(line, c) for c in all_candidates]
        scored_candidates.sort(key=lambda x: x.confidence, reverse=True)

        # Step 5: Auto-apply?
        top1 = scored_candidates[0] if scored_candidates else None
        top2 = scored_candidates[1] if len(scored_candidates) > 1 else None

        auto_apply_threshold = get_org_setting(line.org_id, "matching.auto_apply_threshold", 0.92)
        auto_apply_gap = get_org_setting(line.org_id, "matching.auto_apply_gap", 0.10)

        if top1 and top1.confidence >= auto_apply_threshold:
            gap = top1.confidence - (top2.confidence if top2 else 0)
            if gap >= auto_apply_gap:
                return MatchResult(
                    internal_sku=top1.sku,
                    confidence=top1.confidence,
                    method="hybrid",
                    status="SUGGESTED",
                    candidates=scored_candidates[:5]
                )

        # No auto-apply
        return MatchResult(
            internal_sku=None,
            confidence=top1.confidence if top1 else 0.0,
            method=None,
            status="UNMATCHED",
            candidates=scored_candidates[:5]
        )

    def score_candidate(self, line: DraftOrderLine, candidate: Product) -> ScoredCandidate:
        # Trigram scores
        S_tri_sku = similarity(line.customer_sku_norm, candidate.internal_sku)
        S_tri_desc = similarity(line.product_description, candidate.name + ' ' + candidate.description)
        S_tri = max(S_tri_sku, 0.7 * S_tri_desc)

        # Embedding score
        S_emb = 0.0
        if candidate.embedding:
            cosine_sim = candidate.embedding.cosine_similarity(line.query_embedding)
            S_emb = max(0.0, min(1.0, (cosine_sim + 1) / 2))

        # Hybrid raw
        S_hybrid_raw = max(0, 0.62 * S_tri + 0.38 * S_emb)

        # Penalties
        P_uom = self.calculate_uom_penalty(line, candidate)
        P_price = self.calculate_price_penalty(line, candidate)

        confidence = max(0.0, min(1.0, S_hybrid_raw * P_uom * P_price))

        return ScoredCandidate(
            sku=candidate.internal_sku,
            name=candidate.name,
            confidence=confidence,
            method="hybrid",
            features={
                "S_tri": S_tri,
                "S_tri_sku": S_tri_sku,
                "S_tri_desc": S_tri_desc,
                "S_emb": S_emb,
                "P_uom": P_uom,
                "P_price": P_price,
            }
        )

    def calculate_uom_penalty(self, line: DraftOrderLine, product: Product) -> float:
        if not line.uom:
            return 0.9  # missing
        if line.uom == product.base_uom:
            return 1.0  # compatible
        if line.uom in product.uom_conversions_json:
            return 1.0  # compatible via conversion
        return 0.2  # incompatible

    def calculate_price_penalty(self, line: DraftOrderLine, product: Product) -> float:
        if not line.unit_price:
            return 1.0  # no price to check

        customer_price = self.find_customer_price(line.customer_id, product.internal_sku, line.qty, line.currency, line.uom, line.order_date)
        if not customer_price:
            return 1.0  # no reference price

        tolerance = get_org_setting(line.org_id, "price_tolerance_percent", 5.0) / 100
        delta = abs(line.unit_price - customer_price.unit_price) / customer_price.unit_price

        if delta <= tolerance:
            return 1.0
        elif delta <= 2 * tolerance:
            return 0.85
        else:
            return 0.65
```

**Trigram Search:**
```python
def trigram_search(self, line: DraftOrderLine) -> list[Product]:
    # SKU search
    sku_results = db.execute(
        """
        SELECT id, internal_sku, similarity(internal_sku, :sku) AS sim
        FROM product
        WHERE org_id = :org_id AND active = true
          AND similarity(internal_sku, :sku) > 0.3
        ORDER BY sim DESC
        LIMIT 30
        """,
        {"org_id": line.org_id, "sku": line.customer_sku_norm}
    ).fetchall()

    # Description search
    desc_results = db.execute(
        """
        SELECT id, internal_sku, similarity(name || ' ' || COALESCE(description, ''), :desc) AS sim
        FROM product
        WHERE org_id = :org_id AND active = true
          AND similarity(name || ' ' || COALESCE(description, ''), :desc) > 0.3
        ORDER BY sim DESC
        LIMIT 30
        """,
        {"org_id": line.org_id, "desc": line.product_description or ""}
    ).fetchall()

    # Merge by product_id
    product_ids = set([r.id for r in sku_results] + [r.id for r in desc_results])
    return db.query(Product).filter(Product.id.in_(product_ids)).all()
```

### Testing Strategy

**Unit Tests:**
- Hybrid scoring formula: various S_tri, S_emb, P_uom, P_price combinations
- Auto-apply logic: threshold/gap scenarios
- UoM penalty: compatible/incompatible cases
- Price penalty: within/outside tolerance

**Integration Tests:**
- End-to-end: draft line → matching runs → candidates ranked → auto-applied if high confidence
- Confirmed mapping: confirm → next line auto-matched
- Rejection: reject 3 times → mapping deprecated
- Trigram search: various SKU/description inputs
- Vector search: semantic similarity

**Accuracy Tests:**
- Prepare 200 test lines with known correct matches
- Run matching, measure Top 1/3/5 accuracy
- Benchmark: Top 1 ≥85%, Top 3 ≥95%

**Performance Tests:**
- Matching 100 lines concurrently: p95 <500ms per line
- Trigram search: 10k products, p95 <50ms
- Vector search: 10k products, p95 <50ms

## SSOT References

- **§5.4.12**: sku_mapping table schema
- **§7.7.5**: Hybrid Search (trigram + embedding)
- **§7.7.6**: Concrete Scoring Formula (with penalties)
- **§7.7.7**: Thresholds (auto_apply_threshold, auto_apply_gap)
- **§7.9**: Match Confidence (method-specific)
- **§7.10.1**: Confirmed Mappings (learning loop)
- **§7.10.2**: Embeddings Reweighting (S_map dominance)
- **T-402**: Trigram Matcher task
- **T-403**: Hybrid Matcher task
- **T-404**: Mapping Confirm/Reject task
- **T-405**: Match Candidates Ranking task
- **T-408**: SKU Mapping Entity task
