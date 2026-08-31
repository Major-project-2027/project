try:
    from database.mongo import COLLECTION_COGNITIVE_STATE_SUMMARIES
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_COGNITIVE_STATE_SUMMARIES
try:
    from database.mongo_counters import next_id, COUNTER_COGNITIVE_STATE_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_COGNITIVE_STATE_ID
from models.cognitive_state import CognitiveStateSummary
from repositories.mongo._common import doc_to_model, utcnow


class CognitiveStateRepository:

    @staticmethod
    def get_by_session_and_student(db, session_id: int, student_id: int):
        return doc_to_model(
            CognitiveStateSummary,
            db[COLLECTION_COGNITIVE_STATE_SUMMARIES].find_one(
                {"session_id": session_id, "student_id": student_id}
            ),
        )

    @staticmethod
    def get_by_session(db, session_id: int):
        rows = db[COLLECTION_COGNITIVE_STATE_SUMMARIES].find({"session_id": session_id})
        return {
            doc["student_id"]: doc_to_model(CognitiveStateSummary, doc)
            for doc in rows
        }

    @staticmethod
    def upsert(
        db,
        session_id: int,
        class_id: int,
        student_id: int,
        status: str,
        cognitive_state,
        focused_percentage,
        neutral_percentage,
        distracted_percentage,
        valid_sample_count: int,
        drowsy_episode_count: int,
        reason,
    ):
        now = utcnow()

        fields = {
            "class_id": class_id,
            "status": status,
            "cognitive_state": cognitive_state,
            "focused_percentage": focused_percentage,
            "neutral_percentage": neutral_percentage,
            "distracted_percentage": distracted_percentage,
            "valid_sample_count": valid_sample_count,
            "drowsy_episode_count": drowsy_episode_count,
            "reason": reason,
            "calculated_at": now,
        }

        existing_doc = db[COLLECTION_COGNITIVE_STATE_SUMMARIES].find_one(
            {"session_id": session_id, "student_id": student_id}
        )

        if existing_doc:
            db[COLLECTION_COGNITIVE_STATE_SUMMARIES].update_one(
                {"session_id": session_id, "student_id": student_id},
                {"$set": fields},
            )
            return CognitiveStateRepository.get_by_session_and_student(
                db, session_id, student_id
            )

        record_id = next_id(db, COUNTER_COGNITIVE_STATE_ID)
        doc = {"id": record_id, "session_id": session_id, "student_id": student_id, **fields}
        db[COLLECTION_COGNITIVE_STATE_SUMMARIES].insert_one(doc)

        return doc_to_model(CognitiveStateSummary, doc)
