"""
Expected Loss and pricing (Canon §2.6, Spec §6.2).

EL = PD x LGD x EAD at facility level. The base loan rate embeds three
ex-ante cost layers: stablecoin deposit remuneration (tier-agnostic at loan
level — P4 separates tiers only for prudential purposes), normal loan
provisions up to the 2% Budgeted Loss, and normal operating margin. When EL
exceeds the Budgeted Loss, the borrower pays a risk premium on top; that
premium is neo-bank income managed by P4 (its allocation to Tier B-Fees is
a P4 governance decision, out of scope for P2 — Canon §2.6, V4.1 correction).
"""

from __future__ import annotations

from . import constants as c
from .schemas import CreditRiskResult, PricingResult

# Cost layers for the base rate — DESIGN-stage placeholders (bps = basis points).
FUNDING_COST_BPS = 300.0     # standard stablecoin-deposit remuneration
OPERATING_MARGIN_BPS = 150.0  # normal neo-bank operating margin


def compute_expected_loss(pd: float, lgd: float, ead: float) -> CreditRiskResult:
    el = pd * lgd * ead
    el_ratio = el / ead if ead else 0.0
    band = "within" if el_ratio <= c.BUDGETED_LOSS_ANNUAL else "above"
    return CreditRiskResult(
        ead=round(ead, 2),
        lgd=round(lgd, 6),
        lgd_with_moc=round(lgd, 6),  # overwritten by caller once MoC is applied to LGD
        expected_loss=round(el, 2),
        el_vs_budgeted_loss=band,
    )


def price_facility(ead: float, expected_loss: float) -> PricingResult:
    """
    Base rate = funding cost + provisions up to Budgeted Loss + operating
    margin. Risk premium = only the EL amount that exceeds the Budgeted
    Loss band, expressed in bps of EAD (Canon §2.6).
    """
    provisions_bps = c.BUDGETED_LOSS_ANNUAL * 10_000  # 2% -> 200 bps, the provisioned layer
    base_rate_bps = FUNDING_COST_BPS + provisions_bps + OPERATING_MARGIN_BPS

    el_ratio = expected_loss / ead if ead else 0.0
    excess_el_ratio = max(0.0, el_ratio - c.BUDGETED_LOSS_ANNUAL)
    risk_premium_bps = excess_el_ratio * 10_000

    return PricingResult(
        base_rate_bps=round(base_rate_bps, 2),
        risk_premium_bps=round(risk_premium_bps, 2),
        all_in_rate_bps=round(base_rate_bps + risk_premium_bps, 2),
    )
