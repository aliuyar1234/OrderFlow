# Customer Detection Algorithm Documentation

## Overview

The Customer Detection system implements a multi-signal, probabilistic approach to automatically identify the correct customer for incoming order documents. The algorithm extracts signals from email metadata and document content, aggregates them using mathematical combination, and auto-selects customers when confidence thresholds are met.

## Algorithm Components

### 1. Signal Extraction

The system extracts six types of signals (S1-S6) from inbound data:

#### S1: From-Email Exact Match (Score: 0.95)
- **Input:** `from_email` from inbound message
- **Process:** Exact match against `customer_contact.email`
- **Priority:** Highest (most reliable signal)
- **Example:** `buyer@customer-a.com` matches contact record exactly

#### S2: From-Domain Match (Score: 0.75)
- **Input:** Email domain extracted from `from_email`
- **Process:** Match against all customer contacts with same domain
- **Filter:** Excludes generic domains (gmail.com, outlook.com, etc.)
- **Example:** `another-buyer@customer-a.com` matches domain `customer-a.com`

#### S3: To-Address Token (Score: 0.98)
- **Status:** Disabled in MVP (org-level routing only)
- **Future:** Will support customer-specific email routing

#### S4: Document Customer Number (Score: 0.98)
- **Input:** Document text (first 2000 chars)
- **Process:** Regex extraction of customer numbers
- **Patterns:**
  - `Kundennr[.:]?\s*([A-Z0-9-]{3,20})`
  - `Customer No[.:]?\s*([A-Z0-9-]{3,20})`
  - `Debitor[.:]?\s*([A-Z0-9-]{3,20})`
- **Match:** Exact match against `customer.erp_customer_number`
- **Example:** "Kundennr: 4711" extracts "4711", matches customer record

#### S5: Document Company Name Fuzzy Match (Score: 0.40 + 0.60 * similarity, max 0.85)
- **Input:** Document text (first 500 chars)
- **Process:**
  1. Heuristic extraction of company name from header
  2. Skip lines with dates, phone numbers, emails
  3. Prefer lines with company keywords (GmbH, Ltd, Inc, etc.)
  4. PostgreSQL trigram similarity match against `customer.name`
- **Scoring Formula:** `score = min(0.85, 0.40 + 0.60 * trigram_similarity)`
- **Threshold:** Only creates signal if similarity >= 0.40
- **Example:** "Muster GmbH" with 0.75 similarity → score = 0.85 (capped)

#### S6: LLM Customer Hint (Score: Variable)
- **Input:** `customer_hint` from LLM extraction output
- **Process:** Treats hint fields as corresponding signals:
  - `erp_customer_number` → Same as S4 (score 0.98)
  - `email` → Same as S1 (score 0.95)
  - `name` → Used for fuzzy matching (S5)
- **Priority:** Fallback signal when other signals are weak
- **Example:** LLM extracts customer hint with number "4711" → matches like S4

### 2. Signal Aggregation

**Probabilistic Combination Formula:**

For each customer with multiple signals, aggregate score is calculated as:

```
aggregate_score = 1 - Π(1 - score_i)
```

Where:
- `Π` is the product over all signals for that customer
- `score_i` is the individual signal score (0.0 to 1.0)
- Result is clamped to max 0.999 (reserves 1.0 for manual override)

**Mathematical Properties:**
- Independent signals reinforce each other
- No single weak signal dominates
- Multiple weak signals combine to strong confidence
- Order-independent (commutative)

**Examples:**

1. **Single Signal:**
   - S1 only (email exact): `1 - (1 - 0.95) = 0.95`

2. **Two Strong Signals:**
   - S2 (domain 0.75) + S4 (customer number 0.98):
   - `1 - (1 - 0.75)(1 - 0.98) = 1 - 0.25 × 0.02 = 0.995`

3. **Weak + Strong Signal:**
   - S5 (name fuzzy 0.55) + S2 (domain 0.75):
   - `1 - (1 - 0.55)(1 - 0.75) = 1 - 0.45 × 0.25 = 0.8875`

4. **Three Signals:**
   - S1 (0.95) + S2 (0.75) + S5 (0.55):
   - `1 - (1 - 0.95)(1 - 0.75)(1 - 0.55)`
   - `= 1 - 0.05 × 0.25 × 0.45 = 0.994375`

### 3. Candidate Ranking

After aggregation, candidates are:
1. Sorted by `aggregate_score` descending
2. Top 5 candidates retained for UI display
3. Lower-scored candidates discarded

### 4. Auto-Selection Logic

**Criteria for Auto-Selection:**

1. **Score Threshold:** `top1.score >= auto_select_threshold` (default 0.90)
2. **Gap Requirement:** `top1.score - top2.score >= min_gap` (default 0.07)

**Auto-Selection Decision Tree:**

```
IF no candidates found:
    → Ambiguous: "No customer matches found"

IF top1.score >= auto_select_threshold:
    IF gap to top2 >= min_gap (or no top2):
        → Auto-select top1
        → Set customer_id, confidence = top1.score
    ELSE:
        → Ambiguous: "Insufficient gap to #2"
ELSE:
    → Ambiguous: "Top score below threshold"
```

**Examples:**

1. **Auto-Selected (clear winner):**
   - Top1: 0.95, Top2: 0.65
   - Gap: 0.30 >= 0.07 ✓
   - Score: 0.95 >= 0.90 ✓
   - **Result:** Auto-select top1

2. **Ambiguous (close scores):**
   - Top1: 0.92, Top2: 0.88
   - Gap: 0.04 < 0.07 ✗
   - **Result:** Ambiguous, manual selection required

