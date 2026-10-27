"""
Monitoring outputs: Early-Warning Signal (EWS) and the CASS data feed.

These are two *distinct* outputs (Canon §2.15, ratified P-7):
  - EWS: facility-level, routes to a human credit officer, triggers NO
    automatic Pillar 3 action, and is NOT an ABSF trigger.
  - CASS feed: portfolio-level, feeds Pillar 4's ABSF engine.
"""

from __future__ import annotations

from . import constants as c
from .enums import IFRS9Stage
from .schemas import CASSFeedPacket, EWSResult


def evaluate_ews(application_id: str, brr_at_origination: int, brr_current: int) -> EWSResult:
    deterioration = brr_current - brr_at_origination
    triggered = deterioration >= c.EWS_BRR_DETERIORATION_TRIGGER
    return EWSResult(
        application_id=application_id,
        triggered=triggered,
        brr_at_origination=brr_at_origination,
        brr_current=brr_current,
        deterioration_notches=deterioration,
        routed_to_officer=triggered,
        triggers_p3_action=False,  # Canon-mandated invariant — never True
    )


def _ifrs9_stage(pd_pit_adjusted: float, days_past_due: int, significant_increase: bool) -> IFRS9Stage:
    """
    Simplified staging: Stage 3 on default/90+ DPD; Stage 2 on a significant
    increase in credit risk since origination (Canon §2.11.1); else Stage 1.
    """
    if days_past_due >= 90:
        return IFRS9Stage.STAGE_3
    if significant_increase:
        return IFRS9Stage.STAGE_2
    return IFRS9Stage.STAGE_1


def build_cass_packet(
    application_id: str,
    brr: int,
    pd_pit_adjusted: float,
    expected_loss: float,
    days_past_due: int = 0,
    significant_credit_risk_increase: bool = False,
    cash_flow_deterioration_indicator: float = 0.0,
) -> CASSFeedPacket:
    """
    Canon §2.13: BRR, PD, IFRS 9 staging (PIT-adjusted, §2.11.1), cash-flow
    deterioration indicator, and EL, fed to P4's CASS engine for ABSF. The
    joint P2/P4 interface spec is PENDING (Spec §16) — this packet uses the
    standard P2 output packet format in the interim, as instructed by Canon.
    """
    stage = _ifrs9_stage(pd_pit_adjusted, days_past_due, significant_credit_risk_increase)
    return CASSFeedPacket(
        application_id=application_id,
        brr=brr,
        pd_pit_adjusted=pd_pit_adjusted,
        ifrs9_stage=stage,
        cash_flow_deterioration_indicator=cash_flow_deterioration_indicator,
        expected_loss=expected_loss,
    )
