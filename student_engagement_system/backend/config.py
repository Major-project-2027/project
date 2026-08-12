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