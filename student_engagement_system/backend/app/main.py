"""
FastAPI application factory for the Student Engagement Monitoring System.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
from app.core.config import get_settings
from app.routers import health
from app.routers import face_authentication
from app.routers import emotion
from app.routers import head_pose
from app.routers import object_detection
from app.routers import engagement_prediction
from app.routers import cognitive_monitoring
from app.routers import monitoring
from app.services.database import close_database_connection
from utils.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance.

    Future phases register additional routers here (authentication,
    emotion, engagement, dashboard, ...) following the same pattern as
    `health`.

    Returns:
        A fully configured FastAPI app.
    """
    settings = get_settings()
    app = FastAPI(
        title="Student Engagement Monitoring System",
        description="Predictive Multimodal Student Engagement and Cognitive Monitoring System API",
        version="0.1.0-phase1",
        debug=settings.app_debug,
    )
    app.add_middleware(
    CORSMiddleware,
    # Vite falls back to the next free port (5174, 5175, ...) whenever
    # 5173 is already taken by another dev-server instance, which
    # silently broke every /ai/analyze-frame call: Starlette's
    # CORSMiddleware rejects the preflight OPTIONS request with 400 for
    # any origin not in the list, the browser's fetch() then fails
    # before the POST is ever sent, and the frontend's live-monitoring
    # loop -- which is otherwise running correctly -- just keeps
    # catching that failure every tick. Matching any localhost/127.0.0.1
    # port covers this without hand-maintaining a port list; still local
    # dev origins only, same as before.
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

    app.include_router(health.router)
    app.include_router(face_authentication.router)
    app.include_router(emotion.router)
    app.include_router(head_pose.router)
    app.include_router(object_detection.router)
    app.include_router(engagement_prediction.router)
    app.include_router(cognitive_monitoring.router)
    app.include_router(monitoring.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler so an unexpected error never leaks a raw traceback."""
        logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await close_database_connection()

    @app.get("/")
    async def root() -> dict:
        """Root endpoint -- simple API identity confirmation."""
        return {"service": app.title, "version": app.version, "phase": 1}

    return app


app = create_app()


# --- Phase 8: Dashboard & Analytics (additive; appended by
# Phase8_Dashboard_Analytics.ipynb) --------------------------------------
from app.routers import dashboard
from fastapi.staticfiles import StaticFiles as _Phase8StaticFiles
from pathlib import Path as _Phase8Path

if "dashboard" not in [getattr(r, "name", "") for r in app.routes]:
    app.include_router(dashboard.router)

_phase8_frontend_dir = _Phase8Path(__file__).resolve().parents[2] / "frontend"
if _phase8_frontend_dir.is_dir():
    app.mount(
        "/dashboard-ui",
        _Phase8StaticFiles(directory=str(_phase8_frontend_dir), html=True),
        name="dashboard-ui",
    )
