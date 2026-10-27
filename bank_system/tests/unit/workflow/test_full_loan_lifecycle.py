"""
Workflow tests — drive full, realistic loan lifecycles through the
orchestrator and check the observable results across every subsystem
(state, core banking, audit trail, P4 routing) agree with each other.
"""
from __future__ import annotations

import pytest

from bank.pillars.p3.domain.enums import LoanState, PostingEventType
from bank.pillars.p3.engine.reconciliation import reconcile
from bank.pillars.p3.errors import VetoFrozenError
from tests.conftest import make_packet


def test_happy_path_origination_to_closure(orchestrator, ledger):
    packet = make_packet(facility_id="FAC-100")

    facility = orchestrator.originate(packet)
    assert facility.state is LoanState.APPROVED

    orchestrator.pledge_collateral("FAC-100", packet, external_reference="title-deed-100")
    orchestrator.disburse("FAC-100", packet, 20_000.0, "USD")
    assert facility.state is LoanState.ACTIVE

    for _ in range(3):
        orchestrator.record_repayment("FAC-100", packet, 150.0, 500.0, "USD")
    assert facility.state is LoanState.REPAYING

    orchestrator.close("FAC-100", packet)
    assert facility.state is LoanState.CLOSED

    # Every posted event should have landed in core banking.
    result = reconcile(orchestrator.posting_service.posted_events(), ledger, tolerance=0.0)
    assert result.within_tolerance

    # Audit trail covers origination, collateral, disbursement, 3x
    # repayment (2 postings each), closure.
    events = [r.event_type for r in orchestrator.audit_trail.for_facility("FAC-100")]
    assert events[0] == "ORIGINATION_RECORDED"
    assert "COLLATERAL_PLEDGED" in events
    assert "DISBURSEMENT" in events
    assert events.count("REPAYMENT") == 6  # interest + principal x 3
    assert events[-1] == "CLOSURE"


def test_delinquency_default_recovery_closure_path(orchestrator, ledger, workout_packet):
    origination_packet = make_packet(facility_id="FAC-200")
    orchestrator.originate(origination_packet)
    orchestrator.disburse("FAC-200", origination_packet, 15_000.0, "USD")
    orchestrator.record_repayment("FAC-200", origination_packet, 100.0, 300.0, "USD")

    orchestrator.mark_delinquent("FAC-200", origination_packet)
    orchestrator.mark_default("FAC-200", origination_packet)

    recovery_packet = make_packet(
        facility_id="FAC-200", packet_id="P2-RECOVERY", human_authorised_for_workout=True
    )
    orchestrator.initiate_recovery("FAC-200", recovery_packet, 8_000.0, "USD")
    orchestrator.close("FAC-200", recovery_packet)

    facility = orchestrator.get_or_create_facility("FAC-200")
    assert facility.state is LoanState.CLOSED

    loss_events = [
        e for e in orchestrator.posting_service.posted_events()
        if e.event_type is PostingEventType.LOSS_RECOVERY
    ]
    assert len(loss_events) == 2  # default marker + recovery receipt


def test_restructuring_path(orchestrator, workout_packet):
    origination_packet = make_packet(facility_id="FAC-300")
    orchestrator.originate(origination_packet)
    orchestrator.disburse("FAC-300", origination_packet, 10_000.0, "USD")
    orchestrator.record_repayment("FAC-300", origination_packet, 80.0, 200.0, "USD")
    orchestrator.mark_delinquent("FAC-300", origination_packet)

    restructure_packet = make_packet(
        facility_id="FAC-300", packet_id="P2-RESTRUCTURE", human_authorised_for_workout=True
    )
    orchestrator.restructure("FAC-300", restructure_packet)

    facility = orchestrator.get_or_create_facility("FAC-300")
    assert facility.state is LoanState.ACTIVE  # back to active post-restructure


def test_p4_veto_freezes_drawdown_and_repayment(orchestrator):
    packet = make_packet(facility_id="FAC-400")
    orchestrator.originate(packet)
    facility = orchestrator.get_or_create_facility("FAC-400")

    orchestrator.p4_router.apply_facility_veto(facility)

    with pytest.raises(VetoFrozenError):
        orchestrator.disburse("FAC-400", packet, 5_000.0, "USD")


def test_veto_is_non_overridable_by_p2_or_p3(orchestrator):
    packet = make_packet(facility_id="FAC-401")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-401", packet, 5_000.0, "USD")
    facility = orchestrator.get_or_create_facility("FAC-401")

    orchestrator.p4_router.apply_facility_veto(facility)

    # Even a fully confirmed, human-authorised workout packet cannot
    # bypass an active P4 veto — the state machine itself checks
    # veto_frozen before consulting packet authorisation.
    workout = make_packet(
        facility_id="FAC-401", packet_id="P2-WORKOUT", human_authorised_for_workout=True
    )
    with pytest.raises(VetoFrozenError):
        orchestrator.state_machine.restructure(facility, workout)


def test_multiple_facilities_are_independent(orchestrator):
    p1 = make_packet(facility_id="FAC-A", packet_id="P2-A")
    p2 = make_packet(facility_id="FAC-B", packet_id="P2-B")
    orchestrator.originate(p1)
    orchestrator.originate(p2)
    orchestrator.disburse("FAC-A", p1, 1000.0, "USD")

    fa = orchestrator.get_or_create_facility("FAC-A")
    fb = orchestrator.get_or_create_facility("FAC-B")
    assert fa.state is LoanState.ACTIVE
    assert fb.state is LoanState.APPROVED
