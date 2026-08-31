from collections import defaultdict

try:
    from database.mongo import COLLECTION_ALERTS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_ALERTS
try:
    from database.mongo_counters import next_id, COUNTER_ALERT_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_ALERT_ID
from models.alert import Alert
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class AlertRepository:

    @staticmethod
    def create(db, session_id: int, class_id: int, student_id: int, alert_type: str):
        alert_id = next_id(db, COUNTER_ALERT_ID)
        created_at = utcnow()

        db[COLLECTION_ALERTS].insert_one({
            "alert_id": alert_id,
            "session_id": session_id,
            "class_id": class_id,
            "student_id": student_id,
            "alert_type": alert_type,
            "created_at": created_at,
        })

        return Alert(
            alert_id=alert_id,
            session_id=session_id,
            class_id=class_id,
            student_id=student_id,
            alert_type=alert_type,
            created_at=created_at,
        )

    @staticmethod
    def counts_by_type(db, session_id: int, student_id: int):
        pipeline = [
            {"$match": {"session_id": session_id, "student_id": student_id}},
            {"$group": {"_id": "$alert_type", "count": {"$sum": 1}}},
        ]
        return {
            row["_id"]: row["count"]
            for row in db[COLLECTION_ALERTS].aggregate(pipeline)
        }

    @staticmethod
    def counts_by_type_for_sessions(db, student_id: int, session_ids: list):
        if not session_ids:
            return {}

        pipeline = [
            {"$match": {"student_id": student_id, "session_id": {"$in": list(session_ids)}}},
            {"$group": {
                "_id": {"session_id": "$session_id", "alert_type": "$alert_type"},
                "count": {"$sum": 1},
            }},
        ]

        result: dict = defaultdict(dict)
        for row in db[COLLECTION_ALERTS].aggregate(pipeline):
            result[row["_id"]["session_id"]][row["_id"]["alert_type"]] = row["count"]

        return dict(result)

    @staticmethod
    def list_for_session_student(db, session_id: int, student_id: int):
        return docs_to_models(
            Alert,
            db[COLLECTION_ALERTS]
            .find({"session_id": session_id, "student_id": student_id})
            .sort("created_at", 1),
        )
