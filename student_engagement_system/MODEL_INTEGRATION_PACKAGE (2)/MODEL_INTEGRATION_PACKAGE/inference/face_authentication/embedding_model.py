"""
ml/training/face_authentication/embedding_model.py
=====================================================
Production face-embedding model wrapper.

Per project requirements, this module uses a strong PRETRAINED,
FROZEN embedding model rather than training a CNN from scratch. The
preferred model order is:

    1. ArcFace        (512-D, state-of-the-art angular-margin loss)
    2. FaceNet512      (512-D, triplet-loss embedding)
    3. MobileFaceNet    (512-D, lightweight, edge-friendly)

All three are exposed as pretrained, TensorFlow-backed models via the
`deepface` library, which downloads and caches the appropriate
architecture + weights on first use. This wrapper adds:
    - a stable, typed interface independent of `deepface`'s internal API
    - batch embedding generation
    - automatic fallback through the model priority list if the
      preferred backend is unavailable in the current environment
    - L2-normalization control (required for meaningful cosine
      similarity comparisons)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

import config as face_auth_config
from utils import DetectedFace, detect_and_align_faces, get_logger, normalize_image

logger = get_logger(__name__)


class EmbeddingModelUnavailableError(Exception):
    """Raised when no embedding model in the priority list can be loaded
    in the current environment (e.g. missing TensorFlow / deepface).
    """


@dataclass
class EmbeddingResult:
    """A single face's embedding plus provenance metadata."""
    embedding: np.ndarray
    model_name: str
    embedding_dim: int
    detection_confidence: float
    bounding_box: tuple[int, int, int, int]


class FaceEmbeddingModel:
    """Loads and serves a single pretrained face-embedding model.

    Usage:
        model = FaceEmbeddingModel()  # uses config.ACTIVE_EMBEDDING_MODEL
        result = model.embed_face(detected_face)
        results = model.embed_faces(list_of_detected_faces)
    """

    def __init__(self, model_name: Optional[str] = None, l2_normalize: bool = True):
        self.requested_model_name = model_name or face_auth_config.ACTIVE_EMBEDDING_MODEL
        self.l2_normalize = l2_normalize
        self.model_name: str = self._load_with_fallback()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def _load_with_fallback(self) -> str:
        """Try the requested model first, then fall back through
        config.EMBEDDING_MODEL_PRIORITY (ArcFace -> Facenet512 ->
        Facenet) if it cannot be built in this environment. Raises
        EmbeddingModelUnavailableError only if every candidate fails.
        """
        from deepface import DeepFace
        from deepface.modules import modeling

        candidates = [self.requested_model_name] + [
            m for m in face_auth_config.EMBEDDING_MODEL_PRIORITY if m != self.requested_model_name
        ]

        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                # DeepFace lazily builds + caches the model graph on first
                # call; `build_model` triggers (and validates) that here.
                modeling.build_model(task="facial_recognition", model_name=candidate)
                logger.info("Loaded face embedding model: %s", candidate)
                self._deepface = DeepFace
                return candidate
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding model '%s' failed to load: %s", candidate, exc)
                last_error = exc
                continue

        raise EmbeddingModelUnavailableError(
            f"None of the candidate embedding models could be loaded: {candidates}"
        ) from last_error

    @property
    def embedding_dim(self) -> int:
        return face_auth_config.EMBEDDING_DIMENSIONS.get(self.model_name, 512)

    # ------------------------------------------------------------------
    # Embedding generation
    # ------------------------------------------------------------------
    def embed_face(self, face: DetectedFace) -> EmbeddingResult:
        """Generate a single embedding for an already-detected, aligned
        face crop (RGB, uint8, TARGET_IMAGE_SIZE).
        """
        from deepface import DeepFace

        representations = DeepFace.represent(
            img_path=face.aligned_face_rgb,
            model_name=self.model_name,
            detector_backend="skip",   # already detected + aligned upstream
            enforce_detection=False,
            align=False,
            normalization="base" if self.model_name == "ArcFace" else "base",
        )
        if not representations:
            raise ValueError("Embedding model returned no representation for the given face.")

        embedding = np.array(representations[0]["embedding"], dtype=np.float32)
        if self.l2_normalize:
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

        return EmbeddingResult(
            embedding=embedding,
            model_name=self.model_name,
            embedding_dim=embedding.shape[0],
            detection_confidence=face.confidence,
            bounding_box=face.bounding_box,
        )

    def embed_faces(self, faces: list[DetectedFace]) -> list[EmbeddingResult]:
        return [self.embed_face(f) for f in faces]

    def embed_image(self, image_bgr: np.ndarray) -> list[EmbeddingResult]:
        """Convenience method: detect all faces in a raw image AND embed
        them in one call. Used by predictor.py's multi-person
        authentication path.
        """
        faces = detect_and_align_faces(image_bgr)
        return self.embed_faces(faces)

    def embed_single_face_image(self, image_bgr: np.ndarray):
        """Convenience method for enrollment: detect+embed exactly one
        face, raising if zero or multiple faces are found (per
        config.ENFORCE_SINGLE_FACE_ON_ENROLLMENT).
        """
        from utils import detect_single_face

        face = detect_single_face(image_bgr)
        return self.embed_face(face)


@lru_cache(maxsize=1)
def get_default_embedding_model() -> FaceEmbeddingModel:
    """Process-wide cached singleton, so notebooks/scripts don't reload
    the (potentially large) TensorFlow graph on every call.
    """
    return FaceEmbeddingModel()
