from __future__ import annotations

import importlib
import os
import tempfile

import pytest


_d = tempfile.mkdtemp(prefix="orch_root_")
_db = os.path.join(_d, "orch.db")
os.environ["BANK_ORCH_DB_PATH"] = _db

# A minimal Vite-shaped build, so the test does not depend on `npm run build`.
_dist = os.path.join(_d, "dist")
os.makedirs(os.path.join(_dist, "assets"))
with open(os.path.join(_dist, "index.html"), "w", encoding="utf-8") as fh:
    fh.write('<div id="root"></div><script type="module" src="/app/assets/index-test.js"></script>')
with open(os.path.join(_dist, "assets", "index-test.js"), "w", encoding="utf-8") as fh:
    fh.write("console.log('app');")
os.environ["BANK_ORCH_FRONTEND_DIST"] = _dist

import bank.orchestrator.config as _orch_config
_orch_config.get_orchestrator_settings.cache_clear()
importlib.reload(_orch_config)
import bank.orchestrator.main as _orch_main
importlib.reload(_orch_main)


@pytest.mark.asyncio
async def test_root_serves_frontend_under_app() -> None:
    """``/`` redirects to the front end at ``/app/``, whose bundle is reachable.

    The assertions are about the *contract* — a mounted SPA shell plus a
    bundle that is actually reachable — not about hashed filenames.
    """
    import re
    from starlette.testclient import TestClient

    app = _orch_main.app
    with TestClient(app) as client:
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (302, 307), resp.text
        assert resp.headers["location"] == "/app/"

        resp = client.get("/app/")
        assert resp.status_code == 200, resp.text
        assert '<div id="root">' in resp.text

        match = re.search(r'src="(/app/assets/[^"]+\.js)"', resp.text)
        assert match, f"no module script referenced by the app index: {resp.text}"
        bundle = client.get(match.group(1))
        assert bundle.status_code == 200, bundle.text
        assert len(bundle.content) > 0


@pytest.mark.asyncio
async def test_client_routes_fall_back_to_shell_without_shadowing_api() -> None:
    """A refresh on a client route boots the SPA; the API paths it mirrors
    (``/bilan``, ``/governance``) keep answering as the API."""
    from starlette.testclient import TestClient

    app = _orch_main.app
    with TestClient(app) as client:
        for route in ("/app/bilan", "/app/governance", "/app/facilities"):
            resp = client.get(route)
            assert resp.status_code == 200, route
            assert '<div id="root">' in resp.text, route

        assert client.get("/app/assets/missing.js").status_code == 404
        assert client.get("/app/..%2F..%2Forch.db").text.startswith('<div id="root">')

        bilan = client.get("/bilan")
        assert bilan.status_code == 200
        assert "actif" in bilan.json()
