"""P2 -> P3 packet translator — the orchestrator's core integration piece.

Pure mapping, mirroring ``combined/orchestrator/adapters/p2_to_p3.py`` on the
``bank.*`` import set: every field on the P3 ``P2OutputPacket`` is taken
verbatim from the P2 ``OutputPacket``, or is a credit-officer / P4 signal
supplied by the caller. Adds no business logic and re-derives nothing.
"""

from __future__ import annotations

import uuid

from bank.pillars.p2.schemas import OutputPacket as P2Packet
from bank.pillars.p3.domain.enums import (
    CollateralTrack as P3CollateralTrack,
    MaturityStage as P3MaturityStage,
    P2PacketStatus as P3PacketStatus,
)
from bank.pillars.p3.domain.packet import P2OutputPacket as P3Packet

# P2's CollateralTrack has a NONE member P3's enum does not carry. Falling back
# to TRACK_1_CLASSICAL is a demo-harmless default: no pledge action is fired for
# an uncollateralised facility, so the field is only recorded, never acted on.
_TRACK_MAP = {
    "NONE": P3CollateralTrack.TRACK_1_CLASSICAL,
    "TRACK_1_CLASSICAL": P3CollateralTrack.TRACK_1_CLASSICAL,
    "TRACK_2_NFT": P3CollateralTrack.TRACK_2_NFT,
    "TRACK_3_STABLECOIN": P3CollateralTrack.TRACK_3_STABLECOIN,
}


def translate_packet(
    p2_packet: P2Packet,
    facility_id: str,
    officer_confirmed: bool = False,
    officer_id: str | None = None,
    human_authorised_for_workout: bool = False,
    packet_version: str = "v1",
) -> P3Packet:
    """Map a real Pillar 2 ``OutputPacket`` onto the ``P2OutputPacket`` shape
    Pillar 3 is contractually allowed to consume.

    ``officer_confirmed`` / ``officer_id`` / ``human_authorised_for_workout``
    are NOT read off the P2 packet — they are separate human-authority signals
    supplied by whoever calls this, exactly as they would arrive from a real
    credit officer, never inferred from the risk numbers (Canon §6.5, §8.1).
    """
    return P3Packet(
        packet_id=f"P2-{p2_packet.application_id}-{uuid.uuid4().hex[:6].upper()}",
        facility_id=facility_id,
        status=P3PacketStatus(p2_packet.status.value),
        maturity_stage=P3MaturityStage(p2_packet.model_maturity_stage.value),
        brr_pd_grid_version=p2_packet.pd_grid_version,
        collateral_track=_TRACK_MAP[p2_packet.collateral_track.value],
        packet_version=packet_version,
        officer_confirmed=officer_confirmed,
        officer_id=officer_id,
        human_authorised_for_workout=human_authorised_for_workout,
    )


def facility_id_for(candidate_id: str) -> str:
    """Deterministic facility id per candidate: ``FAC-<candidate>[0:10].upper()``."""
    return f"FAC-{candidate_id[:10].upper()}"