// Fallback sample data, shaped exactly like the real orchestrator responses
// documented in the API reference. Used ONLY when a real request fails (e.g.
// the backend isn't running yet) so the UI can still be reviewed end to end.
// Every shape here mirrors a real example payload from the spec — nothing is
// invented beyond the six seeded demo profiles the backend itself ships.

const PROFILES = [
  { id: "ahmed", first_name: "Ahmed", last_name: "— Corner Shop", tier: "small", outcome: "paid", requested_amount: 8000, disbursed: 6000, tenure: 10 },
  { id: "yusuf", first_name: "Yusuf", last_name: "— Street Vendor", tier: "small", outcome: "default", requested_amount: 5000, disbursed: 4000, tenure: 8 },
  { id: "layla", first_name: "Layla", last_name: "— Textile Exporter", tier: "medium", outcome: "paid", requested_amount: 32000, disbursed: 22000, tenure: 18 },
  { id: "omar", first_name: "Omar", last_name: "— Fruit Vendor", tier: "medium", outcome: "default", requested_amount: 15000, disbursed: 12000, tenure: 12 },
  { id: "nadia", first_name: "Nadia", last_name: "— Catering Service", tier: "good", outcome: "paid", requested_amount: 45000, disbursed: 35000, tenure: 24 },
  { id: "fatima", first_name: "Fatima", last_name: "— General Store", tier: "good", outcome: "default", requested_amount: 25000, disbursed: 20000, tenure: 15 },
];

function makeRepayments(months, amount) {
  const principalPerMonth = amount / months;
  return Array.from({ length: months }, (_, i) => ({
    month: i + 1,
    principal: Math.round(principalPerMonth),
    interest: Math.round(amount * 0.01 * (1 - i / months)),
  }));
}

export function mockCandidates() {
  return PROFILES.map((p, idx) => {
    const isNew = idx === 5;
    const isScored = idx === 4;
    const isApproved = idx === 3;
    const isDisbursed = idx <= 2;
    const status = isNew ? "new" : isScored ? "scored" : isApproved ? "approved" : isDisbursed ? (p.outcome === "default" && idx === 1 ? "defaulted" : "disbursed") : "new";
    const paidMonths = status === "disbursed" ? Math.floor(p.tenure / 3) : status === "defaulted" ? Math.floor(p.tenure / 3) : 0;
    const repayments = makeRepayments(p.tenure, p.disbursed);
    const paidPrincipal = repayments.slice(0, paidMonths).reduce((s, r) => s + r.principal, 0);
    return {
      id: p.id,
      display_name: `${p.first_name} ${p.last_name}`,
      seed_profile: p.id,
      status,
      requested_amount: p.requested_amount,
      requested_tenure_months: p.tenure,
      monthly_salary: 1200 + idx * 700,
      national_id: null,
      facility_id: status === "new" || status === "scored" ? null : `FAC-${p.id.toUpperCase().slice(0, 8)}`,
      application_id: status === "new" ? null : `APP-${p.id.toUpperCase()}-${100 + idx}`,
      p2_zone: status === "new" ? null : idx % 3 === 0 ? "AUTO_APPROVE" : idx % 3 === 1 ? "AUGMENTED_DECISION" : "MANUAL_REVIEW",
      p2_brr: status === "new" ? null : 2 + idx,
      p2_pd: status === "new" ? null : 0.008 + idx * 0.01,
      p2_lgd: status === "new" ? null : 0.35 + idx * 0.02,
      p2_ead: status === "new" ? null : p.disbursed,
      p2_el: status === "new" ? null : Math.round(p.disbursed * (0.008 + idx * 0.01) * (0.35 + idx * 0.02)),
      outstanding: ["disbursed", "delinquent", "defaulted"].includes(status) ? p.disbursed - paidPrincipal : null,
      sim_month: paidMonths,
      payments_made: paidMonths,
      defaulted: status === "defaulted",
      closed: false,
      payment_behavior: {
        outcome: p.outcome,
        facility_amount: p.requested_amount,
        disbursed: p.disbursed,
        currency: "USD",
        tenure_months: p.tenure,
        repayments,
        delinquent_month: p.outcome !== "paid" ? Math.floor(p.tenure / 3) : null,
        default_month: p.outcome === "default" ? Math.floor(p.tenure / 3) + 1 : null,
        recovered_amount: p.outcome === "default" ? Math.round(p.disbursed * 0.2) : 0,
        interest_rate_bps: 900 + idx * 50,
      },
      created_at: new Date(Date.now() - idx * 86400000).toISOString(),
      updated_at: new Date().toISOString(),
    };
  });
}

export function mockDemoState() {
  const candidates = mockCandidates();
  return {
    sim_month: 4,
    candidates,
    p4: {
      balances: { el_pool: 4200, ula_buffer: 9800, liquidity_reserve: 62000, rp_pool: 3100 },
      mode: "conventional",
      track1_status: "clear",
      event_log_count: 14,
    },
  };
}

export function mockCapitalSnapshot() {
  return {
    tier_d_over_rwa: 0.164,
    portfolio_el: 0.0138,
    guarantees_granted_over_received: 0.71,
    tier_d_amount: 210000,
    rwa: 1280000,
    budgeted_loss: 0.02,
    el_pool_balance: 4200,
    given_book: 96000,
    received_book: 135000,
    tier_d_floor: 0.12,
    budgeted_loss_ratio: 0.02,
  };
}

export function mockPoolAdequacy() {
  return { required_amount: 120000, received: 135000, adequate: true, headroom: 15000 };
}

