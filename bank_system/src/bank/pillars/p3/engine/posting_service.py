"""
Posting service — the P3<->core-banking seam and the P3->P4 routing
signal producer (Spec §3, Build Handoff §4).

    "Build rule — capture and post, do not allocate. For income,
    risk-premium, and loss events, Pillar 3 captures the per-loan event,
    posts it to core banking, and routes the portfolio-level allocation
    question to Pillar 4. Pillar 3 must not implement any cross-tier
    allocation, ABSF, Tier B-Fees, or loss-repartition computation."

This service is deliberately "dumb": for every event type it does the
same two things — post to core banking, and (if the event type is in
ALLOCATION_ROUTED_EVENTS) emit an AllocationQuestion for P4. It has no
branch anywhere that computes a share, a percentage, or a per-tier
amount. `assert_allocation_untouched` is run on every payload before
it's returned, as a belt-and-braces structural check.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import List, Optional

from bank.pillars.p3.core_banking.interface import CoreBankingClient
from bank.pillars.p3.domain.enums import ALLOCATION_ROUTED_EVENTS, PostingEventType
from bank.pillars.p3.domain.events import PostingEvent
from bank.pillars.p3.errors import OutOfPostingSetError
from bank.pillars.p3.governance.allocation_guard import assert_allocation_untouched


@dataclass(frozen=True)
class AllocationQuestion:
    """The routing signal P3 sends to P4 — NOT an allocation. It carries
    only the facts P4 needs to decide the allocation; it contains no
    per-tier amount."""

    source_event_id: str
    facility_id: str
    event_type: PostingEventType
    amount: float
    currency: str


class PostingService:
    def __init__(self, core_banking: CoreBankingClient) -> None:
        self._core_banking = core_banking
        self._posted_events: List[PostingEvent] = []
        self._routed_questions: List[AllocationQuestion] = []

    def capture_and_post(
        self,
        facility_id: str,
        event_type: PostingEventType,
        amount: float,
        currency: str,
        p2_packet_id: str,
        memo: Optional[str] = None,
    ) -> PostingEvent:
        if not isinstance(event_type, PostingEventType):
            raise OutOfPostingSetError(
                f"{event_type!r} is not in the canonical per-loan posting "
                "set (Spec §3 / Build Handoff §4)."
            )

        # One central check for every event type: a non-finite amount poisons
        # every total it touches, and NaN in particular slips through any
        # "< 0" / "> cap" comparison because both are False (R2).
        if not isinstance(amount, (int, float)) or not math.isfinite(amount):
            raise ValueError(f"posting amount must be finite (got {amount!r})")

        routes = event_type in ALLOCATION_ROUTED_EVENTS

        event = PostingEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
            facility_id=facility_id,
            event_type=event_type,
            amount=amount,
            currency=currency,
            p2_packet_id=p2_packet_id,
            routes_allocation_question_to_p4=routes,
            memo=memo,
        )

        # Structural check: the event we're about to post/route must not
        # carry anything resembling an allocation computation.
        assert_allocation_untouched(
            {"event_type": event.event_type.value, "amount": event.amount}
        )

        self._core_banking.post_event(event)
        self._posted_events.append(event)

        if routes:
            question = AllocationQuestion(
                source_event_id=event.event_id,
                facility_id=facility_id,
                event_type=event_type,
                amount=amount,
                currency=currency,
            )
            self._routed_questions.append(question)

        return event

    def posted_events(self) -> List[PostingEvent]:
        return list(self._posted_events)

    def routed_allocation_questions(self) -> List[AllocationQuestion]:
        """P4's inbox, conceptually. P3 has no visibility into what P4
        does with these — that's the whole point of the micro/macro cut."""
        return list(self._routed_questions)
