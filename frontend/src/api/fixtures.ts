// Synthetic demo data, used only when the API at API_BASE is unreachable.
// Every borrower below is invented; the UI labels this source as demo data.
import type { BoardSnapshot, Candidate, CandidateCreate, CandidateStatus, DecisioningZone } from "./types";

let seq = 100;
const iso = (day: number) => new Date(Date.UTC(2026, 2, day, 9, 30)).toISOString();

function make(
  first: string,
  last: string,
  product: string,
  amount: number,
  status: CandidateStatus,
  score?: { brr: number; pd: number; zone: DecisioningZone },
  extra: Partial<Candidate> = {},
): Candidate {
  const id = `cand-${++seq}`;
  return {
    id,
    display_name: `${first} ${last}`,
    first_name: first,
    last_name: last,
    name_ar: null,
    gender: "male",
    age: 41,
    national_id: null,
    phone: null,
    city: "Muscat",
    employer_name: `${first} ${last}`,
    employer_type: "self_employed",
    employment_years: 6,
    job_title: "Owner",
    monthly_salary: Math.round(amount / 9),
    product,
    requested_amount: amount,
    requested_tenure_months: 24,
    status,
    submitted_at: score ? iso(4) : null,
    scored_at: score ? iso(4) : null,
    approved_at: status === "approved" || status === "disbursed" ? iso(6) : null,
    originated_at: status === "approved" || status === "disbursed" ? iso(6) : null,
    disbursed_at: status === "disbursed" ? iso(8) : null,
    facility_id: status === "approved" || status === "disbursed" ? `fac-${seq}` : null,
    p2_brr: score?.brr ?? null,
    p2_pd: score?.pd ?? null,
    p2_zone: score?.zone ?? null,
    p2_packet_status: score ? "PROVISIONAL" : null,
    approval_note: null,
    approved_by: status === "approved" || status === "disbursed" ? "Admin" : null,
    // spread intake over the first months of 2026 so date filters have something to do
    created_at: new Date(Date.UTC(2026, 0, 5, 9, 30) + (seq - 100) * 5 * 86_400_000).toISOString(),
    updated_at: iso(8),
    ...extra,
  };
}

export function fixtureBoard(): BoardSnapshot {
  const candidates: Candidate[] = [
    make("Al Hinai", "Bakery", "working_capital_line", 48000, "new"),
    make("Sfax", "Olive Press", "term_loan", 120000, "new"),
    make("Nour", "Textiles", "invoice_discounting", 22500, "new"),
    make("Bayt", "Logistics", "supply_chain_finance", 75000, "new"),
    make("Ruwi", "Print House", "growth_loan", 60000, "new"),
    make("Kairouan", "Ceramics", "working_capital_line", 90000, "submitted", { brr: 4, pd: 0.021, zone: "AUTO_APPROVE" }),
    make("Seeb", "Cold Chain", "term_loan", 140000, "submitted", { brr: 6, pd: 0.048, zone: "AUGMENTED_DECISION" }),
    make("Medina", "Spices", "invoice_discounting", 35000, "submitted", { brr: 8, pd: 0.096, zone: "MANUAL_REVIEW" }),
    make("Dhofar", "Agri Tools", "growth_loan", 58000, "submitted", { brr: 5, pd: 0.03, zone: "AUTO_APPROVE" }),
    make("Sohar", "Marine Parts", "growth_loan", 82000, "approved", { brr: 5, pd: 0.032, zone: "AUTO_APPROVE" }),
    make("Bizerte", "Fresh", "supply_chain_finance", 40000, "approved", { brr: 3, pd: 0.012, zone: "AUTO_APPROVE" }),
    make("Gabès", "Solar Fit", "term_loan", 110000, "disbursed", { brr: 4, pd: 0.022, zone: "AUTO_APPROVE" }),
    make("Muttrah", "Fabrics", "working_capital_line", 52000, "disbursed", { brr: 7, pd: 0.071, zone: "AUGMENTED_DECISION" }),
    make("Tozeur", "Tours", "growth_loan", 64000, "disbursed", { brr: 4, pd: 0.024, zone: "AUTO_APPROVE" }),
    make("Barka", "Feeds", "term_loan", 78000, "disbursed", { brr: 5, pd: 0.035, zone: "AUTO_APPROVE" }),
    make("Quick Mobile", "Repair", "working_capital_line", 18000, "rejected", { brr: 9, pd: 0.14, zone: "MANUAL_REVIEW" }, {
      approval_note: "Cash flow too thin for the requested tenor.",
      approved_by: "Admin",
    }),
  ];
  const barka = candidates.find((c) => c.display_name === "Barka Feeds")!;
  // ?scenario=veto shows the demo bank with a standing Track 1 freeze
  const vetoScenario = new URLSearchParams(window.location.search).get("scenario") === "veto";
  return {
    month: 7,
    candidates,
    closedFacilities: 2,
    frozenFacilityIds: [barka.facility_id!],
    veto: {
      any_frozen: true,
      track1_frozen: vetoScenario,
      track1_triggers: vetoScenario ? ["Tier D / RWA below the 12% floor"] : [],
      track2_frozen_for_facility: false,
      track2_policy: null,
    },
    mode: { mode: "CONVENTIONAL", adaptive: false, conventional: true },
  };
}

/** A deterministic stand-in for Pillar 2 so the offline demo can be driven end to end. */
export function fixtureScore(c: Candidate): { brr: number; pd: number; zone: DecisioningZone } {
  const burden = c.requested_amount / Math.max(c.monthly_salary * c.requested_tenure_months, 1);
  const brr = Math.min(10, Math.max(1, Math.round(2 + burden * 6 - Math.min(c.employment_years, 10) * 0.3)));
  const pd = Math.round((0.004 * 1.55 ** brr) * 1000) / 1000;
  const zone: DecisioningZone = brr <= 5 ? "AUTO_APPROVE" : brr <= 7 ? "AUGMENTED_DECISION" : "MANUAL_REVIEW";
  return { brr, pd, zone };
}

export function fixtureCandidate(body: CandidateCreate): Candidate {
  return {
    ...make(body.first_name, body.last_name, body.product, body.requested_amount, "new"),
    ...body,
    display_name: `${body.first_name} ${body.last_name}`,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}
