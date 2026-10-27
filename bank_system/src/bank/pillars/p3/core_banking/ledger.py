"""
Core banking: the accounting system of record for all fiat postings.

Canon §3.3 / §8.3: "Core banking is the accounting system of record for
all fiat postings ... In any reconciliation dispute, core banking
prevails over the Pillar 3 shadow ledger ... in all fiat accounting
matters."

This module is a minimal stand-in for a real core banking system so the
Pillar 3 build can be developed and tested against a stable interface
(Build Handoff §8: "Build the interface contracts ... against a test
core-banking ledger first — they are the load-bearing seams."). It is
intentionally simple: real core banking is out of scope for Pillar 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from bank.pillars.p3.domain.events import PostingEvent


@dataclass(frozen=True)
class CoreBankingPosting:
    """A posting as recorded on the core banking side, keyed by the
    event_id that produced it so P3<->core-banking reconciliation is a
    simple set comparison."""

    posting_id: str
    source_event_id: str
    facility_id: str
    amount: float
    currency: str
    posted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CoreBankingLedger:
    """In-memory stand-in for the core banking system of record.

    P3 never reads or writes this class directly in production topology —
    it goes through CoreBankingClient (interface.py) — but tests may
    inspect it to assert postings landed correctly.
    """

    def __init__(self) -> None:
        self._postings: Dict[str, CoreBankingPosting] = {}
        self._next_id = 1

    def post(self, event: PostingEvent) -> CoreBankingPosting:
        posting_id = f"CB-{self._next_id:08d}"
        self._next_id += 1
        posting = CoreBankingPosting(
            posting_id=posting_id,
            source_event_id=event.event_id,
            facility_id=event.facility_id,
            amount=event.amount,
            currency=event.currency,
        )
        self._postings[posting.posting_id] = posting
        return posting

    def postings_for_facility(self, facility_id: str) -> List[CoreBankingPosting]:
        return [p for p in self._postings.values() if p.facility_id == facility_id]

    def all_postings(self) -> List[CoreBankingPosting]:
        return list(self._postings.values())

    def source_event_ids(self) -> set:
        return {p.source_event_id for p in self._postings.values()}

    def total_amount(self) -> float:
        return sum(p.amount for p in self._postings.values())
