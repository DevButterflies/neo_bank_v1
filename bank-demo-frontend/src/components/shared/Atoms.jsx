export function Panel({ title, eyebrow, right, children, className = "" }) {
  return (
    <div className={`bg-panel border border-line rounded-md p-5 ${className}`}>
      {(title || right) && (
        <div className="flex items-baseline justify-between mb-4">
          <div>
            {eyebrow && <div className="text-[11px] text-faint tracking-wide mb-0.5">{eyebrow}</div>}
            {title && <h3 className="font-head text-sm font-medium text-text">{title}</h3>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

const STATUS_STYLES = {
  new: "bg-info/10 text-info border-info/30",
  scored: "bg-amber/10 text-amber border-amber/30",
  approved: "bg-ledger/10 text-ledger border-ledger/30",
  disbursed: "bg-ledger/15 text-ledger border-ledger/40",
  delinquent: "bg-amber/15 text-amber border-amber/40",
  defaulted: "bg-danger/15 text-danger border-danger/40",
  closed: "bg-faint/10 text-muted border-line",
  rejected: "bg-danger/10 text-danger border-danger/30",
  AUTO_APPROVE: "bg-ledger/10 text-ledger border-ledger/30",
  AUGMENTED_DECISION: "bg-amber/10 text-amber border-amber/30",
  MANUAL_REVIEW: "bg-danger/10 text-danger border-danger/30",
  clear: "bg-ledger/10 text-ledger border-ledger/30",
  frozen: "bg-danger/15 text-danger border-danger/40",
};

export function StatusBadge({ value, label }) {
  const cls = STATUS_STYLES[value] || "bg-faint/10 text-muted border-line";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[11px] font-mono ${cls}`}>
      {label ?? value}
    </span>
  );
}

export function Dot({ ok }) {
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${ok ? "bg-ledger" : "bg-danger"} ${ok ? "" : "pulse-dot"}`} />;
}

export function StatLine({ label, value, tone = "text" }) {
  const toneCls = { text: "text-text", ledger: "text-ledger", amber: "text-amber", danger: "text-danger", muted: "text-muted" }[tone];
  return (
    <div className="flex items-baseline justify-between py-1.5 border-b border-line/60 last:border-0">
      <span className="text-xs text-muted">{label}</span>
      <span className={`font-mono text-sm ${toneCls}`}>{value}</span>
    </div>
  );
}
