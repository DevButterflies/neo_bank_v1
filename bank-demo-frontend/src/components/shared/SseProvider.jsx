import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SSE_URL, API } from "../../data/api";
import { invalidateLive } from "../../data/hooks";

const SseContext = createContext({ connected: false, lastEvent: null });

export function useSse() {
  return useContext(SseContext);
}

/**
 * Wraps GET /p1/demo/events/sse. Per the API doc: frames are `data: {...}`,
 * `kind` distinguishes state / tick / reset / state_update, and an idle
 * heartbeat `{}` fires every 30s (ignored here). On reconnect failure we
 * back off 3s, matching the documented client contract, and we skip
 * reconnecting while the tab is hidden.
 *
 * Crucially: SSE only carries the P1 snapshot. It does NOT push P3 facility/
 * ledger/audit changes or P4 capital/adequacy changes, even though a tick
 * or disburse changes all of them. So on every frame (not just ones with a
 * `state` payload) we also invalidate the P3/P4 react-query keys — see
 * data/hooks.js LIVE_KEYS. That's what makes the whole demo feel live
 * instead of "the KPI tab is stale until you click refresh."
 */
export function SseProvider({ children }) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const qc = useQueryClient();
  const esRef = useRef(null);
  const retryRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      let es;
      try {
        es = new EventSource(SSE_URL);
      } catch {
        setConnected(false);
        scheduleRetry();
        return;
      }
      esRef.current = es;

      es.onopen = () => setConnected(true);

      es.onmessage = (evt) => {
        if (!evt.data || evt.data === "{}") return; // heartbeat
        let payload;
        try {
          payload = JSON.parse(evt.data);
        } catch {
          return;
        }
        setLastEvent(payload);
        const kind = payload.kind;
        // Only SERVER-INITIATED frames carry an authoritative snapshot built
        // AFTER a commit: tick / reset / state_update. The poll-triggered
        // "state" frames are redundant with the poll's own GET response, so we
        // never setQueryData from them — an older poll snapshot must not be
        // able to overwrite a freshly refetched board (stale-last-write-wins).
        if (
          (kind === "tick" || kind === "reset" || kind === "state_update") &&
          payload.state
        ) {
          qc.setQueryData(["demoState"], payload.state);
        }
        invalidateLive(qc);
      };

      es.onerror = () => {
        setConnected(false);
        es.close();
        scheduleRetry();
      };
    }

    function scheduleRetry() {
      if (document.visibilityState === "hidden") return;
      clearTimeout(retryRef.current);
      retryRef.current = setTimeout(connect, 3000);
    }

    connect();

    // API.demoState() already polls as a fallback path via useDemoStatePoll;
    // this just kicks the very first paint so the badge isn't blank.
    API.ready();

    return () => {
      cancelled = true;
      clearTimeout(retryRef.current);
      esRef.current?.close();
    };
  }, [qc]);

  return <SseContext.Provider value={{ connected, lastEvent }}>{children}</SseContext.Provider>;
}
