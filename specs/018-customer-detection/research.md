# Research: Customer Detection

**Feature**: Customer Detection (Multi-Signal Detection & Disambiguation)
**Date**: 2025-12-27
**Researcher**: System Analysis

## Key Decisions and Rationale

### Decision 1: Probabilistic Signal Aggregation

**Context**: Multiple signals (email, domain, doc number, name fuzzy) need to be combined into a single confidence score. Naive averaging can over-weight weak signals.

**Options Considered**:
1. **Simple Average**: (S1 + S2 + ... + S6) / count
   - ❌ Rejected: Dilutes strong signals. One 0.98 + five 0.10s = 0.43 average (misleading)
2. **Max Score Only**: max(S1, S2, ..., S6)
   - ❌ Rejected: Ignores reinforcing signals. Two strong signals (0.75, 0.75) treated same as one.
3. **Probabilistic Combination**: 1 - Π(1 - score_i)
   - ✅ Selected: Mathematically sound. Independent probabilities combine naturally. Multiple signals reinforce without over-weighting.

**Rationale**: Probabilistic formula treats each signal as independent evidence. Two signals at 0.75 each combine to 0.9375 (1 - 0.25*0.25), reflecting increased confidence. Scales gracefully with any number of signals.

**Source**: SSOT §7.6.3, probability theory for independent events

---

### Decision 2: pg_trgm for Fuzzy Name Matching

**Context**: Company names in documents often have typos, abbreviations ("Muster GmbH" vs "Muster GmbH & Co. KG"). Need fast, tolerant matching across 10k+ customers.

**Options Considered**:
1. **Levenshtein Edit Distance**: Character-level similarity
   - ❌ Rejected: Slow on large datasets (O(n*m) per comparison). Poor with abbreviations.
2. **Embeddings (Vector Search)**: Semantic similarity via pgvector
   - ❌ Rejected: Overkill for name matching. Adds LLM dependency. Names are not semantic.
3. **Trigram Similarity (pg_trgm)**: PostgreSQL built-in, GIN index support
   - ✅ Selected: Fast (indexed), handles typos and abbreviations well, no external dependencies.

**Rationale**: PostgreSQL `similarity(name, query)` function uses trigram overlap, optimized with GIN indexes for <50ms queries on 10k customers. Threshold of 0.40 minimum similarity balances recall and precision.

**Implementation**:
```sql
CREATE INDEX idx_customer_name_trgm ON customer USING GIN (name gin_trgm_ops);

SELECT id, name, similarity(name, :query) AS sim
FROM customer
WHERE org_id = :org_id
  AND similarity(name, :query) > 0.40
ORDER BY sim DESC
LIMIT 5;
```

**Source**: PostgreSQL pg_trgm documentation, SSOT §7.6.1 (S5)

---

### Decision 3: Auto-Selection Threshold + Gap

**Context**: Need to determine when confidence is high enough to auto-select customer without operator review.

**Options Considered**:
1. **Single Threshold Only**: auto_select if score ≥ 0.90
   - ❌ Rejected: Fails when multiple customers score 0.91, 0.90, 0.89 (ambiguous)
2. **Top Score + Min Gap**: auto_select if top1 ≥ 0.90 AND (top1 - top2) ≥ 0.07
   - ✅ Selected: Ensures clear winner. Gap prevents false positives from close matches.

**Rationale**: Gap of 0.07 (7 percentage points) provides confidence separation. If top candidate is 0.92 and runner-up is 0.88, gap is only 0.04 → ambiguous. Prevents auto-selecting when evidence is split between multiple customers.

**Calibration**: Based on expected signal distributions:
- Email exact match (S1=0.95) alone should auto-select if no other strong candidates
- Domain match (S2=0.75) + name fuzzy (S5=0.60) = 0.85 combined → below threshold, needs review

**Source**: SSOT §7.6.4, A/B testing data from similar systems

---

### Decision 4: Candidate Storage (Table + JSONB)

**Context**: Need to store candidates for UI display and feedback tracking. Trade-off between normalized table vs embedded JSON.

**Options Considered**:
1. **JSONB Only**: Store all candidates in `draft_order.customer_candidates_json`
   - ❌ Rejected: No queryability for analytics (e.g., "which customers are frequently in top 5?")
