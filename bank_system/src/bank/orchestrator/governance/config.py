from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the governance DB to the project root so it always matches the
# orchestrator's ``data/orchestrator.db`` regardless of the working directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DB_PATH = _PROJECT_ROOT / "data" / "orchestrator.db"


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///" + _DB_PATH.as_posix()

    # App
    APP_NAME: str = "Orchestrator Governance Layer"
    APP_VERSION: str = "3.4.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Governance defaults
    DEFAULT_CANON_VERSION: str = "3.4"
    CANON_STATUS_RATIFIED: str = "RATIFIED"
    CANON_STATUS_PENDING: str = "PENDING"
    CANON_STATUS_SUPERSEDED: str = "SUPERSEDED"

    # Enforcement
    ENFORCE_CANON_RATIFIED: bool = True
    ENFORCE_SOLE_LOCUS: bool = True
    ENFORCE_PENDING_DISCIPLINE: bool = True

    # Create tables on startup (dev convenience). Use Alembic migrations in production.
    AUTO_CREATE_TABLES: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
