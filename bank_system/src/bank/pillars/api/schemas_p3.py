"""Response schemas (DTOs) for the Pillar 3 HTTP API.

These document the *wire* shape after :func:`bank.pillars.api.codec.to_wire`
flattening: enums as their plain string value, datetimes as ISO-8601 strings,
no persistence markers. ``extra="allow"`` everywhere so the schema documents
the common fields without ever dropping a field the engine adds — response
validation must never change a payload.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class FacilitySummary(_Out):
    facility_id: str
    state: str
    origination_packet_id: str
    collateral_count: int
    veto_frozen: bool
    updated_at: str


class FacilityDetail(_Out):
    facility_id: str
    state: str
    origination_packet_id: str
    veto_frozen: bool
    created_at: str
    updated_at: str
    collateral_objects: list[dict] = Field(default_factory=list)
    collateral_service_recorded: list[dict] = Field(default_factory=list)


class P2PacketOut(_Out):
    packet_id: str
    facility_id: str
    status: str
    maturity_stage: str
    brr_pd_grid_version: str
    collateral_track: str
    packet_version: str
    officer_confirmed: bool = False
    officer_id: str | None = None
    human_authorised_for_workout: bool = False
    issued_at: str | None = None


class PostingEventOut(_Out):
    event_id: str
    facility_id: str
    event_type: str
    amount: float
    currency: str
    p2_packet_id: str
    occurred_at: str | None = None
    routes_allocation_question_to_p4: bool = False
    memo: str | None = None


class AuditRecordOut(_Out):
    record_id: str
    facility_id: str
    event_type: str
    timestamp: str | None = None
    actor_reference: str
    p2_packet_version: str
    maturity_stage: str
    brr_pd_grid_version: str
    collateral_track: str | None = None
    p4_veto_status: str
    posting_routing_flag: str | None = None
    core_banking_confirmed: bool
    resulting_state: str
    collateral_reference: str | None = None
    guarantee_linkage: str | None = None


class LedgerPostingOut(_Out):
    posting_id: str
    source_event_id: str
    facility_id: str
    amount: float
    currency: str
    posted_at: str | None = None


class ReconcileOut(_Out):
    p3_event_total: float
    core_banking_total: float
    discrepancy: float
    tolerance: float
    within_tolerance: bool
    unmatched_p3_event_ids: list[str] = Field(default_factory=list)


class CollateralOut(_Out):
    collateral_id: str
    facility_id: str
    kind: str
    track: str
    model_flag: str
    p2_packet_id: str
    recorded_at: str | None = None
    external_reference: str | None = None


class OriginationResultOut(_Out):
    facility_id: str
    state: str


class StatusAckOut(_Out):
    facility_id: str
    status: str


class RepaymentResultOut(_Out):
    income_event: PostingEventOut
    principal_event: PostingEventOut
