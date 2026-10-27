"""Concrete Mode Gate service (governance-controlled switch).

Wraps the domain :class:`~pillar4.domain.mode_state.ModeGate` and provides the
service-level interface used by the rest of Pillar 4 (and, at Stage 2, by
callers that ask whether adaptive components may run).

Guarantees:
  - Conventional Mode is the DEFAULT and the PERMANENT FLOOR.
  - Adaptive activation requires an explicit governance ruling (ActivationRule).
  - Everything adaptive is dormant while mode == conventional.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.mode_state import ModeGate, ModeGateError, OperatingMode


@dataclass
class GovernanceRuling:
    """An explicit, signed record of a governance decision (SI-1 act)."""

    ruling_ref: str
    rule_type: str  # e.g. "activate_adaptive", "fallback_conventional"
    signed_by: str
    detail: str = ""


class ModeGateService:
    def __init__(self):
        self._gate = ModeGate()

    @property
    def mode(self) -> str:
        return self._gate.mode

    def is_adaptive(self) -> bool:
        return self._gate.is_adaptive()

    def is_conventional(self) -> bool:
        return self._gate.is_conventional()

    def activate_adaptive(self, ruling: GovernanceRuling, criteria_check=None):
        """Activate Adaptive Mode under an explicit governance ruling.

        Passing criteria_check (callable) lets the caller assert SI-1 Gate G1
        readiness. The PENDING gate criteria numbers are surfaced there, never
        guessed here (claude.md §13, §17 PENDING_SI1_GATE_CRITERIA).
        """
        if criteria_check is None:
            criteria_check = lambda: None  # noqa: E731
        self._gate.activate_adaptive_mode(ruling.ruling_ref, criteria_check)
        # record the full ruling (signed, so the governance act is auditable)
        self._gate.governance_events[-1]["signed_by"] = ruling.signed_by
        self._gate.governance_events[-1]["detail"] = ruling.detail

    def fallback_to_conventional(self, ruling: GovernanceRuling):
        self._gate.fallback_to_conventional(ruling.ruling_ref)

    def require_adaptive(self):
        """Raise if Adaptive Mode is not active (used to guard adaptive paths)."""
        if not self._gate.is_adaptive():
            raise ModeGateError(
                "Adaptive component is dormant: Pillar 4 is in Conventional "
                "Mode. Adaptive machinery is built but gated by governance "
                "(SI-1); it must not run in Conventional Mode."
            )
