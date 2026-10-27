// Synthetic demo data for Facilities, Prudential, Bilan and Governance, used only while the API is offline.
// Facilities are derived from the pipeline's demo borrowers so the two screens agree.
import type {
  AuditRecord,
  Bilan,
  BilanConfig,
  Buffers,
  CapitalSnapshot,
  Facility,
  GovernanceState,
  Ifrs9Row,
  LedgerPosting,
  P4Event,
  PoolAdequacy,
  Posting,
  Reconcile,
  VetoNotification,
} from "./areas";
import type { BoardSnapshot } from "./types";

const day = (y: number, m: number, d: number) => new Date(Date.UTC(y, m - 1, d, 9, 0)).toISOString();

export interface FacilityDemo {
  facilities: Facility[];
  postings: Posting[];
  ledger: LedgerPosting[];
  audit: Record<string, AuditRecord[]>;
}

export function demoFacilities(board: BoardSnapshot): FacilityDemo {
  const live = board.candidates.filter((c) => c.facility_id && (c.status === "disbursed" || c.status === "approved"));
  const facilities: Facility[] = live.map((c) => ({
    facility_id: c.facility_id!,
    state:
      c.status === "approved"
        ? "ORIGINATED"
        : c.display_name === "Muttrah Fabrics"
          ? "DELINQUENT"
          : "DISBURSED",
    origination_packet_id: `pkt-${c.id}`,
    veto_frozen: board.frozenFacilityIds.includes(c.facility_id!),
    collateral_count: c.requested_amount > 70000 ? 2 : 1,
    updated_at: c.updated_at,
  }));
  facilities.push(
    { facility_id: "fac-090", state: "CLOSED", origination_packet_id: "pkt-090", veto_frozen: false, collateral_count: 1, updated_at: day(2026, 6, 30) },
    { facility_id: "fac-091", state: "CLOSED", origination_packet_id: "pkt-091", veto_frozen: false, collateral_count: 0, updated_at: day(2026, 8, 14) },
  );

  const postings: Posting[] = [];
  const audit: Record<string, AuditRecord[]> = {};
  let n = 0;
  for (const f of facilities) {
    const c = live.find((x) => x.facility_id === f.facility_id);
    const amount = c?.requested_amount ?? 50000;
    const rec = (event_type: string, timestamp: string): AuditRecord => ({
      record_id: `aud-${++n}`,
      facility_id: f.facility_id,
      event_type,
      timestamp,
      actor_reference: event_type === "ORIGINATED" ? "ADMIN-1" : "P3",
      p2_packet_version: "3.0",
      maturity_stage: "SANDBOX",
      brr_pd_grid_version: "BRRPD-2.5.1",
      p4_veto_status: f.veto_frozen ? "FROZEN" : "CLEAR",
    });
    const trail = [rec("ORIGINATED", day(2026, 3, 6))];
    if (f.state !== "ORIGINATED") {
      postings.push(
        { event_id: `evt-${++n}`, facility_id: f.facility_id, event_type: "PRINCIPAL_MOVEMENT", amount, currency: "USD", occurred_at: day(2026, 3, 8), routes_allocation_question_to_p4: false, memo: "Disbursement" },
        { event_id: `evt-${++n}`, facility_id: f.facility_id, event_type: "ORIGINATION_FEE", amount: Math.round(amount * 0.01), currency: "USD", occurred_at: day(2026, 3, 8), routes_allocation_question_to_p4: true, memo: null },
      );
      trail.push(rec("DISBURSED", day(2026, 3, 8)));
      const months = f.state === "CLOSED" ? 6 : f.state === "DELINQUENT" ? 3 : 5;
      for (let m = 0; m < months; m++) {
        const when = day(2026, 4 + m, 8);
        postings.push(
          { event_id: `evt-${++n}`, facility_id: f.facility_id, event_type: "SCHEDULED_REPAYMENT_PRINCIPAL", amount: Math.round(amount / 24), currency: "USD", occurred_at: when, routes_allocation_question_to_p4: false, memo: null },
          { event_id: `evt-${++n}`, facility_id: f.facility_id, event_type: "SCHEDULED_REPAYMENT_INTEREST", amount: Math.round(amount * 0.008), currency: "USD", occurred_at: when, routes_allocation_question_to_p4: true, memo: "Risk-premium slice to RP Pool" },
        );
        trail.push(rec("REPAYMENT", when));
      }
      if (f.state === "DELINQUENT") trail.push(rec("MARKED_DELINQUENT", day(2026, 8, 12)));
      if (f.state === "CLOSED") trail.push(rec("CLOSED", f.updated_at));
    }
    audit[f.facility_id] = trail;
  }
  const ledger: LedgerPosting[] = postings.map((p, i) => ({
    posting_id: `cb-${1000 + i}`,
    source_event_id: p.event_id,
    facility_id: p.facility_id,
    amount: p.amount,
    currency: p.currency,
    posted_at: p.occurred_at,
  }));
  return { facilities, postings, ledger, audit };
}

