from sqlalchemy.orm import Session

from models.teacher import Teacher


class TeacherRepository:

    @staticmethod
    def get_by_email(db: Session, email: str):

        return (
            db.query(Teacher)
            .filter(Teacher.email == email)
            .first()
        )

    @staticmethod
    def get_by_id(db: Session, teacher_id: int):
        return (
            db.query(Teacher)
            .filter(Teacher.teacher_id == teacher_id)
            .first()
        )

    @staticmethod
    def create_teacher(db: Session, teacher: Teacher):

        db.add(teacher)

        db.commit()

        db.refresh(teacher)

        return teacher

