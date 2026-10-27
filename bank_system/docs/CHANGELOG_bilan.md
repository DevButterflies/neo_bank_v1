# Bilan & ledger fixes — changelog

What changed in `bank_system/`, why, and how to verify it. This file replaces the
round-1 instruction sheet (`bug_bilan_fix.md`, deleted); the round-2 instruction
sheet (`bug_bilan_fix_round_2.md`) stays as-is.

**Bug IDs are stable.** Source comments and tests cite them, e.g. ``B5``,
``B7``, ``R1``. A reference like `see docs/CHANGELOG_bilan.md, B5` points at the
row in the tables below.

Two rounds:

| Round | Sheet | Bugs | Tests before → after |
|---|---|---|---|
| 1 | `bug_bilan_fix.md` (deleted) | B1–B10, Tasks 0–8 | 220 passed + 1 pre-existing failure → **221 passed, 0 failed** |
| 2 | `bug_bilan_fix_round_2.md` | R0–R5 | 221 → **255 passed, 0 failed** |

No pre-existing test was ever allowed to fail, and no public JSON field was
renamed or removed in either round.

---

## Round 1 — B1 to B10

### Baseline (Task 0)

`pytest -q` before touching anything: **220 passed, 1 failed**. The single
failure was pre-existing and not related to the bilan:

* `tests/integration/test_demo_root.py::test_root_serves_demo_index` asserted a
  legacy `demo/static` page and a `Bank Orchestrator` title that the Vite SPA
  frontend no longer serves. Fixed in round 2 (**R0**), never silently.

### The bugs

| ID | Bug | Severity |
|---|---|---|
| B1 | Opening cash was a plug computed to force Actif == Passif, so `balanced: true` proved nothing | High |
| B2 | Defaulted loans were never written off: account 4110 showed 20,200 outstanding while all 6 loans were CLOSED | High |
| B3 | Recoveries (`LOSS_RECOVERY` / "recovery receipt", 13,500) never reached cash; the UI called them "sinistres" | High |
| B4 | Provision 4280 was the P4 EL-Pool balance, not IFRS 9 ECL, and the code then subtracted it from cash (`cash -= ecl_total - el_pool`) — i.e. created money | High |
| B5 | `record_repayment` accepted any principal (one loan repaid 25,000 on 22,000 drawn); `_outstanding()` hid it with `max(0, …)` | High |
| B6 | Result (1190) ignored the principal loss | High |
| B7 | `given_book` (guarantees granted, 99,000) never decreases | Medium — needs owner decision |
| B8 | `tier_d` was read live into derived opening cash, so a governance capital change rewrote past cash | Medium — needs owner decision |
| B9 | `PUT /bilan/config` had no auth and no audit, and moves cash directly | Medium |
| B10 | Money is `float`; the opening-cash formula was duplicated in `router.py` and `compute.py` | Low |

### What was changed

