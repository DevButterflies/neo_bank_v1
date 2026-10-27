import pytest

from bank.pillars.p3.domain.enums import LoanState
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.engine.state_machine import LoanLifecycleStateMachine
from bank.pillars.p3.errors import (
    InvalidStateTransitionError,
    UnauthorisedDecisionError,
    UnconfirmedPacketError,
    VetoFrozenError,
)
from tests.conftest import make_packet


@pytest.fixture
def sm():
    return LoanLifecycleStateMachine()


@pytest.fixture
def facility():
    return LoanFacility(facility_id="FAC-001")


def test_initial_state_is_approved(facility):
    assert facility.state is LoanState.APPROVED


def test_activate_requires_confirmed_packet(sm, facility):
    from bank.pillars.p3.domain.enums import P2PacketStatus
    unconfirmed = make_packet(status=P2PacketStatus.PROVISIONAL, officer_confirmed=False, officer_id=None)
    with pytest.raises(UnconfirmedPacketError):
        sm.activate(facility, unconfirmed)
    assert facility.state is LoanState.APPROVED


def test_full_happy_path_lifecycle(sm, facility, confirmed_packet, workout_packet):
    sm.activate(facility, confirmed_packet)
    assert facility.state is LoanState.ACTIVE

    sm.receive_repayment(facility)
    assert facility.state is LoanState.REPAYING

    sm.mark_delinquent(facility)
    assert facility.state is LoanState.DELINQUENT

    sm.mark_default(facility)
    assert facility.state is LoanState.DEFAULT

    sm.initiate_recovery(facility, workout_packet)
    assert facility.state is LoanState.RECOVERY

    sm.close(facility)
    assert facility.state is LoanState.CLOSED


def test_delinquency_can_cure_back_to_repaying(sm, facility, confirmed_packet):
    sm.activate(facility, confirmed_packet)
    sm.receive_repayment(facility)
    sm.mark_delinquent(facility)
    sm.receive_repayment(facility)  # cures
    assert facility.state is LoanState.REPAYING


def test_illegal_transition_raises(sm, facility):
    with pytest.raises(InvalidStateTransitionError):
        sm.mark_default(facility)  # APPROVED -> DEFAULT not permitted


def test_closed_is_terminal(sm, facility, confirmed_packet):
    sm.activate(facility, confirmed_packet)
    sm.close(facility)
    with pytest.raises(InvalidStateTransitionError):
        sm.receive_repayment(facility)


def test_restructuring_requires_human_authorisation(sm, facility, confirmed_packet):
    sm.activate(facility, confirmed_packet)
    # confirmed_packet has human_authorised_for_workout=False by default
    with pytest.raises(UnauthorisedDecisionError):
        sm.restructure(facility, confirmed_packet)
    assert facility.state is LoanState.ACTIVE


def test_restructuring_with_authorisation_returns_to_active(sm, facility, confirmed_packet, workout_packet):
    sm.activate(facility, confirmed_packet)
    sm.restructure(facility, workout_packet)
    assert facility.state is LoanState.ACTIVE


def test_recovery_requires_human_authorisation(sm, facility, confirmed_packet):
    sm.activate(facility, confirmed_packet)
    sm.receive_repayment(facility)
    sm.mark_delinquent(facility)
    sm.mark_default(facility)
    with pytest.raises(UnauthorisedDecisionError):
        sm.initiate_recovery(facility, confirmed_packet)


def test_veto_frozen_facility_rejects_all_transitions(sm, facility, confirmed_packet):
    sm.activate(facility, confirmed_packet)
    facility.veto_frozen = True
    with pytest.raises(VetoFrozenError):
        sm.receive_repayment(facility)


def test_activate_veto_precedes_packet_confirmation(sm, facility):
    """Spec §4 check order (veto first): a frozen facility with an UNCONFIRMED
    packet must raise VetoFrozenError, not UnconfirmedPacketError."""
    from bank.pillars.p3.domain.enums import P2PacketStatus
    unconfirmed = make_packet(status=P2PacketStatus.PROVISIONAL, officer_confirmed=False, officer_id=None)
    facility.veto_frozen = True
    with pytest.raises(VetoFrozenError):
        sm.activate(facility, unconfirmed)
    assert facility.state is LoanState.APPROVED


def test_restructure_veto_precedes_packet_authorisation(sm, facility, workout_packet):
    """A veto-frozen facility rejects restructure even on a fully confirmed,
    human-authorised packet."""
    sm.activate(facility, workout_packet)
    facility.veto_frozen = True
    with pytest.raises(VetoFrozenError):
        sm.restructure(facility, workout_packet)
    assert facility.state is LoanState.ACTIVE


def test_initiate_recovery_veto_precedes_packet_authorisation(sm, facility, workout_packet):
    sm.activate(facility, workout_packet)
    sm.mark_delinquent(facility)
    sm.mark_default(facility)
    facility.veto_frozen = True
    with pytest.raises(VetoFrozenError):
        sm.initiate_recovery(facility, workout_packet)
    assert facility.state is LoanState.DEFAULT


def test_valid_next_state_precedes_packet_confirmation(sm, facility, confirmed_packet):
    """Spec §4 check order: illegal next-state is rejected before the packet
    confirmation is even consulted."""
    from bank.pillars.p3.domain.enums import P2PacketStatus
    unconfirmed = make_packet(status=P2PacketStatus.PROVISIONAL, officer_confirmed=False, officer_id=None)
    sm.activate(facility, confirmed_packet)  # now ACTIVE; ACTIVATE again is illegal
    with pytest.raises(InvalidStateTransitionError):
        sm.activate(facility, unconfirmed)
    assert facility.state is LoanState.ACTIVE


def test_drawdown_frozen_states(sm, facility, confirmed_packet):
    sm.activate(facility, confirmed_packet)
    assert sm.is_drawdown_frozen(facility) is False
    sm.receive_repayment(facility)
    sm.mark_delinquent(facility)
    assert sm.is_drawdown_frozen(facility) is True
