"""A.1 gate — orchestrator ASGI restart-ok story, end to end.

Opens the real :data:`bank.orchestrator.main.app` through a Starlette
``TestClient`` (which runs the app's ``lifespan`` — the same manual
``os.makedirs`` of the KvStore parent dir that ``uvicorn`` triggers at boot),
persists real Pillar 3/4 snapshots over the orchestrator's KvStore file, then
asserts:

* ``GET /health``  -> 200 with the orchestrator's advertised app/version, and
* ``GET /ready``   -> 200, the *byte-identical restart* probe that re-opens
  fresh Pillar 3/4 runtimes over the **same** file and compares the rehydrated
  snapshot to the persisted blob (the round-trip proved byte-exact by
  ``tests/pillars/rt4_restart.py``).

The ``BANK_ORCH_DB_PATH`` env is set *before* importing the app because
``bank.orchestrator.config.settings`` is cached at import time.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

_d = tempfile.mkdtemp(prefix="orch_a1_")
_db = os.path.join(_d, "orch.db")
# The /ready probe re-opens `settings.db_path` (orchestrator_main.ready),
# so the seeded file MUST be that path — set it before importing the app,
# because bank.orchestrator.config settings are cached at import time.
os.environ["BANK_ORCH_DB_PATH"] = _db

# Under the FULL suite, tests/governance/conftest.py imports
# bank.orchestrator.config first (via the package __init__), caching
# `settings` with the DEFAULT db_path before this module's env set above
# runs. Clear the lru_cache and reload config + main so every settings
# reference (config.settings and orchestrator_main.ready) honors the seed.
import importlib

import bank.orchestrator.config as _orch_config
_orch_config.get_orchestrator_settings.cache_clear()
importlib.reload(_orch_config)
import bank.orchestrator.main as _orch_main
importlib.reload(_orch_main)


@pytest.mark.asyncio
async def test_orchestrator_ready_restart_ok() -> None:
    from bank.orchestrator.config import settings as orch_settings
    from bank.orchestrator.main import app
    from bank.pillars.api.p3 import P3Runtime
    from bank.pillars.api.p4 import P4Runtime

    assert orch_settings.db_path == _db

    p3 = P3Runtime(_db)
    p4 = P4Runtime(_db)
    await p3.load()
    await p4.load()
    # Persist a real snapshot on both mounted sub-apps' shared KvStore file.
    await p3.run(lambda o: None)
    await p4.run(lambda o: None)

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "ok"
        assert body["app"] == orch_settings.app_name
        assert body["version"] == orch_settings.app_version

        ready = client.get("/ready")
        assert ready.status_code == 200, ready.text
        checks = ready.json()["checks"]
        assert checks["p3_restart_ok"] is True
        assert checks["p4_restart_ok"] is True
