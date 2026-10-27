"""Regression tests for the standing-veto demo flow (freeze -> lift -> restart).

Covers the governance-release path whose absence made the demo soft-lock into
"every loan is frozen":
  - an over-budget booking trips a STANDING Track-1 freeze (portfolio EL)
  - a clean read never self-unfreezes (review #1: only governance may lift)
  - review_and_lift_track1 clears the freeze AND records the governance_ref
  - once the offending exposure is released, good loans proceed without a
    re-freeze
  - the demo state feed (_safe_p4_summary) exposes ratio / headroom / triggers
    read-only, with zero freeze side-effects
"""
from __future__ import annotations

import pytest

from bank.pillars.p1.state import _safe_p4_summary
from bank.pillars.p2.decisioning import determine_zone, packet_status_and_confirmation
from bank.pillars.p2.enums import (
    DecisioningZone,
    ModelMaturityStage,
    PacketStatus,
)
from bank.pillars.p4.contracts.p2_inbound import Pillar2RiskPacket
from bank.pillars.p4.integration.pillar4 import Pillar4
from bank.pillars.p4.domain.veto import TriggerType


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


def _good(ref: str) -> Pillar2RiskPacket:
    # EL ratio = 5 / 1000 = 0.5% — comfortably inside the 2% budget.
    return _packet(ref, brr=3, pd=0.01, lgd=0.5, ead=1000.0)


def _overbudget(ref: str) -> Pillar2RiskPacket:
    # EL ratio = 450 / 12000 = 3.75% — over the 2% budgeted-loss bound.
    return _packet(ref, brr=6, pd=0.05, lgd=0.75, ead=12000.0)


def _ratio_loan(ref: str, *, ead: float, el: float, brr: int = 6) -> Pillar2RiskPacket:
    """Loan built directly from README scenario numbers (ead, el)."""
    return Pillar2RiskPacket(
        facility_ref=ref,
        brr=brr,
        pd=1.0,
        lgd=1.0,
        ead=ead,
        el=el,
        product_type="TERM_LOAN",
    )


def _engine(with_tier_d: bool = True) -> Pillar4:
    p4 = Pillar4(in_memory_ports=True)
    if with_tier_d:
        # Keep Tier D / RWA far above the floor so ONLY portfolio EL is the
        # discriminant in these tests (Tier D starts at 0 by default).
        p4.capital.set_tier_d_amount(100_000.0)
    return p4


def test_good_book_stays_clear():
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_good("FAC-G1"))
    p4.ports.p2.feed_risk_packet(_good("FAC-G2"))

    read = p4.evaluate_track1_read_only()
    assert read["breached_triggers"] == []
    assert p4.veto_engine.state.track1.is_frozen() is False


def test_overbudget_booking_trips_standing_freeze():
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_good("FAC-G1"))
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))  # book avg 3.75% -> freeze

    assert p4.veto_engine.state.track1.is_frozen() is True
    assert TriggerType.PORTFOLIO_EL.value in p4.veto_engine.state.track1.breached_triggers

    # The freeze is STANDING: subsequent clean recomputes must NOT self-lift
    # (review #1). Only a governance review may lift it.
    read = p4.evaluate_track1_read_only()
    assert read["breached_triggers"] == [TriggerType.PORTFOLIO_EL.value]
    p4.recompute_and_evaluate_track1()
    assert p4.veto_engine.state.track1.is_frozen() is True


def test_lift_records_governance_ref_but_standing_reeasserts():
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    p4.veto_engine.review_and_lift_track1("GOV-FLOW-001")
    assert p4.veto_engine.state.track1.is_frozen() is False
    assert p4.veto_engine.state.track1.breached_triggers == {}

    # The release is traceable (veto_lift notification carries the ref).
    lifts = [n for n in p4.veto_engine.notifier.notifications if n.get("event") == "veto_lift"]
    assert lifts and lifts[-1]["governance_ref"] == "GOV-FLOW-001"
    assert TriggerType.PORTFOLIO_EL.value in lifts[-1]["triggers"]

    # While the over-budget exposure remains, the standing condition re-asserts
    # on the next evaluation — governance release is not a free pass.
    p4.recompute_and_evaluate_track1()
    assert p4.veto_engine.state.track1.is_frozen() is True

    # Even after the offending exposure is withdrawn (mirror_close releases the
    # risk packet), the standing freeze does NOT self-clear: only a governance
    # review may lift it (review #1).
    p4.capital.release_risk_packet("FAC-BAD")
    p4.ifrs9.release("FAC-BAD")
    p4.recompute_and_evaluate_track1()
    assert p4.veto_engine.state.track1.is_frozen() is True

    # Governance releases on a now-clean book: the state stays clean and new
    # good loans proceed without a re-freeze.
    p4.veto_engine.review_and_lift_track1("GOV-FLOW-002")
    assert p4.veto_engine.state.track1.is_frozen() is False
    p4.recompute_and_evaluate_track1()
    assert p4.veto_engine.state.track1.is_frozen() is False
    p4.ports.p2.feed_risk_packet(_good("FAC-G3"))
    assert p4.veto_engine.state.track1.is_frozen() is False
    assert p4.evaluate_track1_read_only()["breached_triggers"] == []


