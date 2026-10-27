"""Tier Consumption Service (claude.md §8.1).

Why it exists: Pillar 4 must apply tier-specific operational treatment
(ceilings, protection status, ABSF eligibility) without ever being the SOURCE
of tier definitions.

Responsibility: hold a READ-ONLY, Orchestrator-sourced tier table and expose
per-tier query methods. Internal to Pillar 4 only. Pure lookup against
Orchestrator-owned data; communicates with nothing outside Pillar 4.
"""

from __future__ import annotations

from ..domain.tiers import canonical_tier_table, PositionRole, Tier, TierPosition


class TierConsumptionService:
    """Consumes the Orchestrator-sourced tier table; never redefines it."""

    def __init__(self, table: dict[TierPosition, Tier] | None = None):
        # The tier table is external, authoritative, and read-only. It is
        # expected to change only via an Orchestrator version update. Pillar 4
        # never mutates it and never decides tier attributes on its own.
        self._table = table or canonical_tier_table()

    def tier(self, position: TierPosition) -> Tier:
        return self._table[position]

    def replace_table_from_orchestrator(self, table: dict[TierPosition, Tier]):
        """Consume a new Orchestrator-versioned tier table (authoritative input)."""
        self._table = table

    # ---- per-tier queries -------------------------------------------------
    def is_absf_eligible(self, position: TierPosition) -> bool:
        return self._table[position].absf_eligible

    def is_bail_in_eligible(self, position: TierPosition) -> bool:
        return self._table[position].bail_in_eligible

    def role(self, position: TierPosition) -> PositionRole:
        return self._table[position].role

    def is_loan_funding(self, position: TierPosition) -> bool:
        return self._table[position].role == PositionRole.LOAN_FUNDING

    def omr_ceiling(self, position: TierPosition) -> float | None:
        return self._table[position].omr_per_client_ceiling

    # Tier D / RWA numerator composition (Basel-conventional; claude.md §4.4).
    def tier_d_positions(self) -> tuple[TierPosition, ...]:
        return (TierPosition.TIER_D,)

    # The loss-absorbing / funding perimeter that participates in ABSF/bail-in.
    def absf_perimeter(self) -> tuple[TierPosition, ...]:
        return tuple(
            p for p, t in self._table.items() if t.absf_eligible and p
            not in (TierPosition.SENIOR_INSTITUTIONAL_DEBT,)
        )
