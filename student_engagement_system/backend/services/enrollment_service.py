from models.enrollment import Enrollment

from repositories.classroom_repository import ClassroomRepository
from repositories.enrollment_repository import EnrollmentRepository
from repositories.session_repository import SessionRepository


class EnrollmentService:

    @staticmethod
    def join_live_class(db, student_id, class_id):
        """Direct join for the "Live Classes" dashboard flow -- no class
        code required. Only allowed while the class actually has an
        active session, and never creates a second session or a
        duplicate enrollment row."""

        classroom = ClassroomRepository.get_by_id(
            db,
            class_id
        )

        if not classroom:
            raise Exception("Classroom not found.")

        active_session = SessionRepository.get_active_session(
            db,
            class_id
        )

        if not active_session:
            raise Exception("This class is not currently live.")

        if not EnrollmentRepository.already_joined(
            db,
            student_id,
            class_id
        ):
            enrollment = Enrollment(
                student_id=student_id,
                class_id=class_id
            )

            EnrollmentRepository.join_class(
                db,
                enrollment
            )

        return classroom, active_session

    @staticmethod
    def join_class(db, student_id, class_code):

        classroom = ClassroomRepository.get_by_code(
            db,
            class_code
        )

        # The dashboard "join" flow links using the numeric class_id
        # rather than the human-entered class_code, so fall back to an
        # id lookup when the code doesn't match anything.
        if not classroom and str(class_code).isdigit():
            classroom = ClassroomRepository.get_by_id(
                db,
                int(class_code)
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

