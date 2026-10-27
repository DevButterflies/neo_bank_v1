import { reportConnection } from "../utils/connectionStore";
import * as mock from "./mock";

// The orchestrator serves everything on one origin (default :8000). In dev,
// vite.config.js proxies these exact prefixes to it, so relative paths work
// unmodified in both dev and a same-origin production build. See README.

async function request(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

function get(path, opts) {
  return request(path, opts);
}
function post(path, body) {
  return request(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });
}
function del(path) {
  return request(path, { method: "DELETE" });
}

/** Wrap a real call with a mock fallback, and report connection health.
 *
 * An aborted request is NOT a failure: it is rethrown so the caller (react-
 * query, after `cancelRefetch: true`) can discard it without a cache write —
 * an aborted poll must never be able to swap the board for mock data.
 */
async function withFallback(realCall, mockFactory) {
  try {
    const data = await realCall();
    reportConnection(true);
    return data;
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
    reportConnection(false);
    return mockFactory();
  }
}

export const API = {
  // System
  health: () => withFallback(() => get("/health"), () => ({ status: "ok", app: "bank-orchestrator", version: "demo" })),
  ready: () => withFallback(() => get("/ready"), () => mock.mockReady()),

  // Bilan — plan comptable, recomputed server-side on every GET
  bilan: (signal) => withFallback(() => get("/bilan", { signal }), () => mock.mockBilan()),

  // P1 — demo / lifecycle
  demoState: (signal) => withFallback(() => get("/p1/demo/state", { signal }), () => mock.mockDemoState()),
  demoTick: () => withFallback(() => post("/p1/demo/tick"), () => mock.mockDemoState()),
  demoReset: () => withFallback(() => post("/p1/demo/reset"), () => ({ status: "reset", state: { sim_month: 0, candidates: [], p4: { balances: { el_pool: 0, ula_buffer: 0, liquidity_reserve: 0, rp_pool: 0 }, mode: "conventional", track1_status: "clear", event_log_count: 0 } } })),
  demoSeed: () => withFallback(() => post("/p1/demo/seed"), () => ({ seeded: 6 })),
  demoProfiles: () => withFallback(() => get("/p1/demo/profiles"), () => mock.mockProfiles()),
  dataFiles: () => withFallback(() => get("/p1/demo/data-files"), () => mock.mockProfiles().map((p) => ({ filename: `${p.id}.json`, ...p }))),

  candidates: (statusFilter) =>
    withFallback(
      () => get(`/p1/candidates${statusFilter ? `?status=${statusFilter}` : ""}`),
      () => mock.mockCandidates().filter((c) => !statusFilter || c.status === statusFilter)
    ),
  candidate: (id) => withFallback(() => get(`/p1/candidates/${id}`), () => mock.mockCandidates().find((c) => c.id === id)),
  createCandidate: (payload) => post("/p1/candidates", payload),
  importCandidate: (payload) => post("/p1/candidates/import", payload),
  deleteCandidate: (id) => del(`/p1/candidates/${id}`),
  submitCandidate: (id) => post(`/p1/candidates/${id}/submit`),
  approveCandidate: (id, { approve, officer_id = "DEMO-OFFICER-1", officer_name = "Demo Officer", note }) =>
    post(`/p1/candidates/${id}/approve`, { approve, officer_id, officer_name, note }),
  disburseCandidate: (id) => post(`/p1/candidates/${id}/disburse`),

  // P3 — facilities / ledger
  facilities: (signal) => withFallback(() => get("/p3/facilities", { signal }), () => mock.mockFacilities()),
  facility: (id) => withFallback(() => get(`/p3/facilities/${id}`), () => mock.mockFacilities().find((f) => f.facility_id === id)),
  facilityAudit: (id) => withFallback(() => get(`/p3/audit/${id}`), () => mock.mockAudit(id)),
  ledger: () => withFallback(() => get("/p3/ledger"), () => []),
  postings: () => withFallback(() => get("/p3/postings"), () => []),
  reconcile: (tolerance = 0) => withFallback(() => get(`/p3/reconcile?tolerance=${tolerance}`), () => ({ within_tolerance: true, discrepancy: 0 })),

  // P4 — capital / buffer / veto
  p4Balances: () => withFallback(() => get("/p4/buffer/balances"), () => mock.mockDemoState().p4.balances),
  p4Adequacy: () => withFallback(() => get("/p4/pool/adequacy"), () => mock.mockPoolAdequacy()),
  p4Capital: () => withFallback(() => get("/p4/capital/snapshot"), () => mock.mockCapitalSnapshot()),
  p4Ifrs9: () => withFallback(() => get("/p4/ifrs9"), () => mock.mockIfrs9()),
  p4Mode: () => withFallback(() => get("/p4/mode"), () => mock.mockMode()),
  p4VetoNotifications: () => withFallback(() => get("/p4/veto/notifications"), () => mock.mockVetoNotifications()),
  // Governance release for a standing Track 1 veto. Deliberately NO mock
  // fallback: a failed lift must surface the real error, never a fake OK.
  p4LiftTrack1: (governanceRef) => post(`/p4/veto/lift-track1?governance_ref=${encodeURIComponent(governanceRef)}`),

  // Governance
  canonCurrent: () => withFallback(() => get("/governance/api/v1/canon/current"), () => ({ version_number: "V3.4", status: "RATIFIED" })),
  isAdaptiveActive: () => withFallback(() => get("/governance/api/v1/staging/is-adaptive-active"), () => ({ adaptive_active: false, current_mode: "CONVENTIONAL", fallback: "Conventional Mode is the permanent floor" })),
  vetoLog: () => withFallback(() => get("/governance/api/v1/vetoes"), () => mock.mockGovernanceVetoes()),
};

export const SSE_URL = "/p1/demo/events/sse";
