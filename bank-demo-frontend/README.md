# Ledger — MSME Credit Control Tower (client demo frontend)

A standalone Vite + React frontend built against the **Bank System — Complete
Engineering & API Reference** you provided. It implements the three things
the demo needs to show:

1. **Control tower** — live KPIs, capital ratios, buffer sub-accounts, IFRS9
   staging, portfolio mix (`/`)
2. **Pipeline** — candidate import → real P2 scoring → manual officer
   decision → disbursement, as a kanban board with a detail drawer
   (`/pipeline`)
3. **Loans** — every originated facility with its live amortization
   schedule, balance chart, and audit trail (`/loans`, `/loans/:facilityId`)

It talks to your orchestrator (`bank.orchestrator.main`, served on `:8000`)
using **exactly** the routes and shapes documented in the API reference. If
the orchestrator isn't reachable, every screen falls back to bundled mock
data shaped like the real responses, so you can review the UI before wiring
it up — you'll see an amber "Showing sample data" strip whenever that
happens.

---

## 1. Where this goes relative to your project

This is a separate frontend, not a patch to your existing `demo/` folder.
You have two ways to use it:

### Option A — run it standalone, next to your backend repo (recommended to start)

```
your-workspace/
├── bank_system/              ← your existing backend (bank.orchestrator.main)
└── bank-demo-frontend/       ← unzip this here
```

```bash
cd bank-demo-frontend
npm install
npm run dev
```

This starts Vite on `http://localhost:5173` and proxies `/health`, `/ready`,
`/governance`, `/p1`, `/p2`, `/p3`, `/p4` to `http://localhost:8000` (see
`vite.config.js`). Start your backend separately, exactly as documented in
§3 of the API reference:

```bash
# in bank_system/, in another terminal
.venv\Scripts\python.exe -m bank.orchestrator.governance.seed.seed
$env:BANK_ORCH_SEED_DEMO = "true"
.venv\Scripts\python.exe -m bank.orchestrator.main
```

Then open `http://localhost:5173`. If your backend runs on a different host
or port, set `BANK_API_TARGET` before starting the frontend:

```bash
BANK_API_TARGET=http://localhost:9000 npm run dev
```

### Option B — replace/merge with your existing `demo/` folder

Your backend already expects to serve a built SPA from `demo/dist` (see
§3 and §10.1 of the API reference: the orchestrator mounts
`demo/dist` at `/` when present). To go this route:

```bash
cd bank_system
rm -rf demo               # or move it aside if you want to keep the old one
# copy the contents of this zip into bank_system/demo/
cp -r /path/to/unzipped/bank-demo-frontend/* bank_system/demo/
cd demo
npm install
npm run build              # emits demo/dist/, which the orchestrator serves at "/"
```

With this option you don't need `vite.config.js`'s proxy at all in
production — same-origin relative paths (`/p1/...`, `/p3/api/v1/p3/...`,
etc.) just work because the orchestrator is serving the built files itself
on the same origin as the API. Keep using `npm run dev` (port 5173, proxied)
for day-to-day frontend iteration; use `npm run build` when you want the
orchestrator to serve the real thing at `/`.

---

## 2. Requirements

- Node.js 18+ and npm
- Your backend running per the API reference §3 (Python venv, `pip install
  -e ".[dev]"`, governance seed, `bank.orchestrator.main`)
- Nothing else — CORS is already open on the backend (`allow_origins=["*"]`
  per §2), so the dev server can call `:8000` directly even without the
  proxy if you point `fetch` at an absolute URL, though the proxy is set up
  for you already.

---

## 3. What's inside

```
src/
  data/
    api.js            Every endpoint from the API reference's canonical
                       table (§12.4), each wrapped with a mock-data fallback
                       and connection-state reporting.
    hooks.js           React Query hooks. LIVE_KEYS + invalidateLive() is
                       the important bit: any SSE frame invalidates P1, P3
                       and P4 queries together (see comment in the file for
                       why — SSE only pushes the P1 snapshot).
    mock.js            Bundled sample data, shaped exactly like real
                       responses in the doc (6 seeded profiles, capital
                       snapshot, IFRS9, audit records, etc).
    useKpiHistory.js   Client-side accumulator for the dashboard's trend
                       chart — see "Known gaps" below, this is a
                       stand-in for a backend history endpoint that
                       doesn't exist yet.
  utils/
    codec.js           asText() / unwrapDeep() — unwraps the P3/P4 tagged
                       JSON envelopes (§12.1/§12.2 of the API reference).
                       Required for anything rendered from a P3/P4 GET.
    connectionStore.js Tiny pub/sub so the UI can show "live vs mock" state
                       anywhere without prop-drilling.
  components/
    shared/            Shell (nav + layout), SseProvider, ReadyBadge,
                       VetoBanner, TickControl, MockModeBanner, Atoms
                       (Panel/StatusBadge/StatLine)
    kpi/               KpiCard, RatioGauge, PortfolioDonut, BalancePanel
    pipeline/          CandidateCard, KanbanColumn, CandidateDrawer,
                       ScorecardPanel, DecisionForm, ImportMenu
    loans/             FacilityTable, AmortizationTable, BalanceChart,
                       AuditTimeline
  pages/
    Dashboard.jsx      "/"          — Control tower
    Pipeline.jsx       "/pipeline"  — kanban + decision drawer
    Loans.jsx          "/loans"     — facility list
    LoanDetail.jsx     "/loans/:facilityId" — schedule + audit trail
```

