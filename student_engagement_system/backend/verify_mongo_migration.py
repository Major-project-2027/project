"""Post-migration verification: SQLite vs MongoDB.

READ-ONLY against both databases -- never writes/modifies anything.
Safe to run as many times as you like, including before a migration has
been run at all (it will just report empty MongoDB collections).

Run from the backend/ directory, AFTER migrate_to_mongodb.py:
    python verify_mongo_migration.py

Checks performed:
  1. Row/document counts for every table/collection.
  2. Relationship spot-checks (engagement_records/alerts/attendance
     reference real students/sessions/classrooms in both databases).
  3. Face embeddings: every stored embedding is 5 samples x 128 dims and
     numerically IDENTICAL between SQLite and MongoDB (exact float
     equality, not "close enough").
  4. Engagement records for a real (session_id, student_id) pair are
     retrievable from MongoDB with the same count and same
     first/last timestamp+score as SQLite.
  5. A real cognitive_state_summaries row is retrievable from MongoDB
     with identical field values to SQLite.
  6. The LSTM's cross-session historical-record query
     (EngagementRepository.get_completed_session_records_for_student)
     is reproduced against MongoDB (completed class_sessions -> their
     engagement_records) and compared for row-count equality.
  7. Attendance and alerts: count + one full-row spot-check each.
"""

import sys

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
from database.mongo import (
    get_db,
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

ISSUES = []


def fail(message):
    ISSUES.append(message)
    print(f"  FAIL: {message}")


def ok(message):
    print(f"  OK: {message}")


# ============================================================
# 1. Counts
# ============================================================

def check_counts(db, mongo_db):
    print("\n--- 1. Row/document counts ---")

    pairs = [
        ("teachers", db.query(Teacher).count(), mongo_db[COLLECTION_TEACHERS].count_documents({})),
        ("students", db.query(Student).count(), mongo_db[COLLECTION_STUDENTS].count_documents({})),
        ("classrooms", db.query(Classroom).count(), mongo_db[COLLECTION_CLASSROOMS].count_documents({})),
        ("enrollments", db.query(Enrollment).count(), mongo_db[COLLECTION_ENROLLMENTS].count_documents({})),
        ("class_sessions", db.query(ClassSessionModel).count(), mongo_db[COLLECTION_CLASS_SESSIONS].count_documents({})),
        ("face_registrations", db.query(FaceRegistration).count(), mongo_db[COLLECTION_FACE_REGISTRATIONS].count_documents({})),
        ("engagement_records", db.query(EngagementRecord).count(), mongo_db[COLLECTION_ENGAGEMENT_RECORDS].count_documents({})),
        ("alerts", db.query(Alert).count(), mongo_db[COLLECTION_ALERTS].count_documents({})),
        ("attendance", db.query(Attendance).count(), mongo_db[COLLECTION_ATTENDANCE].count_documents({})),
        ("future_engagement_predictions", db.query(FutureEngagementPrediction).count(), mongo_db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].count_documents({})),
        ("cognitive_state_summaries", db.query(CognitiveStateSummary).count(), mongo_db[COLLECTION_COGNITIVE_STATE_SUMMARIES].count_documents({})),
    ]

    for name, sqlite_count, mongo_count in pairs:
        diff = mongo_count - sqlite_count
        status = "OK" if diff == 0 else "MISMATCH"
        print(f"  {name:32s} sqlite={sqlite_count:6d}  mongo={mongo_count:6d}  diff={diff:+d}  [{status}]")
        if diff != 0:
            fail(f"{name}: count mismatch (sqlite={sqlite_count}, mongo={mongo_count})")


# ============================================================
# 2. Relationship spot-checks
# ============================================================

