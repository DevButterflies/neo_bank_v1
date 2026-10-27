import { useEffect, useRef, useState } from "react";
import { fmt, groupLines } from "./bilanFormat";

/** True for 700ms after `value` changes — makes a realtime update visible
 *  rather than merely correct. No flash on first paint. */
function useFlash(value) {
  const prevRef = useRef(value);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (prevRef.current === value) return undefined;
    prevRef.current = value;
    setFlash(true);
    const timer = setTimeout(() => setFlash(false), 700);
    return () => clearTimeout(timer);
  }, [value]);

  return flash;
}

function LineRow({ compte, label, montant }) {
  const flash = useFlash(montant);
  const negative = Number(montant) < 0;

  return (
    <div className="flex items-baseline gap-2 py-[5px]">
      <span className="font-mono text-[11px] text-faint w-9 shrink-0">{compte}</span>
      <span className="text-[13px] text-muted truncate">{label}</span>
      <span className="flex-1 h-0 border-b border-dotted border-line self-end mb-[3px] min-w-4" />
      <span
        className={`font-mono text-[13px] tabular-nums px-1 -mx-1 rounded-sm transition-colors duration-500 ${
          negative ? "text-danger" : "text-text"
        } ${flash ? "bg-ledger/25 text-ledger" : ""}`}
      >
        {fmt(montant)}
      </span>
    </div>
  );
}

function RubriqueBlock({ title, rows, total }) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="text-[10px] uppercase tracking-[0.14em] text-faint mb-1.5">{title}</div>
      <div className="border-l border-line pl-3">
        {rows.map((row) => (
          <LineRow key={row.compte} {...row} />
        ))}
        <div className="flex items-baseline justify-between border-t border-line/70 mt-1 pt-2">
          <span className="text-[11px] uppercase tracking-wide text-muted">
            Total {title.toLowerCase()}
          </span>
          <span className="font-mono text-[13px] font-medium tabular-nums text-text">
            {fmt(total)}
          </span>
        </div>
      </div>
    </div>
  );
}

export function BilanColumn({ side, lines = [], rubriques, total }) {
  const groups = groupLines(lines, rubriques);

  return (
    <div className="bg-panel border border-line rounded-md p-5 min-w-0">
      <div className="flex items-baseline justify-between mb-4 pb-3 border-b border-line">
        <h3 className="font-head text-sm font-semibold uppercase tracking-[0.18em] text-text">
          {side}
        </h3>
        <span className="text-[10px] uppercase tracking-wide text-faint">Montants en USD</span>
      </div>

      {groups.map((group_) => (
        <RubriqueBlock key={group_.key} title={group_.title} rows={group_.rows} total={group_.total} />
      ))}

      <div className="flex items-baseline justify-between border-t-2 border-b-[3px] border-text/50 mt-4 pt-3 pb-2">
        <span className="font-head text-[13px] font-semibold uppercase tracking-[0.14em] text-text">
          Total général {side.toLowerCase()}
        </span>
        <span className="font-mono text-lg font-semibold tabular-nums text-text">{fmt(total)}</span>
      </div>
    </div>
  );
}
