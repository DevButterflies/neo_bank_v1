"""Inbound/outbound contracts (DTOs) for Pillar 4.

Per claude.md §16 `contracts/` layer. These are LOGICAL-field DTOs; wire
formats for the PENDING items (CASS feed methodology, IFRS9 staging signal
format) are explicitly not resolved here - they are surfaced as named stops via
the PENDING register.

The `p2_inbound` module carries the risk outputs and the required
pooled-guarantee level. The required pooled-guarantee level transport is
BLOCKED by PENDING_TWO_GUARANTEE_LAYER_CONTRACT; the value is carried as a
logical field whose transport mechanism is unresolved.
"""

from .p2_inbound import (  # noqa: F401
    Pillar2RiskPacket,
    StagingSignal,
    RequiredGuaranteeLevel,
    CASSFeedRecord,
)
from .p3_inbound import (  # noqa: F401
    Pillar3Event,
    Pillar3EventType,
)
from .p5_inbound import (  # noqa: F401
    PledgeSubmission,
    SubmissionDisposition,
)
from .p2_outbound import (  # noqa: F401
    VetoConsultation,
    AdmissibilityPolicy,
    PoolAdequacyNotice,
)

__all__ = [
    "Pillar2RiskPacket",
    "StagingSignal",
    "RequiredGuaranteeLevel",
    "CASSFeedRecord",
    "Pillar3Event",
    "Pillar3EventType",
    "PledgeSubmission",
    "SubmissionDisposition",
    "VetoConsultation",
    "AdmissibilityPolicy",
    "PoolAdequacyNotice",
]
