"""Event Router (claude.md §8.10, §5.4).

Why it exists: to enforce, in code, the "no-allocation-logic-in-P3" rule.
Pillar 3 doesn't decide where its own events go - it just emits typed events
that Pillar 4 routes according to a FIXED map.

Responsibility: map each Pillar 3 event type to its sub-account and downstream
use (claude.md §5.4 routing table). The routing MAP is a build construction
(Derivation Register II-b); the event FORMATS are PENDING (PENDING_LEDGER_MECHANICS)
- build the router against a stable logical event-type enum, don't hard-code
wire formats.

Role: this is the ONLY entry point for Pillar 3 loan-level events into Pillar 4.
There is no other per-loan interface with Pillar 3 (claude.md §2.2).
"""

from __future__ import annotations

from ..domain.events import Pillar3Event, Pillar3EventType
from ..domain.buffer_account import BufferAccount
from ..domain.events import IntraP4Event, IntraP4EventType


class EventRouter:
    """Maps typed Pillar 3 events to sub-account postings (P4-side decision)."""

    def __init__(self, buffer: BufferAccount, event_sink=None):
        self._buffer = buffer
        self._event_sink = event_sink or (lambda ev: None)

    def _emit(self, ev: IntraP4Event):
        self._event_sink(ev)

    def route(self, event: Pillar3Event):
        """Route a Pillar 3 per-loan event to its sub-account.

        Routing table (claude.md §5.4):
          scheduled_repayment          -> RP Pool (risk-premium component)
          origination_fee              -> RP Pool (revenue, not buffer)
          risk_premium_accrual         -> RP Pool
          default_or_write_off         -> EL Pool (provision utilisation)
          recovery_collateral_leg      -> EL Pool / ULA Buffer (recovery credit)
          guarantee_call_guarantee_leg -> recorded; the settlement itself is a
                                          Pillar 4 macro operation in the
                                          guarantee-call engine - NOT posted
                                          here (no double post).

        The router NEVER returns allocation logic to Pillar 3.
        """
        t = event.event_type
        if t == Pillar3EventType.SCHEDULED_REPAYMENT:
            # Scheduled repayment: interest (risk premium) component funds the
            # EL Pool via the RP Pool; principal returns to the funder side.
            self._buffer.rp_pool.credit(event.interest_component, "risk_premium")
        elif t == Pillar3EventType.ORIGINATION_FEE:
            # Origination fee: revenue recognition, margin retention - RP Pool.
            self._buffer.rp_pool.credit(event.amount, "origination_fee")
        elif t == Pillar3EventType.RISK_PREMIUM_ACCRUAL:
            self._buffer.rp_pool.credit(event.amount, "risk_premium")
        elif t == Pillar3EventType.DEFAULT_OR_WRITE_OFF:
            # Provision utilisation draws against the EL Pool. The boundary
            # beyond Budgeted Loss (moving into ULA Buffer / guarantee call /
            # funder distribution) is handled by Part II's default handling and
            # the guarantee-call settlement engine, not by a blind debit here.
            self._buffer.el_pool.debit(event.amount, "provision_utilisation")
        elif t == Pillar3EventType.RECOVERY_COLLATERAL_LEG:
            # Recovery on the collateral leg: credit EL Pool (provision release).
            self._buffer.el_pool.credit(event.amount, "recovery_collateral_leg")
        elif t == Pillar3EventType.GUARANTEE_CALL_GUARANTEE_LEG:
            # The guarantee leg is COMPUTED and SETTLED by Pillar 4's settlement
            # engine (§4 of claude.md §5.4). This typed event is the RECORD of
            # the call; the actual draw/passage/distribution is a Pillar 4 macro
            # operation performed by the GuaranteeCallSettlementEngine. To avoid
            # double posting, the router does not mutate the buffer here; it
            # only surfaces the call for settlement.
            self._emit(
                IntraP4Event(
                    IntraP4EventType.GUARANTEE_CALL_SETTLED,
                    {"facility_ref": event.facility_ref, "amount": event.amount},
                )
            )
            return
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unhandled Pillar 3 event type {t}")

        self._emit(
            IntraP4Event(IntraP4EventType.SUB_ACCOUNT_BALANCE_CHANGED, {}),
        )
