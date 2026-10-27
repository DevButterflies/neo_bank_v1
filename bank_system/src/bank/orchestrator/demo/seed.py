"""Demo seed — populates the orchestrator's shared KvStore file with real data.

Drives the **actual** Pillar 3/4 engines through their production facades
(``P3Runtime.run`` / ``P4Runtime.run``) over the orchestrator's one KvStore
file (:attr:`bank.orchestrator.config.OrchestratorSettings.db_path`), the same
file ``/ready`` re-opens. No fabricated blobs: every row is produced by engine
operations (originate / pledge-collateral / disburse / repayment, plus P4 risk
packets, staging signals and required-guarantee-level feeds) exactly as the
``/p3`` and ``/p4`` HTTP routes would, so the seeded state is what the demo
web UI will read back.

Facility story (every persistable LoanState represented):

=============  ===========  ==========================================================
facility       state        story
=============  ===========  ==========================================================
FAC-DEMO-001   ACTIVE       $20k disbursed, clean, IFRS9 Stage 2 staging signal
FAC-DEMO-002   REPAYING     $35k, three scheduled repayments (interest + principal)
FAC-DEMO-003   CLOSED       workout: delinquent -> default -> recovery $8k -> closed
FAC-DEMO-004   DELINQUENT   one on-time payment, then missed (drawdowns frozen)
FAC-DEMO-005   DEFAULT      delinquent -> default marker (IFRS9 Stage 3)
FAC-DEMO-006   RECOVERY     workout rests in recovery: $4.5k recovered so far
FAC-DEMO-007   APPROVED     originated + collateral pledged, not yet disbursed
FAC-DEMO-008   ACTIVE       restructured (workout-authorized); audit shows the
                            RESTRUCTURING transient -> ACTIVE
=============  ===========  ==========================================================

RESTRUCTURING is a transient intermediate (the restructure transition moves
straight to ACTIVE), so no resting facility sits in that state — FAC-DEMO-008
demonstrates it through its audit trail.

Re-runnable: the engine is re-instantiated from an empty file every run (the
file is overwritten with the fresh snapshot), and a final restart check
re-opens fresh runtimes to prove the persisted blob rehydrates byte-identically.

Run:  python -m bank.orchestrator.demo.seed  (from repo root, ``PYTHONPATH=src``)
"""

from __future__ import annotations

import asyncio
import json
import os

from bank.orchestrator.config import settings

from bank.pillars.api.codec import encode
from bank.pillars.api.p3 import P3Runtime, STORAGE_KEY as P3_KEY
from bank.pillars.api.p4 import P4Runtime, STORAGE_KEY as P4_KEY

from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    MaturityStage,
    P2PacketStatus,
)
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p4.contracts.p2_inbound import Pillar2RiskPacket
from bank.pillars.p4.domain.model_maturity import ModelStage


def _make_packet(*, packet_id: str, facility_id: str, workout: bool = False) -> P2OutputPacket:
    return P2OutputPacket(
        packet_id=packet_id,
        facility_id=facility_id,
        status=P2PacketStatus.APPROVED,
        maturity_stage=MaturityStage.SANDBOX,
        brr_pd_grid_version="BRR-GRID-2026-04",
        collateral_track=CollateralTrack.TRACK_1_CLASSICAL,
        packet_version="v1",
        officer_confirmed=True,
        officer_id="OFFICER-1",
        human_authorised_for_workout=workout,
    )


def _risk_packet(*, facility_ref: str, brr: float, pd: float, lgd: float, ead: float) -> Pillar2RiskPacket:
    return Pillar2RiskPacket(
        facility_ref=facility_ref,
        brr=brr,
        pd=pd,
        lgd=lgd,
        ead=ead,
        el=brr * pd * lgd * ead,
        model_maturity_stage=ModelStage.SANDBOX,
        brr_pd_grid_version="BRR-GRID-2026-04",
    )


