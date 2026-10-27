"""
Collateral service — three-track model (Spec §4) and the two
structurally distinct collateral objects (Spec §4.1).

Two governance gates are enforced here, both structural, not advisory:

1. Recording ANY collateral object requires a validated P2 packet
   (Canon §8.4 / Interface Contract Sheet: "P3 records the confirmed
   collateral object only upon the validated P2 packet. P3 performs no
   admissibility validation.").

2. Track 2 and Track 3 are PENDING-gated. Spec §4: "No market goes live
   on Track 2 or Track 3 before the haircut-governance PENDING item is
   resolved." Build Handoff §6.2 lists "Track 2/Track 3 collateral
   recording & realization go-live per market" as a blocked item under
   THREE_TRACK_HAIRCUT_GOVERNANCE. This service therefore only records
   Track 1 objects; Track 2/3 attempts raise via the pending registry
   rather than silently succeeding.

The NEO_BANK_POOLED_GUARANTEE object kind is separately PENDING-gated
via TWO_GUARANTEE_LAYER_INTERFACE — Canon §5.2 keeps it structurally
distinct from MSME_PLEDGED, and the P2/P3/P4 recording interface for it
is explicitly open governance.
"""
from __future__ import annotations

import uuid
from typing import List

from bank.pillars.p3.domain.collateral import CollateralObject, CollateralObjectKind
from bank.pillars.p3.domain.enums import CollateralTrack
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.errors import AdmissibilityNotConfirmedError
from bank.pillars.p3.governance.pending_registry import PendingItem, stub

LIVE_TRACKS = frozenset({CollateralTrack.TRACK_1_CLASSICAL})
PENDING_TRACKS = frozenset({CollateralTrack.TRACK_2_NFT, CollateralTrack.TRACK_3_STABLECOIN})


class CollateralService:
    def __init__(self) -> None:
        self._recorded: List[CollateralObject] = []

    def record_msme_pledged_collateral(
        self,
        facility: LoanFacility,
        packet: P2OutputPacket,
        external_reference: str | None = None,
    ) -> CollateralObject:
        """Record facility-specific MSME-pledged collateral. Only
        available on Track 1 in this build; Track 2/3 raise
        PendingGovernanceItemError (see module docstring)."""
        if not packet.is_confirmed():
            raise AdmissibilityNotConfirmedError(
                f"Packet {packet.packet_id} is not confirmed/validated; "
                "P3 records collateral only on a validated P2 packet "
                "(Canon §8.4)."
            )

        track = packet.collateral_track
        if track in PENDING_TRACKS:
            stub(PendingItem.THREE_TRACK_HAIRCUT_GOVERNANCE)

        collateral = CollateralObject(
            collateral_id=f"COL-{uuid.uuid4().hex[:12]}",
            facility_id=facility.facility_id,
            kind=CollateralObjectKind.MSME_PLEDGED,
            track=track,
            model_flag=packet_model_flag_for_track(track),
            p2_packet_id=packet.packet_id,
            external_reference=external_reference,
        )
        facility.add_collateral(collateral)
        self._recorded.append(collateral)
        return collateral

    def record_pooled_guarantee_pledge(self, *_args, **_kwargs) -> None:
        """Recording a neo-bank pooled guarantee against a facility is
        blocked: the P2/P3/P4 two-guarantee-layer interface is strict
        PENDING (Canon §10, Build Handoff §6.2). Always raises."""
        stub(PendingItem.TWO_GUARANTEE_LAYER_INTERFACE)

    def recorded_for_facility(self, facility_id: str) -> List[CollateralObject]:
        return [c for c in self._recorded if c.facility_id == facility_id]


def packet_model_flag_for_track(track: CollateralTrack):
    from bank.pillars.p3.domain.enums import ModelFlag

    if track is CollateralTrack.TRACK_3_STABLECOIN:
        return ModelFlag.STABLECOIN
    return ModelFlag.GUARANTEE
