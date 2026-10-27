"""PENDING register - every open governance item as a named, visible stop.

Per `claude.md` §17 (and §18's "one rule to hold above all others"), every
PENDING item must appear in code as a named, visible stop - a stub, a config
flag, or a clearly-named exception - never as a guessed default. This module is
that register.

Each PENDING item is identified by a stable, traceable key. Consuming a value
that is still PENDING raises :class:`PendingNotResolvedError` with the key and
its governance meaning in the message. Nothing in this codebase silently
defaults or guesses any of these numbers or formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PendingItem:
    """A single named, open governance item that a build must stop at."""

    key: str
    """Stable machine-readable key (used as exception message marker)."""

    description: str
    """Human-readable description carried on every raised stop."""

    owning_register: str = "PENDING"
    """Register line name (claude.md §17 / source Spec register)."""

    # (optional) Phase/boundary context, e.g. "before first origination".
    note: str = ""


_ALL_PENDING: dict[str, PendingItem] = {}


def _register(
    key: str, description: str, register: str = "PENDING", note: str = ""
) -> PendingItem:
    item = PendingItem(
        key=key, description=description, owning_register=register, note=note
    )
    _ALL_PENDING[key] = item
    return item


# --- PENDING register (mirrors claude.md §17; do-not-resolve-in-code) --------
PENDING_CASS_FEED_SPEC = _register(
    "PENDING_CASS_FEED_SPEC",
    "Full P2+P4 CASS data feed interface specification (methodology). "
    "The single hinge blocking all of Stage 2.",
    note="gates Stage 2 / Adaptive Mode (SI-1 Gate G1). CIS-1 is a frozen "
    "10-field contract SHAPE only; it does not satisfy this.",
)
PENDING_STAGING_SIGNAL_FORMAT = _register(
    "PENDING_STAGING_SIGNAL_FORMAT",
    "IFRS 9 staging signal wire format (P2 -> P4 direct feed, bypassing P3).",
    note="blocks the staging-feed wire build (Part I §3.1). Distinct, co-timed "
    "feed from the CASS feed; not carried on CIS-1.",
)
PENDING_LEDGER_MECHANICS = _register(
    "PENDING_LEDGER_MECHANICS",
    "Buffer + guarantee-pool detailed ledger mechanics, reconciliation rules, "
    "and event formats (Pillar 4 canon).",
    note="blocks §1-§3 and §7 of Part II and the reconciliation tolerance; "
    "PENDING before sandbox go-live.",
)
PENDING_CONCENTRATION_LIMITS = _register(
    "PENDING_CONCENTRATION_LIMITS",
    "Concentration limit percentages (all dimensions: borrower, sector, "
    "guarantee pool, funding source).",
    note="interim operational limits set before first origination; formalised "
    "before Phase 2.",
)
PENDING_LIQUIDITY_MINIMUM = _register(
    "PENDING_LIQUIDITY_MINIMUM",
    "Liquidity Reserve minimum threshold number.",
    note="LR sizing category schema is built; the number is PENDING "
    "(Pillar 4 governance, Orchestrator-approved).",
)
PENDING_PLEDGE_TERM = _register(
    "PENDING_PLEDGE_TERM",
    "Pledge-term structure: notice-period length and pre-term "
    "exception/penalty parameters.",
    note="blocks §6.2-§6.3 of Part II; before first pledge intake.",
)
PENDING_IFRS10_IFRS9 = _register(
    "PENDING_IFRS10_IFRS9",
    "IFRS 10 SPV consolidation determination and IFRS 9 given-guarantee "
    "liability measurement (P4 + Legal + Auditor).",
    note="governs balance-sheet treatment of the pool and the given-guarantee "
    "liability; before sandbox.",
)
PENDING_ESCROW_SPV = _register(
    "PENDING_ESCROW_SPV",
    "Escrow vs SPV custody framework by asset class (P4 + Legal).",
    note="before pledge intake; blocks §5.4 inflow and custodial mechanics of "
    "release.",
)
PENDING_THREE_TRACK_HAIRCUT = _register(
    "PENDING_THREE_TRACK_HAIRCUT",
    "Three-track collateral haircut governance (final percentages, per-country "
    "track availability) [P-9].",
    note="Track 2/3 only; Stage 1 is Track 1 (Classical) and is not blocked "
    "by this.",
)
PENDING_MODEL_MATURITY_CRITERIA = _register(
    "PENDING_MODEL_MATURITY_CRITERIA",
    "Model Maturity Stage graduation criteria (quantitative thresholds) [P-5].",
    note="P2 + P4 + Governance Committee; per stage transition.",
)
PENDING_BAIL_IN_PLAYBOOK = _register(
    "PENDING_BAIL_IN_PLAYBOOK",
    "Bail-in playbook (professional-capital-only; P4 + Legal).",
    note="Phase 2 prerequisite; bail-in is framework-only / no operative "
    "trigger in sandbox.",
)
PENDING_TWO_GUARANTEE_LAYER_CONTRACT = _register(
    "PENDING_TWO_GUARANTEE_LAYER_CONTRACT",
    "Two-guarantee-layer data-field contract (P2/P3/P4) - including transport "
    "of the required pooled-guarantee level (R_pool).",
    note="conceptual interface is CLOSED (Orchestrator §6.2 rule); only the "
    "data-field contract remains open. RDG transport is blocked by this.",
)
PENDING_SI1_GATE_CRITERIA = _register(
    "PENDING_SI1_GATE_CRITERIA",
    "SI-1 gate criteria calibration (actual pass/fail numbers behind Gates "
    "G0-G3).",
    note="governance instrument SI-1; not a build concern to resolve.",
)


class PendingNotResolvedError(Exception):
    """Raised when a build consumes a not-yet-resolved PENDING item.

    Consistent with the "do-not-resolve-in-code" discipline: a valid business
    operation may reach a PENDING boundary and must fail loud and named, never
    silently guess.
    """

    def __init__(self, item: PendingItem):
        self.item = item
        super().__init__(
            f"[{item.owning_register}] PENDING item not resolved in code: "
            f"{item.key} - {item.description}"
            + (f" [note: {item.note}]" if item.note else "")
        )


def require_resolved(item: PendingItem):
    """Raise :class:`PendingNotResolvedError` for a PENDING item.

    A registered PENDING item is by definition unresolved; this is the helper
    that surfaces the stop at the point of consumption. (A resolved item would
    be removed from the register and have a concrete value in config.)
    """
    if item.key in _ALL_PENDING:
        raise PendingNotResolvedError(item)


def list_pending() -> list[PendingItem]:
    """Return all registered PENDING items (for reporting/tracing)."""
    return list(_ALL_PENDING.values())


def pending_keys() -> set[str]:
    return set(_ALL_PENDING.keys())


# Convenience reference for the most commonly hit boundaries.
REGISTER: dict[str, PendingItem] = _ALL_PENDING
