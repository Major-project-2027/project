"""
Face matching module -- compares a live embedding against all registered
students using cosine similarity.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

UNKNOWN_LABEL = "unknown"


@dataclass
class MatchResult:
    """Result of comparing one live embedding against the registered gallery."""
    student_id: str
    confidence: float
    matched: bool


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec_a: First embedding vector.
        vec_b: Second embedding vector.

    Returns:
        Cosine similarity in [-1, 1] (1.0 = identical direction).
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


class FaceMatcher:
    """Loads registered embeddings and matches live faces against them."""

    def __init__(self, registered_faces_dir: Path, similarity_threshold: float = 0.68) -> None:
        """
        Args:
            registered_faces_dir: Root directory containing one sub-folder
                per registered student (see face_registration.py).
            similarity_threshold: Minimum cosine similarity to accept a match.
        """
        self.registered_faces_dir = Path(registered_faces_dir)
        self.similarity_threshold = similarity_threshold
        self._gallery: Dict[str, np.ndarray] = {}
        self.reload_gallery()

    def reload_gallery(self) -> int:
        """(Re)load every registered student's embedding from disk.

        Returns:
            The number of students loaded into the in-memory gallery.
        """
        self._gallery.clear()
        if not self.registered_faces_dir.is_dir():
            return 0
        for student_dir in self.registered_faces_dir.iterdir():
            embedding_path = student_dir / "embedding.npy"
            if student_dir.is_dir() and embedding_path.exists():
                self._gallery[student_dir.name] = np.load(embedding_path)
        logger.info(f"FaceMatcher gallery reloaded -- {len(self._gallery)} student(s) loaded.")
        return len(self._gallery)

    @property
    def gallery_size(self) -> int:
        return len(self._gallery)

    def match(self, live_embedding: np.ndarray) -> MatchResult:
        """Compare a live embedding against every registered student.

        Args:
            live_embedding: (512,) embedding of the face currently in frame.

        Returns:
            A MatchResult naming the best match if it clears the similarity
            threshold, otherwise an "unknown" MatchResult carrying the best
            (sub-threshold) similarity found, for logging/debugging.
        """
        if not self._gallery:
            return MatchResult(student_id=UNKNOWN_LABEL, confidence=0.0, matched=False)

        best_student, best_score = UNKNOWN_LABEL, -1.0
        for student_id, ref_embedding in self._gallery.items():
            score = cosine_similarity(live_embedding, ref_embedding)
            if score > best_score:
                best_student, best_score = student_id, score

        matched = best_score >= self.similarity_threshold
        result = MatchResult(
            student_id=best_student if matched else UNKNOWN_LABEL,
            confidence=round(best_score, 4),
            matched=matched,
        )
        logger.debug(f"Match result: {result}")
        return result
