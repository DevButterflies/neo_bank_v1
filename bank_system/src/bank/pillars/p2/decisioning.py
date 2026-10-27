"""
Three-zone decisioning (Canon §2.7, ratified P-6; Spec §10).

"The decisioning zone is determined jointly by three conditions, not by
BRR alone: (i) risk band, (ii) data confidence, (iii) absence of policy
exceptions. Auto-approve requires all three favourable simultaneously;
failing any one pushes the case to a higher-touch zone regardless of BRR."
Thin-file cases can never reach auto-approve (Canon §2.8).
"""

from __future__ import annotations

from . import constants as c
from .enums import DecisioningZone, ModelMaturityStage, PacketStatus


def determine_zone(
    brr: int,
    dqs: float,
    is_thin_file: bool,
    has_policy_exception: bool,
    el_within_budgeted_loss: bool,
) -> DecisioningZone:
    high_risk = brr >= c.MANUAL_REVIEW_MIN_BRR
    low_data_confidence = dqs < c.DQS_HIGH_CONFIDENCE_THRESHOLD

    if high_risk or has_policy_exception or (is_thin_file and c.THIN_FILE_BLOCKS_AUTO_APPROVE and brr >= c.THIN_FILE_MIN_BRR):
        return DecisioningZone.MANUAL_REVIEW

    auto_conditions = (
        brr <= c.AUTO_APPROVE_MAX_BRR
        and not low_data_confidence
        and not is_thin_file
        and not has_policy_exception
        and el_within_budgeted_loss
    )
    if auto_conditions:
        return DecisioningZone.AUTO_APPROVE

    return DecisioningZone.AUGMENTED_DECISION


def packet_status_and_confirmation(
    zone: DecisioningZone,
    stage: ModelMaturityStage,
    production_auto_approve_enabled: bool,
) -> tuple[PacketStatus, bool]:
    """
    Maps zone -> P2->P3 packet status (V3.0 addition, Canon §2.7) and whether
    a human credit-officer confirmation is still required.

    SANDBOX: human gate mandatory at every zone, regardless of outcome.
    PRODUCTION: straight-through auto-approve only if the (separate,
    per-model, P4-approved) governance switch has been explicitly turned on
    (ratified condition P-5) — never automatic on the passage of time.
    DESIGN: no live credit decisions are permitted at all (Table §3.3);
    every packet still requires confirmation as a structural safeguard.
    """
    if zone == DecisioningZone.AUTO_APPROVE:
        skip_confirmation = stage == ModelMaturityStage.PRODUCTION and production_auto_approve_enabled
        return PacketStatus.APPROVED, not skip_confirmation
    if zone == DecisioningZone.AUGMENTED_DECISION:
        return PacketStatus.PROVISIONAL, True
    return PacketStatus.CONDITIONAL, True