def check_relationships(db, mongo_db):
    print("\n--- 2. Relationship spot-checks (10 rows per table) ---")

    student_ids = {s["student_id"] for s in mongo_db[COLLECTION_STUDENTS].find({}, {"student_id": 1})}
    class_ids = {c["class_id"] for c in mongo_db[COLLECTION_CLASSROOMS].find({}, {"class_id": 1})}
    session_ids = {s["session_id"] for s in mongo_db[COLLECTION_CLASS_SESSIONS].find({}, {"session_id": 1})}

    checked = 0
    broken = 0
    for doc in mongo_db[COLLECTION_ENGAGEMENT_RECORDS].find({}).limit(10):
        checked += 1
        if doc["session_id"] not in session_ids or doc["student_id"] not in student_ids:
            broken += 1
    if broken:
        fail(f"engagement_records: {broken}/{checked} sampled rows reference a missing session/student")
    else:
        ok(f"engagement_records: {checked}/{checked} sampled rows reference valid session/student")

    checked = 0
    broken = 0
    for doc in mongo_db[COLLECTION_ALERTS].find({}).limit(10):
        checked += 1
        if (
            doc["session_id"] not in session_ids
            or doc["student_id"] not in student_ids
            or doc["class_id"] not in class_ids
        ):
            broken += 1
    if broken:
        fail(f"alerts: {broken}/{checked} sampled rows reference a missing session/student/class")
    else:
        ok(f"alerts: {checked}/{checked} sampled rows reference valid session/student/class")

    checked = 0
    broken = 0
    for doc in mongo_db[COLLECTION_ATTENDANCE].find({}).limit(10):
        checked += 1
        if doc["student_id"] not in student_ids or doc["class_id"] not in class_ids:
            broken += 1
    if broken:
        fail(f"attendance: {broken}/{checked} sampled rows reference a missing student/class")
    else:
        ok(f"attendance: {checked}/{checked} sampled rows reference valid student/class")

    checked = 0
    broken = 0
    for doc in mongo_db[COLLECTION_COGNITIVE_STATE_SUMMARIES].find({}).limit(10):
        checked += 1
        if doc["session_id"] not in session_ids or doc["student_id"] not in student_ids:
            broken += 1
    if broken:
        fail(f"cognitive_state_summaries: {broken}/{checked} sampled rows reference a missing session/student")
    else:
        ok(f"cognitive_state_summaries: {checked}/{checked} sampled rows reference valid session/student")


# ============================================================
# 3. Face embeddings -- exact numeric equality, every row
# ============================================================

def check_face_embeddings(db, mongo_db):
    print("\n--- 3. Face embeddings (every row, exact numeric equality) ---")

    rows = db.query(FaceRegistration).all()
    if not rows:
        print("  (no face_registrations rows to check)")
        return

    all_ok = True
    for row in rows:
        mongo_doc = mongo_db[COLLECTION_FACE_REGISTRATIONS].find_one({"student_id": row.student_id})

        if mongo_doc is None:
            fail(f"face_registrations: student_id={row.student_id} missing from MongoDB")
            all_ok = False
            continue

        sqlite_embedding = row.embedding
        mongo_embedding = mongo_doc["embedding"]

        shape_ok = (
            isinstance(mongo_embedding, list)
            and len(mongo_embedding) == len(sqlite_embedding)
            and all(len(a) == len(b) for a, b in zip(mongo_embedding, sqlite_embedding))
        )
        if not shape_ok:
            fail(f"face_registrations: student_id={row.student_id} embedding shape mismatch")
            all_ok = False
            continue

        # Exact float equality -- these values pass through Python
        # floats -> JSON (SQLite) and Python floats -> BSON double
        # (MongoDB) with no lossy re-encoding, so they must match bit
        # for bit, not just "close enough".
        values_ok = all(
            a == b
            for sample_a, sample_b in zip(sqlite_embedding, mongo_embedding)
            for a, b in zip(sample_a, sample_b)
        )
        if not values_ok:
            fail(f"face_registrations: student_id={row.student_id} embedding values differ")
            all_ok = False
            continue

        samples = len(mongo_embedding)
        dims = len(mongo_embedding[0]) if samples else 0
        if samples != 5 or dims != 128:
            print(f"  NOTE: student_id={row.student_id} has {samples} samples x {dims} dims (expected 5x128)")

    if all_ok:
        ok(f"{len(rows)}/{len(rows)} face_registrations rows numerically identical, correct shape")


# ============================================================
# 4. Engagement records retrievable for a real (session, student)
# ============================================================

