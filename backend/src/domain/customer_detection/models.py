"""Customer Detection Domain Models

Dataclasses for customer detection results, candidates, and signals.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class DetectionSignal:
    """Represents a single detection signal extracted from inbound data.

    Signals are individual pieces of evidence pointing to a specific customer,
    such as email match, domain match, or document customer number.
    """
    signal_type: str  # from_email_exact, from_domain, doc_customer_number, doc_company_name, llm_hint
    value: str  # The extracted value (email, domain, customer number, etc.)
    score: float  # Signal-specific confidence score (0.0 to 1.0)
    metadata: dict = field(default_factory=dict)  # Additional context (e.g., similarity score)


@dataclass
class Candidate:
    """Represents a candidate customer for an incoming order.

    A candidate is a customer that matches one or more detection signals,
    with an aggregated score representing overall confidence.
    """
    customer_id: UUID
    customer_name: str
    signals: list[DetectionSignal] = field(default_factory=list)
    aggregate_score: float = 0.0

    def add_signal(self, signal: DetectionSignal):
        """Add a signal and recalculate aggregate score using probabilistic combination.

        Formula: score = 1 - Π(1 - score_i)
        This ensures signals reinforce each other without over-weighting.
        """
        self.signals.append(signal)

        # Probabilistic combination: 1 - product of (1 - each score)
        complement_product = 1.0
        for s in self.signals:
            complement_product *= (1 - s.score)

        # Clamp to max 0.999 (reserve 1.0 for manual override)
        self.aggregate_score = min(0.999, 1 - complement_product)

    def get_signal_badges(self) -> list[str]:
        """Get human-readable signal badges for UI display."""
        badges = []
        signal_types = {s.signal_type for s in self.signals}

        if "from_email_exact" in signal_types:
            badges.append("Email Match")
        if "from_domain" in signal_types:
            badges.append("Domain Match")
        if "doc_customer_number" in signal_types:
            badges.append("Customer # in Doc")
        if "doc_company_name" in signal_types:
            badges.append("Company Name Match")
        if "llm_hint" in signal_types:
            badges.append("AI Detection")

        return badges


@dataclass
class DetectionResult:
    """Result of customer detection for an inbound order.

    Contains ranked candidates, auto-selection status, and metadata.
    """
    candidates: list[Candidate] = field(default_factory=list)
    selected_customer_id: Optional[UUID] = None
    confidence: float = 0.0
    auto_selected: bool = False
    ambiguous: bool = False
    reason: Optional[str] = None

    @property
    def top_candidate(self) -> Optional[Candidate]:
        """Get the top-ranked candidate."""
        return self.candidates[0] if self.candidates else None

    @property
    def needs_manual_selection(self) -> bool:
        """Check if manual customer selection is required."""
        return self.ambiguous or not self.auto_selected
