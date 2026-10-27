"""Canonical memo strings for the Pillar 3 posting set.

``PostingEvent.memo`` is free text on the wire but carries *semantic* meaning
for aggregation: the bilan decides what is a drawdown, what is a repayment and
what is a write-off by comparing this string. Defining them once here stops the
engine, the P1 simulator and the bilan aggregator from drifting apart.

These strings are persisted in the database. Changing one is a data migration,
not a rename.
"""

from __future__ import annotations

MEMO_DISBURSEMENT = "disbursement"
MEMO_SCHEDULED_PRINCIPAL = "scheduled principal"
MEMO_SCHEDULED_INTEREST = "scheduled interest"
MEMO_WRITE_OFF = "write-off"
MEMO_RECOVERY = "recovery receipt"
MEMO_DEFAULT_MARKER = "default event marker"
