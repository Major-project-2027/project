from models.enrollment import Enrollment

from repositories.active import ClassroomRepository, EnrollmentRepository, SessionRepository
from services import face_verification_state


class EnrollmentService:

    @staticmethod
    def join_live_class(db, student_id, class_id):
        """Direct join for the "Live Classes" dashboard flow -- no class
        code required. Only allowed while the class actually has an
        active session, and never creates a second session or a
        duplicate enrollment row.

        Also the backend-enforced anti-bypass gate for Feature 2: this is
        THE join endpoint the "Join class" button calls, so it is where
        face verification is actually required and consumed -- a request
        that never passed /face/verify-live for this exact
        (student_id, class_id) is rejected here regardless of anything
        the client claims, because consume_verification() can only
        return True if the backend itself recorded a real match.
        """

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

        if not face_verification_state.consume_verification(student_id, class_id):
            raise Exception(
                "Face verification required before joining this class."
            )

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

        # A student who is NOT yet enrolled and enters a class code for a
        # class that is currently LIVE is functionally doing the same
        # thing as "Join class" on the Live Classes card (entering a
        # monitored session for the first time) -- so this path must not
        # be a face-verification bypass just because it goes through a
        # code instead of the one-click button. Enrolling in a class that
        # isn't live yet (the normal "add a scheduled class" case) is
        # unaffected, since there is nothing live to verify against.
        active_session = SessionRepository.get_active_session(
            db,
            classroom.class_id,
        )

        if active_session and not face_verification_state.consume_verification(
            student_id, classroom.class_id
        ):
            raise Exception(
                "Face verification required before joining this class."
            )

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

