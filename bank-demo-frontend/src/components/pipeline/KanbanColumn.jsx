import { CandidateCard } from "./CandidateCard";

export function KanbanColumn({ title, candidates, onSelect, tone = "text" }) {
  const toneCls = { text: "text-text", amber: "text-amber", ledger: "text-ledger", danger: "text-danger" }[tone];
  return (
    <div className="flex-1 min-w-[220px]">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <span className={`text-xs font-medium ${toneCls}`}>{title}</span>
        <span className="text-[11px] font-mono text-faint">{candidates.length}</span>
      </div>
      <div className="space-y-2.5 min-h-[80px]">
        {candidates.map((c) => (
          <CandidateCard key={c.id} candidate={c} onClick={() => onSelect(c)} />
        ))}
        {candidates.length === 0 && (
          <div className="text-[11px] text-faint border border-dashed border-line rounded-md py-6 text-center">Empty</div>
        )}
      </div>
    </div>
  );
}
