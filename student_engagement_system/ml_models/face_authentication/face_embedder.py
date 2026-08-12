"""
Face embedding module built on DeepFace (Facenet512 backbone).
"""
from typing import Optional

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 512


class EmbeddingError(Exception):
    """Raised when an embedding could not be generated for a face image."""


class FaceEmbedder:
    """Generates 512-D Facenet512 embeddings for preprocessed face images.

    DeepFace is imported lazily inside __init__ so that modules which do
    not need embeddings (e.g. webcam.py, face_detector.py) never pay the
    TensorFlow/DeepFace import cost.
    """

    def __init__(self, model_name: str = "Facenet512") -> None:
        """
        Args:
            model_name: DeepFace backbone name. Facenet512 outputs a
                512-dimensional embedding, matching EMBEDDING_DIM.
        """
        try:
            from deepface import DeepFace  # noqa: WPS433 -- deliberate lazy import
        except ImportError as exc:
            raise EmbeddingError(
                "DeepFace is not installed. Run `pip install deepface tensorflow` "
                "(see Phase 1 Section 4 special-installation notes)."
            ) from exc

        self._DeepFace = DeepFace
        self.model_name = model_name
        # Trigger a one-time model build/download so later calls are fast.
        self._DeepFace.build_model(model_name)
        logger.info(f"FaceEmbedder ready -- backbone={model_name}")

    def embed(self, face_rgb_0_1: np.ndarray) -> np.ndarray:
        """Generate a 512-D embedding for a single preprocessed face.

        Args:
            face_rgb_0_1: RGB float32 array in [0, 1], as returned by
                preprocessing.preprocess_face().

        Returns:
            A (512,) float32 NumPy embedding vector.

        Raises:
            EmbeddingError: If DeepFace fails to produce an embedding.
        """
        face_uint8 = (face_rgb_0_1 * 255.0).astype(np.uint8)
        try:
            result = self._DeepFace.represent(
                img_path=face_uint8,
                model_name=self.model_name,
                enforce_detection=False,  # we already ran our own MediaPipe detector
                detector_backend="skip",
            )
        except Exception as exc:  # noqa: BLE001 -- DeepFace raises assorted exception types
            raise EmbeddingError(f"DeepFace failed to generate an embedding: {exc}") from exc

        if not result:
            raise EmbeddingError("DeepFace returned no embedding for the given face.")

        embedding = np.asarray(result[0]["embedding"], dtype=np.float32)
        if embedding.shape[0] != EMBEDDING_DIM:
            raise EmbeddingError(
                f"Unexpected embedding dimension {embedding.shape[0]}, expected {EMBEDDING_DIM}."
            )
        return embedding

    def embed_batch(self, faces_rgb_0_1: list) -> np.ndarray:
        """Embed a list of preprocessed faces (e.g. the 10 registration images).

        Args:
            faces_rgb_0_1: List of RGB float32 [0, 1] face arrays.

        Returns:
            A (N, 512) float32 array of embeddings.
        """
        embeddings = [self.embed(face) for face in faces_rgb_0_1]
        return np.stack(embeddings, axis=0)


def average_embedding(embeddings: np.ndarray) -> np.ndarray:
    """Average multiple embeddings of the same person into one reference vector.

    Args:
        embeddings: (N, 512) array of embeddings from N images of one person.

    Returns:
        A single (512,) averaged and L2-normalized embedding.
    """
    mean_vec = embeddings.mean(axis=0)
    norm = np.linalg.norm(mean_vec)
    return mean_vec / norm if norm > 0 else mean_vec
