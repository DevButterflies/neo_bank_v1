"""Seed candidates for the P1 demo: the six demo_3 borrower profiles.

Faithful port of ``combined/demo_3/app/profiles.py`` onto the
``bank.pillars.p2`` schema (same enum names/values), so entering the same
application through Pillar 2 reproduces the same data tier -> BRR/DQS ->
decisioning-zone journey:

  ahmed  small data / paid     layla  medium data / paid     nadia  good data / paid
  yusuf  small data / default  omar   medium data / default  fatima good data / default

Each row carries its full ``BorrowerApplication`` (``application_json``) and
the explicit payment behaviour from the profile's repayment tables, so the
tick simulation follows the exact demo_3 cash flows.
"""

from __future__ import annotations

from datetime import date, timedelta

from bank.pillars.p1.schemas import PaymentBehavior, RepaymentRow
from bank.pillars.p2.enums import (
    CollateralClass,
    CollateralTrack,
    ModelMaturityStage,
    OperatingModel,
    Product,
    Segment,
)
from bank.pillars.p2.schemas import (
    BorrowerApplication,
    BusinessProfile,
    CashFlowData,
    CollateralOffer,
    FacilityRequest,
    FinancialStatement,
    ManagementProfile,
)

_TODAY = date.today()


def _payments(rows: list[dict]) -> list[RepaymentRow]:
    return [RepaymentRow(**r) for r in rows]


def _bps(disbursed: float, first_interest: float) -> int:
    if disbursed <= 0:
        return 1000
    return int(round(first_interest / disbursed * 12 * 10_000 / 100.0) * 100)


