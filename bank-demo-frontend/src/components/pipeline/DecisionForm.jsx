import { useState } from "react";
import { useApproveCandidate } from "../../data/hooks";

export function DecisionForm({ candidate, onDone }) {
  const [note, setNote] = useState("");
  const approve = useApproveCandidate();

  function submit(approveDecision) {
    approve.mutate(
      { id: candidate.id, decision: { approve: approveDecision, officer_id: "DEMO-OFFICER-1", officer_name: "Demo Officer", note: note || undefined } },
      { onSuccess: onDone }
    );
  }

  return (
    <div className="border border-line rounded-md p-4 bg-raised">
      <div className="text-xs text-muted mb-3">
        Officer decision — approval is always manual in this system; scoring alone never originates a facility.
      </div>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Officer note (optional)"
        className="w-full bg-ink border border-line rounded-sm px-3 py-2 text-sm text-text placeholder:text-faint focus:outline-none focus:border-ledger/50 mb-3"
        rows={2}
      />
      <div className="flex gap-2">
        <button
          onClick={() => submit(true)}
          disabled={approve.isPending}
          className="flex-1 bg-ledger text-ink text-sm font-medium py-2 rounded-sm hover:bg-ledger/90 disabled:opacity-50 transition"
        >
          Approve
        </button>
        <button
          onClick={() => submit(false)}
          disabled={approve.isPending}
          className="flex-1 border border-danger/40 text-danger text-sm font-medium py-2 rounded-sm hover:bg-danger/10 disabled:opacity-50 transition"
        >
          Reject
        </button>
      </div>
      {approve.isError && <div className="text-xs text-danger mt-2">{approve.error.message}</div>}
    </div>
  );
}
