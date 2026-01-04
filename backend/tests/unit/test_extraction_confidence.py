"""Unit tests for extraction confidence calculation

Tests cover:
- Header confidence calculation
- Line confidence calculation
- Overall confidence calculation with weighted average
- Edge cases (empty data, partial data)
- Confidence thresholds for routing

SSOT Reference: §7.8 (Confidence Calculation)
"""

import pytest
from decimal import Decimal

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from domain.extraction.confidence import (
    calculate_header_confidence,
    calculate_line_confidence,
    calculate_lines_confidence,
    calculate_confidence
)
from domain.extraction.canonical_output import (
    CanonicalExtractionOutput,
    ExtractionOrderHeader,
    ExtractionLineItem
)


class TestHeaderConfidence:
    """Test header completeness scoring"""

    def test_complete_header_full_confidence(self):
        """Test header with all required fields gets 1.0 confidence"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )

        confidence = calculate_header_confidence(header)
        assert confidence == 1.0

    def test_partial_header_partial_confidence(self):
        """Test header missing some required fields gets partial confidence"""
        # Missing order_date (2 out of 3 required fields)
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date=None,
            currency="EUR"
        )

        confidence = calculate_header_confidence(header)
        assert confidence == pytest.approx(0.667, abs=0.01)  # 2/3

    def test_header_missing_order_number(self):
        """Test header without order_number"""
        header = ExtractionOrderHeader(
            order_number=None,
            order_date="2024-01-15",
            currency="EUR"
        )

        confidence = calculate_header_confidence(header)
        assert confidence == pytest.approx(0.667, abs=0.01)  # 2/3

    def test_header_missing_currency(self):
        """Test header without currency"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency=None
        )

        confidence = calculate_header_confidence(header)
        assert confidence == pytest.approx(0.667, abs=0.01)  # 2/3

    def test_header_only_one_field(self):
        """Test header with only one required field"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date=None,
            currency=None
        )

        confidence = calculate_header_confidence(header)
        assert confidence == pytest.approx(0.333, abs=0.01)  # 1/3

    def test_header_no_fields(self):
        """Test header with no required fields"""
        header = ExtractionOrderHeader(
            order_number=None,
            order_date=None,
            currency=None
        )

        confidence = calculate_header_confidence(header)
        assert confidence == 0.0


class TestLineConfidence:
    """Test single line item completeness scoring"""

    def test_complete_line_full_confidence(self):
        """Test line with all essential fields gets 1.0 confidence"""
        line = ExtractionLineItem(
            line_no=1, customer_sku="SKU-001",
            qty=Decimal("10.000"),
            description="Widget A"
        )

        confidence = calculate_line_confidence(line)
        assert confidence == 1.0

    def test_line_missing_description(self):
        """Test line without description (2 out of 3 fields)"""
        line = ExtractionLineItem(
            line_no=1, customer_sku="SKU-001",
            qty=Decimal("10.000"),
            description=None
        )

        confidence = calculate_line_confidence(line)
        assert confidence == pytest.approx(0.667, abs=0.01)  # 2/3

    def test_line_missing_quantity(self):
        """Test line without quantity"""
        line = ExtractionLineItem(
            line_no=1, customer_sku="SKU-001",
            qty=None,
            description="Widget A"
        )

        confidence = calculate_line_confidence(line)
        assert confidence == pytest.approx(0.667, abs=0.01)  # 2/3

    def test_line_missing_sku(self):
        """Test line without customer SKU"""
        line = ExtractionLineItem(
            line_no=1, customer_sku=None,
            qty=Decimal("10.000"),
            description="Widget A"
        )

        confidence = calculate_line_confidence(line)
        assert confidence == pytest.approx(0.667, abs=0.01)  # 2/3

    def test_line_only_sku(self):
        """Test line with only SKU"""
        line = ExtractionLineItem(
            line_no=1, customer_sku="SKU-001",
            qty=None,
            description=None
        )

        confidence = calculate_line_confidence(line)
        assert confidence == pytest.approx(0.333, abs=0.01)  # 1/3

    def test_line_no_essential_fields(self):
        """Test line with no essential fields"""
        line = ExtractionLineItem(
            line_no=1, customer_sku=None,
            qty=None,
            description=None
        )

        confidence = calculate_line_confidence(line)
        assert confidence == 0.0

    def test_line_with_optional_fields_no_bonus(self):
        """Test optional fields don't affect confidence score"""
        # Line with optional fields (uom, unit_price) but missing description
        line = ExtractionLineItem(
            line_no=1, customer_sku="SKU-001",
            qty=Decimal("10.000"),
            description=None,
            uom="EA",
            unit_price=Decimal("25.50")
        )

        confidence = calculate_line_confidence(line)
        # Should still be 2/3 (only essential fields count)
        assert confidence == pytest.approx(0.667, abs=0.01)


