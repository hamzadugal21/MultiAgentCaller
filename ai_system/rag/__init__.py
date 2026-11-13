"""Permission-aware local retrieval primitives for bounded agents."""

from ai_system.rag.service import (
    LocalMiniLMEmbedder,
    RagDocument,
    RetrievalPrincipal,
    RetrievalResult,
    SharedRagService,
)

__all__ = [
    "LocalMiniLMEmbedder",
    "RagDocument",
    "RetrievalPrincipal",
    "RetrievalResult",
    "SharedRagService",
]
