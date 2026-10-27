import pytest

from bank.pillars.p3.core_banking.interface import CoreBankingClient
from bank.pillars.p3.core_banking.ledger import CoreBankingLedger
from bank.pillars.p3.domain.enums import CollateralTrack, MaturityStage, P2PacketStatus
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.engine.orchestrator import Pillar3Orchestrator


@pytest.fixture
def ledger():
    return CoreBankingLedger()


@pytest.fixture
def core_banking(ledger):
    return CoreBankingClient(ledger)


@pytest.fixture
def orchestrator(core_banking):
    return Pillar3Orchestrator(core_banking)


def make_packet(
    facility_id="FAC-001",
    packet_id="P2-0001",
    status=P2PacketStatus.APPROVED,
    maturity_stage=MaturityStage.SANDBOX,
    officer_confirmed=True,
    officer_id="OFFICER-1",
    human_authorised_for_workout=False,
    collateral_track=CollateralTrack.TRACK_1_CLASSICAL,
    packet_version="v1",
    grid_version="grid-2026.1",
):
    return P2OutputPacket(
        packet_id=packet_id,
        facility_id=facility_id,
        status=status,
        maturity_stage=maturity_stage,
        brr_pd_grid_version=grid_version,
        collateral_track=collateral_track,
        packet_version=packet_version,
        officer_confirmed=officer_confirmed,
        officer_id=officer_id,
        human_authorised_for_workout=human_authorised_for_workout,
    )


@pytest.fixture
def confirmed_packet():
    return make_packet()


@pytest.fixture
def workout_packet():
    return make_packet(
        packet_id="P2-0002",
        human_authorised_for_workout=True,
    )
