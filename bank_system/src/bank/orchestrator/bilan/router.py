"""``GET /bilan`` and ``GET|PUT /bilan/config`` — the bilan's HTTP surface.

Mounted on the **orchestrator root app** (not inside a Pillar sub-app) by the
single registration line in :mod:`bank.orchestrator.main`, so the paths are
``/bilan`` and ``/bilan/config`` alongside ``/health`` and ``/ready``.

``GET /bilan`` re-reads the shared KvStore on every call — no cache, no
background task, no engine instance — so the answer always reflects the last
committed Pillar 3/4 write.
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from bank.orchestrator.bilan import store
from bank.orchestrator.bilan.compute import compute_bilan, opening_cash
from bank.orchestrator.bilan.config import CONFIG_KEY, BilanConfig

router = APIRouter(tags=["bilan"])

logger = logging.getLogger(__name__)

AUDIT_KEY = "bilan_config_audit_v1"


class BilanLine(BaseModel):
    compte: str
    libelle: str
    montant: float


class BilanTotaux(BaseModel):
    actif: float
    passif: float


class BilanCheck(BaseModel):
    """One named invariant of the balance sheet, with why it passed or failed."""

    id: str
    ok: bool
    detail: str


class BilanFacilite(BaseModel):
    """Per-facility principal ledger behind 4110."""

    dec: float
    rem: float
    rad: float
    rec: float
    etat: str | None = None


class BilanMouvements(BaseModel):
    """Flow terms read from Pillar 3/4 — the inputs behind every line."""

    decaisses: float
    remboursements: float
    interets: float
    frais: float
    sinistres: float
    ecl_total: float
    el_pool: float
    ecl_consomme: float
    tresorerie_ouverture: float
    recouvrements: float = 0.0
    radiations: float = 0.0
    non_classes: int = 0
    par_facilite: dict[str, BilanFacilite] = Field(default_factory=dict)


class BilanHorsBilan(BaseModel):
    """Memo items reported alongside the balance, never added to either face."""

    ula_buffer: float
    liquidity_reserve: float
    rp_pool: float
    rwa: float
    tier_d_over_rwa: float | None
    garanties_consenties: float
    garanties_recues: float
    niveau_requis_garanties: float
    el_pool: float = 0.0


class BilanSources(BaseModel):
    p3_events: int
    p4_facilities: int


class BilanResponse(BaseModel):
    actif: list[BilanLine]
    passif: list[BilanLine]
    totaux: BilanTotaux
    ecart: float
    balanced: bool
    mouvements: BilanMouvements
    hors_bilan: BilanHorsBilan
    sources: BilanSources
    as_of: datetime
    checks: list[BilanCheck] = Field(default_factory=list)
    reliable: bool = True
    warnings: list[str] = Field(default_factory=list)


class BilanConfigView(BilanConfig):
    """The stored config plus the cash opening it *resolves* to.

    Overriding ``tresorerie_ouverture`` here deliberately changes its meaning:
    on :class:`BilanConfig` it is the *configured* opening cash (``None`` =
    derive it), on this response it is the value the bilan actually used.

    The resolved value alone cannot say which of the two it started as, so
    ``tresorerie_ouverture_configured`` reports the original ``None``-ness —
    a client that needs to know "did a human set this?" reads that flag
    (``bug_bilan_fix_round_2.md``, R4).
    """

    tresorerie_ouverture: float
    tresorerie_ouverture_configured: bool


class BilanConfigUpdate(BaseModel):
    """Partial update — any subset of :class:`BilanConfig` fields."""

    immobilisations: float | None = Field(None, allow_inf_nan=False)
    autres_creances: float | None = Field(None, allow_inf_nan=False)
    apport_reserve: float | None = Field(None, allow_inf_nan=False)
    resultat_anterieur: float | None = Field(None, allow_inf_nan=False)
    sid: float | None = Field(None, allow_inf_nan=False)
    tier_c: float | None = Field(None, allow_inf_nan=False)
    autres_emprunts: float | None = Field(None, allow_inf_nan=False)
    depots_clients: float | None = Field(None, allow_inf_nan=False)
    autres_dettes: float | None = Field(None, allow_inf_nan=False)
    tresorerie_ouverture: float | None = Field(None, allow_inf_nan=False)


def _load_config() -> BilanConfig:
    payload = store.read_config()
    known = {field for field in BilanConfig.model_fields}
    return BilanConfig.model_validate({k: v for k, v in payload.items() if k in known})


def _config_view(cfg: BilanConfig) -> BilanConfigView:
    payload = cfg.model_dump()
    payload["tresorerie_ouverture_configured"] = cfg.tresorerie_ouverture is not None
    payload["tresorerie_ouverture"] = opening_cash(cfg, store.read_p4())
    return BilanConfigView.model_validate(payload)


@router.get("/bilan", response_model=BilanResponse, summary="Bilan Actif/Passif")
async def get_bilan() -> BilanResponse:
    """Compute the balance sheet live from the shared KvStore."""
    p3, p4 = store.read_p3(), store.read_p4()
    return BilanResponse.model_validate(compute_bilan(_load_config(), p3, p4))


@router.get("/bilan/config", response_model=BilanConfigView, summary="Bilan config")
async def get_bilan_config() -> BilanConfigView:
    return _config_view(_load_config())


def _require_admin_token(x_admin_token: str | None) -> None:
    """Gate the only bilan path that writes.

    Refusing when the token is not configured at all is deliberate: an
    unconfigured endpoint must fail closed, not stay open (B9).
    """
    from bank.orchestrator.config import get_orchestrator_settings

    expected = get_orchestrator_settings().bilan_admin_token
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="PUT /bilan/config is disabled: set BANK_ORCH_BILAN_ADMIN_TOKEN",
        )
    if x_admin_token is None or not hmac.compare_digest(
        x_admin_token.encode("utf-8"), str(expected).encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="invalid X-Admin-Token")


async def _append_audit(old: BilanConfig, new: BilanConfig) -> None:
    """Append one row per **accepted change** — a no-op update changes nothing
    and is therefore not a change worth recording."""
    old_dump = old.model_dump()
    new_dump = new.model_dump()
    if old_dump == new_dump:
        return

    from bank.orchestrator.config import get_orchestrator_settings
    from bank.pillars.api.storage import KvStore

    store_ = KvStore(get_orchestrator_settings().db_path)
    trail = await store_.get_json(AUDIT_KEY)
    entries = trail if isinstance(trail, list) else []
    entries.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old": old_dump,
            "new": new_dump,
        }
    )
    await store_.set_json(AUDIT_KEY, entries)


@router.put("/bilan/config", response_model=BilanConfigView, summary="Update bilan config")
async def put_bilan_config(
    update: BilanConfigUpdate,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> BilanConfigView:
    """Merge a partial update into ``bilan_config_v1`` and return the result.

    This is the only bilan path that writes — to a brand-new KV key, leaving
    ``p3_state_v1``/``p4_state_v1`` (and therefore ``/ready``) untouched.
    Requires ``X-Admin-Token`` and leaves an append-only audit row behind.

    The config write and the audit append are two separate KV writes and are
    **not atomic**: the config is committed first, then the audit row. If the
    audit append fails the error is logged and the response is still 200,
    because the caller's change *did* take effect — reporting failure would
    invite a retry that then records a spurious second change. A failure of
    the config write itself still propagates (no transaction layer is built
    here; see ``bug_bilan_fix_round_2.md``, R4).
    """
    _require_admin_token(x_admin_token)

    from bank.orchestrator.config import get_orchestrator_settings
    from bank.pillars.api.storage import KvStore

    previous = _load_config()
    merged = previous.model_dump()
    merged.update(update.model_dump(exclude_unset=True))
    cfg = BilanConfig.model_validate(merged)

    await KvStore(get_orchestrator_settings().db_path).set_json(CONFIG_KEY, cfg.model_dump())
    try:
        await _append_audit(previous, cfg)
    except Exception:
        logger.exception(
            "bilan config was written but the audit row could not be appended"
        )
    return _config_view(cfg)