class TestLinesConfidence:
    """Test average line confidence across multiple lines"""

    def test_all_complete_lines(self):
        """Test all lines complete gives 1.0 average"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
            ExtractionLineItem(line_no=1, customer_sku="SKU-002", qty=Decimal("20"), description="Widget B"),
            ExtractionLineItem(line_no=1, customer_sku="SKU-003", qty=Decimal("5"), description="Widget C"),
        ]

        confidence = calculate_lines_confidence(lines)
        assert confidence == 1.0

    def test_mixed_completeness_lines(self):
        """Test lines with varying completeness"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),  # 1.0
            ExtractionLineItem(line_no=1, customer_sku="SKU-002", qty=Decimal("20"), description=None),        # 0.667
            ExtractionLineItem(line_no=1, customer_sku="SKU-003", qty=None, description=None),                 # 0.333
        ]

        confidence = calculate_lines_confidence(lines)
        # Average: (1.0 + 0.667 + 0.333) / 3 = 0.667
        assert confidence == pytest.approx(0.667, abs=0.01)

    def test_single_line(self):
        """Test single line average equals that line's confidence"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description=None),  # 0.667
        ]

        confidence = calculate_lines_confidence(lines)
        assert confidence == pytest.approx(0.667, abs=0.01)

    def test_empty_lines_list(self):
        """Test empty lines list returns 0.0"""
        lines = []

        confidence = calculate_lines_confidence(lines)
        assert confidence == 0.0

    def test_all_incomplete_lines(self):
        """Test all lines with minimal data"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=None, description=None),  # 0.333
            ExtractionLineItem(line_no=1, customer_sku="SKU-002", qty=None, description=None),  # 0.333
        ]

        confidence = calculate_lines_confidence(lines)
        assert confidence == pytest.approx(0.333, abs=0.01)


