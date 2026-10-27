"""A write-off must be true before it is booked (``bug_bilan_fix_round_2.md``, R1).

Round 1 gave ``mark_default`` a ``loss_amount`` so a defaulted loan stops
carrying its balance in 4110 forever (B2) — but the amount was accepted
verbatim: ``1e12`` on a 10,000 loan, ``inf`` and ``nan`` all posted. Every one
of them would have pushed loss onto the passif without a matching debit.

The guard runs *before* the state machine and before any post, so a rejected
write-off leaves the ledger exactly as it was: no marker, no write-off, no
state change.
"""
from __future__ import annotations

import math

import pytest

from bank.pillars.p3.domain.enums import PostingEventType
from bank.pillars.p3.domain.memos import MEMO_DEFAULT_MARKER, MEMO_WRITE_OFF
from bank.pillars.p3.errors import WriteOffExceedsOutstandingError
from tests.conftest import make_packet

_DISBURSED = 10_000.0


def _prepare(orchestrator, facility_id: str):
    """Drive the facility to the only state a default is legal from."""
    packet = make_packet(facility_id=facility_id)
    orchestrator.originate(packet)
    orchestrator.disburse(facility_id, packet, _DISBURSED, "USD")
    orchestrator.mark_delinquent(facility_id, packet)
    return packet


def _event_count(orchestrator) -> int:
    return len(orchestrator.posting_service.posted_events())


def _write_offs(orchestrator) -> list:
    return [
        e
        for e in orchestrator.posting_service.posted_events()
        if e.memo == MEMO_WRITE_OFF
    ]


def test_write_off_above_outstanding_is_rejected(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO-HUGE")
    before = _event_count(orchestrator)

    with pytest.raises(WriteOffExceedsOutstandingError):
        orchestrator.mark_default("FAC-WO-HUGE", packet, 1e12, "USD")

    assert _event_count(orchestrator) == before
    assert _write_offs(orchestrator) == []


@pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan])
def test_non_finite_write_off_is_rejected(orchestrator, bad: float) -> None:
    packet = _prepare(orchestrator, "FAC-WO-NAN")
    before = _event_count(orchestrator)

    with pytest.raises(ValueError):
        orchestrator.mark_default("FAC-WO-NAN", packet, bad, "USD")

    assert _event_count(orchestrator) == before
    assert _write_offs(orchestrator) == []


def test_negative_write_off_is_rejected(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO-NEG")
    before = _event_count(orchestrator)

    with pytest.raises(ValueError):
        orchestrator.mark_default("FAC-WO-NEG", packet, -1.0, "USD")

    assert _event_count(orchestrator) == before
    assert _write_offs(orchestrator) == []


def test_write_off_equal_to_outstanding_is_accepted(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO-EQ")

    marker = orchestrator.mark_default("FAC-WO-EQ", packet, _DISBURSED, "USD")

    assert marker.memo == MEMO_DEFAULT_MARKER
    assert len(_write_offs(orchestrator)) == 1
    assert _write_offs(orchestrator)[0].amount == _DISBURSED


def test_write_off_below_outstanding_is_accepted(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO-OK")

    orchestrator.mark_default("FAC-WO-OK", packet, 3_200.0, "USD")

    assert len(_write_offs(orchestrator)) == 1
    assert _write_offs(orchestrator)[0].amount == 3_200.0


def test_a_facility_with_no_disbursement_has_nothing_to_measure(orchestrator) -> None:
    """The cap is skipped rather than rejected — same rule as the repayment guard."""
    packet = make_packet(facility_id="FAC-WO-UNDISBURSED")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-WO-UNDISBURSED", packet, 0.0, "USD")
    orchestrator.mark_delinquent("FAC-WO-UNDISBURSED", packet)

    orchestrator.mark_default("FAC-WO-UNDISBURSED", packet, 3_200.0, "USD")

    assert len(_write_offs(orchestrator)) == 1


def test_a_rejected_write_off_does_not_default_the_facility(orchestrator) -> None:
    from bank.pillars.p3.domain.enums import LoanState

    packet = _prepare(orchestrator, "FAC-WO-STATE")

    with pytest.raises(WriteOffExceedsOutstandingError):
        orchestrator.mark_default("FAC-WO-STATE", packet, 1e12, "USD")

    facility = orchestrator._facilities["FAC-WO-STATE"]
    assert facility.state is not LoanState.DEFAULT
    assert not any(
        e.event_type is PostingEventType.LOSS_RECOVERY
        and e.memo == MEMO_DEFAULT_MARKER
        for e in orchestrator.posting_service.posted_events()
    )
