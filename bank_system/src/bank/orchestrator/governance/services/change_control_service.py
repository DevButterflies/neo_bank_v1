"""Change Control service."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bank.orchestrator.governance.models.change_control import (
    ChangeProposal,
    DependencyReview,
    RatificationVote,
)
from bank.orchestrator.governance.schemas.change_control import ChangeProposalCreate, DependencyReviewCreate


class ChangeControlNotFoundError(Exception):
    pass


class ChangeControlConflictError(Exception):
    pass


async def _next_proposal_number(db: AsyncSession) -> str:
    result = await db.execute(select(func.count()).select_from(ChangeProposal))
    count = result.scalar() or 0
    return f"CP-{count + 1:03d}"


async def create_proposal(
    db: AsyncSession, data: ChangeProposalCreate
) -> ChangeProposal:
    number = await _next_proposal_number(db)
    proposal = ChangeProposal(
        proposal_number=number,
        title=data.title,
        description=data.description,
        change_type=data.change_type,
        proposed_by=data.proposed_by,
        canon_version_target=data.canon_version_target,
        requires_dependency_review=data.requires_dependency_review,
        requires_g2s_review=data.requires_g2s_review,
    )
    # G→S migration is always a full structural change requiring dependency review.
    if data.change_type == "MIGRATION_G2S":
        proposal.requires_dependency_review = True
        proposal.requires_g2s_review = True
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    # Auto-create dependency review rows if required.
    if proposal.requires_dependency_review:
        for pillar in (2, 3, 4):
            db.add(
                DependencyReview(
                    proposal_id=proposal.id, pillar_number=pillar, review_status="PENDING"
                )
            )
        await db.commit()
        await db.refresh(proposal)
    return proposal


async def list_proposals(
    db: AsyncSession, status: str | None = None, change_type: str | None = None
) -> list[ChangeProposal]:
    stmt = select(ChangeProposal).order_by(ChangeProposal.submitted_at.desc())
    if status:
        stmt = stmt.where(ChangeProposal.status == status)
    if change_type:
        stmt = stmt.where(ChangeProposal.change_type == change_type)
    result = await db.execute(stmt.options(selectinload(ChangeProposal.dependency_reviews)))
    return list(result.scalars().all())


async def get_proposal(db: AsyncSession, proposal_id) -> ChangeProposal | None:
    result = await db.execute(
        select(ChangeProposal)
        .options(
            selectinload(ChangeProposal.dependency_reviews),
            selectinload(ChangeProposal.ratification_votes),
        )
        .where(ChangeProposal.id == proposal_id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def submit_dependency_review(
    db: AsyncSession, proposal_id, data: DependencyReviewCreate
) -> DependencyReview:
    proposal = await get_proposal(db, proposal_id)
    if not proposal:
        raise ChangeControlNotFoundError("Proposal not found.")
    # Update an existing review for this pillar if one exists (auto-created
    # at proposal time), otherwise create a new one.
    existing_review = next(
        (r for r in proposal.dependency_reviews if r.pillar_number == data.pillar_number),
        None,
    )
    if existing_review:
        existing_review.review_status = data.review_status
        existing_review.reviewer_notes = data.reviewer_notes
        existing_review.reviewed_at = datetime.now(timezone.utc)
        review = existing_review
    else:
        review = DependencyReview(
            proposal_id=proposal.id,
            pillar_number=data.pillar_number,
            review_status=data.review_status,
            reviewer_notes=data.reviewer_notes,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


async def ratify_proposal(
    db: AsyncSession,
    proposal_id,
    instrument_number: str | None = None,
    resolution_ref: str | None = None,
) -> ChangeProposal:
    proposal = await get_proposal(db, proposal_id)
    if not proposal:
        raise ChangeControlNotFoundError("Proposal not found.")
    if proposal.status == "RATIFIED":
        raise ChangeControlConflictError("Proposal already ratified.")

    # If dependency review is required, all must be APPROVED or NOT_APPLICABLE.
    if proposal.requires_dependency_review:
        reviews = proposal.dependency_reviews
        pending = [r for r in reviews if r.review_status == "PENDING"]
        if pending:
            raise ChangeControlConflictError(
                f"Cannot ratify: {len(pending)} dependency review(s) still PENDING."
            )

    proposal.status = "RATIFIED"
    proposal.resolved_at = datetime.now(timezone.utc)

    # Assign ratification instrument number.
    if instrument_number is None:
        result = await db.execute(select(func.count()).select_from(RatificationVote))
        count = result.scalar() or 0
        instrument_number = f"RI-{count + 1}"

    vote = RatificationVote(
        proposal_id=proposal.id,
        instrument_number=instrument_number,
        resolution_ref=resolution_ref,
        vote="RATIFIED",
        voted_at=datetime.now(timezone.utc),
    )
    db.add(vote)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def reject_proposal(db: AsyncSession, proposal_id) -> ChangeProposal:
    proposal = await get_proposal(db, proposal_id)
    if not proposal:
        raise ChangeControlNotFoundError("Proposal not found.")
    proposal.status = "REJECTED"
    proposal.resolved_at = datetime.now(timezone.utc)
    vote = RatificationVote(
        proposal_id=proposal.id, vote="REJECTED", voted_at=datetime.now(timezone.utc)
    )
    db.add(vote)
    await db.commit()
    await db.refresh(proposal)
    return proposal
