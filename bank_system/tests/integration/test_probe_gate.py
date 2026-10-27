from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_probe_gate_script_runs() -> None:
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    pythonpath = str(root / "src")
    existing = env.get("PYTHONPATH")
    if existing:
        env["PYTHONPATH"] = pythonpath + os.pathsep + existing
    else:
        env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, str(root / "probe_gate.py")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "seeded p3/p4 snapshots" in result.stdout
    assert "health 200" in result.stdout
    assert "ready 200" in result.stdout
