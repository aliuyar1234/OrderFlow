# Feature Specification: Customer Detection (Multi-Signal Detection & Disambiguation)

**Feature Branch**: `018-customer-detection`
**Created**: 2025-12-27
**Status**: Draft
**Module**: customer_detection
**SSOT Refs**: §5.5.4 (customer_detection_candidate), §7.6 (Customer Detection), §7.8.2 (Customer Confidence), T-505, T-506

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Email-Based Customer Detection (Priority: P1)

When an inbound email arrives, the system extracts the sender email and automatically matches it against customer contacts. If exact match found, customer is auto-selected with high confidence.

**Why this priority**: Email is the strongest signal. Most orders come from known customer contacts. Enables hands-free customer detection for majority of cases.

**Independent Test**: Email from buyer@customer-a.com arrives → customer contact exact match → customer_id auto-set, confidence=0.95, no manual selection needed.

**Acceptance Scenarios**:

1. **Given** inbound email from_email="buyer@customer-a.com", **When** running customer detection, **Then** finds customer_contact with email="buyer@customer-a.com", creates candidate with score=0.95 (S1: from-email exact)
2. **Given** candidate with score=0.95 and gap to #2 ≥0.07, **When** auto-select threshold ≥0.90, **Then** sets draft.customer_id, customer_confidence=0.95, candidate.status=SELECTED
3. **Given** no exact email match but domain matches (e.g., from another-buyer@customer-a.com), **When** detecting, **Then** creates candidate with score=0.75 (S2: from-domain match)
4. **Given** multiple customers share same domain (e.g., @gmail.com), **When** detecting, **Then** creates multiple candidates with score=0.75 each, triggers ambiguity handling

---

### User Story 2 - Document-Based Customer Detection (SKU + Fuzzy Name) (Priority: P1)

The system scans the extracted document text for customer numbers (regex patterns) and company names. Matches against customer.erp_customer_number and customer.name (fuzzy trigram). Combines signals with email to select best candidate.

**Why this priority**: Orders often include customer number in header/footer. Provides fallback when email domain is generic.

**Independent Test**: PDF contains "Kundennr: 4711" → matches customer.erp_customer_number="4711" → score=0.98, combined with domain score=0.75 → aggregate score=0.998 → auto-selected.

**Acceptance Scenarios**:

1. **Given** PDF text contains "Kundennr: 4711", **When** running regex extraction, **Then** finds "4711", queries customer WHERE erp_customer_number="4711", creates candidate with score=0.98 (S4: doc customer number)
2. **Given** PDF contains "Muster GmbH" in header, **When** running fuzzy name match, **Then** calculates trigram similarity vs all customer.name values, if best match ≥0.60 creates candidate with score=0.40 + 0.60*name_sim (S5: doc company name fuzzy)
3. **Given** multiple signals (S1=0.0, S2=0.75, S4=0.98), **When** aggregating, **Then** score = 1 - (1-0.75)*(1-0.98) = 1 - 0.25*0.02 = 0.995
4. **Given** LLM extraction provides customer_hint.name="Muster GmbH", **When** no other strong signals, **Then** uses LLM hint for fuzzy name match (S6: LLM customer hint)

---

### User Story 3 - Candidate Ranking and Ambiguity Handling (Priority: P1)

When multiple candidates exist, the system ranks by aggregate score, checks if top candidate meets auto-select threshold AND has sufficient gap to #2. If not, creates CUSTOMER_AMBIGUOUS issue and shows selection UI.

**Why this priority**: Prevents auto-selecting wrong customer when signals are weak or conflicting. Ensures human verification for edge cases.

**Independent Test**: Email from generic domain, 3 customers with similar names → all score ~0.70 → top1-top2 gap=0.05 (below threshold) → CUSTOMER_AMBIGUOUS issue created, UI shows selection dropdown.

**Acceptance Scenarios**:

1. **Given** 3 candidates with scores [0.92, 0.88, 0.60], **When** checking auto-select, **Then** top1=0.92 ≥ threshold (0.90), gap=0.92-0.88=0.04 < min_gap (0.07) → ambiguous, no auto-select
2. **Given** ambiguous customer, **When** creating draft, **Then** customer_id=null, CUSTOMER_AMBIGUOUS issue (ERROR severity) created, draft.status=NEEDS_REVIEW
3. **Given** candidates stored in customer_detection_candidate table, **When** rendering UI, **Then** Draft detail shows customer detection panel with Top 5 candidates, scores, signal badges (email match, domain match, doc number)
4. **Given** Ops selects customer from dropdown and clicks "Confirm Customer", **When** confirming, **Then** draft.customer_id set, selected candidate.status=SELECTED, other candidates.status=REJECTED, CUSTOMER_AMBIGUOUS issue resolved, feedback_event created

