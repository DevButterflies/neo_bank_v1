"""Orchestrator package root.

The composed ASGI app lives at ``bank.orchestrator.main:app`` and is the
canonical uvicorn entry point.  It is *not* re-exported here to avoid the
circular import that fires a ``RuntimeWarning`` when invoked via
``python -m bank.orchestrator.main``.
"""

from bank.orchestrator.config import OrchestratorSettings, get_orchestrator_settings

settings = get_orchestrator_settings()

__all__ = ["settings", "OrchestratorSettings", "get_orchestrator_settings"]
