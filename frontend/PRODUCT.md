# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript (single-page app). Talks to the Bank Orchestrator v3.4.0 REST API at `http://localhost:8000` (flat JSON, ISO-8601 datetimes, enums as plain strings) and to the SSE stream `GET /p1/demo/events/sse`. Types should be generated from the backend OpenAPI schema.

## Users

One admin user for now: a bank staff member who runs MSME loan originations end to end and monitors the book. The tool is used for stakeholder demos first (driven by the demo loop: seed, monthly tick, reset), then as a real back-office operator tool. Other personas (loan officer, risk officer, CRO, finance, governance admin) exist in the domain but are folded into the single admin for now.

## Product Purpose

Front-end for a neo-bank that lends to micro, small and medium enterprises. It lets the admin move a borrower from intake to a disbursed facility, see why the credit engine scored it as it did, run the loan lifecycle, and watch whether the bank's capital stays safe. Success: the full golden path (create, submit, score, approve, disburse, tick) is understandable at a glance in a demo and fast to operate for real.

## Positioning

The platform separates responsibilities into four pillars under a governance layer: Pillar 1 intake, Pillar 2 credit scoring (BRR, PD, LGD, EAD, EL, three decision zones), Pillar 3 loan execution and core-banking ledger, Pillar 4 prudential layer that can veto new lending (Track 1 portfolio freeze, Track 2 facility freeze). A human officer approval is always required (MANUAL_APPROVAL_ALWAYS), even in the AUTO_APPROVE zone. The front-end must make these boundaries and the veto state visible rather than hide them.

## Operating Context

- Admin works at a desktop; demos are screen-shared or projected.
- Demo controls (seed profiles, advance one month, factory reset) must stay reachable while the app is also a real tool.
- Live state arrives by SSE (`state_update`, `tick`, `reset`, 30 s keep-alive) with `GET /p1/demo/state` as polling fallback.
- Source documents: `DOCS/neo-bank-api-playbook.pdf` (full API), `DOCS/NeoBank_logique_metier.pdf` (business logic summary).

## Capabilities and Constraints

- Areas: loan pipeline (candidates new / submitted / approved / disbursed / rejected), candidate intake + score card + approval + disbursement, facilities (list, detail, lifecycle actions: repayment, delinquent, default, restructure, recovery, close; audit, postings, ledger, reconcile), prudential dashboard (EL Pool, ULA Buffer, Liquidity Reserve, RP Pool; Tier D / RWA vs 12% floor; portfolio EL vs 2% Budgeted Loss; guarantee-pool adequacy; IFRS 9 map; veto state and notifications; Conventional / Adaptive mode), bilan (French PCG balance sheet), governance console.
- Errors: body `{"detail": ...}`; 404 unknown id, 409 veto / state-machine conflict / governance PENDING (explain, never offer blind retry), 422 validation.
- Authentication: skipped for now (backend has none). `PUT /bilan/config` needs an `X-Admin-Token` header.
- Language: English only for now; no Arabic / RTL (the `name_ar` field is still stored and may be displayed as data).
- BRR: standard scale; exact grid comes from `GET /p2/v1/brr-pd-grid`.
- Currency defaults to USD.
- Undecided: exact facility state strings (read from `GET /p3/facilities`), future multi-role auth.

## Evidence on Hand

- Demo seed profiles from `GET /p1/demo/profiles`; no real customer data, testimonials or metrics exist. Never fabricate borrowers, figures or regulatory claims in the UI beyond what the API returns.

## Product Principles

1. The golden path is the spine: every screen should make clear where a borrower or loan sits in create, score, approve, disburse, perform.
2. Show the reason, not just the result: scores, zones, vetoes and 409s always carry their cause.
3. Human approval is never implied or skipped.
4. Pillar boundaries are product truth; keep each pillar's data and actions in their own place.
5. Demo-ready and operator-fast at once: the story reads in a demo without slowing down real work.

## Accessibility & Inclusion

No product-specific standard confirmed; default to WCAG 2.2 AA. Risk states must never rely on color alone (veto, zone, IFRS 9 stage carry text labels).
