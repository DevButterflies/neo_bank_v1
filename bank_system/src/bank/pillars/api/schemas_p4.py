"""Response schemas (DTOs) for the Pillar 4 HTTP API.

Wire shapes after :func:`bank.pillars.api.codec.to_wire` flattening: enums
as plain string values, datetimes as ISO-8601 strings, no persistence
markers. ``extra="allow"`` everywhere — response validation documents the
contract without ever dropping an engine field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class BufferBalancesOut(_Out):
    """The four buffer sub-accounts (Part II)."""

    el_pool: float = 0.0
    ula_buffer: float = 0.0
    liquidity_reserve: float = 0.0
    rp_pool: float = 0.0


class PoolAdequacyOut(_Out):
    """Guarantees received vs the Pillar 2 required level."""

    received: float
    required: float
    status: str
    shortfall_amount: float


class CapitalSnapshotOut(_Out):
    """Tier D / RWA, portfolio EL, and the G/G ratio with their inputs.

    Ratio fields are nullable: the engine returns ``None`` where a
    denominator is still zero (e.g. no guarantees received yet).
    """

    tier_d_over_rwa: float | None = None
    portfolio_el: float | None = None
    guarantees_granted_over_received: float | None = None
    tier_d_amount: float | None = None
    rwa: float | None = None
    rwa_by_facility: dict = Field(default_factory=dict)
    risk_weights: dict = Field(default_factory=dict)
    budgeted_loss: float | None = None
    el_pool_balance: float | None = None
    given_book: float | None = None
    received_book: float | None = None
    tier_d_floor: float | None = None
    budgeted_loss_ratio: float | None = None


class TierDAckOut(_Out):
    tier_d_amount: float
    status: str


class FacilityRefOut(_Out):
    facility_ref: str
    status: str


class StagingAckOut(_Out):
    facility_ref: str
    stage: int
    status: str


class RevisionAckOut(_Out):
    revision_ref: str
    status: str


class VetoConsultOut(_Out):
    """The veto state Pillar 2 must consult before confirming any packet."""

    any_frozen: bool
    track1_frozen: bool
    track1_triggers: list[str] = Field(default_factory=list)
    track2_frozen_for_facility: bool = False
    track2_policy: str | None = None


class ConfirmPacketOut(_Out):
    facility_ref: str
    confirmed: bool


class Track2ResultOut(_Out):
    facility_ref: str
    resolution: str


class LiftTrack1Out(_Out):
    governance_ref: str
    status: str


class Pillar3EventAckOut(_Out):
    event_type: str
    facility_ref: str
    status: str


class RecomputeTrack1Out(_Out):
    tier_d_over_rwa: float | None = None
    portfolio_el: float | None = None
    breached_triggers: list[str] = Field(default_factory=list)
    unmonitored_triggers: list[str] = Field(default_factory=list)
    auto_lifted: bool = False


class ModeStatusOut(_Out):
    mode: str
    adaptive: bool
    conventional: bool


class ModeAckOut(_Out):
    mode: str
    status: str


class PledgeSubmitOut(_Out):
    submission_ref: str
    disposition: str
    reason: str | None = None
    policy_version: str


class PledgeAckOut(_Out):
    pledge_ref: str
    status: str


class IntraP4EventOut(_Out):
    type: str
    payload: dict = Field(default_factory=dict)
    occurred_at: str | None = None


class VetoNotificationOut(_Out):
    event: str
    track: str
    triggers: dict | list = Field(default_factory=dict)
    governance_ref: str | None = None
