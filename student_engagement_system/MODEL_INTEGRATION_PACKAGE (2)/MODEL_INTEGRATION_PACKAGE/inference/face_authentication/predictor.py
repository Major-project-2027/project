"""
ml/training/face_authentication/predictor.py
================================================
Real-time and batch face-authentication inference.

Pipeline (per project requirements):
    Webcam/Image -> Face Detection -> Face Alignment -> Embedding ->
    Cosine Similarity (vs. registered students) -> Identity ->
    Confidence -> Accept / Reject

Supports:
    - single image authentication
    - batch image authentication
    - live webcam authentication (multi-person, with lightweight
      IOU-based face tracking so each visible face keeps a stable
      track ID across frames)
    - unknown-person rejection via the calibrated cosine-similarity
      threshold from config.load_calibrated_threshold()

This module contains no training/calibration logic (see trainer.py)
and no notebook-only exploratory code - it is the reusable inference
engine that both notebooks and (eventually) the backend's face-auth
service call into.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

import config as face_auth_config
from embedding_model import EmbeddingResult, FaceEmbeddingModel, get_default_embedding_model
from utils import (
    DetectedFace,
    cosine_similarity,
    detect_and_align_faces,
    draw_face_annotation,
    euclidean_distance,
    get_logger,
    load_json,
    read_image_bgr,
    similarity_to_confidence,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class AuthenticationResult:
    """Result of matching one detected face against the registered
    student embedding gallery.
    """
    is_known: bool
    student_id: Optional[str]
    student_name: Optional[str]
    similarity_score: float
    confidence: float
    bounding_box: tuple[int, int, int, int]
    detection_confidence: float
    accepted: bool
    threshold_used: float


@dataclass
class FrameAuthenticationResult:
    """Result of running authentication on one full frame, which may
    contain zero, one, or multiple faces.
    """
    results: list[AuthenticationResult] = field(default_factory=list)
    frame_timestamp: float = field(default_factory=time.time)

    @property
    def known_count(self) -> int:
        return sum(1 for r in self.results if r.is_known and r.accepted)

    @property
    def unknown_count(self) -> int:
        return sum(1 for r in self.results if not (r.is_known and r.accepted))


# ---------------------------------------------------------------------------
# Student embedding gallery
# ---------------------------------------------------------------------------
class StudentGallery:
    """In-memory representation of all registered students' embeddings,
    loaded from config.STUDENT_REGISTRY_FILE (written by
    register_faces.ipynb). Provides nearest-neighbor matching.
    """

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or face_auth_config.STUDENT_REGISTRY_FILE
        self.student_ids: list[str] = []
        self.student_names: list[str] = []
        self.embeddings: np.ndarray = np.zeros((0, face_auth_config.get_active_embedding_dim()), dtype=np.float32)
        self.reload()

    def reload(self) -> None:
        """(Re)load the gallery from disk. Safe to call if the file
        does not exist yet (gallery starts empty - every face will be
        classified as unknown until at least one student is registered).
        """
        if not self.registry_path.exists():
            logger.warning("Student registry not found at %s - gallery is empty.", self.registry_path)
            self.student_ids, self.student_names = [], []
            self.embeddings = np.zeros((0, face_auth_config.get_active_embedding_dim()), dtype=np.float32)
            return

        registry = load_json(self.registry_path)
        students = registry.get("students", [])

        ids, names, vectors = [], [], []
        for entry in students:
            ids.append(entry["student_id"])
            names.append(entry["student_name"])
            vectors.append(np.array(entry["embedding"], dtype=np.float32))

        self.student_ids = ids
        self.student_names = names
        self.embeddings = np.stack(vectors, axis=0) if vectors else np.zeros(
            (0, face_auth_config.get_active_embedding_dim()), dtype=np.float32
        )
        logger.info("Loaded %d registered students from %s", len(ids), self.registry_path)

    def __len__(self) -> int:
        return len(self.student_ids)

    def find_best_match(self, embedding: np.ndarray, metric: str = None) -> tuple[Optional[int], float]:
        """Return (best_index, best_score) against every registered
        student, or (None, -inf) if the gallery is empty. `best_score`
        is a similarity-like value (higher = more similar) regardless
        of the underlying metric, so callers can compare it against a
        single threshold uniformly.
        """
        metric = metric or face_auth_config.SIMILARITY_METRIC

        if len(self) == 0:
            return None, float("-inf")

        if metric == "cosine":
            scores = np.array([cosine_similarity(embedding, e) for e in self.embeddings])
        elif metric in ("euclidean", "euclidean_l2"):
            scores = np.array([
                -euclidean_distance(embedding, e, l2_normalize=(metric == "euclidean_l2"))
                for e in self.embeddings
            ])
        else:
            raise ValueError(f"Unknown similarity metric: {metric}")

        best_index = int(np.argmax(scores))
        return best_index, float(scores[best_index])


# ---------------------------------------------------------------------------
# Core predictor
# ---------------------------------------------------------------------------
class FaceAuthenticator:
    """High-level authentication engine tying together detection,
    embedding, and gallery matching.
    """

    def __init__(
        self,
        embedding_model: Optional[FaceEmbeddingModel] = None,
        gallery: Optional[StudentGallery] = None,
        similarity_threshold: Optional[float] = None,
    ):
        self.embedding_model = embedding_model or get_default_embedding_model()
        self.gallery = gallery or StudentGallery()
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else face_auth_config.load_calibrated_threshold()
        )

    def _match_face(self, detected: DetectedFace) -> AuthenticationResult:
        embedding_result: EmbeddingResult = self.embedding_model.embed_face(detected)
        best_index, best_score = self.gallery.find_best_match(embedding_result.embedding)

        accepted = best_index is not None and best_score >= self.similarity_threshold
        confidence = similarity_to_confidence(best_score) if best_index is not None else 0.0

        return AuthenticationResult(
            is_known=best_index is not None,
            student_id=self.gallery.student_ids[best_index] if accepted else None,
            student_name=self.gallery.student_names[best_index] if accepted else None,
            similarity_score=best_score,
            confidence=confidence,
            bounding_box=detected.bounding_box,
            detection_confidence=detected.confidence,
            accepted=accepted,
            threshold_used=self.similarity_threshold,
        )

    # ------------------------------------------------------------------
    # Single image
    # ------------------------------------------------------------------
    def authenticate_image(self, image_bgr: np.ndarray) -> FrameAuthenticationResult:
        """Authenticate every face found in a single image (supports
        multi-person authentication automatically per
        config.MULTI_PERSON_AUTH_ENABLED).
        """
        faces = detect_and_align_faces(image_bgr)
        if not face_auth_config.MULTI_PERSON_AUTH_ENABLED and len(faces) > 1:
            faces = [max(faces, key=lambda f: f.confidence)]

        results = [self._match_face(f) for f in faces]
        return FrameAuthenticationResult(results=results)

    def authenticate_image_path(self, image_path: str | Path) -> FrameAuthenticationResult:
        image_bgr = read_image_bgr(image_path)
        return self.authenticate_image(image_bgr)

    # ------------------------------------------------------------------
    # Batch images
    # ------------------------------------------------------------------
    def authenticate_batch(self, image_paths: list[str | Path]) -> dict[str, FrameAuthenticationResult]:
        """Authenticate a batch of image files. Returns a mapping of
        (string) path -> FrameAuthenticationResult. Errors on
        individual images are logged and skipped rather than aborting
        the whole batch.
        """
        results: dict[str, FrameAuthenticationResult] = {}
        for path in image_paths:
            path = Path(path)
            try:
                results[str(path)] = self.authenticate_image_path(path)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to authenticate %s: %s", path, exc)
                results[str(path)] = FrameAuthenticationResult(results=[])
        return results

    # ------------------------------------------------------------------
    # Annotated visualization
    # ------------------------------------------------------------------
    def annotate_frame(self, image_bgr: np.ndarray, frame_result: FrameAuthenticationResult) -> np.ndarray:
        annotated = image_bgr
        for result in frame_result.results:
            if result.accepted:
                label = f"{result.student_name} ({result.confidence:.0%})"
                color = (0, 200, 0)
            else:
                label = f"Unknown ({result.similarity_score:.2f})"
                color = (0, 0, 220)
            annotated = draw_face_annotation(annotated, result.bounding_box, label, color)
        return annotated


# ---------------------------------------------------------------------------
# Lightweight IOU-based multi-face tracker for webcam sessions
# ---------------------------------------------------------------------------
def _iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1, inter_y1 = max(ax, bx), max(ay, by)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a, area_b = aw * ah, bw * bh
    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


@dataclass
class TrackedFace:
    track_id: int
    bounding_box: tuple[int, int, int, int]
    last_result: Optional[AuthenticationResult]
    frames_since_seen: int = 0


class FaceTracker:
    """Minimal IOU-based multi-object tracker so that a webcam
    authentication session can maintain stable track IDs per visible
    face across frames, re-authenticating periodically rather than on
    every single frame (see config.WEBCAM_AUTH_SAMPLING_INTERVAL_SECONDS).
    """

    def __init__(
        self,
        iou_threshold: float = None,
        max_disappeared_frames: int = None,
    ):
        self.iou_threshold = iou_threshold or face_auth_config.FACE_TRACKING_IOU_MATCH_THRESHOLD
        self.max_disappeared_frames = (
            max_disappeared_frames or face_auth_config.FACE_TRACKING_MAX_DISAPPEARED_FRAMES
        )
        self._tracks: dict[int, TrackedFace] = {}
        self._next_id = 1

    def update(self, detections: list[AuthenticationResult]) -> list[TrackedFace]:
        unmatched_detections = list(range(len(detections)))
        matched_track_ids: set[int] = set()

        for track_id, track in list(self._tracks.items()):
            best_iou, best_det_idx = 0.0, None
            for det_idx in unmatched_detections:
                score = _iou(track.bounding_box, detections[det_idx].bounding_box)
                if score > best_iou:
                    best_iou, best_det_idx = score, det_idx

            if best_det_idx is not None and best_iou >= self.iou_threshold:
                detection = detections[best_det_idx]
                track.bounding_box = detection.bounding_box
                track.last_result = detection
                track.frames_since_seen = 0
                matched_track_ids.add(track_id)
                unmatched_detections.remove(best_det_idx)
            else:
                track.frames_since_seen += 1

        # Create new tracks for unmatched detections.
        for det_idx in unmatched_detections:
            detection = detections[det_idx]
            new_id = self._next_id
            self._next_id += 1
            self._tracks[new_id] = TrackedFace(
                track_id=new_id,
                bounding_box=detection.bounding_box,
                last_result=detection,
                frames_since_seen=0,
            )

        # Drop stale tracks.
        stale_ids = [
            tid for tid, t in self._tracks.items()
            if t.frames_since_seen > self.max_disappeared_frames
        ]
        for tid in stale_ids:
            del self._tracks[tid]

        return list(self._tracks.values())


# ---------------------------------------------------------------------------
# Live webcam authentication loop
# ---------------------------------------------------------------------------
def run_webcam_authentication(
    authenticator: Optional[FaceAuthenticator] = None,
    device_index: int = None,
    display_window: bool = True,
    max_frames: Optional[int] = None,
) -> None:
    """Run a live webcam authentication loop. Displays an annotated
    video feed (unless `display_window=False`, e.g. in a headless CI
    environment) and prints authentication events to the logger.

    This function blocks until the window is closed ('q' key) or
    `max_frames` is reached. It is intended to be called from
    inference.ipynb, not imported into a web server request path
    (the backend's real-time pipeline instead streams sampled frames
    over WebSocket per the architecture document, and would call
    `FaceAuthenticator.authenticate_image` per-frame directly).
    """
    authenticator = authenticator or FaceAuthenticator()
    device_index = device_index if device_index is not None else face_auth_config.WEBCAM_DEVICE_INDEX

    cap = cv2.VideoCapture(device_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, face_auth_config.WEBCAM_FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, face_auth_config.WEBCAM_FRAME_HEIGHT)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam device index {device_index}")

    tracker = FaceTracker()
    frame_count = 0
    last_auth_time = 0.0

    logger.info("Starting webcam authentication loop (press 'q' to quit)")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame from webcam; stopping.")
                break

            now = time.time()
            if now - last_auth_time >= face_auth_config.WEBCAM_AUTH_SAMPLING_INTERVAL_SECONDS:
                frame_result = authenticator.authenticate_image(frame)
                tracker.update(frame_result.results)
                last_auth_time = now

                for result in frame_result.results:
                    status = "ACCEPTED" if result.accepted else "REJECTED (unknown)"
                    logger.info(
                        "Face @ %s -> %s | similarity=%.3f confidence=%.2f",
                        result.bounding_box, status, result.similarity_score, result.confidence,
                    )

                annotated = authenticator.annotate_frame(frame, frame_result)
            else:
                annotated = frame

            if display_window:
                cv2.imshow("Face Authentication", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_count += 1
            if max_frames is not None and frame_count >= max_frames:
                break
    finally:
        cap.release()
        if display_window:
            cv2.destroyAllWindows()
        logger.info("Webcam authentication loop stopped after %d frames", frame_count)
