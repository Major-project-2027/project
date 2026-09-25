import sys
from pathlib import Path

# Backend modules import each other as top-level packages (services, app,
# models, ...), exactly as uvicorn runs them from backend/. The project root
# has same-named modules (app.py, models/), so backend/ must come first and
# these tests run as their own suite: python -m pytest backend/tests
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
