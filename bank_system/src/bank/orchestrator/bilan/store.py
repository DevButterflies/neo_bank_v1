"""Read-only access to the orchestrator KvStore snapshots.

``GET /bilan`` must never be able to perturb the live Pillar 3/4 runtimes, so
every read opens the SQLite file in **URI read-only mode**
(``file:<path>?mode=ro``). A read-only connection cannot create tables, cannot
write, and cannot block a concurrent writer beyond the instant of the read
itself.

Nothing here instantiates :class:`~bank.pillars.api.p3.P3Runtime` or
:class:`~bank.pillars.api.p4.P4Runtime` — the raw JSON blobs are walked
directly, which is enough because the fields the bilan needs (``amount``,
``memo``, ``balance``, ``ecl``, ``ead``) are plain JSON; only enums and
datetimes are tagged, and the single enum we inspect (``event_type``) carries
its value under ``"value"``.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

P3_KEY = "p3_state_v1"
P4_KEY = "p4_state_v1"


def _db_path() -> str:
    # Resolved per call (not at import time) so the env-var override applied by
    # the test suite before importing the orchestrator is always honoured.
    from bank.orchestrator.config import get_orchestrator_settings

    return get_orchestrator_settings().db_path


def read_json(key: str, db_path: str | None = None) -> Any | None:
    """Return ``json.loads`` of ``kv.value`` for ``key``, or ``None``.

    Every failure mode of a read — missing file, missing table, missing row,
    corrupt blob — degrades to ``None`` rather than raising, so a half-seeded
    database still serves a bilan (an empty one) instead of a 500.
    """
    path = db_path or _db_path()
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        try:
            row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        except sqlite3.Error:
            return None
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
    finally:
        conn.close()


def read_p3() -> dict:
    snap = read_json(P3_KEY)
    return snap if isinstance(snap, dict) else {}


def read_p4() -> dict:
    snap = read_json(P4_KEY)
    return snap if isinstance(snap, dict) else {}


def read_config() -> dict:
    from bank.orchestrator.bilan.config import CONFIG_KEY

    snap = read_json(CONFIG_KEY)
    return snap if isinstance(snap, dict) else {}
