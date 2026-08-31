from sqlalchemy.orm import Session

from models.enrollment import Enrollment
from models.classroom import Classroom
from models.student import Student


class EnrollmentRepository:

    @staticmethod
    def join_class(db: Session, enrollment: Enrollment):

        db.add(enrollment)

        db.commit()

        db.refresh(enrollment)

        return enrollment

    @staticmethod
    def get_for_class(db: Session, class_id: int):
        return (
            db.query(Enrollment)
            .filter(Enrollment.class_id == class_id)
            .all()
        )

    @staticmethod
    def count_for_class(db: Session, class_id: int):
        return (
            db.query(Enrollment)
            .filter(Enrollment.class_id == class_id)
            .count()
        )

    @staticmethod
    def already_joined(db: Session, student_id: int, class_id: int):

        return (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.class_id == class_id
            )
            .first()
        )

    @staticmethod
    def get_student_classes(db: Session, student_id: int):

        return (
            db.query(Classroom)
            .join(
                Enrollment,
                Enrollment.class_id == Classroom.class_id
            )
            .filter(
                Enrollment.student_id == student_id
            )
            .all()
        )
    @staticmethod
    def get_teacher_students(db: Session, teacher_id: int):
        """Every distinct student enrolled in ANY of this teacher's
        classrooms -- the authorization-scoped student roster used by the
        teacher's Future Engagement Prediction list, so a teacher only
        ever sees students belonging to their own classes (same
        Classroom.teacher_id scoping already used throughout this
        project, e.g. class_history/get_teacher_classrooms)."""

        return (
            db.query(Student)
            .join(
                Enrollment,
                Enrollment.student_id == Student.student_id
            )
            .join(
                Classroom,
                Enrollment.class_id == Classroom.class_id
            )
            .filter(
                Classroom.teacher_id == teacher_id
            )
            .distinct()
            .all()
        )

    @staticmethod
    def count_teacher_students(db: Session, teacher_id: int):

        return (
            db.query(Enrollment)
            .join(
                Classroom,
                Enrollment.class_id == Classroom.class_id
            )
            .filter(
                Classroom.teacher_id == teacher_id
            )
            .count()
        )

