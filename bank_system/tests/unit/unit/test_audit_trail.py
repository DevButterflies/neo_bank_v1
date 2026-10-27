from datetime import datetime, timezone

from bank.pillars.p3.audit.trail import AuditTrail
from bank.pillars.p3.domain.enums import LoanState, MaturityStage


def make_record(record_id="AUD-1", facility_id="FAC-1"):
    from bank.pillars.p3.domain.events import AuditRecord

    return AuditRecord(
        record_id=record_id,
        facility_id=facility_id,
        event_type="DISBURSEMENT",
        timestamp=datetime.now(timezone.utc),
        actor_reference="SYSTEM",
        p2_packet_version="v1",
        maturity_stage=MaturityStage.SANDBOX,
        brr_pd_grid_version="grid-1",
        collateral_track=None,
        p4_veto_status="TRACK_1_PORTFOLIO:CLEAR",
        posting_routing_flag="PRINCIPAL_MOVEMENT",
        core_banking_confirmed=True,
        resulting_state=LoanState.ACTIVE,
    )


def test_append_and_retrieve():
    trail = AuditTrail()
    trail.append(make_record())
    assert len(trail) == 1


def test_returned_list_is_a_copy_not_the_live_store():
    trail = AuditTrail()
    trail.append(make_record())
    records = trail.all_records()
    records.append(make_record(record_id="AUD-FORGED"))
    assert len(trail) == 1  # mutation of the returned list must not leak in


def test_for_facility_filters_correctly():
    trail = AuditTrail()
    trail.append(make_record(record_id="AUD-1", facility_id="FAC-1"))
    trail.append(make_record(record_id="AUD-2", facility_id="FAC-2"))
    assert len(trail.for_facility("FAC-1")) == 1


def test_no_update_or_delete_methods_exist():
    # Structural check: append-only means these methods must not exist.
    trail = AuditTrail()
    assert not hasattr(trail, "update")
    assert not hasattr(trail, "delete")
    assert not hasattr(trail, "remove")
    assert not hasattr(trail, "clear")
