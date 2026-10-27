"""Controlled vocabularies (Canon §2.1, §2.2, §2.3, §2.7, §2.12, §4.2)."""

from enum import Enum


class Segment(str, Enum):
    """MSME segment — size/complexity based, not data-availability based (Canon §2.1)."""
    MICRO = "MICRO"
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"


class MaturityRegime(str, Enum):
    """Digital maturity regime — an internal regime inside each segment (Canon §2.2)."""
    LOW = "LOW"
    INTERMEDIATE = "INTERMEDIATE"
    HIGH = "HIGH"


class ModelTier(str, Enum):
    """Three-tier modelling stack (Canon §2.3)."""
    TIER_1 = "TIER_1"   # expert/statistical backbone — always on
    TIER_2 = "TIER_2"   # tree-based ML workhorse
    TIER_3 = "TIER_3"   # deep/graph challenger — advisory only, never production-authoritative


class ModelMaturityStage(str, Enum):
    """Model Maturity Stage (Canon §2.0, ratified P-5)."""
    DESIGN = "DESIGN"
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"


class OperatingModel(str, Enum):
    """Which sibling Orchestrator Canon the market runs under."""
    STABLECOIN = "S"    # Stablecoin Deposit Model (V3.1-S)
    GUARANTEE = "G"      # Guarantee Intermediation Model (V3.1-G)


class Product(str, Enum):
    """Facility products — EAD conventions differ by product (Canon §2.5)."""
    INVOICE_DISCOUNTING = "INVOICE_DISCOUNTING"
    SUPPLY_CHAIN_FINANCE = "SUPPLY_CHAIN_FINANCE"
    WORKING_CAPITAL_LINE = "WORKING_CAPITAL_LINE"
    TERM_LOAN = "TERM_LOAN"        # forward-compatible only, not built this phase
    GROWTH_LOAN = "GROWTH_LOAN"    # forward-compatible only, not built this phase


class CollateralClass(str, Enum):
    RECEIVABLES = "RECEIVABLES"
    INVENTORY = "INVENTORY"
    EQUIPMENT = "EQUIPMENT"
    REAL_ESTATE = "REAL_ESTATE"
    PERSONAL_GUARANTEE = "PERSONAL_GUARANTEE"  # not recognised at neo-bank level


class CollateralTrack(str, Enum):
    """Three-track collateral model, model-conditional (Canon §2.12.1, ratified P-9)."""
    NONE = "NONE"
    TRACK_1_CLASSICAL = "TRACK_1_CLASSICAL"
    TRACK_2_NFT = "TRACK_2_NFT"
    TRACK_3_STABLECOIN = "TRACK_3_STABLECOIN"   # [S] only — not applicable under [G]


class FactorCategory(int, Enum):
    """The six BRR master factor categories (Spec §4.2) — the system backbone."""
    FINANCIAL_PERFORMANCE = 1
    LIQUIDITY_CASH_FLOW = 2
    BUSINESS_PROFILE = 3
    MANAGEMENT_OWNERSHIP = 4
    INDUSTRY_MACRO = 5
    DATA_QUALITY_DIGITAL_MATURITY = 6


class DecisioningZone(str, Enum):
    """Three-zone decisioning model (Canon §2.7, ratified P-6)."""
    AUTO_APPROVE = "AUTO_APPROVE"
    AUGMENTED_DECISION = "AUGMENTED_DECISION"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class PacketStatus(str, Enum):
    """P2→P3 output packet status (V3.0 addition, Canon §2.7)."""
    APPROVED = "APPROVED"
    PROVISIONAL = "PROVISIONAL"     # augmented zone — needs officer counter-signature
    CONDITIONAL = "CONDITIONAL"     # manual review — needs revised submission + confirmation


class IFRS9Stage(str, Enum):
    """IFRS 9 staging signal fed to P4, PIT-adjusted (Canon §2.11.1, §2.13)."""
    STAGE_1 = "STAGE_1"
    STAGE_2 = "STAGE_2"
    STAGE_3 = "STAGE_3"
