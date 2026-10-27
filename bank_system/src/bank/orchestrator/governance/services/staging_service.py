"""Staging / Mode registry service (SI-1: Staging Instrument)."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.models.staging import GateState, ModeState, StageState
from bank.orchestrator.governance.schemas.staging import ModeChangeIn


class StagingConflictError(Exception):
    pass


class StagingNotFoundError(Exception):
    pass


async def get_current_mode(db: AsyncSession) -> ModeState | None:
    result = await db.execute(
        select(ModeState).order_by(ModeState.changed_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def set_mode(db: AsyncSession, data: ModeChangeIn) -> ModeState:
    if data.new_mode not in ("CONVENTIONAL", "ADAPTIVE"):
        raise StagingConflictError(f"Invalid mode: {data.new_mode}")
    new_state = ModeState(
        current_mode=data.new_mode,
        changed_by=data.changed_by,
        change_rationale=data.change_rationale,
        changed_at=datetime.now(timezone.utc),
    )
    db.add(new_state)
    await db.commit()
    await db.refresh(new_state)
    return new_state


async def get_current_stage(db: AsyncSession) -> StageState | None:
    result = await db.execute(
        select(StageState).order_by(StageState.changed_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def set_stage(db: AsyncSession, stage: int) -> StageState:
    if stage not in (0, 1, 2, 3):
        raise StagingConflictError(f"Invalid stage: {stage}. Must be 0-3.")
    new_state = StageState(current_stage=stage, changed_at=datetime.now(timezone.utc))
    db.add(new_state)
    await db.commit()
    await db.refresh(new_state)
    return new_state


async def list_gates(db: AsyncSession) -> list[GateState]:
    result = await db.execute(
        select(GateState).order_by(GateState.gate_label)
    )
    return list(result.scalars().all())


async def get_gate(db: AsyncSession, label: str) -> GateState | None:
    result = await db.execute(
        select(GateState).where(GateState.gate_label == label).limit(1)
    )
    return result.scalar_one_or_none()


async def clear_gate(
    db: AsyncSession, label: str, by: str = "Governance Committee"
) -> GateState:
    gate = await get_gate(db, label)
    if not gate:
        raise StagingNotFoundError(f"Gate {label} not found.")
    gate.status = "CLEARED"
    gate.cleared_at = datetime.now(timezone.utc)
    gate.cleared_by = by
    await db.commit()
    await db.refresh(gate)
    return gate


async def block_gate(
    db: AsyncSession, label: str, notes: str | None = None
) -> GateState:
    gate = await get_gate(db, label)
    if not gate:
        raise StagingNotFoundError(f"Gate {label} not found.")
    gate.status = "BLOCKED"
    gate.notes = notes if notes else gate.notes
    await db.commit()
    await db.refresh(gate)
    return gate
