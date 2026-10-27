"""P1 CRUD + lifecycle endpoints (submit / approve / disburse).

Mounted at ``/p1``.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from bank.pillars.p1 import flow
from bank.pillars.p1.broker import publish_event
from bank.pillars.p1.mirror import mirror_close
from bank.pillars.p1.schemas import (
    ApprovalDecision,
    CandidateCreate,
    CandidateEnvelope,
    CandidateImport,
    CandidateListOut,
    CandidateRead,
    DataFileListOut,
    DisbursementRequest,
    FlowResultOut,
)
from bank.pillars.p1.service import (
    CandidateDuplicateError,
    CandidateNotFoundError,
    CandidateStateError,
    service,
)
from bank.pillars.p1.state import build_demo_state

router = APIRouter(tags=["p1"])

_DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "candidates"


def _error(status: int, msg: str) -> HTTPException:
    return HTTPException(status_code=status, detail=msg)


# ---- helpers ----------------------------------------------------------------


def _read(cand) -> CandidateRead:
    return CandidateRead.model_validate(cand, from_attributes=True)


# ---- CRUD -------------------------------------------------------------------


@router.post(
    "/candidates",
    response_model=CandidateEnvelope,
    status_code=201,
    summary="Create a candidate",
    description=(
        "Borrower intake form. Auto-generates a payment behaviour (or uses "
        "the override) and stages the candidate as ``new``."
    ),
)
async def create_candidate(body: CandidateCreate):
    cand = await service.create(body)
    await _publish()
    return {
        "candidate": _read(cand),
        "payment_behavior": cand.payment_behavior,
    }


@router.get(
    "/candidates",
    response_model=CandidateListOut,
    summary="List candidates",
    description="Optionally filter by ``status`` (new / submitted / approved / disbursed / rejected).",
)
async def list_candidates(status: str | None = Query(None)):
    page = await service.list(status=status)
    return {"candidates": [_read(c) for c in page]}


# ---- import from exported JSON (static paths BEFORE {candidate_id}) --------


@router.post(
    "/candidates/import",
    response_model=CandidateEnvelope,
    status_code=201,
    summary="Import a candidate (JSON body)",
    description=(
        "Import a candidate from an exported JSON payload. Payment "
        "behaviour is used verbatim when present; otherwise auto-generated. "
        "Status is always ``new`` so the demo pipeline can re-run from "
        "scratch. Re-importing an existing borrower returns 409 (never a "
        "duplicate row)."
    ),
    responses={409: {"description": "Candidate already exists"}},
)
async def import_candidate(body: CandidateImport):
    """Import a candidate from an exported JSON payload.

    Payment behaviour is used verbatim when present; otherwise auto-generated.
    Status is always ``new`` so the demo pipeline can re-run from scratch.
    Re-importing an existing borrower returns ``409 Conflict`` (never a
    duplicate row).
    """
    try:
        cand = await service.import_candidate(body)
    except CandidateDuplicateError as exc:
        raise _error(409, str(exc))
    await _publish()
    return {
        "candidate": _read(cand),
        "payment_behavior": cand.payment_behavior,
    }


@router.post(
    "/candidates/import/file",
    response_model=CandidateEnvelope,
    status_code=201,
    summary="Import a candidate (file upload)",
    description="Import a candidate from a JSON file upload.",
    responses={409: {"description": "Candidate already exists"}},
)
async def import_candidate_file(file: UploadFile = File(...)):
    """Import a candidate from a JSON file upload."""
    raw = await file.read()
    data = json.loads(raw)
    body = CandidateImport.model_validate(data)
    try:
        cand = await service.import_candidate(body)
    except CandidateDuplicateError as exc:
        raise _error(409, str(exc))
    await _publish()
    return {
        "candidate": _read(cand),
        "payment_behavior": cand.payment_behavior,
    }


@router.get(
    "/demo/data-files",
    response_model=DataFileListOut,
    summary="List exported candidate files",
    description="List exported candidate JSON files under ``data/candidates/``.",
)
async def list_data_files():
    """List exported candidate JSON files under ``data/candidates/``."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            files.append({
                "filename": p.name,
                "name": (data.get("first_name", "") + " " + data.get("last_name", "")).strip(),
                "seed_profile": data.get("seed_profile"),
                "status": data.get("status", "new"),
                "size_bytes": p.stat().st_size,
            })
        except Exception:
            files.append({"filename": p.name, "name": "?", "size_bytes": p.stat().st_size})
    return {"files": files}


