import { useReady } from "../../data/hooks";
import { useSse } from "./SseProvider";
import { Dot } from "./Atoms";

export function ReadyBadge() {
  const { data } = useReady();
  const { connected } = useSse();
  const ok = data?.status === "ok";

  return (
    <div className="flex items-center gap-4 text-[11px] font-mono text-muted">
      <span className="flex items-center gap-1.5">
        <Dot ok={ok} />
        {ok ? "Engine ready" : "Engine degraded"}
      </span>
      <span className="flex items-center gap-1.5">
        <Dot ok={connected} />
        {connected ? "Live · SSE" : "Polling"}
      </span>
    </div>
  );
}
