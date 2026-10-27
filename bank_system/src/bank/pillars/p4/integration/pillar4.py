"""Pillar 4 orchestration facade.

Composes Part I + Part II + Mode Gate into the Pillar 4 whole and wires the
Part I <-> Part II relationships (claude.md §6) and the cross-pillar
communication (claude.md §9).

Hard boundaries enforced here:
  - NO per-loan interface between Pillar 4 and Pillar 3. The only path to
    Pillar 3 is via Pillar 2's confirmed/withheld packet (resolution-at-P2,
    claude.md §2.2).
  - No allocation/burden-sharing/repartition logic in Pillar 3.
  - Two-Guarantee-Layer Rule: the pooled guarantee (PledgePosition) and
    MSME-pledged collateral (Pillar5AdmittedCollateral) are distinct types.
  - Four-Event Discipline: release != redemption != foreclosure != call.
  - Pledge-release invariant: no cash, no LR draw.
  - No double-counting of conservatism.
"""

from __future__ import annotations

from ..mode_gate.mode_gate import ModeGateService
from ..domain.buffer_account import BufferAccount, SubAccountId
from ..domain.guarantee_pool import GuaranteePool
from ..domain.events import IntraP4Event, IntraP4EventType
from ..part1_core_prudential import (
    TierConsumptionService,
    CapitalLeverageCalculator,
    VetoEngine,
    OrchestratorNotifier,
    Ifrs9StagingConsumer,
    LiquidityMonitor,
    ConcentrationMonitor,
)
from ..part2_guarantee_buffer import (
    BufferService,
    EventRouter,
    GuaranteeCallSettlementEngine,
    GuaranteePoolCustody,
    PledgeReleaseManager,
)
from .adapters import (
    OrchestratorPartner,
    Pillar2Port,
    Pillar3Port,
    Pillar5Port,
)


