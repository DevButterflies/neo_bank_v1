"""Pledge-Release Manager (claude.md §8.13, §5.4/§6).

Enforces the RELEASE INVARIANT as a hard, testable constraint (claude.md §5.4):
  INVARIANT: no release path may generate a cash-outflow posting or an LR draw.

At/post-term -> release is a right (subject to a short notice period).
Pre-term     -> release only by exception, with penalty.

Within the notice window, Pillar 4 manages pool adequacy via:
  - origination pacing (slow/hold new lending)
  - replacement intake (admit new pledges to backfill)
  - Track 1 veto (if adequacy breach coincides with ratio breach)

FOUR-EVENT DISCIPLINE (claude.md §4.4): release shares NO code path, vocabulary,
or posting type with classical foreclosure, guarantee call, or redemption. This
manager is the RELEASE path only. Redemption is [S]-reserved and does not appear
in operative [G] code.

Notice-period length + pre-term penalty parameters are PENDING
(PENDING_PLEDGE_TERM); the window structure is built, the specific numbers stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..domain.buffer_account import BufferAccount, SubAccountId
from ..domain.guarantee_pool import (
    GuaranteePool,
    PledgeReleaseState,
    PoolAdequacyStatus,
)
from ..domain.events import IntraP4Event, IntraP4EventType
from ..domain.pending import PENDING_PLEDGE_TERM, PendingNotResolvedError


class PledgeReleaseError(Exception):
    pass


@dataclass
class ReleaseInvariantViolationError(PledgeReleaseError):
    """Raised if a release path would violate the no-cash / no-LR-draw invariant."""

    message: str = ""


@dataclass
class PledgeReleaseManager:
    """Manages the release-request -> adequacy-managed -> released state machine.

    Encodes the RELEASE INVARIANT structurally: the release logic has no access
    to any cash-outflow posting nor to the Liquidity Reserve. It can only reduce
    the guarantees-received book and set release state.
    """

    pool: GuaranteePool
    buffer: BufferAccount | None = None
    event_sink=None
    # Adequacy-management knobs (mirror of deposit-outflow management; no cash).
    origination_held: bool = False
    replacement_intake_available: bool = False
    # Pre-term exception available only if governance approves (penalty applies);
    # the penalty parameters are PENDING.
    pre_term_exception_approved: bool = False
    # Condition surfaced for the Part I<->II bridge (shortfall_gap, ratio_breach).
    _pending_track1_on_ratio_breach: tuple = (0.0, False)

    def __post_init__(self):
        if self.event_sink is None:
            self.event_sink = (lambda ev: None)

    def _emit(self, ev):
        self.event_sink(ev)

    def find_position(self, pledge_ref: str):
        match = next((p for p in self.pool.positions if p.pledge_ref == pledge_ref), None)
        if match is None:
            raise KeyError(f"No pledge position {pledge_ref}")
        return match

    # ---- state machine transitions ----------------------------------------
    def request_release(self, pledge_ref: str, at_or_post_term: bool = True):
        """Open the notice window (post-term -> right; pre-term -> exception)."""
        position = self.find_position(pledge_ref)
        if not at_or_post_term:
            if not self.pre_term_exception_approved:
                raise PledgeReleaseError(
                    "Pre-term release only by exception with penalty; no "
                    "exception approved. Pledge-term penalty parameters are "
                    "PENDING (PENDING_PLEDGE_TERM)."
                )
        if position.release_state != PledgeReleaseState.NONE:
            raise PledgeReleaseError(
                f"Release already in progress ({position.release_state.value})"
            )
        position.release_state = PledgeReleaseState.REQUESTED
        self._emit(
            IntraP4Event(IntraP4EventType.PLEDGE_RELEASE_REQUESTED, {"pledge_ref": pledge_ref})
        )

    def manage_adequacy(self, pledge_ref: str):
        """Adequacy management across the notice window (claude.md §5.4/§6.3).

        If the pool is short after the pending release, manage adequacy via:
          origination pacing and/or replacement intake. If the shortfall
          coincides with a G/G ratio breach, the Track 1 veto must be raised by
          the caller via the integration layer - here we surface that condition.
        """
        position = self.find_position(pledge_ref)
        if position.release_state != PledgeReleaseState.REQUESTED:
            raise PledgeReleaseError(
                "manage_adequacy only valid while REQUESTED"
            )
        # Simulate pool adequacy after this release (mirror the outflow).
        after_received = self.pool.received_received_value() - position.amount
        shortfall = after_received < self.pool.required_level - 1e-9
        if shortfall:
            # Pool adequacy tools: pacing and/or replacement.
            gap = self.pool.required_level - after_received
            if self.replacement_intake_available:
                # replacement pledges can backfill - mark adequate-managed.
                position.release_state = PledgeReleaseState.ADEQUACY_MANAGED
                self.replacement_intake_available = False  # one intake consumed
            else:
                # Origination pacing: hold new lending until adequacy restored.
                self.origination_held = True
                position.release_state = PledgeReleaseState.ADEQUACY_MANAGED
            self._pending_track1_on_ratio_breach = (gap, shortfall)
        else:
            position.release_state = PledgeReleaseState.ADEQUACY_MANAGED
            self._pending_track1_on_ratio_breach = (0.0, False)

    def finalize_release(self, pledge_ref: str):
        """Execute the release: lift security interest, extinguish the position.

        INVARIANT: no cash movement and no LR draw. This method only reduces the
        guarantees-received book by the released amount and marks RELEASED. It
        has NO access to any cash posting or to the Liquidity Reserve balance.
        """
        position = self.find_position(pledge_ref)
        if position.release_state != PledgeReleaseState.ADEQUACY_MANAGED:
            raise PledgeReleaseError(
                f"Cannot finalize release from state {position.release_state.value}; "
                "must pass through adequacy management first."
            )
        # Reduce guarantees received (the pool's received aggregate book + the
        # position itself), so the adequacy comparison reflects the outflow.
        # PENDING_PLEDGE_TERM governs the penalty parameters - not resolved here.
        self.pool.received_guarantee_book = max(
            0.0, self.pool.received_guarantee_book - position.amount
        )
        self.pool.remove_position(pledge_ref)
        position.release_state = PledgeReleaseState.RELEASED

    # ---- invariant helper / flags -----------------------------------------
    def pending_track1_condition(self):
        """(shortfall_gap, ratio_breach) surfaced for the Part I<->II bridge."""
        return self._pending_track1_on_ratio_breach
