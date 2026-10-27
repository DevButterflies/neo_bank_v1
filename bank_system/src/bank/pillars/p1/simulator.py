"""P1 payment simulation — one-month-per-tick lifecycle driver.

Processes every disburseable candidate whose status is in
``TICKABLE_STATUSES``, applying the deterministic behaviour profile to move
the loan through repayment / delinquency / default / recovery / close.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from bank.orchestrator.config import settings as _orch_settings
from bank.pillars.api.storage import KvStore

from bank.pillars.p1.flow import (
    dict_to_packet,
    packet_to_dict,
    _sim_defaults,
    _recovery_packet,
    _p3_run,
)
from bank.pillars.p1.mirror import mirror_close, mirror_default, mirror_recovery, mirror_repayment, mirror_staging_signal
from bank.pillars.p1.service import service
from bank.pillars.p3.domain.enums import LoanState
from bank.pillars.p3.errors import InvalidStateTransitionError

TICKABLE_STATUSES: frozenset[str] = frozenset({"disbursed", "delinquent", "defaulted"})

AUTO_TICK_SECONDS: float = float(os.environ.get("BANK_SIMULATION_TICK_SECONDS", "0"))

# The global sim clock is durable: it lives in the shared KvStore (key
# ``p1_sim_state_v1``) next to the P3/P4 snapshots, so a restart resumes the
# same month instead of resetting to zero, and a factory reset writes ``0``.
_SIM_STATE_KEY = "p1_sim_state_v1"
_sim_store = KvStore(_orch_settings.db_path)


async def _load_sim_month() -> int:
    raw = await _sim_store.get_json(_SIM_STATE_KEY)
    if isinstance(raw, dict):
        return int(raw.get("current_month", 0) or 0)
    return 0


async def _save_sim_month(month: int) -> None:
    await _sim_store.set_json(
        _SIM_STATE_KEY,
        {"current_month": month, "updated_at": _utcnow().isoformat()},
    )


async def load_sim_month() -> int:
    """Current global sim month (persisted; resumed across restarts)."""
    return await _load_sim_month()


async def reset_sim_month() -> None:
    """Factory reset of the global sim clock."""
    await _save_sim_month(0)

# ---- helpers ----------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _paid_principal(payments_made: list[dict]) -> float:
    """Principal actually posted so far. Deliberately *not* clamped: the raw
    figure is what the overpayment check compares against ``disbursed``."""
    return round(sum(p["principal"] for p in payments_made), 2)


def _outstanding(disbursed: float, payments_made: list[dict]) -> float:
    return round(max(0.0, disbursed - _paid_principal(payments_made)), 2)


async def _p3_transition_or_accept(
    step, facility_id: str, expected_state: LoanState
) -> None:
    """Run a P3 lifecycle step, accepting the outcome as already applied when
    the facility is already in ``expected_state``.

    The sim commits its P3/P4 side effects before persisting its own state, so a
    failure midway leaves the model ahead of the sim. Retrying such a step
    blindly would raise ``InvalidStateTransitionError`` forever (e.g. re-marking
    an already-DEFAULT facility); this helper turns the already-committed outcome
    into an idempotent no-op of its own step and lets the sim resume.
    """
    try:
        await _p3_run(step)
    except InvalidStateTransitionError:
        fac = await _p3_run(lambda o: o.get_facility(facility_id))
        if fac is None or fac.state != expected_state:
            raise


def _build_status_counts(statuses: list[str]) -> dict[str, int]:
    from collections import Counter
    return dict(Counter(statuses))


# ---- per-candidate tick ------------------------------------------------------


async def tick_candidate(cand, month: int) -> dict:
    """Advance *cand* by one simulated month."""
    behavior = service.hydrate_behavior(cand)
    sim = dict(cand.sim_state or {})

    f_id = cand.facility_id
    base: dict = {"candidate_id": cand.id, "facility_id": f_id, "month": month}

    # --- already closed / defaulted without recovery left ---
    if sim.get("closed"):
        return {**base, "action": "noop", "reason": "closed"}

    packet_dict = sim.get("p3_packet")
    if packet_dict is None:
        return {**base, "action": "noop", "reason": "no_packet"}

    packet = dict_to_packet(packet_dict)

    # --- sim clock: elapsed is measured from the month the facility funded ----
    if sim.get("disbursed_at_month") is None:
        # Older sim states predate disbursal-month tracking. Re-base so elapsed
        # starts at 1 on the first tick after funding instead of jumping to the
        # bank-wide month (which would skip every scheduled repayment).
        sim["disbursed_at_month"] = max(0, month - 1)
    disbursed_at_month = int(sim.get("disbursed_at_month", 0) or 0)
    elapsed = max(0, month - disbursed_at_month)

    # --- default booking: a single window, retried until every leg commits --
    # The month is a *floor* (>=), not a one-shot equality: if a tick fails part
    # way through (P3 committed, P4 mirror or sim state not yet persisted), the
    # next month retries instead of silently skipping the default forever.
    if (
        behavior.default_month is not None
        and elapsed >= behavior.default_month
        and not sim.get("defaulted")
    ):
        steps: list[str] = []

        # Prerequisite: the delinquency must be on record in P3 so the default
        # transition is valid (DELINQUENT -> DEFAULT).
        if (
            behavior.delinquent_month is not None
            and elapsed >= behavior.delinquent_month
            and not sim.get("delinquent")
        ):
            await _p3_transition_or_accept(
                lambda o: o.mark_delinquent(f_id, packet),
                f_id,
                LoanState.DELINQUENT,
            )
            await mirror_staging_signal(f_id, 2, cand.application_id)
            sim["delinquent"] = True
            steps.append("delinquent")

        # What is still owed is computed once and handed to both sides: P3
        # writes it off as a real posting, P4 mirrors it as the loss (B2).
        loss = _outstanding(behavior.disbursed, sim.get("payments_made", []))

        if not sim.get("default_marked_p3"):
            await _p3_transition_or_accept(
                lambda o: o.mark_default(f_id, packet, loss, behavior.currency),
                f_id,
                LoanState.DEFAULT,
            )
            sim["default_marked_p3"] = True
            steps.append("default_marked_p3")

        if not sim.get("default_mirrored_p4"):
            await mirror_default(f_id, loss)
            sim["default_mirrored_p4"] = True
            sim["default_loss"] = loss
            steps.append("default_mirrored_p4")

        if not sim.get("default_staged"):
            await mirror_staging_signal(f_id, 3, cand.application_id)
            sim["default_staged"] = True
            steps.append("default_staged")

        sim["defaulted"] = True
        sim["default_month"] = elapsed
        sim["current_month"] = elapsed
        await service.update_status(cand.id, "defaulted", defaulted_at=_utcnow())
        await service.set_sim_state(cand.id, sim)
        return {**base, "action": "defaulted", "steps": steps}

    # --- recovery + close: retried until the P4 exposure is actually released -
    if sim.get("defaulted") and not sim.get("recovery_done"):
        recovery_amount = float(
            sim.get("recovery_amount")
            or behavior.recovered_amount
            or round(
                _outstanding(behavior.disbursed, sim.get("payments_made", []))
                * 0.50,
                2,
            )
        )
        recovery_pkt = _recovery_packet(packet_dict)

        if not sim.get("recovery_started"):
            await _p3_transition_or_accept(
                lambda o: o.initiate_recovery(
                    f_id, recovery_pkt, recovery_amount, behavior.currency
                ),
                f_id,
                LoanState.RECOVERY,
            )
            sim["recovery_started"] = True
            sim["recovery_amount"] = recovery_amount

        if not sim.get("recovery_mirrored"):
            await mirror_recovery(f_id, recovery_amount)
            sim["recovery_mirrored"] = True

        if not sim.get("close_marked"):
            await _p3_transition_or_accept(
                lambda o: o.close(f_id, recovery_pkt), f_id, LoanState.CLOSED
            )
            sim["close_marked"] = True

        if not sim.get("recovery_done"):
            await mirror_close(f_id)
            sim["recovery_done"] = True
            sim["closed"] = True
            sim["recoveries"] = sim.get("recoveries", []) + [
                {"month": elapsed, "amount": recovery_amount}
            ]

        sim["current_month"] = elapsed
        await service.update_status(cand.id, "closed", closed_at=_utcnow())
        await service.set_sim_state(cand.id, sim)
        return {**base, "action": "recovered_closed", "recovered": recovery_amount}

    # --- check if a repayment is due this month ---
    due = next((r for r in behavior.repayments if r.month == elapsed), None)

    if due is not None:
        interest = due.interest
        payments = sim.get("payments_made", [])
        # A schedule can carry a final instalment larger than what is still
        # owed (docs/CHANGELOG_bilan.md, B5). P3 rejects any repayment that would
        # drive the outstanding balance below zero, so clamp first; when
        # nothing is left the payment is skipped entirely and the loan just
        # closes on the check below.
        outstanding = _outstanding(behavior.disbursed, payments)

        if outstanding > 0.0:
            principal = round(min(due.principal, outstanding), 2)
            await _p3_run(
                lambda o: o.record_repayment(
                    f_id, packet, interest, principal, behavior.currency
                )
            )
            await mirror_repayment(f_id, principal, interest)
            payments = payments + [
                {"month": elapsed, "interest": interest, "principal": principal}
            ]
            sim["payments_made"] = payments
            sim["current_month"] = elapsed

            # cured after delinquency
            if sim.get("delinquent"):
                sim["delinquent"] = False
                await service.update_status(cand.id, "disbursed")

        # close when fully repaid
        if _outstanding(behavior.disbursed, payments) <= 0.001:
            await _p3_run(lambda o: o.close(f_id, packet))
            await mirror_close(f_id)
            sim["closed"] = True
            await service.update_status(cand.id, "closed", closed_at=_utcnow())
            await service.set_sim_state(cand.id, sim)
            return {**base, "action": "repayment_closed", "payments": payments}

        await service.set_sim_state(cand.id, sim)
        return {**base, "action": "repayment", "payments": payments}

    # --- no repayment due this month — delinquency check (one-shot window) ---
    actions: list[str] = []
    if (
        behavior.delinquent_month is not None
        and elapsed == behavior.delinquent_month
        and not sim.get("defaulted")
        and not sim.get("delinquent")
    ):
        await _p3_run(lambda o: o.mark_delinquent(f_id, packet))
        await mirror_staging_signal(f_id, 2, cand.application_id)
        sim["delinquent"] = True
        await service.update_status(cand.id, "delinquent")
        actions.append("delinquent")

    # The default booking itself lives in the retrying terminal pipeline above,
    # so a failed default can never slip past an already-passed month window.

    if not actions:
        sim["current_month"] = elapsed
        await service.set_sim_state(cand.id, sim)
        return {**base, "action": "noop"}

    await service.set_sim_state(cand.id, sim)
    return {**base, "action": actions}


# ---- top-level tick ----------------------------------------------------------


async def tick() -> dict:
    """Advance every active candidate by one simulated month."""
    month = await _load_sim_month() + 1
    await _save_sim_month(month)
    all_candidates = []
    statuses_seen: list[str] = []

    for status in TICKABLE_STATUSES:
        page = await service.list(status=status)
        for c in page:
            all_candidates.append(c)
            statuses_seen.append(c.status)

    events = []
    for cand in all_candidates:
        ev = await tick_candidate(cand, month)
        events.append(ev)

    return {
        "month": month,
        "candidates_processed": len(events),
        "events": events,
    }


# ---- background auto-tick ----------------------------------------------------


async def _auto_tick_loop() -> None:
    """Runs until cancelled; sleeps ``AUTO_TICK_SECONDS`` between ticks."""
    while True:
        await asyncio.sleep(AUTO_TICK_SECONDS)
        try:
            await tick()
        except Exception:
            pass  # best-effort; never crash the background task


_auto_task: asyncio.Task | None = None


def start_auto_tick() -> None:
    global _auto_task
    if AUTO_TICK_SECONDS <= 0:
        return
    loop = asyncio.get_event_loop()
    _auto_task = loop.create_task(_auto_tick_loop())


def stop_auto_tick() -> None:
    global _auto_task
    if _auto_task is not None:
        _auto_task.cancel()
        _auto_task = None
