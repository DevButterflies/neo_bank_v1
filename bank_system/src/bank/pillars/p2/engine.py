"""
Pillar2Engine — the single entry point that runs an application through the
full pipeline: features -> DQS/MoC -> Tier-1 BRR -> BRR->PD grid -> EAD ->
LGD (+ pooled guarantee under G) -> EL -> pricing -> decisioning zone ->
P2->P3 output packet.

This mirrors Spec §2 (Architecture Overview) end to end. `Pillar2Engine` is
intentionally the only class a caller needs to know about; every other
module is a pure-function building block it composes.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import constants as c
from . import dqs as dqs_mod
from . import ead as ead_mod
from . import lgd as lgd_mod
from . import pricing as pricing_mod
from . import scoring as scoring_mod
from .decisioning import determine_zone, packet_status_and_confirmation
from .features import (
    account_conduct, asset_turnover, bounced_items, business_age_years,
    cashflow_volatility, customer_hhi, dscr, leverage_ratio, net_margin,
    owner_experience, revenue_growth_yoy, wc_days,
)
from .schemas import BorrowerApplication, OutputPacket, ScoringResult


def _collect_features(app: BorrowerApplication) -> dict:
    """All Tier-1 features, for DQS completeness measurement (Canon §7.1)."""
    fns = (
        net_margin, leverage_ratio, revenue_growth_yoy, asset_turnover,
        cashflow_volatility, dscr, wc_days, bounced_items,
        customer_hhi, business_age_years, owner_experience, account_conduct,
    )
    return {fn.__name__: fn(app) for fn in fns}


@dataclass
class Pillar2Engine:
    """
    Parameters
    ----------
    production_auto_approve_enabled:
        Governance switch for straight-through auto-approve in PRODUCTION
        (ratified condition P-5 — a separate, explicit, per-model P4
        approval act). Defaults to False: never automatic.
    """
    production_auto_approve_enabled: bool = False

    def score(self, app: BorrowerApplication) -> ScoringResult:
        features = _collect_features(app)
        dqs = dqs_mod.compute_dqs(app, features)
        rating = scoring_mod.score_brr(app, dqs)

        ead = ead_mod.compute_ead(app.facility)
        raw_lgd = lgd_mod.compute_lgd(app.collateral, ead, app.operating_model)
        lgd_with_moc = dqs_mod.apply_moc_to_lgd(raw_lgd, dqs.moc_lgd_uplift)

        credit_risk = pricing_mod.compute_expected_loss(rating.pd_with_moc, lgd_with_moc, ead)
        credit_risk.lgd = raw_lgd
        credit_risk.lgd_with_moc = lgd_with_moc
        credit_risk.expected_loss = round(rating.pd_with_moc * lgd_with_moc * ead, 2)
        el_ratio = credit_risk.expected_loss / ead if ead else 0.0
        credit_risk.el_vs_budgeted_loss = "within" if el_ratio <= c.BUDGETED_LOSS_ANNUAL else "above"

        pricing = pricing_mod.price_facility(ead, credit_risk.expected_loss)

        zone = determine_zone(
            brr=rating.brr,
            dqs=dqs.dqs,
            is_thin_file=dqs.is_thin_file,
            has_policy_exception=bool(app.policy_exception_flags),
            el_within_budgeted_loss=(credit_risk.el_vs_budgeted_loss == "within"),
        )
        status, requires_confirmation = packet_status_and_confirmation(
            zone, app.model_maturity_stage, self.production_auto_approve_enabled
        )

        packet = OutputPacket(
            application_id=app.application_id,
            status=status,
            model_maturity_stage=app.model_maturity_stage,
            pd_grid_version=rating.pd_grid_version,
            collateral_track=lgd_mod.primary_track(app.collateral),
            brr=rating.brr,
            pd=rating.pd_with_moc,
            lgd=lgd_with_moc,
            ead=ead,
            expected_loss=credit_risk.expected_loss,
            pricing=pricing,
            zone=zone,
            requires_officer_confirmation=requires_confirmation,
        )

        return ScoringResult(
            application_id=app.application_id,
            segment=app.segment,
            maturity_regime=app.maturity_regime,
            data_quality=dqs,
            rating=rating,
            credit_risk=credit_risk,
            pricing=pricing,
            zone=zone,
            packet=packet,
        )
