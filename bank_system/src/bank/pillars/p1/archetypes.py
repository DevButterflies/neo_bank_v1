"""
Dummy Pillar 1 data feed — stand-in for the real P1 rails.

Per Orchestrator Canon §1, Pillar 1 is external and country-dependent,
and is out of scope for this milestone. This module plays P1's role only
as far as the P1 -> P2 contract requires: it hands Pillar 2 a populated
`BorrowerApplication`, exactly shaped like the standardized feature-store
record P1 would produce (Canon §3), so Pillar 2 runs completely
unmodified against it.

Four MSME archetypes are provided, chosen to land in different
decisioning zones so the P2 -> P3 handoff can be shown under different
packet statuses (APPROVED / PROVISIONAL / CONDITIONAL) without touching
any P2 internals. All run under the Guarantee Intermediation model
(V3.1-G), the operative model this Pillar 3 build implements.
"""
from __future__ import annotations

from datetime import date, timedelta

from bank.pillars.p2.enums import (
    CollateralClass, CollateralTrack, ModelMaturityStage, OperatingModel,
    Product, Segment,
)
from bank.pillars.p2.schemas import (
    BorrowerApplication, BusinessProfile, CashFlowData, CollateralOffer,
    FacilityRequest, FinancialStatement, ManagementProfile,
)