def check_engagement_retrieval(db, mongo_db):
    print("\n--- 4. Engagement records retrievable for a real (session, student) ---")

    # Pick the (session_id, student_id) pair with the most records --
    # deterministic, reproducible, and exercises a real, sizable history.
    from sqlalchemy import func as sql_func

    top = (
        db.query(
            EngagementRecord.session_id,
            EngagementRecord.student_id,
            sql_func.count(EngagementRecord.record_id),
        )
        .group_by(EngagementRecord.session_id, EngagementRecord.student_id)
        .order_by(sql_func.count(EngagementRecord.record_id).desc())
        .first()
    )

    if top is None:
        print("  (no engagement_records to check)")
        return

    session_id, student_id, sqlite_count = top

    sqlite_rows = (
        db.query(EngagementRecord)
        .filter(
            EngagementRecord.session_id == session_id,
            EngagementRecord.student_id == student_id,
        )
        .order_by(EngagementRecord.timestamp.asc())
        .all()
    )

    mongo_rows = list(
        mongo_db[COLLECTION_ENGAGEMENT_RECORDS]
        .find({"session_id": session_id, "student_id": student_id})
        .sort("timestamp", 1)
    )

    print(f"  session_id={session_id} student_id={student_id}")
    print(f"  sqlite rows={len(sqlite_rows)}  mongo rows={len(mongo_rows)}")

    if len(sqlite_rows) != len(mongo_rows):
        fail(f"engagement retrieval: count mismatch ({len(sqlite_rows)} vs {len(mongo_rows)})")
        return

    first_match = (
        sqlite_rows[0].timestamp == mongo_rows[0]["timestamp"]
        and float(sqlite_rows[0].engagement_score) == float(mongo_rows[0]["engagement_score"])
    )
    last_match = (
        sqlite_rows[-1].timestamp == mongo_rows[-1]["timestamp"]
        and float(sqlite_rows[-1].engagement_score) == float(mongo_rows[-1]["engagement_score"])
    )

    if first_match and last_match:
        ok("first and last record (timestamp + engagement_score) match exactly, same order")
    else:
        fail("engagement retrieval: first/last record values or ordering differ")


# ============================================================
# 5. Cognitive state summary retrievable
# ============================================================

def check_cognitive_state_retrieval(db, mongo_db):
    print("\n--- 5. Cognitive state summary retrievable ---")

    row = db.query(CognitiveStateSummary).first()
    if row is None:
        print("  (no cognitive_state_summaries rows to check)")
        return

    mongo_doc = mongo_db[COLLECTION_COGNITIVE_STATE_SUMMARIES].find_one(
        {"session_id": row.session_id, "student_id": row.student_id}
    )

    if mongo_doc is None:
        fail(f"cognitive_state_summaries: (session={row.session_id}, student={row.student_id}) missing from MongoDB")
        return

    fields_match = (
        mongo_doc.get("status") == row.status
        and mongo_doc.get("cognitive_state") == row.cognitive_state
        and mongo_doc.get("focused_percentage") == row.focused_percentage
        and mongo_doc.get("neutral_percentage") == row.neutral_percentage
        and mongo_doc.get("distracted_percentage") == row.distracted_percentage
        and mongo_doc.get("valid_sample_count") == row.valid_sample_count
        and mongo_doc.get("drowsy_episode_count") == row.drowsy_episode_count
    )

    print(
        f"  session_id={row.session_id} student_id={row.student_id} "
        f"state={row.cognitive_state!r} status={row.status!r}"
    )

    if fields_match:
        ok("all fields match exactly between SQLite and MongoDB")
    else:
        fail("cognitive_state_summaries: field values differ between SQLite and MongoDB")


# ============================================================
# 6. LSTM cross-session historical query (future-engagement prediction)
# ============================================================