export function mockIfrs9() {
  return {
    "FAC-AHMED": { stage: 1, ecl: 210, ead: 6000, el: 45 },
    "FAC-YUSUF": { stage: 3, ecl: 1400, ead: 4000, el: 900 },
    "FAC-LAYLA": { stage: 1, ecl: 380, ead: 22000, el: 210 },
  };
}

export function mockMode() {
  return { mode: "CONVENTIONAL", adaptive: false, conventional: true };
}

export function mockFacilities() {
  return mockCandidates()
    .filter((c) => c.facility_id)
    .map((c) => ({
      facility_id: c.facility_id,
      state: c.status === "defaulted" ? "DEFAULT" : c.status === "disbursed" ? "REPAYING" : "APPROVED",
      origination_packet_id: `PKT-${c.id}`,
      collateral_count: c.id === "layla" ? 1 : 0,
      veto_frozen: false,
      updated_at: new Date().toISOString(),
    }));
}

export function mockAudit(facilityId) {
  const base = new Date();
  const step = (mins, type, state) => ({
    record_id: `AUD-${Math.random().toString(16).slice(2, 8)}`,
    facility_id: facilityId,
    event_type: type,
    timestamp: new Date(base.getTime() - mins * 60000).toISOString(),
    actor_reference: type === "ORIGINATION_RECORDED" ? "DEMO-OFFICER-1" : "SYSTEM",
    p2_packet_version: "v1",
    maturity_stage: "SANDBOX",
    brr_pd_grid_version: "BRR-GRID-2026-04",
    collateral_track: "TRACK_1_CLASSICAL",
    p4_veto_status: "TRACK_1_PORTFOLIO:CLEAR; TRACK_2_FACILITY:CLEAR",
    posting_routing_flag: type,
    core_banking_confirmed: true,
    resulting_state: state,
    collateral_reference: null,
    guarantee_linkage: null,
  });
  return [
    step(300, "ORIGINATION_RECORDED", "APPROVED"),
    step(240, "DISBURSEMENT", "ACTIVE"),
    step(180, "REPAYMENT", "REPAYING"),
    step(120, "REPAYMENT", "REPAYING"),
    step(60, "REPAYMENT", "REPAYING"),
  ];
}

export function mockVetoNotifications() {
  return [];
}

export function mockGovernanceVetoes() {
  return [];
}

export function mockReady() {
  return { status: "ok", checks: { p3_restart_ok: true, p4_restart_ok: true } };
}

/** Shape of GET /bilan (orchestrator), mirrored on the real seeded figures so
 *  the screen reads identically with or without a backend. */
export function mockBilan() {
  const actif = [
    { compte: "2180", libelle: "Immobilisations", montant: 0 },
    { compte: "4110", libelle: "Crédits clients (encours brut)", montant: 46600 },
    { compte: "4190", libelle: "Autres créances", montant: 0 },
    { compte: "5120", libelle: "Trésorerie", montant: 56249.36 },
  ];
  const passif = [
    { compte: "1010", libelle: "Capital social (Tier D)", montant: 100000 },
    { compte: "1180", libelle: "Réserve d'apport", montant: 0 },
    { compte: "1190", libelle: "Résultat cumulé", montant: -1443.56 },
    { compte: "4280", libelle: "Provisions pour risques (ECL IFRS 9)", montant: 4292.92 },
    { compte: "2670", libelle: "Dettes financières", montant: 0 },
    { compte: "4210", libelle: "Dépôts des clients", montant: 0 },
    { compte: "4260", libelle: "Autres dettes", montant: 0 },
  ];
  const total = (lines) => Math.round(lines.reduce((s, l) => s + l.montant, 0) * 100) / 100;
  const totaux = { actif: total(actif), passif: total(passif) };
  return {
    actif,
    passif,
    totaux,
    ecart: Math.round((totaux.actif - totaux.passif) * 100) / 100,
    balanced: true,
    checks: [
      { id: "BALANCE", ok: true, detail: "actif 102849.36 vs passif 102849.36 (ecart 0.00)" },
      { id: "OPENING_CASH_INDEPENDENT", ok: true, detail: "opening cash configured at 100000.00" },
      { id: "NO_OVERPAYMENT", ok: true, detail: "no facility repaid more than it drew" },
      { id: "CLOSED_FACILITIES_ZERO_BALANCE", ok: true, detail: "every closed facility is fully written down" },
      { id: "NO_UNCLASSIFIED_LOSS_EVENTS", ok: true, detail: "every non-zero loss event is classified" },
      { id: "NO_NEGATIVE_RECEIVABLE", ok: true, detail: "4110 = 46600.00" },
    ],
    reliable: true,
    warnings: [],
    mouvements: {
      decaisses: 99000,
      remboursements: 52400,
      interets: 3994,
      frais: 0,
      radiations: 0,
      sinistres: 0,
      recouvrements: 0,
      non_classes: 0,
      par_facilite: {},
      ecl_total: 5437.56,
      el_pool: 4292.92,
      ecl_consomme: 0,
      tresorerie_ouverture: 100000,
    },
    hors_bilan: {
      ula_buffer: 0,
      liquidity_reserve: 0,
      rp_pool: 3994,
      el_pool: 4292.92,
      rwa: 109150,
      tier_d_over_rwa: 0.9162,
      garanties_consenties: 99000,
      garanties_recues: 0,
      niveau_requis_garanties: 0,
    },
    sources: { p3_events: 35, p4_facilities: 6 },
    as_of: new Date().toISOString(),
  };
}

export function mockProfiles() {
  return PROFILES.map((p) => ({
    id: p.id,
    data_tier: p.tier,
    outcome: p.outcome,
    tagline: `${p.tier} data file · ${p.outcome === "paid" ? "repays in full" : "defaults mid-term"}`,
    requested_amount: p.requested_amount,
    disbursed_amount: p.disbursed,
  }));
}
