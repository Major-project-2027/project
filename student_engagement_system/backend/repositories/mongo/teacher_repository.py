try:
    from database.mongo import COLLECTION_TEACHERS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_TEACHERS
try:
    from database.mongo_counters import next_id, COUNTER_TEACHER_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_TEACHER_ID
from models.teacher import Teacher
from repositories.mongo._common import doc_to_model, utcnow


class TeacherRepository:

    @staticmethod
    def get_by_email(db, email: str):
        return doc_to_model(Teacher, db[COLLECTION_TEACHERS].find_one({"email": email}))

    @staticmethod
    def get_by_id(db, teacher_id: int):
        return doc_to_model(Teacher, db[COLLECTION_TEACHERS].find_one({"teacher_id": teacher_id}))

    @staticmethod
    def create_teacher(db, teacher: Teacher):
        teacher.teacher_id = next_id(db, COUNTER_TEACHER_ID)
        if teacher.created_at is None:
            teacher.created_at = utcnow()

        db[COLLECTION_TEACHERS].insert_one({
            "teacher_id": teacher.teacher_id,
            "name": teacher.name,
            "email": teacher.email,
            "password_hash": teacher.password_hash,
            "department": teacher.department,
            "created_at": teacher.created_at,
        })

        return teacher
