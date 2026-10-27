"""Guarantee-Pool Custody & Adequacy (claude.md §8.12, §5.4).

Why it exists: to maintain the [G] model's core "isomorphism" - a macro
accounting duty analogous to a conventional bank's aggregate deposit/loan books.

Responsibilities:
  - hold pool composition (Tier A + Tier B aggregate);
  - receive Pillar 2's REQUIRED level computation;
  - monitor adequacy continuously (received vs required);
  - manage inflow (admitted pledges: P5 submissions vs admissibility POLICY) and
    outflow (pledge release);
  - enforce guarantee-pool concentration;
  - maintain the aggregate given/received guarantee books that back the leverage
    ratio.

KEY RULE: Pillar 4 NEVER re-sizes the required level - it only compares against
what Pillar 2 gives it (claude.md §5.2, §8.12).

Admissibility gate (claude.md §5.4): P4 reviews P5 submissions against its own
POLICY (eligible types, haircuts, concentration) and admits/rejects at POLICY
level - it does NOT enter the individual case (P2 confirms that + recalc LGD/EL).
Stage 1 is Track 1 (Classical) collateral only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.guarantee_pool import (
    GuaranteePool,
    PoolAdequacyStatus,
    PledgePosition,
    Pillar5AdmittedCollateral,
    ConcentrationMetrics as PoolConcentrationMetrics,
)
from ..domain.tiers import TierPosition
from ..domain.buffer_account import BufferAccount
from ..domain.pending import (
    PENDING_CONCENTRATION_LIMITS,
    PENDING_ESCROW_SPV,
    PENDING_THREE_TRACK_HAIRCUT,
    PendingNotResolvedError,
)
from ..contracts.p2_inbound import RequiredGuaranteeLevel
from ..contracts.p5_inbound import PledgeSubmission, SubmissionDisposition, AdmittedSubmitResult
from ..contracts.p2_outbound import AdmissibilityPolicy


class AdmissibilityPolicyError(Exception):
    pass


class AdmissibilityPolicyService:
    """Holds and applies Pillar 4's collateral admissibility POLICY."""

    def __init__(self, policy: AdmissibilityPolicy | None = None):
        self._policy = policy
        self._rejections: list[dict] = []

    def current_policy(self) -> AdmissibilityPolicy | None:
        return self._policy

    def set_policy(self, policy: AdmissibilityPolicy):
        # A policy, not a case decision - applies prospectively to future cases.
        self._policy = policy

    def can_admit(self, submission: PledgeSubmission) -> tuple[bool, str]:
        """Policy-level admissibility check (eligible type/haircut).

        Returns (admitted, reason). Does NOT enter the individual case; that is
        Pillar 2's confirmation, which recalculates LGD/EL (claude.md §5.4).
        """
        if self._policy is None:
            raise AdmissibilityPolicyError(
                "No admissibility policy configured: Pillar 4 has not set its "
                "collateral admissibility policy (types/haircuts/limits)."
            )
        if submission.asset_class not in self._policy.eligible_asset_types:
            return False, f"asset class {submission.asset_class!r} not eligible"
        haircut = self._policy.haircuts_by_asset_class.get(submission.asset_class)
        if haircut is None and self._policy.haircuts_by_asset_class:
            return False, f"no haircut policy for asset class {submission.asset_class!r}"
        # Escrow-vs-SPV custody framework is PENDING before pledge intake.
        # We surface the stop as an admission blocker rather than silently
        # choosing a custody model (claude.md §17 PENDING_ESCROW_SPV).
        if not self._custody_framework_resolved():
            raise PendingNotResolvedError(PENDING_ESCROW_SPV)
        # Track-2/3 haircut governance not applicable in Stage 1 (Track 1 only).
        if submission.asset_class in getattr(self._policy, "track2_3_only", ()):
            raise PendingNotResolvedError(PENDING_THREE_TRACK_HAIRCUT)
        return True, "eligible"

    def _custody_framework_resolved(self) -> bool:
        # The escrow-vs-SPV decision is PENDING until governance resolves it.
        # Until then, no pledge may be admitted (inflow blocked per claude.md §17
        # PENDING_ESCROW_SPV "before pledge intake").
        return False

    def record_rejection(self, submission_ref: str, reason: str):
        self._rejections.append({"submission_ref": submission_ref, "reason": reason})


