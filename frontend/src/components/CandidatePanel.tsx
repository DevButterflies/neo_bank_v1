import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { X } from "lucide-react";
import { ApiError } from "../api/client";
import type { Candidate } from "../api/types";
import { money, pct, productLabel, ZONES } from "../lib/format";
import { useBoard } from "../state/board";
import { ZoneMark } from "./ZoneMark";

const STATION_LABEL = {
  new: "New · waiting to be scored",
  submitted: "Scored · waiting for your decision",
  approved: "Approved · ready to disburse",
  disbursed: "Disbursed · facility live",
  rejected: "Rejected",
} as const;

export function CandidatePanel({ candidate, onClose }: { candidate: Candidate; onClose(): void }) {
  const { submit, decide, disburse } = useBoard();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const title = useRef<HTMLHeadingElement>(null);

  useEffect(() => title.current?.focus(), []);

  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached. Check that the backend is running."));
    } finally {
      setBusy(false);
    }
  };

  const zone = candidate.p2_zone ? ZONES[candidate.p2_zone] : null;

  return (
    <aside className="panel" aria-labelledby="panel-title">
      <div className="panel-head">
        <div>
          <h2 id="panel-title" ref={title} tabIndex={-1}>
            {candidate.display_name}
          </h2>
          <p>{STATION_LABEL[candidate.status]}</p>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close candidate">
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="panel-body">
        {candidate.p2_brr != null && (
          <section className="panel-section" aria-label="Pillar 2 score">
            <h3>Pillar 2 score</h3>
            <div className="score">
              <div className="score-brr" style={{ "--c": zone?.color } as CSSProperties}>
                <span>
                  {candidate.p2_brr}
                  <small>BRR</small>
                </span>
              </div>
              <dl className="facts">
                <dt>Probability of default</dt>
                <dd>{pct(candidate.p2_pd)}</dd>
                <dt>Zone</dt>
                <dd>
                  <ZoneMark zone={candidate.p2_zone} />
                </dd>
                <dt>Packet</dt>
                <dd>{candidate.p2_packet_status ?? "–"}</dd>
              </dl>
            </div>
            {zone && candidate.status === "submitted" && <p className="zone-note">{zone.note}</p>}
          </section>
        )}

        <section className="panel-section" aria-label="Request">
          <h3>Request</h3>
          <dl className="facts">
            <dt>Product</dt>
            <dd>{productLabel(candidate.product)}</dd>
            <dt>Amount</dt>
            <dd>{money(candidate.requested_amount)}</dd>
            <dt>Tenure</dt>
            <dd>{candidate.requested_tenure_months} months</dd>
            <dt>Monthly income</dt>
            <dd>{money(candidate.monthly_salary)}</dd>
            <dt>Employer</dt>
            <dd>{candidate.employer_name ?? "–"}</dd>
            <dt>Years employed</dt>
            <dd>{candidate.employment_years}</dd>
            <dt>City</dt>
            <dd>{candidate.city}</dd>
          </dl>
        </section>

        {(candidate.approved_by || candidate.facility_id) && (
          <section className="panel-section" aria-label="Decision">
            <h3>Decision</h3>
            <dl className="facts">
              <dt>Decided by</dt>
              <dd>{candidate.approved_by ?? "–"}</dd>
              <dt>Facility</dt>
              <dd>{candidate.facility_id ?? "–"}</dd>
              {candidate.approval_note && (
                <>
                  <dt>Note</dt>
                  <dd>{candidate.approval_note}</dd>
                </>
              )}
            </dl>
          </section>
        )}

        {error && (
          <div className="error" role="alert">
            <b>{error.isConflict ? "Blocked. " : "Not done. "}</b>
            {error.detail}
          </div>
        )}

        {candidate.status === "new" && (
          <div className="actions">
            <button className="btn btn-primary" disabled={busy} onClick={() => act(() => submit(candidate.id))}>
              Submit for scoring
            </button>
          </div>
        )}

        {candidate.status === "submitted" && (
          <section className="panel-section" aria-label="Your decision">
            <div className="field">
              <label htmlFor="note">Note for the file</label>
              <textarea id="note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why you approve or reject" />
            </div>
            <div className="actions" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" disabled={busy} onClick={() => act(() => decide(candidate.id, true, note))}>
                Approve and open facility
              </button>
              <button className="btn btn-danger" disabled={busy} onClick={() => act(() => decide(candidate.id, false, note))}>
                Reject
              </button>
            </div>
          </section>
        )}

        {candidate.status === "approved" && (
          <div className="actions">
            <button className="btn btn-primary" disabled={busy} onClick={() => act(() => disburse(candidate.id))}>
              Disburse {money(candidate.requested_amount)}
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