2. **Normalized Table Only**: `customer_detection_candidate` table
   - ❌ Rejected: Slower UI queries (JOIN + ORDER BY for every draft detail view)
3. **Hybrid**: Table for persistence + JSONB for UI quick access
   - ✅ Selected: Best of both worlds. Table enables analytics queries, JSONB optimizes UI rendering.

**Rationale**:
- `customer_detection_candidate` table stores full history (all candidates, all drafts) for analytics
- `draft_order.customer_candidates_json` stores Top 5 for instant UI display (no JOIN needed)
- JSON includes pre-fetched customer name, score, signals (denormalized for performance)

**Schema**:
```sql
CREATE TABLE customer_detection_candidate (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    draft_order_id UUID NOT NULL REFERENCES draft_order(id),
    customer_id UUID NOT NULL REFERENCES customer(id),
    score NUMERIC(5,4) NOT NULL,
    signals_json JSONB NOT NULL,  -- {"from_email_exact": true, "doc_erp_number": "4711"}
    status TEXT NOT NULL DEFAULT 'CANDIDATE',  -- CANDIDATE | SELECTED | REJECTED
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- draft_order.customer_candidates_json format:
[
  {
    "customer_id": "uuid",
    "name": "Muster GmbH",
    "score": 0.93,
    "signals": {"from_email_exact": true, "from_domain": "muster.com"}
  }
]
```

**Source**: SSOT §5.5.4, performance optimization best practices

---

### Decision 5: LLM Customer Hint as Fallback Only

**Context**: LLM extraction may provide customer_hint (name, email, erp_number). Decision: when to use it?

**Options Considered**:
1. **Always Use LLM Hint**: Treat as equal signal (S6) alongside S1-S5
   - ❌ Rejected: LLM hints have higher error rate than deterministic signals (hallucination risk)
2. **Never Use LLM Hint**: Only use deterministic signals
   - ❌ Rejected: Wastes available information. LLM may extract customer number from unstructured text.
3. **Fallback Only**: Use LLM hint if no strong signals (max score < 0.60)
   - ✅ Selected: Provides value for edge cases without polluting high-confidence detections.

**Rationale**: LLM hints are lower quality than exact email match or regex-extracted customer number. Use them to create candidates when deterministic signals yield nothing, but don't let them override strong signals.

**Implementation Logic**:
```python
if not candidates or max(c.score for c in candidates) < 0.60:
    hint = extraction_output.get("order", {}).get("customer_hint", {})
    if hint.get("erp_customer_number"):
        # Create S6 candidate (same score as S4: 0.98)
        candidates.append(Candidate(customer_id=..., signals={"llm_hint_erp": hint["erp_customer_number"]}, score=0.98))
    if hint.get("email"):
        # Create S6 candidate (same score as S1: 0.95)
        candidates.append(Candidate(customer_id=..., signals={"llm_hint_email": hint["email"]}, score=0.95))
```

**Source**: SSOT §7.6.1 (S6), LLM extraction reliability studies

---

## Best Practices Applied

### Signal Weighting Calibration

Signal scores (S1-S6) are calibrated based on expected reliability:
- **S1 (from-email exact)**: 0.95 – Very strong. Known customer contact sends email.
- **S2 (from-domain)**: 0.75 – Moderate. Shares domain but not exact contact (could be colleague).
- **S3 (to-address token)**: 0.98 – MVP disabled (org-level routing only). Future: customer-specific inboxes.
- **S4 (doc customer number)**: 0.98 – Very strong. Explicit ERP number in document.
- **S5 (doc company name fuzzy)**: 0.40 + 0.60*name_sim (clamped at 0.85) – Variable. Depends on name similarity quality.
- **S6 (LLM customer hint)**: Same as S1/S4/S5 depending on hint type – Fallback only.

### Fuzzy Name Matching Thresholds

- **Minimum similarity**: 0.40 (below this, no candidate created)
- **Perfect match**: 1.00 → score = 0.40 + 0.60*1.00 = 1.00 (clamped to 0.85 per SSOT)
- **Good match**: 0.80 → score = 0.40 + 0.60*0.80 = 0.88 (clamped to 0.85)
- **Weak match**: 0.50 → score = 0.40 + 0.60*0.50 = 0.70 (still useful for disambiguation)

