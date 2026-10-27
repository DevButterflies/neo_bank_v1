// Pillar 3, Pillar 4, bilan and governance endpoints (DOCS/neo-bank-api-playbook.pdf).
import { API_BASE, ApiError } from "./client";

// ---------- Pillar 3 ----------
export interface Facility {
  facility_id: string;
  state: string;
  origination_packet_id: string | null;
  veto_frozen: boolean;
  collateral_count: number;
  updated_at: string;
}

export interface P2Packet {
  packet_id: string;
  facility_id: string;
  status: string;
  maturity_stage: string;
  brr_pd_grid_version: string;
  collateral_track: string;
  packet_version: string;
  officer_confirmed: boolean;
  officer_id: string | null;
  human_authorised_for_workout: boolean;
  issued_at: string;
}

export interface AuditRecord {
  record_id: string;
  facility_id: string | null;
  event_type: string;
  timestamp: string;
  actor_reference: string;
  p2_packet_version: string | null;
  maturity_stage: string | null;
  brr_pd_grid_version: string | null;
  p4_veto_status: string | boolean | null;
}

export interface Posting {
  event_id: string;
  facility_id: string;
  event_type: string;
  amount: number;
  currency: string;
  occurred_at: string;
  routes_allocation_question_to_p4: boolean;
  memo: string | null;
}

export interface LedgerPosting {
  posting_id: string;
  source_event_id: string;
  facility_id: string;
  amount: number;
  currency: string;
  posted_at: string;
}

export interface Reconcile {
  p3_event_total: number;
  core_banking_total: number;
  discrepancy: number;
  tolerance: number;
  within_tolerance: boolean;
  unmatched_p3_event_ids: string[];
}

/** Lifecycle actions; each needs the facility's Pillar 2 packet as its body. */
export type FacilityAction = "repayment" | "mark-delinquent" | "mark-default" | "restructure" | "recovery" | "close";

// ---------- Pillar 4 ----------
export interface Buffers {
  el_pool: number;
  ula_buffer: number;
  liquidity_reserve: number;
  rp_pool: number;
}

export interface CapitalSnapshot {
  tier_d_over_rwa: number | null;
  portfolio_el: number | null;
  guarantees_granted_over_received: number | null;
  tier_d_amount: number | null;
  rwa: number | null;
  budgeted_loss: number | null;
  el_pool_balance: number | null;
  given_book: number | null;
  received_book: number | null;
  tier_d_floor: number | null;
  budgeted_loss_ratio: number | null;
}

export interface PoolAdequacy {
  received: number;
  required: number;
  status: string;
  shortfall_amount: number;
}

export interface Ifrs9Row {
  facility_ref: string;
  stage: number;
  ecl: number | null;
  ead: number | null;
  el: number | null;
}

export interface P4Event {
  type: string;
  payload: Record<string, unknown> | null;
  occurred_at: string | null;
}

/** One freeze or lift notified to the Orchestrator (`GET /p4/veto/notifications`). */
export interface VetoNotification {
  event: string;
  track: string;
  triggers: string[];
  governance_ref: string | null;
}

export interface Ruling {
  ruling_ref: string;
  rule_type: string;
  signed_by: string;
  detail: string;
}

// ---------- bilan ----------
export interface BilanLine {
  compte: string;
  libelle: string;
  montant: number;
}

export interface Bilan {
  actif: BilanLine[];
  passif: BilanLine[];
  totaux: { actif: number; passif: number };
  ecart: number;
  balanced: boolean;
  hors_bilan: Record<string, number | null>;
  mouvements: Record<string, unknown>;
  checks: { name?: string; ok?: boolean; passed?: boolean; detail?: string; message?: string }[];
  reliable: boolean;
  warnings: string[];
  as_of: string;
}

export type BilanConfig = Record<string, number | boolean>;

// ---------- governance ----------
export interface CanonVersion {
  id: string;
  version_number: string;
  name: string;
  status: string;
  ratified_at: string | null;
  ratification_instrument: string | null;
  is_current: boolean;
  change_summary: string | null;
}

export interface Gate {
  id: string;
  gate_label: string;
  status: string;
  criteria: string | null;
  cleared_at: string | null;
  cleared_by: string | null;
  notes: string | null;
}

export interface PendingItem {
  id: string;
  item_number: string | null;
  title: string | null;
  description: string;
  category: string;
  status: string;
  priority: string | null;
  assigned_to: string | null;
  registered_at: string;
  resolved_at: string | null;
  resolution_notes: string | null;
  governance_reference: string | null;
}

export interface VetoEvent {
  id: string;
  event_number: number;
  track: string;
  scope: string | null;
  facility_id: string | null;
  pillar_4_signal: string;
  p2_packet_action: string;
  orchestrator_notified_at: string;
  governance_review_status: string;
  restart_authorized_at: string | null;
  restart_authorized_by: string | null;
  notes: string | null;
}

export interface GovernanceState {
  canon: CanonVersion | null;
  mode: string;
  stage: number | null;
  gates: Gate[];
  pending: PendingItem[];
  vetoes: VetoEvent[];
}