@pytest.mark.asyncio
async def test_demo_state_feed_surfaces_ratio_and_triggers(monkeypatch):
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_good("FAC-G1"))
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    class _FakeRuntime:
        _loaded = True

        def __init__(self, engine):
            self._engine = engine

        async def load(self):
            return None

        def _ensure_engine(self):
            return self._engine

    monkeypatch.setattr("bank.pillars.p1.mirror.p4_runtime", lambda: _FakeRuntime(p4))

    summary = await _safe_p4_summary()

    assert summary["track1_status"] == "frozen"
    assert summary["portfolio_el_ratio"] == pytest.approx(455.0 / 13000.0)
    assert summary["budgeted_loss_ratio"] == 0.02
    assert TriggerType.PORTFOLIO_EL.value in summary["breached_triggers"]
    assert isinstance(summary["unmonitored_triggers"], list)
    # STANDING freeze reason must be surfaced even when the live read is clean:
    # the freeze is held for portfolio_el and carries a frozen_since timestamp.
    assert summary["standing_breached_triggers"] == [TriggerType.PORTFOLIO_EL.value]
    assert summary["frozen_since"] is not None
    # The demo feed must never freeze on its own — calling it twice leaves the
    # veto state untouched.
    assert p4.veto_engine.state.track1.is_frozen() is True


def test_read_only_eval_never_freezes():
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_good("FAC-G1"))
    p4.capital.register_risk_packet(_overbudget("FAC-BAD"))

    read = p4.evaluate_track1_read_only()
    assert read["breached_triggers"] == [TriggerType.PORTFOLIO_EL.value]
    assert p4.veto_engine.state.track1.is_frozen() is False
    # still standing-clear even after being consulted
    p4.evaluate_track1_read_only()
    assert p4.veto_engine.state.track1.is_frozen() is False


# ---- README Rule A: per-loan EL/EAD > 2% downgrades the zone, never rejects --


def test_rule_a_over_budget_el_downgrades_auto_approve_to_augmented():
    # Loan D scenario: EL/EAD = 3.0% > 2% budget. Rule A is a zone downgrade
    # ONLY — the application is never auto-rejected.
    zone = determine_zone(
        brr=6, dqs=0.9, is_thin_file=False, has_policy_exception=False,
        el_within_budgeted_loss=False,
    )
    assert zone is DecisioningZone.AUGMENTED_DECISION
    status, confirm_required = packet_status_and_confirmation(
        DecisioningZone.AUGMENTED_DECISION,
        ModelMaturityStage.PRODUCTION,
        production_auto_approve_enabled=False,
    )
    assert status is PacketStatus.PROVISIONAL
    assert confirm_required is True


def test_rule_a_auto_approve_requires_el_within_budget():
    in_budget = determine_zone(
        brr=2, dqs=0.9, is_thin_file=False, has_policy_exception=False,
        el_within_budgeted_loss=True,
    )
    assert in_budget is DecisioningZone.AUTO_APPROVE

    over_budget = determine_zone(
        brr=2, dqs=0.9, is_thin_file=False, has_policy_exception=False,
        el_within_budgeted_loss=False,
    )
    assert over_budget is DecisioningZone.AUGMENTED_DECISION


def test_rule_a_high_brr_is_manual_review_regardless_of_el():
    zone = determine_zone(
        brr=8, dqs=0.9, is_thin_file=False, has_policy_exception=False,
        el_within_budgeted_loss=True,
    )
    assert zone is DecisioningZone.MANUAL_REVIEW


# ---- README Rule B: whole-book portfolio EL freezes Track 1 ------------------


