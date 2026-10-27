import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { LayoutList, OctagonAlert, Route } from "lucide-react";
import type { Candidate, CandidateStatus } from "../api/types";
import { CandidatePanel } from "../components/CandidatePanel";
import { CountUp } from "../components/CountUp";
import { NewCandidatePanel } from "../components/NewCandidatePanel";
import { PipelineTable } from "../components/PipelineTable";
import type { StatusFilter } from "../components/PipelineTable";
import { RouteMap } from "../components/RouteMap";
import type { MapStation } from "../components/RouteMap";
import { ZoneMark } from "../components/ZoneMark";
import { money, pct, productLabel } from "../lib/format";
import { useBoard } from "../state/board";

type StationId = Exclude<CandidateStatus, "rejected">;

interface Station {
  id: StationId;
  name: string;
  /** the segment leaving this station: the pillar that runs the next step */
  segment: MapStation["segment"];
  empty: string;
}

const STATIONS: Station[] = [
  {
    id: "new",
    name: "New",
    segment: { color: "var(--p2)", textColor: "var(--p2-text)", label: "Pillar 2 · credit scoring" },
    empty: "Nobody waiting. Add a borrower with New candidate.",
  },
  {
    id: "submitted",
    name: "Scored",
    segment: { color: "var(--p1)", textColor: "var(--p1)", label: "Officer approval" },
    empty: "No scores waiting for your decision.",
  },
  {
    id: "approved",
    name: "Approved",
    segment: { color: "var(--p3)", textColor: "var(--p3-text)", label: "Pillar 3 · disbursement" },
    empty: "Nothing approved and waiting to disburse.",
  },
  {
    id: "disbursed",
    name: "Disbursed",
    segment: { color: "var(--p3)", textColor: "var(--p3-text)", label: "Pillar 3 · repayment" },
    empty: "No live facilities yet.",
  },
];

const ZONE_ORDER = { MANUAL_REVIEW: 0, AUGMENTED_DECISION: 1, AUTO_APPROVE: 2 } as const;

type View = "table" | "line";
const VIEW_KEY = "pipeline.view";

/** The last layout this viewer chose; the table is the default. */
function storedView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "line" ? "line" : "table";
  } catch {
    return "table";
  }
}

type Panel = { kind: "candidate"; id: string } | { kind: "new" } | null;