@router.get(
    "/demo/data-files/{filename}",
    summary="Read one exported candidate file",
    description="Return the content of a specific exported candidate JSON file.",
    responses={404: {"description": "File not found"}},
)
async def get_data_file(filename: str):
    """Return the content of a specific exported candidate JSON file."""
    path = _DATA_DIR / filename
    if not path.exists():
        raise _error(404, f"File {filename} not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ---- parametrised CRUD (after static paths) ---------------------------------


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateRead,
    summary="Read a candidate",
    responses={404: {"description": "Unknown candidate"}},
)
async def get_candidate(candidate_id: str):
    try:
        cand = await service.get(candidate_id)
    except CandidateNotFoundError as exc:
        raise _error(404, str(exc))
    return _read(cand)


@router.delete(
    "/candidates/{candidate_id}",
    status_code=204,
    summary="Delete a candidate",
    description="Deletes the candidate row; a disbursed facility is mirrored closed in P3/P4 first.",
    responses={404: {"description": "Unknown candidate"}},
)
async def delete_candidate(candidate_id: str):
    try:
        cand = await service.get(candidate_id)
    except CandidateNotFoundError as exc:
        raise _error(404, str(exc))
    if cand.facility_id:
        await mirror_close(cand.facility_id)
    try:
        await service.delete(candidate_id)
    except CandidateNotFoundError as exc:
        raise _error(404, str(exc))


# ---- lifecycle actions ------------------------------------------------------


@router.post(
    "/candidates/{candidate_id}/submit",
    response_model=FlowResultOut,
    summary="Submit for scoring",
    description=(
        "Run the origination flow: Pillar 2 scores the candidate (BRR, "
        "PD, zone) and a provisional output packet is registered with "
        "Pillar 3; Pillar 4's veto state is consulted as the packet is "
        "confirmed."
    ),
    responses={
        404: {"description": "Unknown candidate"},
        409: {"description": "Candidate not in a submittable state"},
    },
)
async def submit_candidate(candidate_id: str):
    try:
        result = await flow.submit(candidate_id)
    except CandidateNotFoundError as exc:
        raise _error(404, str(exc))
    except CandidateStateError as exc:
        raise _error(409, str(exc))
    await _publish()
    return result


@router.post(
    "/candidates/{candidate_id}/approve",
    response_model=FlowResultOut,
    summary="Officer approval decision",
    description=(
        "The manual officer gate — ALWAYS required "
        "(MANUAL_APPROVAL_ALWAYS). Approval confirms the Pillar 2 packet "
        "and opens the facility in Pillar 3."
    ),
    responses={
        404: {"description": "Unknown candidate"},
        409: {"description": "Candidate not in an approvable state"},
    },
)
async def approve_candidate(candidate_id: str, body: ApprovalDecision):
    try:
        result = await flow.approve(candidate_id, body.model_dump())
    except CandidateNotFoundError as exc:
        raise _error(404, str(exc))
    except CandidateStateError as exc:
        raise _error(409, str(exc))
    await _publish()
    return result


@router.post(
    "/candidates/{candidate_id}/disburse",
    response_model=FlowResultOut,
    summary="Disburse the approved facility",
    description=(
        "Disburse the facility in Pillar 3, register the opening balance "
        "in Pillar 4, and book the origination-fee and risk-premium "
        "postings."
    ),
    responses={
        404: {"description": "Unknown candidate"},
        409: {"description": "Candidate not in a disbursable state"},
    },
)
async def disburse_candidate(
    candidate_id: str,
    body: DisbursementRequest = DisbursementRequest(),
):
    try:
        result = await flow.disburse(
            candidate_id, amount=body.amount, currency=body.currency
        )
    except CandidateNotFoundError as exc:
        raise _error(404, str(exc))
    except CandidateStateError as exc:
        raise _error(409, str(exc))
    await _publish()
    return result


async def _publish():
    state = await build_demo_state()
    await publish_event("state_update", state)
