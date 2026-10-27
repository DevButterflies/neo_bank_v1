import { unwrapDeep, humanize } from "../../utils/codec";

const EVENT_TONE = {
  ORIGINATION_RECORDED: "info",
  DISBURSEMENT: "ledger",
  COLLATERAL_PLEDGED: "ledger",
  REPAYMENT: "ledger",
  DELINQUENCY: "amber",
  DEFAULT: "danger",
  RESTRUCTURING_EXECUTED: "amber",
  RECOVERY_EXECUTED: "info",
  CLOSURE: "text",
};

const DOT_COLOR = { info: "#5B8DEF", ledger: "#2FBF9F", amber: "#E8A33D", danger: "#E5566A", text: "#8697A6" };

export function AuditTimeline({ records = [] }) {
  const rows = unwrapDeep(records);
  if (rows.length === 0) return <div className="text-xs text-faint">No audit records yet.</div>;

  return (
    <div className="space-y-0">
      {rows.map((r, i) => {
        const tone = EVENT_TONE[r.event_type] || "text";
        return (
          <div key={r.record_id || i} className="flex gap-3 pb-4 last:pb-0">
            <div className="flex flex-col items-center">
              <span className="w-2 h-2 rounded-full mt-1" style={{ background: DOT_COLOR[tone] }} />
              {i < rows.length - 1 && <span className="w-px flex-1 bg-line mt-1" />}
            </div>
            <div className="pb-1">
              <div className="flex items-baseline gap-2">
                <span className="text-sm text-text">{humanize(r.event_type)}</span>
                <span className="text-[10px] text-faint font-mono">{new Date(r.timestamp).toLocaleString()}</span>
              </div>
              <div className="text-[11px] text-muted mt-0.5">
                {r.actor_reference} · resulting state <span className="font-mono text-text">{r.resulting_state}</span>
              </div>
              {r.p4_veto_status && <div className="text-[10px] text-faint mt-0.5">{r.p4_veto_status}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
