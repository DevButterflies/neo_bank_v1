"""
Pillar 3 exception hierarchy.

The governance-boundary exceptions in this module are not generic error
handling — they are the enforcement mechanism for structural rules that
the Canon says "may not be varied by operational parameter" (Canon §4,
"Standing rule — no allocation logic in Pillar 3"). Where the documents
say a thing must not happen, the corresponding code path raises one of
these instead of silently doing the wrong thing or silently doing
nothing.
"""


class Pillar3Error(Exception):
    """Base class for all Pillar 3 domain errors."""


# ---------------------------------------------------------------------------
# Lifecycle / state machine
# ---------------------------------------------------------------------------

class InvalidStateTransitionError(Pillar3Error):
    """Raised when a transition is attempted that the state machine does
    not permit (Spec §2)."""


class UnconfirmedPacketError(Pillar3Error):
    """Raised when P3 is asked to act on a P2 packet that is not
    confirmed — Canon §8.1: 'Pillar 3 shall not initiate origination on a
    provisional or conditional packet until the credit-officer
    counter-signature is recorded and the packet status is confirmed.'"""


class AutoOriginationNotPermittedError(Pillar3Error):
    """Raised when auto-origination (conditional auto-approve without
    officer sign-off) is attempted outside PRODUCTION, or in PRODUCTION
    without explicit P4 approval — Build Handoff §5, 'Binding gate — do
    not build auto-origination for sandbox.'"""


class VetoFrozenError(Pillar3Error):
    """Raised when an action is attempted on a facility/portfolio under
    an active, non-overridable P4 veto — Interface Contract Sheet §3."""


class RepaymentExceedsOutstandingError(Pillar3Error):
    """Raised when a repayment would push the cumulative principal repaid
    above the cumulative principal disbursed for that facility.

    A facility's outstanding balance can never go negative: core banking
    has no such state, and a negative balance silently inflates the loan
    ledger of every account that reads it (see ``docs/CHANGELOG_bilan.md``, B5).
    """


class WriteOffExceedsOutstandingError(Pillar3Error):
    """Raised when a write-off would exceed the principal still outstanding
    for that facility.

    Writing off more than was ever lent would manufacture loss on the
    passif side without a matching debit, breaking the balance sheet; a
    write-off larger than the outstanding balance is always a caller bug
    or a replayed packet (see ``bug_bilan_fix_round_2.md``, R1).
    """


# ---------------------------------------------------------------------------
# Governance / structural boundary violations
#
# These are deliberately NOT subclasses of a generic ValidationError: they
# represent an attempt to make Pillar 3 do something the Canon explicitly
# forbids it from doing, as opposed to a caller passing bad data.
# ---------------------------------------------------------------------------

class GovernanceBoundaryError(Pillar3Error):
    """Base class for attempts to cross a structural P3/P4/P2/P5 boundary."""


class AllocationLogicForbiddenError(GovernanceBoundaryError):
    """Raised if any code path attempts to compute a cross-tier
    allocation, burden-sharing, Tier B-Fees, ABSF, or loss-repartition
    result inside Pillar 3. Canon §4: 'Pillar 3 shall not contain,
    compute, or encode any cross-tier allocation ... logic. These are
    exclusively Pillar 4.'"""


class PendingGovernanceItemError(GovernanceBoundaryError):
    """Raised if code attempts to resolve a strict-PENDING item instead
    of stubbing it and routing to the owning register. Build Handoff §6.2:
    'A PENDING gap filled by an engineering assumption is a governance
    breach, not a shortcut.'"""


class AdmissibilityNotConfirmedError(GovernanceBoundaryError):
    """Raised when a Pillar 5 object is recorded without confirmed
    admissibility via the P4→P2 chain — Canon §8.5."""


class UnauthorisedDecisionError(GovernanceBoundaryError):
    """Raised if P3 is asked to take an independent credit, prudential,
    restructuring, or recovery decision instead of executing a confirmed,
    human-authorised P2 packet — Canon §8.6."""


class OutOfPostingSetError(GovernanceBoundaryError):
    """Raised if a posting is attempted for an event type outside the
    canonical per-loan posting set (Spec §3 / Build Handoff §4)."""


class ReconciliationBreachError(Pillar3Error):
    """Raised (as an alertable condition, not silently swallowed) when
    P3 event-log totals diverge from core banking beyond the P4-defined
    tolerance — Canon §8.3."""
