"""
Face registration (student enrollment) module.
"""
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np

from ml_models.face_authentication.face_detector import FaceDetector
from ml_models.face_authentication.face_embedder import FaceEmbedder, average_embedding
from ml_models.face_authentication.preprocessing import check_quality, preprocess_face
from ml_models.face_authentication.webcam import WebcamStream
from utils.image_utils import save_image
from utils.logger import get_logger

logger = get_logger(__name__)

REQUIRED_IMAGE_COUNT = 10


@dataclass
class StudentMetadata:
    """Metadata persisted alongside a registered student's embedding."""
    student_id: str
    name: str
    department: str
    semester: str
    section: str
    registered_at: str
    num_images_used: int


class RegistrationError(Exception):
    """Raised when registration cannot be completed successfully."""


class FaceRegistrar:
    """Registers new students by capturing webcam images and storing a
    reference face embedding.
    """

    def __init__(self, registered_faces_dir: Path, detector: Optional[FaceDetector] = None,
                 embedder: Optional[FaceEmbedder] = None, camera_index: int = 0) -> None:
        self.registered_faces_dir = Path(registered_faces_dir)
        self.registered_faces_dir.mkdir(parents=True, exist_ok=True)
        self.detector = detector or FaceDetector(min_confidence=0.6)
        self.embedder = embedder  # lazily created on first use if None (needs DeepFace)
        self.camera_index = camera_index

    def _get_embedder(self) -> FaceEmbedder:
        if self.embedder is None:
            self.embedder = FaceEmbedder()
        return self.embedder

    def capture_images(self, num_images: int = REQUIRED_IMAGE_COUNT,
                        max_attempts_per_image: int = 30) -> List[np.ndarray]:
        """Capture ``num_images`` good-quality face crops from the webcam.

        Args:
            num_images: Number of accepted face crops to collect.
            max_attempts_per_image: Frames to try before giving up on one slot.

        Returns:
            List of raw (un-preprocessed) BGR face crops that passed quality gates.

        Raises:
            RegistrationError: If the webcam or detector cannot supply enough
                acceptable frames.
        """
        captured: List[np.ndarray] = []
        with WebcamStream(device_index=self.camera_index) as cam:
            while len(captured) < num_images:
                accepted_this_slot = False
                for _ in range(max_attempts_per_image):
                    frame = cam.read_frame()
                    faces = self.detector.detect(frame)
                    if len(faces) != 1:
                        continue  # require exactly one face in frame during enrollment
                    report = check_quality(faces[0].cropped_face)
                    if report.passed:
                        captured.append(faces[0].cropped_face)
                        accepted_this_slot = True
                        break
                if not accepted_this_slot:
                    raise RegistrationError(
                        f"Could not capture an acceptable frame for image "
                        f"{len(captured) + 1}/{num_images} after {max_attempts_per_image} attempts."
                    )
        logger.info(f"Captured {len(captured)} acceptable face images for registration.")
        return captured

    def register_from_images(self, student_id: str, name: str, department: str,
                              semester: str, section: str,
                              face_crops: List[np.ndarray]) -> StudentMetadata:
        """Register a student from a list of already-captured face crops.

        This is the pure, testable core of registration -- it never touches
        the webcam, so it can be exercised with synthetic images in tests.

        Args:
            student_id: Unique student identifier.
            name: Student full name.
            department: Department name.
            semester: Semester label.
            section: Section label.
            face_crops: List of raw BGR face crop images (any count >= 1).

        Returns:
            The StudentMetadata that was persisted.

        Raises:
            RegistrationError: If no face crops are provided.
        """
        if not face_crops:
            raise RegistrationError("At least one face image is required for registration.")

        embedder = self._get_embedder()
        processed = [preprocess_face(crop, target_size=(224, 224)) for crop in face_crops]
        embeddings = embedder.embed_batch(processed)
        reference_embedding = average_embedding(embeddings)

        student_dir = self.registered_faces_dir / student_id
        student_dir.mkdir(parents=True, exist_ok=True)

        np.save(student_dir / "embedding.npy", reference_embedding)
        save_image(face_crops[0], student_dir / "photo.jpg")

        metadata = StudentMetadata(
            student_id=student_id, name=name, department=department, semester=semester,
            section=section, registered_at=datetime.utcnow().isoformat(),
            num_images_used=len(face_crops),
        )
        with open(student_dir / "metadata.json", "w") as f:
            json.dump(asdict(metadata), f, indent=2)

        logger.info(f"Registered student {student_id} ({name}) using {len(face_crops)} image(s).")
        return metadata

    def register_live(self, student_id: str, name: str, department: str, semester: str,
                       section: str, num_images: int = REQUIRED_IMAGE_COUNT) -> StudentMetadata:
        """Full live-webcam registration flow: capture + register in one call.

        Args:
            student_id, name, department, semester, section: Student metadata.
            num_images: Number of webcam images to capture (default 10).

        Returns:
            The persisted StudentMetadata.
        """
        face_crops = self.capture_images(num_images=num_images)
        return self.register_from_images(student_id, name, department, semester, section, face_crops)


def is_student_registered(registered_faces_dir: Path, student_id: str) -> bool:
    """Check whether a student already has a stored embedding.

    Args:
        registered_faces_dir: Root registered_faces/ directory.
        student_id: Student identifier to check.

    Returns:
        True if embedding.npy exists for this student.
    """
    return (Path(registered_faces_dir) / student_id / "embedding.npy").exists()
