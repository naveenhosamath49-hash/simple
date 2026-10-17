from __future__ import annotations

import logging
import re
from typing import List, Set, Tuple, Optional
from app.config import settings

logger = logging.getLogger(__name__)


def get_token_shingles(text: str, n: int = 2) -> Set[str]:
    """Generate unigram and n-gram word shingles from normalized text."""
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w.rstrip("s") if len(w) > 4 else w for w in cleaned.split() if len(w) > 1]
    if not words:
        return set()

    shingles = set(words)  # include unigrams
    if len(words) >= n:
        for i in range(len(words) - n + 1):
            shingles.add(" ".join(words[i : i + n]))
    return shingles


def calculate_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculate Jaccard similarity coefficient between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    if union == 0:
        return 0.0
    return intersection / union


class DeduplicationService:
    """
    Two-stage deduplication engine:
    1. Exact duplicate detection via deterministic SHA-256 fingerprinting.
    2. Near-duplicate detection via token shingle Jaccard similarity.
    """

    def __init__(self, threshold: Optional[float] = None):
        self.threshold = threshold or settings.DEDUPLICATION_SIMILARITY_THRESHOLD

    def compute_similarity(self, title_a: str, body_a: str, title_b: str, body_b: str) -> float:
        """
        Compute weighted similarity between two articles.
        Title holds 60% weight, body holds 40% weight.
        """
        title_shingles_a = get_token_shingles(title_a, n=2)
        title_shingles_b = get_token_shingles(title_b, n=2)
        title_sim = calculate_jaccard_similarity(title_shingles_a, title_shingles_b)

        # Fast path: if titles have zero similarity, unlikely to be duplicates
        if title_sim < 0.3:
            return title_sim * 0.6

        body_shingles_a = get_token_shingles(body_a[:1000] if body_a else "", n=2)
        body_shingles_b = get_token_shingles(body_b[:1000] if body_b else "", n=2)
        body_sim = calculate_jaccard_similarity(body_shingles_a, body_shingles_b)

        weighted_score = (0.6 * title_sim) + (0.4 * body_sim)
        return weighted_score

    def find_near_duplicate(
        self,
        candidate_title: str,
        candidate_body: str,
        existing_articles: List[Tuple[int, str, str]],  # List of (id, title, body)
    ) -> Optional[Tuple[int, float]]:
        """
        Check if candidate article is a near-duplicate of any existing article in the window.
        Returns (existing_article_id, similarity_score) if threshold exceeded, else None.
        """
        best_id: Optional[int] = None
        best_score = 0.0

        for art_id, title, body in existing_articles:
            sim = self.compute_similarity(candidate_title, candidate_body, title, body)
            if sim > best_score:
                best_score = sim
                best_id = art_id

        if best_score >= self.threshold and best_id is not None:
            logger.info(f"Near-duplicate detected (score={best_score:.2f}) against article ID {best_id}.")
            return best_id, best_score

        return None
