"""
Application settings for the FastAPI backend.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "student_engagement_db"

    secret_key: str = "change-this-in-production"
    access_token_expire_minutes: int = 60

    # Comma-separated list of additional CORS origins allowed on top of the
    # always-on localhost/127.0.0.1 regex (see app/main.py) -- e.g. the
    # deployed Vercel frontend's URL. Empty by default so local dev is
    # unaffected until this is actually set in production.
    frontend_origin: str = ""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
