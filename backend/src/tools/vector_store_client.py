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
import time
from typing import List

import requests

logger = logging.getLogger("traguard.vector_store_client")

# ── Singleton index (loaded once, read-only) ─────────────────────────────────
_index = None
_documents: List[str] = []
_initialized = False
_HF_EMBEDDING_URL = (
    "https://router.huggingface.co/models/"
    "sentence-transformers/all-MiniLM-L6-v2"
)


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Generates embeddings via HuggingFace Inference API with 503 retry."""
    hf_token = os.getenv("HF_API_TOKEN", "")
    if not hf_token:
        raise EnvironmentError("HF_API_TOKEN not set")

    headers = {"Authorization": f"Bearer {hf_token}"}
    payload = {"inputs": texts}

    last_error = ""
    for attempt in range(1, 4):
        response = requests.post(
            _HF_EMBEDDING_URL,
            headers=headers,
            json=payload,
            timeout=40,
        )

        if response.status_code == 200:
            body = response.json()
            if (
                isinstance(body, list)
                and body
                and isinstance(body[0], list)
            ):
                return body
            raise RuntimeError(f"Unexpected embedding response format: {body}")

        if response.status_code == 503 and attempt < 3:
            logger.info(
                "Embedding model is loading (503). Retrying %d/3 in 10s...",
                attempt + 1,
            )
            time.sleep(10)
            continue

        last_error = f"HTTP {response.status_code}: {response.text}"
        break

    raise RuntimeError(f"Embedding inference failed: {last_error}")


def _lazy_init() -> bool:
    """Lazy-initialise the FAISS index on first call."""
    global _index, _documents, _initialized

    if _initialized:
        return _index is not None

    _initialized = True
    index_path     = os.getenv("FAISS_INDEX_PATH", "backend/data/disease_index.faiss")
    documents_path = os.getenv("FAISS_DOCS_PATH",  "backend/data/disease_docs.json")

    try:
        import faiss  # type: ignore[import]
        import json
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
        import numpy as np

        query_text = " ".join(symptoms[:20])[:512]
        embedding_vectors = _embed_texts([query_text])
        embedding = np.array(embedding_vectors, dtype="float32")

        distances, indices = _index.search(embedding, top_k)
        candidates = [
            _documents[i]
            for i in indices[0]
            if 0 <= i < len(_documents)
        ]
        return {"candidates": candidates, "success": True, "error": None}

    except Exception as exc:
        return {"candidates": [], "success": False, "error": str(exc)}
