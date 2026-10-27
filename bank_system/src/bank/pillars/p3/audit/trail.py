"""
Append-only audit trail — Spec §8.

    "Pillar 3 produces a clear, append-only audit trail ... No record may
    be deleted or amended after writing."

AuditTrail enforces append-only at the type level: there is no update or
delete method, and `append` returns a copy-safe reference. Records are
stored in a plain list to make "no record may be deleted or amended"
trivially auditable — a reviewer can diff the list length and contents
across two points in time.
"""
from __future__ import annotations

from typing import List

from bank.pillars.p3.domain.events import AuditRecord


class AuditTrail:
    def __init__(self) -> None:
        self._records: List[AuditRecord] = []

    def append(self, record: AuditRecord) -> None:
        self._records.append(record)

    def all_records(self) -> List[AuditRecord]:
        """Returns a shallow copy — callers cannot mutate the trail by
        mutating the returned list."""
        return list(self._records)

    def for_facility(self, facility_id: str) -> List[AuditRecord]:
        return [r for r in self._records if r.facility_id == facility_id]

    def __len__(self) -> int:
        return len(self._records)
