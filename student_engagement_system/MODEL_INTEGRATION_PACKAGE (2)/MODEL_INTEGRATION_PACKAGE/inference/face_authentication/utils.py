"""
ml/training/face_authentication/utils.py
==========================================
Reusable, stateless utility functions for the Face Authentication
module: logging setup, face detection/alignment/preprocessing,
duplicate detection, corrupted-image filtering, and small I/O helpers.

No model-loading or embedding-generation code lives here (see
embedding_model.py) - this module is pure image/data plumbing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np

import config as face_auth_config


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    """Return a module-local logger writing to both stdout and a
    rotating file under `config.LOG_DIR`. Safe to call multiple times
    (handlers are only attached once per logger name).
    """
    logger = logging.getLogger(f"face_authentication.{name}")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, face_auth_config.LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler(
        filename=str(face_auth_config.LOG_DIR / "face_authentication.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class FaceAuthError(Exception):
    """Base exception for all Face Authentication module errors."""


class NoFaceDetectedError(FaceAuthError):
    """Raised when zero faces are found in an image where at least one was required."""


class MultipleFacesError(FaceAuthError):
    """Raised when more than one face is found but exactly one was required
    (e.g. during single-student enrollment capture with
    ENFORCE_SINGLE_FACE_ON_ENROLLMENT=True).
    """


class CorruptedImageError(FaceAuthError):
    """Raised when an image file cannot be read or decoded."""


# ---------------------------------------------------------------------------
# Image I/O + validation
# ---------------------------------------------------------------------------
def read_image_bgr(image_path: str | Path) -> np.ndarray:
    """Read an image file into a BGR numpy array (OpenCV convention).
    Raises CorruptedImageError if the file cannot be decoded.
    """
    image_path = Path(image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        raise CorruptedImageError(f"Could not decode image: {image_path}")
    return image


def is_image_corrupted(image_path: str | Path) -> bool:
    """Return True if the image cannot be opened/decoded, or is
    degenerate (zero width/height)."""
    try:
        image = read_image_bgr(image_path)
    except CorruptedImageError:
        return True
    if image.size == 0 or image.shape[0] == 0 or image.shape[1] == 0:
        return True
    return False


def bgr_to_rgb(image_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def resize_image(image: np.ndarray, size: tuple[int, int] = None) -> np.ndarray:
    size = size or face_auth_config.TARGET_IMAGE_SIZE
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def normalize_image(image_rgb: np.ndarray, method: str = None) -> np.ndarray:
    """Normalize a uint8 RGB image (0-255) into the float range expected
    by the active embedding model.

    method:
        "arcface"  -> (pixel - 127.5) / 128.0   range approx [-1, 1]
        "facenet"  -> (pixel - mean) / std (per-image standardization)
        "0_1"      -> pixel / 255.0
        "-1_1"     -> (pixel / 127.5) - 1.0
    """
    method = method or face_auth_config.NORMALIZE_METHOD
    image = image_rgb.astype(np.float32)

    if method == "arcface":
        return (image - 127.5) / 128.0
    if method == "facenet":
        mean = image.mean()
        std = image.std()
        std_adj = max(std, 1.0 / np.sqrt(image.size))
        return (image - mean) / std_adj
    if method == "0_1":
        return image / 255.0
    if method == "-1_1":
        return (image / 127.5) - 1.0

    raise ValueError(f"Unknown normalization method: {method}")


# ---------------------------------------------------------------------------
# Face detection + alignment (thin wrapper around deepface's detector
# backends, which already implement detection + eye-based alignment for
# every backend option exposed in config.FACE_DETECTOR_BACKEND).
# ---------------------------------------------------------------------------
@dataclass
class DetectedFace:
    """A single detected + aligned face, ready for embedding."""
    aligned_face_rgb: np.ndarray     # aligned, cropped face, RGB, TARGET_IMAGE_SIZE
    bounding_box: tuple[int, int, int, int]   # (x, y, w, h) in the ORIGINAL image
    confidence: float
    left_eye: Optional[tuple[int, int]] = None
    right_eye: Optional[tuple[int, int]] = None


def detect_and_align_faces(
    image_bgr: np.ndarray,
    detector_backend: str = None,
    min_confidence: float = None,
    min_face_size_px: int = None,
) -> list[DetectedFace]:
    """
    Detect all faces in an image and return aligned face crops.
    Compatible with DeepFace 0.0.93.
    """
    from deepface import DeepFace

    detector_backend = detector_backend or face_auth_config.FACE_DETECTOR_BACKEND
    min_confidence = (
        min_confidence
        if min_confidence is not None
        else face_auth_config.FACE_DETECTION_CONFIDENCE_THRESHOLD
    )
    min_face_size_px = (
        min_face_size_px
        if min_face_size_px is not None
        else face_auth_config.MIN_FACE_SIZE_PX
    )

    image_rgb = bgr_to_rgb(image_bgr)

    try:
        extracted = DeepFace.extract_faces(
            img_path=image_rgb,
            detector_backend=detector_backend,
            enforce_detection=False,
            align=True,
        )
    except Exception as exc:
        logger.warning(
            "Face extraction raised an exception, treating as no-face: %s",
            exc,
        )
        return []

    results: list[DetectedFace] = []

    for item in extracted:

        confidence = float(item.get("confidence", 0.0))

        if confidence < min_confidence:
            continue

        region = item.get("facial_area", {})

        w = int(region.get("w", 0))
        h = int(region.get("h", 0))

        if w < min_face_size_px or h < min_face_size_px:
            continue

        face_array = item["face"]

        if face_array.dtype != np.uint8:
            face_array = (
                np.clip(face_array, 0.0, 1.0) * 255
            ).astype(np.uint8)

        face_array = resize_image(face_array)

        left_eye = region.get("left_eye")
        right_eye = region.get("right_eye")

        results.append(
            DetectedFace(
                aligned_face_rgb=face_array,
                bounding_box=(
                    int(region.get("x", 0)),
                    int(region.get("y", 0)),
                    w,
                    h,
                ),
                confidence=confidence,
                left_eye=tuple(left_eye) if left_eye else None,
                right_eye=tuple(right_eye) if right_eye else None,
            )
        )

    return results


def detect_single_face(image_bgr: np.ndarray, **kwargs) -> DetectedFace:
    """Convenience wrapper for enrollment flows that require EXACTLY one
    face per image. Raises NoFaceDetectedError / MultipleFacesError.
    """
    faces = detect_and_align_faces(image_bgr, **kwargs)
    if len(faces) == 0:
        raise NoFaceDetectedError("No face detected in image.")
    if len(faces) > 1 and face_auth_config.ENFORCE_SINGLE_FACE_ON_ENROLLMENT:
        raise MultipleFacesError(f"Expected exactly one face, found {len(faces)}.")
    return max(faces, key=lambda f: f.confidence)


# ---------------------------------------------------------------------------
# Duplicate detection (perceptual hashing)
# ---------------------------------------------------------------------------
def compute_average_hash(image_rgb: np.ndarray, hash_size: int = 8) -> np.ndarray:
    """Compute a simple average-hash (aHash) perceptual hash, returned
    as a flattened boolean array. Cheap, dependency-free duplicate
    detection suitable for filtering near-identical enrollment/dataset
    images.
    """
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    avg = small.mean()
    return (small > avg).flatten()


def hamming_distance(hash_a: np.ndarray, hash_b: np.ndarray) -> int:
    return int(np.count_nonzero(hash_a != hash_b))


def find_duplicate_images(
    image_paths: Iterable[str | Path],
    hash_threshold: int = None,
) -> list[tuple[Path, Path]]:
    """Scan a collection of image paths and return pairs considered
    near-duplicates (Hamming distance <= hash_threshold). O(n^2) - fine
    for per-identity folders (tens of images), not intended for
    whole-dataset dedup at LFW scale (use find_duplicate_images per
    identity subfolder instead).
    """
    hash_threshold = hash_threshold if hash_threshold is not None else face_auth_config.DUPLICATE_IMAGE_HASH_THRESHOLD

    hashes: list[tuple[Path, np.ndarray]] = []
    for p in image_paths:
        p = Path(p)
        try:
            image = read_image_bgr(p)
        except CorruptedImageError:
            continue
        hashes.append((p, compute_average_hash(bgr_to_rgb(image))))

    duplicates: list[tuple[Path, Path]] = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            path_a, hash_a = hashes[i]
            path_b, hash_b = hashes[j]
            if hamming_distance(hash_a, hash_b) <= hash_threshold:
                duplicates.append((path_a, path_b))

    return duplicates


def filter_corrupted_images(image_paths: Iterable[str | Path]) -> tuple[list[Path], list[Path]]:
    """Split a list of image paths into (valid, corrupted)."""
    valid, corrupted = [], []
    for p in image_paths:
        p = Path(p)
        if is_image_corrupted(p):
            corrupted.append(p)
        else:
            valid.append(p)
    return valid, corrupted


# ---------------------------------------------------------------------------
# Similarity / matching math
# ---------------------------------------------------------------------------
def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    vec_a = vec_a.flatten().astype(np.float64)
    vec_b = vec_b.flatten().astype(np.float64)
    denom = (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
    if denom == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / denom)


def euclidean_distance(vec_a: np.ndarray, vec_b: np.ndarray, l2_normalize: bool = False) -> float:
    vec_a = vec_a.flatten().astype(np.float64)
    vec_b = vec_b.flatten().astype(np.float64)
    if l2_normalize:
        vec_a = vec_a / (np.linalg.norm(vec_a) + 1e-10)
        vec_b = vec_b / (np.linalg.norm(vec_b) + 1e-10)
    return float(np.linalg.norm(vec_a - vec_b))


def similarity_to_confidence(
    similarity: float,
    low_bound: float = None,
    high_bound: float = None,
) -> float:
    """Linearly rescale a cosine similarity score into a [0, 1]
    confidence value using the configured low/high bounds, clipped.
    """
    low_bound = low_bound if low_bound is not None else face_auth_config.CONFIDENCE_LOW_SIMILARITY_BOUND
    high_bound = high_bound if high_bound is not None else face_auth_config.CONFIDENCE_HIGH_SIMILARITY_BOUND

    if high_bound <= low_bound:
        raise ValueError("high_bound must be greater than low_bound")

    confidence = (similarity - low_bound) / (high_bound - low_bound)
    return float(np.clip(confidence, 0.0, 1.0))


def aggregate_embeddings(embeddings: list[np.ndarray], method: str = None) -> np.ndarray:
    """Aggregate multiple per-image embeddings captured during
    enrollment into a single representative embedding for a student.
    """
    method = method or face_auth_config.ENROLLMENT_EMBEDDING_AGGREGATION
    stacked = np.stack([e.flatten() for e in embeddings], axis=0)

    if method == "mean":
        return stacked.mean(axis=0)
    if method == "median":
        return np.median(stacked, axis=0)
    raise ValueError(f"Unknown aggregation method: {method}")


# ---------------------------------------------------------------------------
# Misc I/O helpers
# ---------------------------------------------------------------------------
def sha256_of_file(path: str | Path) -> str:
    """Content hash, used to detect byte-identical duplicate files
    (complements the perceptual hash, which catches near-duplicates)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(data: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dataclass_to_dict(obj) -> dict:
    return asdict(obj)


def draw_face_annotation(
    image_bgr: np.ndarray,
    bounding_box: tuple[int, int, int, int],
    label: str,
    color: tuple[int, int, int] = (0, 200, 0),
) -> np.ndarray:
    """Draw a bounding box + text label on a BGR image (used by the
    webcam authentication loop in inference.ipynb / predictor.py).
    Returns a new array; does not mutate the input in place.
    """
    annotated = image_bgr.copy()
    x, y, w, h = bounding_box
    cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
    text_y = max(y - 10, 15)
    cv2.putText(
        annotated, label, (x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA,
    )
    return annotated
