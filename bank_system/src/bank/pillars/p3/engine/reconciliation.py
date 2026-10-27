"""
Daily reconciliation — Canon §8.3 / Interface Contract Sheet §3.

    "A daily reconciliation of P3 event-log totals against core banking
    is produced; discrepancies above the P4-defined tolerance alert P4
    and governance. In any reconciliation dispute, core banking prevails
    over the Pillar 3 shadow ledger ... in all fiat accounting matters."

Two properties matter here:
1. Core banking is always treated as ground truth in a discrepancy — this
   module never "corrects" core banking to match P3's log.
2. A breach above tolerance is *raised*, not silently logged, so it can't
   be missed by a caller that forgets to check a return value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from bank.pillars.p3.core_banking.ledger import CoreBankingLedger
from bank.pillars.p3.domain.events import PostingEvent
from bank.pillars.p3.errors import ReconciliationBreachError


@dataclass(frozen=True)
class ReconciliationResult:
    p3_event_total: float
    core_banking_total: float
    discrepancy: float
    tolerance: float
    within_tolerance: bool
    unmatched_p3_event_ids: List[str]


def reconcile(
    p3_events: List[PostingEvent],
    ledger: CoreBankingLedger,
    tolerance: float,
) -> ReconciliationResult:
    p3_total = sum(e.amount for e in p3_events)
    cb_total = ledger.total_amount()
    discrepancy = abs(p3_total - cb_total)

    posted_ids = ledger.source_event_ids()
    unmatched = [e.event_id for e in p3_events if e.event_id not in posted_ids]

    within = discrepancy <= tolerance and not unmatched

    return ReconciliationResult(
        p3_event_total=p3_total,
        core_banking_total=cb_total,
        discrepancy=discrepancy,
        tolerance=tolerance,
        within_tolerance=within,
        unmatched_p3_event_ids=unmatched,
    )


def reconcile_or_alert(
    p3_events: List[PostingEvent],
    ledger: CoreBankingLedger,
    tolerance: float,
) -> ReconciliationResult:
    """Same as reconcile(), but raises ReconciliationBreachError if the
    result is outside tolerance, so a breach can't be accidentally
    ignored by a caller that doesn't check `within_tolerance`."""
    result = reconcile(p3_events, ledger, tolerance)
    if not result.within_tolerance:
        raise ReconciliationBreachError(
            f"P3/core-banking reconciliation breach: discrepancy="
            f"{result.discrepancy} > tolerance={tolerance}; "
            f"unmatched_events={result.unmatched_p3_event_ids}"
        )
    return result