3. **Ambiguous (low confidence):**
   - Top1: 0.75, Top2: 0.50
   - Score: 0.75 < 0.90 ✗
   - **Result:** Ambiguous, manual selection required

### 5. Confidence Tracking

**Auto-Selection:**
- `customer_confidence = aggregate_score` of selected candidate

**Manual Selection:**
- `customer_confidence = max(candidate.score, 0.90)` if candidate exists
- `customer_confidence = 0.90` if manually searched (baseline human override)

**Rationale:** Human verification is treated as high confidence (0.90 minimum).

## Performance Characteristics

### Time Complexity

- **Email Exact Match (S1):** O(1) with index on `customer_contact.email`
- **Domain Match (S2):** O(k) where k = contacts with matching domain
- **Customer Number (S4):** O(1) with index on `customer.erp_customer_number`
- **Fuzzy Name (S5):** O(n log n) with GIN trigram index on `customer.name`
- **Aggregation:** O(m × s) where m = candidates, s = avg signals per candidate

**Expected Performance:**
- Detection on single inbound: <100ms (p95)
- Fuzzy name search (1000 customers): <50ms
- Regex extraction (10-page PDF): <10ms

### Database Indexes Required

1. `customer_contact.email` (BTREE)
2. `customer.erp_customer_number` (BTREE)
3. `customer.name` (GIN trigram - `gin_trgm_ops`)

## Edge Cases Handling

### 1. Generic Email Domains
- **Problem:** gmail.com, outlook.com shared by many customers
- **Solution:** S2 domain signal excludes generic domains
- **Fallback:** Rely on S4 (doc customer number) or S5 (fuzzy name)

### 2. Multiple Contacts Per Customer
- **Problem:** Customer has 5 contacts, email matches one
- **Solution:** All contacts for same customer create same candidate
- **Aggregation:** Multiple S1 signals for same customer don't multiply

### 3. Typos in Customer Number
- **Problem:** Document has "471 1" vs database "4711"
- **Current:** No match (exact match only)
- **Future:** Could add fuzzy number matching (edit distance)

### 4. Abbreviated Company Names
- **Problem:** Document says "Muster" vs database "Muster GmbH & Co. KG"
- **Solution:** Trigram similarity tolerates differences
- **Scoring:** Short matches get lower similarity → lower score

### 5. No From-Email (Forwarded/System)
- **Problem:** Inbound message has no valid sender
- **Solution:** Fall back to S4 (doc number) and S5 (name)
- **Result:** May be ambiguous, requires manual selection

### 6. LLM Hallucination
- **Problem:** LLM customer_hint contains made-up customer number
- **Solution:** S6 only matches if number exists in database
- **Safety:** No new customers created, only existing matched

## Quality Metrics

**Success Criteria (per SSOT):**

- Email exact match (S1): ≥95% auto-selection rate
- Doc customer number (S4): ≥90% auto-selection rate
- Combined signals (S2+S5): ≥70% auto-selection rate
- Auto-selection accuracy: ≥97% (correct customer)
- Ambiguity rate: <15% of total orders
- Manual override rate: <5% of auto-selections

## Configuration

**Org-Level Settings:**

```json
{
  "customer_detection": {
    "auto_select_threshold": 0.90,
    "min_gap": 0.07,
    "enable_llm_hints": true,
    "fuzzy_name_min_similarity": 0.40
  }
}
```

## Implementation Notes

### Database Schema

**customer_detection_candidate:**
- `id` (UUID, PK)
- `org_id` (UUID, FK → org)
- `draft_order_id` (UUID, FK → draft_order)
- `customer_id` (UUID, FK → customer)
- `score` (FLOAT)
- `signals_json` (JSONB) - Array of signal objects
- `status` (TEXT) - 'CANDIDATE', 'SELECTED', 'REJECTED'
- `created_at`, `updated_at` (TIMESTAMPTZ)

**Unique Constraint:** `(draft_order_id, customer_id)` prevents duplicates

### Signal Storage Format

```json
{
  "signals": [
    {
      "signal_type": "from_email_exact",
      "value": "buyer@customer-a.com",
      "score": 0.95,
      "metadata": {"email": "buyer@customer-a.com"}
    },
    {
      "signal_type": "doc_customer_number",
      "value": "4711",
      "score": 0.98,
      "metadata": {"pattern": "Kundennr: (.*)", "extracted_number": "4711"}
    }
  ],
  "aggregate_score": 0.999
}
```

## Testing Strategy

### Unit Tests
- Signal extraction (regex, email domain)
- Fuzzy name matching edge cases
- Probabilistic aggregation formula
- Auto-select threshold/gap logic

### Integration Tests
- End-to-end: inbound → candidates → auto-select
- Database queries with realistic data
- Performance benchmarks

### Accuracy Tests
- 100+ real order samples with known customers
- Measure auto-selection accuracy vs manual labeling
- Measure ambiguity rate

## Future Enhancements

1. **Order History Signal (S7):**
   - Match based on previous orders from same inbound email
   - Score based on recency and frequency

2. **Ship-To Address Matching:**
   - Extract address from document
   - Calculate address similarity score
   - Combine with other signals

3. **Learning Loop:**
   - Track manual overrides
   - Adjust signal weights per organization
   - Re-train fuzzy matching thresholds

4. **Customer Number Fuzzy Matching:**
   - Handle typos, spaces, formatting differences
   - Edit distance or normalization

5. **Domain Reputation:**
   - Lower score for domains with many customers
   - Boost score for exclusive domains

## References

- **SSOT Spec:** §7.6 (Customer Detection)
- **Spec File:** `specs/018-customer-detection/spec.md`
- **Plan File:** `specs/018-customer-detection/plan.md`
- **Tasks File:** `specs/018-customer-detection/tasks.md`
