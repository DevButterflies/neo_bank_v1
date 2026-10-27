import type { CSSProperties } from "react";
import { CountUp } from "./CountUp";

export interface LineStop {
  id: string;
  name: string;
  count: number;
  /** colour of the segment leaving this stop */
  color: string;
}

interface Props {
  label: string;
  stops: LineStop[];
  /** a stop drawn as a branch below the line (Restructured, Rejected) */
  spur?: LineStop;
  selected: string | null;
  onSelect(id: string | null): void;
}

/** A compact transit line used as an area's state filter: stops with counts, one selectable at a time. */
export function StateLine({ label, stops, spur, selected, onSelect }: Props) {
  const toggle = (id: string) => onSelect(selected === id ? null : id);
  return (
    <div
      className="state-line"
      role="group"
      aria-label={label}
      data-selecting={selected ? "" : undefined}
      style={{ "--n": stops.length } as CSSProperties}
    >
      <ol className="state-stops">
        {stops.map((s, i) => (
          <li
            key={s.id}
            className="state-stop"
            data-last={i === stops.length - 1 || undefined}
            data-selected={selected === s.id}
            style={{ "--seg": s.color } as CSSProperties}
          >
            <button aria-pressed={selected === s.id} onClick={() => toggle(s.id)}>
              <span className="state-mark" data-occupied={s.count > 0} aria-hidden="true" />
              <span className="state-name">{s.name}</span>
              <span className="state-count">
                <CountUp value={s.count} />
              </span>
            </button>
          </li>
        ))}
      </ol>
      {spur && (
        <button
          className="state-spur"
          data-selected={selected === spur.id}
          aria-pressed={selected === spur.id}
          onClick={() => toggle(spur.id)}
          style={{ "--seg": spur.color } as CSSProperties}
        >
          <span className="state-spur-stroke" aria-hidden="true" />
          <span className="stop" aria-hidden="true" />
          {spur.name} <span className="state-count">{spur.count}</span>
        </button>
      )}
    </div>
  );
}
