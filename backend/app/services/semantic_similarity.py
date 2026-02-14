"""
Semantic similarity service for ingredient substitute ranking.

Uses sentence-transformers (all-MiniLM-L6-v2) to compute semantic similarity
between the original ingredient and candidate substitutes. Improves ranking
by understanding that "butter" and "ghee" are conceptually similar even when
molecule overlap differs.

Phase 1 of LLM-to-transformer replacement.
"""

import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model: Optional[object] = None


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        logger.info("Semantic similarity model loaded (all-MiniLM-L6-v2)")
        return _model
    except ImportError as e:
        logger.warning(
            "sentence-transformers not installed. Semantic re-ranking disabled. "
            "Install with: pip install sentence-transformers"
        )
        raise e


def compute_similarity_scores(
    original: str,
    candidates: List[str],
) -> List[Tuple[str, float]]:
    """
    Compute semantic similarity between original ingredient and each candidate.

    Returns list of (candidate_name, similarity_score) where similarity_score
    is 0-100 (higher = more semantically similar).

    Args:
        original: Original ingredient name (e.g. "butter")
        candidates: List of candidate substitute names

    Returns:
        List of (candidate, score) tuples, sorted by score descending.
        Returns empty list if model fails or candidates empty.
    """
    if not candidates:
        return []

    try:
        model = _get_model()
    except ImportError:
        return []

    try:
        # Encode original and candidates
        orig_emb = model.encode(original, convert_to_tensor=False)
        cand_embs = model.encode(candidates, convert_to_tensor=False)

        # Cosine similarity (embeddings are L2-normalized, so dot product = cosine)
        import numpy as np
        scores = np.dot(cand_embs, orig_emb)

        # Map [-1, 1] to [0, 100]
        normalized = [(s + 1) / 2 * 100 for s in scores]

        # Sort by score descending
        ranked = sorted(
            zip(candidates, normalized),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked

    except Exception as e:
        logger.warning(f"Semantic similarity failed: {e}")
        return []
