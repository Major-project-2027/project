from sqlalchemy.orm import Session

from models.student import Student


class StudentRepository:

    @staticmethod
    def get_by_email(db: Session, email: str):
        return (
            db.query(Student)
            .filter(Student.email == email)
            .first()
        )

    @staticmethod
    def get_by_usn(db: Session, usn: str):
        return (
            db.query(Student)
            .filter(Student.usn == usn)
            .first()
        )
    @staticmethod
    def get_student_by_email(db: Session, email: str):
        return (
            db.query(Student)
            .filter(Student.email == email)
            .first()
        )

    @staticmethod
    def create_student(db: Session, student: Student):

        db.add(student)

        db.commit()

        db.refresh(student)

        return student

