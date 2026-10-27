"""
Tier 1 — expert & statistical backbone (Canon §2.3).

"Tier 1 is the expert statistical backbone and must always produce a valid
BRR and PD even when data are sparse." This module is the one guaranteed
scorer in the engine: a transparent, monotonic scorecard over the six
factor categories, weighted per segment (Spec §4.3).

Tier 2 (gradient-boosted trees, champion for Small/Medium once validated)
and Tier 3 (deep/graph challenger, advisory-only per Canon §2.3) are
pluggable extension points — see `Pillar2Engine(tier2_scorer=...)` in
engine.py. This module never fabricates their output; where no Tier-2/3
scorer is supplied, Tier 1 remains the champion, which is always Canon-valid.
"""

from __future__ import annotations

from . import constants as c
from . import features as feat
from .enums import FactorCategory, ModelTier, Segment
from .overlay import geography_risk_score, sector_risk_score
from .schemas import BorrowerApplication, CategoryScore, RatingResult
from .dqs import DataQualityResult


def _bounded(x: float | None, lo: float, hi: float, default: float) -> float:
    """
    Map a raw value to a [0,1] risk contribution, linearly, clipped.
    `lo` is the value at which risk = 0 (the safe end); `hi` is the value at
    which risk = 1 (the risky end) — `lo` need not be numerically smaller
    than `hi`. Missing input (`x is None`) returns `default`, a conservative
    mid-to-high risk score consistent with the Margin of Conservatism
    principle: missing information is never treated as favourable.
    """
    if x is None:
        return default
    if hi == lo:
        return default
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _score_category_1(app: BorrowerApplication) -> float:
    """Financial Performance & Strength."""
    nm = feat.net_margin(app)
    lev = feat.leverage_ratio(app)
    growth = feat.revenue_growth_yoy(app)
    turn = feat.asset_turnover(app)

    s_margin = _bounded(nm.value, lo=0.30, hi=-0.10, default=0.65)
    s_lev = _bounded(lev.value, lo=0.0, hi=4.0, default=0.70)
    s_growth = _bounded(growth.value, lo=0.40, hi=-0.20, default=0.55)
    s_turn = _bounded(turn.value, lo=3.0, hi=0.2, default=0.55)
    return round((s_margin + s_lev + s_growth + s_turn) / 4, 4)


def _score_category_2(app: BorrowerApplication) -> float:
    """Liquidity & Cash Flow."""
    vol = feat.cashflow_volatility(app)
    d = feat.dscr(app)
    wc = feat.wc_days(app)
    bounced = feat.bounced_items(app)

    s_vol = _bounded(vol.value, lo=0.05, hi=0.60, default=0.60)
    s_dscr = _bounded(d.value, lo=2.5, hi=0.8, default=0.65)
    s_wc = _bounded(wc.value, lo=0, hi=120, default=0.55)
    s_bounced = _bounded(bounced.value, lo=0, hi=5, default=0.60)
    return round((s_vol + s_dscr + s_wc + s_bounced) / 4, 4)


def _score_category_3(app: BorrowerApplication) -> float:
    """Business Profile & Market Position."""
    hhi = feat.customer_hhi(app)
    age = feat.business_age_years(app)
    supplier_share = app.business.single_supplier_share

    s_hhi = _bounded(hhi.value, lo=0.10, hi=0.80, default=0.55)
    s_age = _bounded(age.value, lo=10.0, hi=0.5, default=0.60)
    s_supplier = _bounded(supplier_share, lo=0.10, hi=0.90, default=0.50)
    return round((s_hhi + s_age + s_supplier) / 3, 4)


def _score_category_4(app: BorrowerApplication) -> float:
    """Management & Ownership Quality — dominant category for Micro."""
    m = app.management
    exp = feat.owner_experience(app)
    conduct = feat.account_conduct(app)

    s_exp = _bounded(exp.value, lo=15.0, hi=0.0, default=0.60)
    s_conduct = _bounded(conduct.value, lo=1.0, hi=0.0, default=0.60)
    s_default_hist = 0.95 if m.prior_default_history else 0.10
    s_governance = 0.20 if m.has_governance_plan else 0.55
    return round((s_exp + s_conduct + s_default_hist + s_governance) / 4, 4)


def _score_category_5(app: BorrowerApplication) -> float:
    """Industry & Macro Environment — blended sector/geography overlay."""
    b = app.business
    return round(0.5 * sector_risk_score(b.sector_code) + 0.5 * geography_risk_score(b.geography_code), 4)


def _score_category_6(dqs: DataQualityResult) -> float:
    """Data Quality & Digital Maturity — inverse of the DQS."""
    return round(1 - dqs.dqs, 4)


_SCORERS = {
    FactorCategory.FINANCIAL_PERFORMANCE: _score_category_1,
    FactorCategory.LIQUIDITY_CASH_FLOW: _score_category_2,
    FactorCategory.BUSINESS_PROFILE: _score_category_3,
    FactorCategory.MANAGEMENT_OWNERSHIP: _score_category_4,
}


def score_brr(app: BorrowerApplication, dqs: DataQualityResult) -> RatingResult:
    weights = c.CATEGORY_WEIGHTS[app.segment]

    category_scores: list[CategoryScore] = []
    for cat, scorer in _SCORERS.items():
        raw = scorer(app)
        category_scores.append(CategoryScore(category=cat, raw_score=raw, weight=weights[cat]))
    cat5_raw = _score_category_5(app)
    category_scores.append(CategoryScore(category=FactorCategory.INDUSTRY_MACRO, raw_score=cat5_raw,
                                          weight=weights[FactorCategory.INDUSTRY_MACRO]))
    cat6_raw = _score_category_6(dqs)
    category_scores.append(CategoryScore(category=FactorCategory.DATA_QUALITY_DIGITAL_MATURITY, raw_score=cat6_raw,
                                          weight=weights[FactorCategory.DATA_QUALITY_DIGITAL_MATURITY]))

    composite = sum(cs.raw_score * cs.weight for cs in category_scores)

    # informational only (Spec §9.1 concentration input to P4) — NOT re-applied
    # to the BRR a second time, since category 5 already carries sector/geo risk.
    from .overlay import overlay_adjustment
    sector_geo_info = overlay_adjustment(app.business.sector_code, app.business.geography_code)

    brr_float = 1 + composite * 9
    brr = max(1, min(10, round(brr_float)))

    thin_file_capped = False
    if dqs.is_thin_file:
        capped = max(c.THIN_FILE_MIN_BRR, min(c.THIN_FILE_MAX_BRR, brr))
        thin_file_capped = capped != brr
        brr = capped

    pd_low, pd_high = c.BRR_PD_GRID[brr]
    pd_point = c.BRR_10_PD_POINT_ESTIMATE if pd_high is None else (pd_low + pd_high) / 2

    from .dqs import apply_moc_to_pd
    pd_with_moc = apply_moc_to_pd(pd_point, dqs.moc_pd_uplift)

    return RatingResult(
        category_scores=category_scores,
        sector_geo_adjustment=sector_geo_info,
        composite_risk_score=round(composite, 4),
        brr=brr,
        tier_used=ModelTier.TIER_1,
        thin_file_capped=thin_file_capped,
        pd_grid_version=c.BRR_PD_GRID_VERSION,
        pd_point_estimate=round(pd_point, 6),
        pd_range=(pd_low, pd_high),
        pd_with_moc=round(pd_with_moc, 6),
    )