| ID | Fix | Files |
|---|---|---|
| B5 | Guard: new `RepaymentExceedsOutstandingError`; `record_repayment` computes disbursed/repaid from posted events **before** `state_machine.receive_repayment` and rejects negative or over-outstanding principal (no partial posting). Simulator clamps each due principal to the real outstanding and skips the P3 post when nothing is left to pay. New `_paid_principal()` helper that does not hide negatives. | `src/bank/pillars/p3/errors.py`, `src/bank/pillars/p3/engine/orchestrator.py` (`_assert_repayable`), `src/bank/pillars/p1/simulator.py`, `src/bank/pillars/api/p3.py` (4xx mapping) |
| B2, B3 | `mark_default(..., loss_amount, currency)` posts a real `LOSS_RECOVERY` event with memo `write-off` next to the legacy zero-amount marker, so P3 (the ledger the bilan reads) knows the loss. Retry-safe: exactly one write-off event. Memo constants live in one module, no magic strings. | `src/bank/pillars/p3/engine/orchestrator.py`, **new** `src/bank/pillars/p3/domain/memos.py` (`MEMO_WRITE_OFF`, `MEMO_RECOVERY`, `MEMO_DEFAULT_MARKER`), `src/bank/pillars/p1/simulator.py` |
| B1, B4, B6 | `compute.py` reworked: `credits_clients = dec - rem - rad`; `tresorerie = T0 + rem + int + frais + rec - dec` (no EL-Pool/ECL term); `resultat = resultat_ant + int + frais + rec - rad - ecl_total`; `provisions = ecl_total`. EL-Pool moved to `hors_bilan` as a memo only. Single `opening_cash(cfg, p4)` implementation. `BilanConfig.tresorerie_ouverture: float \| None` — `None` = derived (legacy), a number = configured and independently checked. `movements()` classifies events by memo (`recouvrements`, `radiations`, `sinistres` kept as alias of `radiations`, `non_classes`), builds `par_facilite`, and infers a write-off for legacy facilities with a default marker and no write-off event (surfaced as a warning, never silent). | `src/bank/orchestrator/bilan/compute.py`, `config.py`, `router.py` (response models + duplicate formula removed) |
| – | `checks: list[{id, ok, detail}]` + `reliable: bool` + `warnings: list[str]` replace the single `balanced` flag (`balanced` kept). Round 1 shipped 6 checks: `BALANCE`, `OPENING_CASH_INDEPENDENT`, `NO_OVERPAYMENT`, `CLOSED_FACILITIES_ZERO_BALANCE`, `NO_UNCLASSIFIED_LOSS_EVENTS`, `NO_NEGATIVE_RECEIVABLE`. Round 2 added a 7th (R3). | `compute.py`, `router.py` |
| B9 | `PUT /bilan/config` requires header `X-Admin-Token` == setting `bilan_admin_token` (`BANK_ORCH_BILAN_ADMIN_TOKEN`), `hmac.compare_digest`; unset setting → 403 (secure by default). Every accepted change appends `{old, new, timestamp}` to the append-only KV list `bilan_config_audit_v1`. GET endpoints stay open. | `src/bank/orchestrator/config.py`, `src/bank/orchestrator/bilan/router.py` (`_require_admin_token`, `_append_audit`) |
| B7, B8 | **Flag only, no behaviour guessed** (owner decision pending). B7: warning when guarantees granted are outstanding and all facilities are CLOSED. B8: with configured opening cash, a later capital change makes `BALANCE` fail on purpose — that failure is the signal. Both carry `TODO(owner)`. | `compute.py`, `tests/unit/test_bilan_compute.py` |
| B10 | Opening cash computed in exactly one place (`compute.opening_cash`), imported by the router. `float` → `Decimal` inside `compute.py` **not done** (low priority, still open). | `compute.py`, `router.py` |
| Task 8 | Frontend Bilan page/labels brought in line with the new payload. | `bank-demo-frontend/src/pages/Bilan.jsx`, `bank-demo-frontend/src/data/mock.js` |

---

## Round 2 — R0 to R5

Round-1 gaps found in review, plus repository hygiene.

### R0 — baseline: fix the pre-existing failure

`tests/integration/test_demo_root.py` rewritten **as a test only** — `main.py`
was deliberately left untouched. It now asserts the Vite SPA contract the demo
actually serves: `GET /` is 200 with `<div id="root">`, `/assets/` exists, and
the first `src="/assets/…js"` bundle is served with content. The legacy
`Bank Orchestrator` / `/static/app.js` assertions were dropped.

**Result: 221 passed, 0 failed.**

### R1 — validate write-off amounts

New attack surface created by round 1: `mark_default(loss_amount=1e12)` on a
10,000 loan was accepted, so were `nan`/`inf`.

* New `_assert_writable(facility_id, loss_amount)` in `orchestrator.py`, called
  **first** in `mark_default` (before `state_machine.mark_default` and before
  any post, so nothing is partially posted):
  * non-finite or negative → `ValueError`;
  * `disbursed > 0` and `loss_amount > (disbursed - repaid) + 0.005` → new
    `WriteOffExceedsOutstandingError(Pillar3Error)` (`errors.py`).
* Registered in `api/p3.py` `_KIND_422`, and the query param is now
  `loss_amount: float = Query(0.0, ge=0, allow_inf_nan=False)`.

Tests: new `tests/unit/test_write_off_guard.py` (7 tests — over-outstanding,
`nan`/`inf`/`-inf`, negative, exactly-equal accepted, below-outstanding
accepted, undisbursed facility skipped, rejected write-off leaves state
unchanged), plus `tests/integration/test_p3_write_off_http.py` (6 tests —
the same contract over HTTP, see *Final verification* below).

### R2 — non-finite and negative interest in the repayment path

