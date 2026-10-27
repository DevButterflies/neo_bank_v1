"""Pure Actif/Passif computation — no I/O.

Two sources of truth feed the bilan: Pillar 3 ``posted_events`` (the loan
movements) and Pillar 4's ``account``/``ifrs9``/``capital``/``pool`` slices
(the provisions and the prudential memo). Everything else — the non-loan
assets and third-party liabilities — comes from :class:`BilanConfig`.

The only Pillar import is :mod:`bank.pillars.p3.domain.memos`, a leaf
constants module: the memo strings are the contract that says which posting is
a drawdown, a repayment, a write-off or a recovery, so they are defined once
rather than duplicated as magic strings.

Identity
--------
Opening cash is **derived** unless ``cfg.tresorerie_ouverture`` is set::

    T0 = tier_d + apport + resultat_anterieur + dettes + depots + autres_dettes
         - immobilisations - autres_creances

With the derived plug the two sides are provably identical for any Pillar 3
activity, any Pillar 4 state and any config value::

    Actif  = I + AC + (dec-rem-rad) + T0 + rem + int + frais + rec - dec
           = I + AC + T0 + int + frais + rec - rad
           = (tierD + A + R0 + D + P + U) + int + frais + rec - rad
    Passif = tierD + A + (R0 + int + frais + rec - rad - eclt) + eclt + D + P + U
           = (tierD + A + R0 + D + P + U) + int + frais + rec - rad
    =>  Actif == Passif  identically.

That is exactly why ``balanced: true`` proves nothing on its own: see the
``OPENING_CASH_INDEPENDENT`` check, and ``reliable``, which is false whenever
opening cash is derived.

The EL Pool and the IFRS 9 ECL are separate things: ``ecl_total`` is the
provision booked on 4280 and charged to the result, while ``el_pool`` is a
prudential buffer reported as a **memo** item only (``hors_bilan``). Adding
either to cash would create money.

ULA buffer and the liquidity reserve are memo items for the same reason.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bank.orchestrator.bilan.config import BilanConfig
from bank.pillars.p3.domain.memos import (
    MEMO_DEFAULT_MARKER,
    MEMO_DISBURSEMENT,
    MEMO_RECOVERY,
    MEMO_WRITE_OFF,
)

_ROUND = 2

CHECK_BALANCE = "BALANCE"
CHECK_OPENING_CASH = "OPENING_CASH_INDEPENDENT"
CHECK_NO_OVERPAYMENT = "NO_OVERPAYMENT"
CHECK_CLOSED_ZERO_BALANCE = "CLOSED_FACILITIES_ZERO_BALANCE"
CHECK_NO_UNCLASSIFIED = "NO_UNCLASSIFIED_LOSS_EVENTS"
CHECK_NO_NEGATIVE_RECEIVABLE = "NO_NEGATIVE_RECEIVABLE"
CHECK_RECOVERY_WITHIN_WRITE_OFF = "RECOVERY_WITHIN_WRITE_OFF"


def _num(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return out if out == out and out not in (float("inf"), float("-inf")) else 0.0


def _event_type(raw: Any) -> str:
    """``PostingEventType`` is JSON-encoded as ``{"__enum__": ..., "value": ...}``."""
    if isinstance(raw, dict):
        return str(raw.get("value") or "")
    return str(raw or "")


def _facility_state(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    state = node.get("state")
    if isinstance(state, dict):
        value = state.get("value")
        return str(value) if value else None
    if isinstance(state, str):
        return state
    return None


def movements(p3: dict) -> dict[str, Any]:
    """Aggregate the Pillar 3 posting set into the bilan's flow terms.

    Loss events are classified by memo, never by event type alone: a single
    ``LOSS_RECOVERY`` posting carries the default marker (amount 0), the
    write-off (principal that will never come back) and the recovery receipt
    (cash that did come back) — three economically opposite things.

    Anything non-zero that matches none of the known memos is counted in
    ``non_classes`` rather than silently swallowed.
    """
    dec = rem = inc = fee = rec = rad = 0.0
    non_classes = 0
    count = 0

    per_facilite: dict[str, dict[str, float]] = {}
    defaulted: set[str] = set()
    written_off: set[str] = set()

    def slot(facility_id: str) -> dict[str, float]:
        return per_facilite.setdefault(
            facility_id, {"dec": 0.0, "rem": 0.0, "rad": 0.0, "rec": 0.0}
        )

    for event in p3.get("posted_events") or []:
        if not isinstance(event, dict):
            continue
        kind = _event_type(event.get("event_type"))
        amount = _num(event.get("amount"))
        memo = str(event.get("memo") or "")
        facility_id = str(event.get("facility_id") or "")
        count += 1
        at = slot(facility_id)

        if kind == "PRINCIPAL_MOVEMENT":
            if memo == MEMO_DISBURSEMENT:
                dec += amount
                at["dec"] = round(at["dec"] + amount, _ROUND)
            else:
                rem += amount
                at["rem"] = round(at["rem"] + amount, _ROUND)
        elif kind == "LOAN_INCOME":
            inc += amount
        elif kind == "ORIGINATION_FEE":
            fee += amount
        elif kind == "LOSS_RECOVERY":
            if memo == MEMO_RECOVERY:
                rec += amount
                at["rec"] = round(at["rec"] + amount, _ROUND)
            elif memo == MEMO_WRITE_OFF:
                rad += amount
                at["rad"] = round(at["rad"] + amount, _ROUND)
                written_off.add(facility_id)
            elif memo == MEMO_DEFAULT_MARKER:
                defaulted.add(facility_id)
            elif amount != 0.0:
                non_classes += 1

    warnings: list[str] = []

    # Legacy inference: the pre-fix database booked defaults with the
    # zero-amount marker only, so the written-off principal has to be
    # reconstructed from the facility's own drawdowns and repayments. It is
    # flagged rather than quietly folded in, because it is a guess.
    for facility_id in sorted(defaulted - written_off):
        at = per_facilite.get(facility_id)
        if not at:
            continue
        inferred = round(max(0.0, at["dec"] - at["rem"]), _ROUND)
        if inferred <= 0.0:
            continue
        rad = round(rad + inferred, _ROUND)
        at["rad"] = round(at["rad"] + inferred, _ROUND)
        warnings.append(f"write-off inferred for {facility_id}")

    par_facilite: dict[str, dict[str, Any]] = {}
    facilities = p3.get("facilities") or {}
    if isinstance(facilities, dict):
        for facility_id in sorted(set(per_facilite) | set(facilities)):
            at = per_facilite.get(facility_id, {"dec": 0.0, "rem": 0.0, "rad": 0.0, "rec": 0.0})
            par_facilite[facility_id] = {
                "dec": round(at["dec"], _ROUND),
                "rem": round(at["rem"], _ROUND),
                "rad": round(at["rad"], _ROUND),
                "rec": round(at["rec"], _ROUND),
                "etat": _facility_state(facilities.get(facility_id)),
            }

    return {
        "decaisses": round(dec, _ROUND),
        "remboursements": round(rem, _ROUND),
        "interets": round(inc, _ROUND),
        "frais": round(fee, _ROUND),
        "recouvrements": round(rec, _ROUND),
        "radiations": round(rad, _ROUND),
        "sinistres": round(rad, _ROUND),
        "non_classes": non_classes,
        "evenements": count,
        "par_facilite": par_facilite,
        "warnings": warnings,
    }


def pillars(p4: dict) -> dict[str, float]:
    """Read the Pillar 4 slices the bilan needs, raw from the snapshot."""
    account = p4.get("account") or {}

    def balance(sub_account: str) -> float:
        node = account.get(sub_account)
        return _num(node.get("balance")) if isinstance(node, dict) else 0.0

    ifrs9 = p4.get("ifrs9") or {}
    ecl_total = rwa = 0.0
    facilities = 0
    for staging in ifrs9.values():
        if not isinstance(staging, dict):
            continue
        facilities += 1
        ecl_total += _num(staging.get("ecl"))
        rwa += _num(staging.get("ead"))

    pool = p4.get("pool") or {}
    capital = p4.get("capital") or {}

    return {
        "el_pool": round(balance("el_pool"), _ROUND),
        "ula_buffer": round(balance("ula_buffer"), _ROUND),
        "liquidity_reserve": round(balance("liquidity_reserve"), _ROUND),
        "rp_pool": round(balance("rp_pool"), _ROUND),
        "tier_d": round(_num(capital.get("tier_d_amount")), _ROUND),
        "ecl_total": round(ecl_total, _ROUND),
        "rwa": round(rwa, _ROUND),
        "garanties_consenties": round(_num(pool.get("given_book")), _ROUND),
        "garanties_recues": round(_num(pool.get("received_book")), _ROUND),
        "niveau_requis": round(_num(pool.get("required_level")), _ROUND),
        "facilities": facilities,
    }


def opening_cash(cfg: BilanConfig, p4: dict) -> float:
    """Opening cash, and the single implementation of the derived plug.

    Configured when ``cfg.tresorerie_ouverture`` is set; otherwise derived
    from the other config lines, which is a plug by construction (B1).
    """
    if cfg.tresorerie_ouverture is not None:
        return round(cfg.tresorerie_ouverture, _ROUND)
    return round(
        pillars(p4)["tier_d"]
        + cfg.apport_reserve
        + cfg.resultat_anterieur
        + cfg.dettes_financieres
        + cfg.depots_clients
        + cfg.autres_dettes
        - cfg.immobilisations
        - cfg.autres_creances,
        _ROUND,
    )


def _check(check_id: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"id": check_id, "ok": bool(ok), "detail": detail}


def compute_bilan(cfg: BilanConfig, p3: dict, p4: dict) -> dict[str, Any]:
    """Return the full ``GET /bilan`` payload as a plain dict."""
    mov = movements(p3)
    pil = pillars(p4)

    dec = mov["decaisses"]
    rem = mov["remboursements"]
    interest = mov["interets"]
    fee = mov["frais"]
    rec = mov["recouvrements"]
    rad = mov["radiations"]

    # TODO(owner): is a capital change after opening a cash contribution?
    # Option, not implemented until confirmed: add `tier_d_ouverture` to the
    # config and book `tier_d - tier_d_ouverture` as a cash inflow. Until then
    # the live Tier D is read straight from P4, so a change after opening makes
    # the BALANCE check fail on purpose when opening cash is configured —
    # that failure is the signal, not a bug (docs/CHANGELOG_bilan.md, B8).
    tier_d = pil["tier_d"]
    dettes_fin = cfg.dettes_financieres
    tresorerie_ouverture = opening_cash(cfg, p4)

    credits_clients = round(dec - rem - rad, _ROUND)
    tresorerie = round(
        tresorerie_ouverture + rem + interest + fee + rec - dec,
        _ROUND,
    )
    resultat_cumule = round(
        cfg.resultat_anterieur + interest + fee + rec - rad - pil["ecl_total"],
        _ROUND,
    )

    actif = [
        {"compte": "2180", "libelle": "Immobilisations", "montant": round(cfg.immobilisations, _ROUND)},
        {"compte": "4110", "libelle": "Cr\u00e9dits clients (encours brut)", "montant": credits_clients},
        {"compte": "4190", "libelle": "Autres cr\u00e9ances", "montant": round(cfg.autres_creances, _ROUND)},
        {"compte": "5120", "libelle": "Tr\u00e9sorerie", "montant": tresorerie},
    ]
    passif = [
        {"compte": "1010", "libelle": "Capital social (Tier D)", "montant": tier_d},
        {"compte": "1180", "libelle": "R\u00e9serve d'apport", "montant": round(cfg.apport_reserve, _ROUND)},
        {"compte": "1190", "libelle": "R\u00e9sultat cumul\u00e9", "montant": resultat_cumule},
        # TODO(owner): confirm with an accountant that 4280 is the IFRS 9 ECL
        # (`ecl_total`, charged to the result) and that the EL Pool is a purely
        # prudential memo — i.e. that the two must never be added to cash
        # (docs/CHANGELOG_bilan.md, B4).
        {"compte": "4280", "libelle": "Provisions pour risques (ECL IFRS 9)", "montant": pil["ecl_total"]},
        {"compte": "2670", "libelle": "Dettes financi\u00e8res", "montant": round(dettes_fin, _ROUND)},
        {"compte": "4210", "libelle": "D\u00e9p\u00f4ts des clients", "montant": round(cfg.depots_clients, _ROUND)},
        {"compte": "4260", "libelle": "Autres dettes", "montant": round(cfg.autres_dettes, _ROUND)},
    ]

    total_actif = round(sum(line["montant"] for line in actif), _ROUND)
    total_passif = round(sum(line["montant"] for line in passif), _ROUND)
    ecart = round(total_actif - total_passif, _ROUND)

    par_facilite = mov["par_facilite"]
    warnings = list(mov["warnings"])

    overpaid = [
        f"{fid} rem {row['rem']:.2f} > dec {row['dec']:.2f}"
        for fid, row in par_facilite.items()
        if row["rem"] > row["dec"] + 0.005
    ]
    left_over = [
        f"{fid} net {row['dec'] - row['rem'] - row['rad']:.2f}"
        for fid, row in par_facilite.items()
        if row["etat"] == "CLOSED" and abs(row["dec"] - row["rem"] - row["rad"]) >= 0.01
    ]
    # Cash in from a workout can never exceed what was written off on that
    # same facility: recovering more than the loss is a duplicated recovery
    # posting (or a write-off that was never booked), and it silently
    # inflates 512 for a loan the ledger says is already settled.
    over_recovered = [
        f"{fid} rec {row['rec']:.2f} > rad {row['rad']:.2f}"
        for fid, row in par_facilite.items()
        if row["rec"] > row["rad"] + 0.005
    ]

    checks = [
        _check(
            CHECK_BALANCE,
            abs(total_actif - total_passif) < 0.005,
            f"actif {total_actif:.2f} vs passif {total_passif:.2f} (ecart {ecart:.2f})",
        ),
        _check(
            CHECK_OPENING_CASH,
            cfg.tresorerie_ouverture is not None,
            (
                f"opening cash configured at {tresorerie_ouverture:.2f}"
                if cfg.tresorerie_ouverture is not None
                else "opening cash derived: BALANCE is tautological"
            ),
        ),
        _check(
            CHECK_NO_OVERPAYMENT,
            not overpaid,
            "no facility repaid more than it drew" if not overpaid else "; ".join(overpaid),
        ),
        _check(
            CHECK_CLOSED_ZERO_BALANCE,
            not left_over,
            (
                "every closed facility is fully written down"
                if not left_over
                else "; ".join(left_over)
            ),
        ),
        _check(
            CHECK_NO_UNCLASSIFIED,
            mov["non_classes"] == 0,
            (
                "every non-zero loss event is classified"
                if mov["non_classes"] == 0
                else f"{mov['non_classes']} loss event(s) with an unknown memo"
            ),
        ),
        _check(
            CHECK_NO_NEGATIVE_RECEIVABLE,
            credits_clients >= -0.005,
            f"4110 = {credits_clients:.2f}",
        ),
        _check(
            CHECK_RECOVERY_WITHIN_WRITE_OFF,
            not over_recovered,
            (
                "no facility recovered more than it wrote off"
                if not over_recovered
                else "; ".join(over_recovered)
            ),
        ),
    ]

    # TODO(owner): guarantees granted only ever grow. Whether the book should
    # shrink on principal repayment and on write-off is not defined in
    # project.md, so it is surfaced instead of guessed at
    # (docs/CHANGELOG_bilan.md, B7).
    if pil["garanties_consenties"] > 0 and par_facilite:
        if all(row["etat"] == "CLOSED" for row in par_facilite.values()):
            warnings.append(
                f"garanties_consenties {pil['garanties_consenties']:.2f} still on the "
                "book although every facility is CLOSED"
            )

    reliable = all(item["ok"] for item in checks)

    rwa = pil["rwa"]
    return {
        "actif": actif,
        "passif": passif,
        "totaux": {"actif": total_actif, "passif": total_passif},
        "ecart": ecart,
        "balanced": abs(ecart) < 0.005,
        "checks": checks,
        "reliable": reliable,
        "warnings": warnings,
        "mouvements": {
            "decaisses": dec,
            "remboursements": rem,
            "interets": interest,
            "frais": fee,
            "recouvrements": rec,
            "radiations": rad,
            "sinistres": rad,
            "non_classes": mov["non_classes"],
            "par_facilite": par_facilite,
            "ecl_total": pil["ecl_total"],
            "el_pool": pil["el_pool"],
            "ecl_consomme": 0.0,
            "tresorerie_ouverture": tresorerie_ouverture,
        },
        "hors_bilan": {
            "ula_buffer": pil["ula_buffer"],
            "liquidity_reserve": pil["liquidity_reserve"],
            "rp_pool": pil["rp_pool"],
            "el_pool": pil["el_pool"],
            "rwa": rwa,
            "tier_d_over_rwa": round(tier_d / rwa, 4) if rwa else None,
            "garanties_consenties": pil["garanties_consenties"],
            "garanties_recues": pil["garanties_recues"],
            "niveau_requis_garanties": pil["niveau_requis"],
        },
        "sources": {
            "p3_events": mov["evenements"],
            "p4_facilities": pil["facilities"],
        },
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
