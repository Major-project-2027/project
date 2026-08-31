"""Shared helpers for the MongoDB repository implementations.

Every route/service accesses returned rows via ATTRIBUTE access
(teacher.teacher_id, classroom.class_code, student.name, ...), never
dict indexing -- confirmed by reading every call site before writing
these repositories. So each Mongo repository method returns instances
of the SAME SQLAlchemy model classes the SQL repositories use (Teacher,
Student, Classroom, Session, ...), NOT raw dicts. Constructing a model
instance without adding it to any SQLAlchemy Session keeps it
"transient": a plain, unpersisted Python object that happens to share
its class (and therefore its exact attribute names) with the SQL path,
so field names can never silently drift out of sync between the two
backends.

Timestamp fields that are `server_default=func.now()` in the SQL models
(created_at, joined_at, ...) are never set by SQLAlchemy until a real
flush/commit against a real engine -- since Mongo repositories never do
that, this module also provides `utcnow()` so every "create" method
fills those fields in Python, consistently, the same way `db.refresh()`
would have.
"""

from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


def doc_to_model(model_class, doc):
    """Hydrate a MongoDB document into a transient instance of
    `model_class`, dropping Mongo's own `_id` (which that model class
    has no column for). Returns None if `doc` is None (mirrors
    SQLAlchemy's .first() returning None)."""

    if doc is None:
        return None

    fields = {k: v for k, v in doc.items() if k != "_id"}
    return model_class(**fields)


def docs_to_models(model_class, docs):
    return [doc_to_model(model_class, doc) for doc in docs]
