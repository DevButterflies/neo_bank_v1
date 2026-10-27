"""
Allocation guard — Canon §4 standing rule:

    "Pillar 3 shall not contain, compute, or encode any cross-tier
    allocation, burden-sharing, Tier B-Fees, ABSF, or loss-repartition
    logic. These are exclusively Pillar 4. Pillar 3 produces the per-loan
    event and the routing signal; the repartition is computed and owned
    by Pillar 4. This rule is structural and may not be varied by
    operational parameter or country tuning."

There is no function in this module that computes an allocation. That is
the point: the only thing offered is `assert_allocation_untouched`, used
by the integrity test suite to prove the posting/routing engine never
produces anything resembling a per-tier split. If a future change adds a
real allocation computation to this codebase, the integrity tests in
tests/integrity/ are designed to fail loudly.
"""
from __future__ import annotations

from typing import Any, Mapping

from bank.pillars.p3.errors import AllocationLogicForbiddenError

# Keys that, if they ever appeared on a PostingEvent/AuditRecord payload,
# would indicate P3 has started doing P4's job.
FORBIDDEN_ALLOCATION_KEYS = frozenset(
    {
        "tier_a_share",
        "tier_b_share",
        "tier_c_share",
        "tier_d_share",
        "tier_allocation",
        "burden_share",
        "absf_amount",
        "loss_repartition",
        "tier_b_fees_allocation",
    }
)


def assert_allocation_untouched(payload: Mapping[str, Any]) -> None:
    """Raise if a payload (e.g. a dict about to be posted or logged)
    contains any key that represents a cross-tier allocation computation.
    """
    present = FORBIDDEN_ALLOCATION_KEYS.intersection(payload.keys())
    if present:
        raise AllocationLogicForbiddenError(
            f"Payload contains forbidden allocation keys: {sorted(present)}. "
            "Cross-tier allocation is exclusively Pillar 4 (Canon §4)."
        )
