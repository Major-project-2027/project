"""MongoDB connection layer.

Added as part of the SQLite -> MongoDB migration. This module ONLY
provides connectivity + collection-name constants -- it does not (by
itself) replace any existing SQLAlchemy repository. The application's
live read/write path still goes through database/database.py (SQLite)
until the migration has been verified and the application layer is
explicitly switched over.

Configuration is environment-variable based (MONGO_URI / MONGO_DB_NAME,
read via config.py -- same load_dotenv(backend/.env) convention already
used for DATABASE_NAME/SECRET_KEY), never hard-coded. MONGO_URI is
expected to be a MongoDB Atlas connection string (mongodb+srv://...) in
normal use, but any valid MongoDB URI (including a local
mongodb://localhost:27017) works identically -- nothing here is
Atlas-specific.
"""

from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

from config import MONGO_URI, MONGO_DB_NAME


class MongoConfigError(Exception):
    """Raised when MONGO_URI/MONGO_DB_NAME are not configured."""


_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """Process-wide singleton MongoClient.

    pymongo's MongoClient is itself connection-pooled and thread-safe;
    constructing it does NOT open a network connection immediately (the
    connection is established lazily, on first actual operation), so
    creating this once and reusing it (mirroring database/database.py's
    own eager `engine = create_engine(...)` pattern) is safe even if
    MongoDB happens to be briefly unreachable at process startup.
    """

    global _client

    if _client is None:
        if not MONGO_URI:
            raise MongoConfigError(
                "MONGO_URI is not set. Set it in backend/.env (see "
                "backend/.env.example) to your MongoDB Atlas connection "
                "string, e.g. mongodb+srv://user:password@cluster.mongodb.net"
            )

        _client = MongoClient(MONGO_URI)

    return _client


def get_db() -> Database:
    if not MONGO_DB_NAME:
        raise MongoConfigError(
            "MONGO_DB_NAME is not set. Set it in backend/.env (see "
            "backend/.env.example)."
        )

    return get_client()[MONGO_DB_NAME]


def close_client() -> None:
    """Best-effort cleanup -- primarily useful for scripts/tests that
    want a clean process exit."""

    global _client

    if _client is not None:
        _client.close()
        _client = None


# ============================================================
# Collection names -- centralized so no caller hardcodes the string more
# than once. One collection per existing SQLite table (see the
# inspection-phase database map); nothing is merged or embedded.
#
# "sessions" (the SQLite table) is named "class_sessions" here, not
# "sessions" -- "sessions" collides conceptually with an auth/JWT
# session concept and would be a confusing collection name; every other
# name matches the existing SQLite table name exactly for traceability.
# ============================================================

COLLECTION_STUDENTS = "students"
COLLECTION_TEACHERS = "teachers"
COLLECTION_CLASSROOMS = "classrooms"
COLLECTION_ENROLLMENTS = "enrollments"
COLLECTION_CLASS_SESSIONS = "class_sessions"
COLLECTION_FACE_REGISTRATIONS = "face_registrations"
COLLECTION_ENGAGEMENT_RECORDS = "engagement_records"
COLLECTION_ALERTS = "alerts"
COLLECTION_ATTENDANCE = "attendance"
COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS = "future_engagement_predictions"
COLLECTION_COGNITIVE_STATE_SUMMARIES = "cognitive_state_summaries"

ALL_COLLECTIONS = (
    COLLECTION_STUDENTS,
    COLLECTION_TEACHERS,
    COLLECTION_CLASSROOMS,
    COLLECTION_ENROLLMENTS,
    COLLECTION_CLASS_SESSIONS,
    COLLECTION_FACE_REGISTRATIONS,
    COLLECTION_ENGAGEMENT_RECORDS,
    COLLECTION_ALERTS,
    COLLECTION_ATTENDANCE,
    COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS,
    COLLECTION_COGNITIVE_STATE_SUMMARIES,
)


