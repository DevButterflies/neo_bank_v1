"""Integration layer - Pillar 4 orchestration and cross-pillar adapters.

Composes the Part I and Part II services into the Pillar 4 whole and wires the
Part I <-> Part II relationships (claude.md §6) and the cross-pillar
communication (claude.md §9).

The Part I <-> Part II relationships wired here:
  Part II -> Part I : sub-account balances feed the capital/leverage calc and
                      the Track-1 liquidity/concentration triggers (§6).
  Part II -> Part I : pool-adequacy shortfall CAN itself invoke the Part I veto
                      engine when it coincides with a G/G ratio breach (§6).
  Part I  -> Part II: veto state gates the pool-adequacy management.

The critical hard boundary is respected structurally: there is NO per-loan
interface between Pillar 4 and Pillar 3. The only cross-pillar path to Pillar 3
is via Pillar 2's confirmed/withheld output packet (resolution-at-P2).
"""

from .pillar4 import Pillar4  # noqa: F401
from .adapters import (  # noqa: F401
    Pillar2Port,
    Pillar3Port,
    Pillar5Port,
    OrchestratorPartner,
)