export function PipelinePage() {
  const { board, moved, submit, disburse } = useBoard();
  const [panel, setPanel] = useState<Panel>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [view, setViewState] = useState<View>(storedView);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const setView = (v: View) => {
    setViewState(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* the choice just will not persist */
    }
  };
  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const rejectedRef = useRef<HTMLDivElement>(null);

  const open = useCallback((next: Exclude<Panel, null>) => {
    if (document.activeElement instanceof HTMLElement && !document.activeElement.closest(".panel")) {
      opener.current = document.activeElement;
    }
    setPanel(next);
  }, []);

  const close = useCallback(() => {
    setPanel(null);
    // give focus back to whatever opened the panel
    requestAnimationFrame(() => opener.current?.focus());
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const byStation = useMemo(() => {
    const groups: Record<CandidateStatus, Candidate[]> = { new: [], submitted: [], approved: [], disbursed: [], rejected: [] };
    for (const c of board?.candidates ?? []) groups[c.status].push(c);
    // the approval queue leads with the cases that need the most attention
    groups.submitted.sort((a, b) => ZONE_ORDER[a.p2_zone ?? "AUTO_APPROVE"] - ZONE_ORDER[b.p2_zone ?? "AUTO_APPROVE"]);
    return groups;
  }, [board]);

  if (!board) {
    return (
      <main className="page">
        <p className="empty">Loading the line…</p>
      </main>
    );
  }

  const selected = panel?.kind === "candidate" ? board.candidates.find((c) => c.id === panel.id) : undefined;
  const frozen = new Set(board.frozenFacilityIds);
  const total = board.candidates.length;
  const requested = board.candidates.reduce((s, c) => s + c.requested_amount, 0);
  const waiting = byStation.submitted.length;
  const suspended = board.veto.track1_frozen;

  const quick = async (id: string, fn: (id: string) => Promise<void>) => {
    setRowBusy(id);
    try {
      await fn(id);
    } catch {
      open({ kind: "candidate", id }); // the panel explains what went wrong
    } finally {
      setRowBusy(null);
    }
  };

  /** The one action a candidate waits on at its station, shared by both layouts. */
  const actionFor = (c: Candidate): ReactNode => {
    switch (c.status) {
      case "new":
        return (
          <button className="btn btn-small" disabled={rowBusy === c.id} onClick={() => quick(c.id, submit)}>
            Submit
          </button>
        );
      case "submitted":
        return (
          <button className="btn btn-small" onClick={() => open({ kind: "candidate", id: c.id })}>
            Decide
          </button>
        );
      case "approved":
        return (
          <button className="btn btn-small" disabled={rowBusy === c.id || suspended} onClick={() => quick(c.id, disburse)}>
            Disburse
          </button>
        );
      default:
        return null;
    }
  };

  const rowFor = (c: Candidate): ReactNode => {
    const isFrozen = c.facility_id != null && frozen.has(c.facility_id);
    let meta: ReactNode;
    let valueLabel: string | null = null;
    switch (c.status) {
      case "new":
        meta = productLabel(c.product);
        break;
      case "submitted":
        meta = (
          <>
            BRR {c.p2_brr} · PD {pct(c.p2_pd)}
            <span className="row-zone">
              <ZoneMark zone={c.p2_zone} />
            </span>
          </>
        );
        break;
      case "approved":
        meta = `BRR ${c.p2_brr} · ${productLabel(c.product)}`;
        break;
      case "disbursed":
        meta = (
          <>
            {c.facility_id ?? "facility"} · BRR {c.p2_brr}
            {isFrozen && (
              <span className="frozen">
                <i aria-hidden="true" />
                Frozen · Track 2
              </span>
            )}
          </>
        );
        valueLabel = "disbursed";
        break;
      case "rejected":
        meta = c.approval_note ?? `BRR ${c.p2_brr}`;
        valueLabel = "requested";
        break;
    }
    return (
      <li
        key={c.id}
        className="row"
        aria-current={selected?.id === c.id}
        data-moved={moved.has(c.id)}
        data-void={c.status === "rejected"}
      >
        <button className="row-main" onClick={() => open({ kind: "candidate", id: c.id })}>
          <span className="row-name">{c.display_name}</span>
          <span className="row-meta">{meta}</span>
        </button>
        <div className="row-side">
          <span className="row-value">
            <span className="amount">{money(c.requested_amount)}</span>
            {valueLabel && <small> {valueLabel}</small>}
          </span>
          {actionFor(c)}
        </div>
      </li>
    );
  };

  const mapStations: MapStation[] = STATIONS.map((s) => ({
    id: s.id,
    name: s.name,
    count: byStation[s.id].length,
    segment: s.segment,
    suspended: s.id === "submitted" && suspended,
  }));

  return (
    <main className="page">
      <div className="page-head">
        <h1>Origination line</h1>
      </div>

      {suspended && (
        <div className="banner" data-tone="veto" role="status">
          <OctagonAlert size={18} aria-hidden="true" />
          <p>
            <b>Approvals are suspended by a Track 1 veto.</b> Pillar 4 has frozen origination
            {board.veto.track1_triggers.length ? ` (${board.veto.track1_triggers.join(", ")})` : ""}, so approving
            or disbursing returns a conflict. Only governance can lift it.
          </p>
        </div>
      )}

      <RouteMap
        stations={mapStations}
        rejected={byStation.rejected.length}
        closed={board.closedFacilities}
        summary={`${total} candidates · ${money(requested)} requested · ${
          waiting > 0 ? `${waiting} waiting for your decision` : "nothing waiting for your decision"
        }`}
        focus={view === "table" ? (statusFilter === "all" ? null : statusFilter) : focus}
        onFocus={(id) => (view === "table" ? setStatusFilter((id ?? "all") as StatusFilter) : setFocus(id))}
        onShowRejected={() => {
          if (view === "table") return setStatusFilter("rejected");
          setFocus("submitted");
          rejectedRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
          rejectedRef.current?.focus();
        }}
        onNew={() => open({ kind: "new" })}
        viewSwitch={
          <div className="segmented" role="group" aria-label="Layout">
            <button aria-pressed={view === "table"} onClick={() => setView("table")}>
              <LayoutList size={15} aria-hidden="true" />
              Table
            </button>
            <button aria-pressed={view === "line"} onClick={() => setView("line")}>
              <Route size={15} aria-hidden="true" />
              Line
            </button>
          </div>
        }
      />

      <div className="workspace" data-panel={panel ? "open" : "closed"}>
        {view === "table" ? (
          <PipelineTable
            candidates={board.candidates}
            status={statusFilter}
            onStatus={setStatusFilter}
            selectedId={selected?.id}
            moved={moved}
            frozen={frozen}
            actionFor={actionFor}
            onOpen={(id) => open({ kind: "candidate", id })}
          />
        ) : (
        <div className="line" data-focus={focus ?? undefined}>
          {STATIONS.map((s, i) => {
            const rows = byStation[s.id];
            const last = i === STATIONS.length - 1;
            return (
              <section
                key={s.id}
                className="station"
                aria-label={`${s.name}, ${rows.length} candidates`}
                data-terminus={last ? "" : undefined}
                data-focused={focus === s.id}
                data-suspended={s.id === "submitted" && suspended}
                style={{ "--seg": s.segment.color } as CSSProperties}
              >
                {/* the station heading only shows where the line runs down the left (narrow screens) */}
                <div className="station-head" aria-hidden="true">
                  <span className="mark" data-occupied={rows.length > 0} />
                  <span className="station-name">{s.name}</span>
                  <span className="count">
                    <CountUp value={rows.length} />
                  </span>
                  <span className="station-seg">
                    {s.id === "submitted" && suspended ? "Suspended · Track 1" : s.segment.label}
                  </span>
                </div>

                {rows.length ? <ul className="rows">{rows.map(rowFor)}</ul> : <p className="empty">{s.empty}</p>}

                {s.id === "submitted" && byStation.rejected.length > 0 && (
                  <div className="spur" ref={rejectedRef} tabIndex={-1} aria-label={`Rejected, ${byStation.rejected.length}`}>
                    <p className="spur-head">
                      <span className="stop" aria-hidden="true" />
                      Rejected {byStation.rejected.length}
                    </p>
                    <ul className="rows">{byStation.rejected.map(rowFor)}</ul>
                  </div>
                )}

                {last && (
                  <p className="terminus-row">
                    <span className="stop" aria-hidden="true" />
                    Closed {board.closedFacilities}
                  </p>
                )}
              </section>
            );
          })}
        </div>
        )}

        {panel && <div className="scrim" onClick={close} aria-hidden="true" />}
        {panel?.kind === "new" && (
          <NewCandidatePanel onClose={close} onCreated={(c) => setPanel({ kind: "candidate", id: c.id })} />
        )}
        {selected && <CandidatePanel key={selected.id} candidate={selected} onClose={close} />}
      </div>
    </main>
  );
}
