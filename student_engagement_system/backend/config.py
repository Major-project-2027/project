import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# =====================================================
# Flask
# =====================================================

SECRET_KEY = os.getenv("SECRET_KEY")

# =====================================================
# Database
# =====================================================

DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_PATH = BASE_DIR / DATABASE_NAME

# =====================================================
# MongoDB (migration target -- see database/mongo.py)
# =====================================================
# The existing SQLite database (DATABASE_PATH above) remains the
# application's live database until the migration is verified and the
# application layer is explicitly switched over. These two settings are
# read by database/mongo.py to connect; never hard-code a connection
# string/credentials here or anywhere else. MONGO_URI is expected to be
# a MongoDB Atlas URI (mongodb+srv://...) but any valid MongoDB
# connection string works identically for local testing.

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

# Which database backend the APPLICATION actually reads/writes.
# "sqlite" (default -- the safe rollback value) or "mongodb". Flipping
# this back to "sqlite" (or removing/blanking it) and restarting both
# the Flask and FastAPI processes is the complete rollback mechanism --
# no code changes required, since the SQLite implementation is never
# removed, only bypassed while this is "mongodb".
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()
if DB_BACKEND not in ("sqlite", "mongodb"):
    DB_BACKEND = "sqlite"

# =====================================================
# Internal service-to-service calls
# =====================================================
# The Flask process notifies the separate FastAPI process (the AI/live-
# monitoring pipeline) over HTTP -- see services/session_service.py. In
# local dev both processes are on 127.0.0.1; in production (Render) they
# are two different services with their own hostnames, so this must be
# configurable. Default preserves the exact previous hardcoded behavior.
FASTAPI_INTERNAL_URL = os.getenv("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8000")

# =====================================================
# AI Models
# =====================================================

FACE_MODEL = os.getenv("FACE_MODEL")
EMOTION_MODEL = os.getenv("EMOTION_MODEL")
LANDMARK_MODEL = os.getenv("LANDMARK_MODEL")
YOLO_MODEL = os.getenv("YOLO_MODEL")

# =====================================================
# Project Paths
# =====================================================

PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT"))

LOG_FOLDER = Path(os.getenv("LOG_FOLDER"))
REPORT_FOLDER = Path(os.getenv("REPORT_FOLDER"))
UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER"))

# =====================================================
# Create folders automatically
# =====================================================

LOG_FOLDER.mkdir(parents=True, exist_ok=True)
REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)