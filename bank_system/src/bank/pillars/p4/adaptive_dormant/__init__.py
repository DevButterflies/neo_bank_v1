"""Dormant Adaptive Layer - Stage-2 sockets, built fully, gated, never active by default.

claude.md §1, §13, §16: the adaptive machinery is BUILT but gated behind the
governance-controlled Mode Gate (SI-1). "Deactivation is not deletion" is a
hard requirement - this module is real, separately-deployable-but-DISABLED, not
commented-out code.

Every entry point in this package FIRST checks the Mode Gate and refuses to run
unless Adaptive Mode is active. In Conventional Mode (the default, and the
permanent floor) all adaptive behavior is dormant.

Conception components here (claude.md §13, §4.5, Workflow E):
  cass_engine              -> CASS = alpha*L + beta*S + gamma*D + delta*F,
                             persistence filter + Transmission Velocity Factor,
                             stress zones (Early / Recovery Activation / Severe
                             Pre-Resolution)
  absf                     -> Adaptive Burden-Sharing Framework: zone weights
                             across Tier D / Tier B-Fees / Tier C
  restoration_waterfall    -> Reverse Restoration Waterfall (post-stress
                             restoration, reverse order of absorption)

The CASS methodology weights/thresholds are PENDING (PENDING_CASS_FEED_SPEC /
PENDING_SI1_GATE_CRITERIA); the FRAMEWORK is fully structured and named, the
specific numbers stop loud.
"""

from .cass_engine import CassEngine, CASSZone, CassInput  # noqa: F401
from .absf import AbsfFramework  # noqa: F401
from .restoration_waterfall import RestorationWaterfall  # noqa: F401
