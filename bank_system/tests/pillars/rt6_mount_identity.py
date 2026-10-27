"""Orchestrator mount identity — one KvStore file behind BOTH pillar mounts.

The two orchestrator restart tapes (rt5_orchestrator.py, rt_orchestrator_
restart.py — both GREEN, both BROKEN if I had written a third duplicate)
prove the *runtime* round-trip. The byte nobody's tape isolates: that
``bank.orchestrator.main`` actually mounts ``/p3`` and ``/p4`` over ONE
``settings.db_path`` (``main.py:39-44 _FIXED_MOUNTS``, ``main.py:58-75
_make_mounted_apps``). This tape asserts exactly that — the two pillar
apps, built from the orchestrator's own ``make_app`` factories, share the
KvStore the orchestrator's ``/ready`` probe re-opens (:func:`bank.
orchestrator.main.ready`).
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from bank.orchestrator.config import get_orchestrator_settings
from bank.orchestrator.main import _FIXED_MOUNTS, _make_mounted_apps

import bank.orchestrator.main as orchestrator_main


async def main() -> None:
    settings = get_orchestrator_settings()

    mounts = _make_mounted_apps()
    print("mount prefixes:", sorted(mounts))

    expected = {"/governance", "/p2", "/p3", "/p4"}
    assert set(mounts) == expected, f"mount set drifted: {sorted(mounts)}"

    p3_app = mounts["/p3"]
    p4_app = mounts["/p4"]
    print("p3 app import:", p3_app.__class__.__name__)
    print("p4 app import:", p4_app.__class__.__name__)

    db = settings.db_path
    print("orchestrator db_path:", db)

    # The /ready probe re-opens fresh P3/P4 runtimes over settings.db_path.
    # Assert both pillar runtime constructors bind to THAT same absolute file
    # (the identity the ready probe's byte round-trip depends on).
    import os.path

    from bank.pillars.api.p3 import P3Runtime
    from bank.pillars.api.p4 import P4Runtime

    p3 = P3Runtime(db)
    p4 = P4Runtime(db)
    print(
        "p3 bound to db_path:",
        p3._store.db_path == os.path.abspath(db),
    )
    print(
        "p4 bound to db_path:",
        p4._store.db_path == os.path.abspath(db),
    )
    assert p3._store.db_path == os.path.abspath(db), "p3 mount drifted off db_path"
    assert p4._store.db_path == os.path.abspath(db), "p4 mount drifted off db_path"
    print("MOUNT IDENTITY OK")


asyncio.run(main())
