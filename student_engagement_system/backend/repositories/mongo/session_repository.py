try:
    from database.mongo import COLLECTION_CLASS_SESSIONS
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_CLASS_SESSIONS
try:
    from database.mongo_counters import next_id, COUNTER_SESSION_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_SESSION_ID
from models.session import Session as ClassSession
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class SessionRepository:

    @staticmethod
    def create_session(db, session: ClassSession):
        session.session_id = next_id(db, COUNTER_SESSION_ID)
        if session.start_time is None:
            session.start_time = utcnow()
        if session.is_active is None:
            session.is_active = True

        db[COLLECTION_CLASS_SESSIONS].insert_one({
            "session_id": session.session_id,
            "class_id": session.class_id,
            "teacher_id": session.teacher_id,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "is_active": session.is_active,
        })

        return session

    @staticmethod
    def get_active_session(db, class_id: int):
        return doc_to_model(
            ClassSession,
            db[COLLECTION_CLASS_SESSIONS].find_one(
                {"class_id": class_id, "is_active": True}
            ),
        )

    @staticmethod
    def get_all_active_sessions(db):
        return docs_to_models(
            ClassSession,
            db[COLLECTION_CLASS_SESSIONS]
            .find({"is_active": True})
            .sort("start_time", -1),
        )

    @staticmethod
    def end_session(db, session: ClassSession):
        """Always stamps its OWN real timestamp here, ignoring whatever
        the caller may have already set on session.end_time --
        SessionService.end_session sets it to a SQLAlchemy
        sqlalchemy.sql.functions.now() expression object (a query
        construct, not a real value; only resolved to an actual
        timestamp by a real SQL flush + db.refresh()) before calling
        this, which is meaningless/unserializable for MongoDB."""

        session.is_active = False
        session.end_time = utcnow()

        db[COLLECTION_CLASS_SESSIONS].update_one(
            {"session_id": session.session_id},
            {"$set": {"is_active": False, "end_time": session.end_time}},
        )

        return session

    @staticmethod
    def get_by_id(db, session_id: int):
        return doc_to_model(
            ClassSession, db[COLLECTION_CLASS_SESSIONS].find_one({"session_id": session_id})
        )

    @staticmethod
    def get_latest_session_for_class(db, class_id: int):
        doc = (
            db[COLLECTION_CLASS_SESSIONS]
            .find({"class_id": class_id})
            .sort("session_id", -1)
            .limit(1)
        )
        docs = list(doc)
        return doc_to_model(ClassSession, docs[0]) if docs else None
