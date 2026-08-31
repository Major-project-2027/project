"""Backend-agnostic db handle for routes/services.

Every Flask route currently does:
    db = SessionLocal()
    try:
        ...
    finally:
        db.close()

get_db()/close_db() replace SessionLocal()/db.close() with the same
2-line shape, but resolve to either a SQLAlchemy Session (DB_BACKEND=
sqlite, the default) or a pymongo Database (DB_BACKEND=mongodb) --
whichever is active. Nothing about the try/finally structure of any
route changes; only these two calls do.
"""

from config import DB_BACKEND


def get_db():
    if DB_BACKEND == "mongodb":
        try:
            from database.mongo import get_db as get_mongo_db
        except ModuleNotFoundError:
            from backend.database.mongo import get_db as get_mongo_db
        return get_mongo_db()

    try:
        from database.database import SessionLocal
    except ModuleNotFoundError:
        from backend.database.database import SessionLocal
    return SessionLocal()


def close_db(db):
    """No-op for MongoDB (the shared MongoClient is pooled and long-
    lived, not a per-request resource); closes the SQLAlchemy session
    for SQLite, exactly as every route already did."""

    if DB_BACKEND != "mongodb":
        db.close()


def is_mongo() -> bool:
    return DB_BACKEND == "mongodb"
