import { useNavigate } from "react-router-dom";
import { useSubmitCandidate, useDisburseCandidate } from "../../data/hooks";
import { formatMoney } from "../../utils/codec";
import { Panel, StatLine, StatusBadge } from "../shared/Atoms";
import { ScorecardPanel } from "./ScorecardPanel";
import { DecisionForm } from "./DecisionForm";

export function CandidateDrawer({ candidate, onClose }) {
  const submit = useSubmitCandidate();
  const disburse = useDisburseCandidate();
  const navigate = useNavigate();

  if (!candidate) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-[440px] bg-panel border-l border-line h-full overflow-y-auto scrollbar-thin p-6 rise-in">
        <div className="flex items-start justify-between mb-1">
          <h2 className="font-head text-lg">{candidate.display_name}</h2>
          <button onClick={onClose} className="text-faint hover:text-text text-lg leading-none">
            ×
          </button>
        </div>
        <div className="mb-5">
          <StatusBadge value={candidate.status} label={candidate.status} />
        </div>

        {candidate.status === "new" && (
          <div className="space-y-4">
            <Panel title="Intake">
              <StatLine label="Requested amount" value={formatMoney(candidate.requested_amount)} />
              <StatLine label="Tenure" value={`${candidate.requested_tenure_months} months`} />
              <StatLine label="Monthly salary" value={formatMoney(candidate.monthly_salary)} />
              <StatLine label="Seed profile" value={candidate.seed_profile || "manual intake"} />
            </Panel>
            <button
              onClick={() => submit.mutate(candidate.id)}
              disabled={submit.isPending}
              className="w-full bg-ledger text-ink text-sm font-medium py-2.5 rounded-sm hover:bg-ledger/90 disabled:opacity-50 transition"
            >
              {submit.isPending ? "Scoring…" : "Submit for scoring"}
            </button>
            {submit.isError && <div className="text-xs text-danger">{submit.error.message}</div>}
          </div>
        )}

        {candidate.status === "scored" && (
          <div className="space-y-4">
            <Panel title="Pillar 2 scorecard" eyebrow="Real credit engine output">
              <ScorecardPanel candidate={candidate} />
            </Panel>
            <DecisionForm candidate={candidate} onDone={onClose} />
          </div>
        )}

        {(candidate.status === "approved" || candidate.status === "disbursing") && (
          <div className="space-y-4">
            <Panel title="Origination recorded">
              <StatLine label="Facility ID" value={candidate.facility_id} />
              <StatLine label="Application ID" value={candidate.application_id} />
              <StatLine label="IFRS9 stage" value="1 (mirrored to Pillar 4)" />
            </Panel>
            <button
              onClick={() => disburse.mutate(candidate.id)}
              disabled={disburse.isPending || candidate.status === "disbursing"}
              className="w-full bg-ledger text-ink text-sm font-medium py-2.5 rounded-sm hover:bg-ledger/90 disabled:opacity-50 transition"
            >
              {candidate.status === "disbursing" || disburse.isPending ? "Disbursing…" : "Disburse funds"}
            </button>
            {disburse.isError && (
              <div className="text-xs text-danger space-y-1">
                <div>{disburse.error.message}</div>
                {/veto|freeze/i.test(disburse.error.message || "") && (
                  <div className="text-muted">
                    Track 1 is frozen — run the "Governance review & release Track 1" action in the banner, then try again.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {["disbursed", "delinquent", "defaulted", "closed"].includes(candidate.status) && (
          <div className="space-y-4">
            <Panel title="Now a live loan">
              <StatLine label="Facility ID" value={candidate.facility_id} />
              <StatLine label="Outstanding" value={formatMoney(candidate.outstanding)} />
              <StatLine label="Payments made" value={candidate.payments_made} />
            </Panel>
            <button
              onClick={() => navigate(`/loans/${candidate.facility_id}`)}
              className="w-full border border-ledger/40 text-ledger text-sm font-medium py-2.5 rounded-sm hover:bg-ledger/10 transition"
            >
              Open loan detail →
            </button>
          </div>
        )}

        {candidate.status === "rejected" && (
          <Panel title="Rejected">
            <p className="text-sm text-muted">{candidate.approval_note || "No officer note recorded."}</p>
          </Panel>
        )}
      </div>
    </div>
  );
}
