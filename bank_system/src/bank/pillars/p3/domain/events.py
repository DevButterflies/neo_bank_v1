"""
Event models: lifecycle events, per-loan postings, and the audit record
schema those events must produce.

Spec §8 lists the exact fields an audit record must carry. This module
defines a single AuditRecord dataclass with those fields as required
(not optional) attributes, so a record missing a field is a construction
error, not a silent gap discovered later by a supervisory reviewer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    LoanState,
    MaturityStage,
    PostingEventType,
    VetoScope,
)


@dataclass(frozen=True)
class PostingEvent:
    """A single per-loan posting event captured by Pillar 3 and posted to
    core banking (Spec §3 / Build Handoff §4)."""

    event_id: str
    facility_id: str
    event_type: PostingEventType
    amount: float
    currency: str
    p2_packet_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    routes_allocation_question_to_p4: bool = False
    memo: Optional[str] = None


@dataclass(frozen=True)
class AuditRecord:
    """Append-only audit record — Spec §8 mandatory field list.

    Every field below is named directly in Spec §8 ('Each event record
    contains: ...'). Do not make any of these Optional without checking
    the Spec first — an Optional field here is a silent gap in the audit
    trail.
    """

    record_id: str
    facility_id: str
    event_type: str                      # canonical event list (lifecycle or posting)
    timestamp: datetime
    actor_reference: str                 # 'SYSTEM' or human officer ID
    p2_packet_version: str
    maturity_stage: MaturityStage
    brr_pd_grid_version: str
    collateral_track: Optional[CollateralTrack]
    p4_veto_status: str                  # e.g. "TRACK_1_PORTFOLIO:CLEAR"
    posting_routing_flag: Optional[str]  # which posting this event produced, if any
    core_banking_confirmed: bool
    resulting_state: LoanState
    collateral_reference: Optional[str] = None
    guarantee_linkage: Optional[str] = None  # [G] given/received guarantee ref
