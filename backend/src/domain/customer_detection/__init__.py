"""Customer Detection Domain Module

This module provides multi-signal customer detection for incoming orders.
It extracts signals from email metadata and document content, aggregates them
using probabilistic scoring, and auto-selects customers when confidence thresholds are met.
"""

from .service import CustomerDetectionService
from .models import DetectionResult, Candidate, DetectionSignal

__all__ = ["CustomerDetectionService", "DetectionResult", "Candidate", "DetectionSignal"]
