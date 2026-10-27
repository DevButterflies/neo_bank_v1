from __future__ import annotations

import importlib
import os
import tempfile

import pytest


_d = tempfile.mkdtemp(prefix="orch_root_")
_db = os.path.join(_d, "orch.db")
os.environ["BANK_ORCH_DB_PATH"] = _db

import bank.orchestrator.config as _orch_config
_orch_config.get_orchestrator_settings.cache_clear()
importlib.reload(_orch_config)
import bank.orchestrator.main as _orch_main
importlib.reload(_orch_main)


@pytest.mark.asyncio
async def test_root_serves_demo_index() -> None:
    """``/`` serves the built demo surface (``demo/dist``, a Vite SPA).

    ``bank.orchestrator.main`` prefers the Vite build over the legacy
    ``demo/static`` page whenever ``demo/dist`` exists, so the shipped page is
    the SPA shell. The assertions are deliberately about the *contract* — a
    mounted root that renders, plus a bundle that is actually reachable — not
    about the hashed filenames or the page title, which move on every rebuild.
    """
    import re
    from starlette.testclient import TestClient

    app = _orch_main.app
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200, resp.text
        assert '<div id="root">' in resp.text
        assert "/assets/" in resp.text

        match = re.search(r'src="(/assets/[^"]+\.js)"', resp.text)
        assert match, f"no module script referenced by the demo index: {resp.text}"
        bundle = client.get(match.group(1))
        assert bundle.status_code == 200, bundle.text
        assert len(bundle.content) > 0
