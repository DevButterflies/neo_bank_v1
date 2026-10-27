// Shapes taken from DOCS/neo-bank-api-playbook.pdf (Bank Orchestrator v3.4.0).

export type CandidateStatus = "new" | "submitted" | "approved" | "disbursed" | "rejected";
export type DecisioningZone = "AUTO_APPROVE" | "AUGMENTED_DECISION" | "MANUAL_REVIEW";
export type EmployerType = "government" | "military" | "private" | "self_employed";
export type Gender = "male" | "female";

export interface Candidate {
  id: string;
  display_name: string;
  first_name: string;
  last_name: string;
  name_ar: string | null;
  gender: Gender;
  age: number;
  national_id: string | null;
  phone: string | null;
  city: string;
  employer_name: string | null;
  employer_type: EmployerType | null;
  employment_years: number;
  job_title: string | null;
  monthly_salary: number;
  product: string;
  requested_amount: number;
  requested_tenure_months: number;
  status: CandidateStatus;
  submitted_at: string | null;
  scored_at: string | null;
  approved_at: string | null;
  originated_at: string | null;
  disbursed_at: string | null;
  facility_id: string | null;
  p2_brr: number | null;
  p2_pd: number | null;
  p2_zone: DecisioningZone | null;
  p2_packet_status: string | null;
  approval_note: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateCreate {
  first_name: string;
  last_name: string;
  gender: Gender;
  age: number;
  national_id: string | null;
  phone: string | null;
  city: string;
  employer_name: string | null;
  employer_type: EmployerType | null;
  employment_years: number;
  job_title: string | null;
  monthly_salary: number;
  product: string;
  requested_amount: number;
  requested_tenure_months: number;
}

export interface ApprovalDecision {
  approve: boolean;
  officer_id: string;
  officer_name: string | null;
  note: string | null;
}

export interface FlowResult {
  status: string | null;
  candidate_id: string | null;
  facility_id: string | null;
  packet_id: string | null;
  approved: boolean | null;
  amount: number | null;
  currency: string | null;
  brr: number | null;
  pd: number | null;
  zone: DecisioningZone | null;
}

export interface VetoState {
  any_frozen: boolean;
  track1_frozen: boolean;
  track1_triggers: string[];
  track2_frozen_for_facility: boolean;
  track2_policy: string | null;
}

export interface ModeState {
  mode: string;
  adaptive: boolean;
  conventional: boolean;
}

/** What the pipeline screen needs, whichever source it came from. */
export interface BoardSnapshot {
  month: number;
  candidates: Candidate[];
  closedFacilities: number;
  frozenFacilityIds: string[];
  veto: VetoState;
  mode: ModeState;
}
