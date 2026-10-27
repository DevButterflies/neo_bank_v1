"""
The loan facility aggregate.

This object holds only lifecycle state and identity — no pricing, no risk
rating, no allocation. Those live in Pillar 2 / Pillar 4 and only ever
enter this object as opaque references carried on the P2 packet (grid
version, maturity stage, collateral track), never recomputed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from bank.pillars.p3.domain.collateral import CollateralObject
from bank.pillars.p3.domain.enums import LoanState


@dataclass
class LoanFacility:
    """A single MSME loan facility under Pillar 3 lifecycle management."""

    facility_id: str
    state: LoanState = LoanState.APPROVED
    origination_packet_id: Optional[str] = None
    collateral_objects: List[CollateralObject] = field(default_factory=list)
    veto_frozen: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_collateral(self, collateral: CollateralObject) -> None:
        if collateral.facility_id != self.facility_id:
            raise ValueError(
                f"Collateral object {collateral.collateral_id} references "
                f"facility {collateral.facility_id}, not {self.facility_id}."
            )
        self.collateral_objects.append(collateral)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
