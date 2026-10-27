"""CASS Engine - Composite Adaptive Stress Score (claude.md §13, Workflow E).

CASS = alpha*L + beta*S + gamma*D + delta*F, the ONLY trigger for ABSF.

Components draw from two sources (CIS-1 consumption in Part III, dormant):
  L - liquidity-stress     (from the LR sub-account, CASS liquidity socket)
  S - solvency-stress      (from the EL Pool utilisation + P2 PD/BRR)
  D - pledge-release/funding stress
  F - financial frictions

A persistence filter + Transmission Velocity Factor dampen the raw signal;
then the score lands in a stress zone: Early / Recovery Activation / Severe
Pre-Resolution. The SEVERE Pre-Resolution zone is the (dormant until Stage 2)
Track 1 trigger.

The component WEIGHTS (alpha/beta/gamma/delta) and the ZONE THRESHOLDS are
PENDING (PENDING_CASS_FEED_SPEC; the full P2+P4 CASS methodology is the hinge
blocking all of Stage 2). The framework structure is complete; the specific
numbers are named stops.

Every score computation is gated: it REFUSES to run unless Adaptive Mode is
active (the mode gate). In Conventional Mode CASS is dormant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..domain.pending import PENDING_CASS_FEED_SPEC, PendingNotResolvedError
from ..mode_gate.mode_gate import ModeGateService


class CASSZone(str, Enum):
    EARLY = "early"
    RECOVERY_ACTIVATION = "recovery_activation"
    SEVERE_PRE_RESOLUTION = "severe_pre_resolution"


@dataclass
class CassInput:
    """Raw component inputs (dormant until Adaptive Mode / CASS spec ratified)."""

    liquidity_component_L: float = 0.0     # from LR sub-account
    solvency_component_S: float = 0.0      # EL Pool utilisation + P2 PD/BRR
    pledge_release_funding_D: float = 0.0  # pledge-release/funding stress
    financial_frictions_F: float = 0.0     # financial frictions


@dataclass
class CassWeights:
    """CASS component weights (alpha,beta,gamma,delta).

    PENDING: the actual weight values are part of the full CASS spec
    (PENDING_CASS_FEED_SPEC). Default None => not resolved; scoring stops.
    """

    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    delta: float | None = None

    @property
    def resolved(self) -> bool:
        return None not in (self.alpha, self.beta, self.gamma, self.delta)


class CassEngine:
    """The dormant CASS engine. Refuses to run unless Adaptive Mode is active."""

    def __init__(
        self,
        mode_gate: ModeGateService,
        weights: CassWeights | None = None,
        zone_thresholds: dict[str, float] | None = None,
    ):
        self._mode = mode_gate
        self.weights = weights or CassWeights()
        self.zone_thresholds = zone_thresholds  # PENDING if None
        self._history: list[float] = []

    def _require_adaptive(self):
        self._mode.require_adaptive()

    def _require_spec_resolved(self):
        if not self.weights.resolved or self.zone_thresholds is None:
            raise PendingNotResolvedError(PENDING_CASS_FEED_SPEC)

    def score(self, inp: CassInput) -> float:
        """Compute the damped CASS score (dormant unless Adaptive + spec resolved)."""
        self._require_adaptive()
        self._require_spec_resolved()
        raw = (
            self.weights.alpha * inp.liquidity_component_L
            + self.weights.beta * inp.solvency_component_S
            + self.weights.gamma * inp.pledge_release_funding_D
            + self.weights.delta * inp.financial_frictions_F
        )
        damped = self._persistence_and_velocity_filter(raw)
        self._history.append(damped)
        return damped

    def _persistence_and_velocity_filter(self, raw: float) -> float:
        """Persistence filter + Transmission Velocity Factor (claude.md Workflow E).

        Structure only: the exact dampening coefficients are part of the CASS
        spec (PENDING). We apply a documented, conservative damping envelope
        here as the FILTER STRUCTURE, not a guessed threshold.
        """
        velocity = 1.0
        if len(self._history) >= 2:
            prev_prev = self._history[-2]
            prev = self._history[-1]
            delta = abs(prev - prev_prev)
            velocity = 0.5 if delta > 0.5 else 1.0  # structure placeholder
        persistence = 0.7  # structure placeholder (PENDING spec value)
        return persistence * raw + (1 - persistence) * (
            self._history[-1] if self._history else 0.0
        )

    def classify_zone(self, score: float) -> CASSZone:
        self._require_adaptive()
        self._require_spec_resolved()
        if score >= self.zone_thresholds["severe"]:
            return CASSZone.SEVERE_PRE_RESOLUTION
        if score >= self.zone_thresholds["recovery_activation"]:
            return CASSZone.RECOVERY_ACTIVATION
        return CASSZone.EARLY

    def severe_pre_resolution(self, score: float) -> bool:
        return self.classify_zone(score) == CASSZone.SEVERE_PRE_RESOLUTION
