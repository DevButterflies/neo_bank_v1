"""
Learning-oriented Override Record (Canon §2.11.2, ratified P-3).

"Every override is recorded with: the model output before, the officer
output after, the direction of change, the factor category overridden, a
reason code, and a narrative rationale. At facility maturity the record is
completed with the realised outcome and a model-improvement disposition."
Mirrors Due-Diligence Template §K.
"""

from __future__ import annotations

from .enums import FactorCategory
from .schemas import OverrideRecord

REASON_CODES = (
    "MATERIAL_INFO_NOT_IN_MODEL",
    "DATA_QUALITY_ISSUE",
    "QUALITATIVE_RISK",
    "SECTOR_MACRO_OVERLAY",
    "COLLATERAL_ADJUSTMENT",
    "MODEL_LIMITATION",
    "OTHER",
)

AUTHORITY_LEVELS = ("SENIOR_ANALYST", "CREDIT_MANAGER", "CREDIT_COMMITTEE")


def open_override(
    application_id: str,
    override_type: str,
    model_brr_before: int,
    officer_brr_after: int,
    factor_category_overridden: FactorCategory,
    reason_code: str,
    narrative: str,
    authority_level: str,
) -> OverrideRecord:
    if reason_code not in REASON_CODES:
        raise ValueError(f"reason_code must be one of {REASON_CODES}")
    if authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"authority_level must be one of {AUTHORITY_LEVELS}")

    direction = "DOWNGRADE" if officer_brr_after > model_brr_before else \
        ("UPGRADE" if officer_brr_after < model_brr_before else "UNCHANGED")

    return OverrideRecord(
        application_id=application_id,
        override_type=override_type,
        model_output_before=f"BRR {model_brr_before}",
        officer_output_after=f"BRR {officer_brr_after}",
        direction=direction,
        factor_category_overridden=factor_category_overridden,
        reason_code=reason_code,
        narrative=narrative,
        authority_level=authority_level,
    )


def close_override(
    record: OverrideRecord,
    outcome_at_maturity: str,
    vindicated: str,
    model_improvement_disposition: str,
    disposition_notes: str = "",
) -> OverrideRecord:
    """Completed later, at/after facility maturity — closes the learning loop."""
    data = record.model_dump()
    data.update(
        outcome_at_maturity=outcome_at_maturity,
        vindicated=vindicated,
        model_improvement_disposition=model_improvement_disposition,
        disposition_notes=disposition_notes,
    )
    return OverrideRecord(**data)
