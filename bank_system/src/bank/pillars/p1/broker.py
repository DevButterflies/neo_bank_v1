"""Demo event broker — tiny in-process pub/sub for SSE.

Copied from the combined demo pattern: one module-level broker survives
resets; SSE clients stay subscribed and immediately receive the fresh
snapshot.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, event: Dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


BROKER = EventBroker()


async def publish_event(kind: str, data: dict | None = None) -> None:
    await BROKER.publish({"kind": kind, **(data or {})})
