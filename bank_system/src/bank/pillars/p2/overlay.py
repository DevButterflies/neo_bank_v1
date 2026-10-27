"""
Sector-Geography Risk Matrix (Spec §9).

"A standalone module ... producing an overlay adjustment to the BRR (within
factor category 5) and serving as a concentration-monitoring input to
Pillar 4. It is model-agnostic." In DESIGN, "seeded from open-data sector
default behaviour (SBA, ECB SAFE, World Bank)".

The lookup tables below are illustrative DESIGN-stage seeds, not a
calibrated production table — that re-estimation on Oman data happens in
SANDBOX (Spec §9.1).
"""

from __future__ import annotations

from . import constants as c

# risk_weight in [0,1]: 0 = benign sector/geography, 1 = high-stress.
_SECTOR_RISK_SEED: dict[str, float] = {
    "TRADE_RETAIL": 0.35,
    "CONSTRUCTION": 0.55,
    "MANUFACTURING": 0.40,
    "HOSPITALITY_TOURISM": 0.60,
    "LOGISTICS_TRANSPORT": 0.45,
    "PROFESSIONAL_SERVICES": 0.25,
    "AGRICULTURE": 0.50,
    "TECH_ECOMMERCE": 0.30,
}
_DEFAULT_SECTOR_RISK = 0.45  # unseeded sector: mid-point, never omitted

_GEOGRAPHY_RISK_SEED: dict[str, float] = {
    "MUSCAT": 0.25,
    "DHOFAR": 0.35,
    "AL_BATINAH": 0.40,
    "AL_DAKHILIYAH": 0.40,
    "MUSANDAM": 0.45,
}
_DEFAULT_GEOGRAPHY_RISK = 0.40


def sector_risk_score(sector_code: str | None) -> float:  # FE-12
    """'Never missing (seeded)' — always returns a value (Data Matrix S-001)."""
    return _SECTOR_RISK_SEED.get((sector_code or "").upper(), _DEFAULT_SECTOR_RISK)


def geography_risk_score(geography_code: str | None) -> float:  # FE-13
    """'Never missing (seeded)' — always returns a value (Data Matrix S-002)."""
    return _GEOGRAPHY_RISK_SEED.get((geography_code or "").upper(), _DEFAULT_GEOGRAPHY_RISK)


def overlay_adjustment(sector_code: str | None, geography_code: str | None) -> float:
    """
    Bounded BRR-notch adjustment (Spec §9.1: "bounded adjustment, not a free
    override"). Centres the blended sector/geo risk on 0.5 and scales into
    +/- SECTOR_GEO_MAX_BRR_ADJUSTMENT notches.
    """
    blended = 0.5 * sector_risk_score(sector_code) + 0.5 * geography_risk_score(geography_code)
    centred = (blended - 0.5) * 2  # in [-1, 1]
    return round(centred * c.SECTOR_GEO_MAX_BRR_ADJUSTMENT, 4)