---

## 4. Running the actual demo script

1. Open **Pipeline**. Click **"+ Bring in a candidate" → Load a demo
   profile**. This seeds the six built-in profiles (idempotent —
   `POST /p1/demo/seed`).
2. Click a card in the **New** column → **Submit for scoring**. Watch it
   move to **Scored** and open the drawer again to show the full Pillar 2
   scorecard (BRR, PD/LGD/EAD/EL, decisioning zone).
3. In the drawer, fill an optional officer note and click **Approve**.
   This is the moment worth narrating: approval is *always* manual
   (`MANUAL_APPROVAL_ALWAYS = True` per the API reference) — there is no
   silent auto-approve path, even for `AUTO_APPROVE`-zoned candidates.
4. Click **Disburse funds**. The candidate becomes a live loan and the card
   moves to **Disbursed**.
5. Open **Loans**, click into the new facility. Show the amortization
   schedule and the (currently empty) audit trail.
6. Use the floating **"Simulate next month ▶"** button (bottom-right,
   visible on every screen) to advance the simulated clock. Watch a payment
   post, the balance chart step down, and a new audit record appear —
   without touching anything else. This is the single best "live system"
   moment in the whole demo.
7. Switch to **Control tower** and tick again from there — the KPIs,
   capital gauges, and portfolio donut all update live via the same click,
   because SSE frames invalidate every screen's data together (see
   `data/hooks.js`).
8. To show the prudential veto story, you'd need a candidate/profile whose
   numbers actually breach a Track 1 trigger (Tier D/RWA, EL vs budget,
   etc.) — the seeded profiles are calibrated to stay within bounds, so this
   isn't demonstrable out of the box. See "Known gaps" below if you want to
   force it for the demo.

---

## 5. Known gaps / recommended backend changes

None of these block the demo — everything above works against the
documented endpoints as-is. Worth doing if you have backend time before the
client meeting:

| # | Gap | Why it happens | Fix | Priority |
|---|---|---|---|---|
| 1 | The **Control tower's trend chart** only has history for the current browser session — a page refresh loses it. | The orchestrator doesn't persist a KPI time series; `sim_month` is a single counter with no stored history. The frontend rebuilds a line client-side on every tick (`src/data/useKpiHistory.js`). | Add a small `p1_kpi_history` KV key that appends a snapshot (`{month, total_outstanding, el_pool, tier_d_over_rwa, ...}`) on every `POST /p1/demo/tick`, plus a `GET /p1/demo/history` route. Swap `useKpiHistory.js` for a fetch against it. | Optional — fine for a scripted live demo as-is |
| 2 | The dashboard needs 3–4 extra round trips beyond `/p1/demo/state` (`capital/snapshot`, `pool/adequacy`, `ifrs9`), none of which are pushed over SSE. | By design — SSE is scoped to the P1 snapshot. The frontend compensates by invalidating those queries on every SSE frame instead (`data/hooks.js` → `LIVE_KEYS`). | Optionally fold a capital/adequacy summary into `/p1/demo/state` (and therefore into SSE frames) so the dashboard updates in one round trip. | Cosmetic polish only |
| 3 | No seeded profile currently breaches a Track 1 prudential trigger, so the **veto banner** (already built, see `components/shared/VetoBanner.jsx`) has nothing to show out of the box. | The six seed profiles are calibrated to stay within Tier D/RWA, EL budget, and G/G bounds. | Either script a manual `POST /p4/api/v1/p4/veto/track2?...&violates_policy=true` call during the demo to trigger it live, or add a seventh "stress" seed profile whose numbers are deliberately over budget. | Only needed if you want to show the veto story live |
| 4 | Chunk-size build warning (`index.js` ~677kB / 192kB gzip). | Recharts + react-query in one bundle; not an issue for a demo served locally or from the orchestrator. | If it matters for a public-facing deploy later, code-split with `React.lazy()` per page. | Cosmetic only |

---

## 6. Design notes

Dark, ledger-styled control room rather than a generic SaaS dashboard:
near-black ink background (`#0B1014`), a single teal accent (`#2FBF9F`) used
consistently for "healthy/performing," amber for "attention," red for
"breach/default." Numbers are set in IBM Plex Mono throughout — this is a
system whose entire value proposition is that every number traces back to a
real ledger, so figures are visually treated as ledger data, not as
decorative stats. Headings use Space Grotesk; body copy uses Inter. See
`tailwind.config.js` for the full token set if you want to adjust the
palette for the client's brand.
