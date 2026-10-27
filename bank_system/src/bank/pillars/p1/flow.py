"""P1 demo flow engine — submit -> score -> approve -> disburse + P3/P4 mirrors.

The orchestrator's approve step ALWAYS requires manual officer sign-off
(MANUAL_APPROVAL_ALWAYS = True). Once approved, disbursement can proceed
immediately — in this demo there is no separate P4 guarantee-gate.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bank.pillars.p2.engine import Pillar2Engine
from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    MaturityStage as P3MaturityStage,
    P2PacketStatus,
)
from bank.pillars.p3.domain.packet import P2OutputPacket as P3Packet

from bank.pillars.p1 import applications
from bank.pillars.p1.behavior_gen import generate_behavior
from bank.pillars.p1.models import Candidate
from bank.pillars.p1.p2_to_p3 import facility_id_for, translate_packet
from bank.pillars.p1.service import (
    CandidateStateError,
    CandidateNotFoundError,
    service,
)
from bank.pillars.p1.mirror import (
    mirror_close,
    mirror_default,
    mirror_disburse,
    mirror_recovery,
    mirror_repayment,
    mirror_risk_packet,
    mirror_staging_signal,
    p4_runtime,
)

# ---- configuration ----------------------------------------------------------
MANUAL_APPROVAL_ALWAYS: bool = True

# ---- P2 re-use --------------------------------------------------------------

_P2_ENGINE = Pillar2Engine()

# ---- serialisation helpers for the P3 packet stored in sim_state ----------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def packet_to_dict(p: P3Packet) -> dict:
    return {
        "packet_id": p.packet_id,
        "facility_id": p.facility_id,
        "status": p.status.value,
        "maturity_stage": p.maturity_stage.value,
        "brr_pd_grid_version": p.brr_pd_grid_version,
        "collateral_track": p.collateral_track.value,
        "packet_version": p.packet_version,
        "officer_confirmed": p.officer_confirmed,
        "officer_id": p.officer_id,
        "human_authorised_for_workout": p.human_authorised_for_workout,
        "issued_at": p.issued_at.isoformat(),
    }


def dict_to_packet(d: dict) -> P3Packet:
    return P3Packet(
        packet_id=d["packet_id"],
        facility_id=d["facility_id"],
        status=P2PacketStatus(d["status"]),
        maturity_stage=P3MaturityStage(d["maturity_stage"]),
        brr_pd_grid_version=d["brr_pd_grid_version"],
        collateral_track=CollateralTrack(d["collateral_track"]),
        packet_version=d["packet_version"],
        officer_confirmed=d.get("officer_confirmed", False),
        officer_id=d.get("officer_id"),
        human_authorised_for_workout=d.get("human_authorised_for_workout", False),
        issued_at=datetime.fromisoformat(d["issued_at"]),
    )


def _sim_defaults(packet_dict: dict) -> dict:
    return {
        "current_month": 0,
        "p3_packet": packet_dict,
        "payments_made": [],
        "defaulted": False,
        "delinquent": False,
        "closed": False,
        "recoveries": [],
    }


def _recovery_packet(packet_dict: dict) -> P3Packet:
    d = dict(packet_dict)
    d["officer_confirmed"] = True
    d["officer_id"] = "SYSTEM"
    d["human_authorised_for_workout"] = True
    return dict_to_packet(d)


# ---- lifecycle actions -------------------------------------------------------


async def submit(candidate_id: str) -> dict:
    """Score via P2 and store results on candidate.

    The risk packet is NOT booked into the P4 capital book here — exposure
    enters P4 at DISBURSEMENT (commitment is not yet funded). So submit never
    changes the portfolio and is never blocked by a freeze.
    """
    cand = await service.get(candidate_id)
    if cand.status != "new":
        raise CandidateStateError(
            f"Candidate {candidate_id} has status '{cand.status}'; "
            "must be 'new' to submit."
        )
    app = applications.build_application(cand)
    result = _P2_ENGINE.score(app)
    p2 = result.packet
    fac = facility_id_for(candidate_id)
    now = _utcnow()
    await service.update_status(
        candidate_id,
        "scored",
        submitted_at=now,
        scored_at=now,
        application_id=p2.application_id,
        facility_id=fac,
        p2_brr=p2.brr,
        p2_pd=p2.pd,
        p2_lgd=p2.lgd,
        p2_ead=p2.ead,
        p2_el=p2.expected_loss,
        p2_zone=result.zone.value,
        p2_packet_status=p2.status.value,
    )
    return {
        "candidate_id": candidate_id,
        "facility_id": fac,
        "application_id": p2.application_id,
        "zone": result.zone.value,
        "brr": p2.brr,
        "pd": p2.pd,
        "lgd": p2.lgd,
        "ead": p2.ead,
        "el": p2.expected_loss,
        "status": "scored",
        "packet_status": p2.status.value,
        "confirmed": True,
    }


async def approve(candidate_id: str, decision: dict) -> dict:
    """Manual officer approve/reject. On approve: originate in P3, optionally
    pledge collateral, prepare sim_state.

    The risk packet is not booked into P4 here — exposure enters P4 at
    DISBURSEMENT. Approve therefore never changes the portfolio and is never
    blocked by a freeze.
    """
    cand = await service.get(candidate_id)
    if cand.status != "scored":
        raise CandidateStateError(
            f"Candidate {candidate_id} has status '{cand.status}'; "
            "must be 'scored' to approve."
        )
    approve_flag = decision.get("approve", True)
    officer_id = decision.get("officer_id", "OFFICER-1")
    officer_name = decision.get("officer_name", "Demo Officer")
    note = decision.get("note", "")

    if not approve_flag:
        fac = cand.facility_id or facility_id_for(candidate_id)
        # Defensive: release any P4 exposure the candidate may carry. With
        # disbursement-booking nothing is registered pre-funding, so this is an
        # idempotent no-op; it is kept so a reject always retires exposure.
        if cand.facility_id is not None:
            await mirror_close(fac)
        await service.update_status(
            candidate_id,
            "rejected",
            approval_note=note,
            approved_by=officer_name,
            approved_at=_utcnow(),
        )
        return {"approved": False, "candidate_id": candidate_id, "status": "rejected"}

    # Re-score deterministically to obtain a fresh packet object.
    app = applications.build_application(cand)
    result = _P2_ENGINE.score(app)
    fac = cand.facility_id or facility_id_for(candidate_id)
    p3_packet = translate_packet(
        result.packet,
        facility_id=fac,
        officer_confirmed=True,
        officer_id=officer_id,
    )

    # Originate in P3 (approve + enter governance gate — auto consumed here).
    from bank.pillars.p3.governance.maturity_gate import ProductionAutoApproval

    await _p3_run(
        lambda o: o.originate(
            p3_packet,
            production_auto_approval=ProductionAutoApproval(
                approved_by_p4=True, orchestrator_notified=True
            ),
        )
    )

    # Pledge collateral if the application carries any.
    if getattr(app, "collateral", None):
        await _p3_run(
            lambda o: o.pledge_collateral(fac, p3_packet, external_reference=None)
        )

    # Prepare simulation state so disburse / tick have a packet to work with.
    await service.set_sim_state(candidate_id, _sim_defaults(packet_to_dict(p3_packet)))
    await service.update_status(
        candidate_id,
        "approved",
        approved_at=_utcnow(),
        approved_by=officer_name,
        approval_note=note,
    )
    return {
        "approved": True,
        "candidate_id": candidate_id,
        "facility_id": fac,
        "packet_id": p3_packet.packet_id,
        "status": "approved",
    }


async def disburse(candidate_id: str, amount: float | None = None, currency: str = "USD") -> dict:
    """Disburse the facility after approval. Records the PRINCIPAL_MOVEMENT.

    Disbursement is where the exposure ENTERS the P4 book: the P2 risk packet
    is registered (EAD + EL), IFRS9 staging 1 mirrors the provision, then the
    money moves. It is also the funding gate — a P4 freeze blocks any further
    disbursement until the portfolio clears.
    """
    cand = await service.get(candidate_id)
    if cand.status not in ("approved", "active", "disbursing"):
        raise CandidateStateError(
            f"Candidate {candidate_id} has status '{cand.status}'; "
            "must be 'approved' to disburse."
        )
    behavior = service.hydrate_behavior(cand)
    disbursed = amount or behavior.disbursed
    packet = dict_to_packet(cand.sim_state["p3_packet"]) if cand.sim_state else None
    if packet is None:
        raise CandidateStateError(
            f"Candidate {candidate_id} missing sim_state[p3_packet] — "
            "approve must complete before disburse."
        )
    # P4 veto gate: a freeze (portfolio or facility-level) blocks disburse —
    # no money out of a frozen portfolio (exposure may not enter a frozen book).
    cons = await p4_runtime().run(
        lambda p4: p4.ports.p2.consult_veto(cand.facility_id)
    )
    if cons.any_frozen:
        raise CandidateStateError(
            f"P4 Track-1 veto active for {cand.facility_id}: disbursement "
            "is rejected by the standing portfolio freeze (non-overridable "
            "by P2/P3). A governance review must lift it before booking."
        )
    # Book the exposure NOW (was at submit/approve) — register the P2 risk
    # packet and IFRS9 Stage 1 provision so RWA / portfolio EL reflect the
    # funded book at the moment the money goes out.
    app = applications.build_application(cand)
    result = _P2_ENGINE.score(app)
    fac = cand.facility_id

    # Atomic claim: only ONE concurrent disburse may move approved→disbursing.
    # A second request (double-click / retry-on-timeout) reads status no longer
    # "approved" and fails fast instead of double-funding the facility.
    claimed = await service.try_transition(candidate_id, "approved", "disbursing")
    if not claimed:
        claimed = await service.try_transition(candidate_id, "active", "disbursing")
    if not claimed:
        raise CandidateStateError(
            f"Candidate {candidate_id} is no longer in a disburseable state "
            "(a concurrent disbursement was detected); "
            "refusing to run the disbursement twice."
        )
    try:
        mirror = await mirror_risk_packet(
            fac,
            brr=result.packet.brr,
            pd=result.packet.pd,
            lgd=result.packet.lgd,
            ead=result.packet.ead,
            el=result.packet.expected_loss,
            model_stage=result.packet.model_maturity_stage.value,
            packet_ref=result.packet.application_id,
            grid_version=result.packet.pd_grid_version,
            product_type=getattr(app.facility.product, "value", None),
        )
        if not mirror.get("confirmed", True):
            # The book froze mid-flight (e.g. another facility breached it between
            # our gate check and this registration): roll back and do not fund.
            await mirror_close(fac)
            raise CandidateStateError(
                f"P4 Track-1 veto active for {fac}: the portfolio froze while "
                "this disbursement was being booked; the exposure was rolled "
                "back and no money left a frozen book."
            )
        await mirror_staging_signal(fac, 1, packet.packet_id)
        await _p3_run(lambda o: o.disburse(fac, packet, disbursed, currency))
        await service.update_status(
            candidate_id,
            "disbursed",
            disbursed_at=_utcnow(),
        )
        # Refresh sim_state with initial month counter and the global month
        # where this facility was first funded. This keeps repayment timing
        # relative to disbursement instead of the bank-wide simulation clock.
        from bank.pillars.p1.simulator import load_sim_month

        sim = dict(cand.sim_state or {})
        sim["disbursed_at_month"] = await load_sim_month()
        sim["current_month"] = 0
        await service.set_sim_state(candidate_id, sim)
        # Mirror the disbursement into P4 so the portfolio recomputes the live
        # book (and the guarantee GRANTED enters the pool's visibility).
        await mirror_disburse(fac, float(disbursed))
    except Exception:
        try:
            await mirror_close(fac)
        except Exception:
            pass
        # Compensating transition: put the candidate back to 'approved' so a
        # failed disbursement remains retryable instead of being stuck in the
        # transient 'disbursing' state.
        try:
            await service.try_transition(candidate_id, "disbursing", "approved")
        except Exception:
            pass
        raise
    return {
        "candidate_id": candidate_id,
        "facility_id": fac,
        "amount": disbursed,
        "currency": currency,
        "status": "disbursed",
    }


async def _p3_run(fn):
    from bank.pillars.p1.mirror import p3_runtime
    return await p3_runtime().run(fn)
