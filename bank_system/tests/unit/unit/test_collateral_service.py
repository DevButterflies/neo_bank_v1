import pytest

from bank.pillars.p3.domain.enums import CollateralTrack
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.engine.collateral_service import CollateralService
from bank.pillars.p3.errors import AdmissibilityNotConfirmedError, PendingGovernanceItemError
from tests.conftest import make_packet


@pytest.fixture
def service():
    return CollateralService()


@pytest.fixture
def facility():
    return LoanFacility(facility_id="FAC-001")


def test_record_track1_collateral_on_confirmed_packet(service, facility):
    packet = make_packet(collateral_track=CollateralTrack.TRACK_1_CLASSICAL)
    collateral = service.record_msme_pledged_collateral(facility, packet, external_reference="deed-123")
    assert collateral in facility.collateral_objects
    assert collateral.track is CollateralTrack.TRACK_1_CLASSICAL


def test_record_collateral_requires_confirmed_packet(service, facility):
    from bank.pillars.p3.domain.enums import P2PacketStatus
    unconfirmed = make_packet(status=P2PacketStatus.CONDITIONAL, officer_confirmed=False, officer_id=None)
    with pytest.raises(AdmissibilityNotConfirmedError):
        service.record_msme_pledged_collateral(facility, unconfirmed)


@pytest.mark.parametrize("track", [CollateralTrack.TRACK_2_NFT, CollateralTrack.TRACK_3_STABLECOIN])
def test_track2_and_track3_are_pending_gated(service, facility, track):
    packet = make_packet(collateral_track=track)
    with pytest.raises(PendingGovernanceItemError):
        service.record_msme_pledged_collateral(facility, packet)
    # nothing should have been recorded despite the attempt
    assert facility.collateral_objects == []


def test_pooled_guarantee_pledge_is_pending_gated(service, facility):
    with pytest.raises(PendingGovernanceItemError):
        service.record_pooled_guarantee_pledge(facility)


def test_track3_object_cannot_be_constructed_under_g_model_flag():
    from bank.pillars.p3.domain.collateral import CollateralObject, CollateralObjectKind
    from bank.pillars.p3.domain.enums import ModelFlag

    with pytest.raises(ValueError):
        CollateralObject(
            collateral_id="COL-1",
            facility_id="FAC-001",
            kind=CollateralObjectKind.MSME_PLEDGED,
            track=CollateralTrack.TRACK_3_STABLECOIN,
            model_flag=ModelFlag.GUARANTEE,
            p2_packet_id="P2-0001",
        )
