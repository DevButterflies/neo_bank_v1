"""
Feature engineering — one function per feature in the Feature Catalogue
(Data Requirements Matrix, sheet `Feature_Catalogue`, FE-01..FE-16).

Each function returns a `Feature(value, missing, note)`. A feature is never
*skipped* for missing inputs — it returns `missing=True` so the DQS and MoC
layers can react; the caller (scoring.py) applies a sector/size proxy
fallback where the catalogue specifies one.

FE-17/FE-18 (supply-chain graph centrality, cash-flow sequence embedding)
are Tier-3 advisory-only features and are intentionally not scored here —
per Canon §2.3, Tier-3 outputs never drive a production BRR/PD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, pstdev
from typing import Optional

from .schemas import BorrowerApplication


@dataclass
class Feature:
    value: Optional[float]
    missing: bool
    note: str = ""


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


# ---- Category 1: Financial Performance & Strength -------------------------
def net_margin(app: BorrowerApplication) -> Feature:  # FE-01
    f = app.financials
    v = _safe_div(f.net_profit, f.revenue)
    if v is None:
        return Feature(None, True, "P&L absent: sector median + MoC (Data Matrix F-002)")
    return Feature(v, False)


def leverage_ratio(app: BorrowerApplication) -> Feature:  # FE-02
    f = app.financials
    v = _safe_div(f.total_liabilities, f.equity)
    if v is None:
        return Feature(None, True, "Missing: assume high leverage worst-case (F-003)")
    return Feature(v, False)


def revenue_growth_yoy(app: BorrowerApplication) -> Feature:  # FE-03
    f = app.financials
    if f.revenue is None or f.prior_period_revenue is None:
        return Feature(None, True, "Needs >=2 periods: low-confidence flag (F-005)")
    v = _safe_div(f.revenue - f.prior_period_revenue, f.prior_period_revenue)
    if v is None:
        return Feature(None, True, "Needs >=2 periods: low-confidence flag (F-005)")
    return Feature(v, False)


def asset_turnover(app: BorrowerApplication) -> Feature:
    f = app.financials
    v = _safe_div(f.revenue, f.total_assets)
    if v is None:
        return Feature(None, True, "Sector proxy + MoC (F-004)")
    return Feature(v, False)


# ---- Category 2: Liquidity & Cash Flow -------------------------------------
def cashflow_volatility(app: BorrowerApplication) -> Feature:  # FE-04
    cf = app.cash_flow
    series = cf.daily_net_cashflow
    if not series or (cf.months_of_history or 0) * 30 < 90:
        return Feature(None, True, "<90d history: sector proxy + low-confidence (L-002)")
    m = mean(series)
    if m == 0:
        return Feature(None, True, "Zero mean inflow: undefined volatility")
    return Feature(pstdev(series) / abs(m), False)


def dscr(app: BorrowerApplication) -> Feature:  # FE-05
    cf = app.cash_flow
    v = _safe_div(cf.avg_daily_inflow, cf.debt_service_obligation)
    if v is None:
        return Feature(None, True, "Worst-case low DSCR if undeterminable (L-003)")
    return Feature(v, False)


def wc_days(app: BorrowerApplication) -> Feature:  # FE-06
    cf = app.cash_flow
    parts = [cf.receivable_days, cf.inventory_days, cf.payable_days]
    if all(p is None for p in parts):
        return Feature(None, True, "Component-wise + MoC (L-004)")
    ar = cf.receivable_days or 0
    inv = cf.inventory_days or 0
    ap = cf.payable_days or 0
    return Feature(ar + inv - ap, any(p is None for p in parts), "Partial components imputed as 0")


def bounced_items(app: BorrowerApplication) -> Feature:  # FE-07
    cf = app.cash_flow
    if cf.bounced_items_count is None:
        return Feature(None, True, "Feed absent (not zero): require feed or MoC (L-006)")
    return Feature(float(cf.bounced_items_count), False)


# ---- Category 3: Business Profile & Market Position ------------------------
def customer_hhi(app: BorrowerApplication) -> Feature:  # FE-08
    b = app.business
    if b.top5_customer_share is None:
        return Feature(None, True, "Invoice proxy; else MoC (B-001)")
    return Feature(b.top5_customer_share, False)


def business_age_years(app: BorrowerApplication) -> Feature:  # FE-09
    b = app.business
    if b.registration_date is None:
        return Feature(None, True, "Vintage unknown: treat as new, conservative (B-003)")
    days = (date.today() - b.registration_date).days
    return Feature(days / 365.25, False)


# ---- Category 4: Management & Ownership Quality ----------------------------
def owner_experience(app: BorrowerApplication) -> Feature:  # FE-10
    m = app.management
    if m.owner_experience_years is None:
        return Feature(None, True, "Conservative band if blank + MoC (M-001)")
    return Feature(m.owner_experience_years, False)


def account_conduct(app: BorrowerApplication) -> Feature:  # FE-11
    m = app.management
    if m.account_conduct_score is None:
        return Feature(None, True, "Bureau/feed dependent; MoC if absent (M-004)")
    return Feature(m.account_conduct_score, False)


# ---- Category 5: Industry & Macro Environment ------------------------------
# Sector/geography overlay (FE-12/FE-13) is computed by pillar2.overlay, not
# here — it is "never missing (seeded)" from an open-data lookup table.

# ---- Category 6: Data Quality & Digital Maturity ---------------------------
def rails_connected_count(app: BorrowerApplication) -> Feature:  # FE-16
    return Feature(float(len(app.rails_connected)), False)
