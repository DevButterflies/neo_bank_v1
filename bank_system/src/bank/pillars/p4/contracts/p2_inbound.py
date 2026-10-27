"""Pillar 2 -> Pillar 4 inbound contracts.

claude.md §4.6 / §9: Pillar 2 feeds Pillar 4 on standard cadence and
event-driven recompute:

  - :class:`Pillar2RiskPacket` - BRR, PD, LGD, EAD, EL + provenance
    (model_maturity_stage, brr_pd_grid_version, packet_ref). PD/LGD are already
    inclusive of Pillar 2's Margin of Conservatism (P4 must NOT re-apply a
    second buffer - no double-counting; claude.md §4.4).
  - :class:`StagingSignal` - the IFRS 9 staging signal (Stage 1/2/3) on
    significant credit-risk increase; DIRECT feed to the EL Pool, bypassing
    Pillar 3. Wire format PENDING (PENDING_STAGING_SIGNAL_FORMAT); this is the
    logical field shape only.
  - :class:`RequiredGuaranteeLevel` - Pillar 2's required pooled-guarantee level
    (R_pool). Pillar 4 holds the pool and monitors adequacy; it NEVER re-sizes
    the requirement. Transport blocked by PENDING_TWO_GUARANTEE_LAYER_CONTRACT.
  - :class:`CASSFeedRecord` - the frozen CIS-1 10-field shape (per-facility
    only, no portfolio aggregates). Dormant in Conventional Mode; methodology
    PENDING (PENDING_CASS_FEED_SPEC). Includes the provenance fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..domain.model_maturity import ModelStage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Pillar2RiskPacket:
    """BRR/PD/LGD/EAD/EL packet (standard cadence + event-driven).

    Bound to Pillar 4's capital/leverage computation (Derivation Register I-a).
    """

    facility_ref: str
    brr: float
    pd: float
    lgd: float
    ead: float
    el: float
    # Provenance fields - carried on feed, NOT scoring inputs.
    model_maturity_stage: ModelStage = ModelStage.PRODUCTION
    brr_pd_grid_version: str | None = None
    packet_ref: str | None = None
    as_of: datetime = field(default_factory=_utcnow)
    # Facility product (P2 Product enum value, e.g. "WORKING_CAPITAL_LINE",
    # "TERM_LOAN"). P4 uses it for the EAD-decay CCF: only revolving lines
    # restore undrawn headroom on repayment (ΔEAD = −0.25 × principal);
    # fully-drawn amortizing products decay dollar-for-dollar.
    product_type: str | None = None

    # Margin of Conservatism is ALREADY included in pd/lgd by Pillar 2; Pillar 4
    # must not re-apply it (no double-counting). Flag carried for audit so the
    # build can assert it was applied exactly once.
    margin_of_conservatism_applied: bool = True


@dataclass(frozen=True)
class StagingSignal:
    """IFRS 9 staging signal (Stage 1/2/3), P2 -> P4 EL Pool DIRECT (bypasses P3).

    A staging migration triggers NO Pillar 3 covenant or freeze - it is purely
    a Pillar 4 provisioning event (claude.md §4.4). Wire format PENDING.
    """

    facility_ref: str
    stage: int  # 1, 2 or 3
    packet_ref: str | None = None
    as_of: datetime = field(default_factory=_utcnow)

    def __post_init__(self):
        if self.stage not in (1, 2, 3):
            raise ValueError(f"Invalid IFRS9 stage {self.stage}; must be 1, 2 or 3")


@dataclass(frozen=True)
class RequiredGuaranteeLevel:
    """Pillar 2's required pooled-guarantee level (R_pool) that P4 monitors.

    Pillar 4 NEVER re-sizes this; it only compares guarantees RECEIVED against
    it (claude.md §5.4/§5.2, §8.12). Units: admitted contingent-cash-equivalent
    value, post-haircut (like-for-like with how P4 measures the pool).
    The transport/carrier is BLOCKED by PENDING_TWO_GUARANTEE_LAYER_CONTRACT;
    this logical field models the value, not the wire.
    """

    required_amount: float
    revision_ref: str
    published_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class CASSFeedRecord:
    """CIS-1 frozen 10-field contract shape (per-facility signal feed only).

    claude.md §9, §17: CIS-1 fixes the contract SHAPE; the full P2+P4 CASS
    methodology is PENDING (PENDING_CASS_FEED_SPEC). Fields:
    facility_id, obligor_id, brr, pd, cashflow_deterioration_indicator, el,
    model_maturity_stage, brr_pd_grid_version, as_of, packet_ref.
    Provenance (model_maturity_stage, brr_pd_grid_version, packet_ref) gates
    and stamps; they do NOT feed L/S/D/F scoring.
    Dormant in Conventional Mode.
    """

    facility_id: str
    obligor_id: str
    brr: float
    pd: float
    cashflow_deterioration_indicator: bool
    el: float
    model_maturity_stage: ModelStage = ModelStage.PRODUCTION
    brr_pd_grid_version: str | None = None
    as_of: datetime = field(default_factory=_utcnow)
    packet_ref: str | None = None
