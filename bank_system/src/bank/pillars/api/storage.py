"""Per-service SQLite key/value store.

One SQLite file per service (``data/<service>.db``), a single ``kv`` table,
holding engine snapshots as JSON blobs plus a couple of bookkeeping rows.
Storage is intentionally the dumbest possible layer: it never interprets the
blobs, it only persists and returns them.
"""

from __future__ import annotations

import json

import aiosqlite


class KvStore:
    """Async SQLite key/value store with one table per connection."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def _connect(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._db_path)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        return conn

    async def get(self, key: str) -> str | None:
        conn = await self._connect()
        try:
            async with conn.execute("SELECT value FROM kv WHERE key = ?", (key,)) as cur:
                row = await cur.fetchone()
            return row[0] if row else None
        finally:
            await conn.close()

    async def set(self, key: str, value: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def delete(self, key: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute("DELETE FROM kv WHERE key = ?", (key,))
            await conn.commit()
        finally:
            await conn.close()

    async def get_json(self, key: str) -> dict | list | None:
        raw = await self.get(key)
        return json.loads(raw) if raw is not None else None

    async def set_json(self, key: str, payload: dict | list) -> None:
        await self.set(key, json.dumps(payload, ensure_ascii=False))