def ensure_indexes(db: Optional[Database] = None) -> None:
    """Create every index this application's existing query patterns
    need. Safe to call repeatedly -- create_index()/create_indexes() are
    idempotent (MongoDB no-ops if an identical index already exists).

    Each index below is annotated with the exact existing SQLAlchemy
    query pattern (repository + method) it supports, so nothing here is
    a guess. No index is created "just in case" -- see the migration
    report for the full justification of each one.
    """

    # NOTE: pymongo's Database deliberately raises NotImplementedError on
    # bool()/truthiness checks (to stop exactly this kind of bug), so
    # `db or get_db()` is invalid here -- must compare to None explicitly.
    database = db if db is not None else get_db()

    # ---------------- students ----------------
    # StudentRepository.get_by_email / get_student_by_email (login),
    # StudentRepository.get_by_usn. student_id is the stable ID every
    # other collection references.
    database[COLLECTION_STUDENTS].create_index("student_id", unique=True)
    database[COLLECTION_STUDENTS].create_index("email", unique=True)
    database[COLLECTION_STUDENTS].create_index("usn", unique=True)

    # ---------------- teachers ----------------
    # TeacherRepository.get_by_email (login).
    database[COLLECTION_TEACHERS].create_index("teacher_id", unique=True)
    database[COLLECTION_TEACHERS].create_index("email", unique=True)

    # ---------------- classrooms ----------------
    # ClassroomRepository.get_by_code (join-by-code),
    # get_classroom_by_id/get_by_id, get_teacher_classrooms/
    # count_teacher_classes (teacher_id).
    database[COLLECTION_CLASSROOMS].create_index("class_id", unique=True)
    database[COLLECTION_CLASSROOMS].create_index("class_code", unique=True)
    database[COLLECTION_CLASSROOMS].create_index("teacher_id")

    # ---------------- enrollments ----------------
    # EnrollmentRepository.already_joined (student_id + class_id, also
    # this collection's natural dedup key), get_student_classes
    # (student_id), get_teacher_students/count_teacher_students
    # (class_id, via a join to classrooms).
    database[COLLECTION_ENROLLMENTS].create_index(
        [("student_id", 1), ("class_id", 1)], unique=True
    )
    database[COLLECTION_ENROLLMENTS].create_index("class_id")

    # ---------------- class_sessions ----------------
    # SessionRepository.get_active_session (class_id + is_active),
    # get_all_active_sessions (is_active), teacher_id scoping elsewhere.
    database[COLLECTION_CLASS_SESSIONS].create_index("session_id", unique=True)
    database[COLLECTION_CLASS_SESSIONS].create_index([("class_id", 1), ("is_active", 1)])
    database[COLLECTION_CLASS_SESSIONS].create_index("teacher_id")

    # ---------------- face_registrations ----------------
    # FaceRepository.get_face_by_student_id / update_face_embedding /
    # delete_face -- one document per student.
    database[COLLECTION_FACE_REGISTRATIONS].create_index("student_id", unique=True)

    # ---------------- engagement_records ----------------
    # record_id is the stable migration/upsert key (SQLite's
    # autoincrement PK). The compound (session_id, student_id, timestamp)
    # index is this collection's single most important index -- it is
    # exactly the shape of EngagementRepository.get_student_session_records
    # / get_recent_student_session_records (used by the live monitoring
    # poll, LSTM predict(), and cognitive-state classification), and
    # get_session_records (session_id prefix of the same index). A
    # separate student_id index supports
    # get_completed_session_records_for_student's cross-session history
    # (used by the future-engagement LSTM).
    database[COLLECTION_ENGAGEMENT_RECORDS].create_index("record_id", unique=True)
    database[COLLECTION_ENGAGEMENT_RECORDS].create_index(
        [("session_id", 1), ("student_id", 1), ("timestamp", 1)]
    )
    database[COLLECTION_ENGAGEMENT_RECORDS].create_index("student_id")

    # ---------------- alerts ----------------
    # AlertRepository.counts_by_type / list_for_session_student
    # (session_id + student_id), counts_by_type_for_sessions (student_id
    # + session_id.in_(...)).
    database[COLLECTION_ALERTS].create_index("alert_id", unique=True)
    database[COLLECTION_ALERTS].create_index([("session_id", 1), ("student_id", 1)])
    database[COLLECTION_ALERTS].create_index("student_id")

    # ---------------- attendance ----------------
    # AttendanceRepository.upsert's own dedup key (get_by_session_and_student),
    # get_by_session, get_for_student, get_for_teacher (via class_id).
    database[COLLECTION_ATTENDANCE].create_index(
        [("session_id", 1), ("student_id", 1)], unique=True
    )
    database[COLLECTION_ATTENDANCE].create_index("class_id")
    database[COLLECTION_ATTENDANCE].create_index("student_id")

    # ---------------- future_engagement_predictions ----------------
    # FutureEngagementRepository.get_by_student / upsert -- one row per
    # student (student_id is unique in the SQL schema too).
    database[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].create_index(
        "student_id", unique=True
    )

    # ---------------- cognitive_state_summaries ----------------
    # CognitiveStateRepository.get_by_session_and_student / upsert's own
    # dedup key, get_by_session (session_id prefix of the same index).
    database[COLLECTION_COGNITIVE_STATE_SUMMARIES].create_index(
        [("session_id", 1), ("student_id", 1)], unique=True
    )
