import type {
  ApprovalDecision,
  BoardSnapshot,
  Candidate,
  CandidateCreate,
  FlowResult,
  ModeState,
  VetoState,
} from "./types";

/** Same origin in a production build (the orchestrator serves the app); the local orchestrator in dev. */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

/** Error carrying the backend's `{"detail": ...}` body and the HTTP status. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }

  /** 409 = prudential veto, state-machine conflict or governance PENDING. */
  get isConflict() {
    return this.status === 409;
  }
}

function readDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // 422 uses FastAPI's array form: [{loc, msg, type}]
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : String(d)))
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* empty body */
    }
    throw new ApiError(res.status, readDetail(body, `${res.status} ${res.statusText}`));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  listCandidates: () => request<{ candidates: Candidate[] }>("/p1/candidates"),
  createCandidate: (body: CandidateCreate) =>
    post<{ candidate: Candidate }>("/p1/candidates", body),
  submit: (id: string) => post<FlowResult>(`/p1/candidates/${id}/submit`),
  decide: (id: string, body: ApprovalDecision) => post<FlowResult>(`/p1/candidates/${id}/approve`, body),
  disburse: (id: string, amount: number | null, currency = "USD") =>
    post<FlowResult>(`/p1/candidates/${id}/disburse`, { amount, currency }),
  demoState: () => request<Record<string, unknown>>("/p1/demo/state"),
  tick: () => post<{ tick: Record<string, unknown>; state: Record<string, unknown> }>("/p1/demo/tick"),
  seed: () => post<{ seeded: number }>("/p1/demo/seed"),
  reset: () => post<{ status: string }>("/p1/demo/reset"),
  veto: () => request<VetoState>("/p4/veto/consult"),
  mode: () => request<ModeState>("/p4/mode"),
  facilities: () =>
    request<{ facility_id: string; state: string; veto_frozen: boolean }[]>("/p3/facilities"),
};

/** Reads the month out of /p1/demo/state without assuming its exact shape. */
function monthFrom(state: Record<string, unknown>): number {
  for (const key of ["sim_month", "month", "current_month", "tick"]) {
    const v = state[key];
    if (typeof v === "number") return v;
  }
  return 0;
}

export async function loadBoard(): Promise<BoardSnapshot> {
  const [{ candidates }, state, veto, mode, facilities] = await Promise.all([
    api.listCandidates(),
    api.demoState(),
    api.veto(),
    api.mode(),
    api.facilities(),
  ]);
  return {
    month: monthFrom(state),
    candidates,
    veto,
    mode,
    closedFacilities: facilities.filter((f) => f.state.toLowerCase().includes("closed")).length,
    frozenFacilityIds: facilities.filter((f) => f.veto_frozen).map((f) => f.facility_id),
  };
}

export function subscribeBoard(onChange: () => void): () => void {
  const source = new EventSource(`${API_BASE}/p1/demo/events/sse`);
  source.onmessage = (event) => {
    // keep-alive frames are an empty {}
    if (event.data && event.data !== "{}") onChange();
  };
  return () => source.close();
}
