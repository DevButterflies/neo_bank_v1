"""Orchestrator runtime settings.

Env prefix: ``BANK_ORCH_``. The orchestrator owns one KvStore SQLite file
(:attr:`OrchestratorSettings.db_path`) that the mounted Pillar 3/4 sub-apps
share — the "one file survives restart byte-identical" story that
:func:`bank.orchestrator.main.ready` asserts by reopening fresh runtimes over
the same file (the exact round-trip proved by :file:`tests/pillars/rt3_restart.py`
and :file:`rt4_restart.py`).

Mount prefixes are deliberately *not* settings here: they are plain constants
in :mod:`bank.orchestrator.main` so the mounted-app map cannot drift from the
ASGI import it advertises (``bank.orchestrator.main:app``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the shared DB file to the project root so launching the orchestrator
# from any working directory always resolves to the SAME ``data/orchestrator.db``
# (a CWD-relative default silently split the demo state across two files).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = str(_PROJECT_ROOT / "data" / "orchestrator.db")


class OrchestratorSettings(BaseSettings):
    """Runtime configuration for the orchestrator ASGI app."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BANK_ORCH_", extra="ignore"
    )

    app_name: str = "bank-orchestrator"
    app_version: str = "3.4.0"
    log_level: str = "INFO"
    db_path: str = _DB_PATH

    # Number of byte-identical-restart checks the ``/ready`` probe must pass.
    ready_assertions: int = 2

    # Import the demo candidates at startup from ``data/candidates/*.json``
    # (the canonical portable export carrier; no code-hardcoded profiles).
    # Default is empty start — set BANK_ORCH_SEED_DEMO=true to preload.
    seed_demo: bool = False

    # Governance-approved initial Tier D (common equity + Perpetual AT1) capital
    # base. Applied to P4 on first boot when tier_d_amount is 0 (uninitialized).
    # Set BANK_ORCH_INITIAL_TIER_D_AMOUNT to override.
    initial_tier_d_amount: float = 100_000.0

    # Demo safety net passed to the mounted Pillar 4 app: auto-lift a standing
    # Track-1 freeze after N consecutive clean recomputes so an unattended demo
    # never bricks on a now-clean book (Rule-B interim-book freezes). The
    # orchestrator is the demo host and defaults ON (=2); a standalone Pillar 4
    # keeps governance-only semantics (core setting default 0). Never fires
    # while the live book is still breached. 0 disables.
    # Set BANK_ORCH_P4_TRACK1_AUTO_LIFT_ON_SUSTAINED_CLEAN to override.
    p4_track1_auto_lift_on_sustained_clean: int = 2

    # Shared secret for ``PUT /bilan/config``, the one bilan path that writes
    # and that moves cash on both faces. Unset means the endpoint refuses
    # every request (secure by default) rather than staying wide open.
    # Set BANK_ORCH_BILAN_ADMIN_TOKEN to enable it.
    bilan_admin_token: str | None = None

    # Built CCC-NeoBank front end, served under /app/ when present. Defaults to
    # ``frontend/dist`` beside this project (``npm run build`` in frontend/).
    # Set BANK_ORCH_FRONTEND_DIST to serve another build.
    frontend_dist: str = str(_PROJECT_ROOT.parent / "frontend" / "dist")


@lru_cache
def get_orchestrator_settings() -> OrchestratorSettings:
    return OrchestratorSettings()


settings = get_orchestrator_settings()
