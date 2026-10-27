"""Operating Mode - the SI-1 governance-controlled switch (claude.md §13).

Conventional Mode (Stage 1) is where the system is today. Adaptive Mode
(Stage 2) adds CASS scoring, ABSF burden-sharing, the Reverse Restoration
Waterfall, and Tier B-Fees interruption/resumption.

The ACTIVATION is a GOVERNANCE act (Governance Committee ruling), not a
deployment. Fallback (Adaptive -> Conventional) requires NO rebuild, NO book
unwind, NO contract amendment; adaptive components are DEACTIVATED, not removed.
Conventional Mode is the PERMANENT FLOOR of the system (claude.md §13).

"Deactivation is not deletion" is a hard requirement: the adaptive layer is
BUILT but gated. The ModeGate is the single governance-controlled switch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperatingMode(str):
    CONVENTIONAL = "conventional"
    ADAPTIVE = "adaptive"


class ModeGateError(Exception):
    """Raised when a mode transition is attempted outside governance rules."""


@dataclass
class ModeGate:
    """The single governance-controlled Conventional <-> Adaptive switch (SI-1).

    Defaults to CONVENTIONAL mode. Activation requires an explicit governance
    ruling (a signed, recorded act). Fallback to Conventional is always
    permitted per the permanent-floor rule.
    """

    _mode: str = OperatingMode.CONVENTIONAL
    governance_events: list = field(default_factory=list)

    @property
    def mode(self) -> str:
        return self._mode

    def is_adaptive(self) -> bool:
        return self._mode == OperatingMode.ADAPTIVE

    def is_conventional(self) -> bool:
        return self._mode == OperatingMode.CONVENTIONAL

    def activate_adaptive_mode(self, governance_ruling_ref: str, criteria_check):
        """Governance-controlled activation.

        Mirrors the Gate G1 ruling: activation is a governance act gated by
        SI-1 gate criteria (the actual numbers are PENDING_SI1_GATE_CRITERIA;
        we run the check callback but the RULING is what counts).
        """
        if self._mode == OperatingMode.ADAPTIVE:
            raise ModeGateError("Adaptive Mode is already active")
        # The governance ruling is the operative act. criteria_check is a
        # callable that can assert gate readiness; PENDING numbers are surfaced
        # there, not guessed here.
        criteria_check()
        self._mode = OperatingMode.ADAPTIVE
        self.governance_events.append(
            {
                "event": "activate_adaptive",
                "ruling_ref": governance_ruling_ref,
                "timestamp": _utcnow(),
                "mode": self._mode,
            }
        )

    def fallback_to_conventional(self, governance_ruling_ref: str):
        """Fallback to Conventional Mode - the permanent floor.

        No rebuild, no book unwind, no contract amendment (claude.md §13).
        Adaptive components are deactivated, not removed.
        """
        if self._mode == OperatingMode.CONVENTIONAL:
            return
        self._mode = OperatingMode.CONVENTIONAL
        self.governance_events.append(
            {
                "event": "fallback_conventional",
                "ruling_ref": governance_ruling_ref,
                "timestamp": _utcnow(),
                "mode": self._mode,
            }
        )