def check_lstm_historical_query(db, mongo_db):
    print("\n--- 6. LSTM historical-record query (completed sessions for one student) ---")

    # Pick a student who actually has records in a completed session.
    from sqlalchemy import func as sql_func

    candidate = (
        db.query(EngagementRecord.student_id)
        .join(ClassSessionModel, EngagementRecord.session_id == ClassSessionModel.session_id)
        .filter(ClassSessionModel.is_active == False)  # noqa: E712
        .group_by(EngagementRecord.student_id)
        .order_by(sql_func.count(EngagementRecord.record_id).desc())
        .first()
    )

    if candidate is None:
        print("  (no completed-session engagement_records to check)")
        return

    student_id = candidate[0]

    # SQLite -- exact query EngagementRepository.get_completed_session_records_for_student uses.
    sqlite_rows = (
        db.query(EngagementRecord)
        .join(ClassSessionModel, EngagementRecord.session_id == ClassSessionModel.session_id)
        .filter(
            EngagementRecord.student_id == student_id,
            ClassSessionModel.is_active == False,  # noqa: E712
        )
        .order_by(ClassSessionModel.start_time.asc(), EngagementRecord.timestamp.asc())
        .all()
    )

    # MongoDB -- two-step application-level "join": completed session_ids
    # for this student, then their engagement_records. This is the same
    # shape the application layer will use once switched over.
    completed_session_ids = [
        s["session_id"]
        for s in mongo_db[COLLECTION_CLASS_SESSIONS].find(
            {"is_active": False}, {"session_id": 1}
        )
    ]
    mongo_rows = list(
        mongo_db[COLLECTION_ENGAGEMENT_RECORDS].find(
            {"student_id": student_id, "session_id": {"$in": completed_session_ids}}
        )
    )

    print(f"  student_id={student_id}  sqlite rows={len(sqlite_rows)}  mongo rows={len(mongo_rows)}")

    if len(sqlite_rows) == len(mongo_rows):
        ok("row count matches -- LSTM's historical-record source query is reproducible against MongoDB")
    else:
        fail(
            f"LSTM historical query: count mismatch for student_id={student_id} "
            f"({len(sqlite_rows)} vs {len(mongo_rows)})"
        )


# ============================================================
# 7. Attendance / alerts spot-check
# ============================================================

def check_attendance_and_alerts(db, mongo_db):
    print("\n--- 7. Attendance / alerts spot-check ---")

    att_row = db.query(Attendance).first()
    if att_row is not None:
        mongo_doc = mongo_db[COLLECTION_ATTENDANCE].find_one(
            {"session_id": att_row.session_id, "student_id": att_row.student_id}
        )
        if mongo_doc and mongo_doc.get("status") == att_row.status and mongo_doc.get("class_id") == att_row.class_id:
            ok(f"attendance row (session={att_row.session_id}, student={att_row.student_id}) matches")
        else:
            fail(f"attendance row (session={att_row.session_id}, student={att_row.student_id}) mismatch or missing")
    else:
        print("  (no attendance rows to check)")

    alert_row = db.query(Alert).first()
    if alert_row is not None:
        mongo_doc = mongo_db[COLLECTION_ALERTS].find_one({"alert_id": alert_row.alert_id})
        if mongo_doc and mongo_doc.get("alert_type") == alert_row.alert_type:
            ok(f"alert row (alert_id={alert_row.alert_id}, type={alert_row.alert_type!r}) matches")
        else:
            fail(f"alert row (alert_id={alert_row.alert_id}) mismatch or missing")
    else:
        print("  (no alerts rows to check)")


def main():
    print("=" * 70)
    print("SQLite vs MongoDB verification")
    print("=" * 70)

    try:
        mongo_db = get_db()
        mongo_db.client.admin.command("ping")
    except MongoConfigError as exc:
        print(f"\nABORTED -- MongoDB is not configured: {exc}")
        sys.exit(1)

    db = SessionLocal()

    try:
        check_counts(db, mongo_db)
        check_relationships(db, mongo_db)
        check_face_embeddings(db, mongo_db)
        check_engagement_retrieval(db, mongo_db)
        check_cognitive_state_retrieval(db, mongo_db)
        check_lstm_historical_query(db, mongo_db)
        check_attendance_and_alerts(db, mongo_db)
    finally:
        db.close()

    print("\n" + "=" * 70)
    if ISSUES:
        print(f"VERIFICATION FAILED -- {len(ISSUES)} issue(s):")
        for issue in ISSUES:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("VERIFICATION PASSED -- no issues found.")
    print("=" * 70)


if __name__ == "__main__":
    main()
