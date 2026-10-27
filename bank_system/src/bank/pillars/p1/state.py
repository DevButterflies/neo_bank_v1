"""P1 demo state snapshot — collected from candidates + P4 live read.

``build_demo_state`` is called by the SSE broker after every mutating
action and also served by ``GET /demo/state``.
"""
from __future__ import annotations

from bank.pillars.p1.service import service


async def _safe_p4_summary() -> dict:
    """Best-effort P4 snapshot; never lets a P4 error block the demo state."""
    try:
        from bank.pillars.p1.mirror import p4_runtime

        rt = p4_runtime()
        if not rt._loaded:
            await rt.load()
        p4 = rt._ensure_engine()
        balances = {k.value: v for k, v in p4.balances().items()}
        veto = p4.veto_engine.state.track1
        summary = {
            "balances": balances,
            "mode": p4.mode_gate.mode,
            "track1_status": veto.status.value,
            "event_log_count": len(p4._event_log),
        }
        # Read-only Track-1 evaluation: ratio, headroom and the breached /
        # unmonitored trigger lists for the veto banner. Never freezes (the
        # authority to freeze stays with recompute_and_evaluate_track1).
        read = p4.evaluate_track1_read_only()
        snap = read["snapshot"]
        summary["portfolio_el_ratio"] = snap.portfolio_el
        summary["budgeted_loss_ratio"] = p4.capital.budgeted_loss_ratio
        summary["tier_d_over_rwa"] = snap.tier_d_over_rwa
        summary["breached_triggers"] = list(read["breached_triggers"])
        summary["unmonitored_triggers"] = list(read["unmonitored_triggers"])
        summary["liquidity_pending"] = read["liquidity_pending"]
        # STANDING freeze reason: which triggers froze the book (possibly frozen
        # while the *live* read above is now clean). The banner must show why a
        # freeze is in force even when the live ratio sits under the 2% bound.
        summary["standing_breached_triggers"] = sorted(
            t.value for t in veto.breached_triggers
        )
        summary["frozen_since"] = (
            veto.frozen_since.isoformat() if veto.frozen_since else None
        )
        # The governing metric values captured when each trigger tripped the
        # freeze (traceability for the banner / governance review): which
        # numbers froze the book, e.g. portfolio_el vs budgeted_loss_ratio.
        summary["freeze_details"] = {
            t: dict(d) for t, d in veto.freeze_details.items()
        }
        return summary
    except Exception as exc:
        return {"error": str(exc)}


async def build_demo_state() -> dict:
    page = await service.list()
    candidates = []
    for c in page:
        behavior = service.hydrate_behavior(cand=c) if c.payment_behavior else None
        sim = c.sim_state or {}
        outstanding = None
        if behavior and c.status in ("disbursed", "delinquent", "defaulted"):
            paid = sum(p["principal"] for p in sim.get("payments_made", []))
            outstanding = round(max(0.0, behavior.disbursed - paid), 2)
        candidates.append(
            {
                "id": c.id,
                "display_name": c.display_name,
                "national_id": c.national_id,
                "monthly_salary": c.monthly_salary,
                "requested_amount": c.requested_amount,
                "requested_tenure_months": c.requested_tenure_months,
                "status": c.status,
                "facility_id": c.facility_id,
                "application_id": c.application_id,
                "p2_zone": c.p2_zone,
                "p2_brr": c.p2_brr,
                "p2_pd": c.p2_pd,
                "p2_lgd": c.p2_lgd,
                "p2_ead": c.p2_ead,
                "p2_el": c.p2_el,
                "outstanding": outstanding,
                "sim_month": sim.get("current_month", 0),
                "payments_made": len(sim.get("payments_made", [])),
                "defaulted": sim.get("defaulted", False),
                "closed": sim.get("closed", False),
                "recovered": sim.get("recovery_done", False),
            }
        )
    from bank.pillars.p1.simulator import load_sim_month
    return {
        "sim_month": await load_sim_month(),
        "candidates": candidates,
        "p4": await _safe_p4_summary(),
    }
