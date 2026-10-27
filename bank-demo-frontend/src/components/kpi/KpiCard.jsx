const ACCENTS = {
  ledger: "border-l-ledger",
  amber: "border-l-amber",
  danger: "border-l-danger",
  info: "border-l-info",
};

export function KpiCard({ label, value, sub, accent = "ledger" }) {
  return (
    <div className={`bg-panel border border-line border-l-[3px] ${ACCENTS[accent]} rounded-md px-5 py-4`}>
      <div className="text-[11px] text-faint mb-1.5">{label}</div>
      <div className="font-mono text-2xl text-text leading-none">{value}</div>
      {sub && <div className="text-xs text-muted mt-2">{sub}</div>}
    </div>
  );
}
