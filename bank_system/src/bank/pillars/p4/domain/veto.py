"""Two-track prudential veto - domain state and shared enforcement.

claude.md §4.4, §8.3: Pillar 4 holds final prudential veto over originations,
restructurings, collateral substitutions, pricing changes, and recovery actions.
There are TWO tracks sharing ONE enforcement state-machine:

  TRACK 1 (portfolio-level, standing/continuous): static triggers armed in
    Stage 1 - Tier D/RWA<12%, EL>2%, sector/MSME concentration, guarantee-pool
    concentration, G/G ratio breach, LR below minimum. (7th trigger - CASS
    Severe Pre-Resolution zone - is DORMANT until Stage 2.)
  TRACK 2 (facility-level): an individual loan decision violates existing P2
    credit policy or P4 governance parameters, even when portfolio metrics are
    in bounds.

Shared enforcement (claude.md §4.4/§2.1): Freeze -> notify Orchestrator ->
governance review before restart. The freeze CANNOT be overridden by P2 or P3.

Resolution boundary (claude.md §2.2/§4.4): a veto resolves at Pillar 2 only,
as a withheld/withdrawn output packet. Pillar 4 has NO per-loan interface with
Pillar 3. The veto STATE is something P2 must consult; it is never pushed to P3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Track(str, Enum):
    TRACK1 = "track1"
    TRACK2 = "track2"


class TriggerType(str, Enum):
    TIER_D_OVER_RWA = "tier_d_over_rwa"
    PORTFOLIO_EL = "portfolio_el"
    SECTOR_CONCENTRATION = "sector_concentration"
    GUARANTEE_POOL_CONCENTRATION = "guarantee_pool_concentration"
    G_G_RATIO = "guarantees_granted_received_ratio"
    LIQUIDITY_BUFFER = "liquidity_buffer_below_minimum"
    CASS_SEVERE_PRE_RESOLUTION = "cass_severe_pre_resolution"  # DORMANT in Stage 1


class VetoStatus(str, Enum):
    CLEAR = "clear"
    FROZEN = "frozen"


@dataclass
class Track1State:
    """Portfolio-level veto state - a standing boolean, not a one-off event.

    Each trigger is a standing violated/not-violated condition re-evaluated
    continuously (claude.md §4.7).
    """

    status: VetoStatus = VetoStatus.CLEAR
    breached_triggers: dict[TriggerType, str] = field(default_factory=dict)
    # Held when frozen so a subsequent evaluation knows what's frozen.
    frozen_since: datetime | None = None
    # Traceability: the governing metric values captured when each trigger
    # first tripped the freeze (e.g. portfolio_el / budgeted_loss_ratio at the
    # moment EL breached). Plain JSON-safe dict, keyed by trigger.value.
    freeze_details: dict[str, dict] = field(default_factory=dict)

    def freeze(self, trigger: TriggerType, reason: str, details: dict | None = None):
        self.status = VetoStatus.FROZEN
        if trigger not in self.breached_triggers:
            self.breached_triggers[trigger] = reason
            if details is not None:
                self.freeze_details[trigger.value] = dict(details)
        if self.frozen_since is None:
            self.frozen_since = _utcnow()

    def unfreeze(self):
        self.status = VetoStatus.CLEAR
        self.breached_triggers.clear()
        self.frozen_since = None
        self.freeze_details.clear()

    def is_frozen(self) -> bool:
        return self.status == VetoStatus.FROZEN


@dataclass
class Track2State:
    """Facility-level veto state, per facility (claude.md §8.3)."""

    status: VetoStatus = VetoStatus.CLEAR
    breached_policy: str | None = None
    frozen_since: datetime | None = None

    def freeze(self, policy: str):
        self.status = VetoStatus.FROZEN
        self.breached_policy = policy
        if self.frozen_since is None:
            self.frozen_since = _utcnow()

    def unfreeze(self):
        self.status = VetoStatus.CLEAR
        self.breached_policy = None
        self.frozen_since = None

    def is_frozen(self) -> bool:
        return self.status == VetoStatus.FROZEN


@dataclass
class OrchestratorNotificationLog:
    """Log of Orchestrator notifications (mandatory on every freeze, both tracks)."""

    entries: list = field(default_factory=list)

    def record(self, track: Track, triggers, timestamp: datetime):
        self.entries.append(
            {
                "track": track.value,
                "triggers": triggers,
                "timestamp": timestamp,
            }
        )


@dataclass
class VetoState:
    """Aggregate veto state (singleton per track scope) + notification log.

    consulted BY Pillar 2 before confirming an output packet (claude.md §8.3,
    §9). Never pushed to Pillar 3.
    """

    track1: Track1State = field(default_factory=Track1State)
    track2: dict[str, Track2State] = field(default_factory=dict)
    notification_log: OrchestratorNotificationLog = field(default_factory=OrchestratorNotificationLog)

    def track2_for(self, facility_ref: str) -> Track2State:
        return self.track2.setdefault(facility_ref, Track2State())

    def any_frozen(self) -> bool:
        if self.track1.is_frozen():
            return True
        return any(s.is_frozen() for s in self.track2.values())
