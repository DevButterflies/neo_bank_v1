import asyncio
import os
import sys
import tempfile

import httpx

d = tempfile.mkdtemp(prefix="orchgate_")
db = os.path.join(d, "orch.db")
os.environ["BANK_ORCH_DB_PATH"] = db


async def main() -> None:
    from bank.orchestrator.main import app
    from bank.pillars.api.p3 import P3Runtime
    from bank.pillars.api.p4 import P4Runtime

    p3 = P3Runtime(db)
    p4 = P4Runtime(db)
    await p3.load()
    await p4.load()
    await p3.run(lambda o: None)
    await p4.run(lambda o: None)
    print("seeded p3/p4 snapshots")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://orch") as c:
        h = await c.get("/health")
        print("health", h.status_code, h.json())
        r = await c.get("/ready")
        print("ready", r.status_code)
        print("ready-body:", r.text[:400])


asyncio.run(main())
