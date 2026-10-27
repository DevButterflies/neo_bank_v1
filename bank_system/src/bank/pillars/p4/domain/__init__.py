"""Domain model for Pillar 4.

The corpus specifies behavior, account structure, and type distinctions - not
literal schemas (claude.md §12 marks the data model as synthesized). These
modules capture the domain vocabulary and the hard invariants:

- `tiers`              : Orchestrator-sourced six-position capital/guarantee stack
- `buffer_account`    : BufferAccount parent + EL Pool / ULA / LR / RP Pool
- `guarantee_pool`    : GuaranteePool, PledgePosition, Pillar5AdmittedCollateral,
                        aggregate books (Two-Guarantee-Layer Rule)
- `events`            : typed Pillar 3 + intra-P4 events, Four-Event Discipline
- `veto`              : Track 1 / Track 2 veto state and freeze machinery
- `mode_state`        : Conventional / Adaptive operating-mode state (SI-1)
- `model_maturity`    : Model Maturity Stage and Pillar 4's sign-off duties
- `pending`           : PENDING register (do-not-resolve-in-code named stops)
"""

from . import (  # noqa: F401
    buffer_account,
    events,
    guarantee_pool,
    model_maturity,
    mode_state,
    pending,
    tiers,
    veto,
)
