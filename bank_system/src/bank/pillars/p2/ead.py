"""
Product-specific Exposure at Default conventions (Spec §6.3, Canon §2.5).

PD is company-level; LGD and EAD are product-specific with segment
adjustments (Canon §2.5). Term/growth loans are forward-compatible only —
their LGD/EAD logic is deliberately not built in this sandbox phase.
"""

from __future__ import annotations

from . import constants as c
from .enums import Product
from .schemas import FacilityRequest


class ProductNotInSandboxScope(NotImplementedError):
    """Raised for products the Spec explicitly defers (§1.3, §6.3)."""


def compute_ead(facility: FacilityRequest) -> float:
    if facility.product in c.FORWARD_COMPATIBLE_ONLY_PRODUCTS:
        raise ProductNotInSandboxScope(
            f"{facility.product.value}: EAD/LGD logic kept forward-compatible but not built "
            "this phase (Spec §1.3, §6.3)."
        )

    if facility.product == Product.INVOICE_DISCOUNTING:
        # "EAD ~= face value of the discounted invoice(s); short tenor; little undrawn exposure."
        return facility.drawn_amount if facility.drawn_amount is not None else facility.requested_amount

    if facility.product == Product.SUPPLY_CHAIN_FINANCE:
        # "EAD ~= approved invoice pool outstanding; recourse terms adjust effective exposure."
        base = facility.drawn_amount if facility.drawn_amount is not None else facility.requested_amount
        return base if facility.recourse else base * 1.0  # recourse-adjustment factor: PENDING calibration

    if facility.product == Product.WORKING_CAPITAL_LINE:
        # "EAD = drawn + CCF x undrawn. Supervisory CCF until internal data sufficient."
        drawn = facility.drawn_amount or 0.0
        undrawn = facility.undrawn_amount if facility.undrawn_amount is not None else max(
            0.0, facility.requested_amount - drawn
        )
        return drawn + c.SUPERVISORY_CCF_WORKING_CAPITAL * undrawn

    raise ValueError(f"Unrecognised product: {facility.product}")
