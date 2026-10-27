"""A.1 boot smoke — the *literal README command* works, over real HTTP.

Everything else in the suite proves the round-trip in-process (Starlette
``TestClient`` runs the same lifespan). This tape is the one probe the others
don't cover: spawn the real :program:`uvicorn` subprocess exactly as the
backend README advertises —

    uvicorn bank.orchestrator.main:app --host 0.0.0.0 --port 8000

— over a fresh temp KvStore file that was **pre-seeded** by real Pillar 3/4
runtimes, then poll ``/health`` and ``/ready`` over plain HTTP and assert the
booted orchestrator answers ``status == "ok"`` with both restart probes true.

This is the exact boot path a demo web app (or a human with a browser at
``http://localhost:8000``) will rely on: ``/ready`` re-opens fresh P3/P4
runtimes over the *same* file the seeded snapshot above was persisted to, so a
passing tape here is the "tapeless demo first-boot" promise.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import pytest

_d = tempfile.mkdtemp(prefix="orch_boot1_")
_db = os.path.join(_d, "orch.db")

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC = os.path.join(_REPO, "src")
_ROOT = os.path.dirname(_REPO)  # repo root (parent of bank_system)
_VENV_PY = sys.executable


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_orchestrator_boot_over_real_http() -> None:
    # Seed the KvStore file with real Pillar 3/4 snapshots first, so /ready
    # (which re-opens fresh runtimes over this exact path) has a blob to
    # rehydrate byte-identically.
    from bank.pillars.api.p3 import P3Runtime
    from bank.pillars.api.p4 import P4Runtime

    p3 = P3Runtime(_db)
    p4 = P4Runtime(_db)
    await p3.load()
    await p4.load()
    await p3.run(lambda o: None)
    await p4.run(lambda o: None)

    port = _free_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC
    env["BANK_ORCH_DB_PATH"] = _db

    proc = subprocess.Popen(
        [
            _VENV_PY,
            "-m",
            "uvicorn",
            "bank.orchestrator.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        health = None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"uvicorn exited early ({proc.returncode}):\n{out}")
            try:
                with httpx.Client(timeout=2) as client:
                    health = client.get(f"{base}/health")
                if health.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        assert health is not None and health.status_code == 200, health

        body = health.json()
        assert body["status"] == "ok"
        assert body["app"] == "bank-orchestrator"

        with httpx.Client(timeout=5) as client:
            ready = client.get(f"{base}/ready")
        assert ready.status_code == 200, ready.text
        checks = ready.json()["checks"]
        assert checks["p3_restart_ok"] is True
        assert checks["p4_restart_ok"] is True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
