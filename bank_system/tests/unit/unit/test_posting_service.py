import pytest

from bank.pillars.p3.domain.enums import ALLOCATION_ROUTED_EVENTS, MICRO_ONLY_EVENTS, PostingEventType
from bank.pillars.p3.engine.posting_service import PostingService
from bank.pillars.p3.errors import OutOfPostingSetError


@pytest.fixture
def service(core_banking):
    return PostingService(core_banking)


def test_capture_and_post_writes_to_core_banking(service, ledger):
    event = service.capture_and_post(
        "FAC-001", PostingEventType.LOAN_INCOME, 100.0, "USD", "P2-0001"
    )
    postings = ledger.postings_for_facility("FAC-001")
    assert len(postings) == 1
    assert postings[0].amount == 100.0
    assert postings[0].source_event_id == event.event_id


@pytest.mark.parametrize("event_type", sorted(ALLOCATION_ROUTED_EVENTS, key=lambda e: e.value))
def test_allocation_routed_events_produce_a_question(service, event_type):
    service.capture_and_post("FAC-001", event_type, 50.0, "USD", "P2-0001")
    questions = service.routed_allocation_questions()
    assert len(questions) == 1
    assert questions[0].event_type is event_type


@pytest.mark.parametrize("event_type", sorted(MICRO_ONLY_EVENTS, key=lambda e: e.value))
def test_micro_only_events_produce_no_question(service, event_type):
    service.capture_and_post("FAC-001", event_type, 50.0, "USD", "P2-0001")
    assert service.routed_allocation_questions() == []


def test_rejects_non_canonical_event_type(service):
    with pytest.raises(OutOfPostingSetError):
        service.capture_and_post("FAC-001", "MADE_UP_EVENT", 50.0, "USD", "P2-0001")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_amounts_before_posting(service, ledger, bad):
    """One central check for every event type (bug_bilan_fix_round_2.md, R2).

    NaN defeats every "< 0" / "> cap" comparison, so a caller-side guard can
    never be complete: it has to die here, before the ledger is touched.
    """
    with pytest.raises(ValueError):
        service.capture_and_post("FAC-001", PostingEventType.PRINCIPAL_MOVEMENT, bad, "USD", "P2-0001")

    assert service.posted_events() == []
    assert service.routed_allocation_questions() == []
    assert ledger.postings_for_facility("FAC-001") == []


def test_rejects_a_non_numeric_amount_before_posting(service, ledger):
    with pytest.raises(ValueError):
        service.capture_and_post("FAC-001", PostingEventType.LOAN_INCOME, "50.0", "USD", "P2-0001")

    assert service.posted_events() == []
    assert ledger.postings_for_facility("FAC-001") == []


def test_posted_events_are_tracked(service):
    service.capture_and_post("FAC-001", PostingEventType.ORIGINATION_FEE, 25.0, "USD", "P2-0001")
    service.capture_and_post("FAC-001", PostingEventType.PRINCIPAL_MOVEMENT, 1000.0, "USD", "P2-0001")
    assert len(service.posted_events()) == 2


def test_allocation_question_carries_no_per_tier_amount(service):
    service.capture_and_post("FAC-001", PostingEventType.LOSS_RECOVERY, 300.0, "USD", "P2-0001")
    q = service.routed_allocation_questions()[0]
    # AllocationQuestion is a frozen dataclass with a fixed field set —
    # this asserts no per-tier field exists on the object at all.
    field_names = {f for f in q.__dataclass_fields__}
    assert field_names == {"source_event_id", "facility_id", "event_type", "amount", "currency"}
