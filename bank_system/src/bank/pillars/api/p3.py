"""Pillar 3 microservice — origination state machine wrapped as HTTP.

Wraps the unmodified :class:`Pillar3Orchestrator` in a REST API. Engine state
is persisted as a JSON snapshot in one per-service SQLite file and rehydrated
on restart, so facilities/packets/audit/postings/ledger survive restarts.
Transport and storage only; the engine logic is untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Query

from bank.core.api import build_app
from bank.core.config import Settings, get_settings
from bank.core.logging import setup_logging

from bank.pillars.api.codec import decode, encode, to_wire
from bank.pillars.api.schemas_common import ErrorOut
from bank.pillars.api.schemas_p3 import (
    AuditRecordOut,
    CollateralOut,
    FacilityDetail,
    FacilitySummary,
    LedgerPostingOut,
    OriginationResultOut,
    P2PacketOut,
    PostingEventOut,
    ReconcileOut,
    RepaymentResultOut,
    StatusAckOut,
)
from bank.pillars.api.storage import KvStore

from bank.pillars.p3.core_banking.interface import CoreBankingClient
from bank.pillars.p3.core_banking.ledger import CoreBankingLedger, CoreBankingPosting
from bank.pillars.p3.domain.collateral import CollateralObject, CollateralObjectKind
from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    LoanState,
    MaturityStage,
    ModelFlag,
    P2PacketStatus,
    PostingEventType,
)
from bank.pillars.p3.domain.events import AuditRecord, PostingEvent
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.engine.orchestrator import Pillar3Orchestrator
from bank.pillars.p3.engine.posting_service import AllocationQuestion
from bank.pillars.p3.engine.reconciliation import reconcile
from bank.pillars.p3.errors import (
    AdmissibilityNotConfirmedError,
    AutoOriginationNotPermittedError,
    GovernanceBoundaryError,
    InvalidStateTransitionError,
    PendingGovernanceItemError,
    ReconciliationBreachError,
    RepaymentExceedsOutstandingError,
    UnauthorisedDecisionError,
    UnconfirmedPacketError,
    VetoFrozenError,
    WriteOffExceedsOutstandingError,
)

settings: Settings = get_settings()

STORAGE_KEY = "p3_state_v1"

_CLASSES = {
    cls.__name__: cls
    for cls in (
        P2OutputPacket,
        LoanFacility,
        CollateralObject,
        PostingEvent,
        AuditRecord,
        AllocationQuestion,
        CoreBankingPosting,
    )
}
_ENUMS = {
    cls.__name__: cls
    for cls in (
        CollateralTrack,
        LoanState,
        MaturityStage,
        ModelFlag,
        P2PacketStatus,
        PostingEventType,
        CollateralObjectKind,
    )
}


class P3Runtime:
    """Holds the orchestrator plus its durable snapshot."""

    def __init__(self, db_path: str) -> None:
        self.store = KvStore(db_path)
        self.orchestrator: Pillar3Orchestrator | None = None
        self._loaded = False

    def _ensure_engine(self) -> Pillar3Orchestrator:
        if self.orchestrator is None:
            self.orchestrator = Pillar3Orchestrator(
                CoreBankingClient(CoreBankingLedger())
            )
        return self.orchestrator

    async def load(self) -> None:
        self._ensure_engine()
        snap = await self.store.get_json(STORAGE_KEY)
        if snap:
            self._apply(snap)
        self._loaded = True

    def _apply(self, snap: dict) -> None:
        o = self._ensure_engine()
        o._facilities.clear()
        o._facilities.update(
            {fid: decode(v, _CLASSES, _ENUMS) for fid, v in snap["facilities"].items()}
        )
        o.p2_gate._received.clear()
        o.p2_gate._received.update(
            {pid: decode(v, _CLASSES, _ENUMS) for pid, v in snap["packets"].items()}
        )
        o.posting_service._posted_events[:] = [
            decode(x, _CLASSES, _ENUMS) for x in snap["posted_events"]
        ]
        o.posting_service._routed_questions[:] = [
            decode(x, _CLASSES, _ENUMS) for x in snap["routed_questions"]
        ]
        o.collateral_service._recorded[:] = [
            decode(x, _CLASSES, _ENUMS) for x in snap["recorded_collateral"]
        ]
        o.audit_trail._records[:] = [
            decode(x, _CLASSES, _ENUMS) for x in snap["audit_records"]
        ]
        o.p4_router._portfolio_vetoed = snap["p4_router"]["portfolio"]
        o.p4_router._facility_vetoed = set(snap["p4_router"]["facility_set"])
        ledger = o.posting_service._core_banking.ledger()
        ledger._postings = {
            pid: decode(v, _CLASSES, _ENUMS)
            for pid, v in snap["ledger"]["postings"].items()
        }
        ledger._next_id = snap["ledger"]["next_id"]

    async def _snapshot(self) -> dict:
        o = self._ensure_engine()
        ledger = o.posting_service._core_banking.ledger()
        return {
            "facilities": {fid: encode(f) for fid, f in o._facilities.items()},
            "packets": {pid: encode(p) for pid, p in o.p2_gate._received.items()},
            "posted_events": [encode(e) for e in o.posting_service.posted_events()],
            "routed_questions": [
                encode(q) for q in o.posting_service.routed_allocation_questions()
            ],
            "recorded_collateral": [
                encode(c) for c in o.collateral_service._recorded
            ],
            "audit_records": [encode(r) for r in o.audit_trail._records],
            "p4_router": {
                "portfolio": o.p4_router._portfolio_vetoed,
                "facility_set": sorted(o.p4_router._facility_vetoed),
            },
            "ledger": {
                "postings": {
                    pid: encode(p) for pid, p in ledger._postings.items()
                },
                "next_id": ledger._next_id,
            },
        }

    async def run(self, fn) -> object:
        if not self._loaded:
            await self.load()
        result = fn(self._ensure_engine())
        await self.store.set_json(STORAGE_KEY, await self._snapshot())
        return result

    async def reset(self) -> None:
        """Factory reset — replace the engine with a pristine one and persist an
        empty snapshot, clearing facilities, packets, postings, audit and ledger."""
        self.orchestrator = Pillar3Orchestrator(
            CoreBankingClient(CoreBankingLedger())
        )
        await self.store.set_json(STORAGE_KEY, await self._snapshot())
        self._loaded = True


runtime = P3Runtime(settings.p3_engine_sqlite_path)

router = APIRouter(tags=["pillar3"])


_KIND_400 = (
    PendingGovernanceItemError,
    GovernanceBoundaryError,
    VetoFrozenError,
    ReconciliationBreachError,
)
_KIND_422 = (
    AdmissibilityNotConfirmedError,
    AutoOriginationNotPermittedError,
    InvalidStateTransitionError,
    RepaymentExceedsOutstandingError,
    UnauthorisedDecisionError,
    UnconfirmedPacketError,
    WriteOffExceedsOutstandingError,
)

_ERR_404 = {404: {"model": ErrorOut, "description": "Unknown identifier"}}
_ERR_409 = {409: {"model": ErrorOut, "description": (
    "Conflict — a prudential veto is frozen at Pillar 2, a governance "
    "PENDING item blocks the action, or the state machine forbids the "
    "transition"
)}}
_ERR_422 = {422: {"model": ErrorOut, "description": (
    "Validation gate failed — unconfirmed packet, missing officer "
    "confirmation/human workout authorisation, or amounts outside "
    "outstanding"
)}}


async def _ready() -> None:
    await runtime.load()


async def _call(fn) -> object:
    try:
        return await runtime.run(fn)
    except _KIND_400 as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except _KIND_422 as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/facilities",
    response_model=list[FacilitySummary],
    summary="List facilities",
    description=(
        "Every facility P3 executes, with its state-machine status, "
        "collateral count, and whether a Pillar 4 veto is currently frozen "
        "on it."
    ),
)
async def list_facilities() -> list[dict]:
    await _ready()
    o = runtime._ensure_engine()
    return [
        {
            "facility_id": f.facility_id,
            "state": f.state.value,
            "origination_packet_id": f.origination_packet_id,
            "collateral_count": len(f.collateral_objects),
            "veto_frozen": f.veto_frozen,
            "updated_at": f.updated_at.isoformat(),
        }
        for f in o._facilities.values()
    ]


@router.get(
    "/facilities/{facility_id}",
    response_model=FacilityDetail,
    summary="Facility detail",
    description=(
        "Full facility record: lifecycle timestamps, the collateral objects "
        "held on the facility, and the collateral-service records recorded "
        "against it."
    ),
    responses=_ERR_404,
)
async def get_facility(facility_id: str) -> dict:
    await _ready()
    o = runtime._ensure_engine()
    facility = o._facilities.get(facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail=f"Unknown facility {facility_id}")
    return {
        "facility_id": facility.facility_id,
        "state": facility.state.value,
        "origination_packet_id": facility.origination_packet_id,
        "veto_frozen": facility.veto_frozen,
        "created_at": facility.created_at.isoformat(),
        "updated_at": facility.updated_at.isoformat(),
        "collateral_objects": [encode(c) for c in facility.collateral_objects],
        "collateral_service_recorded": [
            encode(c) for c in o.collateral_service.recorded_for_facility(facility_id)
        ],
    }


@router.get(
    "/packets",
    response_model=list[P2PacketOut],
    summary="Received Pillar 2 packets",
    description=(
        "All Pillar 2 output packets P3 has received. These are pass-through "
        "records — P3 records every field verbatim and never infers or "
        "recomputes a packet field (Canon §8.1)."
    ),
)
async def list_packets() -> list[dict]:
    await _ready()
    o = runtime._ensure_engine()
    return [to_wire(p) for p in o.p2_gate.all_received()]


@router.get(
    "/audit",
    response_model=list[AuditRecordOut],
    summary="Full audit trail",
    description=(
        "Append-only audit trail carrying the Spec §8 mandatory field list: "
        "packet version, Model Maturity Stage, BRR-PD grid version, P4 veto "
        "status, and core-banking confirmation for every event."
    ),
)
async def list_audit() -> list[dict]:
    await _ready()
    o = runtime._ensure_engine()
    return [to_wire(r) for r in o.audit_trail.all_records()]


@router.get(
    "/audit/{facility_id}",
    response_model=list[AuditRecordOut],
    summary="Facility audit trail",
    description="Append-only audit records for one facility.",
)
async def facility_audit(facility_id: str) -> list[dict]:
    await _ready()
    o = runtime._ensure_engine()
    return [to_wire(r) for r in o.audit_trail.for_facility(facility_id)]


@router.get(
    "/postings",
    response_model=list[PostingEventOut],
    summary="Per-loan posting events",
    description=(
        "Every posting event P3 captured (disbursements, repayments, fees, "
        "losses, recoveries). P3 computes no allocation — events flagged "
        "``routes_allocation_question_to_p4`` carry the allocation question "
        "to Pillar 4, which owns all burden-sharing."
    ),
)
async def list_postings() -> list[dict]:
    await _ready()
    o = runtime._ensure_engine()
    return [to_wire(e) for e in o.posting_service.posted_events()]


@router.get(
    "/ledger",
    response_model=list[LedgerPostingOut],
    summary="Core-banking ledger",
    description=(
        "Core-banking postings — the system of record. Core banking always "
        "wins a reconciliation dispute against the P3 event log; P4 governs "
        "only the tolerance."
    ),
)
async def list_ledger() -> list[dict]:
    await _ready()
    o = runtime._ensure_engine()
    ledger = o.posting_service._core_banking.ledger()
    return [to_wire(p) for p in ledger.all_postings()]


@router.get(
    "/reconcile",
    response_model=ReconcileOut,
    summary="Reconcile postings vs ledger",
    description=(
        "Compare total P3 posting amounts against the core-banking ledger "
        "within a tolerance (default 0.0 — exact match). Returns the "
        "unmatched P3 event ids when they differ."
    ),
)
async def core_banking_reconcile(tolerance: float = 0.0) -> dict:
    await _ready()
    o = runtime._ensure_engine()
    ledger = o.posting_service._core_banking.ledger()
    result = reconcile(o.posting_service.posted_events(), ledger, tolerance)
    return to_wire(result)


@router.post(
    "/originate",
    response_model=OriginationResultOut,
    summary="Originate a facility",
    description=(
        "Open a facility from a confirmed Pillar 2 packet. The packet must "
        "pass the confirmation gate (Canon §8.1); a frozen Pillar 4 veto "
        "resolves at Pillar 2 and surfaces here as a 409 — P3 never sees a "
        "veto event, only a confirmed or withheld packet."
    ),
    responses=_ERR_409,
)
async def originate(packet: P2OutputPacket) -> dict:
    result = await _call(lambda o: o.originate(packet))
    return {"facility_id": result.facility_id, "state": result.state.value}


@router.post(
    "/disburse",
    response_model=PostingEventOut,
    summary="Disburse a facility",
    description=(
        "Disburse funds against an originated facility. Emits the "
        "PRINCIPAL_MOVEMENT posting event and posts it to core banking."
    ),
    responses=_ERR_409,
)
async def disburse(packet: P2OutputPacket, facility_id: str, amount: float, currency: str) -> dict:
    event = await _call(
        lambda o: (o.p2_gate.receive_packet(packet), o.disburse(facility_id, packet, amount, currency))[1]
    )
    return to_wire(event)


@router.post(
    "/pledge-collateral",
    response_model=CollateralOut,
    summary="Pledge facility collateral",
    description=(
        "Record a facility-specific collateral pledge against a facility. "
        "Stage 1 is Track 1 (classical) collateral only; this pledge is "
        "structurally distinct from the pooled guarantee held by Pillar 4 "
        "(Two-Guarantee-Layer Rule)."
    ),
    responses=_ERR_409,
)
async def pledge_collateral(
    packet: P2OutputPacket, facility_id: str, external_reference: str | None = None
) -> dict:
    collateral = await _call(
        lambda o: (
            o.p2_gate.receive_packet(packet),
            o.pledge_collateral(facility_id, packet, external_reference),
        )[1]
    )
    return to_wire(collateral)


@router.post(
    "/repayment",
    response_model=RepaymentResultOut,
    summary="Record a repayment",
    description=(
        "Record a scheduled repayment. Splits into an interest (income) "
        "posting and a principal posting; the risk-premium component of "
        "income is routed to Pillar 4's RP Pool."
    ),
    responses=_ERR_409,
)
async def record_repayment(
    packet: P2OutputPacket,
    facility_id: str,
    interest_amount: float,
    principal_amount: float,
    currency: str,
) -> dict:
    income, principal = await _call(
        lambda o: (
            o.p2_gate.receive_packet(packet),
            o.record_repayment(facility_id, packet, interest_amount, principal_amount, currency),
        )[1]
    )
    return {"income_event": to_wire(income), "principal_event": to_wire(principal)}


@router.post(
    "/mark-delinquent",
    response_model=StatusAckOut,
    summary="Mark facility delinquent",
    description=(
        "Risk-officer delinquency marker. P3 detects and routes only — no "
        "allocation, provisioning, or burden-sharing is computed here; "
        "those belong to Pillar 4."
    ),
    responses=_ERR_409,
)
async def mark_delinquent(packet: P2OutputPacket, facility_id: str) -> dict:
    await _call(
        lambda o: (o.p2_gate.receive_packet(packet), o.mark_delinquent(facility_id, packet))[1]
    )
    return {"facility_id": facility_id, "status": "marked_delinquent"}


@router.post(
    "/mark-default",
    response_model=PostingEventOut,
    summary="Mark facility defaulted",
    description=(
        "Crystallize a default and record the loss amount. The guarantee "
        "leg (Pillar 4 computes and settles the guarantee call) runs "
        "separately from the collateral leg P3 records here — the two legs "
        "never substitute for each other."
    ),
    responses=_ERR_409,
)
async def mark_default(
    packet: P2OutputPacket,
    facility_id: str,
    loss_amount: float = Query(0.0, ge=0, allow_inf_nan=False),
    currency: str = "USD",
) -> dict:
    event = await _call(
        lambda o: (
            o.p2_gate.receive_packet(packet),
            o.mark_default(facility_id, packet, loss_amount, currency),
        )[1]
    )
    return to_wire(event)


@router.post(
    "/restructure",
    response_model=StatusAckOut,
    summary="Restructure a facility",
    description=(
        "Restructure a facility. Requires ``human_authorised_for_workout`` "
        "on the packet — origination confirmation and workout "
        "authorisation are deliberately separate acts (Canon §8.6)."
    ),
    responses=_ERR_409,
)
async def restructure(packet: P2OutputPacket, facility_id: str) -> dict:
    await _call(
        lambda o: (o.p2_gate.receive_packet(packet), o.restructure(facility_id, packet))[1]
    )
    return {"facility_id": facility_id, "status": "restructured"}


@router.post(
    "/recovery",
    response_model=PostingEventOut,
    summary="Record a recovery",
    description=(
        "Record the collateral-leg recovery receipt against a defaulted "
        "facility — classical foreclosure proceeds returned to the book. "
        "Pillar 4 credits the EL Pool / ULA Buffer separately."
    ),
    responses=_ERR_409,
)
async def initiate_recovery(
    packet: P2OutputPacket, facility_id: str, recovered_amount: float, currency: str
) -> dict:
    event = await _call(
        lambda o: (
            o.p2_gate.receive_packet(packet),
            o.initiate_recovery(facility_id, packet, recovered_amount, currency),
        )[1]
    )
    return to_wire(event)


@router.post(
    "/close",
    response_model=StatusAckOut,
    summary="Close a facility",
    description="Close a facility after final settlement.",
    responses=_ERR_409,
)
async def close_facility(packet: P2OutputPacket, facility_id: str) -> dict:
    await _call(
        lambda o: (o.p2_gate.receive_packet(packet), o.close(facility_id, packet))[1]
    )
    return {"facility_id": facility_id, "status": "closed"}


def make_app(*, db_path: str) -> FastAPI:
    global runtime
    runtime = P3Runtime(db_path)
    setup_logging("pillar3", settings.log_level, settings.log_json)
    return build_app(
        service="Pillar 3",
        settings=settings,
        routers=[("", router)],
        description=(
            "Loan lifecycle & execution. Records every P2 packet verbatim, "
            "captures the audit trail and postings, and posts to the "
            "core-banking ledger — the system of record. No allocation "
            "logic lives here; allocation questions route to Pillar 4."
        ),
    )


app = make_app(db_path=settings.p3_engine_sqlite_path)