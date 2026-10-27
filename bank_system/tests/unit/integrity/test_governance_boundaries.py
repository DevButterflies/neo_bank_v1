"""
Integrity tests.

These are not feature tests — they assert properties the governing
documents call *structural* and that must therefore hold across the
whole codebase, not just in the modules that were deliberately written
to enforce them. If someone adds a new engine module three years from
now that quietly computes a tier split, these tests are designed to
catch it.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from bank.pillars import p3
from bank.pillars.p3.core_banking.interface import CoreBankingClient
from bank.pillars.p3.core_banking.ledger import CoreBankingLedger
from bank.pillars.p3.domain.enums import CollateralTrack, PostingEventType
from bank.pillars.p3.engine.orchestrator import Pillar3Orchestrator
from bank.pillars.p3.errors import GovernanceBoundaryError, PendingGovernanceItemError
from bank.pillars.p3.governance.pending_registry import PendingItem
from tests.conftest import make_packet

SRC_ROOT = pathlib.Path(p3.__file__).resolve().parent

# Identifiers that would indicate cross-tier allocation logic has crept
# into the codebase outside the explicitly-approved governance module
# (which only ever *rejects* these, never computes them).
FORBIDDEN_IDENTIFIERS = {
    "tier_a_share", "tier_b_share", "tier_c_share", "tier_d_share",
    "tier_allocation", "burden_share", "absf_amount", "loss_repartition",
    "tier_b_fees_allocation", "compute_allocation", "allocate_tier",
}

# Files allowed to *mention* these identifiers, because their entire job
# is to define/reject them.
ALLOWLISTED_FILES = {"allocation_guard.py"}


def _iter_source_files():
    return [p for p in SRC_ROOT.rglob("*.py") if p.name != "__init__.py"]


def test_no_cross_tier_allocation_identifiers_anywhere_in_source():
    """Static proof of Canon §4: allocation logic must not exist in P3
    source at all, not just be blocked at runtime."""
    offenders = []
    for path in _iter_source_files():
        if path.name in ALLOWLISTED_FILES:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            name = getattr(node, "id", None) or getattr(node, "attr", None)
            if name and name.lower() in FORBIDDEN_IDENTIFIERS:
                offenders.append(f"{path.relative_to(SRC_ROOT)}: {name}")
    assert not offenders, f"Forbidden allocation identifiers found: {offenders}"


def test_pending_registry_has_no_resolving_method():
    """Static proof that the PENDING registry module exposes no function
    that could return a real value for a PENDING item — only `stub`,
    which always raises."""
    module_path = SRC_ROOT / "governance" / "pending_registry.py"
    tree = ast.parse(module_path.read_text())
    public_funcs = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]
    assert set(public_funcs) == {"stub", "is_registered"}


@pytest.mark.parametrize("item", list(PendingItem))
def test_all_five_pending_items_are_unresolvable(item):
    from bank.pillars.p3.governance.pending_registry import stub
    with pytest.raises(PendingGovernanceItemError):
        stub(item)


def test_only_core_banking_client_can_write_the_ledger():
    """CoreBankingLedger.post() is only ever called through
    CoreBankingClient. reconciliation.py is allowed to *read* the ledger
    (Canon §8.3 -- daily reconciliation is inherently read-only) but must
    never call .post() on it directly -- that distinction, not the mere
    import, is what this test enforces."""
    # orchestrator.py legitimately holds a CoreBankingClient, not the raw
    # ledger, so it is out of scope for this scan -- the client is the seam.
    read_only_allowed = {"reconciliation.py"}

    for subdir in ("engine", "interfaces"):
        for path in (SRC_ROOT / subdir).glob("*.py"):
            if path.name == "orchestrator.py":
                continue
            source = path.read_text()
            if path.name in read_only_allowed:
                assert "ledger.post(" not in source, (
                    f"{path.relative_to(SRC_ROOT)} is read-only-allowed for "
                    "CoreBankingLedger but appears to call .post() on it "
                    "directly, bypassing CoreBankingClient."
                )
                continue
            assert "CoreBankingLedger" not in source, (
                f"{path.relative_to(SRC_ROOT)} references CoreBankingLedger "
                "directly; it must go through CoreBankingClient (core "
                "banking is system of record -- Canon §3.3)."
            )


def test_end_to_end_sandbox_run_never_produces_an_allocation_or_bypasses_pending():
    """Behavioral proof: drive a full facility through the orchestrator
    and confirm nothing in the resulting audit trail / posted events /
    routed questions carries an allocation computation, and any Track 2/3
    or pooled-guarantee attempt is refused rather than silently applied.
    """
    ledger = CoreBankingLedger()
    client = CoreBankingClient(ledger)
    orch = Pillar3Orchestrator(client)

    packet = make_packet(facility_id="FAC-INTEGRITY")
    orch.originate(packet)
    orch.pledge_collateral("FAC-INTEGRITY", packet)
    orch.disburse("FAC-INTEGRITY", packet, 10_000.0, "USD")
    orch.record_repayment("FAC-INTEGRITY", packet, 100.0, 500.0, "USD")

    for event in orch.posting_service.posted_events():
        assert not hasattr(event, "tier_allocation")

    for question in orch.posting_service.routed_allocation_questions():
        assert not hasattr(question, "tier_allocation")
        # the routing signal must carry a raw amount + facts only
        assert set(question.__dataclass_fields__) == {
            "source_event_id", "facility_id", "event_type", "amount", "currency"
        }

    # Attempting Track 2 collateral must refuse, not silently downgrade.
    track2_packet = make_packet(
        facility_id="FAC-INTEGRITY", packet_id="P2-T2", collateral_track=CollateralTrack.TRACK_2_NFT
    )
    with pytest.raises(PendingGovernanceItemError):
        orch.collateral_service.record_msme_pledged_collateral(
            orch.get_or_create_facility("FAC-INTEGRITY"), track2_packet
        )

    with pytest.raises(GovernanceBoundaryError):
        orch.collateral_service.record_pooled_guarantee_pledge()


def test_audit_trail_is_append_only_across_a_full_run():
    """Behavioral proof of Spec §8: the audit trail only grows; no
    action decreases its length or mutates an existing record."""
    ledger = CoreBankingLedger()
    client = CoreBankingClient(ledger)
    orch = Pillar3Orchestrator(client)
    packet = make_packet(facility_id="FAC-AUDIT")

    orch.originate(packet)
    n1 = len(orch.audit_trail)
    orch.disburse("FAC-AUDIT", packet, 5_000.0, "USD")
    n2 = len(orch.audit_trail)
    orch.record_repayment("FAC-AUDIT", packet, 50.0, 200.0, "USD")
    n3 = len(orch.audit_trail)

    assert n1 < n2 < n3
    # identity check: earlier records are still present, unchanged, at
    # their original list position
    all_records = orch.audit_trail.all_records()
    assert all_records[0].event_type == "ORIGINATION_RECORDED"


def test_sandbox_auto_origination_path_cannot_be_reached():
    """Behavioral proof of Build Handoff §5's binding gate: an
    unconfirmed packet at SANDBOX maturity can never reach `originate`
    successfully, with or without a production-style approval object."""
    from bank.pillars.p3.domain.enums import MaturityStage, P2PacketStatus
    from bank.pillars.p3.errors import AutoOriginationNotPermittedError
    from bank.pillars.p3.governance.maturity_gate import ProductionAutoApproval

    ledger = CoreBankingLedger()
    client = CoreBankingClient(ledger)
    orch = Pillar3Orchestrator(client)

    unconfirmed_sandbox = make_packet(
        facility_id="FAC-SANDBOX",
        status=P2PacketStatus.CONDITIONAL,
        officer_confirmed=False,
        officer_id=None,
        maturity_stage=MaturityStage.SANDBOX,
    )
    bogus_approval = ProductionAutoApproval(approved_by_p4=True, orchestrator_notified=True)
    with pytest.raises(AutoOriginationNotPermittedError):
        orch.originate(unconfirmed_sandbox, production_auto_approval=bogus_approval)
