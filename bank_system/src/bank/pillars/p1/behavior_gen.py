"""Deterministic payment-behaviour generation for P1 candidates.

When a candidate is created without an explicit
:class:`~bank.pillars.p1.schemas.PaymentBehavior`, one is auto-generated from
a seeded PRNG keyed by ``candidate_id``, so the same candidate always produces
the same behaviour across restarts (stable for demos):

  - 60% paid            — every instalment made, facility closes at maturity
  - 25% default         — pays for a few months, turns delinquent, then
                          defaults; a partial recovery is realized
  - 15% delinquent-cured — misses one instalment (delinquent), then resumes
                          and repays in full

Generated schedules use equal-principal amortization at a deterministic
monthly rate so the interest component shrinks month-over-month exactly like
the hand-written demo_3 repayment tables.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from bank.pillars.p1.schemas import PaymentBehavior


def generate_behavior(
    candidate_id: str,
    *,
    requested_amount: float,
    requested_tenure_months: int,
    outcome: str | None = None,
    seed_override: int | None = None,
) -> PaymentBehavior:
    """Build a deterministic :class:`PaymentBehavior` for a candidate.

    ``seed_override`` pins the PRNG for tests; by default the seed is derived
    from ``candidate_id`` so behaviour is stable per candidate forever.
    """
    seed = seed_override if seed_override is not None else _seed_for(candidate_id)
    rng = random.Random(seed)

    if outcome is None:
        roll = rng.random()
        outcome = (
            "paid" if roll < 0.60
            else "default" if roll < 0.85
            else "delinquent_cured"
        )

    tenure = requested_tenure_months or 12
    disbursed = round(requested_amount * rng.uniform(0.80, 1.0), 2)
    rate_bps = rng.randint(800, 1500)  # 8%–15% APR as in demo_3's figures
    monthly_rate = (rate_bps / 10_000) / 12

    base_principal = disbursed / tenure
    repayments: list[dict[str, Any]] = []
    outstanding = disbursed

    for m in range(1, tenure + 1):
        interest = round(outstanding * monthly_rate, 2)
        principal = round(base_principal, 2)
        if m == tenure:
            principal = round(outstanding, 2)
        repayments.append({"interest": interest, "principal": principal, "month": m})
        outstanding = round(outstanding - principal, 2)

    behavior = PaymentBehavior(
        outcome=outcome,
        facility_amount=requested_amount,
        disbursed=disbursed,
        currency="USD",
        tenure_months=tenure,
        repayments=repayments,
        interest_rate_bps=rate_bps,
    )

    if outcome == "default":
        # Miss an instalment -> delinquent, then default the following month.
        behavior.delinquent_month = max(2, tenure // 3)
        behavior.default_month = behavior.delinquent_month + 1
        # Only instalments before the miss are actually paid.
        behavior.repayments = [
            r for r in behavior.repayments if r.month < behavior.delinquent_month
        ]
        # Partial recovery after default (roughly 30–60% of outstanding).
        behavior.recovered_amount = round(disbursed * rng.uniform(0.30, 0.60), 2)
    elif outcome == "delinquent_cured":
        behavior.delinquent_month = max(2, min(4, tenure // 3))
        # The missed instalment is dropped; later instalments resume and cure.
        behavior.repayments = [
            r for r in behavior.repayments if r.month != behavior.delinquent_month
        ]

    return behavior


def _seed_for(candidate_id: str) -> int:
    # Stable across processes/restarts (unlike built-in hash() which is
    # randomized per interpreter run).
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)