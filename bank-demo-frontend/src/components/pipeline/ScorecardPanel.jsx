import { formatMoney, formatPct } from "../../utils/codec";
import { StatusBadge, StatLine } from "../shared/Atoms";

export function ScorecardPanel({ candidate }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] text-faint">Decisioning zone</div>
          <div className="mt-1">
            <StatusBadge value={candidate.p2_zone} label={candidate.p2_zone?.replace(/_/g, " ")} />
          </div>
        </div>
        <div className="text-right">
          <div className="text-[11px] text-faint">Bank risk rating</div>
          <div className="font-mono text-2xl text-text mt-0.5">BRR {candidate.p2_brr}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-6">
        <div>
          <StatLine label="Probability of default" value={formatPct(candidate.p2_pd)} />
          <StatLine label="Loss given default" value={formatPct(candidate.p2_lgd)} />
          <StatLine label="Exposure at default" value={formatMoney(candidate.p2_ead)} />
        </div>
        <div>
          <StatLine label="Expected loss" value={formatMoney(candidate.p2_el)} tone={candidate.p2_el > candidate.p2_ead * 0.02 ? "danger" : "ledger"} />
          <StatLine label="Requested amount" value={formatMoney(candidate.requested_amount)} />
          <StatLine label="Tenure" value={`${candidate.requested_tenure_months} months`} />
        </div>
      </div>

      <div className="pt-2 border-t border-line text-[11px] text-muted">
        Zone <span className="font-mono text-text">{candidate.p2_zone}</span> was produced by the real Pillar 2 scoring
        engine from this applicant's data file — thinner files are scored more conservatively and route to manual
        review by design.
      </div>
    </div>
  );
}
