"""Pillar 4 -> Pillar 2 outbound contracts.

claude.md §6.1 / §8.3 / §9:

  - :class:`VetoConsultation` - the veto STATE Pillar 2 must consult before
    confirming any output packet. Not a "message" in the request/response
    sense; it is a state consulted by P2. The freeze CANNOT be overridden by P2
    or P3.
  - :class:`AdmissibilityPolicy` - a POLICY (eligible asset types, haircuts,
    concentration limits), NOT individual-case decisions. P2 applies it to
    every future case; P2 confirms the individual case.
  - :class:`PoolAdequacyNotice` - the communication that pool adequacy
    (shortfall) constrains origination into the P2 flow. Its precise signal is
    PENDING (PENDING_TWO_GUARANTEE_LAYER_CONTRACT) - named here as a logical
    notice whose carrier is unresolved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..domain.veto import VetoStatus, Track


@dataclass(frozen=True)
class VetoConsultation:
    """The state Pillar 2 consults before confirming a packet.

    This is the resolution-at-P2 mechanism (claude.md §2.2). Pillar 2 reads
    this state; if frozen, it withholds/withdraws the packet. The state is
    NEVER pushed to Pillar 3.
    """

    any_frozen: bool
    track1_frozen: bool
    track1_triggers: tuple = ()
    track2_frozen_for_facility: bool = False
    track2_policy: str | None = None


@dataclass(frozen=True)
class AdmissibilityPolicy:
    """Pillar 4's collateral admissibility POLICY (types, haircuts, limits).

    A policy, not a case decision. Versioned so prospective application is
    traceable. Concentration limit percentages are PENDING
    (PENDING_CONCENTRATION_LIMITS); haircut percentages per asset class are
    populated where settled and surfaced as PENDING stops where not.
    """

    policy_version: str
    eligible_asset_types: tuple = ()
    haircuts_by_asset_class: dict = field(default_factory=dict)
    concentration_limits: dict | None = None  # None => PENDING_CONCENTRATION_LIMITS
    revaluation_frequency_by_asset_class: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PoolAdequacyNotice:
    """Logical notice that pool adequacy constrains origination.

    Shortfall -> origination paced/held. If shortfall COINCIDES with a
    G/G-ratio breach -> Track 1 veto. The precise carrier P4 uses to
    communicate "hold origination" back into the P2 flow is the open
    two-guarantee-layer data-field contract (claude.md §14, §17).
    """

    adequacy_ok: bool
    shortfall_amount: float
    track1_triggered: bool = False
