"""Seed script — populates all Orchestrator registries with canonical V3.4 content.

Populated from orchestrator_claude.md:
  - Canon versions + lineage + ratification (RI-1/2/3)
  - Master Lexicon categories and terms (Annex A)
  - Tier table + protection rules + Tier A insurance "sole locus"
  - The 7 interface rules (§6.1–§6.7)
  - CASS interface stub
  - Staging/Mode registry (Conventional, Stage 0, Gates PENDING)
  - PENDING register (Section 17.6 items)
  - Pillar boundaries (produces/consumes/decides/must_not_do)

Run via the CLI:  python -m orchestrator.seed.seed  (local)
or the FastAPI lifecycle / bootstrap function `run_seed`.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance import models
from bank.orchestrator.governance.database import async_session_factory

logger = logging.getLogger("orchestrator.seed")


CANON_VERSION = "3.4"


# ---------------------------------------------------------------------------
# Canon versions + lineage
# ---------------------------------------------------------------------------
CANON_VERSIONS = [
    {
        "version_number": "2.0",
        "name": "Orchestrator Canon V2.0",
        "status": "SUPERSEDED",
        "lineage_notes": "Three generations back. Stablecoin-only model. Superseded.",
    },
    {
        "version_number": "3.0",
        "name": "Orchestrator Canon V3.0 (merged)",
        "status": "SUPERSEDED",
        "lineage_notes": "Guarantee Model made operative; Stablecoin Model recorded as the ratified G->S migration target.",
    },
    {
        "version_number": "3.1",
        "name": "Orchestrator Canon V3.1",
        "status": "SUPERSEDED",
        "lineage_notes": "V3.1-G was an intermediate, already-superseded state on the path to V3.0-merged -> V3.4.",
    },
    {
        "version_number": "3.2",
        "name": "Orchestrator Canon V3.2",
        "status": "SUPERSEDED",
        "lineage_notes": "Struck the Guarantees-Granted/Received leverage ratio bound (now an ordinary Pillar 4 calibration parameter).",
    },
    {
        "version_number": "3.3",
        "name": "Orchestrator Canon V3.3",
        "status": "SUPERSEDED",
        "lineage_notes": "Harmonization pass; staging update.",
    },
    {
        "version_number": "3.4",
        "name": "Orchestrator Canon V3.4 (Ratified — Operative Canon)",
        "status": "RATIFIED",
        "ratified_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "ratification_instrument": "RI-1",
        "change_summary": (
            "Ratified per Ratification Instrument RI-1 (Governance Committee, July 2026). "
            "External-citation interdiction removed corpus-wide (RI-1 Resolution 4). "
            "Added Decision-Gate/Staging framework (Annex B, SI-1), Master Lexicon (Annex A), "
            "CASS interface stub, Guarantee Call (§6.7, PA-1), Migration-Coupling Rule (§2A.1), "
            "and tightened role separation (§6.3, §6.5)."
        ),
        "lineage_notes": "V2.0 -> V3.0-S/G (parallel siblings) -> V3.0 (merged) -> V3.1 -> V3.2 -> V3.3 -> V3.4. Head of the lineage.",
    },
]

RATIFICATION_INSTRUMENTS = [
    {
        "version_number": "3.4",
        "instrument_number": "RI-1",
        "resolution_ref": "Resolution 4",
        "description": "Ratified V3.4 and removed the external-citation interdiction corpus-wide. Operative Canon.",
    },
    {
        "version_number": "3.4",
        "instrument_number": "RI-2",
        "resolution_ref": None,
        "description": "Consolidation of scattered pillar-level glossaries into the single locked Master Lexicon (Annex A).",
    },
    {
        "version_number": "3.4",
        "instrument_number": "RI-3",
        "resolution_ref": "Resolution 3",
        "description": "Added the two-guarantee-layer transport scope and gate G0 criteria additions.",
    },
]


# ---------------------------------------------------------------------------
# Master Lexicon categories (Annex A)
# ---------------------------------------------------------------------------
LEXICON_CATEGORIES = [
    {
        "name": "Architecture and governance",
        "annex_ref": "A.1",
        "description": "APRBA, Clear-Advantage test, Conventional Mode, Adaptive Mode.",
        "sort_order": 1,
    },
    {
        "name": "Model vocabulary — G and S",
        "annex_ref": "A.2",
        "description": "Guarantee Intermediation [G], Stablecoin Deposit [S], loan execution record, smart contract.",
        "sort_order": 2,
    },
    {
        "name": "Collateral, guarantee, and pledge lifecycle",
        "annex_ref": "A.4",
        "description": "Two-Guarantee-Layer Rule, pledge, guarantee position, four-event discipline.",
        "sort_order": 3,
    },
    {
        "name": "Credit risk",
        "annex_ref": "A.5",
        "description": "Model Maturity Stage, MoC, DQS, IFRS9, TTC/PIT, EWS, decisioning zone.",
        "sort_order": 4,
    },
    {
        "name": "Execution, roles, and accounting",
        "annex_ref": "A.6",
        "description": "Pillar 2 credit officer, Pillar 3 risk officer, Pillar 3 event log.",
        "sort_order": 5,
    },
]


# ---------------------------------------------------------------------------
# Master Lexicon terms (Annex A excerpts)
# ---------------------------------------------------------------------------
LEXICON_TERMS = [
    # A.1 Architecture and governance
    {
        "term": "APRBA",
        "category": "Architecture and governance",
        "definition": "Adaptive Progressive Resolution Banking Architecture; Pillar 4's adaptive operating architecture (ABSF, CASS, buffer sub-accounts, Reverse Restoration Waterfall). Name locked.",
        "model_scope": "NEUTRAL",
        "abbreviation": "APRBA",
        "canon_section_ref": "§3/Annex A.1",
    },
    {
        "term": "Clear-Advantage test",
        "category": "Architecture and governance",
        "definition": "A blockchain/smart-contract mechanism is admitted only where it brings a distinctive, documented advantage over a conventional alternative for that specific function; burden of proof on the on-chain option. Now stated at the Orchestrator level (§14).",
        "model_scope": "NEUTRAL",
        "canon_section_ref": "§14",
    },
    {
        "term": "Conventional Mode",
        "category": "Architecture and governance",
        "definition": "The neo-bank operating with the full [G] tier structure and classical mechanics only; APRBA/ABSF/CASS/ERME not active; fully integrated with core banking. A Governance-Committee-controlled state. The permanent floor of the system.",
        "model_scope": "NEUTRAL",
        "is_new_in_v34": True,
        "canon_section_ref": "Annex B/SI-1",
    },
    {
        "term": "Adaptive Mode",
        "category": "Architecture and governance",
        "definition": "Conventional Mode plus the activated adaptive layer (APRBA, ABSF, CASS, ERME/ESV, Reverse Restoration Waterfall, Tier B-Fees mechanics). Reversion to Conventional Mode is a governance ruling, not a rebuild.",
        "model_scope": "NEUTRAL",
        "is_new_in_v34": True,
        "canon_section_ref": "Annex B/SI-1",
    },
    # A.2 Model vocabulary
    {
        "term": "Guarantee Intermediation Model",
        "category": "Model vocabulary — G and S",
        "definition": "[G] The single operative capital model. Guarantee providers collateralize; professional capital funds.",
        "model_scope": "G",
        "abbreviation": "[G]",
        "canon_section_ref": "§2A",
    },
    {
        "term": "Stablecoin Deposit Model",
        "category": "Model vocabulary — G and S",
        "definition": "[S] A ratified migration target, not a co-equal alternative. Not operative until a future version update activates it.",
        "model_scope": "S",
        "abbreviation": "[S]",
        "canon_section_ref": "§2A",
    },
    {
        "term": "loan execution record",
        "category": "Model vocabulary — G and S",
        "definition": "The model-neutral authoritative per-facility record; a conventional execution ledger under [G], a loan smart contract only under [S]. Replaces 'smart contract' in un-flagged text.",
        "model_scope": "NEUTRAL",
        "is_new_in_v34": True,
        "supersedes": "smart contract",
        "canon_section_ref": "§6.2/Annex A.2",
    },
    {
        "term": "smart contract",
        "category": "Model vocabulary — G and S",
        "definition": "Reserved to [S]-flagged text only. Under [G], the authoritative per-facility record is the loan execution record.",
        "model_scope": "S",
        "canon_section_ref": "Annex A.2",
    },
    {
        "term": "redemption",
        "category": "Model vocabulary — G and S",
        "definition": "Reserved to [S] only: a cash-based redemption-at-par mechanic. The [G] equivalent is pledge release.",
        "model_scope": "S",
        "canon_section_ref": "Annex A.4",
    },
    # A.4 Collateral, guarantee, pledge lifecycle
    {
        "term": "Two-Guarantee-Layer Rule",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "MSME-pledged collateral and the neo-bank pooled guarantee are two distinct, never-conflated objects. A stated rule, not a description.",
        "model_scope": "NEUTRAL",
        "canon_section_ref": "§6.2",
    },
    {
        "term": "pledge",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "[LX-1] The legal act of pledging. Distinct from the underlying asset (pledged RWA) and the economic position it creates (guarantee position).",
        "model_scope": "G",
        "canon_section_ref": "Annex A.4",
    },
    {
        "term": "pledged RWA",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "[LX-1] The underlying asset pledged as collateral. Real-world asset under [G].",
        "model_scope": "G",
        "abbreviation": "RWA",
        "canon_section_ref": "Annex A.4",
    },
    {
        "term": "guarantee position",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "[LX-1] The economic position created by a pledge — the contingent cash-equivalent position. Pooled-pledged as collateral.",
        "model_scope": "G",
        "canon_section_ref": "Annex A.4",
    },
    {
        "term": "pledge term",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "[LX-1] The term of a pledge. The [G] going-concern exit is pledge release (not redemption).",
        "model_scope": "G",
        "is_new_in_v34": True,
        "canon_section_ref": "Annex A.4",
    },
    {
        "term": "pledge release",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "[LX-1, RA-1] The [G] going-concern exit: the security interest is lifted, the asset exits custody, the contingent cash-equivalent position is extinguished; no cash moves. Post-term notice period; pre-term exception with penalty. The [G] equivalent of [S]'s redemption.",
        "model_scope": "G",
        "is_new_in_v34": True,
        "canon_section_ref": "§2A, RA-1",
    },
    {
        "term": "guarantee call",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "[LX-1, PA-1] The event in which the pooled guarantee is drawn to cover a loss and settled to the funders. Operates within existing tier protections and does not enter or expand the ABSF perimeter. New operative concept in V3.4 (§6.7).",
        "model_scope": "G",
        "is_new_in_v34": True,
        "canon_section_ref": "§6.7, PA-1",
    },
    {
        "term": "Four-Event Discipline",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "release ≠ redemption ≠ foreclosure ≠ call. No document may use one term for another.",
        "model_scope": "NEUTRAL",
        "canon_section_ref": "Annex A.4",
    },
    {
        "term": "foreclosure",
        "category": "Collateral, guarantee, and pledge lifecycle",
        "definition": "Classical foreclosure in liquidation — the [G] Tier B principal realization. Distinct from guarantee call and pledge release.",
        "model_scope": "G",
        "canon_section_ref": "Annex A.4",
    },
    # A.5 Credit risk
    {
        "term": "Model Maturity Stage",
        "category": "Credit risk",
        "definition": "DESIGN -> SANDBOX -> PRODUCTION. Governs deployment readiness of Pillar 2 models.",
        "model_scope": "NEUTRAL",
        "canon_section_ref": "Annex A.5",
    },
    {
        "term": "MoC",
        "category": "Credit risk",
        "definition": "Margin of Conservatism. Applied if DQS is low.",
        "model_scope": "NEUTRAL",
        "abbreviation": "MoC",
        "canon_section_ref": "Annex A.5",
    },
    {
        "term": "DQS",
        "category": "Credit risk",
        "definition": "Data Quality Score. Gates the confidence in Pillar 2 outputs.",
        "model_scope": "NEUTRAL",
        "abbreviation": "DQS",
        "canon_section_ref": "Annex A.5",
    },
    {
        "term": "decisioning zone",
        "category": "Credit risk",
        "definition": "The decisioning branch: auto-approve / augmented / manual review. Determined jointly at origination.",
        "model_scope": "NEUTRAL",
        "canon_section_ref": "Annex A.5",
    },
    # A.6 Execution, roles, and accounting
    {
        "term": "Pillar 2 credit officer",
        "category": "Execution, roles, and accounting",
        "definition": "The human decision owner for credit, including all posterior restructuring/recovery/workout decisions. New explicit role in V3.4.",
        "model_scope": "NEUTRAL",
        "is_new_in_v34": True,
        "canon_section_ref": "§6.5",
    },
    {
        "term": "Pillar 3 risk officer",
        "category": "Execution, roles, and accounting",
        "definition": "The human follow-up owner for the loan lifecycle; detection and routing only, no decision authority. Takes no credit, prudential, or allocation decision.",
        "model_scope": "NEUTRAL",
        "is_new_in_v34": True,
        "canon_section_ref": "§6.5",
    },
    {
        "term": "Pillar 3 event log",
        "category": "Execution, roles, and accounting",
        "definition": "Replaces 'P3 shadow ledger' corpus-wide. The source of the postings, not a competing system of record; holds no independent accounting authority. The renaming is a documented consequence of the Clear-Advantage test retiring the on-chain stablecoin shadow ledger.",
        "model_scope": "NEUTRAL",
        "supersedes": "P3 shadow ledger",
        "is_new_in_v34": True,
        "canon_section_ref": "§6.4",
    },
    {
        "term": "do-not-resolve-in-code",
        "category": "Execution, roles, and accounting",
        "definition": "A standing rule codified in the Master Lexicon: certain cross-pillar PENDING items must not be resolved unilaterally in code. They require explicit governance resolution. Items must be raised to governance, not assumed.",
        "model_scope": "NEUTRAL",
        "canon_section_ref": "§13/Annex A",
    },
    {
        "term": "Migration-Coupling Rule [S]",
        "category": "Execution, roles, and accounting",
        "definition": "§2A.1: The chain-posture decision for Pillar 3's surviving on-chain function and Pillar 5's stablecoin issuance-venue determination shall be taken jointly at G->S migration. Under operative [G], no chain-posture decision is required or taken at all — dormant, pre-registered.",
        "model_scope": "S",
        "is_new_in_v34": True,
        "canon_section_ref": "§2A.1",
    },
]


# ---------------------------------------------------------------------------
# Tier table + protection rules
# ---------------------------------------------------------------------------
TIERS = [
    {
        "tier_label": "A",
        "tier_name": "Guarantee positions (Tier A)",
        "model_scope": "G",
        "description": "Guarantee positions — RWA pledged for a fee, contingent cash equivalents, pooled-pledged as collateral.",
        "insurance_status": "Conditional (CBO-dependent). Governed by §4.6 (sole locus).",
        "insurance_status_authority": "Orchestrator Canon §4.6 (sole locus)",
        "sort_order": 4,
        "canon_section_ref": "§4",
    },
    {
        "tier_label": "B",
        "tier_name": "Subordinated capital (Tier B)",
        "model_scope": "G",
        "description": "Subordinated capital layer, with Tier B-Fees mechanics in Adaptive Mode.",
        "insurance_status": None,
        "insurance_status_authority": None,
        "sort_order": 3,
        "canon_section_ref": "§4",
    },
    {
        "tier_label": "C",
        "tier_name": "Tier C — loss-absorption capital / funder",
        "model_scope": "G",
        "description": "Additional loss-absorption capital. A funder beneficiary in Guarantee Call settlement.",
        "insurance_status": None,
        "insurance_status_authority": None,
        "sort_order": 2,
        "canon_section_ref": "§4",
    },
    {
        "tier_label": "D",
        "tier_name": "Tier D — AT1 and Common Equity",
        "model_scope": "G",
        "description": "AT1 (Additional Tier 1) and CE (Common Equity). Most loss-exposed. A funder beneficiary in Guarantee Call settlement.",
        "insurance_status": None,
        "insurance_status_authority": None,
        "sort_order": 1,
        "canon_section_ref": "§4",
    },
]

TIER_PROTECTION_RULES = [
    {
        "source": "D",
        "target": "C",
        "direction": "PROTECTS",
        "description": "Tier D absorbs losses first, protecting Tier C.",
    },
    {
        "source": "C",
        "target": "B",
        "direction": "PROTECTS",
        "description": "Tier C protects Tier B.",
    },
    {
        "source": "B",
        "target": "A",
        "direction": "PROTECTS",
        "description": "Tier B protects Tier A.",
    },
    {
        "source": "A",
        "target": "D",
        "direction": "ABSORBS_LOSS_FROM",
        "description": "Tier A absorbs losses from Tier D (inverse view).",
    },
]


# ---------------------------------------------------------------------------
# Pillar boundaries
# ---------------------------------------------------------------------------
PILLARS = [
    {
        "pillar_number": 1,
        "pillar_name": "MSME engagement and data acquisition",
        "produces": ["Standardized feature store", "MSME data"],
        "consumes": [],
        "decides": [],
        "must_not_do": [
            "lending decisions",
            "credit scoring",
            "loan execution",
            "prudential policy",
        ],
        "canon_section_ref": "§5",
    },
    {
        "pillar_number": 2,
        "pillar_name": "AI/ML credit scoring and risk-rating engine",
        "produces": [
            "BRR/PD",
            "MoC outputs",
            "IFRS 9 staging signal",
            "CASS feed",
            "Output packet (approved/provisional/conditional)",
            "Admissibility operation for individual case",
        ],
        "consumes": ["Feature store (P1)", "Admissibility policy (P4)", "Case transfer (P3 risk officer)"],
        "decides": [
            "facility approval/pricing/risk premium",
            "individual-case collateral admissibility and haircut",
            "restructuring/recovery/workout decisions (credit officer)",
        ],
        "must_not_do": [
            "loan execution",
            "per-loan accounting",
            "setting prudential policy",
            "govern Pillar 5 internal risk/tokenization logic",
        ],
        "canon_section_ref": "§5/§6.3/§6.5",
    },
    {
        "pillar_number": 3,
        "pillar_name": "Deterministic loan execution layer",
        "produces": [
            "Loan execution record entries",
            "Pillar 3 event log postings",
            "Default/call event records",
            "Lifecycle deterioration detection (risk officer)",
        ],
        "consumes": ["Confirmed output packet (P2)", "Posting set"],
        "decides": [],
        "must_not_do": [
            "credit decisions",
            "prudential decisions",
            "allocation decisions",
            "act on a facility absent a confirmed human-authorised P2 packet",
            "take any decision (risk officer is detection/routing only)",
        ],
        "canon_section_ref": "§5/§6.5/§6.7",
    },
    {
        "pillar_number": 4,
        "pillar_name": "Prudential capital, liquidity, and loss-absorption layer",
        "produces": [
            "Admissibility policy (asset types, haircuts, concentration limits)",
            "CASS computation",
            "ABSF weights (in Adaptive Mode)",
            "Guarantee Call computation/settlement",
            "Reverse Restoration Waterfall (in Adaptive Mode)",
        ],
        "consumes": ["CASS feed (P2)", "IFRS 9 staging (P2)", "Portfolio allocation routes (P3)"],
        "decides": [
            "what the admissibility policy is",
            "whether a guarantee call is settled and how",
        ],
        "must_not_do": [
            "enter the individual case",
            "direct per-loan interface with Pillar 3",
            "govern Pillar 5 internal risk/tokenization logic",
        ],
        "canon_section_ref": "§5/§6.3/§6.7",
    },
    {
        "pillar_number": 5,
        "pillar_name": "External pledge-guarantee/RWA tokenization and custody",
        "produces": ["Pledge guarantee/NFT collateral submissions", "Pledged RWA"],
        "consumes": ["Admissibility interface (P4)"],
        "decides": [
            "its own internal risk/tokenization logic",
        ],
        "must_not_do": [
            "originate lending",
            "decide credit",
        ],
        "canon_section_ref": "§5/§7",
    },
]


# ---------------------------------------------------------------------------
# 7 interface rules (§6.1–§6.7)
# ---------------------------------------------------------------------------
INTERFACES = [
    {
        "rule_number": "6.1",
        "name": "IFRS 9 Staging Signal",
        "description": "Pillar 2 sends an IFRS 9 staging migration signal directly to Pillar 4, bypassing Pillar 3 entirely; a staging migration triggers no Pillar 3 covenant or freeze.",
        "direction": "P2_TO_P4",
        "decides_who": "P2",
        "executes_who": "P4",
        "bypasses_pillar3": True,
        "canon_section_ref": "§6.1",
        "notable_v34_change": "None",
    },
    {
        "rule_number": "6.2",
        "name": "Loan Execution Record & Two-Guarantee-Layer Rule",
        "description": "The model-neutral authoritative per-facility record plus the Two-Guarantee-Layer Rule (MSME-pledged collateral and the neo-bank pooled guarantee are two distinct objects). Field-level data contract across P2/P3/P4 is PENDING, including transport of the pooled-guarantee level (grain, identity, revision trigger, failure semantics) per RI-3.",
        "direction": "STRUCTURAL",
        "decides_who": "P2 (sizes pooled guarantee)",
        "executes_who": "P3 (records), P4 (holds)",
        "bypasses_pillar3": False,
        "canon_section_ref": "§6.2",
        "notable_v34_change": "Terminology; transport now in-scope for the PENDING data contract (RI-3).",
    },
    {
        "rule_number": "6.3",
        "name": "Admissibility — P4 -> P2 -> P3",
        "description": "Pillar 4 sets policy only; Pillar 2 operates the individual case (adopts haircut-adjusted value, recalculates LGD/EL, issues revised packet); Pillar 3 records only on the validated packet. No other routing permitted. 'Pillar 4 does not enter the individual case.'",
        "direction": "CHAINED_P4_P2_P3",
        "decides_who": "P4 (policy) + P2 (individual case)",
        "executes_who": "P3 (recording)",
        "bypasses_pillar3": False,
        "canon_section_ref": "§6.3",
        "notable_v34_change": "Role split revised — Pillar 2, not Pillar 4, now operates the individual case.",
    },
    {
        "rule_number": "6.4",
        "name": "Pillars 3 Event Log / Core Banking System-of-Record",
        "description": "Pillar 3 produces the event log — the source of the postings, not a competing system of record, holding no independent accounting authority. Core banking prevails in any reconciliation dispute.",
        "direction": "BIDIRECTIONAL_P3_COREBANKING",
        "decides_who": "Core banking",
        "executes_who": "P3 (event log)",
        "bypasses_pillar3": False,
        "canon_section_ref": "§6.4",
        "notable_v34_change": "Terminology: 'shadow ledger' -> 'event log'.",
    },
    {
        "rule_number": "6.5",
        "name": "Restructuring and Recovery Decision Ownership",
        "description": "Pillar 2 credit officer originates and decides at origination and on all posterior events. Pillar 3 risk officer follows up lifecycle events, identifies intervention needs, and transfers cases to Pillar 2 — detection and routing only. Pillar 3 (execution) acts only on a confirmed, human-authorised P2 packet.",
        "direction": "CHAINED_P3_P2",
        "decides_who": "P2 credit officer",
        "executes_who": "P3 risk officer (detect/route), P3 execution (act on confirmed packet)",
        "bypasses_pillar3": False,
        "canon_section_ref": "§6.5",
        "notable_v34_change": "New explicit two-role split within Pillar 3's boundary.",
    },
    {
        "rule_number": "6.6",
        "name": "CASS and ERME Data Feeds -> P4",
        "description": "Pillar 2 sends CASS feed (contract shape per Orchestrator interface stub) + IFRS 9 staging to Pillar 4, bypassing Pillar 3. ERME data is advisory. The Orchestrator issues the CASS interface stub unblocking design while the full P2+P4 specification remains PENDING. Signal derivation (P2) and consumption (P4) are outside the stub's scope.",
        "direction": "P2_TO_P4",
        "decides_who": "P2 (CASS), ERME (advisory)",
        "executes_who": "P4",
        "bypasses_pillar3": True,
        "canon_section_ref": "§6.6",
        "notable_v34_change": "Orchestrator issues interface stub, unblocking design without resolving the full spec.",
    },
    {
        "rule_number": "6.7",
        "name": "Guarantee Call — Guarantee Leg of Default Realization",
        "description": "When a facility loss crystallizes and the neo-bank pooled guarantee is drawn, that draw is a guarantee call. Pillar 3 records the default event and call as event-log entries (micro, no allocation logic, routes per §6.5). Pillar 4 computes and settles the draw through reserve/provision sub-accounts to the funders (SID, Tier C, Tier D). Operates independently of, and does not feed into, the ABSF perimeter.",
        "direction": "CHAINED_P3_P4_FUNDERS",
        "decides_who": "P4 (computation/settlement)",
        "executes_who": "P3 (records only)",
        "bypasses_pillar3": False,
        "canon_section_ref": "§6.7, PA-1",
        "notable_v34_change": "Entirely new interface (§6.7, PA-1).",
    },
]


# ---------------------------------------------------------------------------
# CASS interface stub
# ---------------------------------------------------------------------------
CASS_STUB = {
    "version": "CIS-1",
    "issued_by": "Orchestrator",
    "scope": (
        "Contract shape only — field set, cardinality, refresh cadence, failure semantics. "
        "Signal derivation (Pillar 2) and consumption logic (Pillar 4) are never resolved here; "
        "they are explicitly outside the stub's scope."
    ),
    "source_pillar": "P2",
    "dest_pillar": "P4",
    "refresh_cadence": "Event-triggered + daily recalibration",
    "failure_semantics": (
        "In-scope for the stub but content PENDING — please request the standalone CASS Interface Stub "
        "CIS-1 V1.0 artifact for the actual failure-semantics values."
    ),
    "fields": [
        {"field_name": "facility_id", "field_type": "string", "cardinality": "1", "is_derived": False, "is_consumed": False},
        {"field_name": "cass_value", "field_type": "decimal", "cardinality": "1", "is_derived": True, "is_consumed": False},
        {"field_name": "stage", "field_type": "string", "cardinality": "1", "is_derived": True, "is_consumed": False},
        {"field_name": "ifrs9_stage", "field_type": "integer", "cardinality": "1", "is_derived": True, "is_consumed": False},
        {"field_name": "as_at", "field_type": "datetime", "cardinality": "1", "is_derived": False, "is_consumed": False},
    ],
}


# ---------------------------------------------------------------------------
# Staging / Mode registry initial state
# ---------------------------------------------------------------------------
STAGING_INIT = {
    "current_mode": "CONVENTIONAL",
    "fallback_guarantee": "Conventional Mode is the permanent floor of the system",
    "changed_by": "Governance Committee (seed)",
    "change_rationale": "System must start in Conventional Mode (mandatory floor). Per SI-1.",
    "current_stage": 0,
    "gates": [
        {
            "gate_label": "G0",
            "status": "PENDING",
            "criteria": "Gate criteria PENDING — Governance Committee to calibrate. Per RI-3, the two-guarantee-layer contract is added to G0 criteria.",
        },
        {
            "gate_label": "G1",
            "status": "PENDING",
            "criteria": "Gates the first actual CASS computation; requires the full P2+P4 CASS specification (not just the Orchestrator's interface stub).",
        },
        {
            "gate_label": "G2",
            "status": "PENDING",
            "criteria": "Not detailed in supplied V3.4 text.",
        },
        {
            "gate_label": "G3",
            "status": "PENDING",
            "criteria": "Not detailed in supplied V3.4 text.",
        },
    ],
}


# ---------------------------------------------------------------------------
# PENDING register — Section 17.6 / 13 / 17 open items
# ---------------------------------------------------------------------------
PENDING_ITEMS = [
    {
        "title": "Pillar 2 Canon V4.3 (current) not supplied",
        "description": "V3.4 points to Pillar 2 Canon V4.3 as current; not supplied. Highest-priority follow-up.",
        "category": "DOCUMENTATION",
        "registered_in_canon": "§17.2",
        "priority": "CRITICAL",
    },
    {
        "title": "Pillar 4 Canon V2.1/V2.2 (current) not supplied — internal inconsistency",
        "description": "V3.4's version-history table names V2.1, its closing status block names V2.2. Requires resolution of which is current.",
        "category": "DOCUMENTATION",
        "registered_in_canon": "§17.2/§0.2",
        "priority": "CRITICAL",
    },
    {
        "title": "Staging Instrument SI-1 standalone document not supplied",
        "description": "Only Annex B's existence and shape are known; actual Gate G0-G3 criteria are PENDING pending Governance Committee calibration.",
        "category": "GATE_CRITERIA",
        "registered_in_canon": "§17.4/§5.5",
        "priority": "HIGH",
    },
    {
        "title": "Loan execution record & Two-Guarantee-Layer field-level data contract",
        "description": "The data-contract implementation across P2/P3/P4 is PENDING — including transport of the pooled-guarantee level (grain, identity, revision trigger, failure semantics) per RI-3.",
        "category": "DATA_CONTRACT",
        "registered_in_canon": "§13/§6.2",
        "priority": "HIGH",
    },
    {
        "title": "Full P2+P4 CASS specification",
        "description": "Methodology, component weights alpha/beta/gamma/delta, zone boundaries, participation-weight schedule, and the definitional overlap between the F component's EL input and the EL underlying the S component via the EL Pool (per RI-3).",
        "category": "MECHANICS",
        "registered_in_canon": "§17.7",
        "priority": "HIGH",
    },
    {
        "title": "Guarantee Call settlement ledger-level mechanics",
        "description": "Existence/direction/non-interaction with ABSF documented (Pillar 4 Canon §4.4.5 named); ledger-level mechanics not verifiable against supplied documents.",
        "category": "MECHANICS",
        "registered_in_canon": "§6.7/§17.8",
        "priority": "HIGH",
    },
    {
        "title": "CASS trigger-zone boundaries",
        "description": "CASS trigger-zone boundaries remain PENDING.",
        "category": "INTERFACE",
        "registered_in_canon": "§17.7",
        "priority": "MEDIUM",
    },
    {
        "title": "No timeout/SLA for governance review before restart",
        "description": "No timeout or SLA documented for 'governance review before restart' following a prudential veto freeze.",
        "category": "GOVERNANCE",
        "registered_in_canon": "§17.6",
        "priority": "LOW",
    },
    {
        "title": "CASS interface stub failure semantics content",
        "description": "Failure semantics named as in-scope for the Orchestrator CASS interface stub, but content not included in supplied V3.4 text — request the standalone stub artifact.",
        "category": "INTERFACE",
        "registered_in_canon": "§13",
        "priority": "MEDIUM",
    },
]


# ---------------------------------------------------------------------------
# Seed runners
# ---------------------------------------------------------------------------
async def seed(db: AsyncSession) -> None:
    """Populate all registries. Idempotent — safe to run multiple times."""

    # 1. Canon versions
    for cv in CANON_VERSIONS:
        existing = await db.execute(
            select(models.CanonVersion).where(
                models.CanonVersion.version_number == cv["version_number"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        data = dict(cv)
        data["is_current"] = data.get("version_number") == CANON_VERSION
        db.add(models.CanonVersion(**data))

    # 2. Ratification instruments
    for ri in RATIFICATION_INSTRUMENTS:
        canon_result = await db.execute(
            select(models.CanonVersion)
            .where(models.CanonVersion.version_number == ri["version_number"])
            .limit(1)
        )
        canon = canon_result.scalar_one_or_none()
        if not canon:
            continue
        existing = await db.execute(
            select(models.RatificationInstrument)
            .where(
                models.RatificationInstrument.instrument_number == ri["instrument_number"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            models.RatificationInstrument(
                canon_version_id=canon.id,
                instrument_number=ri["instrument_number"],
                resolution_ref=ri["resolution_ref"],
                description=ri["description"],
                ratified_at=datetime.now(timezone.utc),
            )
        )

    # 3. Lexicon categories (collect id map for terms)
    category_ids = {}
    for cat in LEXICON_CATEGORIES:
        existing = await db.execute(
            select(models.LexiconCategory).where(
                models.LexiconCategory.name == cat["name"]
            )
        )
        c = existing.scalar_one_or_none()
        if not c:
            c = models.LexiconCategory(**cat)
            db.add(c)
            await db.flush()
        category_ids[c.name] = c.id

    # 4. Lexicon terms
    for term in LEXICON_TERMS:
        existing = await db.execute(
            select(models.LexiconTerm).where(
                models.LexiconTerm.term == term["term"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        cat_id = category_ids.get(term["category"])
        db.add(
            models.LexiconTerm(
                category_id=cat_id,
                term=term["term"],
                abbreviation=term.get("abbreviation"),
                definition=term["definition"],
                model_scope=term.get("model_scope", "NEUTRAL"),
                canon_section_ref=term.get("canon_section_ref"),
                is_new_in_v34=term.get("is_new_in_v34", False),
                supersedes=term.get("supersedes"),
            )
        )

    # 5. Tiers (collect labels for protection rules)
    tier_ids = {}
    for t in TIERS:
        existing = await db.execute(
            select(models.TierDefinition).where(
                models.TierDefinition.tier_label == t["tier_label"]
            )
        )
        tier = existing.scalar_one_or_none()
        if not tier:
            tier = models.TierDefinition(**t)
            db.add(tier)
            await db.flush()
        tier_ids[t["tier_label"]] = tier.id

    # 6. Protection rules
    for pr in TIER_PROTECTION_RULES:
        existing = await db.execute(
            select(models.TierProtectionRule)
            .where(
                models.TierProtectionRule.source_tier_id == tier_ids[pr["source"]],
                models.TierProtectionRule.target_tier_id == tier_ids[pr["target"]],
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            models.TierProtectionRule(
                source_tier_id=tier_ids[pr["source"]],
                target_tier_id=tier_ids[pr["target"]],
                direction=pr["direction"],
                description=pr["description"],
            )
        )

    # 7. Pillar boundaries
    for p in PILLARS:
        existing = await db.execute(
            select(models.PillarBoundary).where(
                models.PillarBoundary.pillar_number == p["pillar_number"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            models.PillarBoundary(
                pillar_number=p["pillar_number"],
                pillar_name=p["pillar_name"],
                produces=p["produces"],
                consumes=p["consumes"],
                decides=p["decides"],
                must_not_do=p["must_not_do"],
                canon_section_ref=p["canon_section_ref"],
            )
        )

    # 8. Interface rules + fields
    for iface in INTERFACES:
        existing = await db.execute(
            select(models.InterfaceRule).where(
                models.InterfaceRule.rule_number == iface["rule_number"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(models.InterfaceRule(**iface))

    # 9. CASS stub
    stub_existing = await db.execute(select(models.CassStubMetadata))
    if not stub_existing.scalar_one_or_none():
        stub = models.CassStubMetadata(
            version=CASS_STUB["version"],
            issued_by=CASS_STUB["issued_by"],
            scope=CASS_STUB["scope"],
            source_pillar=CASS_STUB["source_pillar"],
            dest_pillar=CASS_STUB["dest_pillar"],
            refresh_cadence=CASS_STUB["refresh_cadence"],
            failure_semantics=CASS_STUB["failure_semantics"],
        )
        db.add(stub)
        await db.flush()
        for f in CASS_STUB["fields"]:
            db.add(
                models.CassStubField(
                    stub_metadata_id=stub.id,
                    field_name=f["field_name"],
                    field_type=f["field_type"],
                    cardinality=f.get("cardinality", "1"),
                    description=f.get("description"),
                    is_derived=f.get("is_derived", False),
                    is_consumed=f.get("is_consumed", False),
                )
            )

    # 10. Staging / Mode
    mode_existing = await db.execute(select(models.ModeState))
    if not mode_existing.scalar_one_or_none():
        db.add(
            models.ModeState(
                current_mode=STAGING_INIT["current_mode"],
                fallback_guarantee=STAGING_INIT["fallback_guarantee"],
                changed_by=STAGING_INIT["changed_by"],
                change_rationale=STAGING_INIT["change_rationale"],
                changed_at=datetime.now(timezone.utc),
            )
        )

    stage_existing = await db.execute(select(models.StageState))
    if not stage_existing.scalar_one_or_none():
        db.add(
            models.StageState(
                current_stage=STAGING_INIT["current_stage"],
                changed_at=datetime.now(timezone.utc),
            )
        )

    for g in STAGING_INIT["gates"]:
        gate_existing = await db.execute(
            select(models.GateState).where(
                models.GateState.gate_label == g["gate_label"]
            )
        )
        if gate_existing.scalar_one_or_none():
            continue
        db.add(
            models.GateState(
                gate_label=g["gate_label"],
                status=g["status"],
                criteria=g["criteria"],
            )
        )

    # 11. PENDING items
    pending_index = 1
    for p in PENDING_ITEMS:
        existing = await db.execute(
            select(models.PendingItem).where(
                models.PendingItem.title == p["title"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            models.PendingItem(
                item_number=f"P-{pending_index:03d}",
                title=p["title"],
                description=p["description"],
                category=p["category"],
                registered_in_canon=p.get("registered_in_canon"),
                priority=p.get("priority", "MEDIUM"),
                status="OPEN",
            )
        )
        pending_index += 1

    await db.commit()
    logger.info("Orchestrator seed completed against Canon %s.", CANON_VERSION)


async def run_seed() -> None:
    async with async_session_factory() as db:
        await seed(db)


def main() -> None:
    """CLI entry point: python -m orchestrator.seed.seed"""
    asyncio.run(run_seed())
    print("Seeding complete.")


if __name__ == "__main__":
    main()
