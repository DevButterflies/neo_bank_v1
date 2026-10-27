import asyncio
import inspect

from bank.pillars.api.codec import encode
from bank.pillars.api.p4 import P4Runtime, STORAGE_KEY
from bank.pillars.p4.contracts.p2_inbound import (
    Pillar2RiskPacket as R,
    StagingSignal as S,
    RequiredGuaranteeLevel as G,
)


async def main() -> None:
    a = P4Runtime(":memory:")
    await a.load()
    o = a._ensure_engine()
    p2 = o.ports.p2
    print("feed_risk_packet", inspect.signature(p2.feed_risk_packet))
    print("feed_staging_signal", inspect.signature(p2.feed_staging_signal))
    print("feed_required_guarantee_level", inspect.signature(p2.feed_required_guarantee_level))
    print("R fields", {k: v.type for k, v in R.__dataclass_fields__.items()})
    print("S fields", {k: v.type for k, v in S.__dataclass_fields__.items()})
    print("G fields", {k: v.type for k, v in G.__dataclass_fields__.items()})
    print("STORAGE_KEY", STORAGE_KEY)


asyncio.run(main())
