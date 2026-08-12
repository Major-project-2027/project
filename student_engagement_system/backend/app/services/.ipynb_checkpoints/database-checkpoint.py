"""
MongoDB connection management for the FastAPI backend.
"""
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_database() -> AsyncIOMotorDatabase:
    """Create (or reuse) the MongoDB client and return the database handle.

    Returns:
        The AsyncIOMotorDatabase instance for this application.
    """
    global _client, _db
    if _db is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
        _db = _client[settings.mongo_db_name]
        logger.info(f"MongoDB client created for database '{settings.mongo_db_name}'")
    return _db


async def close_database_connection() -> None:
    """Close the MongoDB client connection, if open."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed.")


async def ping_database() -> bool:
    """Attempt to ping MongoDB; returns False (not raises) if unreachable.

    This lets the /health endpoint report DB status without crashing the
    whole API when MongoDB is not yet running (expected in Phase 1).
    """
    try:
        db = await connect_to_database()
        await db.command("ping")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"MongoDB ping failed: {exc.__class__.__name__}: {exc}")
        return False