---

### User Story 4 - Signal Aggregation with Probabilistic Combination (Priority: P2)

The system combines multiple independent signals using probabilistic formula: score = 1 - Π(1 - score_i), ensuring signals reinforce each other without over-weighting.

**Why this priority**: Mathematically sound aggregation. Prevents single weak signal from dominating. Enables transparent score breakdown for debugging.

**Independent Test**: Candidate with S2=0.75 (domain) and S5=0.55 (name fuzzy) → aggregate = 1 - (1-0.75)*(1-0.55) = 0.8875 → strong combined signal.

**Acceptance Scenarios**:

1. **Given** candidate with S1=0.95 only, **When** aggregating, **Then** score=0.95
2. **Given** candidate with S2=0.75 and S4=0.98, **When** aggregating, **Then** score = 1 - (1-0.75)*(1-0.98) = 1 - 0.25*0.02 = 0.995
3. **Given** candidate with S5=0.55 only, **When** aggregating, **Then** score=0.55 (below threshold, not auto-selected)
4. **Given** aggregate score >0.999, **When** clamping, **Then** score clamped to 0.999 (max)

---

### User Story 5 - Confidence Tracking and Learning (Priority: P2)

When Ops manually selects customer (overriding auto-selection or resolving ambiguity), customer_confidence is set to max(detection_score, 0.90) to reflect human verification. Feedback event is logged for quality monitoring.

**Why this priority**: Human override is treated as high confidence. Feedback enables analysis of detection accuracy over time.

**Independent Test**: Candidate auto-selected with score=0.92 → Ops changes to different customer → new customer_confidence=0.90 (human override baseline), feedback_event shows before/after.

**Acceptance Scenarios**:

1. **Given** customer auto-selected with score=0.93, **When** draft approved, **Then** customer_confidence=0.93
2. **Given** customer manually selected from candidates (score=0.75), **When** confirming, **Then** customer_confidence=max(0.75, 0.90)=0.90
3. **Given** Ops selects customer not in candidates (searched manually), **When** confirming, **Then** customer_confidence=0.90, feedback_event.event_type=CUSTOMER_SELECTED, before_json=candidates, after_json=selected_customer_id
4. **Given** feedback events collected, **When** analyzing, **Then** can measure auto-select accuracy (how often auto-selected customer is confirmed vs changed)

---

### User Story 6 - LLM Customer Hint as Fallback (Priority: P3)

When email/doc signals yield no candidates and LLM extraction is used, the system uses customer_hint from LLM output (name, email, erp_customer_number) as additional signal.

**Why this priority**: LLM can extract customer info from unstructured documents. Useful fallback when other signals fail.

**Independent Test**: Upload scan with no structured customer number → LLM extraction provides customer_hint.name="ABC Corp" → fuzzy match finds customer → score=0.60 → candidate created.

**Acceptance Scenarios**:

1. **Given** LLM extraction returns customer_hint.erp_customer_number="4711", **When** detecting, **Then** matches against customer.erp_customer_number, creates candidate with score=0.98 (same as S4)
2. **Given** LLM extraction returns customer_hint.name="Muster GmbH", **When** no S1-S4 signals, **Then** runs fuzzy name match (S6: LLM hint), creates candidate
3. **Given** LLM extraction returns customer_hint.email="buyer@customer.com", **When** detecting, **Then** checks if email matches customer_contact, creates candidate with score=0.95 (same as S1)
4. **Given** LLM already used for extraction, **When** customer hint available, **Then** no additional LLM call needed (hint is part of extraction output)

---

### Edge Cases

- What happens when email domain is generic (gmail.com, outlook.com) and many customers use it?
- How does system handle typos in customer number (e.g., "471 1" vs "4711")?
- What happens when customer name in document is abbreviated ("Muster" vs "Muster GmbH & Co. KG")?
- How does system handle multiple customers with same domain (parent company + subsidiaries)?
- What happens when inbound email has no from_email (system-generated, forwarded)?
- How does system handle customer contact email change (old email no longer valid)?

## Requirements *(mandatory)*

### Functional Requirements

**Signal Extraction:**
- **FR-001**: System MUST extract from_email from inbound_message
- **FR-002**: System MUST extract domain from from_email (part after @)
- **FR-003**: System MUST scan document text for customer number patterns using regex:
  - Patterns: `Kundennr[.:]?\s*([A-Z0-9-]{3,20})`, `Customer No[.:]?\s*([A-Z0-9-]{3,20})`, `Debitor[.:]?\s*([A-Z0-9-]{3,20})`
  - Extract alphanumeric sequence 3-20 chars