// ---------- transport ----------
async function call<T>(path: string, init?: RequestInit & { query?: Record<string, string | number | boolean | null | undefined> }): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  for (const [k, v] of Object.entries(init?.query ?? {})) if (v != null && v !== "") url.searchParams.set(k, String(v));
  const res = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = body.detail.map((d: { msg?: string }) => d.msg ?? String(d)).join("; ");
    } catch {
      /* empty body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const asArray = <T>(v: unknown, key?: string): T[] =>
  Array.isArray(v) ? (v as T[]) : key && v && typeof v === "object" && Array.isArray((v as Record<string, unknown>)[key]) ? ((v as Record<string, unknown>)[key] as T[]) : [];

/** /p4/ifrs9 is an untyped object in the schema; accept a list or a map keyed by facility. */
function toIfrs9(v: unknown): Ifrs9Row[] {
  const rows = Array.isArray(v) ? v : v && typeof v === "object" ? Object.entries(v as Record<string, unknown>).map(([k, r]) => ({ facility_ref: k, ...(r as object) })) : [];
  return rows
    .filter((r): r is Record<string, unknown> => !!r && typeof r === "object")
    .map((r) => ({
      facility_ref: String(r.facility_ref ?? r.facility_id ?? ""),
      stage: Number(String(r.stage ?? r.ifrs9_stage ?? 1).replace(/\D/g, "")) || 1,
      ecl: typeof r.ecl === "number" ? r.ecl : null,
      ead: typeof r.ead === "number" ? r.ead : null,
      el: typeof r.el === "number" ? r.el : null,
    }));
}

export const p3 = {
  facilities: () => call<Facility[]>("/p3/facilities"),
  packets: () => call<P2Packet[]>("/p3/packets"),
  audit: (id: string) => call<AuditRecord[]>(`/p3/audit/${id}`),
  postings: () => call<Posting[]>("/p3/postings"),
  ledger: () => call<LedgerPosting[]>("/p3/ledger"),
  reconcile: () => call<Reconcile>("/p3/reconcile"),
  async act(action: FacilityAction, facilityId: string, params: Record<string, string | number>, authoriseWorkout = false) {
    const packets = await p3.packets();
    const packet = packets.filter((p) => p.facility_id === facilityId).at(-1);
    if (!packet) throw new ApiError(409, "No confirmed Pillar 2 packet is recorded for this facility.");
    const body = { ...packet, human_authorised_for_workout: authoriseWorkout || packet.human_authorised_for_workout };
    return call<unknown>(`/p3/${action}`, { method: "POST", body: JSON.stringify(body), query: { facility_id: facilityId, ...params } });
  },
};

export const p4 = {
  buffers: () => call<Buffers>("/p4/buffer/balances"),
  capital: () => call<CapitalSnapshot>("/p4/capital/snapshot"),
  adequacy: () => call<PoolAdequacy>("/p4/pool/adequacy"),
  ifrs9: async () => toIfrs9(await call<unknown>("/p4/ifrs9")),
  events: async () => asArray<P4Event>(await call<unknown>("/p4/events")),
  notifications: async () => asArray<VetoNotification>(await call<unknown>("/p4/veto/notifications")),
  liftTrack1: (governance_ref: string) => call<unknown>("/p4/veto/lift-track1", { method: "POST", query: { governance_ref } }),
  activateAdaptive: (r: Ruling) => call<unknown>("/p4/mode/activate", { method: "POST", body: JSON.stringify(r) }),
  fallbackConventional: (r: Ruling) => call<unknown>("/p4/mode/fallback", { method: "POST", body: JSON.stringify(r) }),
};

export const bilanApi = {
  get: () => call<Bilan>("/bilan"),
  config: () => call<BilanConfig>("/bilan/config"),
  saveConfig: (patch: Record<string, number>, token: string) =>
    call<BilanConfig>("/bilan/config", { method: "PUT", body: JSON.stringify(patch), headers: { "X-Admin-Token": token } }),
};

const G = "/governance/api/v1";
export const governance = {
  async state(): Promise<GovernanceState> {
    const [canon, mode, stage, gates, pending, vetoes] = await Promise.all([
      call<CanonVersion>(`${G}/canon/current`).catch(() => null),
      call<Record<string, unknown>>(`${G}/staging/mode`),
      call<Record<string, unknown>>(`${G}/staging/stage`),
      call<unknown>(`${G}/staging/gates`),
      call<unknown>(`${G}/pending`),
      call<unknown>(`${G}/vetoes`),
    ]);
    return {
      canon,
      mode: String(mode.mode ?? mode.current_mode ?? "–"),
      stage: typeof stage.current_stage === "number" ? stage.current_stage : null,
      gates: asArray<Gate>(gates),
      pending: asArray<PendingItem>(pending),
      vetoes: asArray<VetoEvent>(vetoes),
    };
  },
  resolvePending: (id: string, resolution_notes: string, governance_reference: string | null) =>
    call<PendingItem>(`${G}/pending/${id}/resolve`, { method: "POST", body: JSON.stringify({ resolution_notes, governance_reference }) }),
  clearGate: (label: string) => call<Gate>(`${G}/staging/gates/${encodeURIComponent(label)}/clear`, { method: "POST" }),
  blockGate: (label: string, notes: string) =>
    call<Gate>(`${G}/staging/gates/${encodeURIComponent(label)}/block`, { method: "POST", query: { notes } }),
};