PROFILES: dict[str, dict] = {
    "amina": {
        "id": "amina",
        "name": "Amina — Home Bakery",
        "tagline": "Thin-file, two rails connected.",
        "scenario": (
            "Only KYC and a mobile-money feed are connected. No financial "
            "statements, seven months trading, no collateral offered."
        ),
        "expected_outcome": "Thin-file -> forced into Manual Review, whatever the BRR says.",
        "application": BorrowerApplication(
            application_id="APP-AMINA-101",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.SANDBOX,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=4_000, drawn_amount=2_500, undrawn_amount=1_500,
            ),
            business=BusinessProfile(
                sector_code="FOOD_PRODUCTION", geography_code="MUSCAT",
                registration_date=date.today() - timedelta(days=210),
            ),
            management=ManagementProfile(owner_experience_years=1.5),
            rails_connected=["kyc", "mobile_money"],
        ),
    },
    "yusuf": {
        "id": "yusuf",
        "name": "Yusuf — Auto Parts Retailer",
        "tagline": "Moderate data, moderate risk.",
        "scenario": (
            "Bank feed and POS connected. Real financials, but leveraged and "
            "with a couple of bounced payments in the last quarter."
        ),
        "expected_outcome": "Mid-range BRR -> Augmented Decision, needs officer counter-signature.",
        "application": BorrowerApplication(
            application_id="APP-YUSUF-102",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.SANDBOX,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=18_000, drawn_amount=12_000, undrawn_amount=6_000,
            ),
            financials=FinancialStatement(
                revenue=140_000, cost_of_sales=95_000, operating_expenses=25_000,
                net_profit=20_000, period_end=date.today() - timedelta(days=40),
                total_assets=90_000, total_liabilities=58_000, equity=32_000,
                prior_period_revenue=132_000,
            ),
            cash_flow=CashFlowData(
                avg_daily_inflow=550, debt_service_obligation=320,
                receivable_days=28, inventory_days=50, payable_days=22,
                bounced_items_count=2, months_of_history=4,
            ),
            business=BusinessProfile(
                sector_code="TRADE_RETAIL", geography_code="AL_BATINAH",
                registration_date=date.today() - timedelta(days=365 * 4),
                top5_customer_share=0.55, single_supplier_share=0.35,
            ),
            management=ManagementProfile(
                owner_experience_years=4.0, prior_default_history=False,
                has_governance_plan=False, account_conduct_score=0.62,
            ),
            collateral=[CollateralOffer(
                collateral_class=CollateralClass.RECEIVABLES,
                track=CollateralTrack.TRACK_1_CLASSICAL, p4_admitted_value=9_000,
            )],
            rails_connected=["kyc", "bank_feed", "pos"],
        ),
    },
    "layla": {
        "id": "layla",
        "name": "Layla — Textile Exporter",
        "tagline": "Strong profile, good data coverage.",
        "scenario": (
            "Four rails connected. Healthy margins, low leverage, eight years "
            "trading, a governance plan on file, Track 1 collateral offered."
        ),
        "expected_outcome": "Low BRR, high data confidence -> Auto-approve zone.",
        "application": BorrowerApplication(
            application_id="APP-LAYLA-103",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.SANDBOX,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=32_000, drawn_amount=22_000, undrawn_amount=10_000,
            ),
            financials=FinancialStatement(
                revenue=260_000, cost_of_sales=155_000, operating_expenses=42_000,
                net_profit=63_000, period_end=date.today() - timedelta(days=12),
                total_assets=210_000, total_liabilities=62_000, equity=148_000,
                prior_period_revenue=228_000,
            ),
            cash_flow=CashFlowData(
                daily_net_cashflow=[820, 910, 770, 860, 930, 790, 830, 880, 950, 780],
                avg_daily_inflow=1250, debt_service_obligation=410,
                receivable_days=24, inventory_days=11, payable_days=32,
                bounced_items_count=0, months_of_history=11,
            ),
            business=BusinessProfile(
                sector_code="TEXTILES_EXPORT", geography_code="MUSCAT",
                registration_date=date.today() - timedelta(days=365 * 8),
                top5_customer_share=0.38, single_supplier_share=0.18,
            ),
            management=ManagementProfile(
                owner_experience_years=8.0, prior_default_history=False,
                has_governance_plan=True, account_conduct_score=0.86,
            ),
            collateral=[CollateralOffer(
                collateral_class=CollateralClass.RECEIVABLES,
                track=CollateralTrack.TRACK_1_CLASSICAL, p4_admitted_value=26_000,
            )],
            rails_connected=["kyc", "bank_feed", "tax", "pos"],
        ),
    },
    "bilal": {
        "id": "bilal",
        "name": "Bilal — Construction Contractor",
        "tagline": "Decent data, but a live policy exception.",
        "scenario": (
            "Good rail coverage and real financials, but flagged for a policy "
            "exception (an open regulatory compliance item) that no BRR can "
            "override, plus Track 2 (NFT) collateral offered — a track this "
            "Pillar 3 build cannot yet record."
        ),
        "expected_outcome": "Policy exception forces Manual Review regardless of BRR.",
        "application": BorrowerApplication(
            application_id="APP-BILAL-104",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.SANDBOX,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=45_000, drawn_amount=30_000, undrawn_amount=15_000,
            ),
            financials=FinancialStatement(
                revenue=310_000, cost_of_sales=210_000, operating_expenses=55_000,
                net_profit=45_000, period_end=date.today() - timedelta(days=20),
                total_assets=260_000, total_liabilities=150_000, equity=110_000,
                prior_period_revenue=300_000,
            ),
            cash_flow=CashFlowData(
                avg_daily_inflow=1100, debt_service_obligation=700,
                receivable_days=40, inventory_days=25, payable_days=28,
                bounced_items_count=1, months_of_history=9,
            ),
            business=BusinessProfile(
                sector_code="CONSTRUCTION", geography_code="DHOFAR",
                registration_date=date.today() - timedelta(days=365 * 6),
                top5_customer_share=0.70, single_supplier_share=0.30,
            ),
            management=ManagementProfile(
                owner_experience_years=6.0, prior_default_history=False,
                has_governance_plan=True, account_conduct_score=0.70,
            ),
            collateral=[CollateralOffer(
                collateral_class=CollateralClass.EQUIPMENT,
                track=CollateralTrack.TRACK_2_NFT, p4_admitted_value=18_000,
            )],
            rails_connected=["kyc", "bank_feed", "tax", "pos"],
            policy_exception_flags=["OPEN_COMPLIANCE_REVIEW"],
        ),
    },
}


def list_profiles() -> list[dict]:
    return [
        {"id": p["id"], "name": p["name"], "tagline": p["tagline"],
         "scenario": p["scenario"], "expected_outcome": p["expected_outcome"]}
        for p in PROFILES.values()
    ]


def get_application(profile_id: str) -> BorrowerApplication:
    return PROFILES[profile_id]["application"]