`nan < 0` and `nan > x` are both `False`, so the round-1 guard let `nan`
principal and `interest=-5` through.

* Central guard in `PostingService.capture_and_post`
  (`src/bank/pillars/p3/engine/posting_service.py`): a non-finite or non-numeric
  amount raises `ValueError` **before the event is built** — so no event is
  posted and no allocation question is routed, for every event type.
* `_assert_repayable(facility_id, principal_amount, interest_amount)` now takes
  the interest too and rejects non-finite/negative principal **and** interest;
  called before `state_machine.receive_repayment` in `record_repayment`.

Tests: `tests/unit/test_repayment_guard.py` (non-finite principal, non-finite
and negative interest, non-finite disbursement, plus a positive guard-the-guard
case) and `tests/unit/unit/test_posting_service.py` (parametrised non-finite +
non-numeric amount, asserting no postings and no routed questions).

### R3 — one more bilan check

`CHECK_RECOVERY_WITHIN_WRITE_OFF` in `compute.py`: for every facility
`rec <= rad + 0.005`; on failure the detail lists the offending facilities
(`F1 rec 12000.00 > rad 10000.00`). A facility cannot recover more than it
wrote off.

Tests: golden scenario passes it (`reliable is True`); a facility lent 10,000,
written off 10,000, recovered 12,000 trips it while `NO_OVERPAYMENT`,
`CLOSED_FACILITIES_ZERO_BALANCE` and `NO_NEGATIVE_RECEIVABLE` stay clean and
`reliable` flips to `False`.

### R4 — frontend contract + non-atomic audit write

1. `GET /bilan/config` returns `tresorerie_ouverture_configured: bool` on
   `BilanConfigView` — `true` only when the value was explicitly configured.
   The existing `tresorerie_ouverture` field is unchanged and still carries the
   resolved number, so a client that only reads the number keeps working.
2. `put_bilan_config` wraps `_append_audit` in `try/except`: if the audit write
   fails it is logged (`logger.exception`) and the endpoint still returns 200,
   because the config write itself succeeded. Config and audit are two separate
   KV writes and are **not** atomic — documented in the endpoint docstring.
   No transaction layer was added, as instructed.

Tests: `tests/integration/test_bilan.py` — configured-vs-derived flag, and a
monkeypatched failing `_append_audit` still yields 200 with the change applied.

**Result after R0–R4: 249 passed, 0 failed.** The HTTP-level contract test
(`tests/integration/test_p3_write_off_http.py`, 6 tests) was added while
writing the final verification, bringing the suite to **255 passed, 0 failed**.

### R5 — repository hygiene

Removed from the deliverable:

* all 10 `*.log` files (`app.*`, `live.*`, `orch.*`, `server*`) and `server.pid`
* `data/orchestrator.db.bak-20261007-133644` (the pre-fix numbers)
* `src/bank_system.egg-info/`
* the `bilan_config_audit_v1` row in the shipped `data/orchestrator.db` — 4
  smoke-test entries, so a fresh install starts with an empty audit trail

New `.gitignore`: `*.log`, `server.pid`, `*.bak-*`, `*.egg-info/`,
`__pycache__/`, `.pytest_cache/`, `.venv/`, `node_modules/`.

**`data/*.db` is deliberately NOT ignored** — the shipped `orchestrator.db`
carries the verified golden scenario and is part of the deliverable.

This file replaces `bug_bilan_fix.md`; the eight code comments and docstrings
that cited it (B2, B4, B5, B7, B8) now cite `docs/CHANGELOG_bilan.md` with the
same bug ID.

---

## How to verify

```bash
cd bank_system

# everything — 255 passed, 0 failed
python -m pytest -q

# the round-2 guards, the bilan checks and the HTTP write-off contract
python -m pytest tests/unit/test_write_off_guard.py \
                 tests/unit/test_repayment_guard.py \
                 tests/unit/test_bilan_compute.py \
                 tests/integration/test_p3_write_off_http.py -q

# boundary/integrity suites that must stay green
python -m pytest tests/unit/integrity tests/unit/unit/test_posting_service.py -q
```

Live smoke test (note: P3 routes are mounted **twice** — the real path is
`/p3/api/v1/p3/...`, not `/p3/...`):

