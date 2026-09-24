from models.enrollment import Enrollment

from repositories.active import (
    ClassroomRepository,
    EnrollmentRepository,
    SessionRepository,
    StudentRepository,
)
from services import face_verification_state
from services.access_control import (
    AccessDenied,
    NOT_AUTHORIZED_TO_JOIN,
    require_class_owner,
    require_student_allowed,
)


class EnrollmentService:
    """A class's enrollment rows are its allowed-student list. Only the
    class's teacher grants them (set_allowed_students); the join
    endpoints below require an existing grant and never create one."""

    @staticmethod
    def join_live_class(db, student_id, class_id):
        """Direct join for the "Live Classes" dashboard flow -- no class
        code required. Only allowed for a student the teacher permitted,
        and only while the class actually has an active session.

        Also the backend-enforced anti-bypass gate for Feature 2: this is
        THE join endpoint the "Join class" button calls, so it is where
        face verification is actually required and consumed -- a request
        that never passed /face/verify-live for this exact
        (student_id, class_id) is rejected here regardless of anything
        the client claims, because consume_verification() can only
        return True if the backend itself recorded a real match.
        """

        classroom, active_session = require_student_allowed(
            db, student_id, class_id, require_live=True
        )

        if not face_verification_state.consume_verification(student_id, class_id):
            raise Exception(
                "Face verification required before joining this class."
            )

        return classroom, active_session

    @staticmethod
    def join_class(db, student_id, class_code):
        """Open a class by its code (or numeric id, which the dashboard and
        the live page use). Succeeds only for a student the class's
        teacher permitted; no longer enrolls the student itself."""

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
            raise AccessDenied(NOT_AUTHORIZED_TO_JOIN)

        require_student_allowed(db, student_id, classroom.class_id)

        return classroom

    @staticmethod
    def get_student_classes(db, student_id):

        return EnrollmentRepository.get_student_classes(
            db,
            student_id
        )

    # ------------------------------------------------------------------
    # Teacher-managed allowed-student list
    # ------------------------------------------------------------------

    @staticmethod
    def get_allowed_students(db, teacher_id, class_id):
        require_class_owner(db, teacher_id, class_id)
        return EnrollmentRepository.student_ids_for_class(db, class_id)

    @staticmethod
    def set_allowed_students(db, teacher_id, class_id, student_ids):
        """Replace the class's allowed-student list with `student_ids`.
        While the class is live, students can be added but not removed,
        so nobody currently in the class is unexpectedly cut off."""

        require_class_owner(db, teacher_id, class_id)

        wanted = {int(s) for s in student_ids}
        for student_id in wanted:
            if not StudentRepository.get_by_id(db, student_id):
                raise Exception(f"Student {student_id} does not exist.")

        current = set(EnrollmentRepository.student_ids_for_class(db, class_id))
        to_remove = current - wanted

        if to_remove and SessionRepository.get_active_session(db, class_id):
            raise Exception(
                "Students can't be removed while this class is live. "
                "You can still add students, or change the list after the class ends."
            )

        for student_id in sorted(wanted - current):
            EnrollmentRepository.join_class(
                db,
                Enrollment(student_id=student_id, class_id=class_id),
            )

        for student_id in sorted(to_remove):
            EnrollmentRepository.remove(db, student_id, class_id)

        return sorted(wanted)