- **FR-004**: System MUST extract potential company name from document header (first 500 chars) or LLM customer_hint
- **FR-005**: System MUST use customer_hint from LLM extraction if available (name, email, erp_customer_number)

**Signal Scoring:**
- **FR-006**: System MUST calculate signal scores per §7.6.1:
  - S1 (from-email exact): 0.95 if from_email matches customer_contact.email exactly
  - S2 (from-domain): 0.75 if domain matches any customer_contact.email domain
  - S3 (to-address token): 0.98 (MVP: disabled, org-level routing only)
  - S4 (doc customer number): 0.98 if extracted number matches customer.erp_customer_number
  - S5 (doc company name fuzzy): 0.40 + 0.60*name_sim, clamped at 0.85, where name_sim = trigram_similarity(extracted_name, customer.name)
  - S6 (LLM customer hint): same as S1/S4/S5 depending on which hint field matches
- **FR-007**: System MUST aggregate signals per §7.6.3:
  - score(c) = 1 - Π(1 - score_i) over all applicable signals i
  - Clamp to [0..0.999]

**Candidate Generation:**
- **FR-008**: System MUST generate candidates from:
  - All customers whose contacts have exact email match (S1)
  - All customers whose contacts share domain (S2)
  - Customer with matching erp_customer_number (S4)
  - Top 5 customers by name similarity if extracted name exists (S5)
- **FR-009**: System MUST create customer_detection_candidate entries per §5.5.4 with:
  - customer_id, score, signals_json (which signals triggered), status=CANDIDATE
- **FR-010**: System MUST store candidates in draft.customer_candidates_json for UI quick access (Top 5)

**Auto-Selection:**
- **FR-011**: System MUST auto-select customer if:
  - top1.score ≥ org.settings.customer_detection.auto_select_threshold (default 0.90)
  - top1.score - top2.score ≥ org.settings.customer_detection.min_gap (default 0.07)
  - Action: set draft.customer_id=top1.customer_id, customer_confidence=top1.score, candidate.status=SELECTED
- **FR-012**: If auto-select fails, system MUST:
  - Set draft.customer_id=null, customer_confidence=0.0
  - Create CUSTOMER_AMBIGUOUS issue (ERROR severity)
  - Set draft.status=NEEDS_REVIEW

**Manual Selection:**
- **FR-013**: When Ops selects customer via UI, system MUST:
  - Set draft.customer_id=selected_id
  - Set customer_confidence=max(candidate.score, 0.90) if candidate exists, else 0.90
  - Update candidate.status=SELECTED for selected, =REJECTED for others
  - Resolve CUSTOMER_AMBIGUOUS issue
  - Create feedback_event: event_type=CUSTOMER_SELECTED, before_json=candidates, after_json=selected_id
- **FR-014**: System MUST re-run ready-check after customer selection

**UI Integration:**
- **FR-015**: Draft detail UI MUST display customer detection panel when customer_id=null OR CUSTOMER_AMBIGUOUS issue exists
- **FR-016**: Panel MUST show:
  - Top 5 candidates sorted by score DESC
  - Format: "Customer Name (93%)" with signal badges (email exact, domain, doc number, name match)
  - Dropdown to select customer + search box for manual lookup
  - "Confirm Customer" button
- **FR-017**: Panel MUST show auto-selected customer (if auto-selected) with confidence badge and allow manual change

### Key Entities

- **customer_detection_candidate** (§5.5.4): Candidate customers with scores and signals
- **CustomerDetectionService**: Service component running detection logic
- **SignalAggregator**: Combines signals using probabilistic formula
- **customer.erp_customer_number**: Key field for doc number matching
- **customer_contact.email**: Key field for email/domain matching

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Email exact match (S1) achieves ≥95% auto-selection rate for known customers
- **SC-002**: Doc customer number (S4) achieves ≥90% auto-selection rate when number present
- **SC-003**: Combined signals (S2+S5) achieve ≥70% auto-selection rate for orders without exact email/number
- **SC-004**: Auto-selection accuracy (correct customer) ≥97% (measured via feedback events)
- **SC-005**: Customer detection completes in <100ms per inbound message
- **SC-006**: Ambiguity rate (CUSTOMER_AMBIGUOUS issues) <15% of total orders
- **SC-007**: Manual overrides (user selects different customer than auto-selected) <5% of auto-selections
- **SC-008**: Signal extraction (regex, fuzzy name) has <5% false positive rate

## Dependencies

