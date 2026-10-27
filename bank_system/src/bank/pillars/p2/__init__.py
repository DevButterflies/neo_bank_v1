"""
Pillar 2 — AI/ML Credit Scoring & Risk Rating Engine
=====================================================
Reference implementation conforming to:
  - Pillar 2 Canon V4.1 (ratified OA-2.0 amendments P-1..P-9)
  - Pillar 2 Scoring & Rating Model Spec v1.0 (Sandbox Design Build)
  - Pillar 2 Data Requirements Matrix v1.0
  - Pillar 2 Credit Due-Diligence Template v1.0

Model Maturity Stage: DESIGN. Every numeric threshold that the source
documents mark as a DESIGN-stage placeholder, a tunable prior, or a
PENDING governance item is isolated in `pillar2.constants` and is loud
about it there — nothing is silently hardcoded deep in the logic.
"""

from .engine import Pillar2Engine
from .schemas import BorrowerApplication, ScoringResult

__all__ = ["Pillar2Engine", "BorrowerApplication", "ScoringResult"]
__version__ = "1.0.0"
