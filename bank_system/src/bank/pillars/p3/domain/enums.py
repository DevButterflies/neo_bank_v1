"""
Canonical enumerations for Pillar 3.

Every value here traces to a named document/section so that a reviewer can
grep this file and find the clause it implements. Do not add values that
aren't backed by the governing documents (Canon V1.2, Spec V5.2, Build
Handoff v1.0) — P3 has no authority to invent new lifecycle states,
posting types, or tracks on its own (Canon §11, Change Control).
"""
from __future__ import annotations

from enum import Enum


class ModelFlag(str, Enum):
    """[S] vs [G] — Canon §7. G is operative; S is the ratified migration
    target, retained only so interfaces are migration-aware."""

    GUARANTEE = "G"        # operative
    STABLECOIN = "S"       # migration target, sandbox-dormant


class MaturityStage(str, Enum):
    """Model Maturity Stage gate — Spec §1, Build Handoff §5."""

    DESIGN = "DESIGN"
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"


class LoanState(str, Enum):
    """Loan lifecycle states — Spec §2 (state machine table)."""

    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    REPAYING = "REPAYING"
    DELINQUENT = "DELINQUENT"
    DEFAULT = "DEFAULT"
    RESTRUCTURING = "RESTRUCTURING"
    RECOVERY = "RECOVERY"
    CLOSED = "CLOSED"


class CollateralTrack(str, Enum):
    """Three-track collateral model — Spec §4."""

    TRACK_1_CLASSICAL = "TRACK_1_CLASSICAL"   # [S]&[G], always available
    TRACK_2_NFT = "TRACK_2_NFT"               # [S]/[G] branch
    TRACK_3_STABLECOIN = "TRACK_3_STABLECOIN"  # [S] only


class PostingEventType(str, Enum):
    """Per-loan posting set — Spec §3 / Build Handoff §4.

    This is the *complete* posting set. P3 must not post anything outside
    this enum, and must not compute cross-tier allocation for any of them
    — see governance.allocation_guard for the structural block on that.
    """

    LOAN_INCOME = "LOAN_INCOME"                       # interest + principal income
    RISK_PREMIUM_FEE = "RISK_PREMIUM_FEE"
    PRINCIPAL_MOVEMENT = "PRINCIPAL_MOVEMENT"         # drawdown/repay/write-off
    LOSS_RECOVERY = "LOSS_RECOVERY"                   # default/write-off/recovery
    ORIGINATION_FEE = "ORIGINATION_FEE"               # P&L, not a buffer
    COVENANT_BREACH = "COVENANT_BREACH"               # control event, not income
    GUARANTEE_EVENT = "GUARANTEE_EVENT"               # [G] given/received guarantee


# Which posting events must route a portfolio-level allocation question to
# P4, per Build Handoff §4 ("Routes allocation Q to P4?" column).
ALLOCATION_ROUTED_EVENTS = frozenset(
    {
        PostingEventType.LOAN_INCOME,
        PostingEventType.RISK_PREMIUM_FEE,
        PostingEventType.LOSS_RECOVERY,
    }
)

# Events that are purely micro / no allocation question at all.
MICRO_ONLY_EVENTS = frozenset(
    {
        PostingEventType.PRINCIPAL_MOVEMENT,
        PostingEventType.ORIGINATION_FEE,
        PostingEventType.COVENANT_BREACH,
    }
)


class VetoScope(str, Enum):
    """P4 veto scope — Interface Contract Sheet §3."""

    TRACK_1_PORTFOLIO = "TRACK_1_PORTFOLIO"
    TRACK_2_FACILITY = "TRACK_2_FACILITY"


class P2PacketStatus(str, Enum):
    """Pillar 2 output packet status — Canon §8.1."""

    APPROVED = "APPROVED"
    PROVISIONAL = "PROVISIONAL"
    CONDITIONAL = "CONDITIONAL"
