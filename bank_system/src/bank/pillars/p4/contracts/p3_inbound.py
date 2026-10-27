"""Pillar 3 -> Pillar 4 inbound contracts (per-loan event log feed).

claude.md §5.4, §9: Pillar 3 emits 7 documented loan-level event types into its
event log; Pillar 4 routes each to a sub-account. Pillar 3 performs NO
allocation, burden-sharing, or repartition computation (no-allocation-logic-in-P3).
These are the typed events P4 consumes.

The 7 events (claude.md §5.4 routing table):
  scheduled_repayment, origination_fee, risk_premium_accrual,
  default_or_write_off, recovery_collateral_leg, guarantee_call_guarantee_leg
  (plus the direct IFRS9 staging signal which is P2->P4 and bypasses P3 - NOT a
  P3 event; modelled in p2_inbound.StagingSignal).

The routing MAP is a build construction (II-b); the event FORMATS are PENDING
(PENDING_LEDGER_MECHANICS). These DTOs are the stable logical event-type enum
shape - build against it, do not hard-code wire formats.
"""

from __future__ import annotations

from ..domain.events import Pillar3Event, Pillar3EventType  # noqa: F401

# Re-export the domain Pillar3Event/Pillar3EventType as the P3-inbound contract.
# Pillar 3 records these typed events; Pillar 4 routes them. No allocation
# logic is, or may be, attached to the Pillar 3 side.

__all__ = ["Pillar3Event", "Pillar3EventType"]
