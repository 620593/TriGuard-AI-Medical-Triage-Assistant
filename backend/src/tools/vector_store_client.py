"""
vector_store_client.py  (Version 6 — tools/)
----------------------------------------------
Stateless FAISS vector store client for disease candidate retrieval.

Rules:
    - NEVER modifies state.
    - Pure function: accepts symptom list, returns candidate list.
    - Index is loaded once at module load time (singleton pattern — read-only).
"""

import os
import logging
from typing import List, Optional

logger = logging.getLogger("traguard.vector_store_client")

# ── Singleton index (loaded once, read-only) ─────────────────────────────────
_index = None
_documents: List[str] = []
_embedder = None
_initialized = False


def _lazy_init() -> bool:
    """Lazy-initialise the FAISS index and sentence embedder on first call."""
    global _index, _documents, _embedder, _initialized

    if _initialized:
        return _index is not None

    _initialized = True
    index_path     = os.getenv("FAISS_INDEX_PATH", "backend/data/disease_index.faiss")
    documents_path = os.getenv("FAISS_DOCS_PATH",  "backend/data/disease_docs.json")

    try:
        import faiss  # type: ignore[import]
        import json
        from sentence_transformers import SentenceTransformer  # type: ignore[import]

        _embedder  = SentenceTransformer("all-MiniLM-L6-v2")
        _index     = faiss.read_index(index_path)

        with open(documents_path, "r", encoding="utf-8") as f:
            _documents = json.load(f)

        logger.info("FAISS index loaded: %d documents", len(_documents))
        return True

    except Exception as exc:
        logger.warning("Vector store unavailable: %s", exc)
        return False


def retrieve_candidates(
    symptoms: List[str],
    top_k: int = 5,
) -> dict:
    """
    Retrieves top-k disease candidate descriptions for given symptoms.

    Args:
        symptoms: List of extracted symptom strings.
        top_k:    Max candidates to return (default 5).

    Returns:
        dict with keys: {'candidates': List[str], 'success': bool, 'error': str | None}
    """
    if not symptoms:
        return {"candidates": [], "success": False, "error": "No symptoms provided"}

    if not _lazy_init():
        return {"candidates": [], "success": False, "error": "Vector store unavailable"}

    try:
        query_text = " ".join(symptoms[:20])[:512]
        embedding  = _embedder.encode([query_text])

        distances, indices = _index.search(embedding, top_k)
        candidates = [
            _documents[i]
            for i in indices[0]
            if 0 <= i < len(_documents)
        ]
        return {"candidates": candidates, "success": True, "error": None}

    except Exception as exc:
        return {"candidates": [], "success": False, "error": str(exc)}
