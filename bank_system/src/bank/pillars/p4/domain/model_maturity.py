"""Model Maturity Stage - Pillar 4's two approval duties (claude.md §4.4, §13).

Pillar 4 owns two explicit approvals (claude.md §4.4, §8 parameterised by
Model Maturity Stage):
  - SANDBOX graduation sign-off: a graduation criterion from SANDBOX to
    PRODUCTION-readiness (P4 governance sign-off required).
  - PRODUCTION graduation: a SEPARATE, explicit, per-model P4 approval act with
    Orchestrator notification - NEVER automatic on elapsed time or data.

Consumption honours the model-stage stamp (model_maturity_stage): DESIGN
records carry NO live-decision authority; SANDBOX records are consumable only
under a mandatory human-gate; PRODUCTION under the standard path.

Graduation criteria numbers are PENDING (PENDING_MODEL_MATURITY_CRITERIA).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ModelStage(str, Enum):
    DESIGN = "DESIGN"
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"


class ModelMaturityApprovalError(Exception):
    pass


@dataclass
class ModelMaturityRecord:
    """Per-model maturity state and approval history."""

    model_id: str
    stage: ModelStage = ModelStage.DESIGN
    approvals: list = field(default_factory=list)

    def approve_sandbox_graduation(self, approved_by: str, governance_ref: str):
        """P4 governance sign-off required to graduate DESIGN -> SANDBOX-capable.

        It is a graduation CRITERION (claude.md §4.4) - without this approval
        the model may not be treated as SANDBOX consumable.
        """
        if not approved_by:
            raise ModelMaturityApprovalError("SANDBOX graduation requires a "
                                             "Pillar 4 governance approver")
        self.stage = ModelStage.SANDBOX
        self.approvals.append(
            {
                "event": "sandbox_graduation",
                "approved_by": approved_by,
                "governance_ref": governance_ref,
                "timestamp": _utcnow(),
            }
        )

    def approve_production_graduation(self, approved_by: str, governance_ref: str):
        """SEPARATE, explicit, per-model P4 approval + Orchestrator notification.

        Never automatic on elapsed time or accumulated data (claude.md §4.4).
        """
        if self.stage not in (ModelStage.SANDBOX,):
            # Must have passed SANDBOX first. DESIGN cannot skip to PRODUCTION.
            raise ModelMaturityApprovalError(
                f"Cannot graduate model {self.model_id} from {self.stage.value} "
                "directly to PRODUCTION; SANDBOX graduation is required first."
            )
        if not approved_by:
            raise ModelMaturityApprovalError("PRODUCTION graduation requires a "
                                             "Pillar 4 approval act")
        self.stage = ModelStage.PRODUCTION
        self.approvals.append(
            {
                "event": "production_graduation",
                "approved_by": approved_by,
                "governance_ref": governance_ref,
                "orchestrator_notified": True,
                "timestamp": _utcnow(),
            }
        )
