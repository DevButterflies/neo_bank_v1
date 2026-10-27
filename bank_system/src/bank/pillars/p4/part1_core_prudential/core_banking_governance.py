"""Core Banking Governance (claude.md §8.8, §4.4/§6).

Why it exists: Pillar 4 sets the prudential RULES core banking must follow,
without owning core banking. Responsibility: define API integration standards,
reconciliation-tolerance thresholds, CBO regulatory reporting format
requirements, and the accounting treatment of guarantee positions. Outputs:
governance standards/config consumed by whoever builds/operates core banking.

Key CONSUMED rule: core banking ALWAYS wins reconciliation disputes against
the Pillar 3 event log (claude.md §6.2). Pillar 4 governs the TOLERANCE, not
the precedence (precedence is Orchestrator-fixed).

The reuse points: daily reconciliation of buffer + guarantee-pool ledger against
core banking, discrepancy-above-tolerance -> alert, 7-year retention minimum
(claude.md §15). Tolerance VALUE is PENDING (PENDING_LEDGER_MECHANICS /
reconciliation tolerance).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.pending import PENDING_LEDGER_MECHANICS, PendingNotResolvedError


@dataclass
class Reconciliation:
    """A reconciled comparison of a P4 sub-account / event-log total vs core
    banking balance.

    Core banking prevails in any fiat accounting dispute (claude.md §6.2).
    The discrepancy-above-TOLERANCE alerting rule is enforced here; the
    tolerance VALUE is PENDING and stops loud when unconfigured.
    """

    reference: str          # e.g. the buffer/ledger total reference
    p4_ledger_total: float
    core_banking_balance: float
    tolerance: float | None = None  # PENDING until a value is approved

    @property
    def discrepancy(self) -> float:
        return abs(self.p4_ledger_total - self.core_banking_balance)

    def is_above_tolerance(self) -> bool:
        if self.tolerance is None:
            raise PendingNotResolvedError(PENDING_LEDGER_MECHANICS)
        return self.discrepancy > self.tolerance

    @property
    def resolved_by(self) -> str:
        # System-of-record rule: core banking always prevails (claude.md §6.2).
        return "core_banking"


@dataclass
class CoreBankingGovernanceStandards:
    """Pillars 4's prudential standards/reference data for core banking."""

    # 7-year retention minimum for all buffer account records (claude.md §15).
    retention_years: int = 7

    # API integration standards / CBO format requirements (informational here).
    api_standards: dict = field(default_factory=dict)
    cbo_reporting_formats: dict = field(default_factory=dict)

    def reconcile(self, rec: Reconciliation) -> dict:
        """Run a daily reconciliation; alert if discrepancy above tolerance.

        Alerting above tolerance -> Pillar 4 governance. Precedence remains
        core banking (system of record) regardless of outcome.
        """
        above = rec.is_above_tolerance()  # may raise PENDING stop if no tolerance
        return {
            "reference": rec.reference,
            "discrepancy": rec.discrepancy,
            "above_tolerance": above,
            "alert_to_governance": above,
            "resolved_by": rec.resolved_by,
            "retention_years": self.retention_years,
        }
