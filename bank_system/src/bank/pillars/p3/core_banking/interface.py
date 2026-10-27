"""
CoreBankingClient — the P3-side of the P3<->core-banking interface
(Interface Contract Sheet §3: "P3 is event producer; core banking is
system of record for all fiat postings. Carry the full per-loan posting
set.")

This is the only object in the codebase allowed to write to
CoreBankingLedger. Keeping it as a single seam makes the "core banking is
system of record" rule structurally true rather than a convention that
other modules could bypass.
"""
from __future__ import annotations

from bank.pillars.p3.core_banking.ledger import CoreBankingLedger, CoreBankingPosting
from bank.pillars.p3.domain.events import PostingEvent


class CoreBankingClient:
    def __init__(self, ledger: CoreBankingLedger) -> None:
        self._ledger = ledger

    def post_event(self, event: PostingEvent) -> CoreBankingPosting:
        """Post a single per-loan event to core banking. Returns the
        confirmed core-banking posting; P3's own event log records the
        posting_id as confirmation (Spec §8, 'confirmation it was posted
        to core banking')."""
        return self._ledger.post(event)

    def ledger(self) -> CoreBankingLedger:
        """Read-only handle for reconciliation. Do not use this to write
        postings from outside this client."""
        return self._ledger
