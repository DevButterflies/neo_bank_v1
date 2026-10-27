"""Mode Gate - the single governance-controlled Conventional <-> Adaptive switch.

claude.md §1, §13, §16: the adaptive machinery is BUILT but gated behind a mode
switch that governance - not code - controls. "Deactivation is not deletion."
This package is the concrete service exposing that switch, backed by the domain
:class:`pillar4.domain.mode_state.ModeGate`.
"""

from .mode_gate import ModeGateService  # noqa: F401

__all__ = ["ModeGateService"]
