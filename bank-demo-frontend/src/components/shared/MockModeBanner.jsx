import { useEffect, useState } from "react";
import { getConnectionState, subscribeConnection } from "../../utils/connectionStore";

export function MockModeBanner() {
  const [state, setState] = useState(getConnectionState());

  useEffect(() => subscribeConnection(setState), []);

  if (state.live !== false) return null;

  return (
    <div className="bg-amber/10 border-b border-amber/30 px-6 py-1.5 text-xs text-amber flex items-center gap-2">
      <span>●</span>
      <span>
        Showing sample data — the orchestrator API isn't reachable at this origin. Start it and set
        <code className="mx-1 px-1 bg-ink/50 rounded-sm font-mono">BANK_API_TARGET</code>
        (see README) to see live figures.
      </span>
    </div>
  );
}
