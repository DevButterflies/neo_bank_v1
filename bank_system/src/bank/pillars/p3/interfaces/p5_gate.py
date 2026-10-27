"""
P3 <-> P5 interface — Canon §8.5 (admissibility gate only).

    "Pillar 5 is strictly external. Pillar 3 records a Pillar 5 object
    ... only upon explicit admissibility confirmation arriving through
    the Pillar 4 -> Pillar 2 chain. Until confirmation is received, no
    Pillar 5 object may appear in any loan record, collateral position,
    or portfolio report. Pillar 3 holds no risk interface with Pillar 5."

The gate is modelled as a single boolean carried on the P2 packet: there
is no separate "ask P5 directly" code path in this module at all,
because Canon §8.5 says P3 "holds no risk interface with Pillar 5" —
the only channel is P4->P2.
"""
from __future__ import annotations

from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.errors import AdmissibilityNotConfirmedError


class P5Gate:
    def record_if_confirmed(self, packet: P2OutputPacket, p5_object_reference: str) -> str:
        """Return the P5 object reference if it may be recorded; raise
        otherwise. The confirmation must have arrived via the P4->P2
        chain, i.e. it must already be present, confirmed, on the P2
        packet P3 is consuming. P3 does not query P5 directly."""
        if not packet.is_confirmed():
            raise AdmissibilityNotConfirmedError(
                f"Packet {packet.packet_id} carries no confirmed P4->P2 "
                "admissibility chain; a Pillar 5 object may not be "
                "recorded (Canon §8.5)."
            )
        return p5_object_reference
