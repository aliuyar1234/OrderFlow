"""Signal Extraction Logic for Customer Detection

Extracts detection signals from email metadata and document content.
Implements signals S1-S6 per SSOT §7.6.1.
"""

import re
from typing import Optional
from uuid import UUID

from .models import DetectionSignal


class SignalExtractor:
    """Extracts customer detection signals from various sources."""

    # Regex patterns for customer number extraction (S4)
    CUSTOMER_NUMBER_PATTERNS = [
        r'Kundennr[.:]?\s*([A-Z0-9-]{3,20})',
        r'Customer\s+No[.:]?\s*([A-Z0-9-]{3,20})',
        r'Debitor[.:]?\s*([A-Z0-9-]{3,20})',
        r'Kunden-Nr[.:]?\s*([A-Z0-9-]{3,20})',
        r'Client\s+ID[.:]?\s*([A-Z0-9-]{3,20})',
    ]

    @staticmethod
    def extract_from_email_exact(from_email: Optional[str]) -> Optional[DetectionSignal]:
        """S1: Extract from-email exact match signal.

        Score: 0.95 (highest priority signal)
        """
        if not from_email:
            return None

        return DetectionSignal(
            signal_type="from_email_exact",
            value=from_email.lower(),
            score=0.95,
            metadata={"email": from_email}
        )

    @staticmethod
    def extract_from_domain(from_email: Optional[str]) -> Optional[DetectionSignal]:
        """S2: Extract email domain match signal.

        Score: 0.75
        Returns None for generic domains (gmail.com, outlook.com, etc.)
        """
        if not from_email or "@" not in from_email:
            return None

        domain = from_email.split("@")[1].lower()

        # Skip generic email providers
        generic_domains = {
            "gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
            "yahoo.com", "web.de", "gmx.de", "gmx.net", "live.com",
            "icloud.com", "me.com", "aol.com"
        }

        if domain in generic_domains:
            return None

        return DetectionSignal(
            signal_type="from_domain",
            value=domain,
            score=0.75,
            metadata={"domain": domain, "email": from_email}
        )

    @staticmethod
    def extract_customer_number_from_doc(document_text: Optional[str]) -> Optional[DetectionSignal]:
        """S4: Extract customer number from document text.

        Score: 0.98 (very high confidence if found)
        Searches for patterns like "Kundennr: 4711", "Customer No: ABC123"
        """
        if not document_text:
            return None

        # Search first 2000 chars (header section)
        search_text = document_text[:2000]

        for pattern in SignalExtractor.CUSTOMER_NUMBER_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                customer_number = match.group(1).strip()
                return DetectionSignal(
                    signal_type="doc_customer_number",
                    value=customer_number,
                    score=0.98,
                    metadata={"pattern": pattern, "extracted_number": customer_number}
                )

        return None

    @staticmethod
    def extract_company_name_from_doc(document_text: Optional[str]) -> Optional[str]:
        """Extract potential company name from document header.

        This is a heuristic extraction - the actual signal is created after
        fuzzy matching against customer database (S5).

        Returns: Extracted company name string or None
        """
        if not document_text:
            return None

        # Search first 500 chars
        lines = document_text[:500].split('\n')

        # Company keywords
        company_keywords = ['GmbH', 'Ltd', 'Inc', 'Corp', 'AG', 'KG', 'OHG', 'SE', 'e.V.', 'mbH']

        for line in lines:
            line = line.strip()

            # Skip if too short or too long
            if len(line) < 10 or len(line) > 100:
                continue

            # Skip date patterns
            if re.match(r'^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', line):
                continue

            # Skip phone/fax patterns
            if re.match(r'^[+\d\s()-]{7,}$', line):
                continue

            # Skip lines with email addresses
            if '@' in line:
                continue

            # Prefer lines with company keywords
            if any(keyword in line for keyword in company_keywords):
                return line

        # Fallback: return first non-empty line that meets basic criteria
        for line in lines:
            line = line.strip()
            if 10 <= len(line) <= 100 and '@' not in line and not re.match(r'^\d', line):
                return line

        return None

    @staticmethod
    def create_fuzzy_name_signal(company_name: str, similarity: float) -> Optional[DetectionSignal]:
        """S5: Create company name fuzzy match signal.

        Score: 0.40 + 0.60 * name_similarity, clamped at 0.85
        Only creates signal if similarity >= 0.40

        Args:
            company_name: The extracted company name
            similarity: Trigram similarity score (0.0 to 1.0)
        """
        if similarity < 0.40:
            return None

        # Formula per SSOT: 0.40 + 0.60 * similarity, max 0.85
        score = min(0.85, 0.40 + 0.60 * similarity)

        return DetectionSignal(
            signal_type="doc_company_name",
            value=company_name,
            score=score,
            metadata={"similarity": similarity, "extracted_name": company_name}
        )

    @staticmethod
    def extract_from_llm_hint(llm_hint: Optional[dict]) -> list[DetectionSignal]:
        """S6: Extract signals from LLM customer hint.

        LLM extraction may provide customer_hint with fields:
        - erp_customer_number: treated same as S4 (score 0.98)
        - email: treated same as S1 (score 0.95)
        - name: used for fuzzy matching (S5)

        Args:
            llm_hint: customer_hint dict from LLM extraction output

        Returns: List of signals extracted from hint
        """
        if not llm_hint:
            return []

        signals = []

        # LLM customer number hint (same as S4)
        if llm_hint.get("erp_customer_number"):
            signals.append(DetectionSignal(
                signal_type="llm_hint",
                value=llm_hint["erp_customer_number"],
                score=0.98,
                metadata={"hint_type": "erp_customer_number", "source": "llm"}
            ))

        # LLM email hint (same as S1)
        if llm_hint.get("email"):
            signals.append(DetectionSignal(
                signal_type="llm_hint",
                value=llm_hint["email"].lower(),
                score=0.95,
                metadata={"hint_type": "email", "source": "llm"}
            ))

        return signals
