# Bank System — Complete Engineering & API Reference

> **Audience:** front-end / integration engineers who must build a UI against this
> system using **only this document**. It is the full technical map: the business
> model, every service, every HTTP route, every data schema with field-by-field
> explanation, the persistence/restart guarantees, and the end-to-end data flows.
>
> **Reading order:** §1 (what this is) → §2 (one-page architecture) → §3 (run it)
> → §4 (global routes) → §5 (Pillar 1 intake & lifecycle) → §6 (Pillar 2) →
> §7 (Pillar 3) → §8 (Pillar 4) → §9 (governance) → §10 (orchestrator internals)
> → §11 (the live demo: state, SSE, tick, reset) → §12 (codec & the demo
> front-end contract) → §13 (persistence) → §14 (end-to-end data flows) → §15
> (why it is a real bank system) → §16 (seeded demo data & intake profiles) →
> §17 (front-end checklist).

---

## Table of contents

1. [What this system is](#1-what-this-system-is)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Running the system](#3-running-the-system)
4. [Global system routes](#4-global-system-routes)
5. [Pillar 1 — MSME intake, lifecycle & data acquisition](#5-pillar-1--msme-intake-lifecycle--data-acquisition)
6. [Pillar 2 — Credit risk & decisioning engine](#6-pillar-2--credit-risk--decisioning-engine)
7. [Pillar 3 — Loan origination, ledger & lifecycle](#7-pillar-3--loan-origination-ledger--lifecycle)
8. [Pillar 4 — Guarantee buffer, capital & prudential veto](#8-pillar-4--guarantee-buffer-capital--prudential-veto)
9. [Governance — Canons, registries, change control](#9-governance--canons-registries-change-control)
10. [The Orchestrator — single public entry point](#10-the-orchestrator--single-public-entry-point)
11. [The live demo — state, SSE feed, tick & factory reset](#11-the-live-demo--state-sse-feed-tick--factory-reset)
12. [Codec & the demo front-end contract](#12-codec--the-demo-front-end-contract)
13. [Persistence & the restart guarantee](#13-persistence--the-restart-guarantee)
14. [End-to-end data flows](#14-end-to-end-data-flows)
15. [What makes this a bank system](#15-what-makes-this-a-bank-system)
16. [Seeded demo data & intake profiles](#16-seeded-demo-data--intake-profiles)
17. [Front-end integration checklist](#17-front-end-integration-checklist)

---

## 1. What this system is

This repository implements a **Basel-III-aligned neo-bank operating system for MSME
credit**, built around a five-pillar regulatory architecture in which the first four
pillars (plus a governance layer) are real, running services mounted inside a single
FastAPI application called the **orchestrator**.

The defining idea is **Guarantee Intermediation [G]**: professional capital (the
Tier stack — A, B, C, D and Senior Institutional Debt) actually *funds* the loans,
while guarantee providers *collateralize* the book by pooling pledge positions. The
bank executes a deterministic loan lifecycle (originate → disburse → repay →
delinquent/default → workout → close), holds the prudential buffers and guarantee
pool that absorb losses, continuously computes whether the bank is still "safe"
(Tier D/RWA, portfolio expected loss, guarantee leverage), can *veto* originations
when safety ratios break, and records every economic event in an append-only audit
trail that reconciles against core banking.

There are **five running pillar services** and **one governance service**:

| Service      | Mount path       | Role                                                                  |
| ------------ | ---------------- | --------------------------------------------------------------------- |
| Orchestrator | `/`              | Public entry point, mounts everything, `/health` + `/ready`, demo UI   |
| Governance   | `/governance`    | Canon versions, lexicon, tiers, interface rules, staging gates, vetoes |
| Pillar 1     | `/p1`            | MSME intake & lifecycle driver: candidates, simulation tick, demo SSE  |
| Pillar 2     | `/p2`            | Stateless credit scoring & risk-rating engine (BRR/PD/EAD/LGD/EL)      |
| Pillar 3     | `/p3`            | Stateful loan origination, postings, collateral, audit, ledger         |
| Pillar 4     | `/p4`            | Stateful guarantee buffer, capital adequacy, veto engine, mode gate    |

All five pillar services are real, running sub-apps mounted inside the one
orchestrator process. **Pillar 1** (MSME engagement / data acquisition) is the
borrower-intake and lifecycle driver: it holds candidate records (same shared DB as
governance), scores them through the **real** Pillar 2 engine, originates and
disburses through the **real** Pillar 3 engine, mirrors risk/staging/lifecycle
events into the **real** Pillar 4 engine, and drives the loan-lifecycle simulation
with a one-month tick (repay → delinquent → default → recovery → close). Pillar 5
(pledge/asset tokenization) remains **a governed boundary only** — it is defined in
the governance registry (`produces`/`consumes`/`decides`/`must_not_do`) but has
**no running service**; Pillar 4 exposes Pillar-5-style pledge submission endpoints
so the whole guarantee story is exercisable end to end.

Every engine is a byte-identical port of its source pillar engine; only import paths
changed. Storage and transport are new infrastructure: **one SQLite file per
service**, and a **static single-page app** served by the orchestrator.

### 1.1 The business story in one paragraph

An applicant is ingested by **Pillar 1** (intake form → candidate row) and submitted
→ **Pillar 2** scores them (affordability, financials, cashflow, management,
alternative data), assigns a risk band (BRR), a probability of default
(PD), exposure (EAD), loss-given-default (LGD), expected loss (EL), a price, and a
three-zone decision (auto-approve / augmented / manual review) wrapped in an
**output packet** → **Pillar 3** originates the facility, disburses funds, pledges
collateral, records repayments and every posting into core banking plus an audit
trail, and walks the facility through a deterministic state machine → **Pillar 4**
holds the four prudential sub-accounts (EL Pool, ULA Buffer, Liquidity Reserve, RP
Pool), the pooled guarantee positions and their adequacy, computes capital snapshots
(Tier D/RWA, portfolio EL, guarantees-granted/received), provisions IFRS9 expected
credit losses, and can freeze originations through a **two-track veto** that only
governance can lift → **Governance** holds the ratified Canon that defines every term,
every rule and every boundary, and blocks any mutation while the Canon is not ratified.

---

## 2. Architecture at a glance

```
(single public entry point)
                                   │
                     ┌─────────────▼─────────────┐
                     │   ORCHESTRATOR  :8000     │
                     │  bank.orchestrator.main   │
                     │  /health  /ready  / (UI)   │
                     └───────┬──────┬──────┬──────┬──────┘
                             │      │      │      │
                 /governance │ /p1  │ /p2  │ /p3  │ /p4
                             │      │      │      │
                 ┌───────────▼┐ ┌──▼───┐ ┌──▼───┐ ┌▼──────────────┐ ┌▼────────────┐
                 │ GOVERNANCE │ │  P1  │ │  P2  │ │      P3       │ │     P4      │
                 │ (SQLAlchemy│ │intake│ │ risk │ │ origination   │ │ buffer/     │
                 │  registries│ │+life │ │engine│ │ state machine │ │ capital/    │
                 │  in same   │ │cycle │ │state-│ │  + postings   │ │ veto/mode   │
                 │  .db file) │ │+demo │ │less  │ │  + audit trail│ │ gate        │
                 │            │ │ SSE  │ │      │ │               │ │             │
                 └────────────┘ └──────┘ └──────┘ └──────┬────────┘ └──────┬──────┘
                                                          │ shared SQLite  │
                                                          └─── data/orchestrator.db ──┘
                                                              (KvStore JSON snapshots)
```

- **One process, mounted sub-apps.** The orchestrator imports the **five** sub-apps
  once and mounts them under **fixed, non-configurable prefixes** (`/governance`,
  `/p1`, `/p2`, `/p3`, `/p4`). There are no other ports you need to know: HTTP is
  always `http://<host>:8000`, and every route below is already prefixed by its
  mount.
- **Exact path shapes (verified from the running app).** P1 routes live at `/p1/...`
  (CRUD + lifecycle) and `/p1/demo/...` (state / SSE / tick / reset). P2 routes
  live at `/p2/...`. P3 lives at `/p3/api/v1/p3/...` and P4 at
  `/p4/api/v1/p4/...` — the doubled `p3`/`p4` is real (service API-prefix + router
  prefix). Governance lives at `/governance/api/v1/...`. **Do not "simplify" these
  paths**; the per-mount `/docs` pages show the truth.
- **Storage.** Pillar 3, Pillar 4, Governance and Pillar 1 share **one SQLite file**
  owned by the orchestrator (default `<project root>/data/orchestrator.db`, config
  `BANK_ORCH_DB_PATH`; anchored to the project root so the CWD never splits the
  state across two files). Pillar 3/4 keep their engine snapshot as a versioned
  JSON blob inside that file's `kv` table (`p3_state_v1`, `p4_state_v1`); governance
  and P1 SQLAlchemy tables (`p1_candidates` plus the canon/lexicon/tier registries)
  live in the same file. Pillar 2 is stateless (no DB). This is what makes `/ready`
  meaningful: it re-opens
  fresh Pillar 3/4 runtimes over the same file and asserts the rehydrated snapshot is
  **byte-identical** to the persisted blob.
- **CORS.** Open (`allow_origins=["*"]`), so your browser dev server can call it
  directly.
- **HTTP errors.** Pillar 3/4 map engine exceptions to `409` (governance/veto/
  mode/pledge conflicts), `422` (invalid state transition / unconfirmed packet /
  unauthorised decision / out-of-posting-set), `404` (unknown facility/packet),
  `400` (governance perimeter violations). The governance middleware returns `409`
  for **any** mutation while the current Canon is not `RATIFIED`.

---

## 3. Running the system

```bash
# all of the following assumes the CWD is bank_system/
python -m venv .venv
.venv\Scripts\activate              # Windows (POSIX: source .venv/bin/activate)
pip install -e ".[dev]"

# optional: seed the governance registries (Canon V3.4 RATIFIED + RI-1/2/3,
# lexicon, tiers, pillar boundaries, PENDING register — idempotent)
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m bank.orchestrator.governance.seed.seed

# the single entry point — serves everything on :8000 (starts EMPTY)
.venv\Scripts\python.exe -m bank.orchestrator.main
#  ...or preload the six P1 intake profiles (data/candidates/*.json):
$env:BANK_ORCH_SEED_DEMO = "true"
.venv\Scripts\python.exe -m bank.orchestrator.main
#  ...optional: auto-advance the simulation every N seconds (0 = manual tick)
$env:BANK_SIMULATION_TICK_SECONDS = "10"
```

The system boots **empty by default**. `BANK_ORCH_SEED_DEMO=true` imports the six
portable candidate exports from `bank_system/data/candidates/*.json` once
(idempotent — skipped if the `p1_candidates` table already has rows).
`POST /p1/demo/reset` is a **full factory reset** (P1 rows wiped + real P3/P4
engines re-instantiated fresh + month back to 0) but **does not re-seed**, so a
reset returns you to the empty start.

Interactive API docs: `http://localhost:8000/docs` (the orchestrator OpenAPI
includes every mounted sub-app); also per mount: `/governance/docs`, `/p1/docs`,
`/p2/docs`, `/p3/docs`, `/p4/docs`. Each sub-app exposes `{prefix}/openapi.json`.
The standalone service processes (`uvicorn bank.pillars.api.p2:app`, `p3`, `p4`)
still exist for local development but are **not** what the demo uses — the UI
always calls the orchestrator on `:8000`.

**Front-end workflow.** In `demo/`: `npm install`, then `npm run dev` (Vite on
`:5173`, proxying `/health /ready /governance /p1 /p2 /p3 /p4 /docs /openapi.json`
to `:8000`) is the fast loop. `npm run build` emits `demo/dist/`, which the
orchestrator serves itself at `/` — the same UI the running system shows.

Tests (if you need to prove behaviour): `python -m pytest -q` (from `bank_system/`).
```

---

## 4. Global system routes

| Route     | Method | Purpose                                                                                                        |
| --------- | ------ | -------------------------------------------------------------------------------------------------------------- |
| `/`       | GET    | The demo SPA (built Vite `dist/` when present, else the static `demo/static` page)                             |
| `/health` | GET    | Liveness: `{"status":"ok","app":"bank-orchestrator","version":"3.4.0"}`                                        |
| `/ready`  | GET    | **Restart-integrity probe.** Re-opens fresh Pillar 3 & 4 runtimes over the same DB and asserts byte-identical snapshots |
| `/docs`   | GET    | Orchestrator OpenAPI                                                                                           |
| `/favicon.ico` | GET | Small favicon helper                                                                                     |

### 4.1 `/ready` response — a contract, not a ping

```json
{
  "status": "ok",
  "checks": { "p3_restart_ok": true, "p4_restart_ok": true }
}
```

If either check is false the response is `503` with `detail` = the same object and
`status: "degraded"`. Treat a red `/ready` as "the bank engine lost state" — surface
it loudly in any operations UI.

---

## 5. Pillar 1 — MSME intake, lifecycle & data acquisition

### 5.1 What it does (narrative)

Pillar 1 is the borrower-facing **intake and lifecycle driver** — the demo's front
door and its clock. It ingests a borrower intake form into a `p1_candidates` row
(persisted in the same shared `data/orchestrator.db`), scores that candidate by
calling the **real Pillar 2 engine**, originates + disburses through the **real
Pillar 3 engine**, mirrors the risk / IFRS9-staging / lifecycle events into the
**real Pillar 4 engine**, and then keeps the loan alive with a **deterministic
one-month "tick"** that walks it through repayment → delinquency → default →
recovery → close. Every lifecycle action (submit / approve / disburse) also
publishes a `state_update` frame on the demo SSE stream so subscribed UIs update
without polling.

Two application sources, one scoring pipeline:

- **Seed / imported candidates** carry the full serialized `BorrowerApplication` in
  `application_json`, so re-running them through Pillar 2 reproduces exactly the
  original profile's data-tier → BRR/DQS → decisioning-zone journey.
- **Form-built candidates** (the `CandidateCreate` intake form) get a **thin**
  application built from the form — KYC + mobile-money rails only
  (`applications.build_thin_application`). A thin file forces the same conservative
  DQS → MoC → `MANUAL_REVIEW` path the always-manual approval gate relies on.

### 5.2 API routes (all under `/p1`)

| Route | Method | Purpose |
| --- | --- | --- |
| `/p1/candidates` | POST | Create candidate from intake form → `{candidate, payment_behavior}` (201) |
| `/p1/candidates` | GET | List; optional `?status=` filter — newest first |
| `/p1/candidates/{id}` | GET | One candidate (404 if unknown) |
| `/p1/candidates/{id}` | DELETE | Remove a candidate (204) |
| `/p1/candidates/{id}/submit` | POST | Score via real P2 + mirror risk packet to P4 → status `scored` |
| `/p1/candidates/{id}/approve` | POST | **Manual officer row gate (always required)** → `approved` / `rejected` |
| `/p1/candidates/{id}/disburse` | POST | Originate (pledge collateral if offered) + disburse via real P3 → `disbursed` |
| `/p1/candidates/import` | POST | Ingest an exported candidate JSON → status `new` (201) |
| `/p1/candidates/import/file` | POST | Same, from a multipart `file` upload (201) |
| `/p1/demo/data-files` | GET | List exported `data/candidates/*.json` carriers |
| `/p1/demo/data-files/{filename}` | GET | Return one exported carrier's JSON |
| `/p1/demo/profiles` | GET | The six profile cards (data tier / outcome / tagline / amounts) |
| `/p1/demo/seed` | POST | Idempotently insert the six profiles → `{seeded: count}` |
| `/p1/demo/state`, `/p1/demo/events/sse`, `/p1/demo/tick`, `/p1/demo/reset` | GET / GET / POST / POST | Live demo snapshot, SSE stream, one-month tick, factory reset — **see §11** |

> **Route-ordering gotcha (front-end, please read):** `/p1/candidates/import` and
> `/p1/candidates/import/file` are **static** paths and must win over the
> parameterised `/p1/candidates/{candidate_id}`. The server wires the import paths
> *before* the `{candidate_id}` routes. If you hand-roll callers, always use the
> full literal path — never let an `/import` suffix fall through a
> `/candidates/{id}` pattern.

### 5.3 Lifecycle & statuses

| Status | How a candidate gets here | UI treatment |
| --- | --- | --- |
| `new` | Created via intake form or carrier import; `payment_behavior` auto-generated | Awaiting Submit |
| `scored` | `submit` ran the real P2 pipeline | Show BRR / PD / LGD / EAD / EL / zone / packet status |
| `approved` | `approve` (always-manual officer); P3 facility originated, IFRS9 stage-1 mirrored | Awaiting Disburse |
| `rejected` | `approve` with `approve: false` | Terminal; render the officer note |
| `disbursed` | `disburse` posted `PRINCIPAL_MOVEMENT` to core banking | Repaying — tickable |
| `delinquent` | Tick reaches `delinquent_month`; drawdowns frozen | Warning flag |
| `defaulted` | Tick reaches `default_month`; P3 loss marker, P4 default event + stage-3 | Danger state |
| `closed` | Fully repaid, or recovered then closed by the tick | Terminal, green |

Status order in the demo snapshot: `new → scored → approved → disbursed →
delinquent | defaulted → closed | rejected`.

### 5.4 Schemas (field-by-field)

**`CandidateCreate`** — the intake form posted to `POST /p1/candidates`.

| Field | Type | Meaning |
| --- | --- | --- |
| `first_name`, `last_name` | string | Required (1–80 chars) |
| `name_ar` | string? | Arabic name |
| `gender` | `male`/`female` | Default `male` |
| `age` | int | 18–100 |
| `national_id`, `phone` | string? | Identifiers |
| `city` | string | Display city; maps to a P2 `geography_code` (unknown → `MUSCAT`) |
| `employer_name`, `job_title` | string? | Employer detail |
| `employer_type` | enum? | `government` / `military` / `private` / `self_employed` |
| `employment_years` | float | Default 1.0 |
| `monthly_salary` | float | 0 allowed (treated as missing) |
| `product` | string | Intake default `auto_loan` (the thin application re-maps to `WORKING_CAPITAL_LINE`) |
| `requested_amount` | float | Required, > 0 |
| `requested_tenure_months` | int | 1–60, default 12 |
| `payment_behavior` | object? | Verbose override of the auto-generated behaviour (below) |
| `outcome_override` | enum? | `paid` / `default` / `delinquent_cured` — force the auto-generator's outcome |

**`CandidateRead`** — the API representation of every candidate (all intake fields
above, plus):

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | UUID string — the engine's primary key |
| `seed_profile` | string? | `ahmed` / `yusuf` / `layla` / `omar` / `nadia` / `fatima` on seeds |
| `status` | enum string | See §5.3 |
| `submitted_at`/`scored_at`/`approved_at`/`disbursed_at` | datetime? | Lifecycle timestamps |
| `application_id` | string? | P2 application id (seed: `APP-NADIA-305`; form-built: `APP-<candidate-id>`) |
| `facility_id` | string? | P3 facility id — deterministic `FAC-<candidate-id>[0:10].upper()` |
| `p2_brr`/`p2_pd`/`p2_lgd`/`p2_ead`/`p2_el` | number? | Informational copy of the P2 score |
| `p2_zone`, `p2_packet_status` | string? | Decisioning zone + packet status |
| `payment_behavior` | object? | The full repayment schedule (below) |
| `sim_state` | object? | Simulation progress: `{current_month, p3_packet, payments_made[], defaulted, delinquent, closed, recoveries[]}` |
| `display_name` | string | Computed `first_name last_name` |
| `created_at`, `updated_at` | datetime | Audit timestamps |
| `approved_by`, `approval_note` | string? | Officer identity + note at approval |

**`PaymentBehavior`** — the payment path a facility follows once disbursed:

| Field | Type | Meaning |
| --- | --- | --- |
| `outcome` | `paid` / `default` / `delinquent_cured` | Terminal story |
| `facility_amount`, `disbursed` | float | Requested vs actually disbursed |
| `currency` | string | Default `USD` |
| `tenure_months` | int | Default 12 |
| `repayments[]` | rows | Each `{interest, principal, month}` — `month` is 1-based from disbursement |
| `delinquent_month` | int? | First missed instalment |
| `default_month` | int? | If outcome `default` |
| `recovered_amount` | float | Partial recovery realized after default |
| `interest_rate_bps` | int | Annual APR in basis points |

The demo renders `repayments[]` as a payment-behaviour table and flags
`delinquent_month`/`default_month`.

### 5.5 Deterministic behaviour generation

When a candidate is created without an explicit `payment_behavior`, one is
auto-generated (`behavior_gen.generate_behavior`) from a **SHA-256-seeded PRNG
keyed on the candidate id** — the same candidate always produces the same
behaviour across restarts. Roll: 60% `paid`, 25% `default`, 15%
`delinquent_cured` (the outcome is stable per candidate, not re-rolled per run).
Generated schedules use equal-principal amortization at a deterministic APR
(800–1500 bps); `default` candidates miss an instalment around `tenure/3`, default
the following month, then realize a partial recovery; `delinquent_cured`
candidates drop one missed instalment and resume.

### 5.6 End-to-end id chain

`candidate_id` (P1, UUID) → `application_id` (P2, `APP-…`) → `facility_id` (P3,
`FAC-<candidate>[0:10].upper()`) → `facility_ref` (P4, same facility id). The same
links appear on the candidate row and across the P3 facility & P4 IFRS9 tables, so
any screen can be joined back to the intake candidate.

> **Approval is always manual (`MANUAL_APPROVAL_ALWAYS = True`).** There is no
> auto-approve path in the demo: `approve` requires an officer identity. The demo
> front-end posts `officer_id: 'DEMO-OFFICER-1'`.

---

## 6. Pillar 2 — Credit risk & decisioning engine

### 6.1 What it does (narrative)

Pillar 2 is the **intake risk brain**. It is stateless: give it a
`BorrowerApplication` and it runs the full scoring pipeline in one call — no storage,
no lifecycle, no ledger. It composes twelve Tier-1 features computed from the
application (net margin, leverage, revenue growth, asset turnover, cashflow
volatility, DSCR, working-capital days, bounced items, customer concentration HHI,
business age, owner experience, account conduct), then applies a **Data Quality Score
(DQS)** with completeness/consistency/recency and a **Margin of Conservatism (MoC)**
uplift when the file is thin (P2 never refuses to score for missing data, it just
marks the data risky). It then produces a **BRR** (Bank Risk Rating), maps BRR → PD
through a versioned grid, computes **EAD** from the facility request (with a
sandbox-scope product check), **LGD** from the collateral offers and operating model,
**EL = PD×LGD×EAD**, a comparison of EL against the **2% budgeted-loss** policy, a
price (base rate + risk premium), and finally a **three-zone decision** driven jointly
by risk band, data confidence and policy exceptions. The zone yields a packet status
(APPROVED / PROVISIONAL / CONDITIONAL) and whether a human credit-officer
counter-signature is still required. In addition to scoring, P2 exposes early-warning
signal evaluation, the CASS data feed packet for P4, the pooled-guarantee-level
computation, and the learning-oriented **override record** open/close loop.

Important engineering facts for the UI: all financial input fields are **optional**;
the response is deterministic per input; there is **no `/p2` persistence**, so a
score is a pure request→response computation.

### 6.2 API routes

| Route                                | Method | Purpose                                                                        |
| ------------------------------------ | ------ | ------------------------------------------------------------------------------ |
| `/p2/health`                         | GET    | `{"status":"ok","brr_pd_grid_version":<version>}`                               |
| `/p2/v1/score`                       | POST   | Run the full pipeline for one application → `ScoringResult`                     |
| `/p2/v1/brr-pd-grid`                 | GET    | The versioned BRR→PD grid: `{"version":..., "grid":{...}}`                      |
| `/p2/v1/category-weights/{segment}`  | GET    | Category weights for a segment (e.g. `MICRO`, `SME`) → `{WEIGHT_CATEGORY: value}` |
| `/p2/v1/ews`                         | POST   | Early-warning signal from BRR deterioration (query/body params) → `EWSResult`    |
| `/p2/v1/cass-feed`                   | POST   | Produce a CASS feed packet for P4 (params) → `CASSFeedPacket`                    |
| `/p2/v1/pooled-guarantee-level`      | POST   | G-model pooled guarantee level from portfolio EAD + collateral value             |
| `/p2/v1/override/open`               | POST   | Open an override record (learning input) → `OverrideRecord`                      |
| `/p2/v1/override/close`              | POST   | Close an override at maturity with outcome/vindication → `OverrideRecord`        |

### 6.3 Request schema — `BorrowerApplication`

The one input to `/p2/v1/score`. Nested: `facility`, plus five optional data blocks
and collateral offers.

```json
{
  "application_id": "APP-0001",
  "segment": "SME",
  "operating_model": "GUARANTEE",
  "facility": {
    "product": "MSME_TERM_LOAN",
    "requested_amount": 25000.0,
    "drawn_amount": null, "undrawn_amount": null,
    "tenor_months": 24, "recourse": true
  },
  "maturity_regime": null,
  "model_maturity_stage": "SANDBOX",
  "financials":   { "revenue": 120000.0, "period_end": "2025-12-31", "...": null },
  "cash_flow":    { "avg_daily_inflow": 400.0, "debt_service_obligation": 900.0, "...": null },
  "business":     { "sector_code": "0101", "registration_date": "2018-04-02", "...": null },
  "management":   { "owner_experience_years": 9.0, "prior_default_history": false, "...": null },
  "alternative":  { "utility_payment_regularity": 0.9, "telco_regularity": 0.8, "...": null },
  "collateral": [ { "collateral_class": "REAL_ESTATE", "track": "TRACK_1_CLASSICAL", "p4_admitted_value": 15000.0 } ],
  "rails_connected": ["bank-feed","pos-scale","ledger-api","erp","telco","gps"],
  "policy_exception_flags": []
}
```

Field-by-field explanation:

| Field | Type | Meaning |
| --- | --- | --- |
| `application_id` | string | Unique applicant/application id (echoed throughout) |
| `segment` | enum | Market segment — drives category weights. Values: `MICRO`, `SME` (see enums: `Segment`) |
| `operating_model` | enum | `GUARANTEE` [G] (operative) or `STABLECOIN` [S] (migration target) |
| `facility.product` | enum | Product family — sandbox-scope checked; e.g. `MSME_TERM_LOAN`, `SUPPLY_CHAIN_FINANCE` |
| `facility.requested_amount` | float | >0; the EAD base |
| `facility.drawn_amount` / `undrawn_amount` | float? | Optional split for facility products |
| `facility.tenor_months` | int? | Maturity in months |
| `facility.recourse` | bool | Default `true` (supply-chain finance flag) |
| `maturity_regime` | enum? | If `null`, **auto-inferred** from `rails_connected` count: ≥6 HIGH, ≥2 INTERMEDIATE, else LOW |
| `model_maturity_stage` | enum | `DESIGN` / `SANDBOX` / `PRODUCTION`; gates auto-approve |
| `financials` | object | OCR'd P&L/B/S: `revenue, cost_of_sales, operating_expenses, net_profit, period_end, total_assets, current_assets, total_liabilities, current_liabilities, equity, prior_period_revenue` (all optional) |
| `cash_flow` | object | Bank-feed derived: `daily_net_cashflow[]`, `avg_daily_inflow`, `debt_service_obligation`, `receivable_days`, `payable_days`, `inventory_days`, `bounced_items_count`, `months_of_history` |
| `business` | object | `top5_customer_share`, `single_supplier_share`, `registration_date`, `sector_code`, `geography_code`, `legal_form` |
| `management` | object | `owner_experience_years`, `prior_default_history`, `has_governance_plan`, `account_conduct_score` (0–1) |
| `alternative` | object | `utility_payment_regularity`, `telco_regularity`, `ecommerce_reputation_score`, `supply_chain_centrality` |
| `collateral[]` | array | Each: `collateral_class` (enum), `track` (`TRACK_1_CLASSICAL`/`TRACK_2_NFT`/`TRACK_3_STABLECOIN`), `p4_admitted_value` (≥0 — the only value P2 may consume; P2 never values raw assets, firewall intact) |
| `rails_connected` | string[] | Connected banking/POS/ERP rails — drives maturity regime |
| `policy_exception_flags` | string[] | If non-empty, case cannot auto-approve |

### 6.4 Response schema — `ScoringResult`

```json
{
  "application_id": "APP-0001",
  "segment": "SME",
  "maturity_regime": "HIGH",
  "data_quality": {
    "completeness": 0.92, "consistency": 0.95, "recency": 0.88, "dqs": 0.91,
    "is_thin_file": false, "moc_pd_uplift": 0.0, "moc_lgd_uplift": 0.0
  },
  "rating": {
    "category_scores": [ {"category":"FINANCIALS","raw_score":0.31,"weight":0.3} ],
    "sector_geo_adjustment": 0.0,
    "composite_risk_score": 0.37, "brr": 4, "tier_used": "TIER_1",
    "thin_file_capped": false, "pd_grid_version": "BRR-GRID-2026-04",
    "pd_point_estimate": 0.0112, "pd_range": [0.008, 0.02], "pd_with_moc": 0.0112
  },
  "credit_risk": {
    "ead": 25000.0, "lgd": 0.38, "lgd_with_moc": 0.38, "expected_loss": 106.4,
    "el_vs_budgeted_loss": "within", "pooled_guarantee_level": null
  },
  "pricing": { "base_rate_bps": 700, "risk_premium_bps": 320, "all_in_rate_bps": 1020 },
  "zone": "AUTO_APPROVE",
  "packet": {
    "application_id": "APP-0001", "status": "APPROVED",
    "model_maturity_stage": "SANDBOX", "pd_grid_version": "BRR-GRID-2026-04",
    "collateral_track": "TRACK_1_CLASSICAL", "brr": 4, "pd": 0.0112,
    "lgd": 0.38, "ead": 25000.0, "expected_loss": 106.4,
    "pricing": { "base_rate_bps": 700, "risk_premium_bps": 320, "all_in_rate_bps": 1020 },
    "zone": "AUTO_APPROVE", "requires_officer_confirmation": false
  }
}
```

Field-by-field explanation:

| Block | Fields | Meaning for a UI |
| --- | --- | --- |
| `data_quality` | `completeness/consistency/recency/dqs` (0–1), `is_thin_file` (bool), `moc_pd_uplift`/`moc_lgd_uplift` | Render as a data-confidence gauge; thin-file ⇒ show conservative scoring |
| `rating` | `category_scores[]` (`category`, `raw_score` 0=safest→1=riskiest, `weight`), `sector_geo_adjustment`, `composite_risk_score`, `brr` (1–10-ish), `tier_used`, `thin_file_capped`, `pd_grid_version`, `pd_point_estimate`, `pd_range`, `pd_with_moc` | The credit scorecard; `brr` is the headline band |
| `credit_risk` | `ead`, `lgd`, `lgd_with_moc`, `expected_loss`, `el_vs_budgeted_loss` (`within`/`above`), `pooled_guarantee_level` | Loss economics; `el_vs_budgeted_loss="above"` blocks auto-approve |
| `pricing` | `base_rate_bps`, `risk_premium_bps`, `all_in_rate_bps` | Basis points; rate = base + risk premium |
| `zone` | enum `AUTO_APPROVE` / `AUGMENTED_DECISION` / `MANUAL_REVIEW` | Headline decision bucket |
| `packet` | The **P2→P3 handoff**: `status` (`APPROVED`/`PROVISIONAL`/`CONDITIONAL`), model fields, `zone`, `requires_officer_confirmation` (bool) | This is what you'll pass to Pillar 3 |

Decisioning rules worth reflecting in the UI:
- `AUTO_APPROVE` ⇒ all of: `brr` low, DQS high, not thin-file, no policy exception,
  EL within budget. In `PRODUCTION` it can skip officer confirmation **only if** the
  governance switch `production_auto_approve_enabled` is on (never automatic).
- `AUGMENTED_DECISION` ⇒ `PROVISIONAL` status, needs officer confirmation.
- `MANUAL_REVIEW` ⇒ `CONDITIONAL` status, needs officer confirmation.
- `DESIGN` stage ⇒ no live decisions at all; confirmation always required.

### 6.5 Other P2 schemas

**`CASSFeedPacket`** (CIS-1 shape, P2→P4 ABSF feed — dormant in Conventional Mode):
`application_id`, `brr`, `pd_pit_adjusted`, `ifrs9_stage`, `cash_flow_deterioration_indicator`, `expected_loss`.

**`EWSResult`** (early-warning signal):
`application_id`, `triggered` (bool), `brr_at_origination`, `brr_current`,
`deterioration_notches`, `routed_to_officer`, `triggers_p3_action` (always `false` by Canon).

**`OverrideRecord`** (learning loop):
`application_id`, `override_type`, `model_output_before`, `officer_output_after`,
`direction` (`UPGRADE`/`DOWNGRADE`), `factor_category_overridden`, `reason_code`,
`narrative`, `authority_level`, and optional `approver`, `approver_decision`,
`outcome_at_maturity`, `vindicated`, `model_improvement_disposition`, `disposition_notes`.

---

## 7. Pillar 3 — Loan origination, ledger & lifecycle

### 7.1 What it does (narrative)

Pillar 3 is the **operational heart** — it is where a decision becomes money and a
facility lives out its life. It is fully **stateful and persistent**: every facility,
packet, posting, collateral object, audit record and ledger row survives restarts
(the snapshot in SQLite is rehydrated byte-identically — that is the `/ready`
contract). Its façade, `Pillar3Orchestrator`, sequences four components per action: a
**P2 gate** (records every incoming packet; authorizes origination only on a
confirmed packet and through the maturity-stage gate), a **state machine** (the
allowed-transitions table — this is the *only* place transitions are defined), a
**posting service** (captures each event, posts it to core banking via
`CoreBankingLedger`, and — for income / risk-premium / loss events — routes an
**AllocationQuestion** to P4; P3 performs **no allocation computation of any kind**,
guaranteed structurally by `assert_allocation_untouched`), and an **audit trail**
(every action appends exactly one `AuditRecord` carrying the mandatory Spec §8 fields).
Around those sit a collateral service (records confirmed collateral objects against a
facility, never values them), a P4 veto router (freezes a facility under Track 1
portfolio or Track 2 facility veto — a freeze that **P2/P3 cannot override**), a P5
gate (Pillar-5 placeholder) and a daily **reconciliation** that totals P3 events vs.
core banking and **raises** (not logs) any breach above tolerance, treating core
banking as ground truth.

The facility lifecycle states are: `APPROVED` → `ACTIVE` → `REPAYING` ⇄ `DELINQUENT`
→ `DEFAULT` → (`RESTRUCTURING` → `ACTIVE` | `RECOVERY`) → `CLOSED`. Drawdowns are
frozen in `DELINQUENT`/`DEFAULT` and under any veto. Restructuring and recovery
require a **human-authorised-for-workout** packet (Canon §8.6) — origination
confirmation and workout authorisation are deliberately separate flags.

### 7.2 Allowed state transitions (render these as a visual waterfall)

| Current      | May go to                                               |
| ------------ | ------------------------------------------------------- |
| `APPROVED`   | `ACTIVE`                                                |
| `ACTIVE`     | `REPAYING`, `DELINQUENT`, `RESTRUCTURING`(→`ACTIVE`), `CLOSED` |
| `REPAYING`   | `REPAYING`, `DELINQUENT`, `RESTRUCTURING`(→`ACTIVE`), `CLOSED` |
| `DELINQUENT` | `REPAYING` (cured), `DEFAULT`, `RESTRUCTURING`(→`ACTIVE`), `CLOSED` |
| `DEFAULT`    | `RECOVERY`, `RESTRUCTURING`(→`ACTIVE`), `CLOSED`         |
| `RESTRUCTURING` | `ACTIVE`, `CLOSED` (transient — resolves to ACTIVE deterministically) |
| `RECOVERY`   | `CLOSED`                                                |
| `CLOSED`     | (terminal)                                              |

### 7.3 API routes (all under `/p3/api/v1/p3`)

> Read routes; note `packets`/`audit`/`postings`/`ledger`/`reconcile` are the whole
> picture for facility detail + audit + treasury screens.

| Route | Method | Purpose / response |
| --- | --- | --- |
| `/p3/api/v1/p3/facilities` | GET | Summary list: `facility_id, state, origination_packet_id, collateral_count, veto_frozen, updated_at` |
| `/p3/api/v1/p3/facilities/{facility_id}` | GET | Detail incl. `created_at`, `collateral_objects[]` and `collateral_service_recorded[]` (full objects) |
| `/p3/api/v1/p3/packets` | GET | All received P2 output packets (full objects) |
| `/p3/api/v1/p3/audit` | GET | Full append-only audit trail (all records) |
| `/p3/api/v1/p3/audit/{facility_id}` | GET | Audit records for one facility — the lifecycle story |
| `/p3/api/v1/p3/postings` | GET | All posted events (micro side of the micro/macro cut) |
| `/p3/api/v1/p3/ledger` | GET | All core-banking ledger postings (system-of-record) |
| `/p3/api/v1/p3/reconcile?tolerance=0.0` | GET | `p3_event_total, core_banking_total, discrepancy, tolerance, within_tolerance, unmatched_p3_event_ids` |
| `/p3/api/v1/p3/originate` | POST | Body `P2OutputPacket` → records packet + facility `{facility_id, state}` |
| `/p3/api/v1/p3/disburse` | POST | Query `facility_id`, `amount`, `currency` + body packet → posts `PRINCIPAL_MOVEMENT`, state → `ACTIVE`; returns `PostingEvent` |
| `/p3/api/v1/p3/pledge-collateral` | POST | Query `facility_id`, optional `external_reference` + packet → records `CollateralObject` |
| `/p3/api/v1/p3/repayment` | POST | Query `facility_id`, `interest_amount`, `principal_amount`, `currency` + packet → returns `{income_event, principal_event}`; state → `REPAYING` |
| `/p3/api/v1/p3/mark-delinquent` | POST | Query `facility_id` + packet → `{status:"marked_delinquent}`; drawdowns frozen |
| `/p3/api/v1/p3/mark-default` | POST | Query `facility_id` + packet → posts `LOSS_RECOVERY` marker; returns `PostingEvent` |
| `/p3/api/v1/p3/restructure` | POST | Query `facility_id` + workout-authorized packet → `{status:"restructured"}` |
| `/p3/api/v1/p3/recovery` | POST | Query `facility_id`, `recovered_amount`, `currency` + workout packet → `PostingEvent` |
| `/p3/api/v1/p3/close` | POST | Query `facility_id` + packet → `{status:"closed"}` |

> **Important contract detail:** every mutating P3 endpoint takes the **same**
> `P2OutputPacket` in the body. To act on a facility you must send the packet that
> authorises it. P3 re-records the packet at each call. `P2OutputPacket` in P3 is a
> dataclass mirroring the P2 packet with the P3-visible fields below.

### 7.4 Data schemas with explanations

**`P2OutputPacket`** (as P3 consumes it — pass-through only, P3 never recomputes):

| Field | Type | Meaning |
| --- | --- | --- |
| `packet_id` | string | Unique packet id (e.g. `DEMO-001`) |
| `facility_id` | string | The facility this packet authorises |
| `status` | enum | `APPROVED` / `PROVISIONAL` / `CONDITIONAL` |
| `maturity_stage` | enum | `DESIGN`/`SANDBOX`/`PRODUCTION` — recorded, gates origination |
| `brr_pd_grid_version` | string | e.g. `BRR-GRID-2026-04` — recorded verbatim |
| `collateral_track` | enum | `TRACK_1_CLASSICAL`/`TRACK_2_NFT`/`TRACK_3_STABLECOIN` |
| `packet_version` | string | Packet schema version (e.g. `v1`) |
| `officer_confirmed` | bool | Credit-officer counter-signature present (required for PROVISIONAL/CONDITIONAL) |
| `officer_id` | string? | The confirming officer |
| `human_authorised_for_workout` | bool | **Separate flag** required to restructure/recover — not the same as confirmation |
| `issued_at` | datetime | Issued timestamp |

Confirmation rule: `status == APPROVED` ⇒ confirmed; otherwise confirmed only if
`officer_confirmed and officer_id` set. Workout actions additionally require
`human_authorised_for_workout == true`.

**`LoanFacility`**:
`facility_id`, `state` (enum above), `origination_packet_id?`, `collateral_objects[]`
(embedded full objects), `veto_frozen` (bool — show a red badge), `created_at`,
`updated_at` (tz-aware ISO).

**`CollateralObject`**:
`collateral_id`, `facility_id`, `kind` (`MSME_PLEDGED` | `NEO_BANK_POOLED_GUARANTEE` —
two-guarantee-layer rule, never conflated), `track`, `model_flag` (`G`|`S`),
`p2_packet_id` (mandatory provenance), `recorded_at`, `external_reference?` (e.g.
deed/NFT/escrow reference).

**`PostingEvent`** (the per-loan economic event):
`event_id`, `facility_id`, `event_type`, `amount`, `currency`, `p2_packet_id`,
`occurred_at`, `routes_allocation_question_to_p4` (bool — income/premium/loss events
also generate an `AllocationQuestion`), `memo`.

`event_type` values (the **complete** posting set — nothing else may be posted):
`LOAN_INCOME`, `RISK_PREMIUM_FEE`, `PRINCIPAL_MOVEMENT`, `LOSS_RECOVERY`,
`ORIGINATION_FEE`, `COVENANT_BREACH`, `GUARANTEE_EVENT`.

**`AllocationQuestion`** (P3→P4 routing signal — never an allocation):
`source_event_id`, `facility_id`, `event_type`, `amount`, `currency`. It carries only
the facts P4 needs; it contains no per-tier amounts by design.

**`AuditRecord`** (append-only; every field required — missing = construction error):

| Field | Meaning for a UI |
| --- | --- |
| `record_id` | e.g. `AUD-<hex>` |
| `facility_id` | Which facility |
| `event_type` | `ORIGINATION_RECORDED`, `DISBURSEMENT`, `COLLATERAL_PLEDGED`, `REPAYMENT`, `DELINQUENCY`, `DEFAULT`, `RESTRUCTURING_EXECUTED`, `RECOVERY_EXECUTED`, `CLOSURE` |
| `timestamp` | tz-aware ISO |
| `actor_reference` | `SYSTEM` or officer id |
| `p2_packet_version` | packet version at time of event |
| `maturity_stage` | at time of event |
| `brr_pd_grid_version` | at time of event |
| `collateral_track` | at time of event (nullable) |
| `p4_veto_status` | snapshot string e.g. `TRACK_1_PORTFOLIO:CLEAR; TRACK_2_FACILITY:CLEAR` |
| `posting_routing_flag` | which posting (if any) this event produced |
| `core_banking_confirmed` | bool — `true` when a posting was posted |
| `resulting_state` | facility `state` after the event |
| `collateral_reference` | optional collateral id |
| `guarantee_linkage` | optional [G] given/received guarantee reference |

**Persistence keys inside the shared SQLite `kv` table:**
- `p3_state_v1`: `{facilities, packets, posted_events, routed_questions, recorded_collateral, audit_records, p4_router{portfolio, facility_set}, ledger{postings, next_id}}`.

---

## 8. Pillar 4 — Guarantee buffer, capital & prudential veto

### 8.1 What it does (narrative)

Pillar 4 is the **protection and prudential layer** — the answer to "is the bank
still safe, and can it keep lending?". It is fully stateful and shares the same
SQLite file as Pillar 3. It composes two parts. **Part I (core prudential)**: a
**capital & leverage calculator** that continuously computes three live measures —
Tier D / RWA (floor 12%, Tier D = common equity + Perpetual AT1 only), Portfolio EL
(≤ 2% budgeted loss), and Guarantees-Granted / Guarantees-Received (the intermediated
leverage ratio, bound ≤ 1.0); an **IFRS9 staging consumer** that takes Pillar 2's
**direct staging signal** (Stage 1/2/3, which **bypasses Pillar 3 entirely**) and
re-provisions the EL Pool from registered expected losses — a staging migration
triggers **no P3 covenant or freeze**, it is a pure provisioning event; liquidity and
concentration monitors; and the **two-track veto engine** (Track 1 = standing
portfolio triggers: Tier D/RWA, EL vs budget, sector concentration, guarantee-pool
concentration, G/G ratio, liquidity minimum; Track 2 = facility-level breach of P2
policy). **Part II (guarantee buffer)**: the **buffer account** with its **four
sub-accounts** — EL Pool (IFRS9 ECL provisions), ULA Buffer (unexpected-loss
absorption beyond budgeted loss), Liquidity Reserve (funding-side-only global fiat
liquidity, minimum-monitored), RP Pool (risk-premium income stream that funds the EL
Pool) — plus the **guarantee pool** (Tier A + Tier B pledge positions, adequacy
monitored against P2's required level; P4 **never re-sizes** the requirement), the
event router (routes pilllar-3 loan events to sub-accounts), the guarantee-call
settlement engine, guarantee-pool custody with admissibility-policy checks for Pillar
5 pledge submissions, and the **pledge-release manager** (four-state release machine:
requested → adequacy-managed → released, with pre-term exceptions). Above Part I/II
sits the **Mode Gate**: Conventional Mode is the default and the **permanent floor**;
adaptive machinery (ABSF/CASS/ERME) is built but dormant until an explicit
**governance ruling** activates it.

Cross-pillar discipline enforced inside P4 (`InMemoryPorts`): P2 feeds risk packets,
staging signals and the required guarantee level; P2 *consults* the **veto state**
before confirming a packet (resolution-at-P2 — the freeze is never pushed to P3);
P3 feeds typed loan-level events; P5 submits pledges checked only against the
admissibility **policy**; the Orchestrator supplies the tier table and receives a
notification on **every** freeze.

### 8.2 API routes (all under `/p4/api/v1/p4`)

**Portfolio / bank-level reads (for a control-tower dashboard):**

| Route | Method | Purpose |
| --- | --- | --- |
| `/p4/api/v1/p4/buffer/balances` | GET | `{"el_pool":x,"ula_buffer":x,"liquidity_reserve":x,"rp_pool":x}` |
| `/p4/api/v1/p4/pool/adequacy` | GET | Pool adequacy metrics + `received` (sum of positions) |
| `/p4/api/v1/p4/capital/snapshot` | GET | The three live measures + supporting figures (below) |
| `/p4/api/v1/p4/ifrs9` | GET | `{"<facility_ref>": {"stage":1,"ecl":x,"ead":x,"el":x}}` |
| `/p4/api/v1/p4/mode` | GET | `{"mode":"CONVENTIONAL"|"ADAPTIVE","adaptive":bool,"conventional":bool}` |
| `/p4/api/v1/p4/veto/consult?facility_ref=` | GET | Veto state for P2 consultation (see `VetoConsultation` below) |
| `/p4/api/v1/p4/veto/confirm?facility_ref=` | GET | `{"facility_ref":..., "confirmed": bool}` — the resolve-at-P2 gate |
| `/p4/api/v1/p4/events` | GET | Intra-P4 event log (`IntraP4Event[]`) |
| `/p4/api/v1/p4/veto/notifications` | GET | Orchestrator freeze notifications (both tracks) |

**Feeds (P2→P4):**

| Route | Method | Body | Purpose |
| --- | --- | --- | --- |
| `/p4/api/v1/p4/risk-packet` | POST | `Pillar2RiskPacket` | Register BRR/PD/LGD/EAD/EL → capital + IFRS9 provisioner |
| `/p4/api/v1/p4/staging-signal` | POST | `StagingSignal` | Direct IFRS9 signal → EL Pool (bypasses P3) |
| `/p4/api/v1/p4/required-guarantee-level` | POST | `RequiredGuaranteeLevel` | P2's required pooled-guarantee; P4 monitors only |

**Events / recompute:**

| Route | Method | Purpose |
| --- | --- | --- |
| `/p4/api/v1/p4/events` | POST | Feed a `Pillar3Event` into the router (P3→P4, the only per-loan path in) |
| `/p4/api/v1/p4/recompute-track1` | POST | Re-read Part II balances/books and re-evaluate Track 1 standing triggers → `{snapshot, breached_triggers[]}` |

**Veto actions:**

| Route | Method | Purpose |
| --- | --- | --- |
| `/p4/api/v1/p4/veto/track2?facility_ref=&violates_policy=` | POST | Evaluate Track 2 for a facility → `{"resolution":"clear"|"frozen"}` |
| `/p4/api/v1/p4/veto/lift-track1?governance_ref=` | POST | Governance-reviewed lift of Track 1 |

**Mode gate (governance-ruled):**

| Route | Method | Body | Purpose |
| --- | --- | --- | --- |
| `/p4/api/v1/p4/mode/activate` | POST | `GovernanceRuling` | Activate adaptive mode under a signed ruling |
| `/p4/api/v1/p4/mode/fallback` | POST | `GovernanceRuling` | Fallback to Conventional (the floor) |

**Pledge lifecycle (P5→P4 surface):**

| Route | Method | Purpose |
| --- | --- | --- |
| `/p4/api/v1/p4/pledge/submit` | POST (`PledgeSubmission`) | Admit/reject against admissibility policy |
| `/p4/api/v1/p4/pledge/release?pledge_ref=&at_or_post_term=` | POST | Request release |
| `/p4/api/v1/p4/pledge/manage-adequacy?pledge_ref=` | POST | Manage adequacy before release |
| `/p4/api/v1/p4/pledge/finalize?pledge_ref=` | POST | Finalize release |

### 8.3 Data schemas with explanations

**`Pillar2RiskPacket`** (P2→P4): `facility_ref`, `brr`, `pd`, `lgd`, `ead`, `el`,
plus provenance `model_maturity_stage` (`PRODUCTION` default), `brr_pd_grid_version?`,
`packet_ref?`, `as_of`, and `margin_of_conservatism_applied=true` — P4 must **not**
re-apply a buffer (no double-counting). P4 consumes **outputs only**, no callback.

**`StagingSignal`**: `facility_ref`, `stage` (1|2|3), `packet_ref?`, `as_of`. Reaches
the EL Pool **directly**, never through P3. A migration ⇒ no P3 covenant/freeze.

**`RequiredGuaranteeLevel`**: `required_amount`, `revision_ref`, `published_at`.
P4 compares guarantees *received* against it; it never modifies it.

**`PledgeSubmission`** (P5→P4): `submission_ref`, `pledger_id`, `tier` (`TierA`/`TierB`
only — loan funding is not a guarantee position), `amount`, `asset_class`, `submitted_at`.

**`GovernanceRuling`**: `ruling_ref`, `rule_type` (e.g. `activate_adaptive`),
`signed_by`, `detail`.

**`VetoConsultation`** (P4→P2, the state P2 reads before confirming):
`any_frozen`, `track1_frozen`, `track1_triggers[]`, `track2_frozen_for_facility`,
`track2_policy?`.

**`CapitalSnapshot`** (from `/capital/snapshot` and `/recompute-track1`):

| Field | Meaning |
| --- | --- |
| `tier_d_over_rwa` | The headline capital ratio (floor 12%) |
| `portfolio_el` | Portfolio expected-loss ratio (budget 2%) |
| `guarantees_granted_over_received` | Leverage/intermediation ratio (≤1.0) or `null` when book empty |
| `tier_d_amount`, `rwa` | Numerator/denominator figures |
| `budgeted_loss` | The 2% policy ratio |
| `el_pool_balance` | Live EL Pool balance |
| `given_book`, `received_book` | Guarantee books |
| `tier_d_floor`, `budgeted_loss_ratio` | Calibration thresholds |

**`FacilityStaging`**: `facility_ref`, `stage` (1|2|3), `ecl`, `ead`, `el`.

**`IntraP4Event`**: `type` (`sub_account.balance_changed`,
`pool_adequacy.shortfall_detected`, `veto.track1_triggered`, `veto.track2_triggered`,
`guarantee_call.settled`, `pledge.release_requested`, `staging_signal.received`),
`payload` (dict), `occurred_at`.

**`Pillar3Event`** (P3→P4 typed feed): `event_type` (`scheduled_repayment`,
`origination_fee`, `risk_premium_accrual`, `default_or_write_off`,
`recovery_collateral_leg`, `guarantee_call_guarantee_leg`), `facility_ref`, `amount`,
`principal_component`, `interest_component`, `collateral_leg_amount`, `occurred_at`, `meta`.

**`VetoStatus`/`Track`:** status is `clear`|`frozen`; Track 1 is portfolio-wide and
standing/continuous, Track 2 is per-facility. Freeze ⇒ notify Orchestrator ⇒
governance review before restart; a freeze is **non-overridable by P2/P3**.

**Persistence key:**
- `p4_state_v1`: `{account{4 sub-accounts}, pool, veto{track1, track2, notifications}, capital, ifrs9, mode, event_log, pledge, custody}`.

---

## 9. Governance — Canons, registries, change control

### 9.1 What it does (narrative)

Governance is the **policy and registry layer** that dictates what every other
service may and may not do — the "constitution" of the bank. It stores the **Canon
lineage** (V2.0 → V3.0 → … → **V3.4 ratified** as current), the ratification
instruments (RI-1/2/3), the **Master Lexicon** (Annex A: locked terms, abbreviations,
model scope [G]/[S]/NEUTRAL, renamed terms, canon section references), the **tier
table** (A/B/C/D labels, model scope, insurance status with the "sole locus" rule for
Tier A, protection rules such as D→C→B→A), the **pillar boundaries** (for each pillar
1–5: what it produces/consumes/decides/must-not-do with canon section refs), the
**7 interface rules** (§6.1–6.7) plus field-level data contracts, the **CASS
interface stub** (CIS-1 contract shape only — never signal derivation logic), the
**staging/mode registry** (Conventional Mode floor, Stage 0, gates G0–G3 status and
criteria), the **PENDING register** (open governance items with discipline that some
things must *not* be resolved unilaterally in code), the **change-control** workflow
(proposals → dependency reviews → ratification/rejection), and the **veto log** (every
P4 veto event with its governance review status). Its middleware enforces the most
important runtime rule: **while the current Canon is not `RATIFIED`, every mutation
(POST/PUT/PATCH/DELETE) is rejected with `409`.** It also audit-logs every request.

For a UI this is your source for: compliance status, mode/gate state, term
definitions, tier/protection diagrams, interface/dependency explanations, veto
history, and what is still "pending".

### 9.2 API routes (all under `/governance/api/v1`)

**Canon**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/canon/current` | GET | Current ratified canon (404 if unseeded) |
| `/governance/api/v1/canon/versions` | GET | All versions |
| `/governance/api/v1/canon/versions/{version}` | GET | One version + ratification instruments |
| `/governance/api/v1/canon/lineage` | GET | Version lineage |
| `/governance/api/v1/canon/versions` | POST | Create a version (`CanonVersionCreate`) |
| `/governance/api/v1/canon/versions/{version}/ratify` | POST | Ratify (`instrument_number`, `resolution_ref`, …) |
| `/governance/api/v1/canon/versions/{version}/supersede` | POST | Supersede |

**Lexicon**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/lexicon/categories` | GET | Category list (name, annex_ref, sort_order) |
| `/governance/api/v1/lexicon/terms` | GET | Terms; filters `category_id`, `model_scope`, `search` |
| `/governance/api/v1/lexicon/terms/{term}` | GET | One term |
| `/governance/api/v1/lexicon/renamed` | GET | Terms that superseded others |
| `/governance/api/v1/lexicon/terms` | POST | Create term |
| `/governance/api/v1/lexicon/terms/{term}` | PUT | Update definition/scope/… |
| `/governance/api/v1/lexicon/validate` | POST | Validate term list → `{valid[], invalid[], renamed{}}` |

**Tiers & Pillar boundaries**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/tiers` | GET | Tier definitions |
| `/governance/api/v1/tiers/protection-rules` | GET | D→C→B→A protection rules |
| `/governance/api/v1/tiers/{label}` | GET | One tier (`A`/`B`/`C`/`D`) |
| `/governance/api/v1/tiers/{label}/insurance-status` | GET | Tier A insurance status (sole locus) |
| `/governance/api/v1/tiers/{label}/insurance-status` | PUT | Set it (only authority) |
| `/governance/api/v1/pillars` | GET | All pillar boundaries (produces/consumes/decides/must_not_do) |
| `/governance/api/v1/pillars/{number}` | GET | One pillar boundary |
| `/governance/api/v1/pillars/{number}/check-perimeter` | POST | Check a proposed action against `must_not_do` → `{allowed, reason, violated_rule?}` |

**Staging & Mode**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/staging/mode` | GET | Current mode state |
| `/governance/api/v1/staging/mode` | PUT | Set mode (body `ModeChangeIn`: `new_mode` CONVENTIONAL\|ADAPTIVE, `changed_by`, `change_rationale`) |
| `/governance/api/v1/staging/stage` | GET | Current stage |
| `/governance/api/v1/staging/stage?stage=0` | PUT | Set stage |
| `/governance/api/v1/staging/gates` | GET | All gates G0–G3 |
| `/governance/api/v1/staging/gates/{label}` | GET | One gate |
| `/governance/api/v1/staging/gates/{label}/clear` | POST | Clear a gate |
| `/governance/api/v1/staging/gates/{label}/block?notes=` | POST | Block a gate |
| `/governance/api/v1/staging/is-adaptive-active` | GET | `{"adaptive_active":bool,"current_mode":...,"fallback":"Conventional Mode is the permanent floor"}` |

**Interface rules**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/interfaces` | GET | All rules with field-level contracts |
| `/governance/api/v1/interfaces/summary` | GET | Rules without fields |
| `/governance/api/v1/interfaces/{rule_number}` | GET | One rule (e.g. `6.1`) |
| `/governance/api/v1/interfaces/validate-flow` | POST | `{source:"P2", destination:"P4"}` → matching rules + `bypasses_pillar3` |

**CASS stub**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/cass-stub` | GET | CIS-1 stub metadata + fields |
| `/governance/api/v1/cass-stub` | PUT | Update stub |
| `/governance/api/v1/cass-stub/fields` | GET | Stub with fields |
| `/governance/api/v1/cass-stub/scope` | GET | Stub with scope |

**Change control**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/changes/proposals` | GET | Proposals (filter `status`, `change_type`) |
| `/governance/api/v1/changes/proposals` | POST | Create proposal |
| `/governance/api/v1/changes/proposals/{proposal_id}` | GET | Detail + dependency reviews + votes |
| `/governance/api/v1/changes/proposals/{proposal_id}/dependency-review` | POST | Submit per-pillar review |
| `/governance/api/v1/changes/proposals/{proposal_id}/ratify` | POST | Ratify |
| `/governance/api/v1/changes/proposals/{proposal_id}/reject` | POST | Reject |

**PENDING register**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/pending` | GET | Items (filter `status`, `priority`, `category`) |
| `/governance/api/v1/pending` | POST | Register item |
| `/governance/api/v1/pending/summary` | GET | `{total, open, by_category{}, by_priority{}}` |
| `/governance/api/v1/pending/{item_id}` | GET | One item |
| `/governance/api/v1/pending/{item_id}` | PUT | Update |
| `/governance/api/v1/pending/{item_id}/resolve` | POST | Resolve (requires `resolution_notes`) |
| `/governance/api/v1/pending/{item_id}/strike` | POST | Strike with `governance_reference?` |

**Veto log**
| Route | Method | Purpose |
| --- | --- | --- |
| `/governance/api/v1/vetoes` | GET | Veto events (filter `track`, `status`) |
| `/governance/api/v1/vetoes` | POST | Record a veto event |
| `/governance/api/v1/vetoes/{event_id}` | GET | One event |
| `/governance/api/v1/vetoes/{event_id}/resolve` | POST | `{decision: RESTART_AUTHORIZED|PACKET_REMAINS_WITHHELD, authorized_by, notes}` |

### 9.3 Table schemas (the SQLite registries)

| Table | Purpose / columns |
| --- | --- |
| `canon_versions` | Canon lineage: `version_number` (unique), `name`, `status` (RATIFIED/PENDING/SUPERSEDED), `ratified_at`, `ratification_instrument`, `is_current`, `change_summary`, `lineage_notes`, `created_at` |
| `ratification_instruments` | `canon_version_id`, `instrument_number` (RI-N), `resolution_ref`, `description`, `ratified_at` |
| `lexicon_categories` | Canonical categories: `name` (unique), `annex_ref`, `description`, `sort_order` |
| `lexicon_terms` | Locked terms: `category_id`, `term` (unique), `abbreviation`, `definition`, `model_scope` (G/S/NEUTRAL), `canon_section_ref`, `is_new_in_v34`, `supersedes`, timestamps |
| `tier_definitions` | `tier_label` (A–D, unique), `tier_name`, `model_scope`, `description`, `insurance_status`, `insurance_status_authority`, `sort_order`, `canon_section_ref` |
| `tier_protection_rules` | `source_tier_id`, `target_tier_id`, `direction` (PROTECTS/ABSORBS_LOSS_FROM), `description` |
| `pillar_boundaries` | `pillar_number` (1–5), `pillar_name`, `produces[]`, `consumes[]`, `decides[]`, `must_not_do[]` (JSON arrays), `canon_section_ref` |
| `interface_rules` / `interface_fields` | Rule §6.1–6.7: `rule_number`, `name`, `description`, `direction`, `decides_who`, `executes_who`, `bypasses_pillar3`, `canon_section_ref`, `notable_v34_change`; fields: `field_name`, `field_type`, `cardinality`, `direction`, `description`, `is_pending` |
| `cass_stub_metadata` / `cass_stub_fields` | CIS-1: `version`, `issued_by`, `scope`, `source_pillar` (P2), `dest_pillar` (P4), `refresh_cadence`, `failure_semantics`; fields with `is_derived`/`is_consumed` |
| `mode_state` | `current_mode` (CONVENTIONAL/ADAPTIVE), `fallback_guarantee`, `changed_at`, `changed_by`, `change_rationale` |
| `stage_state` | `current_stage` (0–3), `changed_at`, `changed_by` |
| `gate_state` | `gate_label` (G0–G3), `status` (PENDING/CLEARED/BLOCKED), `criteria`, `cleared_at`, `cleared_by`, `notes` |
| `pending_items` | `item_number` (P-001), `title`, `description`, `category` (DATA_CONTRACT/INTERFACE/MECHANICS/GOVERNANCE/GATE_CRITERIA/DOCUMENTATION), `registered_in_canon`, `scope_details`, `status` (OPEN/IN_PROGRESS/RESOLVED/STRUCK), `priority` (CRITICAL/HIGH/MEDIUM/LOW), `assigned_to`, timestamps, `governance_reference` |
| `change_proposals` / `dependency_reviews` / `ratification_votes` | Proposal workflow: `proposal_number`, `change_type` (STRUCTURAL/INTERFACE/TIER/LEXICON/MIGRATION_G2S/CALIBRATION), `status` (SUBMITTED→RATIFIED/REJECTED), flags for dependency/G2S review; per-pillar review status; votes with instrument refs |
| `veto_events` | `event_number` (VE-001), `track` (1/2), `scope` (facility/portfolio/pillar), `facility_id?`, `pillar_4_signal`, `p2_packet_action` (WITHHELD/WITHDRAWN), `orchestrator_notified_at`, `governance_review_status` (OPEN/RESTART_AUTHORIZED/PACKET_REMAINS_WITHHELD), `restart_authorized_at/by`, `notes` |

---

## 10. The Orchestrator — single public entry point

### 10.1 What it does (narrative)

`bank.orchestrator.main` builds the composed platform app. On import it lazily
imports the **five** sub-apps once and **mounts them under fixed constants**
(`/governance`, `/p1`, `/p2`, `/p3`, `/p4`) — the mounted-prefix map cannot drift
from the ASGI import it advertises. It creates the shared Pillar 3/4 runtimes over
**one KvStore file** (`OrchestratorSettings.db_path`, default
`<project root>/data/orchestrator.db`, anchored to the repo root so CWD never
splits state; env prefix `BANK_ORCH_`, version `3.4.0`, log level from env). On
startup (lifespan) it ensures the DB parent directory exists, runs `create_all` for
the governance + P1 SQLAlchemy tables, optionally imports the six P1 candidate
exports from `data/candidates/*.json` when `BANK_ORCH_SEED_DEMO=true`
(idempotent), and starts the P1 auto-tick loop (`BANK_SIMULATION_TICK_SECONDS`,
default 0 = off). It adds open CORS, mounts the demo app (the built Vite
`demo/dist` when present — served at `/` with `/assets` static mount — otherwise
the bundled static page), and exposes `/health`, `/ready` and `/favicon.ico`.

**`/ready`** is the "restart-ok" probe: it re-opens **fresh** `P3Runtime` and
`P4Runtime` instances over the same file, `load()`s them, encodes `_snapshot()` for
each, and compares byte-for-byte against the stored `p3_state_v1`/`p4_state_v1`
blobs. All checks green ⇒ `200 {"status":"ok",...}`; any mismatch ⇒ `503 degraded`.
This is the same tape proven by `tests/pillars/rt3_restart.py` and
`rt4_restart.py`, and asserted in-process by `tests/integration/`.

### 10.2 Orchestrator settings (env)

| Env | Default | Meaning |
| --- | --- | --- |
| `BANK_ORCH_APP_NAME` | `bank-orchestrator` | Health payload name |
| `BANK_ORCH_APP_VERSION` | `3.4.0` | Version |
| `BANK_ORCH_LOG_LEVEL` | `INFO` | Logging level |
| `BANK_ORCH_DB_PATH` | `<project root>/data/orchestrator.db` | The shared SQLite file P3/P4/governance/P1 persist to |
| `BANK_ORCH_READY_ASSERTIONS` | `2` | Number of ready checks |
| `BANK_ORCH_SEED_DEMO` | `false` | Boot with P1 candidates imported from `data/candidates/*.json` (idempotent) |
| `BANK_SIMULATION_TICK_SECONDS` | `0` | P1 auto-tick interval in seconds; `0` = off (manual tick only) |

---

## 11. The live demo — state, SSE feed, tick & factory reset

### 11.1 The snapshot (`GET /p1/demo/state`)

```json
{
  "sim_month": 0,
  "candidates": [
    {
      "id": "96f2b8c0-...", "display_name": "Nadia Catering Service",
      "national_id": null, "monthly_salary": 6500,
      "requested_amount": 45000, "requested_tenure_months": 5,
      "status": "new", "facility_id": null, "application_id": null,
      "p2_zone": null, "p2_brr": null, "p2_pd": null,
      "p2_lgd": null, "p2_ead": null, "p2_el": null,
      "outstanding": null, "sim_month": 0, "payments_made": 0,
      "defaulted": false, "closed": false, "recovered": false
    }
  ],
  "p4": {
    "balances": {
      "el_pool": 0.0, "ula_buffer": 0.0,
      "liquidity_reserve": 0.0, "rp_pool": 0.0
    },
    "mode": "conventional",
    "track1_status": "clear",
    "event_log_count": 0
  }
}
```

Field notes:
- `sim_month` = the global `CURRENT_MONTH` counter.
- `candidates[]` is ordered newest-first. Per candidate: intake fields, P2 score
  echo, `outstanding` (computed only for `disbursed`/`delinquent`/`defaulted` as
  `disbursed − Σ payments_made[].principal`), `sim_month` = per-candidate
  simulation month (distinct from the global), `payments_made` = count.
- `p4.balances` is a **plain float dict** (`{el_pool, ula_buffer,
  liquidity_reserve, rp_pool}` — the enum `.value` keys, no codec envelope).
  `mode` and `track1_status` are plain strings.

### 11.2 SSE (`GET /p1/demo/events/sse`)

- Frames are `data: {...}\n\n`; idle heartbeat: `data: {}\n\n` every 30 seconds.
- The `kind` field distinguishes frames: `state` (GET /state), `tick` (POST /tick,
  carries both the `tick` result and the fresh `state`), `reset` (POST /reset,
  carries `state`), `state_update` (published after every mutating lifecycle action
  with the full fresh snapshot).
- Clients should subscribe on page load; on `onerror`, close + reconnect after a
  short delay (3 s). Poll `GET /p1/demo/state` as a fallback/backup path and on
  initial page load before the SSE connection is established.

### 11.3 Tick (`POST /p1/demo/tick`)

Global `CURRENT_MONTH` advances by 1. Only candidates in `{disbursed, delinquent,
defaulted}` are processed — one simulated month each.

Per-candidate logic (deterministic by `PaymentBehavior`):
1. **Repayment due this month?** If `repayments[]` has a row matching
   `month == CURRENT_MONTH`, record it via real P3 `record_repayment` + P4 mirror.
   If outstanding hits 0, close the facility → `closed`.
2. **Delinquency:** `delinquent_month == CURRENT_MONTH` → P3 `mark_delinquent`
   → status `delinquent`.
3. **Default:** `default_month == CURRENT_MONTH` → P3 `mark_default` + P4 default
   event + stage-3 mirror → status `defaulted`.
4. **Recovery:** defaulted + not yet recovered → partial recovery via real P3
   `initiate_recovery` → close → `closed`.
5. **Cured:** was delinquent and a repayment arrives → status returns to `disbursed`.

Response: `{"tick":{"month":N,"candidates_processed":N,"events":[...]},"state":{…}}`.

**Auto-tick:** set `BANK_SIMULATION_TICK_SECONDS=N` (N > 0) to advance the clock
automatically in the background. `0` = manual tick only (POST /tick).

### 11.4 Factory reset (`POST /p1/demo/reset`)

1. `service.reset_all()` — deletes **all** `p1_candidates` rows.
2. Fresh `P3Runtime().reset()` / `P4Runtime().reset()` — brand-new engine +
   empty persisted snapshot.
3. `CURRENT_MONTH = 0`.
4. Publishes a `reset` SSE frame containing the fresh (empty) snapshot.

Returns `{"status":"reset","state":{<empty snapshot>}}`. **Does NOT re-seed.**
`BANK_ORCH_SEED_DEMO=true` must be set *before boot* to preload profiles. After a
manual `POST /reset` the system is empty until profiles are re-imported via
`POST /p1/demo/seed` or `POST /p1/candidates/import`.

### 11.5 Seed profiles

`GET /p1/demo/profiles` returns the six FE card definitions (profile id, data tier,
outcome, tagline, scenario, requested/disbursed amounts). `POST /p1/demo/seed`
idempotently inserts them (returns `{seeded: N}`). `BANK_ORCH_SEED_DEMO=true`
does the same thing at boot (idempotent — skips when `p1_candidates` is
non-empty).

---

## 12. Codec & the demo front-end contract

### 12.1 The event codec (`bank.pillars.api.codec`)

P3/P4 engine dataclasses, enums, datetimes, sets and tuples are round-tripped
through **tagged JSON markers** so their type survives serialization:

| Envelope | Shape | Example |
| --- | --- | --- |
| Enum | `{"__enum__":"<Class>","value":v}` | `{"__enum__":"P2PacketStatus","value":"APPROVED"}` |
| Datetime | `{"__dt__":"<ISO>"}` | `{"__dt__":"2026-09-15T14:00:00+00:00"}` |
| Set | `{"__set__":[...]}` | `{"__set__":["REPAYING","DELINQUENT"]}` |
| Tuple | `{"__tuple__":[...]}` | `{"__tuple__":[1, 2]}` |
| Dataclass | `{"__dc__":"<Class>",...fields}` | `{"__dc__":"LoanFacility","facility_id":"FAC-…"}` |

Decode resolves against per-service class/enum registries (`_CLASSES`/`_ENUMS` in
`p3.py`/`p4.py`). P1 demo state and P1 candidate rows are **already plain JSON**
— no envelope unwrapping needed. **P3 and P4 GET endpoints return encoded engine
objects**, so any value rendered raw on screen risks a React error #31.

### 12.2 The `asText()` rule (front-end, please read)

Never render a response value directly — unwrap codec envelopes first:

```js
export function asText(value, fallback = '—') {
  if (value == null) return fallback;
  if (typeof value === 'object') {
    if ('value' in value) return String(value.value);        // __enum__
    if ('__dt__' in value) return String(value.__dt__);      // __dt__
    return JSON.stringify(value);                            // fallback
  }
  return String(value);
}
```

This is the **only** safe way to render P3/P4 data in the SPA. The demo ships
`asText()` in `hooks.js` and every tab uses it. P1 state / P1 candidate fields
(`display_name`, `status`, `p2_brr` etc.) are already plain strings/numbers.

### 12.3 The built SPA structure

Three tabs in `App.jsx` → `TABS = [{key:'portfolio',label:'Portfolio'},
{key:'pipeline',label:'Pipeline'}, {key:'simulation',label:'Simulation'}]`.

| Tab | Components | Primary data sources |
| --- | --- | --- |
| Portfolio | `PortfolioTab` | `p4.balances`, `p4.track1_status`, `state.candidates` summary |
| Pipeline | `PipelineTab` + `ImportPanel` | `state.candidates` (new/scored/approved), `GET /p1/demo/data-files`, `POST /p1/candidates/import`, `POST /p1/candidates/{id}/submit|approve|disburse` |
| Simulation | `SimulationTab` + `FacilityTab` + `GovernanceTab` | `state.sim_month`, `GET /p3/.../facilities`, `GET /p4/.../ifrs9`, `GET /governance/api/v1/canon/*`, `POST /p1/demo/tick`, `POST /p1/demo/reset` |

### 12.4 API client (`api.js`)

The canonical endpoint table a replacement front-end must know:

```js
const API = {
  // P1 demo
  demoState:   '/p1/demo/state',
  demoTick:    '/p1/demo/tick',
  demoReset:   '/p1/demo/reset',
  demoSse:     '/p1/demo/events/sse',
  dataFiles:   '/p1/demo/data-files',
  importFile:  '/p1/candidates/import',
  candidates:  '/p1/candidates',
  // P3
  facilities: '/p3/api/v1/p3/facilities',
  packets:    '/p3/api/v1/p3/packets',
  ledger:     '/p3/api/v1/p3/ledger',
  postings:   '/p3/api/v1/p3/postings',
  audit:      '/p3/api/v1/p3/audit',
  reconcile:  '/p3/api/v1/p3/reconcile',
  // P4
  p4Balances:          '/p4/api/v1/p4/buffer/balances',
  p4Adequacy:          '/p4/api/v1/p4/pool/adequacy',
  p4Capital:           '/p4/api/v1/p4/capital/snapshot',
  p4Ifrs9:             '/p4/api/v1/p4/ifrs9',
  p4Mode:              '/p4/api/v1/p4/mode',
  p4Events:            '/p4/api/v1/p4/events',
  p4VetoConsult:       '/p4/api/v1/p4/veto/consult',
  p4VetoNotifications: '/p4/api/v1/p4/veto/notifications',
  // Governance
  canonCurrent:    '/governance/api/v1/canon/current',
  canonVersions:   '/governance/api/v1/canon/versions',
  tiers:           '/governance/api/v1/tiers',
  tiersProtection: '/governance/api/v1/tiers/protection-rules',
  lexiconTerms:    '/governance/api/v1/lexicon/terms',
  pending:         '/governance/api/v1/pending',
  pendingSummary:  '/governance/api/v1/pending/summary',
  stagingMode:     '/governance/api/v1/staging/mode',
  vetoLog:         '/governance/api/v1/vetoes',
  interfaces:      '/governance/api/v1/interfaces/summary',
  pillars:         '/governance/api/v1/pillars',
};
```

`request()` throws `Error(detail)` with `.status` on any non-2xx. Status 204
returns `null`. File upload uses `FormData` → `POST /p1/candidates/import/file`.

### 12.5 `useDemoState` hook (poll + SSE merge)

```js
useDemoState(pollMs = 5000)
  → { state, connected, lastEvent, error, refresh, forceUpdate: refresh }
```

- **Poll:** `GET /p1/demo/state` every `pollMs` ms.
- **SSE:** `EventSource('/p1/demo/events/sse')` — on each message, if
  `payload.state` exists, merge it into `state`; otherwise ignore.
- **Reconnect:** on `onerror`, close + retry after 3 seconds; skip reconnect when
  `document.visibilityState === 'hidden'`.
- **`connected`** drives the Live · SSE indicator vs. "Polling" label. `error` is
  set when the poll fails; a toast fires in `App.jsx`.

### 12.6 Approve action

```js
export const approveCandidate = (id, note) =>
  post(`/p1/candidates/${id}/approve`, {
    approve: true,
    officer_id: 'DEMO-OFFICER-1',
    officer_name: 'Demo Officer',
    note: note || undefined,
  });
```

`MANUAL_APPROVAL_ALWAYS = True` — the demo always requires this call before
disbursement; `submit` alone does not create a P3 facility.

---

## 13. Persistence & the restart guarantee

- **KvStore** (`bank.pillars.api.storage`): one SQLite file per service, one table
  `kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)`. Async (`aiosqlite`). Methods
  `get/set/delete/get_json/set_json`. It is deliberately dumb — it never interprets
  blobs.
- **Lossless codec** (`bank.pillars.api.codec`): engine dataclasses/enums/datetimes/
  sets/tuples are round-tripped through tagged markers so type survives serialization:
  `{"__dc__":<cls>,...fields}`, `{"__enum__":<cls>,"value":v}`,
  `{"__dt__":"<iso>"}`, `{"__set__":[...]}`, `{"__tuple__":[...]}`. Decoding resolves
  against per-service class/enum registries (`_CLASSES`/`_ENUMS` in `p3.py`/`p4.py`).
- **Writes:** every P3/P4 mutating call runs through `runtime.run(fn)` which ensures
  load, executes, then writes the **whole snapshot** under the versioned key.
- **Snapshots:**
  - P3 — `p3_state_v1`: facilities, packets, posted events, routed allocation
    questions, recorded collateral, audit records, the P4-veto-router flags, and the
    core-banking ledger (`postings` + `next_id`).
  - P4 — `p4_state_v1`: the four sub-accounts, guarantee pool (positions,
    required-level + revision, received/given books), veto state (track1 + track2 +
    notification log + notifier + governance-review pendings), capital calculator
    (packets, tier D amount, budgeted loss, floor/ratio), IFRS9 stages, mode gate,
    intra-P4 event log, pledge-release manager flags, custody adjustments.
- **Result:** a restarted process rehydrates every facility, posting, audit record,
  buffer balance, guarantee position, veto freeze, staging class, mode **and every
  P1 candidate row** — byte-identically. That is exactly what `/ready` asserts
  (fresh P3/P4 runtimes over the same file) and what the P1 demo drives against.
  After `POST /p1/demo/reset` the KvStore blobs are brand-new and empty and the
  `p1_candidates` table is wiped; after a process restart the same blobs and rows
  reappear exactly as they were left.

---

## 14. End-to-end data flows

### 14.1 Standard origination flow (P1 → P2 → P3 → P4)

```
P1 intake:
  POST /p1/candidates/import (carrier JSON)  or  POST /p1/candidates (intake form)
      ──▶ candidate "new", payment_behavior auto-generated (SHA-256-seeded per id)
  POST /p1/candidates/{id}/submit
      ──▶ real P2 score + risk packet mirrored to P4 via mirror_risk_packet
      ──▶ candidate status → "scored"
  POST /p1/candidates/{id}/approve  (ALWAYS manual officer, MANUAL_APPROVAL_ALWAYS=True)
      ──▶ real P3 originate (record packet + facility → APPROVED) + pledge collateral if any
      ──▶ IFRS9 stage-1 mirror to P4
      ──▶ candidate status → "approved"
  POST /p1/candidates/{id}/disburse
      ──▶ real P3 disburse (PRINCIPAL_MOVEMENT posted to core banking)
      ──▶ candidate status → "disbursed"
  POST /p1/demo/tick (one simulated month)
      ──▶ repayment / delinquent / default / recovery / close (see §11.3)

End-to-end id chain:
  candidate_id (P1 UUID) → application_id (APP-...) → facility_id (FAC-...) → facility_ref (P4)

P2 → P3 handoff (standalone flow, also used internally by P1):

BorrowerApplication ──POST /p2/v1/score──▶ ScoringResult (packet status APPROVED/PROVISIONAL/CONDITIONAL)
                                             │ (front-end holds session; officer may need to confirm)
                                             ▼
                        POST /p3/api/v1/p3/originate  (body = P2OutputPacket)
                                             │  P2Gate records packet + origination gate; facility APPROVED
                                             ▼
                        POST /p3/api/v1/p3/pledge-collateral  (facility_id, packet, external_reference)
                                             │  CollateralObject recorded against facility
                                             ▼
                        POST /p3/api/v1/p3/disburse  (facility_id, amount, currency, packet)
                                             │  state -> ACTIVE; PRINCIPAL_MOVEMENT posted to core banking;
                                             │  audit record appended
                                             ▼
        POST /p4/api/v1/p4/risk-packet        ◀── P2 risk data (BRR/PD/LGD/EAD/EL) into capital + IFRS9
        POST /p4/api/v1/p4/staging-signal     ◀── stage 1..3 IFRS9 signal straight to EL Pool (bypasses P3)
        POST /p4/api/v1/p4/required-guarantee-level  ◀── R_pool for pool adequacy monitoring
```

### 14.2 Live servicing (money movement)

- **Repayment** (`POST .../p3/repayment`): `income_event` (`LOAN_INCOME`) +
  `principal_event` (`PRINCIPAL_MOVEMENT`) posted to the ledger; the income event
  sets `routes_allocation_question_to_p4=true`, i.e. P3 also emits an
  `AllocationQuestion` to P4 (the "micro/macro cut": P3 records per-loan, P4 decides
  portfolio treatment). Facility → `REPAYING`. Two audits.
- **Risk premium / origination fee / loss events** are typed postings; premium and
  loss events also route allocation questions to P4. The P4 side routes typed
  `Pillar3Event`s onto sub-accounts (RP Pool funds EL Pool; losses draw the EL Pool /
  ULA / guarantee call).
- **Reconciliation** (`GET .../p3/reconcile?tolerance=`): sums P3 events vs core
  banking, returns discrepancy + unmatched ids; core banking wins in any dispute.

### 14.3 Deterioration & default

```
facility DELINQUENT (POST mark-delinquent) ──▶ drawdowns frozen
    │   failure continues
    ▼
facility DEFAULT (POST mark-default) ──▶ LOSS_RECOVERY marker event posted
    │   IFRS9 signal moves facility to Stage 3 (P2→P4 direct)
    │   EL Pool provision increases; pool adequacy may shortfall; CapitalSnapshot re-evaluated
    ├── workout: POST /p3/restructure  (packet.human_authorised_for_workout=true)  RESTRUCTURING → ACTIVE
    └── workout: POST /p3/recovery     (recovered_amount, currency)                RECOVERY
                  POST /p3/close        (packet)                                   CLOSED
```

### 14.4 Prudential veto (bank-level safety switch)

```
Continuous: POST /p4/api/v1/p4/recompute-track1 reads EL Pool/LR balances + guarantee
books → CapitalSnapshot → Track 1 triggers evaluated
    │  any breached (TierD/RWA <12%, EL >2%, G/G >1.0, LR below min, concentration, CASS severe)
    ▼
Track 1 FROZEN ──▶ Orchestrator notified (veto/notifications) ──▶ /governance veto log records event
    │  freeze is non-overridable by P2/P3
    ▼
P2 consults: GET /p4/api/v1/p4/veto/consult (frozen?) → confirm_packet returns false → packet withheld
   │   (resolution-at-P2; the freeze is never pushed to P3 — P3 only ever sees an absent/withheld packet)
   ▼
Governance reviews (veto log resolve: RESTART_AUTHORIZED | PACKET_REMAINS_WITHHELD)
   → only then P4 POST /p4/api/v1/p4/veto/lift-track1 un-freezes
```

### 14.5 Mode gate

`/governance/api/v1/staging/mode` starts `CONVENTIONAL` (the permanent floor).
Adaptive machinery exists but is dormant — `GET /p4/api/v1/p4/mode` reports it, and
only an explicit signed `GovernanceRuling` via `POST /p4/api/v1/p4/mode/activate`
can switch; `POST .../mode/fallback` returns to conventional.

### 14.6 Where each screen's data comes from (decision table)

| Use case | Endpoint(s) |
| --- | --- |
| Intake / candidate pipeline | `/p1/candidates`, `/p1/candidates/{id}/submit|approve|disburse`, `/p1/candidates/import` |
| Live demo state & tick | `/p1/demo/state`, `/p1/demo/tick`, `/p1/demo/events/sse` |
| Candidate profiles / import | `/p1/demo/profiles`, `/p1/demo/data-files`, `/p1/candidates/import` |
| Bank health / capital | `/p4/api/v1/p4/capital/snapshot`, `/p4/api/v1/p4/pool/adequacy`, `/p4/api/v1/p4/buffer/balances`, `/ready` |
| Exposure & provisioning | `/p4/api/v1/p4/risk-packet`+`staging-signal` (feeds), `/p4/api/v1/p4/ifrs9` |
| Facility list / detail | `/p3/api/v1/p3/facilities`, `/p3/api/v1/p3/facilities/{id}` |
| Facility lifecycle timeline | `/p3/api/v1/p3/audit/{facility_id}` |
| Ledger / treasury | `/p3/api/v1/p3/postings`, `/p3/api/v1/p3/ledger`, `/p3/api/v1/p3/reconcile` |
| Candidate scoring (P2) | `/p2/v1/score`, `/p2/v1/ews`, `/p2/v1/override/open`, `/p2/v1/override/close` |
| Veto / compliance | `/p4/api/v1/p4/veto/consult`, `/governance/api/v1/vetoes`, `/p4/api/v1/p4/veto/notifications` |
| Mode / stage / gates | `/p4/api/v1/p4/mode`, `/governance/api/v1/staging/*` |
| Policy / terms / tiers | `/governance/api/v1/canon/*`, `/governance/api/v1/lexicon/*`, `/governance/api/v1/tiers*`, `/governance/api/v1/pillars` |
| Pledges | `/p4/api/v1/p4/pledge/*` |

---

## 15. What makes this a bank system

1. **Deterministic, governed life cycle.** A facility can only change state along the
   Spec §2 table; every action requires a confirmed (and for workouts,
   human-authorised) P2 packet — P3 "takes no independent decision".
2. **Double-entry-ish reality via a core-banking ledger + mandatory audit.** Every
   economic event is posted to a core-banking ledger and produces a full `AuditRecord`
   with a mandatory field set; loss of a field is a construction error, not a silent
   gap. Daily reconciliation treats core banking as ground truth and **raises** (not
   logs) breaches.
3. **Prudential safety rails, continuously.** Tier D/RWA floor, 2% budgeted-loss
   bound, guarantees-granted/guarantees-received leverage bound, liquidity minimum,
   concentration monitors, IFRS9 staging with ECL provisioning — all computed from
   live balances, not faked.
4. **Veto power with a governance review loop.** The bank can freeze origination
   (portfolio-wide or per-facility), and that freeze cannot be overridden by the
   originating/executing pillars; only governance can authorise a restart.
5. **No double-counting of conservatism.** P2 applies MoC once, flags it on the
   packet, and P4 consumes it as-is.
6. **Structural role separation.** "No allocation logic in P3", "no per-loan P4↔P3
   interface", "P4 enters no individual case", "P2 does not run the ledger",
   "do-not-resolve-in-code" for PENDING items — enforced in code and in the
   governance boundary registry.
7. **A ratified constitution.** All mutations are gated on the Canon being
   `RATIFIED`; change control, dependencies and ratification votes are recorded;
   the lexicon is locked.
8. **Restart correctness as a service contract.** The `/ready` probe proves a fresh
   boot rehydrates byte-identically — the data you render is the data that survives.
9. **Conventional Mode is the floor.** Adaptive/stablecoin machinery may be built but
   may not run without a signed governance ruling (permanent floor).

9. **A watched life cycle.** P1 materializes the whole story — intake form → real
   P2 score → real P3 facility → real P4 provisioning → repay / delinquent /
   default / recovery — animated one month at a time, with every intermediate state
   reproducible after restart. The demo SSE stream makes every transition visible.

---

## 16. Seeded demo data & intake profiles

The system boots **empty**. The demo starts from a clean slate — no candidates, no
P3 facilities, no P4 balances. To preload content, either:

* set `BANK_ORCH_SEED_DEMO=true` before starting, which imports the six profile
  carriers from `bank_system/data/candidates/*.json` (idempotent — skipped if
  `p1_candidates` already has rows), or
* run `POST /p1/candidates/import` per carrier JSON on a running server, or
* run `POST /p1/demo/seed` to insert the six built-in profiles directly.

The six profiles (exported from the seed definitions to
`data/candidates/<slug>.json` by `python -m bank.pillars.p1.export_candidates`)
reproduce the original demo_3 data tiers exactly:

| Profile | Data | Outcome | Requested | Disbursed | Story in one line |
| --- | --- | --- | --- | --- | --- |
| Ahmed — Corner Shop | small | paid | $8,000 | $6,000 | Thin file, steady payments |
| Yusuf — Street Vendor | small | default | $5,000 | $4,000 | Thin file, defaults month 3 |
| Layla — Textile Exporter | medium | paid | $32,000 | $22,000 | Partial data, strong fundamentals |
| Omar — Fruit Vendor | medium | default | $15,000 | $12,000 | Partial data, stressed metrics |
| Nadia — Catering Service | good | paid | $45,000 | $35,000 | Full data, strong credit profile |
| Fatima — General Store | good | default | $25,000 | $20,000 | Full data, over-leveraged |

Every carrier JSON is a plain `CandidateImport` payload: intake fields, the full
serialized `BorrowerApplication` (`application_json`), the explicit
`payment_behavior` repayment table, and `seed_profile`. Importing one re-runs it
through the **real** P2 → P3 → P4 pipeline exactly as a live intake would — zero
fabrication.

For governance the register seed (`python -m
bank.orchestrator.governance.seed.seed`) creates the Canon lineage with **V3.4
RATIFIED** (instruments RI-1/2/3), the lexicon, tier table, pillar boundaries, the
7 interface rules, the CASS stub, staging/mode registry, PENDING register and
change-control examples.

Expected month-0 readbacks after an empty boot: `GET /p1/demo/state` → 0
candidates, `sim_month` 0, P4 balances all zero, `track1_status` `clear`;
`GET /p4/api/v1/p4/ifrs9` → `{}`; `GET /p3/api/v1/p3/facilities` → `[]`.

---

## 17. Front-end integration checklist

1. **Always call `http://<host>:8000`** — never another port. Use
   orchestrator-mounted paths.
2. **Verify liveness & integrity first:** `GET /health`, `GET /ready`. Keep
   `/ready` green; a `503 degraded` means engine state is suspect — show it
   prominently in your ops UI.
3. **Respect the exact prefixes:** `/p1/...`, `/p2/...`, `/p3/api/v1/p3/...`,
   `/p4/api/v1/p4/...`, `/governance/api/v1/...`. Each mount has
   `{prefix}/docs` + `{prefix}/openapi.json`.
4. **Drive the demo from P1.** Candidates enter via `POST /p1/candidates`
   (intake form) or `POST /p1/candidates/import` (carrier JSON;
   `POST /p1/candidates/import/file` for file uploads). Move them through
   `submit` → `approve` → `disburse`, then advance the world with
   `POST /p1/demo/tick`.
5. **Subscribe to `GET /p1/demo/events/sse`** and merge every `payload.state`
   into your view; poll `GET /p1/demo/state` as the reconnect/backup path
   (30-second idle heartbeat frames are `{}` — ignore them).
6. **Never render an engine value raw.** P3/P4 GETs return codec envelopes
   (`{__enum__:…,value:…}`, `{__dt__:…}`, `{__dc__:…}`, sets/tuples).
   Unwrap with `asText()` (see §12.2). P1 state and P1 candidate fields
   are already plain JSON.
7. **Understand the packet handoff:** every P3 mutation needs the
   `P2OutputPacket` in the body; workouts require
   `human_authorised_for_workout=true`. Rejections are `409`/`422` with a
   `detail` string — render it to the user.
8. **Split your screens by truth source:**
   - Candidate pipeline ⇒ **P1** (`/p1/candidates`, statuses + P2 score echo).
   - Bank/portfolio posture ⇒ **P4** (`capital/snapshot`, `pool/adequacy`,
     `buffer/balances`, `ifrs9`, `mode`, `veto/*`).
   - Facility lifecycle & money ⇒ **P3** (facilities, audit, postings, ledger,
     reconcile).
   - Policy & compliance ⇒ **Governance** (canon, lexicon, tiers, interfaces,
     staging, vetoes, pending).
9. **Never fabricate financial numbers client-side** — they all come from engine
   state; the six seeded profiles give truthful demo values to start from.
10. **Treat P3/P4/P1 as stateful** — they persist across restarts; refresh from
    GETs, don't assume a clean slate.
11. **Mode matters:** if adaptive machinery isn't active, don't show ABSF/CASS
    numbers as live — read `/p4/api/v1/p4/mode` and
    `/governance/api/v1/staging/is-adaptive-active`.
12. **Vetoes are a governance loop:** show freeze state from `veto/consult` and
    the governance `vetoes` log together, so users see why originations are
    withheld.
13. **Pagination/simulation:** GETs return full collections; do client-side
    pagination for long audit/ledger lists.

**Golden rule.** Build the mental model once: P1 ingests and animates the pipeline,
P2 decides credit quality, P3 executes facility operations and the ledger, P4
enforces loss protection and aggregate health, Governance defines and enforces the
rules, and the Orchestrator makes it all one system behind a single URL.