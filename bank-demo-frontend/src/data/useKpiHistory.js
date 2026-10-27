import { useEffect, useRef, useState } from "react";

/**
 * The orchestrator doesn't persist a KPI time series (see README §"Known
 * gaps"): `sim_month` is a single counter with no stored history. We
 * reconstruct a trend line client-side by snapshotting on every state
 * change. This resets on a page reload or factory reset — fine for a
 * scripted live demo, but call this out to the client rather than presenting
 * it as durable history. Fix: add a `p1_kpi_history` table / KV key server-
 * side that appends on every POST /p1/demo/tick, plus a GET to read it back.
 */
export function useKpiHistory(state) {
  const [history, setHistory] = useState([]);
  const lastMonth = useRef(null);

  useEffect(() => {
    if (!state) return;
    const month = state.sim_month ?? 0;
    if (lastMonth.current === month && history.length > 0) return;
    lastMonth.current = month;

    const total = (state.candidates || [])
      .filter((c) => ["disbursed", "delinquent", "defaulted"].includes(c.status))
      .reduce((s, c) => s + (c.outstanding || 0), 0);

    setHistory((prev) => {
      const withoutThisMonth = prev.filter((p) => p.month !== month);
      return [...withoutThisMonth, { month, total }].sort((a, b) => a.month - b.month);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.sim_month, state?.candidates]);

  return history;
}
