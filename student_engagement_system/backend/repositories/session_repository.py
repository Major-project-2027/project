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
    def get_all_active_sessions(db: Session):
        """Every session currently marked live, across every teacher and
        class -- used to let any authenticated student discover and join
        a live class without needing its code."""

        return (
            db.query(ClassSession)
            .filter(ClassSession.is_active == True)
            .order_by(ClassSession.start_time.desc())
            .all()
        )

    @staticmethod
    def end_session(db: Session, session):

        session.is_active = False

        db.commit()

        db.refresh(session)

        return session

