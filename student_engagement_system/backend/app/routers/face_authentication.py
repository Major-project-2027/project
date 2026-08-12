"""
Face Authentication & Attendance router.
"""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml_models.face_authentication.attendance_database import AttendanceCSVStore
from ml_models.face_authentication.attendance_manager import AttendanceManager, DuplicateAttendanceError
from ml_models.face_authentication.face_matcher import FaceMatcher
from ml_models.face_authentication.face_registration import FaceRegistrar, RegistrationError
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/face-auth", tags=["face-authentication"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REGISTERED_FACES_DIR = _PROJECT_ROOT / "models" / "face_authentication" / "registered_faces"
_ATTENDANCE_CSV = _PROJECT_ROOT / "models" / "face_authentication" / "attendance_logs" / "attendance.csv"

# NOTE: FaceRegistrar/FaceMatcher construct a FaceDetector, which initializes a
# MediaPipe backend (and may need to download a model asset on first use). We
# deliberately do NOT construct them at import time -- a slow download or a
# missing backend must never crash the whole API on startup. Instead they are
# created lazily, on first actual use, and cached thereafter.
_registrar: Optional[FaceRegistrar] = None
_matcher: Optional[FaceMatcher] = None
_attendance_manager: Optional[AttendanceManager] = None


def _get_registrar() -> FaceRegistrar:
    global _registrar
    if _registrar is None:
        _registrar = FaceRegistrar(registered_faces_dir=_REGISTERED_FACES_DIR)
    return _registrar


def _get_matcher() -> FaceMatcher:
    global _matcher
    if _matcher is None:
        _matcher = FaceMatcher(registered_faces_dir=_REGISTERED_FACES_DIR)
    return _matcher


def _get_attendance_manager() -> AttendanceManager:
    global _attendance_manager
    if _attendance_manager is None:
        _attendance_manager = AttendanceManager(csv_path=_ATTENDANCE_CSV)
    return _attendance_manager


class RegisterRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    name: str
    department: str
    semester: str
    section: str
    face_crops_b64: Optional[List[str]] = Field(
        None, description="Base64-encoded JPEG face crops (>=1). Omitted in this API "
                           "stub for synthetic/test registration via /register/test."
    )


class RegisterResponse(BaseModel):
    student_id: str
    name: str
    num_images_used: int
    registered_at: str


class AuthenticateRequest(BaseModel):
    embedding: List[float] = Field(..., min_length=512, max_length=512)


class AuthenticateResponse(BaseModel):
    student_id: str
    confidence: float
    matched: bool


class AttendanceRequest(BaseModel):
    student_id: str
    name: str
    confidence: float
    allow_duplicate: bool = False


class AttendanceResponse(BaseModel):
    student_id: str
    name: str
    date: str
    time: str
    confidence: float
    present: bool


def _decode_b64_images(face_crops_b64: List[str]):
    """Decode a list of base64 JPEG strings into BGR NumPy arrays."""
    import base64
    import cv2
    import numpy as np

    images = []
    for b64_string in face_crops_b64:
        raw_bytes = base64.b64decode(b64_string)
        array = np.frombuffer(raw_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is not None:
            images.append(image)
    return images


@router.post("/register", response_model=RegisterResponse)
async def register_student(payload: RegisterRequest) -> RegisterResponse:
    """Register a new student from base64-encoded face crop images."""
    if not payload.face_crops_b64:
        raise HTTPException(status_code=400, detail="face_crops_b64 must contain at least one image.")
    images = _decode_b64_images(payload.face_crops_b64)
    if not images:
        raise HTTPException(status_code=400, detail="No valid images could be decoded.")
    try:
        registrar = _get_registrar()
        metadata = registrar.register_from_images(
            student_id=payload.student_id, name=payload.name, department=payload.department,
            semester=payload.semester, section=payload.section, face_crops=images,
        )
    except RegistrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Face detection backend unavailable: {exc}") from exc
    _get_matcher().reload_gallery()
    return RegisterResponse(student_id=metadata.student_id, name=metadata.name,
                             num_images_used=metadata.num_images_used, registered_at=metadata.registered_at)


@router.post("/authenticate", response_model=AuthenticateResponse)
async def authenticate(payload: AuthenticateRequest) -> AuthenticateResponse:
    """Match a 512-D embedding against the registered gallery."""
    import numpy as np
    result = _get_matcher().match(np.asarray(payload.embedding, dtype=np.float32))
    return AuthenticateResponse(student_id=result.student_id, confidence=result.confidence, matched=result.matched)


@router.post("/attendance", response_model=AttendanceResponse)
async def mark_attendance(payload: AttendanceRequest) -> AttendanceResponse:
    """Mark attendance for a student, rejecting same-day duplicates unless overridden."""
    try:
        entry = _get_attendance_manager().mark_attendance(
            student_id=payload.student_id, name=payload.name, confidence=payload.confidence,
            allow_duplicate=payload.allow_duplicate,
        )
    except DuplicateAttendanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AttendanceResponse(**entry.__dict__)


@router.get("/students")
async def list_students() -> List[dict]:
    """List every registered student's metadata."""
    import json
    students = []
    if _REGISTERED_FACES_DIR.is_dir():
        for student_dir in _REGISTERED_FACES_DIR.iterdir():
            metadata_path = student_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    students.append(json.load(f))
    return students


@router.get("/attendance", response_model=List[AttendanceResponse])
async def list_attendance() -> List[AttendanceResponse]:
    """List every attendance record currently stored."""
    store = AttendanceCSVStore(_ATTENDANCE_CSV)
    return [AttendanceResponse(**e.__dict__) for e in store.read_all()]
