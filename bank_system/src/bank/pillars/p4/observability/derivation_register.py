"""Derivation Register + audit/observability (claude.md §1, §17, §15).

DERIVATION REGISTER
  A logged list of every build-level decision the Spec made that the Canon
  didn't literally state, so governance can review decisions rather than
  re-derive them (claude.md §1). The corpus names construction points I-a, II-b
  and a PENDING discipline; this module centralizes the log.

AUDIT / OBSERVABILITY
  claude.md §15 documents reporting obligations and a 7-year retention rule for
  buffer records, but deliberately leaves log levels, tracing, alert routing and
  SLOs to the build. This module provides a light, framework-neutral audit
  trail + a PENDING-named observability surface (no guessed thresholds).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class DerivationEntry:
    """A single logged build decision (claude.md §1, §16 derivation_register)."""

    key: str
    description: str
    basis: str          # where in the Canon it comes from (or 'inference')
    severity: str = "inference"  # explicit | inference
    recorded_at: str = field(default_factory=_utcnow)


class DerivationRegister:
    """Central, immutable-by-convention log of derivation decisions."""

    def __init__(self):
        self._entries: list[DerivationEntry] = []

    def record(self, key: str, description: str, basis: str, severity: str = "inference"):
        self._entries.append(
            DerivationEntry(key=key, description=description, basis=basis, severity=severity)
        )

    def entries(self):
        return list(self._entries)

    def export(self) -> list[dict]:
        return [
            {
                "key": e.key,
                "description": e.description,
                "basis": e.basis,
                "severity": e.severity,
                "recorded_at": e.recorded_at,
            }
            for e in self._entries
        ]


@dataclass
class AuditRecord:
    """An auditable, retained event record (claude.md §15)."""

    event_type: str
    detail: dict
    at: str = field(default_factory=_utcnow)


class AuditLedger:
    """Minimal audit ledger with retention bookkeeping.

    claude.md §15: buffer + guarantee-pool ledgers must be reconciled daily and
    retained a minimum of 7 years. This ledger records every audit-relevant
    event and stamps retention metadata; the retention PRUNING schedule is a
    build concern and left as configuration, not guessed.
    """

    RETENTION_YEARS = 7  # claude.md §15 minimum

    def __init__(self):
        self._records: list[AuditRecord] = []

    def record(self, event_type: str, detail: dict | None = None):
        self._records.append(AuditRecord(event_type=event_type, detail=detail or {}))

    def records(self):
        return list(self._records)

    def retention_months(self) -> int:
        return self.RETENTION_YEARS * 12

    def export(self) -> list[dict]:
        return [
            {"event_type": r.event_type, "detail": r.detail, "at": r.at}
            for r in self._records
        ]


def build_default_derivation_register() -> DerivationRegister:
    """Populate the register with the canonical build-level derivations.

    These are the derivations the corpus flags across its Derivation Registers
    and the deliverables produced for this implementation. Named; reviewable;
    never silently assumed.
    """
    reg = DerivationRegister()
    reg.record(
        "I-a",
        "Capital-adequacy input-binding structure: how P2 risk outputs + Part II "
        "sub-account balances bind into the capital recompute (cadence + "
        "event-driven). Canon mandates the computation, not the wiring.",
        "claude.md §4.4 / §6 (Derivation Register Part I flag)",
        severity="explicit-flag",
    )
    reg.record(
        "II-b",
        "Event-to-sub-account routing map as a build construction (the 7 P3 "
        "event types map to EL Pool / ULA / LR / RP Pool).",
        "claude.md §5.4 routing table; §8.10",
        severity="explicit-flag",
    )
    reg.record(
        "micro-macro-cut",
        "No-allocation-logic-in-P3 enforced in code: P3 emits typed events only; "
        "all allocation/burden-sharing/repartition lives in P4 (Part I/II).",
        "claude.md §2 micro/macro cut",
        severity="explicit-flag",
    )
    reg.record(
        "two-layer-type",
        "Two-Guarantee-Layer Rule encoded as a structural TYPE distinction "
        "(Pillar5AdmittedCollateral != PledgePosition) so conflation is "
        "unrepresentable, not merely disallowed.",
        "claude.md §3 / §14",
        severity="explicit-flag",
    )
    reg.record(
        "four-event",
        "Four-Event Discipline as separate code paths/vocabularies/postings: "
        "release != redemption != foreclosure != call (redemption [S]-reserved).",
        "claude.md §3 / §4.4",
        severity="explicit-flag",
    )
    reg.record(
        "pool-custody-never-resizes",
        "GuaranteePoolCustody only MONITORS adequacy vs the P2-supplied required "
        "level; it never re-sizes the requirement.",
        "claude.md §8.12",
        severity="explicit-flag",
    )
    reg.record(
        "veto-resolves-at-p2",
        "Veto state consulted by Pillar 2 at packet confirmation; never pushed "
        "to Pillar 3. Implemented as Pillar2Port.consult_veto / confirm_packet.",
        "claude.md §2.2 / §9",
        severity="explicit-flag",
    )
    return reg
