"""P4 in-process restart round-trip through the production KvStore facade.

Byte-exact mirror of rt3.py (GREEN) against P4Runtime: feed a Facet2 risk
packet, a staging signal, and a required-guarantee-level through the real
ports.p2 adapters inside P4Runtime.run(fn), persist, then open a FRESH
P4Runtime on the same SQLite file and assert the rehydrated engine
re-encodes to a byte-identical snapshot.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone

from bank.pillars.api.codec import encode
from bank.pillars.api.p4 import P4Runtime, STORAGE_KEY
from bank.pillars.p4.contracts.p2_inbound import (
    Pillar2RiskPacket,
    RequiredGuaranteeLevel,
    StagingSignal,
)
from bank.pillars.p4.domain.model_maturity import ModelStage

SEED = Pillar2RiskPacket(
    facility_ref="FAC-P4-RT-1",
    brr=0.012,
    pd=0.011,
    lgd=0.40,
    ead=180_000.0,
    el=2_000.0,
    model_maturity_stage=ModelStage.SANDBOX,
    brr_pd_grid_version="BRR-GRID-2026-04",
)
STAGING = StagingSignal(
    facility_ref="FAC-P4-RT-1",
    stage=3,  # IFRS9 stage int (1/2/3); SANDBOX packet feeds the EL pool via stage 3
    packet_ref="P2-P4-RT-1",
)
REQUIRED = RequiredGuaranteeLevel(
    required_amount=100_000.0,
    revision_ref="REV-P4-RT-1",
    published_at=None,
)


async def main() -> None:
    d = tempfile.mkdtemp(prefix="rt4_")
    db = os.path.join(d, "p4.db")

    a = P4Runtime(db)
    await a.load()
    await a.run(lambda o: o.ports.p2.feed_risk_packet(SEED))
    await a.run(lambda o: o.ports.p2.feed_staging_signal(STAGING.facility_ref, STAGING.stage, STAGING.packet_ref))
    await a.run(lambda o: o.ports.p2.feed_required_guarantee_level(REQUIRED.required_amount, REQUIRED.revision_ref))
    snap_before = encode(await a._snapshot())
    print(
        "veto track1 breached triggers:",
        len(a._ensure_engine().veto_engine.state.track1.breached_triggers),
    )
    print("snapshot bytes:", len(json.dumps(snap_before)))

    b = P4Runtime(db)  # fresh process on the same file
    await b.load()
    snap_after = encode(await b._snapshot())
    print(
        "restarted track1 breached:",
        len(b._ensure_engine().veto_engine.state.track1.breached_triggers),
    )
    print("snapshots identical:", snap_before == snap_after)

    stored = await b.store.get_json(STORAGE_KEY)
    print("stored == snapshot:", stored == snap_after)
    assert snap_before == snap_after, "P4 restart lost state"
    assert stored == snap_after, "stored blob drifted"
    print("P4 ROUND-TRIP OK")


asyncio.run(main())
