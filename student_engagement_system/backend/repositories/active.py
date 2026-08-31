"""Single dispatch point for "which repository implementation is
actually active right now" -- SQLite (default) or MongoDB, chosen by
config.DB_BACKEND.

Every route/service imports repository classes from HERE (e.g.
`from repositories.active import StudentRepository`) instead of
importing directly from repositories.student_repository /
repositories.mongo.student_repository. That is the ONLY change most
call sites need to make: the class name and every method's signature
and return shape are identical between the SQL and Mongo
implementations (each Mongo repository returns instances of the same
SQLAlchemy model classes -- see repositories/mongo/_common.py), so
`StudentRepository.get_by_email(db, email)` reads/behaves the same
regardless of which backend is active.

ROLLBACK: set DB_BACKEND back to "sqlite" (or remove it) in backend/.env
and restart both the Flask and FastAPI processes -- every repository
re-resolves to its SQLite implementation with no code changes.
"""

from config import DB_BACKEND

if DB_BACKEND == "mongodb":
    from repositories.mongo.teacher_repository import TeacherRepository
    from repositories.mongo.student_repository import StudentRepository
    from repositories.mongo.classroom_repository import ClassroomRepository
    from repositories.mongo.enrollment_repository import EnrollmentRepository
    from repositories.mongo.session_repository import SessionRepository
    from repositories.mongo.face_repository import FaceRepository
    from repositories.mongo.engagement_repository import EngagementRepository
    from repositories.mongo.alert_repository import AlertRepository
    from repositories.mongo.attendance_repository import AttendanceRepository
    from repositories.mongo.future_engagement_repository import FutureEngagementRepository
    from repositories.mongo.cognitive_state_repository import CognitiveStateRepository
else:
    from repositories.teacher_repository import TeacherRepository
    from repositories.student_repository import StudentRepository
    from repositories.classroom_repository import ClassroomRepository
    from repositories.enrollment_repository import EnrollmentRepository
    from repositories.session_repository import SessionRepository
    from repositories.face_repository import FaceRepository
    from repositories.engagement_repository import EngagementRepository
    from repositories.alert_repository import AlertRepository
    from repositories.attendance_repository import AttendanceRepository
    from repositories.future_engagement_repository import FutureEngagementRepository
    from repositories.cognitive_state_repository import CognitiveStateRepository

__all__ = [
    "TeacherRepository",
    "StudentRepository",
    "ClassroomRepository",
    "EnrollmentRepository",
    "SessionRepository",
    "FaceRepository",
    "EngagementRepository",
    "AlertRepository",
    "AttendanceRepository",
    "FutureEngagementRepository",
    "CognitiveStateRepository",
]
