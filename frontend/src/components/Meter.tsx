import { CircleAlert, CircleCheck } from "lucide-react";

interface Props {
  label: string;
  /** the measured value, as a fraction (0.142 = 14.2%) */
  value: number | null;
  /** the limit, as a fraction */
  limit: number;
  /** "floor": breach below the limit; "ceiling": breach above it */
  kind: "floor" | "ceiling";
  limitLabel: string;
  /** the right end of the track, as a fraction */
  max: number;
  note?: string;
  format?: (v: number) => string;
}

const asPct = (v: number) => `${(v * 100).toFixed(1)}%`;

/** A single ratio against its limit: value bar, limit tick, and a status that never relies on colour alone. */
export function Meter({ label, value, limit, kind, limitLabel, max, note, format = asPct }: Props) {
  const breach = value != null && (kind === "floor" ? value < limit : value > limit);
  const pos = (v: number) => `${Math.max(0, Math.min(1, v / max)) * 100}%`;
  return (
    <figure className="meter" data-breach={breach || undefined}>
      <figcaption className="meter-label">{label}</figcaption>
      <p className="meter-value">{value == null ? "–" : format(value)}</p>
      <p className="meter-status">
        {value == null ? (
          "Not reported"
        ) : breach ? (
          <>
            <CircleAlert size={15} aria-hidden="true" /> {kind === "floor" ? "Below" : "Above"} {limitLabel}
          </>
        ) : (
          <>
            <CircleCheck size={15} aria-hidden="true" /> Within {limitLabel}
          </>
        )}
      </p>
      <div
        className="meter-track"
        role="img"
        aria-label={`${label}: ${value == null ? "not reported" : format(value)}, limit ${format(limit)}`}
        title={`${value == null ? "–" : format(value)} against a ${kind} of ${format(limit)}`}
      >
        {value != null && <span className="meter-fill" style={{ width: pos(value) }} />}
        <span className="meter-limit" style={{ left: pos(limit) }}>
          <span>{format(limit)}</span>
        </span>
      </div>
      {note && <p className="meter-note">{note}</p>}
    </figure>
  );
}
