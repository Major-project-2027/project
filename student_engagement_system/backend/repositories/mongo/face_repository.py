try:
    from database.mongo import COLLECTION_FACE_REGISTRATIONS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_FACE_REGISTRATIONS
try:
    from database.mongo_counters import next_id, COUNTER_FACE_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_FACE_ID
from models.face_registration import FaceRegistration
from repositories.mongo._common import doc_to_model, utcnow


class FaceRepository:

    @staticmethod
    def get_face_by_student_id(db, student_id: int):
        return doc_to_model(
            FaceRegistration,
            db[COLLECTION_FACE_REGISTRATIONS].find_one({"student_id": student_id}),
        )

    @staticmethod
    def save_face_embedding(db, student_id: int, embedding):
        """`embedding` is preserved exactly as given -- a plain Python
        list (of floats, or of lists-of-floats for multi-sample
        registration) -- pymongo serializes it to a BSON array of
        doubles with no numerical change, same as the migration script
        already verified for the migrated rows."""

        face_id = next_id(db, COUNTER_FACE_ID)
        created_at = utcnow()

        db[COLLECTION_FACE_REGISTRATIONS].insert_one({
            "face_id": face_id,
            "student_id": student_id,
            "embedding": embedding,
            "created_at": created_at,
        })

        face = FaceRegistration(
            face_id=face_id,
            student_id=student_id,
            embedding=embedding,
            created_at=created_at,
        )
        return face

    @staticmethod
    def update_face_embedding(db, student_id: int, embedding):
        db[COLLECTION_FACE_REGISTRATIONS].update_one(
            {"student_id": student_id},
            {"$set": {"embedding": embedding}},
        )
        return FaceRepository.get_face_by_student_id(db, student_id)

    @staticmethod
    def delete_face(db, student_id: int):
        db[COLLECTION_FACE_REGISTRATIONS].delete_one({"student_id": student_id})