class GuaranteePoolCustody:
    """Holds the pool and monitors adequacy against P2's required level."""

    def __init__(
        self,
        pool: GuaranteePool | None = None,
        admissibility: AdmissibilityPolicyService | None = None,
        event_sink=None,
    ):
        self.pool = pool or GuaranteePool()
        self.admissibility = admissibility or AdmissibilityPolicyService()
        self._event_sink = event_sink or (lambda ev: None)
        self._given_book_adjustments: list[float] = []
        self._outflow_events: list[dict] = []

    def _emit(self, ev):
        self._event_sink(ev)

    # ---- receive required level (never re-size) ----------------------------
    def receive_required_level(self, req: RequiredGuaranteeLevel):
        """Record Pillar 2's required pooled-guarantee level.

        Pillar 4 NEVER re-sizes the requirement; it only compares against it.
        A required-level revision is a NEW dated output, not an edit.
        """
        self.pool.required_level = req.required_amount
        self.pool.required_level_revision = req.revision_ref

    # ---- inflow: P5 submission vs admissibility policy ---------------------
    def admit_submission(self, submission: PledgeSubmission) -> AdmittedSubmitResult:
        admitted, reason = self.admissibility.can_admit(submission)
        if not admitted:
            self.admissibility.record_rejection(submission.submission_ref, reason)
            return AdmittedSubmitResult(
                submission_ref=submission.submission_ref,
                disposition=SubmissionDisposition.REJECTED,
                reason=reason,
                policy_version=self._policy_version(),
            )
        # Admit the pledge INTO THE POOL (Tier A / Tier B position).
        position = PledgePosition(
            pledge_ref=submission.submission_ref,
            tier=submission.tier,
            amount=submission.amount,
            pledge_term=0.0,  # PENDING_PLEDGE_TERM - length unresolved
        )
        self.pool.add_position(position)
        # received guarantee book reflects the admitted pledge.
        self.pool.received_guarantee_book += submission.amount
        self._emit(self._intra("pool_adequacy.shortfall_detected", {}))
        return AdmittedSubmitResult(
            submission_ref=submission.submission_ref,
            disposition=SubmissionDisposition.ADMITTED,
            reason="admitted into pooled guarantee (policy level)",
            policy_version=self._policy_version(),
        )

    def _policy_version(self) -> str | None:
        p = self.admissibility.current_policy()
        return p.policy_version if p else None

    # ---- the aggregate given/received books (macro accounting) -------------
    def record_given_book(self, amount: float):
        """Record guarantees GRANTED (to the funded book) at portfolio level."""
        self.pool.given_guarantee_book += amount
        self._given_book_adjustments.append(amount)

    def reduce_received_book(self, amount: float):
        self.pool.received_guarantee_book = max(
            0.0, self.pool.received_guarantee_book - amount
        )

    # ---- adequacy monitor (continuous received vs required) ----------------
    def adequacy(self) -> PoolAdequacyStatus:
        return self.pool.adequacy_status()

    def adequacy_metrics(self) -> dict:
        received = self.pool.received_received_value()
        required = self.pool.required_level
        return {
            "received": received,
            "required": required,
            "status": self.adequacy().value,
            "shortfall_amount": max(0.0, required - received),
        }

    def constrains_origination(self) -> bool:
        """Shortfall -> origination paced/held (claude.md §5.4/§5.3)."""
        return self.adequacy() == PoolAdequacyStatus.SHORTFALL

    def _intra(self, name, payload):
        from ..domain.events import IntraP4Event, IntraP4EventType
        if name == "pool_adequacy.shortfall_detected":
            if self.constrains_origination():
                return IntraP4Event(IntraP4EventType.POOL_ADEQUACY_SHORTFALL, payload)
        return None
