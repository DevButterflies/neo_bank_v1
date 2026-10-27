# Bank System – Round 2 (remaining fixes)

Round 1 is done and verified (221 tests pass, golden numbers match on the shipped DB).
This round closes the gaps found in the final review. Same rules as before: one task at a time, run the tests after each, do not touch unrelated code, report anything you assume.

```bash
cd bank_system
python -m pytest -q          # baseline must be 221 passed before you start
```

---

## R1 – Validate write-off amounts (new attack surface created by round 1)

`mark_default(facility_id, packet, loss_amount, currency)` and `POST /p3/mark-default?loss_amount=` accept anything. Verified by probe:

| Input | Result today | Should be |
|---|---|---|
| write-off `1e12` on a 10,000 loan | ACCEPTED | rejected |
| write-off `inf` | ACCEPTED | rejected |
| write-off `nan` | ACCEPTED | rejected |

Fix in `src/bank/pillars/p3/engine/orchestrator.py`:

- Add `_assert_writable(facility_id, loss_amount)` (next to `_assert_repayable`):
  - `loss_amount` must be finite and `>= 0`, else `ValueError`.
  - Using `_principal_totals`, `outstanding = disbursed - repaid`. If `disbursed > 0` and `loss_amount > outstanding + _REPAYMENT_TOLERANCE` → raise a new `WriteOffExceedsOutstandingError(Pillar3Error)` in `errors.py`.
  - Call it **before** `state_machine.mark_default` and before any post (no partial posting).
- Register the new error in `src/bank/pillars/api/p3.py` in the same tuple where `RepaymentExceedsOutstandingError` is mapped to a 4xx.
- In the same file, declare the query param as `loss_amount: float = Query(0.0, ge=0, allow_inf_nan=False)`.

Tests (`tests/unit/test_write_off_guard.py`): over-outstanding, `inf`, `nan`, negative all rejected and **zero events posted**; write-off exactly equal to outstanding accepted; the existing simulator test still passes.

## R2 – Close the NaN / negative-interest hole in the repayment guard

Verified by probe: `record_repayment(..., principal=nan)` and `interest=-5` are ACCEPTED. `nan < 0` and `nan > x` are both False, so the round-1 guard lets NaN through.

Best place (central, covers every event type): `PostingService.capture_and_post` in `src/bank/pillars/p3/engine/posting_service.py`:

```python
import math
if not math.isfinite(amount):
    raise ValueError(f"posting amount must be finite (got {amount!r})")
```

Also in `_assert_repayable` (`orchestrator.py`) add `interest_amount` as a parameter; reject non-finite and negative interest. Update the single call in `record_repayment`.

Then run `tests/unit/integrity` and `tests/unit/unit/test_posting_service.py` (boundary tests) and keep them green.

Tests: `nan`, `inf`, `-inf` for principal, interest, disbursement and write-off all raise; nothing posted.

## R3 – Add one more bilan check (cheap, optional but recommended)

In `compute.py` add check `RECOVERY_WITHIN_WRITE_OFF`: for every facility, `rec <= rad + 0.005`. Failure detail lists the facility ids. Add the id constant next to the other `CHECK_*`, include it in `checks`, and add two tests (ok case, and `rec > rad` flagged). Keep the golden scenario `reliable == True`.

## R4 – Frontend contract (the UI is not in this repo, so only the API side)

1. `GET /bilan/config` returns `tresorerie_ouverture` as the **resolved** value, so a client cannot tell "configured" from "derived". Add `tresorerie_ouverture_configured: bool` to `BilanConfigView` (true when `cfg.tresorerie_ouverture is not None`). Keep the existing field unchanged.
2. Make the audit write safer: in `put_bilan_config`, if `_append_audit` raises, log the error and still return 200 only if the config write succeeded; document the behaviour in the docstring. (Config and audit are two separate KV writes, so they are not atomic. Do not build a transaction layer, just document it.)

## R5 – Repository hygiene (do this last)

Remove from the deliverable, they should not ship:

- `app.err.log`, `app.out.log`
- `data/orchestrator.db.bak-*` (it contains the old, wrong data)
- `src/bank_system.egg-info/`
- Add them to `.gitignore` (`*.log`, `*.bak-*`, `*.egg-info/`, and `data/*.db` if the project does not intend to ship a DB).
- The shipped `bilan_config_audit_v1` contains 4 entries from manual smoke tests (e.g. `depots_clients` 12345 then back to 0). Reset the audit key in the demo seed or delete it from the shipped DB, so a fresh install starts with an empty trail.
- `bug_bilan_fix.md` is a copy of the round-1 instructions. Rename it to `docs/CHANGELOG_bilan.md` and replace its content with a real changelog (what changed, why, how to verify).

## Still open on purpose (need a human decision, do NOT implement)

| ID | Item | Current behaviour |
|---|---|---|
| B7 | Should `given_book` (guarantees granted, 99,000) shrink on repayment / write-off? | Only a warning in `warnings` |
| B8 | Is a capital change after opening a cash contribution? | `BALANCE` fails on purpose when opening cash is configured |
| – | Provision 4280 = IFRS9 ECL, EL-Pool = memo only: accountant must confirm | Implemented that way, marked `TODO(owner)` |
| B10 | `Decimal` instead of `float` in `compute.py` | Not done (low priority) |

## Final verification

```bash
python -m pytest -q                               # all green
python -m pytest tests/unit/test_write_off_guard.py tests/unit/test_repayment_guard.py tests/unit/test_bilan_compute.py -q
export BANK_ORCH_BILAN_ADMIN_TOKEN=test-token
uvicorn bank.orchestrator.main:app --port 8000 &
curl -s "localhost:8000/p3/mark-default?facility_id=X&loss_amount=nan"   # expect 422
curl -s localhost:8000/bilan | python -c "import sys,json; d=json.load(sys.stdin); print(d['balanced'], d['reliable']); print(d['totaux'])"
```

Acceptance: no write-off above outstanding or non-finite amount can be posted; NaN/negative repayments are rejected; the golden scenario still gives cash 95,510, 4110 = 0, result -4,490, `reliable: true`.