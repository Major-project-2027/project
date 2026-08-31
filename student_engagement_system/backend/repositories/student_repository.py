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
    def get_by_id(db: Session, student_id: int):
        return (
            db.query(Student)
            .filter(Student.student_id == student_id)
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

    @staticmethod
    def get_usns_starting_with(db: Session, prefix: str):
        """Every existing usn beginning with `prefix` -- used by
        StudentService._generate_usn to find the next unused auto-
        generated USN. Extracted into its own repository method (rather
        than an inline query in the service) so it has a MongoDB
        equivalent too -- see repositories/mongo/student_repository.py."""

        return [
            usn for (usn,) in
            db.query(Student.usn).filter(Student.usn.like(f"{prefix}%")).all()
        ]

