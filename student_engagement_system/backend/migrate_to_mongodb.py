"""SQLite -> MongoDB migration script.

SAFE / READ-ONLY against SQLite: this script only ever reads from the
existing SQLite database (backend/student_engagement.db) via the
existing SQLAlchemy models -- it never writes, alters, or deletes
anything there. The SQLite file is untouched and remains a full backup
after this runs, and after the application is eventually switched to
MongoDB.

IDEMPOTENT: every write into MongoDB is an upsert keyed on that table's
own existing stable integer ID (or an already-unique-constrained
combination -- the exact same key each repository already relies on for
uniqueness today), via pymongo bulk_write(UpdateOne(..., upsert=True)).
Running this script any number of times converges to the same MongoDB
state; it never creates duplicate documents.

Field names in every migrated document match the original SQLAlchemy
column names 1:1 (no renaming, no reshaping) -- this is deliberate, to
keep the migration mechanically traceable against the database map
produced during inspection, and because the existing integer IDs
(student_id, teacher_id, class_id, session_id, record_id, alert_id,
attendance_id, ...) must remain exactly as they are (per explicit
instruction) rather than being replaced by MongoDB's own ObjectId
`_id` (which each document still gets automatically, but is never used
as the source of truth by application logic).

Run from the backend/ directory:
    python migrate_to_mongodb.py

What this does NOT do:
    - does not switch the application to read/write MongoDB (see
      MIGRATION_REPORT for that separate, later step)
    - does not modify/retrain any AI model
    - does not touch the SQLite database at all
"""

import sys
import time

from pymongo import UpdateOne
from pymongo.errors import PyMongoError

# Register every SQLAlchemy model up front -- same reasoning
# create_database.py / routes/student.py already rely on: a model's FK
# target table must be imported into this process before any query
# touches it, or SQLAlchemy can't resolve the foreign key at flush/query
# time. Reading is enough to trigger this; this script never flushes.
from models.teacher import Teacher
from models.student import Student
from models.classroom import Classroom
from models.session import Session as ClassSessionModel
from models.enrollment import Enrollment
from models.face_registration import FaceRegistration
from models.engagement import EngagementRecord
from models.alert import Alert
from models.attendance import Attendance
from models.future_engagement_prediction import FutureEngagementPrediction
from models.cognitive_state import CognitiveStateSummary

from database.database import SessionLocal
from database.mongo_counters import set_counter_if_higher
from database.mongo import (
    get_db,
    ensure_indexes,
    MongoConfigError,
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

BATCH_SIZE = 1000


def _bulk_upsert(collection, key_fields, documents):
    """Upsert `documents` into `collection`, keyed by `key_fields` (a
    tuple of field names forming a unique key for this collection).
    Batches writes so large tables (engagement_records, alerts) don't
    make one network round-trip per row. Returns (matched, upserted)."""

    total_matched = 0
    total_upserted = 0

    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start:start + BATCH_SIZE]

        operations = [
            UpdateOne(
                {field: doc[field] for field in key_fields},
                {"$set": doc},
                upsert=True,
            )
            for doc in batch
        ]

        if not operations:
            continue

        result = collection.bulk_write(operations, ordered=False)
        total_matched += result.matched_count
        total_upserted += len(result.upserted_ids)

    return total_matched, total_upserted


