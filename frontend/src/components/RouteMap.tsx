import type { CSSProperties, ReactNode } from "react";
import { Plus } from "lucide-react";
import { CountUp } from "./CountUp";

export interface MapStation {
  id: string;
  name: string;
  count: number;
  /** the segment leaving this station */
  segment: { color: string; textColor: string; label: string };
  suspended?: boolean;
}

interface Props {
  stations: MapStation[];
  rejected: number;
  closed: number;
  summary: string;
  focus: string | null;
  onFocus(id: string | null): void;
  onShowRejected(): void;
  onNew(): void;
  /** layout switch shown beside New candidate */
  viewSwitch?: ReactNode;
}

/** The origination line as a transit diagram: stations, pillar-coloured segments, a Rejected spur and a Closed terminus. */
export function RouteMap({ stations, rejected, closed, summary, focus, onFocus, onShowRejected, onNew, viewSwitch }: Props) {
  return (
    <section className="map" aria-label="Origination line">
      <div className="map-head">
        <p>{summary}</p>
        {viewSwitch}
        <button className="btn btn-primary" onClick={onNew}>
          <Plus size={16} aria-hidden="true" />
          New candidate
        </button>
      </div>

      <div className="map-line" data-focus={focus ?? undefined}>
        {stations.map((s, i) => {
          const last = i === stations.length - 1;
          return (
            <div
              key={s.id}
              className="map-cell"
              data-focused={focus === s.id}
              data-suspended={s.suspended || undefined}
              data-last={last || undefined}
              style={{ "--seg": s.segment.color, "--seg-text": s.segment.textColor } as CSSProperties}
            >
              <button
                className="map-station"
                aria-pressed={focus === s.id}
                onClick={() => onFocus(focus === s.id ? null : s.id)}
              >
                <span className="map-name">{s.name}</span>
                <span className="sr-only">, {s.count} candidates</span>
              </button>
              <span className="map-seg" aria-hidden="true" />
              <span className="map-mark" data-occupied={s.count > 0} aria-hidden="true" />
              <span className="map-badge" aria-hidden="true">
                <CountUp value={s.count} />
              </span>
              <span className="map-seg-label">{s.suspended ? "Suspended · Track 1 veto" : s.segment.label}</span>

              {s.id === "submitted" && rejected > 0 && (
                <button className="map-spur" onClick={onShowRejected}>
                  <span className="map-spur-stroke" aria-hidden="true" />
                  <span className="map-stop" aria-hidden="true" />
                  Rejected <CountUp value={rejected} />
                </button>
              )}

              {last && (
                <span className="map-terminus">
                  <span className="map-stop" aria-hidden="true" />
                  Closed {closed}
                </span>
              )}
            </div>
          );
        })}
      </div>

      <p className="map-key">
        <span>
          <i className="key-mark" data-occupied="true" /> candidates at this station
        </span>
        <span>
          <i className="key-mark" /> station empty
        </span>
        <span>
          <i className="key-hatch" /> suspended by a Pillar 4 veto
        </span>
      </p>
    </section>
  );
}