export function demoReconcile(postings: Posting[], ledger: LedgerPosting[]): Reconcile {
  const p3 = postings.reduce((s, p) => s + p.amount, 0);
  const cb = ledger.reduce((s, p) => s + p.amount, 0);
  return { p3_event_total: p3, core_banking_total: cb, discrepancy: p3 - cb, tolerance: 0, within_tolerance: p3 === cb, unmatched_p3_event_ids: [] };
}

export interface PrudentialDemo {
  buffers: Buffers;
  capital: CapitalSnapshot;
  adequacy: PoolAdequacy;
  ifrs9: Ifrs9Row[];
  events: P4Event[];
  notifications: VetoNotification[];
}

export function demoPrudential(board: BoardSnapshot): PrudentialDemo {
  const frozen = board.veto.track1_frozen;
  const live = board.candidates.filter((c) => c.status === "disbursed");
  return {
    buffers: { el_pool: 18400, ula_buffer: 42000, liquidity_reserve: 120000, rp_pool: 9650 },
    capital: {
      tier_d_over_rwa: frozen ? 0.108 : 0.142,
      portfolio_el: 0.016,
      guarantees_granted_over_received: 0.86,
      tier_d_amount: frozen ? 46400 : 61000,
      rwa: 430000,
      budgeted_loss: 8600,
      el_pool_balance: 18400,
      given_book: 180000,
      received_book: 210000,
      tier_d_floor: 0.12,
      budgeted_loss_ratio: 0.02,
    },
    adequacy: { received: 210000, required: 240000, status: "SHORTFALL", shortfall_amount: 30000 },
    ifrs9: live.map((c) => ({
      facility_ref: c.facility_id!,
      stage: c.display_name === "Muttrah Fabrics" ? 2 : 1,
      ead: c.requested_amount,
      ecl: Math.round(c.requested_amount * (c.p2_pd ?? 0.02) * 0.45 * (c.display_name === "Muttrah Fabrics" ? 2.6 : 1)),
      el: Math.round(c.requested_amount * (c.p2_pd ?? 0.02) * 0.45),
    })),
    events: [
      { type: "staging_signal", payload: { facility_ref: live.find((c) => c.display_name === "Muttrah Fabrics")?.facility_id, stage: 2 }, occurred_at: day(2026, 8, 12) },
      { type: "adequacy_shortfall", payload: { shortfall_amount: 30000 }, occurred_at: day(2026, 9, 1) },
      { type: "risk_premium_accrual", payload: { amount: 1180 }, occurred_at: day(2026, 9, 8) },
    ],
    notifications: [
      { event: "veto_freeze", track: "track1", triggers: ["portfolio_el"], governance_ref: null },
      { event: "veto_lift", track: "track1", triggers: ["portfolio_el"], governance_ref: "AUTO-LIFT-SUSTAINED-CLEAN" },
      ...(frozen ? [{ event: "veto_freeze", track: "track1", triggers: ["tier_d_over_rwa"], governance_ref: null }] : []),
    ],
  };
}

export function demoBilan(): Bilan {
  const actif = [
    { compte: "27", libelle: "Prêts aux clients (encours)", montant: 304000 },
    { compte: "29", libelle: "Dépréciations ECL (EL Pool)", montant: -18400 },
    { compte: "46", libelle: "Autres créances", montant: 4200 },
    { compte: "512", libelle: "Banque · trésorerie", montant: 155000 },
  ];
  const passif = [
    { compte: "101", libelle: "Capital Tier D", montant: 61000 },
    { compte: "12", libelle: "Résultat de l'exercice", montant: 9650 },
    { compte: "15", libelle: "Provisions · ULA Buffer", montant: 42000 },
    { compte: "164", libelle: "Emprunts · Tier C", montant: 230000 },
    { compte: "165", libelle: "Dépôts clients", montant: 102150 },
  ];
  const sum = (l: { montant: number }[]) => l.reduce((s, x) => s + x.montant, 0);
  return {
    actif,
    passif,
    totaux: { actif: sum(actif), passif: sum(passif) },
    ecart: sum(actif) - sum(passif),
    balanced: sum(actif) === sum(passif),
    hors_bilan: {
      garanties_recues: 210000,
      garanties_consenties: 180000,
      niveau_requis_garanties: 240000,
      liquidity_reserve: 120000,
      rwa: 430000,
    },
    mouvements: { decaisses: 304000, remboursements: 61800, interets: 9650, frais: 3040, sinistres: 0 },
    checks: [
      { name: "Actif = Passif", ok: true },
      { name: "Dépréciations = EL Pool", ok: true },
      { name: "Trésorerie d'ouverture configurée", ok: true },
    ],
    reliable: true,
    warnings: [],
    as_of: new Date().toISOString(),
  };
}