`POST /mark-default` also requires a Pillar 2 packet as its JSON body, so a
bare `curl` without `-d` returns 422 for a *missing body* and would mask the
guard's own answer. The end-to-end proof — origination, disbursement, then
each rejected amount, asserting zero events were posted — lives in
`tests/integration/test_p3_write_off_http.py`; the smoke below only re-checks
the status codes.

```bash
export BANK_ORCH_BILAN_ADMIN_TOKEN=test-token
uvicorn bank.orchestrator.main:app --port 8000 &

# write-off guards -> 422 each
curl -s -o /dev/null -w '%{http_code}\n' \
  "localhost:8000/p3/api/v1/p3/mark-default?facility_id=FAC-X&loss_amount=nan"
curl -s -o /dev/null -w '%{http_code}\n' \
  "localhost:8000/p3/api/v1/p3/mark-default?facility_id=FAC-X&loss_amount=1e12"
curl -s -o /dev/null -w '%{http_code}\n' \
  "localhost:8000/p3/api/v1/p3/mark-default?facility_id=FAC-X&loss_amount=-1"

# golden numbers
curl -s localhost:8000/bilan | python -c "import sys,json;d=json.load(sys.stdin);print(d['balanced'],d['reliable'],d['totaux'],d['ecart']);[print(c) for c in d['checks']]"

# config: 403 without the token, 200 with it
curl -s -o /dev/null -w '%{http_code}\n' -X PUT localhost:8000/bilan/config \
  -H 'content-type: application/json' -d '{"depots_clients": 50000}'
curl -s -o /dev/null -w '%{http_code}\n' -X PUT localhost:8000/bilan/config \
  -H 'content-type: application/json' -H 'X-Admin-Token: test-token' \
  -d '{"depots_clients": 50000}'
```

Expected on the shipped DB: `balanced True reliable True`,
`ecart 0.0`, `totaux 95510.0 / 95510.0`, 4110 = 0, 1190 = -4,490,
4280 = 0, and **all 7 checks `[True]`**.

Acceptance:

* [x] No test that passed in the baseline fails now (221 → 255, 0 failed).
* [x] A repayment above the outstanding principal is impossible (P3 guard + simulator clamp).
* [x] NaN/negative principal, interest, disbursement and write-off amounts are rejected before anything is posted.
* [x] A write-off above the outstanding balance raises `WriteOffExceedsOutstandingError` (HTTP 422).
* [x] After a default, P3 holds a `write-off` event with the loss amount, posted exactly once.
* [x] `GET /bilan` on the golden scenario returns 95,510 / 0 / -4,490 with `reliable: true`.
* [x] Cash does not change when the P4 EL-Pool balance changes.
* [x] `balanced: true` together with `reliable: false` is possible and visible when the opening cash is derived.
* [x] `PUT /bilan/config` is rejected without the token and audited with it.
* [x] `sinistres` means write-offs; `recouvrements` carries the recoveries.
* [x] Repository ships no logs, no `.bak`, no `egg-info`, and an empty audit trail.

---

## Still open on purpose (needs a human decision — do NOT implement)

| ID | Item | Current behaviour |
|---|---|---|
| B7 | Should `given_book` (guarantees granted, 99,000) shrink on repayment / write-off? `project.md` does not define the semantics. | Warning in `warnings` when guarantees are outstanding and all facilities are CLOSED; `TODO(owner)` in `compute.py`. |
| B8 | Is a capital change after opening a cash contribution? (Option: a `tier_d_ouverture` config field booked as a cash inflow.) | With configured opening cash, `BALANCE` fails on purpose when `tier_d` changes — that failure is the signal. |
| – | Provision 4280 = IFRS 9 ECL and EL-Pool = prudential memo only: an accountant must confirm. | Implemented that way, `TODO(owner)` in `compute.py`. |
| B10 | `Decimal` instead of `float` inside `compute.py` (JSON boundary unchanged). | Not done — low priority. |

Out of scope for both rounds (noted, not fixed): governance endpoint 500,
mutation-before-persist in `api/p3.py`, IFRS 9 `_synced_provision`
double-count, CORS `allow_origins=["*"]`, path traversal in `p1/router.py`.

---

## Frontend note

The UI source is not in this repo. `mouvements.sinistres` now means **write-offs**
(`radiations` is its new name; `sinistres` is kept as an alias), and a separate
`mouvements.recouvrements` carries the recoveries. The Bilan page should show a
"Recouvrements" line, and `GET /bilan/config` now also returns
`tresorerie_ouverture_configured`.
