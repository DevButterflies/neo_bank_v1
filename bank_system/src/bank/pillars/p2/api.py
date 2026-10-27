"""
FastAPI layer — exposes the Pillar 2 engine as HTTP APIs.

Run with:  uvicorn pillar2.api:app --reload
Docs at:   http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from bank.core.openapi_tags import OPENAPI_TAGS

from . import constants as c
from .ead import ProductNotInSandboxScope
from .engine import Pillar2Engine
from .enums import FactorCategory
from .lgd import TrackNotAvailableUnderModel, compute_pooled_guarantee_level
from .monitoring import build_cass_packet, evaluate_ews
from .override import close_override, open_override
from .schemas import (
    BorrowerApplication, CASSFeedPacket, EWSResult, OverrideRecord, ScoringResult,
)


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class BrrPdGridOut(_Out):
    version: str
    grid: dict


class PooledGuaranteeLevelOut(_Out):
    pooled_guarantee_level: float


app = FastAPI(
    title="Pillar 2 — Credit Scoring & Risk Rating Engine",
    version="1.0.0",
    description=(
        "Conforms to Pillar 2 Canon V4.1 (ratified OA-2.0) and the Scoring & "
        "Rating Model Spec v1.0. Stateless: every request is scored in "
        "process; nothing is persisted here."
    ),
    openapi_tags=OPENAPI_TAGS,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = Pillar2Engine()


@app.get("/health", tags=["health"], summary="Liveness + grid version")
def health() -> dict:
    return {"status": "ok", "brr_pd_grid_version": c.BRR_PD_GRID_VERSION}


@app.post(
    "/v1/score",
    response_model=ScoringResult,
    tags=["pillar2"],
    summary="Score one application",
    description=(
        "The full Pillar 2 pipeline for one application (Spec §2): factor "
        "scoring, BRR assignment via the versioned BRR→PD grid, PD/LGD/EAD/EL, "
        "collateral-track selection, and the output packet Pillar 3 records "
        "verbatim. 422 when the product is outside sandbox scope or the "
        "selected track is unavailable under the model."
    ),
    responses={422: {"description": "Product out of sandbox scope or track unavailable"}},
)
def score_application(application: BorrowerApplication) -> ScoringResult:
    try:
        return engine.score(application)
    except (ProductNotInSandboxScope, TrackNotAvailableUnderModel) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get(
    "/v1/brr-pd-grid",
    response_model=BrrPdGridOut,
    tags=["pillar2"],
    summary="Versioned BRR→PD grid",
    description="The versioned BRR→PD grid (Canon §2.5.1, ratified P-2).",
)
def get_brr_pd_grid() -> dict:
    return {"version": c.BRR_PD_GRID_VERSION, "grid": c.BRR_PD_GRID}


@app.get(
    "/v1/category-weights/{segment}",
    tags=["pillar2"],
    summary="Category weights for a segment",
    description="Scoring category weights for one borrower segment (Spec §4.3).",
    responses={404: {"description": "Unknown segment"}},
)
def get_category_weights(segment: str) -> dict:
    from .enums import Segment
    try:
        seg = Segment(segment.upper())
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown segment: {segment}")
    return {k.name: v for k, v in c.CATEGORY_WEIGHTS[seg].items()}


@app.post(
    "/v1/ews",
    response_model=EWSResult,
    tags=["pillar2"],
    summary="Early-Warning Signal",
    description="EWS evaluation from a BRR migration (Canon §2.15, ratified P-7).",
)
def ews(application_id: str, brr_at_origination: int, brr_current: int) -> EWSResult:
    return evaluate_ews(application_id, brr_at_origination, brr_current)


@app.post(
    "/v1/cass-feed",
    response_model=CASSFeedPacket,
    tags=["pillar2"],
    summary="CASS feed packet (contract shape)",
    description=(
        "Builds the CIS-1-contract-shaped data packet Pillar 4's future ABSF "
        "engine will consume (Canon §2.13). The full CASS methodology is "
        "PENDING — this is the contract stub, not a live scoring feed."
    ),
)
def cass_feed(
    application_id: str,
    brr: int,
    pd_pit_adjusted: float,
    expected_loss: float,
    days_past_due: int = 0,
    significant_credit_risk_increase: bool = False,
    cash_flow_deterioration_indicator: float = 0.0,
) -> CASSFeedPacket:
    """CASS data feed to Pillar 4's ABSF engine (Canon §2.13)."""
    return build_cass_packet(
        application_id, brr, pd_pit_adjusted, expected_loss,
        days_past_due, significant_credit_risk_increase, cash_flow_deterioration_indicator,
    )


@app.post(
    "/v1/pooled-guarantee-level",
    response_model=PooledGuaranteeLevelOut,
    tags=["pillar2"],
    summary="G-model pooled guarantee level",
    description=(
        "The required pooled-guarantee level under the Guarantee "
        "Intermediation Model (Canon §2.12.2) — computed by Pillar 2, "
        "monitored against guarantees received by Pillar 4."
    ),
)
def pooled_guarantee_level(portfolio_ead: float, portfolio_facility_collateral_value: float) -> dict:
    level = compute_pooled_guarantee_level(portfolio_ead, portfolio_facility_collateral_value)
    return {"pooled_guarantee_level": level}


@app.post(
    "/v1/override/open",
    response_model=OverrideRecord,
    tags=["pillar2"],
    summary="Open an override record",
    description=(
        "Opens a learning-oriented Override Record (Canon §2.11.2, ratified "
        "P-3): an officer's reasoned BRR adjustment, kept as model-"
        "recalibration evidence."
    ),
    responses={422: {"description": "Invalid override parameters"}},
)
def override_open(
    application_id: str,
    override_type: str,
    model_brr_before: int,
    officer_brr_after: int,
    factor_category_overridden: FactorCategory,
    reason_code: str,
    narrative: str,
    authority_level: str,
) -> OverrideRecord:
    """Opens a learning-oriented Override Record (Canon §2.11.2, ratified P-3)."""
    try:
        return open_override(
            application_id, override_type, model_brr_before, officer_brr_after,
            factor_category_overridden, reason_code, narrative, authority_level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post(
    "/v1/override/close",
    response_model=OverrideRecord,
    tags=["pillar2"],
    summary="Close an override record",
    description=(
        "Closes the loop at facility maturity — the evidence-led "
        "recalibration input."
    ),
)
def override_close(
    record: OverrideRecord,
    outcome_at_maturity: str,
    vindicated: str,
    model_improvement_disposition: str,
    disposition_notes: str = "",
) -> OverrideRecord:
    """Closes the loop at facility maturity — the evidence-led recalibration input."""
    return close_override(record, outcome_at_maturity, vindicated, model_improvement_disposition, disposition_notes)
