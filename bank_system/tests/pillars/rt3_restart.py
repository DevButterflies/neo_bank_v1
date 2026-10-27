"""P3 in-process restart round-trip through the production KvStore facade.

Byte-exact mirror of rt4.py (GREEN) against P3Runtime: originate a
Pillar 2 output packet through the real p2_gate inside P3Runtime.run(fn),
persist, then open a FRESH P3Runtime on the same SQLite file and assert
the rehydrated engine re-encodes to a byte-identical snapshot. This is the
exact Pillar 3 half of the orchestrator's ``/ready`` story
(:func:`bank.orchestrator.main.ready`).
"""

import asyncio
import json
import os
import tempfile

from bank.pillars.api.codec import encode
from bank.pillars.api.p3 import P3Runtime, STORAGE_KEY
from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    MaturityStage,
    P2PacketStatus,
)
from bank.pillars.p3.domain.packet import P2OutputPacket

SEED = P2OutputPacket(
    packet_id="P2-P3-RT-1",
    facility_id="FAC-P3-RT-1",
    status=P2PacketStatus.APPROVED,
    maturity_stage=MaturityStage.SANDBOX,
    brr_pd_grid_version="BRR-GRID-2026-04",
    collateral_track=CollateralTrack.TRACK_1_CLASSICAL,
    packet_version="v1",
)


async def main() -> None:
    d = tempfile.mkdtemp(prefix="rt3_")
    db = os.path.join(d, "p3.db")

    a = P3Runtime(db)
    await a.load()
    await a.run(lambda o: o.originate(SEED))
    snap_before = encode(await a._snapshot())
    print(
        "originated facilities:",
        len(a._ensure_engine()._facilities),
    )
    print("snapshot bytes:", len(json.dumps(snap_before)))

    b = P3Runtime(db)  # fresh process on the same file
    await b.load()
    snap_after = encode(await b._snapshot())
    print(
        "restarted facilities:",
        len(b._ensure_engine()._facilities),
    )
    print("snapshots identical:", snap_before == snap_after)

    stored = await b.store.get_json(STORAGE_KEY)
    print("stored == snapshot:", stored == snap_after)
    assert snap_before == snap_after, "P3 restart lost state"
    assert stored == snap_after, "stored blob drifted"
    print("P3 ROUND-TRIP OK")


asyncio.run(main())
