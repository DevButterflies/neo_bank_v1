"""
Collateral: LGD by track and the G-model pooled guarantee.

Pillar 2 never values raw assets and has no interface with Pillar 5 (Canon
§2.11, §2.12, §3 P2<->P5 firewall). It consumes only the haircut-adjusted
value Pillar 4 has already admitted (`CollateralOffer.p4_admitted_value`)
and applies its own LGD methodology on top of that value (Canon §2.12).
"""

from __future__ import annotations

from . import constants as c
from .enums import CollateralTrack, OperatingModel
from .schemas import CollateralOffer


class TrackNotAvailableUnderModel(ValueError):
    """Track 3 (stablecoin) does not apply under the Guarantee model (Canon §2.12.1)."""


def available_tracks(operating_model: OperatingModel) -> set[CollateralTrack]:
    return c.TRACKS_AVAILABLE_UNDER_S if operating_model == OperatingModel.STABLECOIN \
        else c.TRACKS_AVAILABLE_UNDER_G


def _validate_track(offer: CollateralOffer, operating_model: OperatingModel) -> None:
    if offer.track == CollateralTrack.NONE:
        return
    if offer.track not in available_tracks(operating_model):
        raise TrackNotAvailableUnderModel(
            f"{offer.track.value} is not available under the {operating_model.value} model "
            "(Canon §2.12.1: Track 3 requires the Stablecoin Deposit Model)."
        )


def compute_lgd(collateral: list[CollateralOffer], ead: float, operating_model: OperatingModel) -> float:
    """
    LGD = 1 - (expected recovery / EAD), floored at 0, capped at 1.
    Expected recovery sums each pledge's P4-admitted value times its
    track's indicative recovery efficiency (design-stage placeholder —
    real per-track haircuts remain a PENDING governance item, Spec §16).
    Unsecured exposure recovers at `UNSECURED_RECOVERY_EFFICIENCY`.
    """
    if ead <= 0:
        return 0.0

    for offer in collateral:
        _validate_track(offer, operating_model)

    secured_recovery = sum(
        offer.p4_admitted_value * c.RECOVERY_EFFICIENCY_BY_TRACK.get(offer.track, 0.0)
        for offer in collateral if offer.track != CollateralTrack.NONE
    )
    secured_value = sum(offer.p4_admitted_value for offer in collateral if offer.track != CollateralTrack.NONE)
    unsecured_exposure = max(0.0, ead - secured_value)
    unsecured_recovery = unsecured_exposure * c.UNSECURED_RECOVERY_EFFICIENCY

    total_recovery = secured_recovery + unsecured_recovery
    lgd = 1 - min(total_recovery, ead) / ead
    return round(max(0.0, min(1.0, lgd)), 6)


def primary_track(collateral: list[CollateralOffer]) -> CollateralTrack:
    """Reports the (first) pledged track for the output packet (Canon §3 P2->P3)."""
    for offer in collateral:
        if offer.track != CollateralTrack.NONE:
            return offer.track
    return CollateralTrack.NONE


def compute_pooled_guarantee_level(portfolio_ead: float, portfolio_facility_collateral_value: float) -> float:
    """
    G-model only (Canon §2.12.2, conforms V3.1-G §6.2): a portfolio-level
    credit enhancement computed by Pillar 2, held under Pillar 4, pledged on
    top of each facility's own collateral — not attributed per-facility.
    Target coverage ratio is a design-stage placeholder (interface spec is
    PENDING, Spec §16).
    """
    uncovered = max(0.0, portfolio_ead - portfolio_facility_collateral_value)
    return round(uncovered * c.POOLED_GUARANTEE_TARGET_COVERAGE_RATIO, 2)
