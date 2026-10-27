"""One-shot export: dump every P1 candidate to ``data/candidates/<slug>.json``.

Run from ``bank_system/``::

    $env:PYTHONPATH = "src"; python -m bank.pillars.p1.export_candidates

Idempotent — overwrites existing files, creates ``data/candidates/`` if missing.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "candidates"


def _slugify(text: str) -> str:
    """Lowercase-hyphenate: 'Fatima General Store' -> 'fatima-general-store'."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s]+", "-", text)


def _serialize(cand) -> dict:
    """Build a flat dict from a Candidate ORM row for JSON output."""
    d = {}
    for col in cand.__table__.columns:
        val = getattr(cand, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[col.name] = val
    d["display_name"] = cand.display_name
    return d


async def export() -> None:
    from bank.orchestrator.governance.database import init_models
    from bank.pillars.p1.seed_data import seed_candidates
    from bank.pillars.p1.service import service

    await init_models()
    await seed_candidates()

    candidates = await service.list()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    wrote = 0
    missing_behavior = 0
    for cand in candidates:
        data = _serialize(cand)
        name_part = _slugify(
            cand.seed_profile
            or f"{cand.first_name} {cand.last_name}"
        )
        path = DATA_DIR / f"{name_part}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        wrote += 1
        if not cand.payment_behavior:
            missing_behavior += 1

    print(f"exported {wrote} candidates -> {DATA_DIR}")
    if missing_behavior:
        print(f"  {missing_behavior} had no payment_behavior")


if __name__ == "__main__":
    asyncio.run(export())
