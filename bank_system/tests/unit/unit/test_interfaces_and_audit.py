import pytest

from bank.pillars.p3.domain.enums import PostingEventType, VetoScope
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.engine.posting_service import PostingService
from bank.pillars.p3.engine.reconciliation import reconcile, reconcile_or_alert
from bank.pillars.p3.errors import (
    AdmissibilityNotConfirmedError,
    AutoOriginationNotPermittedError,
    GovernanceBoundaryError,
    ReconciliationBreachError,
    VetoFrozenError,
)
from bank.pillars.p3.interfaces.non_interfaces import emit_cass_feed, emit_ifrs9_staging_signal
from bank.pillars.p3.interfaces.p2_gate import P2Gate
from bank.pillars.p3.interfaces.p4_router import P4VetoRouter
from bank.pillars.p3.interfaces.p5_gate import P5Gate
from tests.conftest import make_packet


# -- P4 veto router -------------------------------------------------------

def test_portfolio_veto_freezes_all_facilities():
    router = P4VetoRouter()
    facilities = [LoanFacility(facility_id=f"FAC-{i}") for i in range(3)]
    router.apply_portfolio_veto(facilities)
    for f in facilities:
        assert f.veto_frozen is True
        with pytest.raises(VetoFrozenError):
            router.assert_not_frozen(f)


def test_facility_veto_is_scoped_to_one_facility():
    router = P4VetoRouter()
    f1, f2 = LoanFacility(facility_id="FAC-1"), LoanFacility(facility_id="FAC-2")
    router.apply_facility_veto(f1)
    assert f1.veto_frozen is True
    assert f2.veto_frozen is False


def test_veto_status_reports_both_scopes():
    router = P4VetoRouter()
    f = LoanFacility(facility_id="FAC-1")
    router.apply_facility_veto(f)
    status = router.veto_status(f)
    assert status[VetoScope.TRACK_1_PORTFOLIO] == "CLEAR"
    assert status[VetoScope.TRACK_2_FACILITY] == "ACTIVE"


def test_clearing_portfolio_veto_respects_facility_level_veto():
    router = P4VetoRouter()
    f1, f2 = LoanFacility(facility_id="FAC-1"), LoanFacility(facility_id="FAC-2")
    router.apply_portfolio_veto([f1, f2])
    router.apply_facility_veto(f1)  # f1 has both
    router.clear_portfolio_veto([f1, f2])
    assert f2.veto_frozen is False
    assert f1.veto_frozen is True  # facility-level veto still holds


# -- P5 gate ----------------------------------------------------------------

def test_p5_object_recorded_only_on_confirmed_packet():
    gate = P5Gate()
    confirmed = make_packet()
    ref = gate.record_if_confirmed(confirmed, "P5-OBJ-001")
    assert ref == "P5-OBJ-001"


def test_p5_object_blocked_without_confirmation():
    from bank.pillars.p3.domain.enums import P2PacketStatus
    gate = P5Gate()
    unconfirmed = make_packet(status=P2PacketStatus.PROVISIONAL, officer_confirmed=False, officer_id=None)
    with pytest.raises(AdmissibilityNotConfirmedError):
        gate.record_if_confirmed(unconfirmed, "P5-OBJ-001")


# -- P2 gate ------------------------------------------------------------------

def test_p2_gate_records_packet_regardless_of_confirmation():
    from bank.pillars.p3.domain.enums import P2PacketStatus
    gate = P2Gate()
    unconfirmed = make_packet(status=P2PacketStatus.PROVISIONAL, officer_confirmed=False, officer_id=None)
    gate.receive_packet(unconfirmed)
    assert gate.get(unconfirmed.packet_id) is unconfirmed


def test_p2_gate_blocks_origination_on_unconfirmed_packet_in_sandbox():
    from bank.pillars.p3.domain.enums import P2PacketStatus, MaturityStage
    gate = P2Gate()
    unconfirmed = make_packet(
        status=P2PacketStatus.PROVISIONAL,
        officer_confirmed=False,
        officer_id=None,
        maturity_stage=MaturityStage.SANDBOX,
    )
    gate.receive_packet(unconfirmed)
    with pytest.raises(AutoOriginationNotPermittedError):
        gate.authorize_origination(unconfirmed.packet_id)


# -- non-interfaces ----------------------------------------------------------

def test_cass_feed_is_never_emitted():
    with pytest.raises(GovernanceBoundaryError):
        emit_cass_feed()


def test_ifrs9_staging_is_never_emitted():
    with pytest.raises(GovernanceBoundaryError):
        emit_ifrs9_staging_signal()


# -- reconciliation ------------------------------------------------------------

def test_reconciliation_within_tolerance(core_banking, ledger):
    service = PostingService(core_banking)
    service.capture_and_post("FAC-1", PostingEventType.LOAN_INCOME, 100.0, "USD", "P2-1")
    result = reconcile(service.posted_events(), ledger, tolerance=0.01)
    assert result.within_tolerance
    assert result.discrepancy == 0.0


def test_reconciliation_breach_raises(core_banking, ledger):
    service = PostingService(core_banking)
    events = service.posted_events()
    # Simulate a P3 event that was never actually posted to core banking
    from bank.pillars.p3.domain.events import PostingEvent
    phantom = PostingEvent(
        event_id="EVT-PHANTOM",
        facility_id="FAC-1",
        event_type=PostingEventType.LOAN_INCOME,
        amount=500.0,
        currency="USD",
        p2_packet_id="P2-1",
    )
    with pytest.raises(ReconciliationBreachError):
        reconcile_or_alert([phantom], ledger, tolerance=0.01)


def test_core_banking_prevails_in_totals_not_p3_shadow_log(core_banking, ledger):
    service = PostingService(core_banking)
    service.capture_and_post("FAC-1", PostingEventType.LOAN_INCOME, 100.0, "USD", "P2-1")
    # ledger.total_amount() is treated as ground truth by reconcile();
    # this test simply pins that behaviour so a refactor can't quietly
    # flip which side is authoritative.
    result = reconcile(service.posted_events(), ledger, tolerance=0.0)
    assert result.core_banking_total == ledger.total_amount()
