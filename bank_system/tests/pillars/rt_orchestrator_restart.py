"""Orchestrator-level restart round-trip over the ONE shared KvStore file.

Byte-exact mirror of :func:`bank.orchestrator.main.ready`: open a fresh
``P3Runtime`` and ``P4Runtime`` over the same SQLite file the two mounted
pillar apps persist to, feed ONE risk packet through each pillar's real
adapter (P3 ``p2_gate`` / P4 ``ports.p2``), assert the persisted blobs,
then re-open BOTH runtimes again and assert each rehydrated engine
re-encodes to a byte-identical snapshot — the exact identity the
orchestrator's ``/ready`` probe proves (Canon §Ready, Build Handoff §5).
"""

import asyncio
import json
import os
import tempfile

from bank.orchestrator.config import get_orchestrator_settings

from bank.pillars.api.codec import encode
from bank.pillars.api.p3 import P3Runtime, STORAGE_KEY as P3_KEY
from bank.pillars.api.p4 import P4Runtime, STORAGE_KEY as P4_KEY

from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    MaturityStage,
    P2PacketStatus,
)
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p4.contracts.p2_inbound import (
    Pillar2RiskPacket,
    RequiredGuaranteeLevel,
    StagingSignal,
)
from bank.pillars.p4.domain.model_maturity import ModelStage

P3_SEED = P2OutputPacket(
    packet_id="P2-OR-P3-1",
    facility_id="FAC-OR-P3-1",
    status=P2PacketStatus.APPROVED,
    maturity_stage=MaturityStage.SANDBOX,
    brr_pd_grid_version="BRR-GRID-2026-04",
    collateral_track=CollateralTrack.TRACK_1_CLASSICAL,
    packet_version="v1",
)
P4_SEED = Pillar2RiskPacket(
    facility_ref="FAC-OR-P4-1",
    brr=0.012,
    pd=0.011,
    lgd=0.40,
    ead=180_000.0,
    el=2_000.0,
    model_maturity_stage=ModelStage.SANDBOX,
    brr_pd_grid_version="BRR-GRID-2026-04",
)
P4_STAGING = StagingSignal(
    facility_ref="FAC-OR-P4-1",
    stage=3,
    packet_ref="P2-OR-P4-1",
)
P4_REQUIRED = RequiredGuaranteeLevel(
    required_amount=100_000.0,
    revision_ref="REV-OR-P4-1",
    published_at=None,
)


async def main() -> None:
    d = tempfile.mkdtemp(prefix="or_")
    db = os.path.join(d, "orchestrator.db")

    p3a = P3Runtime(db)
    p4a = P4Runtime(db)
    await p3a.load()
    await p4a.load()
    await p3a.run(lambda o: o.originate(P3_SEED))
    await p4a.run(lambda o: o.ports.p2.feed_risk_packet(P4_SEED))
    await p4a.run(
        lambda o: o.ports.p2.feed_staging_signal(
            P4_STAGING.facility_ref, P4_STAGING.stage, P4_STAGING.packet_ref
        )
    )
    await p4a.run(
        lambda o: o.ports.p2.feed_required_guarantee_level(
            P4_REQUIRED.required_amount, P4_REQUIRED.revision_ref
        )
    )
    p3_before = encode(await p3a._snapshot())
    p4_before = encode(await p4a._snapshot())
    print(
        "p3 facilities:",
        len(p3a._ensure_engine()._facilities),
    )
    print(
        "p4 track1 breached:",
        len(p4a._ensure_engine().veto_engine.state.track1.breached_triggers),
    )

    # Exact /ready shape: fresh runtimes over the same file.
    p3b = P3Runtime(db)
    await p3b.load()
    p3_after = encode(await p3b._snapshot())
    p4b = P4Runtime(db)
    await p4b.load()
    p4_after = encode(await p4b._snapshot())
    print(
        "restarted p3 facilities:",
        len(p3b._ensure_engine()._facilities),
    )
    print(
        "restarted p4 track1 breached:",
        len(p4b._ensure_engine().veto_engine.state.track1.breached_triggers),
    )
    print("p3 snapshots identical:", p3_before == p3_after)
    print("p4 snapshots identical:", p4_before == p4_after)

    p3_stored = await p3b.store.get_json(P3_KEY)
    p4_stored = await p4b.store.get_json(P4_KEY)
    print("p3 stored == snapshot:", p3_stored == p3_after)
    print("p4 stored == snapshot:", p4_stored == p4_after)

    assert p3_before == p3_after, "orchestrator P3 restart lost state"
    assert p4_before == p4_after, "orchestrator P4 restart lost state"
    assert p3_stored == p3_after, "orchestrator p3 stored blob drifted"
    assert p4_stored == p4_after, "orchestrator p4 stored blob drifted"
    print("ORCHESTRATOR ROUND-TRIP OK")


asyncio.run(main())
