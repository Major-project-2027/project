from sqlalchemy.orm import Session

from models.enrollment import Enrollment
from models.classroom import Classroom


class EnrollmentRepository:

    @staticmethod
    def join_class(db: Session, enrollment: Enrollment):

        db.add(enrollment)

        db.commit()

        db.refresh(enrollment)

        return enrollment

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

