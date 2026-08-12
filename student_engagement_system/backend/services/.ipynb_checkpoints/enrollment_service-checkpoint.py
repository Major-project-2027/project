from models.enrollment import Enrollment

from repositories.classroom_repository import ClassroomRepository
from repositories.enrollment_repository import EnrollmentRepository


class EnrollmentService:

    @staticmethod
    def join_class(db, student_id, class_code):

        classroom = ClassroomRepository.get_by_code(
            db,
            class_code
        )

        if not classroom:
            raise Exception("Invalid classroom code.")

        if EnrollmentRepository.already_joined(
            db,
            student_id,
            classroom.class_id
        ):
            raise Exception("You have already joined this classroom.")

        enrollment = Enrollment(
            student_id=student_id,
            class_id=classroom.class_id
        )

        EnrollmentRepository.join_class(
            db,
            enrollment
        )

        return classroom

    @staticmethod
    def get_student_classes(db, student_id):

        return EnrollmentRepository.get_student_classes(
            db,
            student_id
        )

