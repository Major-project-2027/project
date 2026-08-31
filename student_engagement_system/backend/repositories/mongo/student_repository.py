import re

try:
    from database.mongo import COLLECTION_STUDENTS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_STUDENTS
try:
    from database.mongo_counters import next_id, COUNTER_STUDENT_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_STUDENT_ID
from models.student import Student
from repositories.mongo._common import doc_to_model, utcnow


class StudentRepository:

    @staticmethod
    def get_by_email(db, email: str):
        return doc_to_model(Student, db[COLLECTION_STUDENTS].find_one({"email": email}))

    @staticmethod
    def get_by_usn(db, usn: str):
        return doc_to_model(Student, db[COLLECTION_STUDENTS].find_one({"usn": usn}))

    @staticmethod
    def get_by_id(db, student_id: int):
        return doc_to_model(Student, db[COLLECTION_STUDENTS].find_one({"student_id": student_id}))

    @staticmethod
    def get_student_by_email(db, email: str):
        return StudentRepository.get_by_email(db, email)

    @staticmethod
    def create_student(db, student: Student):
        student.student_id = next_id(db, COUNTER_STUDENT_ID)
        if student.created_at is None:
            student.created_at = utcnow()

        db[COLLECTION_STUDENTS].insert_one({
            "student_id": student.student_id,
            "usn": student.usn,
            "name": student.name,
            "email": student.email,
            "password_hash": student.password_hash,
            "department": student.department,
            "semester": student.semester,
            "section": student.section,
            "created_at": student.created_at,
        })

        return student

    @staticmethod
    def get_usns_starting_with(db, prefix: str):
        return [
            doc["usn"]
            for doc in db[COLLECTION_STUDENTS].find(
                {"usn": {"$regex": f"^{re.escape(prefix)}"}}, {"usn": 1}
            )
        ]
