"""IFRS 9 / Staging Consumer (claude.md §8.4, §4.4).

Why it exists: to keep provisioning centralized at the macro level, deliberately
bypassing Pillar 3's per-loan world.

Responsibility: consume Pillar 2's DIRECT staging signal (Stage 1/2/3 per
facility on significant increase in credit risk), update per-facility stage
classification, and recompute the ECL provision. The staging signal feeds
DIRECTLY P2 -> EL Pool, BYPASSING Pillar 3 entirely (claude.md §4.4, §9). A
staging migration triggers NO Pillar 3 covenant or freeze - it is purely a
Pillar 4 provisioning event.

No double-counting of conservatism: PD/LGD arrive already inclusive of Pillar
2's Margin of Conservatism; Pillar 4 must NOT re-apply a second buffer (claude.md
§4.4). We honor this by never adding a conservatism factor of our own.

Wire format of the staging signal is PENDING (PENDING_STAGING_SIGNAL_FORMAT);
the logical field shape is `contracts.p2_inbound.StagingSignal`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.buffer_account import BufferAccount, SubAccountId
from ..domain.events import IntraP4Event, IntraP4EventType
from ..contracts.p2_inbound import StagingSignal, Pillar2RiskPacket
from ..domain.pending import PENDING_STAGING_SIGNAL_FORMAT, require_resolved

# Lifetime-ECL multiple for Stage 2 (significant increase in credit risk):
# IFRS 9 moves a Stage-2 facility from 12-month ECL to lifetime ECL. The
# lifetime PD is P2's to refine; here we escalate the Stage-1 provision by a
# calibration multiple rather than leaving Stage 2 equal to Stage 1. Stage 3
# (default) is provisioned at LGD x EAD (PD ~ 1), i.e. the full exposure less
# expected collateral recovery — never equal to the origination-time EL.
STAGE2_LIFETIME_ECL_MULTIPLE: float = 1.5


@dataclass
class FacilityStaging:
    facility_ref: str
    stage: int = 1
    ecl: float = 0.0
    ead: float = 0.0
    el: float = 0.0
    pd: float = 0.0
    lgd: float = 0.0


class Ifrs9StagingConsumer:
    """Consumes the direct P2 staging signal and recomputes ECL provision."""

    def __init__(self, buffer_account: BufferAccount, event_sink=None):
        self._buffer = buffer_account
        self._event_sink = event_sink or (lambda ev: None)
        self._facilities: dict[str, FacilityStaging] = {}
        # Aggregate ECL provision figure the EL Pool was last synced to. The EL
        # Pool is a real ledger (RP-Pool-funded, drawn by real defaults via the
        # event router); provisioning here posts only the DELTA so a default
        # debit is never silently erased by a wholesale overwrite.
        self._synced_provision: float = 0.0

    def _emit(self, ev: IntraP4Event):
        self._event_sink(ev)

    def register_risk(self, packet: Pillar2RiskPacket):
        """Register the P2 risk packet used to derive ECL for a facility."""
        f = self._facilities.setdefault(
            packet.facility_ref,
            FacilityStaging(facility_ref=packet.facility_ref, ead=packet.ead),
        )
        f.el = packet.el
        f.ead = packet.ead
        f.pd = packet.pd
        f.lgd = packet.lgd
        # Keep the provision on the facility's current stage (re-registration
        # after an EAD reduction must not snap a Stage 2/3 loan back to
        # the flat 12-month ECL).
        f.ecl = self._stage_ecl(f)

    def release(self, facility_ref: str):
        """Drop a facility's staging state once its exposure is gone (close / withhold).

        Removes the facility from the provision book and re-syncs the EL Pool
        to the remaining aggregate ECL provision (a release back to the pool).
        """
        if facility_ref not in self._facilities:
            return
        del self._facilities[facility_ref]
        self._sync_el_pool(None)

    def _stage_ecl(self, f: FacilityStaging) -> float:
        """IFRS 9 ECL is stage-dependent — provisioning scales with deterioration.

        Stage 1: 12-month ECL (the origination EL from P2, incl. MoC).
        Stage 2: lifetime ECL — escalated by a calibration multiple.
        Stage 3: defaulted → PD ≈ 1, so ECL = LGD × EAD (the full exposure
                 less expected recovery). Never equal to the origination EL.
        """
        if f.stage == 3:
            return round(f.lgd * f.ead, 2)
        if f.stage == 2:
            return round(f.el * STAGE2_LIFETIME_ECL_MULTIPLE, 2)
        return f.el

    def sync_provision(self) -> None:
        """Re-sync the EL Pool to the aggregate ECL provisions.

        Used after a risk re-registration (e.g. EAD decline on repayment)
        so the provision cover tracks the live per-facility ECL values.
        """
        self._sync_el_pool(None)

    def on_staging_signal(self, signal: StagingSignal):
        """Handle a direct P2 staging signal (bypasses Pillar 3)."""
        # Staging is a Pillar 4 provisioning event only: no Pillar 3 covenant
        # or freeze is triggered by a staging migration (claude.md §4.4). We
        # therefore never touch Pillar 3 here.
        f = self._facilities.get(signal.facility_ref)
        if f is None:
            # A staging signal for an unknown facility is not silently ignored:
            # fail loud (a real feed integrity gap), do not guess.
            raise ValueError(
                f"Staging signal for unknown facility {signal.facility_ref} "
                "(no risk packet registered)"
            )
        # On stage migration we re-provision ECL from the stage-adjusted formula
        # (MoC is already applied by P2 — no double-counting of conservatism).
        f.stage = signal.stage
        f.ecl = self._stage_ecl(f)

        # EL Pool absorbs/releases provision accordingly. We adjust the EL Pool
        # by the change in ECL provision (delta). A positive delta is a credit
        # (provision cover added), a negative delta is a release.
        self._sync_el_pool(f)

        self._emit(
            IntraP4Event(
                IntraP4EventType.STAGING_SIGNAL_RECEIVED,
                {"facility_ref": f.facility_ref, "stage": f.stage, "ecl": f.ecl},
            )
        )

    def _sync_el_pool(self, f: FacilityStaging):
        # The EL Pool is a REAL ledger and is separately drawn by the event
        # router on defaults (provision utilisation) and recovered on the
        # collateral leg. Provisioning therefore posts only the DELTA of the
        # aggregate ECL, never a wholesale overwrite — otherwise the sync that
        # follows a staging migration (or any repayment) would silently erase
        # the loss the router just realised out of the buffer.
        total_provision = round(sum(x.ecl for x in self._facilities.values()), 2)
        delta = round(total_provision - self._synced_provision, 2)
        if abs(delta) > 1e-9:
            el_pool = self._buffer.sub_account(SubAccountId.EL_POOL)
            if delta > 0:
                el_pool.credit(delta, "provision_adjustment")
            else:
                el_pool.debit(-delta, "provision_adjustment")
            self._synced_provision = total_provision

    @property
    def total_provision(self) -> float:
        return sum(x.ecl for x in self._facilities.values())

    def facility_stage(self, facility_ref: str) -> int | None:
        f = self._facilities.get(facility_ref)
        return f.stage if f else None
