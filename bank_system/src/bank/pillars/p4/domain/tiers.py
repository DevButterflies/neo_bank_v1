"""Tier definitions (Orchestrator-sourced, consumed - never redefined).

claude.md §3: "Tier A/B/Senior Debt/C/B-Fees/D | The six-position
capital/guarantee stack | Orchestrator (§4) | Pillar 4 only *consumes* -- never
redefines." And §2: Pillar 4 reproduces no tier as an independent authority and
asserts no carve-out from Layer 1.

This module therefore models the tier TABLE as external, authoritative input.
The :class:`TierTable` is treated as read-only data supplied by the
Orchestrator (expected to change only via Orchestrator version update); Pillar 4
never mutates it and never decides whether a position is ABSF-eligible,
bail-in-eligible, or loan-funding on its own authority - it reads those
attributes from the consumed table.

The funding-vs-collateral boundary (claude.md §4.1, §5.5) is a structural
property of each tier: loan-FUNDING positions (SID, Tier C, Tier D) versus
COLLATERAL/guarantee positions (Tier A, Tier B), plus the fee stream
(Tier B-Fees).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TierPosition(str, Enum):
    TIER_A = "TierA"
    TIER_B = "TierB"
    SENIOR_INSTITUTIONAL_DEBT = "SeniorInstitutionalDebt"
    TIER_C = "TierC"  # AT2
    TIER_B_FEES = "TierBFees"
    TIER_D = "TierD"


class PositionRole(str, Enum):
    """Funding-vs-collateral boundary (Orchestrator §4; claude.md §4.1/§5.5)."""

    LOAN_FUNDING = "loan_funding"
    """Professional capital that actually funds loans: SID, Tier C, Tier D."""

    COLLATERAL_GUARANTEE = "collateral_guarantee"
    """Positions pooled-pledged as collateral, secure the book, do NOT fund:
    Tier A, Tier B."""

    FEE_STREAM = "fee_stream"
    """Tier B-Fees: not principal; a contractual distribution stream."""


@dataclass(frozen=True)
class Tier:
    """A single entry in the consumed, immutable tier table."""

    position: TierPosition
    role: PositionRole
    # Operational attributes (all read from the Orchestrator-owned table).
    absf_eligible: bool = False
    bail_in_eligible: bool = False
    # Per-client OMR ceiling (country-calibrated, Orchestrator-governed).
    omr_per_client_ceiling: float | None = None
    # Any other tier-attribute annotations (free-form, informational).
    attributes: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.position.value


def _tier(position, role, absf=False, bail_in=False, omr=None, **attrs):
    return Tier(
        position=position,
        role=role,
        absf_eligible=absf,
        bail_in_eligible=bail_in,
        omr_per_client_ceiling=omr,
        attributes=attrs,
    )


def canonical_tier_table(omr_ceiling: float = 20000.0) -> dict[TierPosition, Tier]:
    """Build the consumed tier table per claude.md §4.1's per-tier duties.

    References:
      - Tier A:  par-protected, zero loss-absorption, insured, OMR 20k/client
                 ceiling (Oman; country-calibrated).
      - Tier B:  two-mechanism protection (ABSF-shielded going concern; classic
                 foreclosure behind professional capital in liquidation).
      - SID:     loan-funding, OUTSIDE ABSF, never bail-inable - immutable.
      - Tier C:  loan-funding, ABSF-participating and bail-in eligible (AT2).
      - Tier B-Fees: simple contractual distribution in Stage 1; not principal.
      - Tier D:  primary loan-funding and loss-absorbing layer (common equity +
                 Perpetual AT1).
    """
    return {
        TierPosition.TIER_A: _tier(
            TierPosition.TIER_A,
            PositionRole.COLLATERAL_GUARANTEE,
            absf=False,
            bail_in=False,
            omr=omr_ceiling,
            protected=True,
            loss_absorption=False,
            insured=True,
        ),
        TierPosition.TIER_B: _tier(
            TierPosition.TIER_B,
            PositionRole.COLLATERAL_GUARANTEE,
            absf=False,  # shielded behind ABSF layers, not itself a participant
            bail_in=False,
            absf_shielded=True,
            foreclosure_protected=True,
        ),
        TierPosition.SENIOR_INSTITUTIONAL_DEBT: _tier(
            TierPosition.SENIOR_INSTITUTIONAL_DEBT,
            PositionRole.LOAN_FUNDING,
            absf=False,
            bail_in=False,  # NEVER bail-inable - immutable
        ),
        TierPosition.TIER_C: _tier(
            TierPosition.TIER_C,
            PositionRole.LOAN_FUNDING,
            absf=True,
            bail_in=True,  # AT2, bail-in eligible
            sub_type="AT2",
        ),
        TierPosition.TIER_B_FEES: _tier(
            TierPosition.TIER_B_FEES,
            PositionRole.FEE_STREAM,
            absf=True,  # participates in ABSF per Part III (Stage 2)
            bail_in=False,
            not_principal=True,
        ),
        TierPosition.TIER_D: _tier(
            TierPosition.TIER_D,
            PositionRole.LOAN_FUNDING,
            absf=True,
            bail_in=True,
            loss_absorbing=True,
            common_equity_plus_AT1=True,
        ),
    }
