"""Auto-increment ID emulation for MongoDB.

MongoDB has no native autoincrement integer primary key (only ObjectId).
Since the migration explicitly preserves the existing SQLite integer IDs
(student_id, class_id, session_id, record_id, alert_id, ...) as the
IDs the application and frontend actually use, newly-created documents
under the MongoDB backend need a way to get the next integer ID for
their entity type. This module implements the standard MongoDB
auto-increment pattern: one document per counter in a `counters`
collection, incremented atomically via findAndModify ($inc), so
concurrent writers (e.g. two students' frames arriving at the same
moment) never receive the same ID.

Counters are seeded once, from the migration's own knowledge of the
highest ID already migrated from SQLite (see migrate_to_mongodb.py's
seed_counters()), so the first newly-created document under MongoDB
continues the sequence rather than colliding with migrated IDs.
"""

from typing import Optional

from pymongo.database import Database

COUNTERS_COLLECTION = "counters"

# Counter name -> the field it drives, purely for documentation; the
# counter name is used directly as the counters collection's _id.
COUNTER_TEACHER_ID = "teacher_id"
COUNTER_STUDENT_ID = "student_id"
COUNTER_CLASS_ID = "class_id"
COUNTER_ENROLLMENT_ID = "enrollment_id"
COUNTER_SESSION_ID = "session_id"
COUNTER_FACE_ID = "face_id"
COUNTER_RECORD_ID = "record_id"
COUNTER_ALERT_ID = "alert_id"
COUNTER_ATTENDANCE_ID = "attendance_id"
COUNTER_FUTURE_PREDICTION_ID = "future_prediction_id"
COUNTER_COGNITIVE_STATE_ID = "cognitive_state_id"


def next_id(db: Database, counter_name: str) -> int:
    """Atomically returns the next integer ID for `counter_name`,
    starting at 1 if the counter does not exist yet."""

    doc = db[COUNTERS_COLLECTION].find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,  # ReturnDocument.AFTER
    )
    return int(doc["seq"])


def set_counter_if_higher(db: Database, counter_name: str, value: int) -> None:
    """Ensures `counter_name`'s stored sequence is at least `value`.
    Used only during migration seeding -- never lowers an existing
    counter, so re-running the seed step is safe/idempotent."""

    db[COUNTERS_COLLECTION].update_one(
        {"_id": counter_name},
        {"$max": {"seq": value}},
        upsert=True,
    )
