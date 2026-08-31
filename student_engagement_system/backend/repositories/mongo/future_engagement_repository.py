try:
    from database.mongo import COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS
try:
    from database.mongo_counters import next_id, COUNTER_FUTURE_PREDICTION_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_FUTURE_PREDICTION_ID
from models.future_engagement_prediction import FutureEngagementPrediction
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class FutureEngagementRepository:

    @staticmethod
    def get_by_student(db, student_id: int):
        return doc_to_model(
            FutureEngagementPrediction,
            db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].find_one({"student_id": student_id}),
        )

    @staticmethod
    def get_for_students(db, student_ids: list):
        if not student_ids:
            return []
        return docs_to_models(
            FutureEngagementPrediction,
            db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].find(
                {"student_id": {"$in": list(student_ids)}}
            ),
        )

    @staticmethod
    def upsert(
        db,
        student_id: int,
        status: str,
        prediction_score,
        historical_sessions_used: int,
        model_version,
        reason,
    ):
        now = utcnow()
        existing_doc = db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].find_one(
            {"student_id": student_id}
        )

        fields = {
            "status": status,
            "prediction_score": prediction_score,
            "historical_sessions_used": historical_sessions_used,
            "model_version": model_version,
            "reason": reason,
            "generated_at": now,
        }

        if existing_doc:
            db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].update_one(
                {"student_id": student_id}, {"$set": fields}
            )
            return FutureEngagementRepository.get_by_student(db, student_id)

        record_id = next_id(db, COUNTER_FUTURE_PREDICTION_ID)
        doc = {"id": record_id, "student_id": student_id, **fields}
        db[COLLECTION_FUTURE_ENGAGEMENT_PREDICTIONS].insert_one(doc)

        return doc_to_model(FutureEngagementPrediction, doc)
