"""Map a P1 candidate onto a Pillar 2 ``BorrowerApplication``.

Two sources:

  * Seed candidates carry the full demo_3 application already serialized on
    the row (``application_json``) — rich financials, cash flow, collateral,
    different rail coverage — so rehydrating reproduces the exact scoring
    inputs that produced each profile's data tier.
  * Candidates entered through the intake form have no rich data feed; a thin
    application is built from the form fields (KYC + mobile-money rails only).
    The thin file forces the same conservative DQS -> MoC -> MANUAL_REVIEW
    path the plan relies on, which fits the always-manual approval gate.
"""

from __future__ import annotations

from datetime import date, timedelta

from bank.pillars.p1.models import Candidate
from bank.pillars.p2.enums import (
    ModelMaturityStage,
    OperatingModel,
    Product,
    Segment,
)
from bank.pillars.p2.schemas import (
    BorrowerApplication,
    BusinessProfile,
    FacilityRequest,
    ManagementProfile,
)

# Display city -> P2 geography code. Unknown cities fall back to MUSCAT (the
# overlay's geography_risk_score defaults gracefully to 0.40 for unknown codes).
_CITY_GEOGRAPHY: dict[str, str] = {
    "muscat": "MUSCAT",
    "dhofar": "DHOFAR",
    "batinah": "AL_BATINAH",
    "al batinah": "AL_BATINAH",
    "nizwa": "AL_DAKHILIYAH",
    "sur": "ASH_SHARQIYAH",
    "salalah": "DHOFAR",
    "sohar": "AL_BATINAH",
}


def geography_code_for(city: str) -> str:
    return _CITY_GEOGRAPHY.get((city or "").strip().lower(), "MUSCAT")


def hydrate_application(row: dict) -> BorrowerApplication:
    """Round-trip a serialized BorrowerApplication stored on the candidate row."""
    return BorrowerApplication.model_validate(row)


def build_application(cand: Candidate, requested_amount: float | None = None) -> BorrowerApplication:
    if cand.application_json:
        return hydrate_application(cand.application_json)
    return build_thin_application(cand, requested_amount=requested_amount)


def build_thin_application(cand: Candidate, requested_amount: float | None = None) -> BorrowerApplication:
    """A thin-file application built from the intake form (no financials, no
    cash flow, no collateral — KYC + mobile money rails only)."""
    requested = requested_amount if requested_amount is not None else cand.requested_amount
    drawn = round(requested * 0.8, 2)
    undrawn = round(requested - drawn, 2)
    experience = max(cand.employment_years or 0.0, 0.1)

    return BorrowerApplication(
        application_id=f"APP-{cand.id}",
        segment=Segment.MICRO,
        operating_model=OperatingModel.GUARANTEE,
        model_maturity_stage=ModelMaturityStage.PRODUCTION,
        facility=FacilityRequest(
            product=Product.WORKING_CAPITAL_LINE,
            requested_amount=requested,
            drawn_amount=drawn,
            undrawn_amount=undrawn,
            tenor_months=cand.requested_tenure_months,
        ),
        business=BusinessProfile(
            sector_code="RETAIL_GENERAL",
            geography_code=geography_code_for(cand.city),
            registration_date=date.today() - timedelta(days=int(experience * 365)),
        ),
        management=ManagementProfile(
            owner_experience_years=experience,
            prior_default_history=False,
            has_governance_plan=False,
        ),
        rails_connected=["kyc", "mobile_money"],
    )