"""Bail-In Framework (inert reference data) (claude.md §8.5, §4.4).

Status: explicitly "no operative trigger in sandbox" - built as inert
configuration/documentation, not live logic, until Phase 2. The intended
loss-absorption SEQUENCE is pre-agreed and held as reference data; no operative
trigger is exposed.

Sequence (claude.md §4.4):
  EL up to Budgeted Loss (2%) covered by interest margins priced ex-ante.
  Losses beyond Budgeted Loss within a band absorbed by IFRS 9 provisions and
  Tier D equity, with ABSF progressive participation (weights Part III, Stage 2).
  As Tier D common equity approaches exhaustion: Perpetual AT1 absorbs;
  Tier B-Fees at max attenuation; Tier C AT2 begins absorption.
  Senior Institutional Debt - not bail-inable under any circumstance.
  Tier B principal - not bail-inable under ABSF.
  Tier A - fully protected throughout; insured.

Operative trigger thresholds, legal docs, notification procedures, CBO approval
are Phase 2 (PENDING_BAIL_IN_PLAYBOOK).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BailInInstrument(str, Enum):
    INTEREST_MARGIN = "interest_margin"
    IFRS9_PROVISIONS = "ifrs9_provisions"
    TIER_D_EQUITY = "tier_d_equity"
    PERPETUAL_AT1 = "perpetual_at1"
    TIER_B_FEES = "tier_b_fees"
    TIER_C_AT2 = "tier_c_at2"


@dataclass(frozen=True)
class BailInSequenceStep:
    order: int
    instrument: BailInInstrument
    description: str


@dataclass
class BailInFramework:
    """Holds the intended loss-absorption sequence as framework-level ordering.

    NO operative trigger in the sandbox phase. Iterate/docs only until Phase 2.
    """

    # The ordered sequence (reference data; Doc order, not live).
    sequence: list[BailInSequenceStep] = field(
        default_factory=lambda: [
            BailInSequenceStep(1, BailInInstrument.INTEREST_MARGIN,
                               "EL up to Budgeted Loss (2%) covered by interest "
                               "margins priced ex-ante"),
            BailInSequenceStep(2, BailInInstrument.IFRS9_PROVISIONS,
                               "Beyond Budgeted Loss within a band absorbed by "
                               "IFRS 9 provisions + Tier D equity; ABSF "
                               "progressive participation (weights = Part III, "
                               "Stage 2)"),
            BailInSequenceStep(3, BailInInstrument.PERPETUAL_AT1,
                               "As Tier D common equity approaches exhaustion, "
                               "Perpetual AT1 absorbs"),
            BailInSequenceStep(4, BailInInstrument.TIER_B_FEES,
                               "Tier B-Fees at maximum attenuation weight"),
            BailInSequenceStep(5, BailInInstrument.TIER_C_AT2,
                               "Tier C AT2 begins absorption per instrument terms"),
        ]
    )

    # Immutable exclusions (claude.md §4.4).
    senior_institutional_debt_bail_inable: bool = False  # NEVER
    tier_b_principal_bail_inable: bool = False  # never under ABSF
    tier_a_protected: bool = True  # fully protected throughout, insured

    operative_trigger_enabled: bool = False  # NO operative trigger in sandbox
