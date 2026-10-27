"""Veto Engine - Track 1 + Track 2 (claude.md §8.3, §4.4).

Pillar 4's single most consequential component - the only place where Pillar 4
can actually STOP something. Shared enforcement state machine (claude.md §4.4):

  Freeze -> Notify Orchestrator -> governance review before restart.
  The freeze cannot be overridden by Pillar 2 or Pillar 3.

RESOLUTION BOUNDARY (claude.md §2.2): a veto resolves at Pillar 2 only, as a
withheld/withdrawn output packet. Pillar 4 has NO per-loan interface with
Pillar 3. The veto STATE is something P2 must consult - it is never pushed to
Pillar 3.

TRACK 1 (portfolio-level, standing booleans, continuous): static triggers armed
in Stage 1. TRACK 2 (facility-level): violates existing P2 credit policy or P4
governance parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..domain.veto import (
    TriggerType,
    Track,
    VetoState,
)
from ..domain.events import IntraP4EventType, IntraP4Event
from ..domain.pending import (
    PendingItem,
    PENDING_CONCENTRATION_LIMITS,
    PENDING_LIQUIDITY_MINIMUM,
)


class VetoResolution(str, Enum):
    CONFIRM = "confirm"          # portfolio clear; P2 may confirm packet
    WITHHOLD = "withhold"        # veto active; P2 withholds/withdraws packet

    @property
    def consult(self) -> str:
        return self.value


@dataclass
class OrchestratorNotifier:
    """Port for the mandatory Orchestrator notification on every freeze."""

    notifications: list = field(default_factory=list)

    def notify_freeze(self, track: Track, triggers) -> None:
        self.notifications.append(
            {"event": "veto_freeze", "track": track.value, "triggers": triggers}
        )

    def notify_lift(self, track: Track, triggers, governance_ref: str) -> None:
        """Trace the governance release that ends a standing freeze."""
        self.notifications.append(
            {
                "event": "veto_lift",
                "track": track.value,
                "triggers": list(triggers),
                "governance_ref": governance_ref,
            }
        )


class Track1EvaluationError(Exception):
    """Raised when a Track 1 evaluation cannot compute a threshold cleanly.

    Used for PENDING thresholds being consumed without configuration (never a
    silent guess).
    """


class VetoEngine:
    """Evaluates Track 1 and Track 2 and drives the shared enforcement machine."""

    def __init__(
        self,
        notifier: OrchestratorNotifier | None = None,
        *,
        auto_lift_on_sustained_clean: int = 0,
    ):
        self.state = VetoState()
        self.notifier = notifier or OrchestratorNotifier()
        # A governance review gate: while TRUE, frozen actions stay frozen.
        self._governance_review_pending: dict[Track, bool] = {
            Track.TRACK1: False,
        }
        # Demo safety net (OFF by default = governance-only semantics): when
        # > 0, a standing Track-1 freeze is auto-lifted after this many
        # CONSECUTIVE clean recomputes. Never fires while the book is breached
        # — see settle_track1_recompute.
        self.auto_lift_on_sustained_clean = int(auto_lift_on_sustained_clean)
        # Consecutive authoritative recomputes observed clean while frozen.
        self._clean_recompute_run: int = 0

    # ---- Track 1 evaluation (continuous) -----------------------------------
    def evaluate_track1(
        self,
        *,
        tier_d_over_rwa: float,
        tier_d_floor: float,
        portfolio_el: float,
        budgeted_loss_ratio: float,
        gg_ratio: float | None,
        gg_bound: float | None,
        liquidity_breached: bool,
        sector_concentration_breached: bool | None = None,
        pool_concentration_breached: bool | None = None,
        cass_severe_zone: bool = False,
    ) -> list[TriggerType]:
        """Evaluate all Stage-1 static Track-1 triggers against current metrics.

        Concentration limits are PENDING: passing None means "no approved
        percentage configured" and no concentration breach is asserted (the
        monitor itself will surface the PENDING stop when asked to actually
        enforce a number). cass_severe_zone is DORMANT in Conventional Mode and
        only evaluated once the mode gate arms it (caller responsibility).
        """
        breached: list[TriggerType] = []

        if tier_d_over_rwa < tier_d_floor:
            breached.append(TriggerType.TIER_D_OVER_RWA)
        if portfolio_el > budgeted_loss_ratio:
            breached.append(TriggerType.PORTFOLIO_EL)
        if gg_ratio is not None and gg_bound is not None and gg_ratio > gg_bound:
            breached.append(TriggerType.G_G_RATIO)
        if liquidity_breached:
            breached.append(TriggerType.LIQUIDITY_BUFFER)
        if sector_concentration_breached:
            breached.append(TriggerType.SECTOR_CONCENTRATION)
        if pool_concentration_breached:
            breached.append(TriggerType.GUARANTEE_POOL_CONCENTRATION)
        if cass_severe_zone:
            # DORMANT in Stage 1; only fire if the caller has armed it via the
            # mode gate (Adaptive Mode active).
            breached.append(TriggerType.CASS_SEVERE_PRE_RESOLUTION)

        return breached

    def ensure_track1(self, breached: list[TriggerType], *, details: dict | None = None):
        """Freeze (or keep frozen) as a STANDING state if any trigger breached.

        Track 1 is a standing condition, not a one-off event: once a trigger is
        breached it freezes ALL new actions of the relevant class until
        governance lifts it (claude.md §4.5). It does not auto-clearing on a
        single clean read.
        """
        if breached:
            for t in breached:
                self.state.track1.freeze(
                    t, "standing trigger breached", details=details
                )
            # mandatory Orchestrator notification recorded once per freeze
            if self.state.track1.frozen_since is not None:
                self.notifier.notify_freeze(Track.TRACK1, [t.value for t in breached])
            return True
        return False

    def settle_track1_recompute(
        self, breached: list[TriggerType], *, details: dict | None = None
    ) -> dict:
        """Close an authoritative Track-1 recompute.

        Freezes (standing) when a trigger is breached, resetting the clean-run
        counter. On a clean read while the standing freeze is in force, feeds
        the optional demo auto-lift: after ``auto_lift_on_sustained_clean``
        consecutive clean recomputes the freeze is released via the same
        governance path as ``review_and_lift_track1`` (ref
        ``AUTO-LIFT-SUSTAINED-CLEAN``) so an unattended demo never bricks on a
        now-clean book. With the default 0 this never fires — only governance
        may lift (claude.md §4.4/§8.3).
        """
        result = {"auto_lifted": False}
        if breached:
            self._clean_recompute_run = 0
            self.ensure_track1(breached, details=details)
            return result
        if not self.state.track1.is_frozen():
            return result
        if self.auto_lift_on_sustained_clean <= 0:
            return result
        self._clean_recompute_run += 1
        if self._clean_recompute_run >= self.auto_lift_on_sustained_clean:
            self.review_and_lift_track1("AUTO-LIFT-SUSTAINED-CLEAN")
            result["auto_lifted"] = True
        return result

    def review_and_lift_track1(self, governance_ref: str):
        """Governance review has concluded; lift the freeze for the reviewed class.

        Only a governance review may lift the standing Track-1 freeze
        (claude.md §4.4/§8.3). The release is recorded against the supplied
        governance_ref so the lift is traceable, then the standing boolean is
        cleared.
        """
        triggers = [t.value for t in self.state.track1.breached_triggers]
        self.notifier.notify_lift(Track.TRACK1, triggers, governance_ref)
        self.state.track1.unfreeze()

    # ---- Track 2 evaluation (facility-level) -------------------------------
    def evaluate_track2(self, facility_ref: str, violates_policy: str | None) -> VetoResolution:
        """Evaluate a facility-level action against existing P2/P4 policy.

        If violates_policy is set (the specific policy broken), the facility is
        frozen (withheld at P2). Resolves at P2 per §2.2 - never reaches P3.
        """
        state = self.state.track2_for(facility_ref)
        if violates_policy:
            state.freeze(violates_policy)
            self.notifier.notify_freeze(Track.TRACK2, [violates_policy])
            return VetoResolution.WITHHOLD
        state.unfreeze()
        return VetoResolution.CONFIRM

    # ---- consultation interface (resolution-at-P2) -------------------------
    def consult_before_confirmation(self, facility_ref: str | None = None):
        """The veto state P2 must consult before confirming an output packet.

        Never pushed to Pillar 3 (claude.md §2.2). Whether the freeze is
        Track1-wide or Track2-for-a-facility, the answer is confirm/withhold.
        """
        if self.state.track1.is_frozen():
            return VetoResolution.WITHHOLD
        if facility_ref is not None:
            t2 = self.state.track2.get(facility_ref)
            if t2 is not None and t2.is_frozen():
                return VetoResolution.WITHHOLD
        return VetoResolution.CONFIRM