export function demoBilanConfig(): BilanConfig {
  return {
    immobilisations: 0,
    autres_creances: 4200,
    apport_reserve: 0,
    resultat_anterieur: 0,
    sid: 0,
    tier_c: 230000,
    autres_emprunts: 0,
    depots_clients: 102150,
    autres_dettes: 0,
    tresorerie_ouverture: 155000,
    tresorerie_ouverture_configured: true,
  };
}

export function demoGovernance(board: BoardSnapshot): GovernanceState {
  return {
    canon: {
      id: "canon-34",
      version_number: "3.4",
      name: "Orchestrator Canon",
      status: "RATIFIED",
      ratified_at: day(2026, 9, 30),
      ratification_instrument: "RI-4",
      is_current: true,
      change_summary: "Two-track veto semantics; Pillar 3 never sees a veto event.",
    },
    mode: "CONVENTIONAL",
    stage: 1,
    gates: [
      { id: "g1", gate_label: "G1", status: "BLOCKED", criteria: "CASS methodology ratified and back-tested in sandbox", cleared_at: null, cleared_by: null, notes: "Waiting on P-11" },
      { id: "g2", gate_label: "G2", status: "CLEARED", criteria: "Core-banking reconciliation within tolerance for 3 months", cleared_at: day(2026, 7, 1), cleared_by: "Governance Committee", notes: null },
      { id: "g3", gate_label: "G3", status: "OPEN", criteria: "Guarantee pool adequacy above required level", cleared_at: null, cleared_by: null, notes: null },
    ],
    pending: [
      { id: "p11", item_number: "P-11", title: "CASS scoring methodology", description: "Adaptive scoring methodology is not ratified; Adaptive Mode stays sandbox-only.", category: "METHODOLOGY", status: "OPEN", priority: "HIGH", assigned_to: "Risk Committee", registered_at: day(2026, 5, 2), resolved_at: null, resolution_notes: null, governance_reference: null },
      { id: "p12", item_number: "P-12", title: "Track 1 thresholds without a number", description: "Some Track 1 triggers are named but have no settled threshold; they are reported as unmonitored.", category: "PRUDENTIAL", status: "OPEN", priority: "MEDIUM", assigned_to: null, registered_at: day(2026, 6, 18), resolved_at: null, resolution_notes: null, governance_reference: null },
      { id: "p08", item_number: "P-08", title: "Bilan opening treasury", description: "Opening treasury value for the balance sheet.", category: "FINANCE", status: "RESOLVED", priority: "LOW", assigned_to: "Finance", registered_at: day(2026, 3, 1), resolved_at: day(2026, 4, 10), resolution_notes: "Set from the founding capital transfer.", governance_reference: "RI-3" },
    ],
    vetoes: [
      { id: "v3", event_number: 3, track: "TRACK_2", scope: "FACILITY", facility_id: board.frozenFacilityIds[0] ?? null, pillar_4_signal: "Collateral concentration above policy limit", p2_packet_action: "WITHHELD", orchestrator_notified_at: day(2026, 9, 3), governance_review_status: "UNDER_REVIEW", restart_authorized_at: null, restart_authorized_by: null, notes: null },
      { id: "v2", event_number: 2, track: "TRACK_1", scope: "PORTFOLIO", facility_id: null, pillar_4_signal: "Guarantee shortfall with ratio breach", p2_packet_action: "WITHHELD", orchestrator_notified_at: day(2026, 5, 20), governance_review_status: "RESOLVED", restart_authorized_at: day(2026, 5, 27), restart_authorized_by: "Governance Committee", notes: "Replacement pledges admitted." },
    ],
  };
}
