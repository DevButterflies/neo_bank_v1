"""Pillar 2 microservice.

Pillar 2's reference FastAPI layer is stateless and already exposes the full
engine (/v1/score, /v1/brr-pd-grid, /v1/ews, /v1/cass-feed, overrides); it is
re-exported here as the deployable ASGI app with uniform logging wired in.
"""

from __future__ import annotations

from bank.core.config import Settings, get_settings
from bank.core.logging import setup_logging
from bank.pillars.p2.api import app  # noqa: F401

settings = get_settings()
setup_logging("pillar2", settings.log_level, settings.log_json)

__all__ = ["app"]