- **Depends on**:
  - Customer and customer_contact entities (from catalog module)
  - InboundMessage entity (from inbox module)
  - Document extraction (for text scanning and LLM customer_hint)
  - Draft entity (to set customer_id)
  - Validation service (to create/resolve CUSTOMER_AMBIGUOUS issue)

- **Blocks**:
  - 013-draft-orders-core (needs customer_id for ready-check)
  - Price validation (requires customer_id to lookup customer_prices)
  - Matching (customer-specific mappings)

## Technical Notes

### Implementation Guidance

**Confidence Cap Rationale:** Maximum aggregated score capped at 0.999 to reserve 1.0 for manual override (explicit user selection). This ensures user-confirmed customer always ranks highest. Formula: min(aggregated_score, 0.999).

**Company Name Extraction Rules:** (1) Skip lines matching date patterns (\\d{1,2}[./-]\\d{1,2}[./-]\\d{2,4}), (2) Skip lines matching phone/fax patterns (^[+\\d\\s()-]{7,}$), (3) Prefer lines 10-100 chars with company keywords (GmbH, Ltd, Inc, Corp, AG, KG, OHG), (4) Fallback to LLM customer_hint if heuristic confidence <0.3. Log extraction method in detection debug.

**LLM Customer Hint:** S6 (LLM hint) is optional enhancement, not requirement. Customer detection MUST work with signals S1-S5 alone (email/domain/doc number/order history/fuzzy name). If LLM extraction not available or fails, skip S6 signal. Detection accuracy may be lower but system remains functional.

**Customer Detection Service:**
```python
class CustomerDetectionService:
    def detect_customer(self, inbound: InboundMessage, draft: DraftOrder, extraction_output: dict) -> DetectionResult:
        candidates = []

        # S1: From-email exact
        if inbound.from_email:
            exact_customers = self.find_by_contact_email(inbound.from_email)
            for cust in exact_customers:
                candidates.append(Candidate(
                    customer_id=cust.id,
                    signals={"from_email_exact": True},
                    score=0.95
                ))

        # S2: From-domain
        if inbound.from_email:
            domain = inbound.from_email.split('@')[1]
            domain_customers = self.find_by_contact_domain(domain)
            for cust in domain_customers:
                if cust.id not in [c.customer_id for c in candidates]:
                    candidates.append(Candidate(
                        customer_id=cust.id,
                        signals={"from_domain": domain},
                        score=0.75
                    ))

        # S4: Doc customer number
        doc_text = self.get_document_text(draft.document_id)
        erp_number = self.extract_customer_number(doc_text)
        if erp_number:
            cust = self.find_by_erp_number(erp_number)
            if cust:
                candidates.append(Candidate(
                    customer_id=cust.id,
                    signals={"doc_erp_number": erp_number},
                    score=0.98
                ))

        # S5: Doc company name fuzzy
        company_name = self.extract_company_name(doc_text) or extraction_output.get("order", {}).get("customer_hint", {}).get("name")
        if company_name:
            name_matches = self.fuzzy_name_search(company_name, top_k=5)
            for cust, name_sim in name_matches:
                if name_sim >= 0.40:  # min threshold
                    score = min(0.85, 0.40 + 0.60 * name_sim)
                    candidates.append(Candidate(
                        customer_id=cust.id,
                        signals={"doc_name_fuzzy": company_name, "name_sim": name_sim},
                        score=score
                    ))

        # S6: LLM customer hint (if no strong signals)
        if not candidates or max(c.score for c in candidates) < 0.60:
            hint = extraction_output.get("order", {}).get("customer_hint", {})
            if hint.get("erp_customer_number"):
                # Same as S4
                pass  # Already handled above
            if hint.get("email"):
                # Same as S1
                pass

        # Aggregate signals per customer
        aggregated = self.aggregate_candidates(candidates)

        # Sort and auto-select
        aggregated.sort(key=lambda c: c.score, reverse=True)
        top1 = aggregated[0] if aggregated else None
        top2 = aggregated[1] if len(aggregated) > 1 else None

        auto_select_threshold = get_org_setting(draft.org_id, "customer_detection.auto_select_threshold", 0.90)
        min_gap = get_org_setting(draft.org_id, "customer_detection.min_gap", 0.07)

        if top1 and top1.score >= auto_select_threshold:
            gap = top1.score - (top2.score if top2 else 0)
            if gap >= min_gap:
                return DetectionResult(
                    selected_customer_id=top1.customer_id,
                    confidence=top1.score,
                    candidates=aggregated[:5],
                    auto_selected=True
                )

        # Ambiguous
        return DetectionResult(
            selected_customer_id=None,
            confidence=0.0,
            candidates=aggregated[:5],
            auto_selected=False,
            issue=CUSTOMER_AMBIGUOUS
        )

    def aggregate_candidates(self, candidates: list[Candidate]) -> list[Candidate]:
        """Combine multiple signals per customer using probabilistic formula"""
        by_customer = {}
        for c in candidates:
            if c.customer_id not in by_customer:
                by_customer[c.customer_id] = []
            by_customer[c.customer_id].append(c)

        aggregated = []
        for customer_id, cands in by_customer.items():
            # score = 1 - Π(1 - score_i)
            complement_product = 1.0
            signals = {}
            for cand in cands:
                complement_product *= (1 - cand.score)
                signals.update(cand.signals)

            score = min(0.999, 1 - complement_product)
            aggregated.append(Candidate(
                customer_id=customer_id,
                signals=signals,
                score=score
            ))

        return aggregated

    def extract_customer_number(self, text: str) -> str | None:
        patterns = [
            r'Kundennr[.:]?\s*([A-Z0-9-]{3,20})',
            r'Customer No[.:]?\s*([A-Z0-9-]{3,20})',
            r'Debitor[.:]?\s*([A-Z0-9-]{3,20})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def extract_company_name(self, text: str) -> str | None:
        # Heuristic: extract first non-email line from header (first 500 chars)
        lines = text[:500].split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 5 and '@' not in line and not re.match(r'^\d', line):
                # Likely company name
                return line
        return None

    def fuzzy_name_search(self, query: str, top_k: int = 5) -> list[tuple[Customer, float]]:
        results = db.execute(
            """
            SELECT id, name, similarity(name, :query) AS sim
            FROM customer
            WHERE org_id = :org_id
              AND similarity(name, :query) > 0.40
            ORDER BY sim DESC
            LIMIT :limit
            """,
            {"org_id": self.org_id, "query": query, "limit": top_k}
        ).fetchall()

        customers = db.query(Customer).filter(Customer.id.in_([r.id for r in results])).all()
        return [(c, r.sim) for c, r in zip(customers, results)]
```

