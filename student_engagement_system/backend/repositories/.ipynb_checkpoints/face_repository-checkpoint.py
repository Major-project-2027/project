from sqlalchemy.orm import Session

from models.face_registration import FaceRegistration


class FaceRepository:

    @staticmethod
    def get_face_by_student_id(db: Session, student_id: int):
        return (
            db.query(FaceRegistration)
            .filter(FaceRegistration.student_id == student_id)
            .first()
        )

    @staticmethod
    def save_face_embedding(
        db: Session,
        student_id: int,
        embedding
    ):

        face = FaceRegistration(
            student_id=student_id,
            embedding=embedding
        )

        db.add(face)
        db.commit()
        db.refresh(face)

        return face

    @staticmethod
    def update_face_embedding(
        db: Session,
        student_id: int,
        embedding
    ):

        face = (
            db.query(FaceRegistration)
            .filter(FaceRegistration.student_id == student_id)
            .first()
        )

        face.embedding = embedding

        db.commit()
        db.refresh(face)

        return face

    @staticmethod
    def delete_face(db: Session, student_id: int):

        face = (
            db.query(FaceRegistration)
            .filter(FaceRegistration.student_id == student_id)
            .first()
        )

        if face:
            db.delete(face)
            db.commit()

