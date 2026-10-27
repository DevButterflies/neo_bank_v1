"""
P2 -> P3 interface — Canon §8.1 / Interface Contract Sheet §3.

    "Pillar 3 consumes approved, provisional, or conditional Pillar 2
    output packets. It records the Model Maturity Stage, BRR-PD grid
    version, and collateral track carried by the packet."

This module is the single intake point for P2 packets. It records the
packet (append-only) and runs the Maturity Stage gate before allowing
origination to proceed — it does not re-derive or second-guess anything
on the packet itself.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.governance.maturity_gate import ProductionAutoApproval, check_origination_gate


class P2Gate:
    def __init__(self) -> None:
        self._received: Dict[str, P2OutputPacket] = {}

    def receive_packet(self, packet: P2OutputPacket) -> None:
        """Record the packet. Recording is unconditional (Canon: P3
        'records the Model Maturity Stage, BRR-PD grid version, and
        collateral track' regardless of confirmation status) — the gate
        is applied separately, at origination time, not at intake."""
        self._received[packet.packet_id] = packet

    def authorize_origination(
        self,
        packet_id: str,
        production_auto_approval: Optional[ProductionAutoApproval] = None,
    ) -> P2OutputPacket:
        """Run the Maturity Stage gate for this packet and return it if
        origination is permitted. Raises otherwise."""
        packet = self._received[packet_id]
        check_origination_gate(packet, production_auto_approval)
        return packet

    def get(self, packet_id: str) -> P2OutputPacket:
        return self._received[packet_id]

    def all_received(self) -> List[P2OutputPacket]:
        return list(self._received.values())
