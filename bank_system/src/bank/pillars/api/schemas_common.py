"""Schemas shared across pillar APIs."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorOut(BaseModel):
    """Uniform error body for HTTPException responses."""

    detail: str
