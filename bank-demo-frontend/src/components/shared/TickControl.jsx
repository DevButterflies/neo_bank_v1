import { useState } from "react";
import { useDemoStatePoll, useTick, useReset } from "../../data/hooks";

export function TickControl() {
  const { data: state } = useDemoStatePoll();
  const tick = useTick();
  const reset = useReset();
  const [confirmReset, setConfirmReset] = useState(false);

  return (
    <div className="fixed bottom-5 right-5 z-40 flex items-center gap-2 bg-raised border border-line rounded-md shadow-2xl shadow-black/40 px-3 py-2">
      <div className="pr-3 border-r border-line">
        <div className="text-[10px] text-faint leading-none mb-0.5">Sim month</div>
        <div className="font-mono text-lg leading-none text-ledger">{state?.sim_month ?? "—"}</div>
      </div>
      <button
        onClick={() => tick.mutate()}
        disabled={tick.isPending}
        className="px-3 py-1.5 bg-ledger text-ink text-xs font-medium rounded-sm hover:bg-ledger/90 disabled:opacity-50 transition"
      >
        {tick.isPending ? "Advancing…" : "Simulate next month ▶"}
      </button>
      {confirmReset ? (
        <div className="flex items-center gap-1">
          <button
            onClick={() => {
              reset.mutate();
              setConfirmReset(false);
            }}
            className="px-2 py-1.5 bg-danger text-ink text-xs rounded-sm"
          >
            Confirm reset
          </button>
          <button onClick={() => setConfirmReset(false)} className="px-2 py-1.5 text-xs text-muted">
            Cancel
          </button>
        </div>
      ) : (
        <button onClick={() => setConfirmReset(true)} className="px-2 py-1.5 text-xs text-muted hover:text-danger transition">
          Factory reset
        </button>
      )}
    </div>
  );
}