class Pillar4:
    """The Pillar 4 whole: composed services + cross-pillar communication."""

    def __init__(
        self,
        *,
        in_memory_ports=True,
        auto_lift_on_sustained_clean: int = 0,
        **service_overrides,
    ):
        # ---- base composition ------------------------------------------
        self.mode_gate = service_overrides.get("mode_gate", ModeGateService())
        tier_table = service_overrides.get("tier_table")
        self.tier_service = TierConsumptionService(tier_table)
        buffer_account = service_overrides.get("buffer_account", BufferAccount())
        self.buffer_service = BufferService(buffer_account)
        self.pool = service_overrides.get("guarantee_pool", GuaranteePool())

        notifier = OrchestratorNotifier()
        self.veto_engine = VetoEngine(
            notifier=notifier,
            auto_lift_on_sustained_clean=auto_lift_on_sustained_clean,
        )

        self.capital = CapitalLeverageCalculator(self.tier_service)
        self.ifrs9 = Ifrs9StagingConsumer(self.buffer_service.account)
        self.liquidity = LiquidityMonitor()
        self.concentration = ConcentrationMonitor()
        self.event_router = EventRouter(self.buffer_service.account)
        self.guarantee_call = GuaranteeCallSettlementEngine(
            self.buffer_service.account, self.pool
        )
        self.custody = GuaranteePoolCustody(self.pool)
        self.pledge_release = PledgeReleaseManager(self.pool, self.buffer_service.account)

        # ---- event plumbing (Part I <-> Part II) ------------------------
        self._event_log: list[IntraP4Event] = []
        self._wire_events()

        # ---- cross-pillar ports -----------------------------------------
        if in_memory_ports:
            self.ports = InMemoryPorts(self)
        self.orchestrator = OrchestratorPartner(notifier)

    def _wire_events(self):
        # Part II -> Part I: a sub-account balance change triggers a capital
        # recompute evaluation (claude.md §6). We hold the log so the bridge
        # can react; the actual continuous evaluation is driven by the
        # reconcile() entry described in the integration module.
        base = self.buffer_service._event_sink

        def sink(ev: IntraP4Event):
            self._event_log.append(ev)

        self.buffer_service._event_sink = sink
        self.event_router._event_sink = sink
        self.ifrs9._event_sink = sink
        self.guarantee_call._event_sink = sink
        self.custody._event_sink = sink
        self.pledge_release.event_sink = sink

    # ---- Part I <-> Part II recompute bridge -----------------------------
    def _track1_inputs(self):
        """Compute the raw Track-1 inputs: snapshot + breached + unmonitored.

        Pure evaluation — no freeze side-effect. Shared by the standing
        recompute (which freezes) and the read-only surfacing (which must
        never mutate the veto state).
        """
        snapshot = self.capital.snapshot(
            self.buffer_service.account, self.pool
        )
        self.capital.evals_to_flags(snapshot)

        # LR below minimum: liquidity monitor (funding-side). If the PENDING
        # minimum is unconfigured, we surface the PENDING stop but do not
        # fabricate a breach.
        min_below = False
        pending_liquidity_msg = None
        try:
            min_below = self.liquidity.is_below_minimum(self.buffer_service.account)
        except Exception as exc:  # noqa: BLE001
            pending_liquidity_msg = str(exc)

        # Guard: no exposure (RWA=0) → ratio vacuously safe (inf means not breached).
        effective_tier_d = snapshot.tier_d_over_rwa if snapshot.rwa > 0 else float("inf")
        # Concentration limits are PENDING until governance approves percentages;
        # captured as plain flags so the evaluation treats them as not-breached
        # while the reported state still surfaces them as unmonitored (never a
        # silent "clear").
        sector_concentration_breached: bool | None = None
        pool_concentration_breached: bool | None = None
        breached = self.veto_engine.evaluate_track1(
            tier_d_over_rwa=effective_tier_d,
            tier_d_floor=self.capital.tier_d_floor,
            portfolio_el=snapshot.portfolio_el,
            budgeted_loss_ratio=self.capital.budgeted_loss_ratio,
            gg_ratio=snapshot.guarantees_granted_over_received,
            gg_bound=1.0,  # calibration bound; G/G ratio breach governed by bound
            liquidity_breached=min_below,
            sector_concentration_breached=sector_concentration_breached,
            pool_concentration_breached=pool_concentration_breached,
            cass_severe_zone=False,
        )

        # Anything we cannot compute a threshold for is "unmonitored", never
        # silently "clear": surface it so the API/UI can distinguish.
        from ..domain.veto import TriggerType

        unmonitored: list[str] = []
        if pending_liquidity_msg:
            unmonitored.append(TriggerType.LIQUIDITY_BUFFER.value)
        if sector_concentration_breached is None:
            unmonitored.append(TriggerType.SECTOR_CONCENTRATION.value)
        if pool_concentration_breached is None:
            unmonitored.append(TriggerType.GUARANTEE_POOL_CONCENTRATION.value)

        return snapshot, breached, unmonitored, pending_liquidity_msg

    def _freeze_evidence(self, snapshot) -> dict:
        """Governing metric values captured at freeze time (traceability).

        Plain JSON-safe dict stored per trigger on ``Track1State.freeze_details``
        so the demo UI / audit trail can say *what value tripped the freeze*,
        not just *which* trigger.
        """
        ead_book = sum(p.ead for p in self.capital._packets.values())
        el_book = sum(p.el for p in self.capital._packets.values())
        return {
            "portfolio_el": snapshot.portfolio_el,
            "budgeted_loss_ratio": self.capital.budgeted_loss_ratio,
            "tier_d_over_rwa": snapshot.tier_d_over_rwa,
            "tier_d_floor": self.capital.tier_d_floor,
            "rwa": snapshot.rwa,
            "ead_book": round(ead_book, 2),
            "el_book": round(el_book, 2),
            "guarantees_granted_over_received": snapshot.guarantees_granted_over_received,
        }

    def recompute_and_evaluate_track1(self) -> dict:
        """Continuous Track 1 evaluation from live Part II balances (claude.md §6).

        Reads the EL Pool / LR balances and the pool books (Part II) and
        evaluates the Track 1 static triggers (Part I). Returns the snapshot
        plus the list of breached triggers (a standing boolean state).
        """
        snapshot, breached, unmonitored, pending_liquidity_msg = self._track1_inputs()
        settled = self.veto_engine.settle_track1_recompute(
            breached, details=self._freeze_evidence(snapshot)
        )

        return {
            "snapshot": snapshot,
            "breached_triggers": [t.value for t in breached],
            "unmonitored_triggers": unmonitored,
            "liquidity_pending": pending_liquidity_msg,
            "auto_lifted": settled["auto_lifted"],
        }

    def evaluate_track1_read_only(self) -> dict:
        """Read-only Track-1 evaluation — never mutates the veto state.

        Identical computation to recompute_and_evaluate_track1 but without the
        compression-into-standing-freeze (ensure_track1). Used by the demo
        state feed so the UI/banner can explain a freeze (or near-breach)
        without side effects. The /p4/recompute-track1 endpoint (with the
        write path) remains the authoritative trigger.
        """
        snapshot, breached, unmonitored, pending_liquidity_msg = self._track1_inputs()

        return {
            "snapshot": snapshot,
            "breached_triggers": [t.value for t in breached],
            "unmonitored_triggers": unmonitored,
            "liquidity_pending": pending_liquidity_msg,
        }

    # ---- convenience accessors -------------------------------------------
    def balances(self):
        return self.buffer_service.balances()

    def pool_adequacy(self):
        return self.custody.adequacy_metrics()

    @property
    def event_log(self):
        return self._event_log


class InMemoryPorts:
    """In-memory cross-pillar ports (no external infra).

    These are the concrete communication adapters: Pillar 2 feeds risk packets,
    staging signals, required guarantee level, and consults the veto state;
    Pillar 3 feeds loan-level events; Pillar 5 submits pledges; the Orchestrator
    supplies the tier table and consumes veto freeze notifications.
    """

    def __init__(self, p4: "Pillar4"):
        self._p4 = p4
        self.p2 = Pillar2Port(p4)
        self.p3 = Pillar3Port(p4)
        self.p5 = Pillar5Port(p4)
        self.orchestrator = OrchestratorPartner(p4.veto_engine.notifier)