**Candidate Storage:**
```python
def store_candidates(draft: DraftOrder, detection_result: DetectionResult):
    # Store in customer_detection_candidate table
    for cand in detection_result.candidates:
        candidate = CustomerDetectionCandidate(
            org_id=draft.org_id,
            draft_order_id=draft.id,
            customer_id=cand.customer_id,
            score=cand.score,
            signals_json=cand.signals,
            status="SELECTED" if cand.customer_id == detection_result.selected_customer_id else "CANDIDATE"
        )
        db.add(candidate)

    # Store in draft.customer_candidates_json for UI quick access
    draft.customer_candidates_json = [
        {
            "customer_id": str(c.customer_id),
            "name": get_customer_name(c.customer_id),
            "score": c.score,
            "signals": c.signals
        }
        for c in detection_result.candidates[:5]
    ]

    db.commit()
```

### Testing Strategy

**Unit Tests:**
- Signal extraction: regex patterns, email domain, fuzzy name
- Signal scoring: S1-S6 individual scores
- Signal aggregation: probabilistic formula, various combinations
- Auto-select logic: threshold/gap scenarios

**Integration Tests:**
- End-to-end: inbound email → detection → candidates → auto-selected
- End-to-end: ambiguous → UI selection → customer confirmed
- Feedback: manual selection → feedback_event created

**Accuracy Tests:**
- Prepare 100 test orders with known customers
- Run detection, measure auto-selection accuracy (correct customer selected)
- Measure ambiguity rate (how often CUSTOMER_AMBIGUOUS triggered)
- Benchmark: ≥97% accuracy, ≤15% ambiguity

**Performance Tests:**
- Detection on 100 inbound messages: p95 <100ms
- Fuzzy name search on 1000 customers: <50ms
- Regex extraction on 10-page PDF text: <10ms

## SSOT References

- **§5.5.4**: customer_detection_candidate table schema
- **§7.6**: Customer Detection (full section)
- **§7.6.1**: Signals (S1-S6) and scores
- **§7.6.2**: Candidate Generation
- **§7.6.3**: Score Aggregation (probabilistic formula)
- **§7.6.4**: Auto-Selection and Ambiguity Handling
- **§7.8.2**: Customer Confidence calculation
- **§7.10.4**: Customer Selection Feedback
- **§9.4**: Draft Order Detail UI (customer detection panel)
- **§10.1**: Org Settings (customer_detection config)
- **T-505**: Customer Detection Service task
- **T-506**: Customer Detection UI Panel task
