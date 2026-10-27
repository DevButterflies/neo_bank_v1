"""Pillar 4 microservice — guarantee buffer, veto engine, and mode gate.

Wraps the unmodified :class:`Pillar4` facade in a REST API. Persistent state
(buffer sub-accounts, guarantee pool, veto state, registered risk packets,
IFRS9 staging, mode gate, Intra-P4 event log) is stored as a JSON snapshot in
one per-service SQLite file and rehydrated on restart. Transport and storage
only; the engine logic is untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException

from bank.core.api import build_app
from bank.core.config import Settings, get_settings
from bank.core.logging import setup_logging

from bank.pillars.api.codec import decode, encode, to_wire
from bank.pillars.api.schemas_common import ErrorOut
from bank.pillars.api.schemas_p4 import (
    BufferBalancesOut,
    CapitalSnapshotOut,
    ConfirmPacketOut,
    FacilityRefOut,
    IntraP4EventOut,
    LiftTrack1Out,
    ModeAckOut,
    ModeStatusOut,
    Pillar3EventAckOut,
    PledgeAckOut,
    PledgeSubmitOut,
    PoolAdequacyOut,
    RecomputeTrack1Out,
    RevisionAckOut,
    StagingAckOut,
    TierDAckOut,
    Track2ResultOut,
    VetoConsultOut,
    VetoNotificationOut,
)
from bank.pillars.api.storage import KvStore

from bank.pillars.p4.contracts.p2_inbound import (
    Pillar2RiskPacket,
    RequiredGuaranteeLevel,
    StagingSignal,
)
from bank.pillars.p4.contracts.p5_inbound import PledgeSubmission
from bank.pillars.p4.domain.buffer_account import SubAccount, SubAccountId
from bank.pillars.p4.domain.events import IntraP4Event, IntraP4EventType, Pillar3Event
from bank.pillars.p4.domain.guarantee_pool import PledgePosition, PledgeReleaseState
from bank.pillars.p4.domain.model_maturity import ModelStage
from bank.pillars.p4.domain.mode_state import ModeGate
from bank.pillars.p4.domain.pending import PendingNotResolvedError
from bank.pillars.p4.domain.tiers import TierPosition
from bank.pillars.p4.domain.veto import TriggerType, Track, Track2State, VetoStatus
from bank.pillars.p4.integration.pillar4 import Pillar4
from bank.pillars.p4.mode_gate.mode_gate import GovernanceRuling, ModeGateError
from bank.pillars.p4.part1_core_prudential.ifrs9_staging import FacilityStaging
from bank.pillars.p4.part2_guarantee_buffer.guarantee_pool_service import (
    AdmissibilityPolicyError,
)
from bank.pillars.p4.part2_guarantee_buffer.pledge_release import (
    PledgeReleaseError,
    ReleaseInvariantViolationError,
)

settings: Settings = get_settings()

STORAGE_KEY = "p4_state_v1"

_CLASSES = {
    cls.__name__: cls
    for cls in (
        PledgePosition,
        Pillar2RiskPacket,
        FacilityStaging,
        IntraP4Event,
    )
}
_ENUMS = {
    cls.__name__: cls
    for cls in (
        ModelStage,
        PledgeReleaseState,
        TierPosition,
        IntraP4EventType,
    )
}

_SUB_ACCOUNT_ATTR = {
    SubAccountId.EL_POOL: "el_pool",
    SubAccountId.ULA_BUFFER: "ula_buffer",
    SubAccountId.LIQUIDITY_RESERVE: "liquidity_reserve",
    SubAccountId.RP_POOL: "rp_pool",
}


class P4Runtime:
    """Holds the Pillar 4 facade plus its durable snapshot."""

    def __init__(
        self,
        db_path: str,
        *,
        track1_auto_lift_on_sustained_clean: int | None = None,
    ) -> None:
        self.store = KvStore(db_path)
        self.p4: Pillar4 | None = None
        self._loaded = False
        # Demo knob: auto-lift a standing Track-1 freeze after N consecutive
        # clean recomputes. None -> the banking Settings value (env
        # BANK_P4_TRACK1_AUTO_LIFT_ON_SUSTAINED_CLEAN, default 0 = never).
        self.track1_auto_lift_on_sustained_clean = (
            settings.p4_track1_auto_lift_on_sustained_clean
            if track1_auto_lift_on_sustained_clean is None
            else int(track1_auto_lift_on_sustained_clean)
        )

    def _ensure_engine(self) -> Pillar4:
        if self.p4 is None:
            self.p4 = Pillar4(
                in_memory_ports=True,
                auto_lift_on_sustained_clean=self.track1_auto_lift_on_sustained_clean,
            )
        return self.p4

    async def load(self) -> None:
        self._ensure_engine()
        snap = await self.store.get_json(STORAGE_KEY)
        if snap:
            self._apply(snap)
        self._loaded = True

    def _apply(self, snap: dict) -> None:
        p4 = self._ensure_engine()

        account = p4.buffer_service.account
        for sid_key, data in snap["account"].items():
            sid = SubAccountId(sid_key)
            sub = SubAccount(sid)
            sub.balance = data["balance"]
            sub.tier_attribution = dict(data["tier_attribution"])
            sub.stage2_socket_active = data["stage2_socket_active"]
            setattr(account, _SUB_ACCOUNT_ATTR[sid], sub)

        pool = p4.pool
        pool.positions[:] = [
            decode(p, _CLASSES, _ENUMS) for p in snap["pool"]["positions"]
        ]
        pool.required_level = snap["pool"]["required_level"]
        pool.required_level_revision = snap["pool"]["required_level_revision"]
        pool.received_guarantee_book = snap["pool"]["received_book"]
        pool.given_guarantee_book = snap["pool"]["given_book"]

        v = p4.veto_engine
        v.state.track1.status = VetoStatus(snap["veto"]["track1_status"])
        v.state.track1.breached_triggers = {
            TriggerType(k): reason
            for k, reason in snap["veto"]["breached_triggers"].items()
        }
        v.state.track1.freeze_details = dict(
            snap["veto"].get("freeze_details", {})
        )
        v.state.track1.frozen_since = decode(
            snap["veto"]["track1_frozen_since"], _CLASSES, _ENUMS
        )
        v.state.track2.clear()
        for fac, data in snap["veto"]["track2"].items():
            st = Track2State()
            st.status = VetoStatus(data["status"])
            st.breached_policy = data["policy"]
            st.frozen_since = decode(data["frozen_since"], _CLASSES, _ENUMS)
            v.state.track2[fac] = st
        v.state.notification_log.entries[:] = decode(
            snap["veto"]["notification_entries"], _CLASSES, _ENUMS
        )
        v.notifier.notifications[:] = decode(snap["veto"]["notifier"], _CLASSES, _ENUMS)
        v._governance_review_pending = {
            Track(key): val
            for key, val in snap["veto"]["governance_review_pending"].items()
        }

        p4.capital._packets = {
            k: decode(v, _CLASSES, _ENUMS)
            for k, v in snap["capital"]["packets"].items()
        }
        p4.capital.tier_d_amount = snap["capital"]["tier_d_amount"]
        p4.capital._budgeted_loss_amount = snap["capital"]["budgeted_loss_amount"]
        p4.capital.tier_d_floor = snap["capital"]["tier_d_floor"]
        p4.capital.budgeted_loss_ratio = snap["capital"]["budgeted_loss_ratio"]

        p4.ifrs9._facilities.clear()
        for fac, data in snap["ifrs9"].items():
            p4.ifrs9._facilities[fac] = FacilityStaging(
                facility_ref=fac,
                stage=data["stage"],
                ecl=data["ecl"],
                ead=data["ead"],
                el=data["el"],
                pd=data.get("pd", 0.0),
                lgd=data.get("lgd", 0.0),
            )

        gate: ModeGate = p4.mode_gate._gate
        gate._mode = snap["mode"]["mode"]
        gate.governance_events[:] = decode(
            snap["mode"]["governance_events"], _CLASSES, _ENUMS
        )

        p4._event_log[:] = [decode(e, _CLASSES, _ENUMS) for e in snap["event_log"]]

        pr = p4.pledge_release
        pr.origination_held = snap["pledge"]["origination_held"]
        pr.replacement_intake_available = snap["pledge"]["replacement_intake_available"]
        pr.pre_term_exception_approved = snap["pledge"]["pre_term_exception_approved"]
        pr._pending_track1_on_ratio_breach = tuple(snap["pledge"]["pending_track1"])

        p4.custody._given_book_adjustments[:] = snap["custody"]["given_book_adjustments"]

    async def _snapshot(self) -> dict:
        p4 = self._ensure_engine()
        account = p4.buffer_service.account
        pool = p4.pool
        v = p4.veto_engine
        return {
            "account": {
                sid.value: {
                    "balance": sub.balance,
                    "tier_attribution": sub.tier_attribution,
                    "stage2_socket_active": sub.stage2_socket_active,
                }
                for sid, sub in account.all_sub_accounts().items()
            },
            "pool": {
                "positions": [encode(p) for p in pool.positions],
                "required_level": pool.required_level,
                "required_level_revision": pool.required_level_revision,
                "received_book": pool.received_guarantee_book,
                "given_book": pool.given_guarantee_book,
            },
            "veto": {
                "track1_status": v.state.track1.status.value,
                "breached_triggers": {
                    t.value: reason for t, reason in v.state.track1.breached_triggers.items()
                },
                "freeze_details": {
                    t: dict(d) for t, d in v.state.track1.freeze_details.items()
                },
                "track1_frozen_since": encode(v.state.track1.frozen_since),
                "track2": {
                    fac: {
                        "status": st.status.value,
                        "policy": st.breached_policy,
                        "frozen_since": encode(st.frozen_since),
                    }
                    for fac, st in v.state.track2.items()
                },
                "notification_entries": encode(v.state.notification_log.entries),
                "notifier": encode(v.notifier.notifications),
                "governance_review_pending": {
                    k.value: val for k, val in v._governance_review_pending.items()
                },
            },
            "capital": {
                "packets": {k: encode(pkt) for k, pkt in p4.capital._packets.items()},
                "tier_d_amount": p4.capital.tier_d_amount,
                "budgeted_loss_amount": p4.capital._budgeted_loss_amount,
                "tier_d_floor": p4.capital.tier_d_floor,
                "budgeted_loss_ratio": p4.capital.budgeted_loss_ratio,
            },
            "ifrs9": {
                fac: {
                    "stage": f.stage,
                    "ecl": f.ecl,
                    "ead": f.ead,
                    "el": f.el,
                    "pd": f.pd,
                    "lgd": f.lgd,
                }
                for fac, f in p4.ifrs9._facilities.items()
            },
            "mode": {
                "mode": p4.mode_gate._gate._mode,
                "governance_events": encode(p4.mode_gate._gate.governance_events),
            },
            "event_log": [encode(e) for e in p4._event_log],
            "pledge": {
                "origination_held": p4.pledge_release.origination_held,
                "replacement_intake_available": p4.pledge_release.replacement_intake_available,
                "pre_term_exception_approved": p4.pledge_release.pre_term_exception_approved,
                "pending_track1": list(p4.pledge_release.pending_track1_condition()),
            },
            "custody": {
                "given_book_adjustments": p4.custody._given_book_adjustments,
            },
        }

    async def run(self, fn) -> object:
        if not self._loaded:
            await self.load()
        result = fn(self._ensure_engine())
        await self.store.set_json(STORAGE_KEY, await self._snapshot())
        return result

    async def reset(self) -> None:
        """Factory reset — replace the facade with a pristine one and persist an
        empty snapshot: buffer at $0, no pools, vetoes, packets, staging, events."""
        self.p4 = Pillar4(
            in_memory_ports=True,
            auto_lift_on_sustained_clean=self.track1_auto_lift_on_sustained_clean,
        )
        await self.store.set_json(STORAGE_KEY, await self._snapshot())
        self._loaded = True


runtime = P4Runtime(settings.p4_engine_sqlite_path)

router = APIRouter(tags=["pillar4"])

_KIND_409 = (
    ModeGateError,
    PendingNotResolvedError,
    AdmissibilityPolicyError,
    PledgeReleaseError,
    ReleaseInvariantViolationError,
)

_ERR_404 = {404: {"model": ErrorOut, "description": "Unknown identifier"}}
_ERR_409 = {409: {"model": ErrorOut, "description": (
    "Conflict — mode-gate refusal, an unresolved governance PENDING item, "
    "an admissibility-policy violation, or a pledge-release invariant "
    "violation"
)}}
_ERR_422 = {422: {"model": ErrorOut, "description": "Validation failed"}}


async def _call(fn) -> object:
    try:
        return await runtime.run(fn)
    except _KIND_409 as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


async def _ready() -> None:
    await runtime.load()


async def ensure_initial_tier_d(amount: float) -> None:
    """Seed the governance-approved Tier D capital base when uninitialized.

    Idempotent: only applies when ``tier_d_amount`` is 0 (e.g. first boot or
    after a factory reset). A runtime adjustment via ``POST /p4/capital/tier-d``
    is never overwritten — a non-zero amount survives restarts untouched.
    """
    if amount <= 0:
        return
    if not runtime._loaded:
        await runtime.load()
    p4 = runtime.p4
    if p4 is None:
        p4 = runtime._ensure_engine()
    if p4.capital.tier_d_amount == 0:
        await runtime.run(lambda p4: p4.capital.set_tier_d_amount(float(amount)))


# ---- buffer / pool / capital -------------------------------------------------


@router.get(
    "/buffer/balances",
    response_model=BufferBalancesOut,
    summary="Buffer sub-account balances",
    description=(
        "Live balances of the four Part II sub-accounts: EL Pool (IFRS 9 "
        "ECL provisions), ULA Buffer (loss capacity beyond Budgeted Loss), "
        "LR (funding-side liquidity), and RP Pool (risk-premium income)."
    ),
)
async def buffer_balances() -> dict:
    await _ready()
    return {k.value: v for k, v in runtime._ensure_engine().balances().items()}


@router.get(
    "/pool/adequacy",
    response_model=PoolAdequacyOut,
    summary="Guarantee-pool adequacy",
    description=(
        "Guarantees received vs the Pillar 2 required pooled-guarantee "
        "level. A shortfall paces origination; a shortfall coinciding with "
        "a ratio breach triggers the Track 1 veto. Pillar 4 never re-sizes "
        "the required level."
    ),
)
async def pool_adequacy() -> dict:
    await _ready()
    p4 = runtime._ensure_engine()
    return {
        **p4.pool_adequacy(),
        "received": p4.pool.received_received_value(),
    }


@router.get(
    "/capital/snapshot",
    response_model=CapitalSnapshotOut,
    summary="Capital & leverage snapshot",
    description=(
        "The three live prudential ratios: Tier D / RWA (floor 12%), "
        "portfolio EL vs the Budgeted Loss (2%), and the "
        "Guarantees-Granted/Received ratio, plus their raw inputs "
        "(RWA by facility, risk weights, guarantee books)."
    ),
)
async def capital_snapshot() -> dict:
    await _ready()
    runtime_ = runtime._ensure_engine()
    snap = runtime_.capital.snapshot(runtime_.buffer_service.account, runtime_.pool)
    return {
        "tier_d_over_rwa": snap.tier_d_over_rwa,
        "portfolio_el": snap.portfolio_el,
        "guarantees_granted_over_received": snap.guarantees_granted_over_received,
        "tier_d_amount": snap.tier_d_amount,
        "rwa": snap.rwa,
        "rwa_by_facility": snap.rwa_by_facility,
        "risk_weights": snap.risk_weights,
        "budgeted_loss": snap.budgeted_loss,
        "el_pool_balance": snap.el_pool_balance,
        "given_book": snap.given_book,
        "received_book": snap.received_book,
        "tier_d_floor": snap.tier_d_floor,
        "budgeted_loss_ratio": snap.budgeted_loss_ratio,
    }


@router.post(
    "/capital/tier-d",
    response_model=TierDAckOut,
    summary="Set Tier D capital base",
    description=(
        "Set the Tier D (common equity + Perpetual AT1) capital base — the "
        "numerator of the Tier D / RWA prudential ratio. Seeded by "
        "governance on first boot; this is the explicit runtime adjustment "
        "path."
    ),
    responses=_ERR_422,
)
async def set_tier_d_amount(amount: float) -> dict:
    """Set the Tier D (common equity + Perpetual AT1) capital base.

    The numerator of the Tier D / RWA prudential ratio. Seeded by governance on
    first boot; this endpoint is the explicit runtime adjustment path.
    """
    if amount < 0:
        raise HTTPException(status_code=422, detail="Tier D amount must be >= 0")
    await _call(lambda p4: p4.capital.set_tier_d_amount(float(amount)))
    return {"tier_d_amount": float(amount), "status": "set"}


@router.get(
    "/ifrs9",
    summary="IFRS 9 staging map",
    description=(
        "Per-facility IFRS 9 stage (1/2/3), ECL, EAD and EL. Fed by "
        "Pillar 2's direct staging signal, which bypasses Pillar 3 "
        "entirely — a staging migration is a provisioning event, never a "
        "covenant or freeze."
    ),
)
async def ifrs9_facilities() -> dict:
    await _ready()
    p4 = runtime._ensure_engine()
    return {
        fac: {"stage": f.stage, "ecl": f.ecl, "ead": f.ead, "el": f.el}
        for fac, f in p4.ifrs9._facilities.items()
    }


# ---- pillar 2 inbound --------------------------------------------------------


@router.post(
    "/risk-packet",
    response_model=FacilityRefOut,
    summary="Register a Pillar 2 risk packet",
    description=(
        "Register P2's BRR/PD/LGD/EAD/EL outputs for a facility — the "
        "inputs to capital adequacy, EL vs Budgeted Loss, and the required "
        "pooled-guarantee comparison."
    ),
    responses=_ERR_409,
)
async def feed_risk_packet(packet: Pillar2RiskPacket) -> dict:
    await _call(lambda p4: p4.ports.p2.feed_risk_packet(packet))
    return {"facility_ref": packet.facility_ref, "status": "registered"}


@router.post(
    "/staging-signal",
    response_model=StagingAckOut,
    summary="Receive an IFRS 9 staging signal",
    description=(
        "Pillar 2's direct staging feed (Stage 1/2/3) on significant "
        "credit-risk increase. Updates ECL provisioning in the EL Pool; "
        "triggers no Pillar 3 covenant or freeze."
    ),
    responses=_ERR_409,
)
async def feed_staging_signal(signal: StagingSignal) -> dict:
    await _call(
        lambda p4: p4.ports.p2.feed_staging_signal(
            signal.facility_ref, signal.stage, signal.packet_ref
        )
    )
    return {
        "facility_ref": signal.facility_ref,
        "stage": signal.stage,
        "status": "provisioned",
    }


@router.post(
    "/required-guarantee-level",
    response_model=RevisionAckOut,
    summary="Update the required guarantee level",
    description=(
        "Pillar 2 sizes the required pooled-guarantee level; Pillar 4 "
        "compares it against guarantees received and monitors adequacy. "
        "Pillar 4 never re-sizes the required level itself."
    ),
    responses=_ERR_409,
)
async def feed_required_guarantee_level(req: RequiredGuaranteeLevel) -> dict:
    await _call(
        lambda p4: p4.ports.p2.feed_required_guarantee_level(
            req.required_amount, req.revision_ref
        )
    )
    return {"revision_ref": req.revision_ref, "status": "monitored"}


# ---- veto consultation (resolution-at-P2) ------------------------------------


@router.get(
    "/veto/consult",
    response_model=VetoConsultOut,
    summary="Consult the veto state",
    description=(
        "The Track 1 / Track 2 veto state Pillar 2 must consult before "
        "confirming any output packet. If frozen, P2 withholds the packet "
        "— Pillar 3 never sees a veto event. Supply ``facility_ref`` for "
        "the facility-level (Track 2) view."
    ),
)
async def consult_veto(facility_ref: str | None = None) -> dict:
    await _ready()
    p4 = runtime._ensure_engine()
    return to_wire(p4.ports.p2.consult_veto(facility_ref))


@router.get(
    "/veto/confirm",
    response_model=ConfirmPacketOut,
    summary="Would a packet be confirmed?",
    description=(
        "Dry-run of P2's packet-confirmation gate for a facility — True "
        "only when no veto blocks the facility and the required guarantee "
        "level permits origination."
    ),
    responses=_ERR_404,
)
async def confirm_packet(facility_ref: str) -> dict:
    await _ready()
    p4 = runtime._ensure_engine()
    return {
        "facility_ref": facility_ref,
        "confirmed": p4.ports.p2.confirm_packet(facility_ref),
    }


@router.post(
    "/veto/track2",
    response_model=Track2ResultOut,
    summary="Evaluate a Track 2 (facility) veto",
    description=(
        "Evaluate one facility against Pillar 4 policy — freezes that "
        "facility's action class even when portfolio metrics are clean. "
        "Resolution happens at Pillar 2; P3 is never contacted."
    ),
    responses=_ERR_409,
)
async def evaluate_track2(facility_ref: str, violates_policy: str | None = None) -> dict:
    result = await _call(
        lambda p4: p4.veto_engine.evaluate_track2(facility_ref, violates_policy)
    )
    return {"facility_ref": facility_ref, "resolution": result.value}


@router.post(
    "/veto/lift-track1",
    response_model=LiftTrack1Out,
    summary="Lift a Track 1 freeze (governance)",
    description=(
        "Governance-only lift of a standing Track 1 freeze, citing its "
        "governance reference. Cannot be overridden by Pillar 2 or 3."
    ),
    responses=_ERR_409,
)
async def lift_track1(governance_ref: str) -> dict:
    await _call(lambda p4: p4.veto_engine.review_and_lift_track1(governance_ref))
    return {"governance_ref": governance_ref, "status": "track1_lifted"}


# ---- pillar 3 inbound / recompute -------------------------------------------


@router.post(
    "/events",
    response_model=Pillar3EventAckOut,
    summary="Route a Pillar 3 event",
    description=(
        "Receive a loan-level event from Pillar 3 and route it to the "
        "correct buffer sub-account. Pillar 3 moves data; Pillar 4 decides "
        "what the data means — no allocation logic lives in P3."
    ),
    responses=_ERR_409,
)
async def feed_pillar3_event(event: Pillar3Event) -> dict:
    await _call(lambda p4: p4.ports.p3.feed_event(event))
    return {
        "event_type": event.event_type.value,
        "facility_ref": event.facility_ref,
        "status": "routed",
    }


@router.post(
    "/recompute-track1",
    response_model=RecomputeTrack1Out,
    summary="Recompute Track 1 triggers",
    description=(
        "Recompute the capital ratios and evaluate the Track 1 threshold "
        "set. ``breached_triggers`` are live freezes; "
        "``unmonitored_triggers`` are named-but-PENDING thresholds with no "
        "settled number yet (never silently defaulted)."
    ),
    responses=_ERR_409,
)
async def recompute_track1() -> dict:
    result = await _call(lambda p4: p4.recompute_and_evaluate_track1())
    return {
        "tier_d_over_rwa": result["snapshot"].tier_d_over_rwa,
        "portfolio_el": result["snapshot"].portfolio_el,
        "breached_triggers": [t for t in result["breached_triggers"]],
        "unmonitored_triggers": list(result.get("unmonitored_triggers", [])),
        "auto_lifted": result.get("auto_lifted", False),
    }


# ---- mode gate ---------------------------------------------------------------


@router.get(
    "/mode",
    response_model=ModeStatusOut,
    summary="Current operating mode",
    description=(
        "Bank-wide operating mode from SI-1: Conventional (static tiers, "
        "classical foreclosure, no adaptive scoring) or Adaptive (CASS "
        "scoring + ABSF, sandbox-gated). A governance switch, not a build "
        "phase."
    ),
)
async def mode_status() -> dict:
    await _ready()
    p4 = runtime._ensure_engine()
    return {
        "mode": p4.mode_gate.mode,
        "adaptive": p4.mode_gate.is_adaptive(),
        "conventional": p4.mode_gate.is_conventional(),
    }


@router.post(
    "/mode/activate",
    response_model=ModeAckOut,
    summary="Activate Adaptive Mode (governance)",
    description=(
        "Governance ruling to enter Adaptive Mode. Requires the Gate G1 "
        "criteria; the CASS methodology itself is still PENDING, so this "
        "is exercised in the sandbox only."
    ),
    responses=_ERR_409,
)
async def activate_adaptive(ruling: GovernanceRuling) -> dict:
    await _call(lambda p4: p4.mode_gate.activate_adaptive(ruling))
    return {"mode": runtime._ensure_engine().mode_gate.mode, "status": "activated"}


@router.post(
    "/mode/fallback",
    response_model=ModeAckOut,
    summary="Fall back to Conventional Mode (governance)",
    description=(
        "Governance ruling to deactivate Adaptive Mode. Deactivation is "
        "not deletion — no rebuild, no book unwind, no contract "
        "amendment; Conventional Mode is the permanent floor."
    ),
    responses=_ERR_409,
)
async def fallback_conventional(ruling: GovernanceRuling) -> dict:
    await _call(lambda p4: p4.mode_gate.fallback_to_conventional(ruling))
    return {"mode": runtime._ensure_engine().mode_gate.mode, "status": "fallback"}


# ---- pillar 5 / pledge -------------------------------------------------------


@router.post(
    "/pledge/submit",
    response_model=PledgeSubmitOut,
    summary="Submit a pledge for admission",
    description=(
        "Pillar 5 pledge intake, reviewed against Pillar 4's admissibility "
        "POLICY (eligible types, haircuts, concentration limits) — a "
        "policy-level check, not a case decision; Pillar 2 confirms each "
        "individual case."
    ),
    responses=_ERR_409,
)
async def submit_pledge(submission: PledgeSubmission) -> dict:
    result = await _call(lambda p4: p4.ports.p5.submit_pledge(submission))
    return to_wire(result)


@router.post(
    "/pledge/release",
    response_model=PledgeAckOut,
    summary="Request a pledge release",
    description=(
        "Open the release notice window. Release is a right at/post term "
        "(exception with penalty pre-term). Invariant: no release path may "
        "ever generate a cash outflow or draw the Liquidity Reserve."
    ),
    responses=_ERR_409,
)
async def request_release(pledge_ref: str, at_or_post_term: bool = True) -> dict:
    await _call(lambda p4: p4.pledge_release.request_release(pledge_ref, at_or_post_term))
    return {"pledge_ref": pledge_ref, "status": "release_requested"}


@router.post(
    "/pledge/manage-adequacy",
    response_model=PledgeAckOut,
    summary="Manage pool adequacy during the release window",
    description=(
        "Run the adequacy tools while a release is pending: origination "
        "pacing, replacement intake, or — if a shortfall coincides with a "
        "ratio breach — the Track 1 veto."
    ),
    responses=_ERR_409,
)
async def manage_adequacy(pledge_ref: str) -> dict:
    await _call(lambda p4: p4.pledge_release.manage_adequacy(pledge_ref))
    return {"pledge_ref": pledge_ref, "status": "adequacy_managed"}


@router.post(
    "/pledge/finalize",
    response_model=PledgeAckOut,
    summary="Finalize a pledge release",
    description=(
        "Execute the release after the notice window: lift the security "
        "interest, exit the asset from custody, extinguish the contingent "
        "cash-equivalent position. No cash moves; guarantees-received "
        "drops."
    ),
    responses=_ERR_409,
)
async def finalize_release(pledge_ref: str) -> dict:
    await _call(lambda p4: p4.pledge_release.finalize_release(pledge_ref))
    return {"pledge_ref": pledge_ref, "status": "released"}


# ---- observability -----------------------------------------------------------


@router.get(
    "/events",
    response_model=list[IntraP4EventOut],
    summary="Intra-Pillar-4 event log",
    description=(
        "Internal Part I/II event stream: staging signals, adequacy "
        "shortfalls, guarantee-call settlements, and other intra-pillar "
        "transitions."
    ),
)
async def intra_events() -> list[dict]:
    await _ready()
    return [to_wire(e) for e in runtime._ensure_engine().event_log]


@router.get(
    "/veto/notifications",
    response_model=list[VetoNotificationOut],
    summary="Orchestrator veto notifications",
    description=(
        "Mandatory freeze notifications sent to the Orchestrator on every "
        "Track 1 / Track 2 freeze — governance review opens on each."
    ),
)
async def veto_notifications() -> list[dict]:
    await _ready()
    p4 = runtime._ensure_engine()
    return p4.veto_engine.notifier.notifications


def make_app(
    *,
    db_path: str,
    track1_auto_lift_on_sustained_clean: int | None = None,
) -> FastAPI:
    global runtime
    runtime = P4Runtime(
        db_path,
        track1_auto_lift_on_sustained_clean=track1_auto_lift_on_sustained_clean,
    )
    setup_logging("pillar4", settings.log_level, settings.log_json)
    return build_app(
        service="Pillar 4",
        settings=settings,
        routers=[("", router)],
        description=(
            "Prudential layer: buffer sub-accounts (EL Pool / ULA / LR / RP), "
            "guarantee-pool adequacy, the Tier D/RWA capital snapshot, IFRS 9 "
            "staging, the two-track veto (resolves at Pillar 2 — Pillar 3 "
            "never sees a veto), the SI-1 mode gate, and pledge "
            "intake/release with the no-cash release invariant."
        ),
    )


app = make_app(db_path=settings.p4_engine_sqlite_path)