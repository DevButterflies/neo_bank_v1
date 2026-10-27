"""Tests for the demo safety net: config-gated auto-lift of a standing Track-1
freeze after N CONSECUTIVE clean recomputes.

Behavior contract:
  - default (auto_lift_on_sustained_clean=0) = governance-only: a standing
    freeze is NEVER lifted by a clean book, matching test_prudential_veto_flow.
  - with N>0, a frozen book that reads clean for N consecutive authoritative
    recomputes is auto-lifted via the SAME path as review_and_lift_track1
    (traceable governance_ref "AUTO-LIFT-SUSTAINED-CLEAN").
  - a breach resets the clean-run counter: the lift NEVER fires while the live
    book is still over budget, and one transient clean read alone never lifts.
"""

from __future__ import annotations

import pytest

from bank.pillars.p4.contracts.p2_inbound import Pillar2RiskPacket
from bank.pillars.p4.domain.veto import TriggerType
from bank.pillars.p4.integration.pillar4 import Pillar4


def _packet(
    facility_ref: str,
    *,
    brr: float = 3,
    pd: float = 0.01,
    lgd: float = 0.5,
    ead: float = 1000.0,
) -> Pillar2RiskPacket:
    return Pillar2RiskPacket(
        facility_ref=facility_ref,
        brr=brr,
        pd=pd,
        lgd=lgd,
        ead=ead,
        el=round(pd * lgd * ead, 2),
        product_type="TERM_LOAN",
    )


def _overbudget(ref: str) -> Pillar2RiskPacket:
    # EL ratio = 450 / 12000 = 3.75% — over the 2% budgeted-loss bound.
    return _packet(ref, brr=6, pd=0.05, lgd=0.75, ead=12000.0)


def _engine(auto_lift: int = 0) -> Pillar4:
    p4 = Pillar4(
        in_memory_ports=True, auto_lift_on_sustained_clean=auto_lift
    )
    p4.capital.set_tier_d_amount(100_000.0)
    return p4


def _release_exposure(p4: Pillar4, ref: str) -> None:
    """Withdraw the offending exposure (mirror_close body) WITHOUT recomputing,
    so tests control exactly how many clean recomputes accumulate."""
    p4.capital.release_risk_packet(ref)
    p4.ifrs9.release(ref)


def test_default_config_never_auto_lifts():
    p4 = _engine(auto_lift=0)
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    _release_exposure(p4, "FAC-BAD")
    p4.recompute_and_evaluate_track1()
    p4.recompute_and_evaluate_track1()

    assert p4.veto_engine.state.track1.is_frozen() is True
    assert p4.veto_engine.state.track1.breached_triggers
    assert "AUTO-LIFT-SUSTAINED-CLEAN" not in [
        n.get("governance_ref") for n in p4.veto_engine.notifier.notifications
    ]


def test_auto_lift_fires_after_two_consecutive_clean_recomputes():
    p4 = _engine(auto_lift=2)
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    _release_exposure(p4, "FAC-BAD")

    # Recompute #1 (clean read #1): frozen still holds (a single clean read
    # must not lift — match the governance-only test invariant).
    first = p4.recompute_and_evaluate_track1()
    assert first["auto_lifted"] is False
    assert p4.veto_engine.state.track1.is_frozen() is True

    # Recompute #2 (clean read #2): the standing freeze auto-lifts.
    second = p4.recompute_and_evaluate_track1()
    assert second["auto_lifted"] is True
    assert p4.veto_engine.state.track1.is_frozen() is False
    assert p4.veto_engine.state.track1.breached_triggers == {}

    lifts = [
        n
        for n in p4.veto_engine.notifier.notifications
        if n.get("event") == "veto_lift"
    ]
    assert lifts and lifts[-1]["governance_ref"] == "AUTO-LIFT-SUSTAINED-CLEAN"


def test_over_budget_book_never_auto_lifts():
    p4 = _engine(auto_lift=2)
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    for _ in range(3):
        result = p4.recompute_and_evaluate_track1()
        assert result["auto_lifted"] is False
        assert p4.veto_engine.state.track1.is_frozen() is True


def test_clean_run_resets_on_rebreach():
    p4 = _engine(auto_lift=2)
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    _release_exposure(p4, "FAC-BAD")
    assert p4.veto_engine.state.track1.is_frozen() is True

    # Clean read #1 accumulates, then a breach resets the run.
    p4.recompute_and_evaluate_track1()
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    _release_exposure(p4, "FAC-BAD")
    assert p4.recompute_and_evaluate_track1()["auto_lifted"] is False
    assert p4.recompute_and_evaluate_track1()["auto_lifted"] is True
    assert p4.veto_engine.state.track1.is_frozen() is False


def test_freeze_details_captured_and_cleared():
    p4 = _engine(auto_lift=0)
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    details = p4.veto_engine.state.track1.freeze_details
    assert TriggerType.PORTFOLIO_EL.value in details
    entry = details[TriggerType.PORTFOLIO_EL.value]
    assert entry["budgeted_loss_ratio"] == 0.02
    assert entry["portfolio_el"] == pytest.approx(450.0 / 12000.0)
    assert entry["ead_book"] == pytest.approx(12000.0)
    assert entry["el_book"] == pytest.approx(450.0)

    p4.veto_engine.review_and_lift_track1("GOV-001")
    assert p4.veto_engine.state.track1.freeze_details == {}


@pytest.mark.asyncio
async def test_freeze_details_survive_restart_round_trip(tmp_path):
    from bank.pillars.api.p4 import P4Runtime

    db = str(tmp_path / "p4_all.db")
    a = P4Runtime(db)
    await a.load()
    await a.run(lambda o: o.ports.p2.feed_risk_packet(_overbudget("FAC-BAD")))
    frozen_details = a._ensure_engine().veto_engine.state.track1.freeze_details
    assert TriggerType.PORTFOLIO_EL.value in frozen_details

    b = P4Runtime(db)
    await b.load()
    restored = b._ensure_engine().veto_engine.state.track1.freeze_details
    assert restored == frozen_details
    assert restored[TriggerType.PORTFOLIO_EL.value]["portfolio_el"] == pytest.approx(
        450.0 / 12000.0
    )