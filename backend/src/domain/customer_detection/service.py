"""Customer Detection Service

Main orchestrator for multi-signal customer detection.
Implements the detection algorithm per SSOT §7.6.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models.customer import Customer
from models.customer_contact import CustomerContact
from .models import DetectionResult, Candidate, DetectionSignal
from .signal_extractor import SignalExtractor

logger = logging.getLogger(__name__)


class CustomerDetectionService:
    """Service for detecting customers from inbound orders using multi-signal approach.

    Extracts signals from email metadata and document content, aggregates them
    using probabilistic scoring, and auto-selects customers when thresholds are met.
    """

    def __init__(self, db: Session, org_id: UUID):
        """Initialize detection service.

        Args:
            db: Database session
            org_id: Organization ID for multi-tenant scoping
        """
        self.db = db
        self.org_id = org_id

    def detect_customer(
        self,
        from_email: Optional[str] = None,
        document_text: Optional[str] = None,
        llm_hint: Optional[dict] = None,
        auto_select_threshold: float = 0.90,
        min_gap: float = 0.07
    ) -> DetectionResult:
        """Run customer detection using all available signals.

        Args:
            from_email: Sender email from inbound message
            document_text: Extracted text from document
            llm_hint: Optional customer_hint from LLM extraction
            auto_select_threshold: Minimum score for auto-selection (default 0.90)
            min_gap: Minimum gap between top 2 candidates (default 0.07)

        Returns:
            DetectionResult with ranked candidates and selection status
        """
        candidates_map: dict[UUID, Candidate] = {}

        # S1: From-email exact match
        if from_email:
            signal = SignalExtractor.extract_from_email_exact(from_email)
            if signal:
                self._process_email_signal(signal, candidates_map)

        # S2: From-domain match
        if from_email:
            signal = SignalExtractor.extract_from_domain(from_email)
            if signal:
                self._process_domain_signal(signal, candidates_map)

        # S4: Document customer number
        if document_text:
            signal = SignalExtractor.extract_customer_number_from_doc(document_text)
            if signal:
                self._process_customer_number_signal(signal, candidates_map)

        # S5: Document company name fuzzy match
        if document_text:
            company_name = SignalExtractor.extract_company_name_from_doc(document_text)
            if company_name:
                self._process_fuzzy_name(company_name, candidates_map)

        # S6: LLM customer hint (fallback signal)
        if llm_hint:
            llm_signals = SignalExtractor.extract_from_llm_hint(llm_hint)
            for signal in llm_signals:
                if signal.metadata.get("hint_type") == "erp_customer_number":
                    self._process_customer_number_signal(signal, candidates_map)
                elif signal.metadata.get("hint_type") == "email":
                    self._process_email_signal(signal, candidates_map)

            # LLM name hint for fuzzy matching
            if llm_hint.get("name"):
                self._process_fuzzy_name(llm_hint["name"], candidates_map)

        # Convert to list and sort by aggregate score
        candidates = sorted(
            candidates_map.values(),
            key=lambda c: c.aggregate_score,
            reverse=True
        )

        # Determine auto-selection
        result = DetectionResult(candidates=candidates[:5])  # Top 5 for UI

        if not candidates:
            result.ambiguous = True
            result.reason = "No customer matches found"
            return result

        top1 = candidates[0]
        top2 = candidates[1] if len(candidates) > 1 else None

        # Auto-select criteria:
        # 1. Top candidate score >= threshold
        # 2. Gap to 2nd candidate >= min_gap (or no 2nd candidate)
        if top1.aggregate_score >= auto_select_threshold:
            gap = top1.aggregate_score - (top2.aggregate_score if top2 else 0)

            if gap >= min_gap:
                result.selected_customer_id = top1.customer_id
                result.confidence = top1.aggregate_score
                result.auto_selected = True
                result.reason = f"Auto-selected with {top1.aggregate_score:.1%} confidence"
                logger.info(
                    f"Auto-selected customer {top1.customer_id} "
                    f"(score={top1.aggregate_score:.3f}, gap={gap:.3f})"
                )
            else:
                result.ambiguous = True
                result.reason = (
                    f"Top candidate score {top1.aggregate_score:.1%} meets threshold, "
                    f"but gap to #2 ({gap:.1%}) is below minimum ({min_gap:.1%})"
                )
                logger.info(f"Ambiguous: insufficient gap ({gap:.3f} < {min_gap})")
        else:
            result.ambiguous = True
            result.reason = (
                f"Top candidate score {top1.aggregate_score:.1%} "
                f"below auto-select threshold {auto_select_threshold:.1%}"
            )
            logger.info(
                f"Ambiguous: top score {top1.aggregate_score:.3f} "
                f"< threshold {auto_select_threshold}"
            )

        return result

    def _process_email_signal(
        self,
        signal: DetectionSignal,
        candidates_map: dict[UUID, Candidate]
    ):
        """Process exact email match signal (S1).

        Finds all customers with matching contact email.
        """
        email = signal.value
        contacts = self.db.execute(
            select(CustomerContact)
            .join(Customer)
            .where(
                CustomerContact.email == email,
                Customer.org_id == self.org_id,
                Customer.is_active == True
            )
        ).scalars().all()

        for contact in contacts:
            customer = contact.customer
            if customer.id not in candidates_map:
                candidates_map[customer.id] = Candidate(
                    customer_id=customer.id,
                    customer_name=customer.name
                )
            candidates_map[customer.id].add_signal(signal)

        logger.debug(f"Email signal {email} matched {len(contacts)} contacts")

    def _process_domain_signal(
        self,
        signal: DetectionSignal,
        candidates_map: dict[UUID, Candidate]
    ):
        """Process email domain match signal (S2).

        Finds all customers with contacts on the same domain.
        """
        domain = signal.value

        # Find all contacts with matching domain
        contacts = self.db.execute(
            select(CustomerContact)
            .join(Customer)
            .where(
                CustomerContact.email.like(f"%@{domain}"),
                Customer.org_id == self.org_id,
                Customer.is_active == True
            )
        ).scalars().all()

        for contact in contacts:
            customer = contact.customer
            if customer.id not in candidates_map:
                candidates_map[customer.id] = Candidate(
                    customer_id=customer.id,
                    customer_name=customer.name
                )
            candidates_map[customer.id].add_signal(signal)

        logger.debug(f"Domain signal {domain} matched {len(contacts)} contacts")

    def _process_customer_number_signal(
        self,
        signal: DetectionSignal,
        candidates_map: dict[UUID, Candidate]
    ):
        """Process customer number match signal (S4).

        Finds customer by exact erp_customer_number match.
        """
        customer_number = signal.value

        customer = self.db.execute(
            select(Customer).where(
                Customer.org_id == self.org_id,
                Customer.erp_customer_number == customer_number,
                Customer.is_active == True
            )
        ).scalar_one_or_none()

        if customer:
            if customer.id not in candidates_map:
                candidates_map[customer.id] = Candidate(
                    customer_id=customer.id,
                    customer_name=customer.name
                )
            candidates_map[customer.id].add_signal(signal)
            logger.debug(f"Customer number {customer_number} matched customer {customer.id}")
        else:
            logger.debug(f"Customer number {customer_number} not found")

    def _process_fuzzy_name(
        self,
        company_name: str,
        candidates_map: dict[UUID, Candidate]
    ):
        """Process fuzzy company name matching (S5).

        Uses PostgreSQL trigram similarity for fuzzy matching.
        Requires pg_trgm extension.
        """
        # Use trigram similarity search
        # Note: This requires pg_trgm extension to be enabled
        query = select(
            Customer.id,
            Customer.name,
            func.similarity(Customer.name, company_name).label('similarity')
        ).where(
            Customer.org_id == self.org_id,
            Customer.is_active == True,
            func.similarity(Customer.name, company_name) > 0.40
        ).order_by(
            func.similarity(Customer.name, company_name).desc()
        ).limit(5)

        results = self.db.execute(query).all()

        for customer_id, customer_name, similarity in results:
            signal = SignalExtractor.create_fuzzy_name_signal(company_name, similarity)
            if signal:
                if customer_id not in candidates_map:
                    candidates_map[customer_id] = Candidate(
                        customer_id=customer_id,
                        customer_name=customer_name
                    )
                candidates_map[customer_id].add_signal(signal)

        logger.debug(
            f"Fuzzy name match for '{company_name}' found {len(results)} candidates"
        )