def migrate_teachers(db, mongo_db):
    rows = db.query(Teacher).all()
    documents = [
        {
            "teacher_id": r.teacher_id,
            "name": r.name,
            "email": r.email,
            "password_hash": r.password_hash,
            "department": r.department,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_TEACHERS], ("teacher_id",), documents
    )
    print(f"teachers: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_students(db, mongo_db):
    rows = db.query(Student).all()
    documents = [
        {
            "student_id": r.student_id,
            "usn": r.usn,
            "name": r.name,
            "email": r.email,
            "password_hash": r.password_hash,
            "department": r.department,
            "semester": r.semester,
            "section": r.section,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_STUDENTS], ("student_id",), documents
    )
    print(f"students: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_classrooms(db, mongo_db):
    rows = db.query(Classroom).all()
    documents = [
        {
            "class_id": r.class_id,
            "classroom_name": r.classroom_name,
            "subject": r.subject,
            "semester": r.semester,
            "section": r.section,
            "teacher_id": r.teacher_id,
            "class_code": r.class_code,
            "meeting_link": r.meeting_link,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_CLASSROOMS], ("class_id",), documents
    )
    print(f"classrooms: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_enrollments(db, mongo_db):
    rows = db.query(Enrollment).all()
    documents = [
        {
            "enrollment_id": r.enrollment_id,
            "student_id": r.student_id,
            "class_id": r.class_id,
            "joined_at": r.joined_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_ENROLLMENTS], ("enrollment_id",), documents
    )
    print(f"enrollments: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_class_sessions(db, mongo_db):
    rows = db.query(ClassSessionModel).all()
    documents = [
        {
            "session_id": r.session_id,
            "class_id": r.class_id,
            "teacher_id": r.teacher_id,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "is_active": r.is_active,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_CLASS_SESSIONS], ("session_id",), documents
    )
    print(f"class_sessions: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_face_registrations(db, mongo_db):
    """embedding is preserved EXACTLY as stored -- SQLAlchemy's JSON
    column type already deserializes it into a plain Python
    list-of-lists of floats on read (5 samples x 128 dims per the
    inspection phase), and pymongo serializes that same nested list of
    Python floats into a BSON array of doubles with no numerical change.
    Nothing about the face-recognition algorithm or embedding format is
    touched here."""

    rows = db.query(FaceRegistration).all()
    documents = [
        {
            "face_id": r.face_id,
            "student_id": r.student_id,
            "embedding": r.embedding,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_FACE_REGISTRATIONS], ("student_id",), documents
    )
    print(f"face_registrations: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_engagement_records(db, mongo_db):
    rows = db.query(EngagementRecord).all()
    documents = [
        {
            "record_id": r.record_id,
            "session_id": r.session_id,
            "student_id": r.student_id,
            "timestamp": r.timestamp,
            "emotion": r.emotion,
            "blink_count": r.blink_count,
            "head_pose": r.head_pose,
            "gaze": r.gaze,
            "phone_detected": r.phone_detected,
            "multiple_person": r.multiple_person,
            "engagement_score": r.engagement_score,
            "engagement_status": r.engagement_status,
            "fps": r.fps,
            "extra_metrics": r.extra_metrics,
            "camera_status": r.camera_status,
            "internet_status": r.internet_status,
            "device_type": r.device_type,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_ENGAGEMENT_RECORDS], ("record_id",), documents
    )
    print(f"engagement_records: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_alerts(db, mongo_db):
    rows = db.query(Alert).all()
    documents = [
        {
            "alert_id": r.alert_id,
            "session_id": r.session_id,
            "student_id": r.student_id,
            "class_id": r.class_id,
            "alert_type": r.alert_type,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_ALERTS], ("alert_id",), documents
    )
    print(f"alerts: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_attendance(db, mongo_db):
    rows = db.query(Attendance).all()
    documents = [
        {
            "attendance_id": r.attendance_id,
            "student_id": r.student_id,
            "class_id": r.class_id,
            "session_id": r.session_id,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_ATTENDANCE], ("attendance_id",), documents
    )
    print(f"attendance: {len(rows)} read from SQLite, {upserted} inserted, {matched} updated")
    return len(rows)


def migrate_future_engagement_predictions(db, mongo_db):
    rows = db.query(FutureEngagementPrediction).all()
    documents = [
        {
            "id": r.id,
            "student_id": r.student_id,
            "status": r.status,
            "prediction_score": r.prediction_score,
            "historical_sessions_used": r.historical_sessions_used,
            "model_version": r.model_version,
            "reason": r.reason,
            "generated_at": r.generated_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS], ("student_id",), documents
    )
    print(
        f"future_engagement_predictions: {len(rows)} read from SQLite, "
        f"{upserted} inserted, {matched} updated"
    )
    return len(rows)


def migrate_cognitive_state_summaries(db, mongo_db):
    rows = db.query(CognitiveStateSummary).all()
    documents = [
        {
            "id": r.id,
            "session_id": r.session_id,
            "class_id": r.class_id,
            "student_id": r.student_id,
            "status": r.status,
            "cognitive_state": r.cognitive_state,
            "focused_percentage": r.focused_percentage,
            "neutral_percentage": r.neutral_percentage,
            "distracted_percentage": r.distracted_percentage,
            "valid_sample_count": r.valid_sample_count,
            "drowsy_episode_count": r.drowsy_episode_count,
            "reason": r.reason,
            "calculated_at": r.calculated_at,
        }
        for r in rows
    ]
    matched, upserted = _bulk_upsert(
        mongo_db[COLLECTION_COGNITIVE_STATE_SUMMARIES],
        ("session_id", "student_id"),
        documents,
    )
    print(
        f"cognitive_state_summaries: {len(rows)} read from SQLite, "
        f"{upserted} inserted, {matched} updated"
    )
    return len(rows)


def seed_counters(db, mongo_db):
    """Seed the MongoDB auto-increment counters (see
    database/mongo_counters.py) from the highest ID SQLite already has
    for each entity, so the first newly-created document under the
    MongoDB backend continues the sequence rather than colliding with a
    migrated ID. Uses $max (see set_counter_if_higher), so this is safe
    to re-run at any time -- it never lowers a counter, including one
    that has already advanced past SQLite's own max because new records
    were created directly in MongoDB after the switch."""

    from sqlalchemy import func as sql_func
    from database.mongo_counters import (
        COUNTER_TEACHER_ID,
        COUNTER_STUDENT_ID,
        COUNTER_CLASS_ID,
        COUNTER_ENROLLMENT_ID,
        COUNTER_SESSION_ID,
        COUNTER_FACE_ID,
        COUNTER_RECORD_ID,
        COUNTER_ALERT_ID,
        COUNTER_ATTENDANCE_ID,
        COUNTER_FUTURE_PREDICTION_ID,
        COUNTER_COGNITIVE_STATE_ID,
    )

    def _max(model, column):
        return db.query(sql_func.max(column)).select_from(model).scalar() or 0

    seeds = [
        (COUNTER_TEACHER_ID, _max(Teacher, Teacher.teacher_id)),
        (COUNTER_STUDENT_ID, _max(Student, Student.student_id)),
        (COUNTER_CLASS_ID, _max(Classroom, Classroom.class_id)),
        (COUNTER_ENROLLMENT_ID, _max(Enrollment, Enrollment.enrollment_id)),
        (COUNTER_SESSION_ID, _max(ClassSessionModel, ClassSessionModel.session_id)),
        (COUNTER_FACE_ID, _max(FaceRegistration, FaceRegistration.face_id)),
        (COUNTER_RECORD_ID, _max(EngagementRecord, EngagementRecord.record_id)),
        (COUNTER_ALERT_ID, _max(Alert, Alert.alert_id)),
        (COUNTER_ATTENDANCE_ID, _max(Attendance, Attendance.attendance_id)),
        (COUNTER_FUTURE_PREDICTION_ID, _max(FutureEngagementPrediction, FutureEngagementPrediction.id)),
        (COUNTER_COGNITIVE_STATE_ID, _max(CognitiveStateSummary, CognitiveStateSummary.id)),
    ]

    for counter_name, max_value in seeds:
        set_counter_if_higher(mongo_db, counter_name, int(max_value))
        print(f"counter '{counter_name}' seeded to at least {max_value}")


# Migration order mirrors FK dependency order (parents before children)
# purely for readable log output -- MongoDB does not require parent
# documents to exist first, so this order is not functionally required.
MIGRATION_STEPS = [
    migrate_teachers,
    migrate_students,
    migrate_classrooms,
    migrate_enrollments,
    migrate_class_sessions,
    migrate_face_registrations,
    migrate_engagement_records,
    migrate_alerts,
    migrate_attendance,
    migrate_future_engagement_predictions,
    migrate_cognitive_state_summaries,
]


def main():
    print("=" * 70)
    print("SQLite -> MongoDB migration")
    print("=" * 70)

    try:
        mongo_db = get_db()
        # Fail fast with a clear message if MongoDB is unreachable,
        # rather than partway through the migration.
        mongo_db.client.admin.command("ping")
    except MongoConfigError as exc:
        print(f"\nABORTED -- MongoDB is not configured: {exc}")
        sys.exit(1)
    except PyMongoError as exc:
        print(f"\nABORTED -- could not connect to MongoDB: {exc}")
        sys.exit(1)

    print(f"Connected to MongoDB database: {mongo_db.name}\n")

    db = SessionLocal()

    sqlite_counts = {}

    try:
        start = time.perf_counter()

        for step in MIGRATION_STEPS:
            sqlite_counts[step.__name__] = step(db, mongo_db)

        print("\nSeeding ID counters...")
        seed_counters(db, mongo_db)

        print("\nCreating/verifying indexes...")
        ensure_indexes(mongo_db)
        print("Indexes ready.")

        elapsed = time.perf_counter() - start
        print(f"\nMigration completed in {elapsed:.2f}s.")
        print(
            "\nSQLite database was NOT modified -- it remains a full "
            "backup. Run verify_mongo_migration.py next to compare "
            "counts and spot-check relationships/embeddings."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