SEED_CANDIDATES: list[dict] = [
    # ------------------------------------------------------------------
    # SMALL DATA
    # ------------------------------------------------------------------
    {
        "profile_id": "ahmed",
        "name": "Ahmed -- Corner Shop",
        "first_name": "Ahmed",
        "last_name": "Corner Shop",
        "gender": "male",
        "age": 34,
        "city": "Muscat",
        "employer_name": "Corner Shop",
        "employer_type": "self_employed",
        "employment_years": 5.0,
        "monthly_salary": 1_650,
        "requested_amount": 8_000,
        "requested_tenure_months": 5,
        "story": {
            "data_tier": "small",
            "outcome": "paid",
            "segment": "MICRO",
            "tagline": "Thin file, but steady payments.",
            "scenario": (
                "Only KYC and utility payment history connected. No financial "
                "statements, no bank feed, no POS data. The engine has almost "
                "nothing to work with -- most features return 'missing' and get "
                "conservative defaults. Thin-file rules cap BRR at 4-10. Despite "
                "the sparse data, Ahmed has 5 years of experience and pays on "
                "schedule."
            ),
        },
        "application": BorrowerApplication(
            application_id="APP-AHMED-301",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.PRODUCTION,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=8_000, drawn_amount=6_000, undrawn_amount=2_000,
            ),
            business=BusinessProfile(
                sector_code="TRADE_RETAIL",
                geography_code="MUSCAT",
                registration_date=_TODAY - timedelta(days=365 * 5),
            ),
            management=ManagementProfile(owner_experience_years=5.0),
            rails_connected=["kyc", "utility"],
        ),
        "behavior": {
            "outcome": "paid",
            "facility_amount": 8_000,
            "disbursed": 6_000,
            "currency": "USD",
            "tenure_months": 5,
            "repayments": _payments([
                {"interest": 120, "principal": 1_200, "month": 1},
                {"interest": 108, "principal": 1_200, "month": 2},
                {"interest": 96, "principal": 1_200, "month": 3},
                {"interest": 84, "principal": 1_200, "month": 4},
                {"interest": 72, "principal": 1_200, "month": 5},
            ]),
            "delinquent_month": None,
            "default_month": None,
            "recovered_amount": 0.0,
            "interest_rate_bps": _bps(6_000, 120),
        },
    },
    {
        "profile_id": "yusuf",
        "name": "Yusuf -- Street Vendor",
        "first_name": "Yusuf",
        "last_name": "Street Vendor",
        "gender": "male",
        "age": 29,
        "city": "Dhofar",
        "employer_name": "Street Vendor",
        "employer_type": "self_employed",
        "employment_years": 1.0,
        "monthly_salary": 1_100,
        "requested_amount": 5_000,
        "requested_tenure_months": 4,
        "story": {
            "data_tier": "small",
            "outcome": "default",
            "segment": "MICRO",
            "tagline": "Thin file, minimal track record.",
            "scenario": (
                "Only KYC and mobile money connected. No financial statements, "
                "no bank feed. Just 7 months in business with 1 year of "
                "experience. Thin-file rules force BRR into 4-10 range. Sparse "
                "data means the engine cannot distinguish risk well -- MoC uplift "
                "is large. Loan is originated but borrower defaults quickly."
            ),
        },
        "application": BorrowerApplication(
            application_id="APP-YUSUF-302",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.PRODUCTION,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=5_000, drawn_amount=4_000, undrawn_amount=1_000,
            ),
            business=BusinessProfile(
                sector_code="HOSPITALITY_TOURISM",
                geography_code="DHOFAR",
                registration_date=_TODAY - timedelta(days=210),
            ),
            management=ManagementProfile(owner_experience_years=1.0),
            rails_connected=["kyc", "mobile_money"],
        ),
        "behavior": {
            "outcome": "default",
            "facility_amount": 5_000,
            "disbursed": 4_000,
            "currency": "USD",
            "tenure_months": 4,
            "repayments": _payments([
                {"interest": 100, "principal": 800, "month": 1},
            ]),
            "delinquent_month": 2,
            "default_month": 3,
            "recovered_amount": 1_500,
            "interest_rate_bps": _bps(4_000, 100),
        },
    },
    # ------------------------------------------------------------------
    # MEDIUM DATA
    # ------------------------------------------------------------------
    {
        "profile_id": "layla",
        "name": "Layla -- Textile Exporter",
        "first_name": "Layla",
        "last_name": "Textile Exporter",
        "gender": "female",
        "age": 41,
        "city": "Muscat",
        "employer_name": "Textile Exporter",
        "employer_type": "private",
        "employment_years": 8.0,
        "monthly_salary": 4_500,
        "requested_amount": 32_000,
        "requested_tenure_months": 6,
        "story": {
            "data_tier": "medium",
            "outcome": "paid",
            "segment": "MICRO",
            "tagline": "Partial data, strong fundamentals.",
            "scenario": (
                "Four rails connected: KYC, bank feed, POS, tax. Has P&L "
                "financials (but no prior-period revenue for growth), cash-flow "
                "summary (but no daily series). Full business profile and "
                "management. Most features present -- completeness ~83%. Strong "
                "metrics: healthy margins, low leverage, 8 years in business, "
                "governance plan on file. Scores well and pays on schedule."
            ),
        },
        "application": BorrowerApplication(
            application_id="APP-LAYLA-303",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.PRODUCTION,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=32_000, drawn_amount=22_000, undrawn_amount=10_000,
            ),
            financials=FinancialStatement(
                revenue=260_000, cost_of_sales=155_000, operating_expenses=42_000,
                net_profit=63_000, period_end=_TODAY - timedelta(days=12),
                total_assets=210_000, total_liabilities=62_000, equity=148_000,
            ),
            cash_flow=CashFlowData(
                avg_daily_inflow=1250, debt_service_obligation=410,
                receivable_days=24, inventory_days=11, payable_days=32,
                bounced_items_count=0, months_of_history=11,
            ),
            business=BusinessProfile(
                sector_code="TEXTILES_EXPORT", geography_code="MUSCAT",
                registration_date=_TODAY - timedelta(days=365 * 8),
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
        "behavior": {
            "outcome": "paid",
            "facility_amount": 32_000,
            "disbursed": 22_000,
            "currency": "USD",
            "tenure_months": 6,
            "repayments": _payments([
                {"interest": 400, "principal": 5_000, "month": 1},
                {"interest": 350, "principal": 5_000, "month": 2},
                {"interest": 300, "principal": 5_000, "month": 3},
                {"interest": 250, "principal": 5_000, "month": 4},
                {"interest": 200, "principal": 5_000, "month": 5},
                {"interest": 150, "principal": 5_000, "month": 6},
            ]),
            "delinquent_month": None,
            "default_month": None,
            "recovered_amount": 0.0,
            "interest_rate_bps": _bps(22_000, 400),
        },
    },
    {
        "profile_id": "omar",
        "name": "Omar -- Fruit Vendor",
        "first_name": "Omar",
        "last_name": "Fruit Vendor",
        "gender": "male",
        "age": 33,
        "city": "Batinah",
        "employer_name": "Fruit Vendor",
        "employer_type": "self_employed",
        "employment_years": 3.0,
        "monthly_salary": 1_800,
        "requested_amount": 15_000,
        "requested_tenure_months": 5,
        "story": {
            "data_tier": "medium",
            "outcome": "default",
            "segment": "MICRO",
            "tagline": "Partial data, stressed metrics.",
            "scenario": (
                "Four rails connected: KYC, bank feed, POS, tax. Same data "
                "coverage as Layla but weaker financials: tight margins, high "
                "leverage, bounced payments. Loan is originated but borrower "
                "struggles with repayments and defaults."
            ),
        },
        "application": BorrowerApplication(
            application_id="APP-OMAR-304",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.PRODUCTION,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=15_000, drawn_amount=12_000, undrawn_amount=3_000,
            ),
            financials=FinancialStatement(
                revenue=95_000, cost_of_sales=68_000, operating_expenses=15_000,
                net_profit=12_000, period_end=_TODAY - timedelta(days=35),
                total_assets=65_000, total_liabilities=42_000, equity=23_000,
            ),
            cash_flow=CashFlowData(
                avg_daily_inflow=380, debt_service_obligation=280,
                receivable_days=35, inventory_days=40, payable_days=20,
                bounced_items_count=2, months_of_history=5,
            ),
            business=BusinessProfile(
                sector_code="FOOD_RETAIL", geography_code="AL_BATINAH",
                registration_date=_TODAY - timedelta(days=365 * 3),
                top5_customer_share=0.48, single_supplier_share=0.40,
            ),
            management=ManagementProfile(
                owner_experience_years=3.0, prior_default_history=False,
                has_governance_plan=False, account_conduct_score=0.58,
            ),
            collateral=[CollateralOffer(
                collateral_class=CollateralClass.RECEIVABLES,
                track=CollateralTrack.TRACK_1_CLASSICAL, p4_admitted_value=7_000,
            )],
            rails_connected=["kyc", "bank_feed", "tax", "pos"],
        ),
        "behavior": {
            "outcome": "default",
            "facility_amount": 15_000,
            "disbursed": 12_000,
            "currency": "USD",
            "tenure_months": 5,
            "repayments": _payments([
                {"interest": 220, "principal": 2_000, "month": 1},
                {"interest": 200, "principal": 2_000, "month": 2},
            ]),
            "delinquent_month": 3,
            "default_month": 4,
            "recovered_amount": 4_500,
            "interest_rate_bps": _bps(12_000, 220),
        },
    },
    # ------------------------------------------------------------------
    # GOOD DATA
    # ------------------------------------------------------------------
    {
        "profile_id": "nadia",
        "name": "Nadia -- Catering Service",
        "first_name": "Nadia",
        "last_name": "Catering Service",
        "gender": "female",
        "age": 37,
        "city": "Muscat",
        "employer_name": "Catering Service",
        "employer_type": "private",
        "employment_years": 5.0,
        "monthly_salary": 6_500,
        "requested_amount": 45_000,
        "requested_tenure_months": 5,
        "story": {
            "data_tier": "good",
            "outcome": "paid",
            "segment": "SMALL",
            "tagline": "Full data, strong credit profile.",
            "scenario": (
                "Six rails connected. All 12 features present -- completeness "
                "100%. Full P&L with prior period, daily cash-flow series, "
                "complete business and management profiles. Two collateral items. "
                "Strong metrics: healthy margins, low leverage, governance plan, "
                "high conduct score. Lowest MoC uplift."
            ),
        },
        "application": BorrowerApplication(
            application_id="APP-NADIA-305",
            segment=Segment.SMALL,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.PRODUCTION,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=45_000, drawn_amount=35_000, undrawn_amount=10_000,
            ),
            financials=FinancialStatement(
                revenue=380_000, cost_of_sales=220_000, operating_expenses=65_000,
                net_profit=95_000, period_end=_TODAY - timedelta(days=10),
                total_assets=320_000, total_liabilities=75_000, equity=245_000,
                prior_period_revenue=340_000,
            ),
            cash_flow=CashFlowData(
                daily_net_cashflow=[1100, 1200, 1050, 1150, 1250, 1080, 1120, 1180, 1280, 1060],
                avg_daily_inflow=1800, debt_service_obligation=520,
                receivable_days=18, inventory_days=8, payable_days=30,
                bounced_items_count=0, months_of_history=12,
            ),
            business=BusinessProfile(
                sector_code="FOOD_SERVICES", geography_code="MUSCAT",
                registration_date=_TODAY - timedelta(days=365 * 5),
                top5_customer_share=0.28, single_supplier_share=0.20,
            ),
            management=ManagementProfile(
                owner_experience_years=5.0, prior_default_history=False,
                has_governance_plan=True, account_conduct_score=0.92,
            ),
            collateral=[
                CollateralOffer(
                    collateral_class=CollateralClass.RECEIVABLES,
                    track=CollateralTrack.TRACK_1_CLASSICAL, p4_admitted_value=25_000,
                ),
                CollateralOffer(
                    collateral_class=CollateralClass.EQUIPMENT,
                    track=CollateralTrack.TRACK_1_CLASSICAL, p4_admitted_value=10_000,
                ),
            ],
            rails_connected=["kyc", "bank_feed", "tax", "pos", "mobile_money", "accounting"],
        ),
        "behavior": {
            "outcome": "paid",
            "facility_amount": 45_000,
            "disbursed": 35_000,
            "currency": "USD",
            "tenure_months": 5,
            "repayments": _payments([
                {"interest": 550, "principal": 7_000, "month": 1},
                {"interest": 480, "principal": 7_000, "month": 2},
                {"interest": 410, "principal": 7_000, "month": 3},
                {"interest": 340, "principal": 7_000, "month": 4},
                {"interest": 270, "principal": 7_000, "month": 5},
            ]),
            "delinquent_month": None,
            "default_month": None,
            "recovered_amount": 0.0,
            "interest_rate_bps": _bps(35_000, 550),
        },
    },
    {
        "profile_id": "fatima",
        "name": "Fatima -- General Store",
        "first_name": "Fatima",
        "last_name": "General Store",
        "gender": "female",
        "age": 39,
        "city": "Muscat",
        "employer_name": "General Store",
        "employer_type": "private",
        "employment_years": 6.0,
        "monthly_salary": 3_200,
        "requested_amount": 25_000,
        "requested_tenure_months": 5,
        "story": {
            "data_tier": "good",
            "outcome": "default",
            "segment": "MICRO",
            "tagline": "Full data, but over-leveraged and defaulted.",
            "scenario": (
                "Six rails connected: same full data package as Nadia. But the "
                "actual values are terrible: high leverage (148k liabilities on "
                "32k equity), concentrated customers (72%), concentrated supplier "
                "(55%), 3 bounced payments, low account conduct. The engine has "
                "great data -- and uses it to identify real credit risk. Despite "
                "good data quality, the borrower defaults."
            ),
        },
        "application": BorrowerApplication(
            application_id="APP-FATIMA-306",
            segment=Segment.MICRO,
            operating_model=OperatingModel.GUARANTEE,
            model_maturity_stage=ModelMaturityStage.PRODUCTION,
            facility=FacilityRequest(
                product=Product.WORKING_CAPITAL_LINE,
                requested_amount=25_000, drawn_amount=20_000, undrawn_amount=5_000,
            ),
            financials=FinancialStatement(
                revenue=220_000, cost_of_sales=130_000, operating_expenses=35_000,
                net_profit=55_000, period_end=_TODAY - timedelta(days=15),
                total_assets=180_000, total_liabilities=148_000, equity=32_000,
                prior_period_revenue=195_000,
            ),
            cash_flow=CashFlowData(
                daily_net_cashflow=[680, 720, 650, 710, 690, 730, 670, 700, 740, 680],
                avg_daily_inflow=1100, debt_service_obligation=850,
                receivable_days=45, inventory_days=30, payable_days=15,
                bounced_items_count=3, months_of_history=10,
            ),
            business=BusinessProfile(
                sector_code="RETAIL_GENERAL", geography_code="MUSCAT",
                registration_date=_TODAY - timedelta(days=365 * 6),
                top5_customer_share=0.72, single_supplier_share=0.55,
            ),
            management=ManagementProfile(
                owner_experience_years=6.0, prior_default_history=False,
                has_governance_plan=True, account_conduct_score=0.45,
            ),
            collateral=[CollateralOffer(
                collateral_class=CollateralClass.RECEIVABLES,
                track=CollateralTrack.TRACK_1_CLASSICAL, p4_admitted_value=12_000,
            )],
            rails_connected=["kyc", "bank_feed", "tax", "pos", "mobile_money", "accounting"],
        ),
        "behavior": {
            "outcome": "default",
            "facility_amount": 25_000,
            "disbursed": 20_000,
            "currency": "USD",
            "tenure_months": 5,
            "repayments": _payments([
                {"interest": 350, "principal": 4_000, "month": 1},
                {"interest": 310, "principal": 4_000, "month": 2},
            ]),
            "delinquent_month": 3,
            "default_month": 4,
            "recovered_amount": 7_500,
            "interest_rate_bps": _bps(20_000, 350),
        },
    },
]


