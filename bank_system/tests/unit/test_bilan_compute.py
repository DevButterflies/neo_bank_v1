"""Bilan arithmetic, as pure functions over hand-built dicts.

No database, no HTTP, no fixtures: ``compute_bilan(cfg, p3, p4)`` takes plain
dicts, so every case here is an exact, readable statement about the numbers.

The golden scenario mirrors the six loans the demo simulation actually
produces — including one loan that used to repay more than it drew, which is
why the fixed formulas are worth pinning.
"""
from __future__ import annotations

import pytest

from bank.orchestrator.bilan.compute import compute_bilan, movements, opening_cash, pillars
from bank.orchestrator.bilan.config import BilanConfig

TIER_D = 100_000.0


def ev(kind: str, amount: float, memo: str, fac: str) -> dict:
    return {
        "event_type": {"value": kind},
        "amount": amount,
        "memo": memo,
        "facility_id": fac,
    }


def loan(
    fid: str,
    state: str,
    *,
    lent: float,
    repaid: float = 0.0,
    interest: float = 0.0,
    write_off: float | None = None,
    recovery: float | None = None,
    marked: bool = False,
) -> tuple[list[dict], dict]:
    events = [ev("PRINCIPAL_MOVEMENT", lent, "disbursement", fid)]
    if repaid:
        events.append(ev("PRINCIPAL_MOVEMENT", repaid, "scheduled principal", fid))
    if interest:
        events.append(ev("LOAN_INCOME", interest, "scheduled interest", fid))
    if write_off:
        events.append(ev("LOSS_RECOVERY", write_off, "write-off", fid))
    if recovery:
        events.append(ev("LOSS_RECOVERY", recovery, "recovery receipt", fid))
    if marked:
        events.append(ev("LOSS_RECOVERY", 0.0, "default event marker", fid))
    return events, {fid: {"state": {"value": state}}}


GOLDEN = [
    loan("A", "CLOSED", lent=12_000, repaid=4_000, interest=420, write_off=8_000, recovery=4_500),
    loan("B", "CLOSED", lent=20_000, repaid=8_000, interest=660, write_off=12_000, recovery=7_500),
    loan("C", "CLOSED", lent=4_000, repaid=800, interest=100, write_off=3_200, recovery=1_500),
    loan("D", "CLOSED", lent=22_000, repaid=22_000, interest=1_500),
    loan("E", "CLOSED", lent=6_000, repaid=6_000, interest=480),
    loan("F", "CLOSED", lent=35_000, repaid=35_000, interest=2_050),
]


def build(pairs) -> dict:
    events: list[dict] = []
    facilities: dict = {}
    for evs, facs in pairs:
        events += evs
        facilities.update(facs)
    return {"posted_events": events, "facilities": facilities}


def p4(*, el_pool: float = 2_484.20, ifrs9: dict | None = None) -> dict:
    return {
        "account": {"el_pool": {"balance": el_pool}},
        "ifrs9": {} if ifrs9 is None else ifrs9,
        "capital": {"tier_d_amount": TIER_D},
        "pool": {},
    }


def cfg(**overrides) -> BilanConfig:
    base = {"tresorerie_ouverture": TIER_D}
    base.update(overrides)
    return BilanConfig.model_validate(base)


def line(body: dict, face: str, compte: str) -> float:
    return next(x["montant"] for x in body[face] if x["compte"] == compte)


def check(body: dict, check_id: str) -> dict:
    return next(c for c in body["checks"] if c["id"] == check_id)


# ---------------------------------------------------------------------------
# Golden scenario
# ---------------------------------------------------------------------------


def test_golden_scenario() -> None:
    body = compute_bilan(cfg(), build(GOLDEN), p4())

    mov = body["mouvements"]
    assert mov["decaisses"] == 99_000.0
    assert mov["remboursements"] == 75_800.0
    assert mov["interets"] == 5_210.0
    assert mov["radiations"] == 23_200.0
    assert mov["recouvrements"] == 13_500.0
    assert mov["sinistres"] == mov["radiations"]

    assert line(body, "actif", "4110") == 0.0
    assert line(body, "actif", "5120") == 95_510.0
    assert line(body, "passif", "1190") == -4_490.0
    assert line(body, "passif", "4280") == 0.0

    assert body["totaux"] == {"actif": 95_510.0, "passif": 95_510.0}
    assert body["ecart"] == 0.0
    assert body["balanced"] is True
    assert body["reliable"] is True
    assert body["warnings"] == []
    assert body["hors_bilan"]["el_pool"] == 2_484.20

    assert body["mouvements"]["par_facilite"]["A"]["rad"] == 8_000.0
    assert body["mouvements"]["par_facilite"]["A"]["etat"] == "CLOSED"
    assert body["mouvements"]["par_facilite"]["F"]["rad"] == 0.0


