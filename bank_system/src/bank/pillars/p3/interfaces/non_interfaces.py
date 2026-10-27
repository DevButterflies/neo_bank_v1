"""
Explicit non-interfaces — Interface Contract Sheet §3:

    "P3 <-> P4 CASS / IFRS 9 — None (by design). CASS feed and IFRS 9
    staging are P2->P4 direct and bypass P3. P3 must not infer, replicate,
    or emit them. P3 records contractual breaches only."

Most absent interfaces are absent simply because nobody wrote the code.
These two are absent *on purpose*, and a future engineer might reasonably
try to add them (e.g. "let's have P3 forward the staging signal since it
already sees the contractual breach event"). This module exists so that
attempt fails loudly and points at the rule, instead of silently
becoming a real integration.
"""
from __future__ import annotations

from bank.pillars.p3.errors import GovernanceBoundaryError


def emit_cass_feed(*_args, **_kwargs):
    raise GovernanceBoundaryError(
        "The CASS data feed interface is P2->P4 direct and bypasses "
        "Pillar 3 by design (Interface Contract Sheet §3). P3 must not "
        "infer, replicate, or emit it."
    )


def emit_ifrs9_staging_signal(*_args, **_kwargs):
    raise GovernanceBoundaryError(
        "IFRS 9 staging signal (PIT-adjusted) is P2->P4 direct and "
        "bypasses Pillar 3 by design (Interface Contract Sheet §3). P3 "
        "records contractual breaches only, never a staging signal."
    )
