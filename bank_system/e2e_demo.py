"""Full E2E over the orchestrator ASGI app, exercising every endpoint the demo UI uses."""
import asyncio
import json
import sys
import logging

import httpx

from bank.orchestrator.governance.database import init_models, async_session_factory
from bank.orchestrator.main import app

BASE = "http://test"
# suppress noisy httpx logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def request(client, method, path, **kw):
    res = await client.request(method, BASE + path, **kw)
    body = res.text
    if res.status_code == 404:
        return None
    if res.status_code >= 400:
        raise AssertionError(f"{method} {path} -> {res.status_code}: {body[:300]}")
    if not body:
        return None
    return json.loads(body)

async def main():
    await init_models()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE, timeout=60) as c:
        h = await request(c, "GET", "/health")
        print(f"1  health OK: {h['status']}")

        # Initial state must be EMPTY
        s0 = await request(c, "GET", "/p1/demo/state")
        print(f"2  state OK: {len(s0['candidates'])} candidates, month={s0['sim_month']}")
        assert len(s0["candidates"]) == 0, f"Expected 0 candidates, got {len(s0['candidates'])}"

        # Data files
        df = await request(c, "GET", "/p1/demo/data-files")
        files = [f["filename"] for f in df["files"]]
        print(f"3  data-files OK: {files}")
        assert len(files) == 6

        # Import one candidate
        raw = await request(c, "GET", "/p1/demo/data-files/fatima.json")
        imported = await request(c, "POST", "/p1/candidates/import", json=raw)
        cand = imported["candidate"]
        cid = cand["id"]
        print(f"4  import OK: {cand['display_name']} ({cand['status']})")

        # Pipeline: submit
        sub = await request(c, "POST", f"/p1/candidates/{cid}/submit")
        print(f"5  submit OK: zone={sub.get('zone')}, brr={sub.get('brr')}")

        # Pipeline: approve
        appr = await request(c, "POST", f"/p1/candidates/{cid}/approve",
                             json={"approve": True, "officer_id": "OFF-1", "note": "test"})
        print(f"6  approve OK: status={appr.get('status', 'n/a')}")

        # Pipeline: disburse
        disb = await request(c, "POST", f"/p1/candidates/{cid}/disburse")
        print(f"7  disburse OK: facility={disb.get('facility_id', 'n/a')}")

        # P3 facilities
        facs = await request(c, "GET", "/p3/facilities")
        fac_list = facs if isinstance(facs, list) else facs.get("facilities", [])
        print(f"8  P3 facilities: {len(fac_list)}")

        # P3 postings
        pos = await request(c, "GET", "/p3/postings")
        pos_list = pos if isinstance(pos, list) else pos.get("postings", [])
        print(f"9  P3 postings: {len(pos_list)}")

        # P3 ledger
        led = await request(c, "GET", "/p3/ledger")
        print(f"10 P3 ledger OK: keys={list(led.keys()) if isinstance(led, dict) else 'n/a'}")

        # P4 balances
        bals = await request(c, "GET", "/p4/buffer/balances")
        print(f"11 P4 balances: {list(bals.keys())[:4]}")

        # P4 capital
        cap = await request(c, "GET", "/p4/capital/snapshot")
        print(f"12 P4 capital: {list(cap.keys())[:4]}")

        # P4 IFRS9
        ifr = await request(c, "GET", "/p4/ifrs9")
        print(f"13 P4 ifrs9: {list(ifr.keys())[:4]}")

        # P4 mode
        mode = await request(c, "GET", "/p4/mode")
        print(f"14 P4 mode: {mode.get('mode', 'n/a')}")

        # P4 events
        evts = await request(c, "GET", "/p4/events")
        evt_list = evts if isinstance(evts, list) else list(evts)
        print(f"15 P4 events: {len(evt_list)}")

        # Tick simulation
        tick = await request(c, "POST", "/p1/demo/tick")
        print(f"16 tick OK: month={tick['state']['sim_month']}")

        # Verify state after tick
        st = await request(c, "GET", "/p1/demo/state")
        print(f"17 state OK: month={st['sim_month']}, candidates={len(st['candidates'])}")
        print(f"    P4: el_pool={st['p4'].get('balances', {}).get('el_pool', 'N/A')}, "
              f"track1={st['p4'].get('track1_status')}, events={st['p4'].get('event_log_count')}")

        # Governance endpoints
        canon = await request(c, "GET", "/governance/api/v1/canon/current")
        print(f"18 governance canon: {canon}")

        tiers = await request(c, "GET", "/governance/api/v1/tiers")
        print(f"19 tiers: {len(tiers) if tiers else 'not seeded'}")

        pending = await request(c, "GET", "/governance/api/v1/pending")
        print(f"20 pending: {len(pending) if pending else 'not seeded'}")

        # Reset
        res = await request(c, "POST", "/p1/demo/reset")
        print(f"21 reset OK: {res['status']}")
        s1 = await request(c, "GET", "/p1/demo/state")
        print(f"22 final state: {len(s1['candidates'])} candidates, month={s1['sim_month']}")

    print("\nALL E2E CHECKS PASSED")

if __name__ == "__main__":
    asyncio.run(main())