class TestOverallConfidence:
    """Test overall extraction confidence calculation"""

    def test_complete_extraction_full_confidence(self):
        """Test extraction with complete header and lines gets 1.0"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
            ExtractionLineItem(line_no=1, customer_sku="SKU-002", qty=Decimal("20"), description="Widget B"),
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, breakdown = calculate_confidence(output)

        assert score == 1.0
        assert breakdown['header_score'] == 1.0
        assert breakdown['lines_score'] == 1.0

    def test_weighted_average_default_weights(self):
        """Test default weights: 40% header, 60% lines"""
        # Header: 0.667 (2/3 fields)
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency=None
        )
        # Lines: 1.0 (all complete)
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, breakdown = calculate_confidence(output)

        # Expected: 0.4 * 0.667 + 0.6 * 1.0 = 0.267 + 0.6 = 0.867
        assert score == pytest.approx(0.867, abs=0.01)
        assert breakdown['header_score'] == pytest.approx(0.667, abs=0.01)
        assert breakdown['lines_score'] == 1.0

    def test_custom_weights(self):
        """Test custom weights for header and lines"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date=None,
            currency=None
        )  # 0.333
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
        ]  # 1.0
        output = CanonicalExtractionOutput(order=header, lines=lines)

        # Custom weights: 20% header, 80% lines
        score, breakdown = calculate_confidence(output, header_weight=0.2, lines_weight=0.8)

        # Expected: 0.2 * 0.333 + 0.8 * 1.0 = 0.067 + 0.8 = 0.867
        assert score == pytest.approx(0.867, abs=0.01)
        assert breakdown['header_weight'] == 0.2
        assert breakdown['lines_weight'] == 0.8

    def test_score_rounded_to_3_decimals(self):
        """Test overall score is rounded to 3 decimal places"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency=None
        )  # 0.667
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description=None),
        ]  # 0.667
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, breakdown = calculate_confidence(output)

        # Score should have max 3 decimal places
        assert len(str(score).split('.')[-1]) <= 3

    def test_breakdown_includes_metadata(self):
        """Test breakdown dict includes all metadata"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
            ExtractionLineItem(line_no=1, customer_sku="SKU-002", qty=Decimal("20"), description="Widget B"),
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, breakdown = calculate_confidence(output)

        assert 'header_score' in breakdown
        assert 'lines_score' in breakdown
        assert 'lines_count' in breakdown
        assert 'header_weight' in breakdown
        assert 'lines_weight' in breakdown
        assert breakdown['lines_count'] == 2

    def test_empty_extraction_zero_confidence(self):
        """Test extraction with no data gets 0.0 confidence"""
        header = ExtractionOrderHeader(
            order_number=None,
            order_date=None,
            currency=None
        )
        lines = []
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, breakdown = calculate_confidence(output)

        assert score == 0.0
        assert breakdown['header_score'] == 0.0
        assert breakdown['lines_score'] == 0.0

    def test_invalid_weights_raises_error(self):
        """Test weights not summing to 1.0 raises ValueError"""
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        # Weights sum to 0.9
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            calculate_confidence(output, header_weight=0.4, lines_weight=0.5)

        # Weights sum to 1.1
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            calculate_confidence(output, header_weight=0.6, lines_weight=0.5)


class TestConfidenceThresholds:
    """Test confidence scores against routing thresholds"""

    def test_auto_approve_threshold(self):
        """Test extraction above 0.95 should route to auto-approval"""
        # Perfect extraction
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
            ExtractionLineItem(line_no=1, customer_sku="SKU-002", qty=Decimal("20"), description="Widget B"),
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, _ = calculate_confidence(output)

        # Should be >= 0.95 for auto-approval
        assert score >= 0.95

    def test_needs_review_threshold(self):
        """Test extraction below 0.95 should route to manual review"""
        # Missing some data
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency=None  # Missing currency
        )
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("10"), description="Widget A"),
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, _ = calculate_confidence(output)

        # Should be < 0.95 for manual review
        assert score < 0.95

    def test_critical_threshold(self):
        """Test extraction below 0.5 indicates poor quality"""
        # Very incomplete data
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date=None,
            currency=None
        )  # 0.333
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=None, description=None),  # 0.333
        ]
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, _ = calculate_confidence(output)

        # Should be < 0.5 indicating poor quality
        assert score < 0.5


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_very_long_lines_list(self):
        """Test confidence calculation with many lines"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku=f"SKU-{i:03d}", qty=Decimal("10"), description=f"Item {i}")
            for i in range(100)
        ]
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, breakdown = calculate_confidence(output)

        assert score == 1.0
        assert breakdown['lines_count'] == 100

    def test_lines_with_zero_qty(self):
        """Test line with quantity=0 is still considered complete"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("0"), description="Widget A"),
        ]
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, _ = calculate_confidence(output)

        # qty=0 is a valid value, should count as complete
        assert score == 1.0

    def test_lines_with_negative_qty(self):
        """Test line with negative quantity is still considered complete"""
        lines = [
            ExtractionLineItem(line_no=1, customer_sku="SKU-001", qty=Decimal("-5"), description="Return"),
        ]
        header = ExtractionOrderHeader(
            order_number="PO-12345",
            order_date="2024-01-15",
            currency="EUR"
        )
        output = CanonicalExtractionOutput(order=header, lines=lines)

        score, _ = calculate_confidence(output)

        # Negative qty is a value, counts as present
        assert score == 1.0
