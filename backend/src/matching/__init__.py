"""Matching module for OrderFlow.

This module implements hybrid SKU matching combining:
- Confirmed mappings (learning loop)
- Trigram similarity (pg_trgm)
- Vector embeddings (pgvector)
- UoM and price penalties

SSOT Reference: §7.7 (Hybrid Search), §7.10 (Learning Loop)
"""

from .ports import MatcherPort, MatchInput, MatchResult, MatchCandidate, MatcherError
from .hybrid_matcher import HybridMatcher
from .scorer import MatchScorer
from .router import router as matching_router

__all__ = [
    "MatcherPort",
    "MatchInput",
    "MatchResult",
    "MatchCandidate",
    "MatcherError",
    "HybridMatcher",
    "MatchScorer",
    "matching_router"
]
