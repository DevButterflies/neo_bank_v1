"""
Data Quality Score (DQS) and Margin of Conservatism (MoC).

DQS is "a formal Pillar 2 output measuring completeness, consistency, and
recency" (Canon Master Lexicon, Spec §7.1). It feeds: factor category 6 of
the BRR, thin-file routing, and MoC sizing.

MoC: "Where data required for a risk estimate is missing or low-quality,
Pillar 2 shall not omit the estimate but shall apply a Margin of
Conservatism ... sized in proportion to the Data Quality Score. The weaker
the data package, the larger the buffer." (Canon §2.6.1, ratified P-1)
"""

from __future__ import annotations

from datetime import date

from . import constants as c
from .features import Feature
from .schemas import BorrowerApplication, DataQualityResult


def _completeness(features: dict[str, Feature]) -> float:
    """Share of expected fields present (D-001)."""
    if not features:
        return 0.0
    present = sum(1 for f in features.values() if not f.missing)
    return present / len(features)


def _consistency(app: BorrowerApplication) -> float:
    """
    Cross-check rules (D-002): e.g. balance-sheet identity roughly holding,
    net profit consistent with revenue - costs. Returns 1.0 if nothing to
    cross-check (no penalty for a genuinely thin package — completeness
    already captures that).
    """
    f = app.financials
    checks, passed = 0, 0
    if f.total_assets is not None and f.total_liabilities is not None and f.equity is not None:
        checks += 1
        implied = f.total_liabilities + f.equity
        if f.total_assets == 0 or abs(implied - f.total_assets) / max(abs(f.total_assets), 1) < 0.15:
            passed += 1
    if None not in (f.revenue, f.cost_of_sales, f.operating_expenses, f.net_profit):
        checks += 1
        implied_profit = f.revenue - f.cost_of_sales - f.operating_expenses
        if abs(implied_profit - f.net_profit) / max(abs(f.revenue), 1) < 0.15:
            passed += 1
    return 1.0 if checks == 0 else passed / checks


def _recency(app: BorrowerApplication) -> float:
    """Age of most recent data (D-003) — linear decay, floors at 0 after 24 months."""
    period_end = app.financials.period_end
    if period_end is None:
        return 0.3  # unknown recency treated conservatively, not as perfect
    months_old = (date.today() - period_end).days / 30.44
    return max(0.0, 1 - months_old / 24)


def compute_dqs(app: BorrowerApplication, features: dict[str, Feature]) -> DataQualityResult:
    completeness = _completeness(features)
    consistency = _consistency(app)
    recency = _recency(app)

    w = c.DQS_COMPONENT_WEIGHTS
    dqs = completeness * w["completeness"] + consistency * w["consistency"] + recency * w["recency"]

    is_thin_file = completeness < c.DQS_LOW_QUALITY_THRESHOLD

    gap = max(0.0, 1 - dqs)
    moc_pd_uplift = min(c.MAX_MOC_UPLIFT_PD, c.MAX_MOC_UPLIFT_PD * gap)
    moc_lgd_uplift = min(c.MAX_MOC_UPLIFT_LGD, c.MAX_MOC_UPLIFT_LGD * gap)

    return DataQualityResult(
        completeness=round(completeness, 4),
        consistency=round(consistency, 4),
        recency=round(recency, 4),
        dqs=round(dqs, 4),
        is_thin_file=is_thin_file,
        moc_pd_uplift=round(moc_pd_uplift, 4),
        moc_lgd_uplift=round(moc_lgd_uplift, 4),
    )


def apply_moc_to_pd(pd_point_estimate: float, moc_pd_uplift: float) -> float:
    """PD delivered downstream (incl. to P4) is already MoC-inclusive (Canon §2.6.1)."""
    return min(1.0, pd_point_estimate * (1 + moc_pd_uplift))


def apply_moc_to_lgd(lgd: float, moc_lgd_uplift: float) -> float:
    return min(1.0, lgd * (1 + moc_lgd_uplift))
