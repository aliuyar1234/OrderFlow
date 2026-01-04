"""Feedback module for learning loop and quality monitoring

This module handles:
- Feedback event capture (user corrections and confirmations)
- Layout fingerprinting for PDF documents
- Few-shot example selection for LLM prompts
- Learning analytics aggregation
"""

from .models import FeedbackEvent, DocLayoutProfile
from .services import FeedbackService, LayoutService, LearningService

__all__ = [
    "FeedbackEvent",
    "DocLayoutProfile",
    "FeedbackService",
    "LayoutService",
    "LearningService",
]
