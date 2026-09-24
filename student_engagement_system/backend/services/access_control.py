"""Server-side authorization shared by the Flask API and the FastAPI
classroom/AI service.

Identity always comes from the verified JWT (user_id + role) -- never
from a URL, request body, or WebSocket message. A class's enrollment
rows are its allowed-student list: the class's teacher grants them
(see EnrollmentService.set_allowed_students); students can no longer
enroll themselves. A class with no enrollments admits no students.
"""

from repositories.active import (
    ClassroomRepository,
    EnrollmentRepository,
    SessionRepository,
    StudentRepository,
    TeacherRepository,
)

NOT_AUTHORIZED_TO_JOIN = "You are not authorized to join this class."


class Unauthenticated(Exception):
    """No / invalid / expired token -> HTTP 401."""


class AccessDenied(Exception):
    """Authenticated, but not allowed -> HTTP 403."""


def payload_from_token(token):
    from services.jwt_service import JWTService

    if not token:
        raise Unauthenticated("Authorization token missing.")
    try:
        return JWTService.verify_token(token)
    except Exception as exc:  # expired / bad signature / malformed
        raise Unauthenticated(f"Invalid or expired token: {exc}") from exc


def payload_from_auth_header(header):
    if not header or " " not in header:
        raise Unauthenticated("Authorization token missing.")
    return payload_from_token(header.split(" ", 1)[1].strip())


def require_role(payload, role):
    """Return the token's user_id if its role is `role`. Students and
    teachers have separate id sequences (student 14 and teacher 14 are
    different people), so every role-specific endpoint must check this."""
    if payload.get("role") != role:
        raise AccessDenied(f"This action requires a {role} account.")
    return payload["user_id"]


def require_class_owner(db, teacher_id, class_id):
    classroom = ClassroomRepository.get_by_id(db, class_id)
    if not classroom:
        raise AccessDenied("Classroom not found.")
    if classroom.teacher_id != teacher_id:
        raise AccessDenied("You are not authorized to manage this class.")
    return classroom


def student_is_allowed(db, student_id, class_id):
    return EnrollmentRepository.already_joined(db, student_id, class_id) is not None


def require_student_allowed(db, student_id, class_id, require_live=False):
    """Return (classroom, active_session or None)."""
    classroom = ClassroomRepository.get_by_id(db, class_id)
    if not classroom or not student_is_allowed(db, student_id, class_id):
        # Same message whether the class exists or not -- don't reveal
        # other teachers' classes to probing students.
        raise AccessDenied(NOT_AUTHORIZED_TO_JOIN)
    session = SessionRepository.get_active_session(db, class_id)
    if require_live and not session:
        raise AccessDenied("This class is not currently live.")
    return classroom, session


def require_class_member(db, payload, class_id, require_live_for_students=True):
    """Teacher who owns the class, or an allowed student (by default only
    while the class is live). Returns {role, user_id, name}."""
    role = payload.get("role")
    user_id = payload.get("user_id")

    if role == "teacher":
        require_class_owner(db, user_id, class_id)
        teacher = TeacherRepository.get_by_id(db, user_id)
        return {"role": "teacher", "user_id": user_id, "name": teacher.name if teacher else "Teacher"}

    if role == "student":
        require_student_allowed(db, user_id, class_id, require_live=require_live_for_students)
        student = StudentRepository.get_by_id(db, user_id)
        return {"role": "student", "user_id": user_id, "name": student.name if student else "Student"}

    raise AccessDenied(NOT_AUTHORIZED_TO_JOIN)


def http_status_for(exc):
    if isinstance(exc, Unauthenticated):
        return 401
    if isinstance(exc, AccessDenied):
        return 403
    return 400
