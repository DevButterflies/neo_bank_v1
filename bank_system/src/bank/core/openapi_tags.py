"""OpenAPI tag metadata — the human-readable grouping of the API playbook.

Every tag that appears on any operation across the root app and the five
mounted sub-apps (governance, P1, P2, P3, P4) is described here so the
unified Swagger UI at ``/docs`` presents the API as one organized playbook.
"""

from __future__ import annotations

OPENAPI_TAGS = [
    {
        "name": "system",
        "description": "Platform probes: liveness (``/health``) and the "
        "restart-ok readiness check (``/ready``) that re-opens fresh Pillar "
        "3/4 runtimes and asserts a byte-identical snapshot round-trip.",
    },
    {
        "name": "bilan",
        "description": "French-PCG balance sheet (Actif/Passif) computed live "
        "from the shared Pillar 3/4 store, its invariant checks, memo "
        "(hors-bilan) items, and the admin-gated opening config.",
    },
    {
        "name": "p1",
        "description": "Pillar 1 — borrower intake: create/import candidates, "
        "run the origination flow (submit → score → approve → disburse), and "
        "read candidate state. Demo harness, not a lending authority.",
    },
    {
        "name": "p1-demo",
        "description": "Pillar 1 demo loop — SSE event stream, board state, "
        "simulation tick, seed profiles and factory reset.",
    },
    {
        "name": "pillar2",
        "description": "Pillar 2 — credit scoring & risk rating: BRR scoring, "
        "PD/LGD/EAD/EL, the versioned BRR→PD grid, early-warning signals, "
        "override records, and the CASS feed contract.",
    },
    {
        "name": "pillar3",
        "description": "Pillar 3 — loan lifecycle & execution: facilities, "
        "P2 packets, audit trail, postings, core-banking ledger, "
        "reconciliation, and the state-machine actions (originate, disburse, "
        "repayment, default, restructure, recovery, close). No allocation "
        "logic lives here.",
    },
    {
        "name": "pillar4",
        "description": "Pillar 4 — prudential layer: buffer sub-account "
        "balances, guarantee-pool adequacy, capital snapshot (Tier D/RWA, "
        "portfolio EL, G/G ratio), IFRS 9 staging, the two-track veto, "
        "mode gate, and pledge intake/release. Veto state resolves at "
        "Pillar 2 — Pillar 3 never sees a veto event.",
    },
    {
        "name": "canon",
        "description": "Orchestrator governance — canon versions, ratification "
        "and lineage.",
    },
    {
        "name": "lexicon",
        "description": "Master Lexicon — locked terms and the rename map.",
    },
    {
        "name": "tiers-and-pillars",
        "description": "Canonical tier table (Tier A/B/Senior Debt/C/B-Fees/D), "
        "insurance status (sole-locus rule) and pillar boundary/perimeter "
        "checks.",
    },
    {
        "name": "interface-rules",
        "description": "Inter-pillar interface rules (§6) and flow validation.",
    },
    {
        "name": "cass-stub",
        "description": "CASS interface stub (CIS-1) — the contract shape only; "
        "the full methodology is PENDING and blocks Gate G1.",
    },
    {
        "name": "staging-mode",
        "description": "SI-1 staging registry — bank-wide mode (Conventional / "
        "Adaptive), build stage, and gate states G0–G3.",
    },
    {
        "name": "change-control",
        "description": "Amendment proposals, dependency review, ratification "
        "and rejection.",
    },
    {
        "name": "veto-log",
        "description": "Immutable log of veto freeze events and their "
        "resolution.",
    },
    {
        "name": "pending-register",
        "description": "Governance PENDING items — named stops that must never "
        "be silently resolved in code.",
    },
    {
        "name": "health",
        "description": "Sub-app liveness probes.",
    },
]
