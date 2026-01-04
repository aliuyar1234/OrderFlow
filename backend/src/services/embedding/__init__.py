"""Embedding Services - Product embedding generation and vector search.

This module provides services for:
- Canonical text generation from product data
- Embedding generation and caching
- Vector similarity search

SSOT Reference: §7.7 (Embedding-based Matching)
"""

from .text_generator import generate_product_embedding_text, generate_query_embedding_text
from .vector_search import vector_search_products

__all__ = [
    "generate_product_embedding_text",
    "generate_query_embedding_text",
    "vector_search_products",
]
