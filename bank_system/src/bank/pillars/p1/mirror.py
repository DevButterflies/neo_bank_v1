"""P1 -> P4 mirror bridge: P2 risk packet, IFRS9 staging, and P3 lifecycle events.

All helpers await ``p4_runtime().run(...)`` so every call serialises a P4
snapshot, matching the production single-thread contract.
"""
from __future__ import annotations

from bank.pillars.p4.contracts.p2_inbound import Pillar2RiskPacket
from bank.pillars.p4.domain.events import Pillar3Event, Pillar3EventType
from bank.pillars.p4.domain.model_maturity import ModelStage


def p3_runtime():
    from bank.pillars.api import p3
    return p3.runtime


def p4_runtime():
    from bank.pillars.api import p4
    return p4.runtime


def _event(event_type: Pillar3EventType, facility_ref: str, **kw) -> Pillar3Event:
    return Pillar3Event(event_type=event_type, facility_ref=facility_ref, **kw)


async def mirror_risk_packet(
    facility_ref: str,
    *,
    brr: float,
    pd: float,
    lgd: float,
    ead: float,
    el: float,
    model_stage: str = "PRODUCTION",
    packet_ref: str | None = None,
    grid_version: str | None = None,
    product_type: str | None = None,
) -> dict:
    pkt = Pillar2RiskPacket(
        facility_ref=facility_ref,
        brr=brr,
        pd=pd,
        lgd=lgd,
        ead=ead,
        el=el,
        model_maturity_stage=ModelStage(model_stage),
        brr_pd_grid_version=grid_version or packet_ref,
        packet_ref=packet_ref,
        product_type=product_type,
    )
    rt = p4_runtime()
    await rt.run(lambda p4: p4.ports.p2.feed_risk_packet(pkt))
    confirmed = await rt.run(lambda p4: bool(p4.ports.p2.confirm_packet(facility_ref)))
    return {"facility_ref": facility_ref, "status": "registered", "confirmed": confirmed}


async def mirror_staging_signal(
    facility_ref: str, stage: int, packet_ref: str | None = None
) -> dict:
    await p4_runtime().run(
        lambda p4: p4.ports.p2.feed_staging_signal(facility_ref, stage, packet_ref)
    )
    return {"facility_ref": facility_ref, "stage": stage, "status": "provisioned"}


async def mirror_close(facility_ref: str) -> dict:
    """Release a facility's exposure from the P4 capital + provisioning book.

    Called when a loan is closed (fully repaid or recovered) OR when a packet is
    withheld by the prudential veto. Drops the risk packet and IFRS9 staging so
    RWA / portfolio EL no longer count exposure that is gone, then recomputes.
    """
    await p4_runtime().run(
        lambda p4: (
            p4.capital.release_risk_packet(facility_ref),
            p4.ifrs9.release(facility_ref),
            p4.recompute_and_evaluate_track1(),
        )
    )
    return {"facility_ref": facility_ref, "status": "released"}


async def mirror_disburse(facility_ref: str, amount: float) -> None:
    """Mirror a P3 disbursement into P4: run the Track-1 eval and record the
    guarantee GRANTED at portfolio level.

    Disbursement draws the pre-registered risk packet's exposure down the
    facility, so the portfolio recomputes (RWA / portfolio EL / freeze state)
    without re-feeding the packet (EAD was fixed at submit/approve). The
    disbursed principal also enters the given-guarantee book — the pool's
    guarantee coverage ratio is a Track-1 trigger, so the granted book must
    move on every disbursement or the G/G ratio stays frozen at zero.
    """
    await p4_runtime().run(
        lambda p4: (
            p4.custody.record_given_book(amount),
            p4.recompute_and_evaluate_track1(),
        )
    )


async def mirror_repayment(
    facility_ref: str, principal: float, interest: float
) -> Pillar3Event:
    ev = _event(
        Pillar3EventType.SCHEDULED_REPAYMENT,
        facility_ref,
        amount=round(principal + interest, 2),
        principal_component=principal,
        interest_component=interest,
    )
    await p4_runtime().run(lambda p4: p4.ports.p3.feed_event(ev))
    return ev


async def mirror_default(facility_ref: str, loss: float) -> Pillar3Event:
    # No collateral recovery is modelled at default time in the simulator: the
    # whole defaulted exposure becomes the guarantee leg. Setting
    # collateral_leg_amount = loss would make the realized net loss zero and
    # the settlement engine would absorb nothing.
    ev = _event(
        Pillar3EventType.DEFAULT_OR_WRITE_OFF,
        facility_ref,
        amount=loss,
        collateral_leg_amount=0.0,
    )
    await p4_runtime().run(lambda p4: p4.ports.p3.feed_event(ev))
    return ev


async def mirror_recovery(facility_ref: str, recovered: float) -> Pillar3Event:
    ev = _event(
        Pillar3EventType.RECOVERY_COLLATERAL_LEG,
        facility_ref,
        amount=recovered,
    )
    await p4_runtime().run(lambda p4: p4.ports.p3.feed_event(ev))
    return ev


async def mirror_origination_fee(facility_ref: str, fee: float) -> Pillar3Event:
    ev = _event(Pillar3EventType.ORIGINATION_FEE, facility_ref, amount=fee)
    await p4_runtime().run(lambda p4: p4.ports.p3.feed_event(ev))
    return ev


async def mirror_risk_premium(
    facility_ref: str, premium: float
) -> Pillar3Event:
    ev = _event(
        Pillar3EventType.RISK_PREMIUM_ACCRUAL, facility_ref, amount=premium
    )
    await p4_runtime().run(lambda p4: p4.ports.p3.feed_event(ev))
    return ev
