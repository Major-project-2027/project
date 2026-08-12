from sqlalchemy.orm import Session

from models.classroom import Classroom


class ClassroomRepository:

    @staticmethod
    def create_classroom(db: Session, classroom: Classroom):

        db.add(classroom)
        db.commit()
        db.refresh(classroom)

        return classroom

    @staticmethod
    def get_by_code(db: Session, class_code: str):

        return (
            db.query(Classroom)
            .filter(Classroom.class_code == class_code)
            .first()
        )

    @staticmethod
    def get_teacher_classrooms(db: Session, teacher_id: int):

        return (
            db.query(Classroom)
            .filter(Classroom.teacher_id == teacher_id)
            .all()
        )
    @staticmethod
    def get_classroom_by_id(db: Session, class_id: int):

        return (
            db.query(Classroom)
            .filter(Classroom.class_id == class_id)
            .first()
        )
    
    @staticmethod
    def get_by_id(db: Session, class_id: int):

        return (
            db.query(Classroom)
            .filter(Classroom.class_id == class_id)
            .first()
        )


    @staticmethod
    def update_classroom(db: Session, classroom):

        db.commit()

        db.refresh(classroom)

        return classroom
    @staticmethod
    def delete_classroom(db: Session, classroom: Classroom):

        db.delete(classroom)

        db.commit()
    
    @staticmethod
    def count_teacher_classes(db: Session, teacher_id: int):

        return (
            db.query(Classroom)
            .filter(
                Classroom.teacher_id == teacher_id
            )
            .count()
        )

