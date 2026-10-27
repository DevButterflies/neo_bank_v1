"""
P3 <-> P4 interface — Canon §8.2 / Interface Contract Sheet §3.

    "Pillar 3 routes portfolio-level economic events to Pillar 4 for
    allocation and prudential treatment ... Freeze the affected action on
    any P4 veto (Track 1 portfolio / Track 2 facility); freeze is
    non-overridable by P2/P3."

This module owns veto application. Once a veto is applied it can only be
cleared by another explicit P4 signal through this same router — nothing
in the engine layer (state machine, posting service) can clear a veto,
which is what makes "non-overridable by P2/P3" structurally true rather
than a documented convention.
"""
from __future__ import annotations

from typing import Dict, Iterable, Set

from bank.pillars.p3.domain.enums import VetoScope
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.errors import VetoFrozenError


class P4VetoRouter:
    def __init__(self) -> None:
        self._portfolio_vetoed: bool = False
        self._facility_vetoed: Set[str] = set()

    # -- P4 signals (inbound to P3) -------------------------------------

    def apply_portfolio_veto(self, facilities: Iterable[LoanFacility]) -> None:
        """Track 1 portfolio-wide veto: freezes every facility passed in."""
        self._portfolio_vetoed = True
        for f in facilities:
            f.veto_frozen = True
            f.touch()

    def apply_facility_veto(self, facility: LoanFacility) -> None:
        """Track 2 facility-level veto: freezes a single facility."""
        self._facility_vetoed.add(facility.facility_id)
        facility.veto_frozen = True
        facility.touch()

    def clear_portfolio_veto(self, facilities: Iterable[LoanFacility]) -> None:
        """Only P4, via this explicit call, may clear a portfolio veto."""
        self._portfolio_vetoed = False
        for f in facilities:
            if f.facility_id not in self._facility_vetoed:
                f.veto_frozen = False
                f.touch()

    def clear_facility_veto(self, facility: LoanFacility) -> None:
        self._facility_vetoed.discard(facility.facility_id)
        if not self._portfolio_vetoed:
            facility.veto_frozen = False
            facility.touch()

    # -- status -----------------------------------------------------------

    def veto_status(self, facility: LoanFacility) -> Dict[VetoScope, str]:
        return {
            VetoScope.TRACK_1_PORTFOLIO: "ACTIVE" if self._portfolio_vetoed else "CLEAR",
            VetoScope.TRACK_2_FACILITY: (
                "ACTIVE" if facility.facility_id in self._facility_vetoed else "CLEAR"
            ),
        }

    def assert_not_frozen(self, facility: LoanFacility) -> None:
        if facility.veto_frozen:
            raise VetoFrozenError(
                f"Facility {facility.facility_id} is under an active, "
                "non-overridable P4 veto."
            )
