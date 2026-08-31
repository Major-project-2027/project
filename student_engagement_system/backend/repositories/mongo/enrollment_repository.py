try:
    from database.mongo import (
    COLLECTION_ENROLLMENTS,
    COLLECTION_CLASSROOMS,
    COLLECTION_STUDENTS,
)
except ModuleNotFoundError:
    from backend.database.mongo import (
    COLLECTION_ENROLLMENTS,
    COLLECTION_CLASSROOMS,
    COLLECTION_STUDENTS,
)
try:
    from database.mongo_counters import next_id, COUNTER_ENROLLMENT_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_ENROLLMENT_ID
from models.enrollment import Enrollment
from models.classroom import Classroom
from models.student import Student
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class EnrollmentRepository:

    @staticmethod
    def join_class(db, enrollment: Enrollment):
        enrollment.enrollment_id = next_id(db, COUNTER_ENROLLMENT_ID)
        if enrollment.joined_at is None:
            enrollment.joined_at = utcnow()

        db[COLLECTION_ENROLLMENTS].insert_one({
            "enrollment_id": enrollment.enrollment_id,
            "student_id": enrollment.student_id,
            "class_id": enrollment.class_id,
            "joined_at": enrollment.joined_at,
        })

        return enrollment

    @staticmethod
    def already_joined(db, student_id: int, class_id: int):
        return doc_to_model(
            Enrollment,
            db[COLLECTION_ENROLLMENTS].find_one(
                {"student_id": student_id, "class_id": class_id}
            ),
        )

    @staticmethod
    def get_student_classes(db, student_id: int):
        """Every classroom this student is enrolled in -- app-level
        "join" equivalent of the SQL INNER JOIN enrollments->classrooms:
        first the student's class_ids from enrollments, then those
        classroom documents. Two queries instead of one $lookup
        aggregation, matching the same explicit two-step pattern already
        used elsewhere in this migration (e.g. the LSTM historical
        query) for readability/traceability."""

        class_ids = [
            e["class_id"]
            for e in db[COLLECTION_ENROLLMENTS].find(
                {"student_id": student_id}, {"class_id": 1}
            )
        ]

        if not class_ids:
            return []

        return docs_to_models(
            Classroom, db[COLLECTION_CLASSROOMS].find({"class_id": {"$in": class_ids}})
        )

    @staticmethod
    def get_teacher_students(db, teacher_id: int):
        """Every distinct student enrolled in ANY of this teacher's
        classrooms -- app-level equivalent of the SQL double JOIN
        (enrollments -> classrooms, filtered by teacher_id)."""

        class_ids = [
            c["class_id"]
            for c in db[COLLECTION_CLASSROOMS].find(
                {"teacher_id": teacher_id}, {"class_id": 1}
            )
        ]

        if not class_ids:
            return []

        student_ids = sorted({
            e["student_id"]
            for e in db[COLLECTION_ENROLLMENTS].find(
                {"class_id": {"$in": class_ids}}, {"student_id": 1}
            )
        })

        if not student_ids:
            return []

        return docs_to_models(
            Student, db[COLLECTION_STUDENTS].find({"student_id": {"$in": student_ids}})
        )

    @staticmethod
    def get_for_class(db, class_id: int):
        return docs_to_models(
            Enrollment, db[COLLECTION_ENROLLMENTS].find({"class_id": class_id})
        )

    @staticmethod
    def count_for_class(db, class_id: int):
        return db[COLLECTION_ENROLLMENTS].count_documents({"class_id": class_id})

    @staticmethod
    def count_teacher_students(db, teacher_id: int):
        """Count of enrollment rows (not distinct students -- mirrors
        the SQL query exactly, which counts enrollments joined to this
        teacher's classrooms, not DISTINCT student_id)."""

        class_ids = [
            c["class_id"]
            for c in db[COLLECTION_CLASSROOMS].find(
                {"teacher_id": teacher_id}, {"class_id": 1}
            )
        ]

        if not class_ids:
            return 0

        return db[COLLECTION_ENROLLMENTS].count_documents(
            {"class_id": {"$in": class_ids}}
        )
