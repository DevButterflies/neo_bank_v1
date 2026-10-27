"""Typed events and the Four-Event Discipline (claude.md §3, §4.4, §5.4).

The Four-Event Discipline states: release != redemption != foreclosure != call.
These are non-interchangeable lexical items with NO shared vocabulary, code
path, or posting type - ever (Master Lexicon; claude.md §3, §5.4, §8.11).

`redemption` is [S]-reserved and must not appear in operative [G] code paths at
all (claude.md §0 / §5.4). This module therefore has NO 'redemption' member and
defines a distinct type for each of the three [G] events.

The Two-Guarantee-Layer Rule (claude.md §3, §14) is also structurally enforced
here: default realization has exactly two distinct legs -
  COLLATERAL_LEG : realization of MSME-pledged, facility-specific collateral by
                   classical foreclosure (P3 detects, P2 decides).
  GUARANTEE_LEG  : application of the pooled guarantee by guarantee call
                   (P4 computes and settles).
These are distinct lexical/typed objects and never substitute for each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---- Pillar 3 loan-level event types (claude.md §5.4 routing table) ---------
class Pillar3EventType(str, Enum):
    SCHEDULED_REPAYMENT = "scheduled_repayment"
    ORIGINATION_FEE = "origination_fee"
    RISK_PREMIUM_ACCRUAL = "risk_premium_accrual"
    DEFAULT_OR_WRITE_OFF = "default_or_write_off"
    RECOVERY_COLLATERAL_LEG = "recovery_collateral_leg"
    GUARANTEE_CALL_GUARANTEE_LEG = "guarantee_call_guarantee_leg"


# Note: the direct IFRS9 staging signal is a Pillar-2-to-Pillar-4 feed that
# BYPASSES Pillar 3 entirely (claude.md §4.4, §5.4) - it is NOT a Pillar 3
# event. It is modelled in events.py for completeness but typed separately.


@dataclass(frozen=True)
class Pillar3Event:
    """A typed, immutable Pillar 3 per-loan event fed into the event router."""

    event_type: Pillar3EventType
    facility_ref: str
    # For repayment / premium events: the split of amounts.
    amount: float = 0.0
    principal_component: float = 0.0
    interest_component: float = 0.0
    # For default / call: realized loss context.
    collateral_leg_amount: float = 0.0
    occurred_at: datetime = field(default_factory=_utcnow)
    meta: dict = field(default_factory=dict)

    # Pillar 3 contains NO allocation logic; it just records typed events.
    # (claude.md §2, §5.4 no-allocation-logic-in-P3.)


# ---- Four-Event Discipline typed events (claude.md §5.4, §8.11) -------------
class DefaultRealizationLeg(str, Enum):
    """The two, structurally-distinct legs of default realization."""

    COLLATERAL_LEG = "collateral_leg"
    GUARANTEE_LEG = "guarantee_leg"


class Pillar4EventType(str, Enum):
    """The lexically-locked events Pillar 4 handles.

    Present in [G]: RELEASE, FORECLOSURE, CALL.
    `redemption` is [S]-reserved and intentionally ABSENT from this set.
    """

    PLEDGE_RELEASE = "pledge_release"      # pledger's going-concern exit
    CLASSICAL_FORECLOSURE = "classical_foreclosure"  # realize a DEFAULTED asset
    GUARANTEE_CALL = "guarantee_call"      # draw pooled guarantee on a loss


# ---- Intra-Pillar-4 events (claude.md §10) ----------------------------------
class IntraP4EventType(str, Enum):
    SUB_ACCOUNT_BALANCE_CHANGED = "sub_account.balance_changed"
    POOL_ADEQUACY_SHORTFALL = "pool_adequacy.shortfall_detected"
    VETO_TRACK1_TRIGGERED = "veto.track1_triggered"
    VETO_TRACK2_TRIGGERED = "veto.track2_triggered"
    GUARANTEE_CALL_SETTLED = "guarantee_call.settled"
    PLEDGE_RELEASE_REQUESTED = "pledge.release_requested"
    STAGING_SIGNAL_RECEIVED = "staging_signal.received"


@dataclass(frozen=True)
class IntraP4Event:
    """An internal Pillar 4 event (claude.md §10 internal event model)."""

    type: IntraP4EventType
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return f"<IntraP4Event {self.type.value} {self.payload!r}>"


__all__ = [
    "Pillar3EventType",
    "Pillar3Event",
    "DefaultRealizationLeg",
    "Pillar4EventType",
    "IntraP4EventType",
    "IntraP4Event",
]
