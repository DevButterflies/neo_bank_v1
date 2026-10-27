"""
Central parameter store.

Every constant here traces to a specific document/section. Where the source
documents themselves say a number is a DESIGN-stage prior, tunable value, or
PENDING governance item, that is called out explicitly in the constant's
comment — the code must not quietly pretend these are final calibrations.

Nothing below should be re-declared or duplicated elsewhere in the package;
other modules import from here.
"""

from .enums import CollateralTrack, FactorCategory, Product, Segment

# ---------------------------------------------------------------------------
# 4.3 — Category weights per model (Spec Table §4.3).
# "Starting values, tunable during testing and learning" — DESIGN-stage priors.
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS: dict[Segment, dict[FactorCategory, float]] = {
    Segment.MICRO: {
        FactorCategory.FINANCIAL_PERFORMANCE: 0.15,
        FactorCategory.LIQUIDITY_CASH_FLOW: 0.20,
        FactorCategory.BUSINESS_PROFILE: 0.15,
        FactorCategory.MANAGEMENT_OWNERSHIP: 0.25,
        FactorCategory.INDUSTRY_MACRO: 0.10,
        FactorCategory.DATA_QUALITY_DIGITAL_MATURITY: 0.15,
    },
    Segment.SMALL: {
        FactorCategory.FINANCIAL_PERFORMANCE: 0.25,
        FactorCategory.LIQUIDITY_CASH_FLOW: 0.25,
        FactorCategory.BUSINESS_PROFILE: 0.15,
        FactorCategory.MANAGEMENT_OWNERSHIP: 0.15,
        FactorCategory.INDUSTRY_MACRO: 0.10,
        FactorCategory.DATA_QUALITY_DIGITAL_MATURITY: 0.10,
    },
    Segment.MEDIUM: {
        FactorCategory.FINANCIAL_PERFORMANCE: 0.30,
        FactorCategory.LIQUIDITY_CASH_FLOW: 0.25,
        FactorCategory.BUSINESS_PROFILE: 0.18,
        FactorCategory.MANAGEMENT_OWNERSHIP: 0.10,
        FactorCategory.INDUSTRY_MACRO: 0.10,
        FactorCategory.DATA_QUALITY_DIGITAL_MATURITY: 0.07,
    },
}
assert all(abs(sum(w.values()) - 1.0) < 1e-6 for w in CATEGORY_WEIGHTS.values())

# ---------------------------------------------------------------------------
# 4.5 / 2.5.1 — Versioned design-stage BRR->PD grid (Spec Table §4.5, Canon §2.5.1).
# Explicitly a "v0" DESIGN-stage anchor, provisional, recalibrated from SANDBOX
# onward. Range upper bound is None for BRR 10 (open-ended ">30%").
# ---------------------------------------------------------------------------
BRR_PD_GRID_VERSION = "v0-design"

BRR_PD_GRID: dict[int, tuple[float, float | None]] = {
    1: (0.0000, 0.0010),
    2: (0.0010, 0.0025),
    3: (0.0025, 0.0050),
    4: (0.0050, 0.0100),
    5: (0.0100, 0.0200),
    6: (0.0200, 0.0400),
    7: (0.0400, 0.0800),
    8: (0.0800, 0.1500),
    9: (0.1500, 0.3000),
    10: (0.3000, None),
}
# Point estimate used for BRR 10 (open-ended range) — DESIGN-stage placeholder.
BRR_10_PD_POINT_ESTIMATE = 0.45

# ---------------------------------------------------------------------------
# 2.8 — Thin-file starter score constraints (Canon §2.8; V3.0 addition,
# structural — not overridable by local calibration).
# ---------------------------------------------------------------------------
THIN_FILE_MIN_BRR = 4          # starter score must NOT produce BRR 1-3
THIN_FILE_MAX_BRR = 10
THIN_FILE_BLOCKS_AUTO_APPROVE = True

# ---------------------------------------------------------------------------
# 2.6 — Budgeted Loss control band (Canon §2.6).
# ---------------------------------------------------------------------------
BUDGETED_LOSS_ANNUAL = 0.02   # 2% annually, "initial control band"

# ---------------------------------------------------------------------------
# 7 — Data Quality Score. DQS = weighted(completeness, consistency, recency).
# Equal weighting and the 0.75/0.55 bands are DESIGN-stage placeholders — the
# spec fixes the *inputs* to DQS (Table §12/D-001..D-004) but not these
# specific weights/thresholds, which are left open for calibration.
# ---------------------------------------------------------------------------
DQS_COMPONENT_WEIGHTS = {"completeness": 1 / 3, "consistency": 1 / 3, "recency": 1 / 3}
DQS_HIGH_CONFIDENCE_THRESHOLD = 0.75   # >= this: eligible for auto-approve data-confidence leg
DQS_LOW_QUALITY_THRESHOLD = 0.55       # < this: treated as low-quality package