def test_default_is_reported_as_unreliable_but_balanced() -> None:
    body = compute_bilan(cfg(tresorerie_ouverture=None), build(GOLDEN), p4())

    assert body["balanced"] is True
    assert check(body, "BALANCE")["ok"] is True
    assert check(body, "OPENING_CASH_INDEPENDENT")["ok"] is False
    assert "tautological" in check(body, "OPENING_CASH_INDEPENDENT")["detail"]
    assert body["reliable"] is False


def test_configured_opening_cash_makes_balance_a_real_check() -> None:
    body = compute_bilan(cfg(tresorerie_ouverture=90_000.0), build(GOLDEN), p4())

    assert body["ecart"] == -10_000.0
    assert body["balanced"] is False
    assert check(body, "BALANCE")["ok"] is False
    assert check(body, "OPENING_CASH_INDEPENDENT")["ok"] is True
    assert body["reliable"] is False


def test_el_pool_does_not_create_money() -> None:
    without = compute_bilan(cfg(), build(GOLDEN), p4(el_pool=0.0))
    with_pool = compute_bilan(cfg(), build(GOLDEN), p4(el_pool=5_000.0))

    assert line(without, "actif", "5120") == line(with_pool, "actif", "5120")
    assert without["totaux"] == with_pool["totaux"]
    assert with_pool["hors_bilan"]["el_pool"] == 5_000.0
    assert line(with_pool, "passif", "4280") == 0.0


def test_overpayment_is_flagged_on_both_checks() -> None:
    overpaid = [
        (evs, facs)
        for evs, facs in GOLDEN
        if not (evs[0]["facility_id"] == "D")
    ]
    overpaid.append(
        loan("D", "CLOSED", lent=22_000, repaid=25_000, interest=1_500, marked=True)
    )

    body = compute_bilan(cfg(), build(overpaid), p4())

    assert check(body, "NO_OVERPAYMENT")["ok"] is False
    assert check(body, "NO_NEGATIVE_RECEIVABLE")["ok"] is False
    assert line(body, "actif", "4110") == -3_000.0
    assert body["reliable"] is False


def test_closed_facility_with_a_leftover_balance_is_flagged() -> None:
    pairs = list(GOLDEN) + [loan("G", "CLOSED", lent=10_000, repaid=4_000, interest=50)]

    failed = check(compute_bilan(cfg(), build(pairs), p4()), "CLOSED_FACILITIES_ZERO_BALANCE")

    assert failed["ok"] is False
    assert "G" in failed["detail"]


def test_recovery_within_write_off_passes_on_the_golden_scenario() -> None:
    body = compute_bilan(cfg(), build(GOLDEN), p4())

    assert check(body, "RECOVERY_WITHIN_WRITE_OFF")["ok"] is True
    assert body["reliable"] is True


def test_a_recovery_larger_than_its_own_write_off_is_flagged() -> None:
    # Everything else stays consistent (rad covers the whole drawdown, so
    # 4110 and CLOSED_FACILITIES_ZERO_BALANCE both stay clean) — only the
    # new check trips, which is what pins it.
    pairs = GOLDEN + [
        loan("H", "CLOSED", lent=10_000, write_off=10_000, recovery=12_000)
    ]

    body = compute_bilan(cfg(), build(pairs), p4())

    failed = check(body, "RECOVERY_WITHIN_WRITE_OFF")
    assert failed["ok"] is False
    assert "H" in failed["detail"]
    assert check(body, "NO_OVERPAYMENT")["ok"] is True
    assert check(body, "CLOSED_FACILITIES_ZERO_BALANCE")["ok"] is True
    assert check(body, "NO_NEGATIVE_RECEIVABLE")["ok"] is True
    assert body["reliable"] is False


def test_unknown_loss_memo_is_not_silently_swallowed() -> None:
    pairs = list(GOLDEN)
    events, facilities = pairs[0]
    pairs[0] = (
        events + [ev("LOSS_RECOVERY", 500.0, "something-else", "A")],
        facilities,
    )

    body = compute_bilan(cfg(), build(pairs), p4())

    assert body["mouvements"]["non_classes"] == 1
    assert check(body, "NO_UNCLASSIFIED_LOSS_EVENTS")["ok"] is False


def test_zero_amount_loss_events_are_informational() -> None:
    events, facilities = loan("A", "CLOSED", lent=1_000, repaid=1_000, marked=True)
    events.append(ev("LOSS_RECOVERY", 0.0, "some other marker", "A"))

    body = compute_bilan(cfg(), {"posted_events": events, "facilities": facilities}, p4())

    assert body["mouvements"]["non_classes"] == 0
    assert check(body, "NO_UNCLASSIFIED_LOSS_EVENTS")["ok"] is True


def test_legacy_inference_recovers_the_missing_write_off() -> None:
    # Exactly the shape the pre-fix database has: a default marker and no
    # write-off event, so the principal loss has to be reconstructed.
    events, facilities = loan("A", "CLOSED", lent=12_000, repaid=4_000, marked=True)
    events.append(ev("LOAN_INCOME", 420.0, "scheduled interest", "A"))

    body = compute_bilan(cfg(), {"posted_events": events, "facilities": facilities}, p4())

    assert body["mouvements"]["radiations"] == 8_000.0
    assert body["mouvements"]["sinistres"] == 8_000.0
    assert body["warnings"] == ["write-off inferred for A"]
    assert check(body, "CLOSED_FACILITIES_ZERO_BALANCE")["ok"] is True
    assert line(body, "actif", "4110") == 0.0