def list_seed_profiles() -> list[dict]:
    """FE-facing seed profile cards (data tier / outcome / tagline)."""
    return [
        {
            "profile_id": c["profile_id"],
            "name": c["name"],
            "data_tier": c["story"]["data_tier"],
            "outcome": c["story"]["outcome"],
            "segment": c["story"]["segment"],
            "tagline": c["story"]["tagline"],
            "scenario": c["story"]["scenario"],
            "requested_amount": c["requested_amount"],
            "disbursed": c["behavior"]["disbursed"],
            "currency": c["behavior"]["currency"],
        }
        for c in SEED_CANDIDATES
    ]


def get_seed_candidate(profile_id: str) -> dict | None:
    for c in SEED_CANDIDATES:
        if c["profile_id"] == profile_id:
            return c
    return None


async def seed_candidates_from_exports() -> int:
    """Import the demo candidates from ``data/candidates/*.json`` exports.

    This is the portable-carrier path the demo is meant to use: candidate
    rows are hydrated from the per-candidate JSON exports via the same
    ``import_candidate`` routine as ``POST /p1/candidates/import``, so there
    are no code-hardcoded profiles in the start-up path.  Idempotent — skips
    when the candidates table is already populated.

    Returns the number of rows imported (0 when already populated).
    """
    import json
    from pathlib import Path

    from sqlalchemy import func, select

    from bank.orchestrator.governance.database import async_session_factory
    from bank.pillars.p1.models import Candidate
    from bank.pillars.p1.schemas import CandidateImport
    from bank.pillars.p1.service import CandidateDuplicateError, service

    async with async_session_factory() as db:
        existing = (
            await db.execute(select(func.count()).select_from(Candidate))
        ).scalar() or 0
        if existing:
            return 0

    data_dir = Path(__file__).resolve().parents[4] / "data" / "candidates"
    count = 0
    for path in sorted(data_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        payload = CandidateImport.model_validate(raw)
        try:
            await service.import_candidate(payload, seed_profile=payload.seed_profile)
            count += 1
        except CandidateDuplicateError:
            # The borrower is already on the book — a second demo seed should
            # never build a duplicate row for the same person.
            continue
    return count


async def seed_candidates() -> int:
    """Insert the six seed candidates if the table is empty (idempotent).

    Returns the number of rows inserted (0 when already populated).
    """
    from sqlalchemy import func, select

    from bank.orchestrator.governance.database import async_session_factory
    from bank.pillars.p1.models import Candidate

    async with async_session_factory() as db:
        existing = (
            await db.execute(select(func.count()).select_from(Candidate))
        ).scalar() or 0
        if existing:
            return 0
        for c in SEED_CANDIDATES:
            behavior = c["behavior"]
            # RepaymentRow pydantic objects must be serialized to dicts for JSON storage.
            behavior_serializable = {
                **{k: v for k, v in behavior.items() if k != "repayments"},
                "repayments": [r.model_dump() if hasattr(r, "model_dump") else r for r in behavior["repayments"]],
            }
            cand = Candidate(
                seed_profile=c["profile_id"],
                first_name=c["first_name"],
                last_name=c["last_name"],
                gender=c["gender"],
                age=c["age"],
                city=c["city"],
                employer_name=c["employer_name"],
                employer_type=c["employer_type"],
                employment_years=c["employment_years"],
                monthly_salary=c["monthly_salary"],
                product="auto_loan",
                requested_amount=c["requested_amount"],
                requested_tenure_months=c["requested_tenure_months"],
                application_json=c["application"].model_dump(mode="json"),
                payment_behavior=behavior_serializable,
                sim_state={"current_month": 0, "payments_made": []},
            )
            db.add(cand)
        await db.commit()
    return len(SEED_CANDIDATES)