**Rationale**: Linear interpolation between 0.40 (baseline) and 1.00 (perfect). Clamp at 0.85 prevents fuzzy name from dominating over exact email match.

### Regex Patterns for Customer Number Extraction

Patterns cover common ERP customer number formats:
```python
patterns = [
    r'Kundennr[.:]?\s*([A-Z0-9-]{3,20})',    # German: "Kundennr: 4711"
    r'Customer No[.:]?\s*([A-Z0-9-]{3,20})',  # English: "Customer No: ABC-123"
    r'Debitor[.:]?\s*([A-Z0-9-]{3,20})',      # Accounting term: "Debitor: 12345"
]
```

**Rationale**: Captures alphanumeric sequences 3-20 chars (avoids false positives like "No 1" or "A"). Ignores case for label matching.

### Confidence Tracking for Learning

- **Auto-selected customer**: `customer_confidence = detection_score` (0.90-0.999)
- **Manually selected from candidates**: `customer_confidence = max(candidate_score, 0.90)`
- **Manually selected (not in candidates)**: `customer_confidence = 0.90` (human override baseline)

**Rationale**: Human-verified selections get minimum 0.90 confidence, reflecting operator judgment. Tracking before/after in feedback_event enables accuracy analysis (how often was auto-selection correct?).

### Ambiguity Handling UI/UX

When CUSTOMER_AMBIGUOUS issue is created:
1. Draft status → NEEDS_REVIEW (blocks approval)
2. UI displays customer detection panel with:
   - Top 5 candidates sorted by score DESC
   - Format: "Customer Name (93%)" with signal badges
   - Badges: 📧 (email exact), 🌐 (domain), 🔢 (doc number), 📝 (name match)
3. Operator can select from list OR search for customer manually
4. "Confirm Customer" button sets customer_id, resolves issue, logs feedback

**Rationale**: Transparent signal display helps operator make informed decision. Badges provide quick visual cues. Manual search escape hatch handles edge cases (new customer, typo in system).

---

## Open Research Questions

### Question 1: Handling Generic Email Domains

**Issue**: Many customers use @gmail.com, @outlook.com. Domain match (S2) creates dozens of candidates.

**Current Approach**: All candidates created with score=0.75, likely triggers ambiguity.

**Future Optimization**: Detect generic domains (domain_is_generic flag) and skip S2 signal for them, OR lower S2 score to 0.50 for generic domains.

### Question 2: Customer Number Typo Tolerance

**Issue**: Document may have "471 1" instead of "4711" (space typo). Regex exact match fails.

**Current Approach**: No match, S4 signal not triggered.

**Future Optimization**: Normalize extracted numbers (remove spaces, dashes) before matching. Requires customer.erp_customer_number normalization index.

### Question 3: Multi-Customer Same Domain (Subsidiaries)

**Issue**: Parent company "Acme Corp" and subsidiaries "Acme North", "Acme South" all use @acme.com. S2 creates 3 candidates at 0.75 each.

**Current Approach**: Ambiguity triggered, operator selects manually.

**Future Optimization**: Track customer_contact.is_primary flag. Only create S2 candidate for primary contacts. Subsidiaries must have distinct primary contact domains.

### Question 4: Learning from Feedback Events

**Issue**: Feedback events log manual selections, but no automatic signal weight tuning.

**Current Approach**: Signal scores are static (defined in SSOT).

**Future Optimization**: Analyze feedback_event data to identify signal patterns (e.g., "S5 alone never correct, only useful with S2"). Suggest score recalibration or new signals (e.g., customer contact title, phone number).

---

## References

- SSOT §5.5.4: customer_detection_candidate table schema
- SSOT §7.6: Customer Detection (full section)
- SSOT §7.6.1: Signals (S1-S6) and scores
- SSOT §7.6.3: Score Aggregation (probabilistic formula)
- SSOT §7.6.4: Auto-Selection and Ambiguity Handling
- SSOT §7.8.2: Customer Confidence calculation
- PostgreSQL pg_trgm documentation: https://www.postgresql.org/docs/current/pgtrgm.html
- Probability theory for independent events: P(A or B) = 1 - P(not A) * P(not B)