async def seed() -> dict:
    db = settings.db_path
    parent = os.path.dirname(os.path.abspath(db))
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(db):
        os.remove(db)

    p3 = P3Runtime(db)
    p4 = P4Runtime(db)
    await p3.load()
    await p4.load()

    amount_map = {
        "FAC-DEMO-001": 20_000.0,
        "FAC-DEMO-002": 35_000.0,
        "FAC-DEMO-003": 12_500.0,
        "FAC-DEMO-004": 10_000.0,
        "FAC-DEMO-005": 15_000.0,
        "FAC-DEMO-006": 9_000.0,
        "FAC-DEMO-007": 25_000.0,
        "FAC-DEMO-008": 18_000.0,
    }

    # 1) Originate + pledge collateral on every facility; disburse all but the
    #    APPROVED showcase (FAC-DEMO-007 stays originated-not-disbursed).
    for idx, facility_id in enumerate(amount_map, start=1):
        packet = _make_packet(packet_id=f"DEMO-{idx:03d}", facility_id=facility_id)
        await p3.run(lambda o, p=packet: o.originate(p))
        await p3.run(
            lambda o, p=packet, fid=facility_id: o.pledge_collateral(
                fid, p, external_reference=f"title-deed-{facility_id}"
            )
        )
        if facility_id == "FAC-DEMO-007":
            continue
        amount = amount_map[facility_id]
        await p3.run(lambda o, p=packet, fid=facility_id, a=amount: o.disburse(fid, p, a, "USD"))

    # 2) FAC-DEMO-002 -> REPAYING: three scheduled repayments.
    packet = _make_packet(packet_id="DEMO-002-A", facility_id="FAC-DEMO-002")
    for _ in range(3):
        await p3.run(
            lambda o, p=packet: o.record_repayment("FAC-DEMO-002", p, 150.0, 500.0, "USD")
        )

    # 3) FAC-DEMO-004 -> DELINQUENT: one on-time payment, then missed.
    packet = _make_packet(packet_id="DEMO-004-A", facility_id="FAC-DEMO-004")
    await p3.run(lambda o, p=packet: o.record_repayment("FAC-DEMO-004", p, 80.0, 250.0, "USD"))
    await p3.run(lambda o, p=packet: o.mark_delinquent("FAC-DEMO-004", p))

    # 4) FAC-DEMO-005 -> DEFAULT: marker event, drawdowns frozen.
    packet = _make_packet(packet_id="DEMO-005-A", facility_id="FAC-DEMO-005")
    await p3.run(lambda o, p=packet: o.mark_delinquent("FAC-DEMO-005", p))
    await p3.run(lambda o, p=packet: o.mark_default("FAC-DEMO-005", p))

    # 5) FAC-DEMO-006 -> RECOVERY: workout-authorized, rests in recovery.
    packet = _make_packet(packet_id="DEMO-006-A", facility_id="FAC-DEMO-006", workout=True)
    await p3.run(lambda o, p=packet: o.mark_delinquent("FAC-DEMO-006", p))
    await p3.run(lambda o, p=packet: o.mark_default("FAC-DEMO-006", p))
    await p3.run(lambda o, p=packet: o.initiate_recovery("FAC-DEMO-006", p, 4_500.0, "USD"))

    # 6) FAC-DEMO-003 -> CLOSED via full workout path.
    packet = _make_packet(packet_id="DEMO-003-A", facility_id="FAC-DEMO-003", workout=True)
    await p3.run(lambda o: o.mark_delinquent("FAC-DEMO-003", packet))
    await p3.run(lambda o: o.mark_default("FAC-DEMO-003", packet))
    await p3.run(lambda o: o.initiate_recovery("FAC-DEMO-003", packet, 8_000.0, "USD"))
    await p3.run(lambda o: o.close("FAC-DEMO-003", packet))

    # 7) FAC-DEMO-008 -> ACTIVE after workout-authorized restructure
    #    (audit shows RESTRUCTURING transient -> ACTIVE).
    packet = _make_packet(packet_id="DEMO-008-A", facility_id="FAC-DEMO-008")
    for _ in range(2):
        await p3.run(
            lambda o, p=packet: o.record_repayment("FAC-DEMO-008", p, 90.0, 300.0, "USD")
        )
    await p3.run(lambda o, p=packet: o.mark_delinquent("FAC-DEMO-008", p))
    packet = _make_packet(packet_id="DEMO-008-B", facility_id="FAC-DEMO-008", workout=True)
    await p3.run(lambda o, p=packet: o.restructure("FAC-DEMO-008", p))

    # 8) Pillar 4 feeds: one risk packet per facility, staging signals for the
    #    IFRS9 journey (1 -> 2 on FAC-DEMO-001/004, 3 on the DEFAULT showcase),
    #    and the required pooled-guarantee level.
    risk_rows = [
        ("FAC-DEMO-001", 0.012, 0.011, 0.40, 180_000.0),
        ("FAC-DEMO-002", 0.010, 0.009, 0.38, 160_000.0),
        ("FAC-DEMO-003", 0.020, 0.019, 0.45, 95_000.0),
        ("FAC-DEMO-004", 0.030, 0.028, 0.50, 88_000.0),
        ("FAC-DEMO-005", 0.045, 0.042, 0.55, 92_000.0),
        ("FAC-DEMO-006", 0.040, 0.038, 0.52, 90_000.0),
        ("FAC-DEMO-007", 0.008, 0.007, 0.35, 150_000.0),
        ("FAC-DEMO-008", 0.025, 0.024, 0.48, 96_000.0),
    ]
    for facility_ref, brr, pd, lgd, ead in risk_rows:
        await p4.run(
            lambda o, fr=facility_ref, b=brr, pd_=pd, l=lgd, e=ead: (
                o.ports.p2.feed_risk_packet(_risk_packet(facility_ref=fr, brr=b, pd=pd_, lgd=l, ead=e))
            )
        )

    for facility_ref, stage in [
        ("FAC-DEMO-001", 2),
        ("FAC-DEMO-002", 1),
        ("FAC-DEMO-004", 2),
        ("FAC-DEMO-005", 3),
    ]:
        await p4.run(
            lambda o, fr=facility_ref, s=stage: (
                o.ports.p2.feed_staging_signal(fr, s, f"STG-{fr}")
            )
        )

    await p4.run(
        lambda o: o.ports.p2.feed_required_guarantee_level(100_000.0, "REV-DEMO-1")
    )

    # 9) Governance canonical content (same sqlite file, idempotent): canon
    #    V3.4 lineage, lexicon, tiers, interface rules, staging/mode registry,
    #    PENDING register, CASS stub, pillar boundaries — everything the /governance
    #    tab reads. Tables are created then seeded (seeder is self-skipping).
    from bank.orchestrator.governance.database import init_models
    from bank.orchestrator.governance.seed.seed import run_seed as run_governance_seed

    await init_models()
    await run_governance_seed()

    # Restart proof: fresh runtimes over the same file must rehydrate identically.
    p3_before = encode(await p3._snapshot())
    p4_before = encode(await p4._snapshot())

    p3b = P3Runtime(db)
    p4b = P4Runtime(db)
    await p3b.load()
    await p4b.load()
    p3_after = encode(await p3b._snapshot())
    p4_after = encode(await p4b._snapshot())

    assert p3_before == p3_after, "p3 demo snapshot lost state on restart"
    assert p4_before == p4_after, "p4 demo snapshot lost state on restart"
    assert await p3b.store.get_json(P3_KEY) == p3_after
    assert await p4b.store.get_json(P4_KEY) == p4_after

    o = p3b._ensure_engine()
    return {
        "db_path": db,
        "facilities": len(o._facilities),
        "audit_records": len((await p3b._snapshot())["audit_records"]),
        "p4_el_pool_balance": p4b._ensure_engine().capital.snapshot(
            p4b._ensure_engine().buffer_service.account, p4b._ensure_engine().pool
        ).el_pool_balance,
        "restart_p3_identical": p3_before == p3_after,
        "restart_p4_identical": p4_before == p4_after,
        "bytes_written": len(json.dumps(p3_after)) + len(json.dumps(p4_after)),
    }


async def main() -> None:
    summary = await seed()
    print("--- DEMO SEED COMPLETE ---")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())