# ---------------------------------------------------------------------------
# 2.6.1 / 7.2 — Margin of Conservatism sizing. MoC scales linearly with the
# data-quality gap: moc = MAX_MOC_UPLIFT * (1 - DQS), clipped to [0, MAX].
# The *principle* (buffer proportional to DQS, shrinking as data improves) is
# Canon-mandated; MAX_MOC_UPLIFT is a DESIGN-stage placeholder magnitude.
# ---------------------------------------------------------------------------
MAX_MOC_UPLIFT_PD = 0.50   # up to +50% relative uplift to PD when DQS -> 0
MAX_MOC_UPLIFT_LGD = 0.25  # up to +25% relative uplift to LGD when DQS -> 0

# ---------------------------------------------------------------------------
# 2.7 / 10 — Decisioning zone thresholds (Canon §2.7, ratified P-6).
# The *joint, three-condition* logic is Canon-mandated; the specific BRR
# cut-off for "low risk band" is a DESIGN-stage placeholder.
# ---------------------------------------------------------------------------
AUTO_APPROVE_MAX_BRR = 3
MANUAL_REVIEW_MIN_BRR = 7

# ---------------------------------------------------------------------------
# 6.3 — Product-specific EAD conventions (Spec Table §6.3).
# CCF (credit conversion factor) for revolving working-capital lines is a
# supervisory placeholder ("supervisory CCF until internal data sufficient").
# ---------------------------------------------------------------------------
SUPERVISORY_CCF_WORKING_CAPITAL = 0.75
SANDBOX_PRODUCTS = {Product.INVOICE_DISCOUNTING, Product.SUPPLY_CHAIN_FINANCE,
                    Product.WORKING_CAPITAL_LINE}
FORWARD_COMPATIBLE_ONLY_PRODUCTS = {Product.TERM_LOAN, Product.GROWTH_LOAN}

# ---------------------------------------------------------------------------
# 8.2 / 2.12.1 — Collateral tracks permitted per operating model.
# Track 1 is always available under both models (Canon §2.12.1).
# ---------------------------------------------------------------------------
TRACKS_AVAILABLE_UNDER_S = {
    CollateralTrack.TRACK_1_CLASSICAL, CollateralTrack.TRACK_2_NFT, CollateralTrack.TRACK_3_STABLECOIN
}
TRACKS_AVAILABLE_UNDER_G = {
    CollateralTrack.TRACK_1_CLASSICAL, CollateralTrack.TRACK_2_NFT
}  # Track 3 does not apply under G — no stablecoin minting

# Indicative recovery efficiency by track (design-stage placeholders only —
# real per-track haircuts are a PENDING governance item, Canon §4 / Spec §16:
# "per-country permitted tracks, dual-layer Track 3 haircut ... remains
# PENDING"). recovery_efficiency = expected recovery / P4-admitted value.
RECOVERY_EFFICIENCY_BY_TRACK = {
    CollateralTrack.TRACK_1_CLASSICAL: 0.60,   # legal recovery time + cost
    CollateralTrack.TRACK_2_NFT: 0.55,         # liquidation haircut + underlying-asset risk
    CollateralTrack.TRACK_3_STABLECOIN: 0.90,  # oracle-triggered transfer, near-full realization
}
UNSECURED_RECOVERY_EFFICIENCY = 0.10  # no collateral pledged

# ---------------------------------------------------------------------------
# 6.4.1 / 2.12.2 — Pooled-guarantee level (G model only). The required level
# is "computed by Pillar 2"; the target coverage ratio itself is a design
# placeholder pending the PENDING two-guarantee-layer interface spec.
# ---------------------------------------------------------------------------
POOLED_GUARANTEE_TARGET_COVERAGE_RATIO = 0.10  # of portfolio EAD not covered by facility collateral

# ---------------------------------------------------------------------------
# 9 — Sector / geography overlay bound (Spec §9.1: "bounded adjustment, not a
# free override"). Overlay is expressed in BRR notches.
# ---------------------------------------------------------------------------
SECTOR_GEO_MAX_BRR_ADJUSTMENT = 1.0

# ---------------------------------------------------------------------------
# 11 — Early-Warning Signal trigger (Canon §2.15, ratified P-7). Trigger is a
# BRR deterioration between origination and current snapshot beyond a
# threshold — magnitude is a DESIGN-stage placeholder.
# ---------------------------------------------------------------------------
EWS_BRR_DETERIORATION_TRIGGER = 2  # notches worse than at origination
