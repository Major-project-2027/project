from sqlalchemy.orm import Session

from models.session import Session as ClassSession


class SessionRepository:

    @staticmethod
    def create_session(db: Session, session: ClassSession):

        db.add(session)

        db.commit()

        db.refresh(session)

        return session

    @staticmethod
    def get_active_session(db: Session, class_id: int):

        return (
            db.query(ClassSession)
            .filter(
                ClassSession.class_id == class_id,
                ClassSession.is_active == True
            )
            .first()
        )

    @staticmethod
    def end_session(db: Session, session):

        session.is_active = False

        db.commit()

        db.refresh(session)

        return session

