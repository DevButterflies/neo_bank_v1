"""Static side of the bilan: the opening-balance-sheet configuration.

Everything the bilan cannot derive from Pillar 3/4 lives here — the non-loan
assets and third-party liabilities of the balance sheet. All fields default to
``0.0``, which is a valid configuration: the opening cash is *derived* (see
:func:`bank.orchestrator.bilan.compute.compute_bilan`), so a zero config always
yields a balanced bilan.

Persisted as a single JSON blob under :data:`CONFIG_KEY` in the orchestrator
KvStore — a brand-new key, invisible to ``/ready`` (which only compares
``p3_state_v1`` and ``p4_state_v1``) and to every existing engine.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

CONFIG_KEY = "bilan_config_v1"


class BilanConfig(BaseModel):
    """Opening balance sheet, other than Tier D equity.

    ``capital_social`` is intentionally **not** here: it is read live from
    Pillar 4's ``capital.tier_d_amount`` so a governance capital decision moves
    both sides of the bilan in real time.
    """

    immobilisations: float = Field(0.0, allow_inf_nan=False)
    autres_creances: float = Field(0.0, allow_inf_nan=False)
    apport_reserve: float = Field(0.0, allow_inf_nan=False)
    resultat_anterieur: float = Field(0.0, allow_inf_nan=False)
    sid: float = Field(0.0, allow_inf_nan=False)
    tier_c: float = Field(0.0, allow_inf_nan=False)
    autres_emprunts: float = Field(0.0, allow_inf_nan=False)
    depots_clients: float = Field(0.0, allow_inf_nan=False)
    autres_dettes: float = Field(0.0, allow_inf_nan=False)
    tresorerie_ouverture: float | None = Field(
        None,
        allow_inf_nan=False,
        description=(
            "Opening cash. ``None`` (the default) derives it from the other "
            "lines, which forces Actif == Passif by construction and makes "
            "the BALANCE check tautological. Set it to a figure that was "
            "observed independently and the check becomes a real one."
        ),
    )

    @property
    def dettes_financieres(self) -> float:
        return self.sid + self.tier_c + self.autres_emprunts
