try:
    from database.mongo import COLLECTION_CLASSROOMS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_CLASSROOMS
try:
    from database.mongo_counters import next_id, COUNTER_CLASS_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_CLASS_ID
from models.classroom import Classroom
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class ClassroomRepository:

    @staticmethod
    def create_classroom(db, classroom: Classroom):
        classroom.class_id = next_id(db, COUNTER_CLASS_ID)
        if classroom.created_at is None:
            classroom.created_at = utcnow()

        db[COLLECTION_CLASSROOMS].insert_one({
            "class_id": classroom.class_id,
            "classroom_name": classroom.classroom_name,
            "subject": classroom.subject,
            "semester": classroom.semester,
            "section": classroom.section,
            "teacher_id": classroom.teacher_id,
            "class_code": classroom.class_code,
            "meeting_link": classroom.meeting_link,
            "created_at": classroom.created_at,
        })

        return classroom

    @staticmethod
    def get_by_code(db, class_code: str):
        return doc_to_model(Classroom, db[COLLECTION_CLASSROOMS].find_one({"class_code": class_code}))

    @staticmethod
    def get_teacher_classrooms(db, teacher_id: int):
        return docs_to_models(
            Classroom, db[COLLECTION_CLASSROOMS].find({"teacher_id": teacher_id})
        )

    @staticmethod
    def get_classroom_by_id(db, class_id: int):
        return doc_to_model(Classroom, db[COLLECTION_CLASSROOMS].find_one({"class_id": class_id}))

    @staticmethod
    def get_by_id(db, class_id: int):
        return ClassroomRepository.get_classroom_by_id(db, class_id)

    @staticmethod
    def update_classroom(db, classroom: Classroom):
        """`classroom` is a previously-fetched instance the caller has
        already mutated in place (see ClassroomService.update_classroom)
        -- re-serialize its current field values and persist them all,
        mirroring what SQLAlchemy's dirty-tracking + commit() would do
        for the SQL path."""

        db[COLLECTION_CLASSROOMS].update_one(
            {"class_id": classroom.class_id},
            {"$set": {
                "classroom_name": classroom.classroom_name,
                "subject": classroom.subject,
                "semester": classroom.semester,
                "section": classroom.section,
                "teacher_id": classroom.teacher_id,
                "class_code": classroom.class_code,
                "meeting_link": classroom.meeting_link,
            }},
        )

        return classroom

    @staticmethod
    def delete_classroom(db, classroom: Classroom):
        db[COLLECTION_CLASSROOMS].delete_one({"class_id": classroom.class_id})

    @staticmethod
    def count_teacher_classes(db, teacher_id: int):
        return db[COLLECTION_CLASSROOMS].count_documents({"teacher_id": teacher_id})
