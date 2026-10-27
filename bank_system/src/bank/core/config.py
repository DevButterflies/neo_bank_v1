"""Environment-driven settings shared by every microservice."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All bank services read env vars prefixed with ``BANK_``."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BANK_", extra="ignore")

    service_name: str = "bank-system"
    app_version: str = "3.4.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    log_level: str = "INFO"
    log_json: bool = False

    # Downstream service URLs (docker compose service names).
    pillar2_url: str = "http://localhost:8002"
    pillar3_url: str = "http://localhost:8003"
    pillar4_url: str = "http://localhost:8004"

    # Pillar engine persistence (per-service SQLite file).
    p2_engine_sqlite_path: str = "./data/pillar2.db"
    p3_engine_sqlite_path: str = "./data/pillar3.db"
    p4_engine_sqlite_path: str = "./data/pillar4.db"

    # Pillar 4 demo safety net (env BANK_P4_TRACK1_AUTO_LIFT_ON_SUSTAINED_CLEAN).
    # 0 (default) = governance-only standing freeze; N>0 auto-lifts a standing
    # Track-1 freeze after N consecutive clean recomputes so an unattended demo
    # never bricks on a now-clean book. Never fires while the live book is
    # still breached.
    p4_track1_auto_lift_on_sustained_clean: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()