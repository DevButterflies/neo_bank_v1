"""
Strict PENDING register — Canon §10, Spec §11, Build Handoff §6.2.

These five items are open at registers OUTSIDE Pillar 3 (merged Canon
register, P2 Canon §4, P4 Canon register, Orchestrator+P2 Canon §4).
Pillar 3 build "must not silently resolve any of them; resolution
returns to the owning register" (Spec §11).

The enforcement mechanism here is deliberate: each PENDING item exposes
only a `stub(...)` method that records that P3 hit the boundary and
raises. There is no method that returns a real value, because writing
one would BE the governance breach the documents warn against
("A PENDING gap filled by an engineering assumption is a governance
breach, not a shortcut." — Build Handoff §6.2).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bank.pillars.p3.errors import PendingGovernanceItemError


class PendingItem(str, Enum):
    TWO_GUARANTEE_LAYER_INTERFACE = "TWO_GUARANTEE_LAYER_INTERFACE"       # [G]; merged-Canon reg; P2 Canon §4
    THREE_TRACK_HAIRCUT_GOVERNANCE = "THREE_TRACK_HAIRCUT_GOVERNANCE"      # [P-9]; merged Orchestrator reg; P2 Canon §4
    P4_BUFFER_GUARANTEE_POOL_LEDGER = "P4_BUFFER_GUARANTEE_POOL_LEDGER"    # P4 Canon register
    CASS_DATA_FEED_INTERFACE = "CASS_DATA_FEED_INTERFACE"                  # Orchestrator + P2 Canon §4
    IFRS9_STAGING_SIGNAL_FORMAT = "IFRS9_STAGING_SIGNAL_FORMAT"            # P2 Canon §4


@dataclass(frozen=True)
class PendingItemInfo:
    item: PendingItem
    owning_register: str
    blocks_in_p3: str


PENDING_REGISTER = {
    PendingItem.TWO_GUARANTEE_LAYER_INTERFACE: PendingItemInfo(
        item=PendingItem.TWO_GUARANTEE_LAYER_INTERFACE,
        owning_register="merged-Canon register; P2 Canon §4",
        blocks_in_p3=(
            "Recording interface for MSME-pledged collateral vs neo-bank "
            "pooled guarantee; pooled-guarantee-level consumption."
        ),
    ),
    PendingItem.THREE_TRACK_HAIRCUT_GOVERNANCE: PendingItemInfo(
        item=PendingItem.THREE_TRACK_HAIRCUT_GOVERNANCE,
        owning_register="merged Orchestrator register; P2 Canon §4",
        blocks_in_p3="Track 2 / Track 3 collateral recording & realization go-live per market.",
    ),
    PendingItem.P4_BUFFER_GUARANTEE_POOL_LEDGER: PendingItemInfo(
        item=PendingItem.P4_BUFFER_GUARANTEE_POOL_LEDGER,
        owning_register="P4 Canon register",
        blocks_in_p3="Event-routing target sub-accounts; fee/income/loss audit-trail granularity.",
    ),
    PendingItem.CASS_DATA_FEED_INTERFACE: PendingItemInfo(
        item=PendingItem.CASS_DATA_FEED_INTERFACE,
        owning_register="Orchestrator + P2 Canon §4",
        blocks_in_p3="Not a P3 event (P2->P4 direct); P3 must not infer or replicate it.",
    ),
    PendingItem.IFRS9_STAGING_SIGNAL_FORMAT: PendingItemInfo(
        item=PendingItem.IFRS9_STAGING_SIGNAL_FORMAT,
        owning_register="P2 Canon §4",
        blocks_in_p3="P2->P4 direct, bypasses P3; P3 records contractual breaches only.",
    ),
}


def stub(item: PendingItem) -> None:
    """Call this at any seam where a PENDING item would otherwise need to
    be resolved. It always raises — there is intentionally no code path
    that lets a caller obtain a real value for a PENDING item from
    Pillar 3. Catch PendingGovernanceItemError at the boundary and route
    the blocker to Project 1 / the owning register; do not work around
    this function.
    """
    info = PENDING_REGISTER[item]
    raise PendingGovernanceItemError(
        f"'{item.value}' is strict PENDING at {info.owning_register}. "
        f"Blocks in P3: {info.blocks_in_p3}. do-not-resolve-in-code — "
        f"route to the owning register."
    )


def is_registered(item: PendingItem) -> bool:
    return item in PENDING_REGISTER
