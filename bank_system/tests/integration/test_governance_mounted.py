"""Governance writes through the composed orchestrator never 500.

Starlette does not run a mounted sub-app's lifespan, so the governance app's
``current_canon_status`` must be loaded by the orchestrator's own lifespan;
without it the canon-enforcement middleware raised AttributeError on every
mutating request. The governance unit tests set that state by hand, so only a
test through ``bank.orchestrator.main.app`` sees the regression.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import uuid

import pytest

_d = tempfile.mkdtemp(prefix="orch_gov_")
os.environ["BANK_ORCH_DB_PATH"] = os.path.join(_d, "orch.db")

import bank.orchestrator.config as _orch_config
_orch_config.get_orchestrator_settings.cache_clear()
importlib.reload(_orch_config)
import bank.orchestrator.main as _orch_main
importlib.reload(_orch_main)


@pytest.mark.asyncio
async def test_mounted_governance_loads_canon_status_and_writes_do_not_500() -> None:
    from starlette.testclient import TestClient

    with TestClient(_orch_main.app) as client:
        assert _orch_main._mounts["/governance"].state.current_canon_status

        # An unknown id writes nothing: the gate answers 409 (canon not
        # ratified) or the route answers 404 — never an unhandled 500.
        resp = client.post(
            f"/governance/api/v1/pending/{uuid.uuid4()}/resolve",
            json={"resolution_notes": "probe", "governance_reference": None},
        )
        assert resp.status_code in (404, 409), resp.text
