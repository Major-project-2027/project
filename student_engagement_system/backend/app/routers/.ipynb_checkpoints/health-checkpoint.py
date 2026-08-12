"""
Health-check router.
"""
from fastapi import APIRouter

from app.services.database import ping_database

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    """Report application liveness and database reachability.

    Returns:
        A dict with overall status and a database sub-status. This endpoint
        always returns HTTP 200 -- it reports health, it does not enforce it.
    """
    db_ok = await ping_database()
    return {
        "status": "ok",
        "database": "reachable" if db_ok else "unreachable",
    }