def test_no_inference_when_a_real_write_off_exists() -> None:
    events, facilities = loan(
        "A", "CLOSED", lent=12_000, repaid=4_000, write_off=8_000, marked=True
    )

    body = compute_bilan(cfg(), {"posted_events": events, "facilities": facilities}, p4())

    assert body["mouvements"]["radiations"] == 8_000.0
    assert body["warnings"] == []


def test_provision_is_ifrs9_ecl_and_never_touches_cash() -> None:
    base = compute_bilan(cfg(), build(GOLDEN), p4(ifrs9={}))
    provisioned = compute_bilan(
        cfg(), build(GOLDEN), p4(ifrs9={"F1": {"ecl": 100.0, "ead": 1_000.0}})
    )

    assert line(provisioned, "passif", "4280") == 100.0
    assert line(provisioned, "passif", "1190") == line(base, "passif", "1190") - 100.0
    assert line(provisioned, "actif", "5120") == line(base, "actif", "5120")
    assert provisioned["hors_bilan"]["rwa"] == 1_000.0


def test_sinistres_is_an_alias_for_radiations() -> None:
    body = compute_bilan(cfg(), build(GOLDEN), p4())

    assert body["mouvements"]["sinistres"] == body["mouvements"]["radiations"]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def test_opening_cash_is_configured_when_set() -> None:
    assert opening_cash(cfg(tresorerie_ouverture=12_345.0), p4()) == 12_345.0


def test_opening_cash_is_derived_from_the_other_lines() -> None:
    derived = opening_cash(
        cfg(tresorerie_ouverture=None, depots_clients=50_000.0, immobilisations=20_000.0),
        p4(),
    )
    assert derived == TIER_D + 50_000.0 - 20_000.0


def test_movements_keeps_every_documented_key() -> None:
    mov = movements(build(GOLDEN))

    assert set(mov) >= {
        "decaisses",
        "remboursements",
        "interets",
        "frais",
        "recouvrements",
        "radiations",
        "sinistres",
        "non_classes",
        "evenements",
        "par_facilite",
        "warnings",
    }


def test_empty_state_serves_an_empty_balanced_bilan() -> None:
    body = compute_bilan(cfg(tresorerie_ouverture=None), {}, {})

    assert body["totaux"] == {"actif": 0.0, "passif": 0.0}
    assert body["ecart"] == 0.0
    assert body["balanced"] is True
    assert body["reliable"] is False
    assert body["mouvements"]["par_facilite"] == {}


@pytest.mark.parametrize("value", [0, None, "nonsense", float("nan")])
def test_num_degrades_bad_input_to_zero(value) -> None:
    from bank.orchestrator.bilan.compute import _num

    assert _num(value) == 0.0


# ---------------------------------------------------------------------------
# Task 5 — owner decisions surfaced as warnings, never guessed at
# ---------------------------------------------------------------------------


def test_garanties_consenties_left_on_a_fully_closed_book_is_flagged() -> None:
    # TODO(owner) B7: the guarantee book only ever grows; whether it should
    # shrink on repayment/write-off is undefined, so the state is reported.
    p4_with_book = p4()
    p4_with_book["pool"] = {"given_book": 12_000.0}

    body = compute_bilan(cfg(), build(GOLDEN), p4_with_book)

    assert body["hors_bilan"]["garanties_consenties"] == 12_000.0
    assert any("garanties_consenties" in w for w in body["warnings"])
    # A warning alone must not mark the sheet unreliable.
    assert body["reliable"] is True


def test_no_guarantee_warning_while_facilities_are_open() -> None:
    pairs = [loan("A", "ACTIVE", lent=12_000, repaid=4_000, interest=420)]
    p4_with_book = p4(el_pool=0.0, ifrs9={"F1": {"ecl": 100.0, "ead": 1_000.0}})
    p4_with_book["pool"] = {"given_book": 12_000.0}

    body = compute_bilan(
        cfg(tresorerie_ouverture=None), build(pairs), p4_with_book
    )

    assert body["warnings"] == []


def test_empty_guarantee_book_is_not_flagged() -> None:
    body = compute_bilan(cfg(), build(GOLDEN), p4())

    assert body["hors_bilan"]["garanties_consenties"] == 0.0
    assert body["warnings"] == []


def test_pillars_reads_the_ifrs9_slices() -> None:
    pil = pillars(p4(el_pool=10.0, ifrs9={"F1": {"ecl": 100.0, "ead": 1_000.0}}))

    assert pil["el_pool"] == 10.0
    assert pil["ecl_total"] == 100.0
    assert pil["rwa"] == 1_000.0
    assert pil["tier_d"] == TIER_D
    assert pil["facilities"] == 1