def test_rule_b_single_over_budget_loan_on_empty_book_freezes():
    # README row 3: Loan D alone (EAD 200k, EL 6k => 3.0% > 2%) freezes the
    # standalone book immediately — the documented mystery, not a bug.
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_ratio_loan("FAC-D", ead=200_000.0, el=6_000.0))

    assert p4.veto_engine.state.track1.is_frozen() is True
    assert (
        TriggerType.PORTFOLIO_EL.value
        in p4.veto_engine.state.track1.breached_triggers
    )


def test_rule_b_diluted_good_book_does_not_freeze():
    # README Loan D example: B 300k/3k + C 500k/5k + D 200k/6k =>
    # sum EL 14k over sum EAD 1,000k = 1.4% < 2%: portfolio stays CLEAR even
    # though D's own loan-level ratio is 3.0% (that is Rule A, zone-only).
    p4 = _engine()
    # Large exposures -> large RWA; raise Tier D well above the 12% floor so
    # ONLY portfolio EL is the discriminant in this scenario.
    p4.capital.set_tier_d_amount(2_000_000.0)
    p4.ports.p2.feed_risk_packet(_ratio_loan("FAC-B", ead=300_000.0, el=3_000.0))
    p4.ports.p2.feed_risk_packet(_ratio_loan("FAC-C", ead=500_000.0, el=5_000.0))
    p4.ports.p2.feed_risk_packet(_ratio_loan("FAC-D", ead=200_000.0, el=6_000.0))

    read = p4.evaluate_track1_read_only()
    assert read["breached_triggers"] == []
    assert p4.veto_engine.state.track1.is_frozen() is False
    assert read["snapshot"].portfolio_el == pytest.approx(14_000.0 / 1_000_000.0)


def test_feed_standing_reason_survives_a_now_clean_live_book():
    # Freeze trips on the over-budget first loan, then the offending exposure
    # is withdrawn. The live book is clean (0 breached triggers), but the
    # STANDING freeze is still held — the feed must report the real reason.
    p4 = _engine()
    p4.ports.p2.feed_risk_packet(_overbudget("FAC-BAD"))
    assert p4.veto_engine.state.track1.is_frozen() is True

    p4.capital.release_risk_packet("FAC-BAD")
    p4.ifrs9.release("FAC-BAD")
    p4.recompute_and_evaluate_track1()

    read = p4.evaluate_track1_read_only()
    assert read["breached_triggers"] == []  # live read is clean
    assert p4.veto_engine.state.track1.is_frozen() is True  # standing holds
    standing = p4.veto_engine.state.track1.breached_triggers
    assert TriggerType.PORTFOLIO_EL.value in standing
    assert p4.veto_engine.state.track1.frozen_since is not None


# ---- import de-dup guard (never a second row for the same borrower) ----------


class _Row:
    def __init__(self, id_: str, display_name: str):
        self.id = id_
        self.display_name = display_name


class _OneResult:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row


class _DupSession:
    def __init__(self, row):
        self._row = row
        self.committed = False

    async def execute(self, *a, **k):
        return _OneResult(self._row)

    async def commit(self):
        self.committed = True

    async def flush(self):
        pass


class _DupCtx:
    def __init__(self, row):
        self._row = row

    async def __aenter__(self):
        return _DupSession(self._row)

    async def __aexit__(self, *exc):
        return False


async def _import_payload(**overrides):
    from bank.pillars.p1.schemas import CandidateImport

    base = dict(
        first_name="Nadia",
        last_name="Al Riyami",
        monthly_salary=900.0,
        requested_amount=10_000.0,
    )
    base.update(overrides)
    return CandidateImport(**base)


@pytest.mark.asyncio
async def test_import_candidate_rejects_duplicate_national_id(monkeypatch):
    from bank.pillars.p1.service import CandidateDuplicateError, CandidateService

    service = CandidateService()
    monkeypatch.setattr(
        service, "_session_factory", lambda: _DupCtx(_Row("cand-dup", "Nadia Al Riyami"))
    )
    payload = await _import_payload(national_id="OM-111-2026")

    with pytest.raises(CandidateDuplicateError):
        await service.import_candidate(payload)


@pytest.mark.asyncio
async def test_import_candidate_rejects_duplicate_display_name_case_insensitive(monkeypatch):
    from bank.pillars.p1.service import CandidateDuplicateError, CandidateService

    service = CandidateService()
    # Existing row stored the name in different case; normalised compare must hit.
    monkeypatch.setattr(
        service, "_session_factory", lambda: _DupCtx(_Row("cand-dup", "NADIA AL RIYAMI"))
    )
    payload = await _import_payload(first_name="nadia", last_name="al riyami", national_id=None)

    with pytest.raises(CandidateDuplicateError):
        await service.import_candidate(payload)