"""
I/O schemas.

`BorrowerApplication` is the single input to the engine — it deliberately
mirrors the P1->P2 standardized feature store (Canon §3) plus the minimum
OCR schema (Spec §12.1). All financial fields are Optional: Pillar 2 must
never refuse to score for missing data, only apply a Margin of Conservatism
(Canon §2.6.1).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .enums import (
    CollateralClass, CollateralTrack, DecisioningZone, FactorCategory,
    IFRS9Stage, MaturityRegime, ModelMaturityStage, ModelTier, OperatingModel,
    PacketStatus, Product, Segment,
)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
class FinancialStatement(BaseModel):
    """Minimum financial schema after OCR (Spec §12.1). All fields optional."""
    revenue: Optional[float] = None
    cost_of_sales: Optional[float] = None
    operating_expenses: Optional[float] = None
    net_profit: Optional[float] = None
    period_end: Optional[date] = None
    total_assets: Optional[float] = None
    current_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    current_liabilities: Optional[float] = None
    equity: Optional[float] = None
    prior_period_revenue: Optional[float] = None


class CashFlowData(BaseModel):
    """Bank-feed / POS derived series (Data Matrix L-001..L-006)."""
    daily_net_cashflow: Optional[list[float]] = None   # for volatility (FE-04)
    avg_daily_inflow: Optional[float] = None
    debt_service_obligation: Optional[float] = None    # for DSCR (FE-05)
    receivable_days: Optional[float] = None
    payable_days: Optional[float] = None
    inventory_days: Optional[float] = None
    bounced_items_count: Optional[int] = None
    months_of_history: Optional[float] = None


class BusinessProfile(BaseModel):
    """Data Matrix B-001..B-005."""
    top5_customer_share: Optional[float] = None
    single_supplier_share: Optional[float] = None
    registration_date: Optional[date] = None
    sector_code: Optional[str] = None
    geography_code: Optional[str] = None
    legal_form: Optional[str] = None


class ManagementProfile(BaseModel):
    """Data Matrix M-001..M-004."""
    owner_experience_years: Optional[float] = None
    prior_default_history: Optional[bool] = None
    has_governance_plan: Optional[bool] = None
    account_conduct_score: Optional[float] = None   # 0 (poor) - 1 (excellent)


class AlternativeData(BaseModel):
    """Data Matrix A-001..A-004."""
    utility_payment_regularity: Optional[float] = None   # 0-1
    telco_regularity: Optional[float] = None             # 0-1
    ecommerce_reputation_score: Optional[float] = None   # 0-1
    supply_chain_centrality: Optional[float] = None      # 0-1, Tier-3 advisory only


class CollateralOffer(BaseModel):
    """
    A single pledged collateral item. Pillar 2 never values raw assets and
    never touches Pillar 5 — `p4_admitted_value` is the only value P2 may
    consume (Canon §2.12, firewall intact).
    """
    collateral_class: CollateralClass
    track: CollateralTrack
    p4_admitted_value: float = Field(ge=0)


class FacilityRequest(BaseModel):
    product: Product
    requested_amount: float = Field(gt=0)
    drawn_amount: Optional[float] = None
    undrawn_amount: Optional[float] = None
    tenor_months: Optional[int] = None
    recourse: bool = True   # for supply-chain finance


class BorrowerApplication(BaseModel):
    """Top-level input to the engine (one per scoring run)."""
    application_id: str
    segment: Segment
    operating_model: OperatingModel
    facility: FacilityRequest

    maturity_regime: Optional[MaturityRegime] = None  # inferred from rails if absent
    model_maturity_stage: ModelMaturityStage = ModelMaturityStage.DESIGN

    financials: FinancialStatement = Field(default_factory=FinancialStatement)
    cash_flow: CashFlowData = Field(default_factory=CashFlowData)
    business: BusinessProfile = Field(default_factory=BusinessProfile)
    management: ManagementProfile = Field(default_factory=ManagementProfile)
    alternative: AlternativeData = Field(default_factory=AlternativeData)

    collateral: list[CollateralOffer] = Field(default_factory=list)

    rails_connected: list[str] = Field(default_factory=list)  # drives maturity regime + nudge
    policy_exception_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _infer_maturity_regime(self):
        if self.maturity_regime is None:
            n = len(self.rails_connected)
            self.maturity_regime = (
                MaturityRegime.HIGH if n >= 6 else
                MaturityRegime.INTERMEDIATE if n >= 2 else
                MaturityRegime.LOW
            )
        return self


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
class DataQualityResult(BaseModel):
    completeness: float
    consistency: float
    recency: float
    dqs: float
    is_thin_file: bool
    moc_pd_uplift: float
    moc_lgd_uplift: float


class CategoryScore(BaseModel):
    category: FactorCategory
    raw_score: float = Field(ge=0, le=1)   # 0 = safest, 1 = riskiest
    weight: float


class RatingResult(BaseModel):
    category_scores: list[CategoryScore]
    sector_geo_adjustment: float
    composite_risk_score: float
    brr: int
    tier_used: ModelTier
    thin_file_capped: bool
    pd_grid_version: str
    pd_point_estimate: float
    pd_range: tuple[float, Optional[float]]
    pd_with_moc: float


class CreditRiskResult(BaseModel):
    ead: float
    lgd: float
    lgd_with_moc: float
    expected_loss: float
    el_vs_budgeted_loss: str  # "within" | "above"
    pooled_guarantee_level: Optional[float] = None


class PricingResult(BaseModel):
    base_rate_bps: float
    risk_premium_bps: float
    all_in_rate_bps: float


class OutputPacket(BaseModel):
    """P2 -> P3 handoff packet (Canon §2.7 V3.0 addition, §3 P2->P3)."""
    application_id: str
    status: PacketStatus
    model_maturity_stage: ModelMaturityStage
    pd_grid_version: str
    collateral_track: CollateralTrack
    brr: int
    pd: float
    lgd: float
    ead: float
    expected_loss: float
    pricing: PricingResult
    zone: DecisioningZone
    requires_officer_confirmation: bool


class ScoringResult(BaseModel):
    application_id: str
    segment: Segment
    maturity_regime: MaturityRegime
    data_quality: DataQualityResult
    rating: RatingResult
    credit_risk: CreditRiskResult
    pricing: PricingResult
    zone: DecisioningZone
    packet: OutputPacket


class CASSFeedPacket(BaseModel):
    """Canon §2.13 — CASS data feed to P4's ABSF engine."""
    application_id: str
    brr: int
    pd_pit_adjusted: float
    ifrs9_stage: IFRS9Stage
    cash_flow_deterioration_indicator: float
    expected_loss: float


class EWSResult(BaseModel):
    """Canon §2.15 — Early-Warning Signal, distinct from CASS."""
    application_id: str
    triggered: bool
    brr_at_origination: int
    brr_current: int
    deterioration_notches: int
    routed_to_officer: bool
    triggers_p3_action: bool = False  # Canon-mandated: always False


class OverrideRecord(BaseModel):
    """Learning-oriented Override Record (Canon §2.11.2, ratified P-3)."""
    application_id: str
    override_type: str
    model_output_before: str
    officer_output_after: str
    direction: str                       # "UPGRADE" | "DOWNGRADE"
    factor_category_overridden: FactorCategory
    reason_code: str
    narrative: str
    authority_level: str
    approver: Optional[str] = None
    approver_decision: Optional[str] = None
    outcome_at_maturity: Optional[str] = None
    vindicated: Optional[str] = None
    model_improvement_disposition: Optional[str] = None
    disposition_notes: Optional[str] = None
