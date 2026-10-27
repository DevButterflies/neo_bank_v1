import { formatMoney } from "../../utils/codec";
import { StatusBadge } from "../shared/Atoms";

export function CandidateCard({ candidate, onClick }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-raised border border-line hover:border-ledger/50 rounded-md p-3.5 transition group"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-head text-sm text-text group-hover:text-ledger transition">{candidate.display_name}</div>
        {candidate.p2_zone && <StatusBadge value={candidate.p2_zone} label={candidate.p2_zone.replace(/_/g, " ")} />}
      </div>
      <div className="mt-2 flex items-baseline justify-between">
        <span className="font-mono text-sm text-muted">{formatMoney(candidate.requested_amount)}</span>
        <span className="text-[11px] text-faint">{candidate.requested_tenure_months}mo</span>
      </div>
      {candidate.p2_brr != null && (
        <div className="mt-2 flex items-center gap-3 text-[11px] font-mono text-faint">
          <span>BRR {candidate.p2_brr}</span>
          <span>PD {(candidate.p2_pd * 100).toFixed(1)}%</span>
          <span>EL {formatMoney(candidate.p2_el)}</span>
        </div>
      )}
    </button>
  );
}
