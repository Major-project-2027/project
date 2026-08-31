try:
    from database.mongo import COLLECTION_ENGAGEMENT_RECORDS, COLLECTION_CLASS_SESSIONS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_ENGAGEMENT_RECORDS, COLLECTION_CLASS_SESSIONS
try:
    from database.mongo_counters import next_id, COUNTER_RECORD_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_RECORD_ID
from models.engagement import EngagementRecord
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class EngagementRepository:

    @staticmethod
    def create(db, record: EngagementRecord):
        record.record_id = next_id(db, COUNTER_RECORD_ID)
        if record.timestamp is None:
            record.timestamp = utcnow()

        db[COLLECTION_ENGAGEMENT_RECORDS].insert_one({
            "record_id": record.record_id,
            "session_id": record.session_id,
            "student_id": record.student_id,
            "timestamp": record.timestamp,
            "emotion": record.emotion,
            "blink_count": record.blink_count,
            "head_pose": record.head_pose,
            "gaze": record.gaze,
            "phone_detected": record.phone_detected,
            "multiple_person": record.multiple_person,
            "engagement_score": record.engagement_score,
            "engagement_status": record.engagement_status,
            "fps": record.fps,
            "extra_metrics": record.extra_metrics,
            "camera_status": record.camera_status,
            "internet_status": record.internet_status,
            "device_type": record.device_type,
        })

        return record

    @staticmethod
    def get_distinct_student_ids_for_session(db, session_id: int):
        return db[COLLECTION_ENGAGEMENT_RECORDS].distinct(
            "student_id", {"session_id": session_id}
        )

    @staticmethod
    def get_session_records(db, session_id: int):
        return docs_to_models(
            EngagementRecord,
            db[COLLECTION_ENGAGEMENT_RECORDS]
            .find({"session_id": session_id})
            .sort("timestamp", 1),
        )

    @staticmethod
    def get_student_session_records(db, session_id: int, student_id: int):
        return docs_to_models(
            EngagementRecord,
            db[COLLECTION_ENGAGEMENT_RECORDS]
            .find({"session_id": session_id, "student_id": student_id})
            .sort("timestamp", 1),
        )

    @staticmethod
    def get_student_class_records(db, class_id: int, student_id: int):
        session_ids = [
            s["session_id"]
            for s in db[COLLECTION_CLASS_SESSIONS].find(
                {"class_id": class_id}, {"session_id": 1}
            )
        ]

        if not session_ids:
            return []

        return docs_to_models(
            EngagementRecord,
            db[COLLECTION_ENGAGEMENT_RECORDS]
            .find({"session_id": {"$in": session_ids}, "student_id": student_id})
            .sort("timestamp", 1),
        )

    @staticmethod
    def get_completed_session_records_for_student(db, student_id: int):
        """This student's engagement_records from every session that has
        actually ENDED (class_sessions.is_active == False), ordered by
        that session's start_time then the record's own timestamp --
        the exact same two-column ordering the SQL JOIN query uses.

        App-level two-step "join" (completed sessions -> their
        records), since MongoDB has no native JOIN: fetch completed
        sessions (small table) first to get both the ordering key
        (start_time) and the id filter, then fetch this student's
        records restricted to those session_ids, and finally sort
        client-side by (session start_time, record timestamp) -- $in
        does not preserve input order, so this final sort is required
        to match the SQL ORDER BY exactly.
        """

        completed_sessions = list(
            db[COLLECTION_CLASS_SESSIONS]
            .find({"is_active": False}, {"session_id": 1, "start_time": 1})
        )

        if not completed_sessions:
            return []

        session_start = {s["session_id"]: s.get("start_time") for s in completed_sessions}
        session_ids = list(session_start.keys())

        docs = list(
            db[COLLECTION_ENGAGEMENT_RECORDS].find(
                {"student_id": student_id, "session_id": {"$in": session_ids}}
            )
        )

        docs.sort(key=lambda d: (session_start.get(d["session_id"]), d["timestamp"]))

        return docs_to_models(EngagementRecord, docs)

    @staticmethod
    def get_recent_student_session_records(db, session_id: int, student_id: int, since):
        return docs_to_models(
            EngagementRecord,
            db[COLLECTION_ENGAGEMENT_RECORDS]
            .find({
                "session_id": session_id,
                "student_id": student_id,
                "timestamp": {"$gte": since},
            })
            .sort("timestamp", 1),
        )
