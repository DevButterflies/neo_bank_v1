import pytest

from bank.pillars.p3.domain.enums import MaturityStage, P2PacketStatus
from bank.pillars.p3.errors import (
    AllocationLogicForbiddenError,
    AutoOriginationNotPermittedError,
    PendingGovernanceItemError,
)
from bank.pillars.p3.governance.allocation_guard import assert_allocation_untouched
from bank.pillars.p3.governance.maturity_gate import (
    ProductionAutoApproval,
    check_origination_gate,
)
from bank.pillars.p3.governance.pending_registry import PENDING_REGISTER, PendingItem, stub
from tests.conftest import make_packet


# -- PENDING registry ----------------------------------------------------

@pytest.mark.parametrize("item", list(PendingItem))
def test_every_pending_item_always_raises(item):
    with pytest.raises(PendingGovernanceItemError):
        stub(item)


def test_pending_register_covers_all_five_documented_items():
    # Canon §10 / Spec §11 / Build Handoff §6.2 name exactly five items.
    assert len(PENDING_REGISTER) == 5
    assert set(PENDING_REGISTER) == set(PendingItem)


# -- allocation guard ------------------------------------------------------

def test_clean_payload_passes():
    assert_allocation_untouched({"event_type": "LOAN_INCOME", "amount": 100.0})


@pytest.mark.parametrize(
    "forbidden_key",
    ["tier_a_share", "tier_b_share", "absf_amount", "loss_repartition", "burden_share"],
)
def test_forbidden_allocation_key_raises(forbidden_key):
    with pytest.raises(AllocationLogicForbiddenError):
        assert_allocation_untouched({"event_type": "LOAN_INCOME", forbidden_key: 42})


# -- maturity gate -----------------------------------------------------------

def test_confirmed_packet_always_passes_gate_regardless_of_stage():
    for stage in MaturityStage:
        packet = make_packet(maturity_stage=stage, officer_confirmed=True, officer_id="O1")
        check_origination_gate(packet)  # should not raise


@pytest.mark.parametrize("stage", [MaturityStage.DESIGN, MaturityStage.SANDBOX])
def test_unconfirmed_packet_blocked_pre_production(stage):
    packet = make_packet(
        maturity_stage=stage,
        status=P2PacketStatus.CONDITIONAL,
        officer_confirmed=False,
        officer_id=None,
    )
    with pytest.raises(AutoOriginationNotPermittedError):
        check_origination_gate(packet)


def test_unconfirmed_packet_blocked_in_production_without_p4_approval():
    packet = make_packet(
        maturity_stage=MaturityStage.PRODUCTION,
        status=P2PacketStatus.CONDITIONAL,
        officer_confirmed=False,
        officer_id=None,
    )
    with pytest.raises(AutoOriginationNotPermittedError):
        check_origination_gate(packet)

    with pytest.raises(AutoOriginationNotPermittedError):
        check_origination_gate(packet, ProductionAutoApproval(approved_by_p4=True, orchestrator_notified=False))


def test_unconfirmed_packet_permitted_in_production_with_full_p4_approval():
    packet = make_packet(
        maturity_stage=MaturityStage.PRODUCTION,
        status=P2PacketStatus.CONDITIONAL,
        officer_confirmed=False,
        officer_id=None,
    )
    approval = ProductionAutoApproval(approved_by_p4=True, orchestrator_notified=True)
    check_origination_gate(packet, approval)  # should not raise
