import { useState } from "react";
import { CircleAlert, CircleCheck, CircleDashed } from "lucide-react";
import { demoGovernance } from "../api/areaFixtures";
import { governance } from "../api/areas";
import type { Gate, GovernanceState, PendingItem } from "../api/areas";
import { ApiError } from "../api/client";
import { ActionError, Sheet } from "../components/Sheet";
import { useArea } from "../state/useArea";

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const fmtDate = (iso: string | null) => (iso ? dateFmt.format(new Date(iso)) : "–");
const label = (t: string) => t.replace(/_/g, " ").toLowerCase().replace(/^\w/, (m) => m.toUpperCase());
const isOpen = (s: string) => !/resolv|struck|clos/i.test(s);
const PRIORITY: Record<string, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

type SheetState = { kind: "pending"; item: PendingItem } | { kind: "gate"; gate: Gate } | null;

export function GovernancePage() {
  const area = useArea<GovernanceState>(() => governance.state(), demoGovernance);
  const [sheet, setSheet] = useState<SheetState>(null);
  const [showResolved, setShowResolved] = useState(false);
  const d = area.data;

  const pending = (d?.pending ?? [])
    .filter((p) => showResolved || isOpen(p.status))
    .sort((a, b) => Number(!isOpen(a.status)) - Number(!isOpen(b.status)) || (PRIORITY[a.priority ?? ""] ?? 3) - (PRIORITY[b.priority ?? ""] ?? 3));
  const openCount = (d?.pending ?? []).filter((p) => isOpen(p.status)).length;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Governance</h1>
          <p>The Orchestrator's rulebook: decisions the code must never take on its own.</p>
        </div>
      </div>

      {area.error && <ActionError error={area.error} />}
      {!d && !area.error && <p className="empty">Loading the governance register…</p>}

      {d && (
        <>
          <section className="status-row" aria-label="Canon and staging">
            <div className="status-tile">
              <p className="tile-label">Current canon</p>
              <p className="tile-value">{d.canon ? `v${d.canon.version_number}` : "None ratified"}</p>
              <p className="tile-note">
                {d.canon
                  ? `${d.canon.name} · ${label(d.canon.status)}${d.canon.ratification_instrument ? ` by ${d.canon.ratification_instrument}` : ""} · ${fmtDate(d.canon.ratified_at)}`
                  : "No canon version is marked current."}
              </p>
            </div>
            <div className="status-tile">
              <p className="tile-label">Staging</p>
              <p className="tile-value">{label(d.mode)}</p>
              <p className="tile-note">{d.stage != null ? `Stage ${d.stage}` : "Stage not reported"}</p>
            </div>
            <div className="status-tile" data-alert={openCount > 0 || undefined}>
              <p className="tile-label">PENDING register</p>
              <p className="tile-value">{openCount} open</p>
              <p className="tile-note">Each blocks the code paths it names until governance resolves it.</p>
            </div>
          </section>

          <h2 className="section-title">Staging gates</h2>
          <ol className="gates">
            {d.gates.map((g) => {
              const st = g.status.toUpperCase();
              const cleared = st.includes("CLEAR");
              const blocked = st.includes("BLOCK");
              return (
                <li key={g.id} className="gate" data-state={cleared ? "cleared" : blocked ? "blocked" : "open"}>
                  <span className="gate-mark" aria-hidden="true">
                    {cleared ? <CircleCheck size={18} /> : blocked ? <CircleAlert size={18} /> : <CircleDashed size={18} />}
                  </span>
                  <div>
                    <p className="gate-name">
                      {g.gate_label} · {cleared ? "Cleared" : blocked ? "Blocked" : label(g.status)}
                    </p>
                    <p className="gate-criteria">{g.criteria ?? "No criteria recorded"}</p>
                    <p className="gate-meta">
                      {cleared ? `Cleared ${fmtDate(g.cleared_at)}${g.cleared_by ? ` by ${g.cleared_by}` : ""}` : g.notes ?? ""}
                    </p>
                  </div>
                  {!cleared && (
                    <button className="btn btn-small" onClick={() => setSheet({ kind: "gate", gate: g })}>
                      Decide…
                    </button>
                  )}
                </li>
              );
            })}
            {d.gates.length === 0 && <li className="empty">No staging gates defined.</li>}
          </ol>

          <div className="section-head">
            <h2 className="section-title">PENDING register</h2>
            <label className="check">
              <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
              Show resolved
            </label>
          </div>
          <section className="table-card" aria-label="PENDING items">
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Category</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Registered</th>
                    <th>
                      <span className="sr-only">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pending.map((p) => (
                    <tr key={p.id} data-void={!isOpen(p.status) || undefined}>
                      <td className="wrap">
                        <span className="row-name">
                          {p.item_number ? `${p.item_number} · ` : ""}
                          {p.title ?? "Untitled"}
                        </span>
                        <span className="row-meta">{isOpen(p.status) ? p.description : p.resolution_notes ?? p.description}</span>
                      </td>
                      <td>{label(p.category)}</td>
                      <td>{p.priority ? label(p.priority) : "–"}</td>
                      <td>
                        {isOpen(p.status) ? label(p.status) : `${label(p.status)}${p.governance_reference ? ` · ${p.governance_reference}` : ""}`}
                      </td>
                      <td>{fmtDate(p.registered_at)}</td>
                      <td data-align="end" className="action-cell">
                        {isOpen(p.status) && (
                          <button className="btn btn-small" onClick={() => setSheet({ kind: "pending", item: p })}>
                            Resolve…
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {pending.length === 0 && <p className="table-empty">No open PENDING items.</p>}
            </div>
          </section>

          <h2 className="section-title">Veto log</h2>
          <section className="table-card" aria-label="Veto log">
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Track</th>
                    <th>Signal</th>
                    <th>Packet</th>
                    <th>Review</th>
                    <th>Notified</th>
                  </tr>
                </thead>
                <tbody>
                  {d.vetoes.map((v) => (
                    <tr key={v.id}>
                      <td>#{v.event_number}</td>
                      <td>
                        {label(v.track)}
                        {v.facility_id && <span className="row-meta">{v.facility_id}</span>}
                      </td>
                      <td className="wrap">{v.pillar_4_signal}</td>
                      <td>{label(v.p2_packet_action)}</td>
                      <td>
                        {label(v.governance_review_status)}
                        {v.restart_authorized_at && (
                          <span className="row-meta">
                            Restart {fmtDate(v.restart_authorized_at)}
                            {v.restart_authorized_by ? ` · ${v.restart_authorized_by}` : ""}
                          </span>
                        )}
                      </td>
                      <td>{fmtDate(v.orchestrator_notified_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {d.vetoes.length === 0 && <p className="table-empty">No veto has ever been raised.</p>}
            </div>
          </section>
        </>
      )}

      {sheet?.kind === "pending" && (
        <ResolveSheet
          item={sheet.item}
          live={area.live}
          onClose={() => setSheet(null)}
          onDone={(notes, ref) =>
            area.live
              ? area.reload()
              : area.setData((s) => ({
                  ...s,
                  pending: s.pending.map((p) =>
                    p.id === sheet.item.id
                      ? { ...p, status: "RESOLVED", resolved_at: new Date().toISOString(), resolution_notes: notes, governance_reference: ref }
                      : p,
                  ),
                }))
          }
        />
      )}
      {sheet?.kind === "gate" && (
        <GateSheet
          gate={sheet.gate}
          live={area.live}
          onClose={() => setSheet(null)}
          onDone={(gate) => (area.live ? area.reload() : area.setData((s) => ({ ...s, gates: s.gates.map((g) => (g.id === gate.id ? gate : g)) })))}
        />
      )}
    </main>
  );
}

function ResolveSheet({
  item,
  live,
  onClose,
  onDone,
}: {
  item: PendingItem;
  live: boolean;
  onClose(): void;
  onDone(notes: string, ref: string | null): void;
}) {
  const [notes, setNotes] = useState("");
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const save = async () => {
    if (!notes.trim()) return setError(new ApiError(422, "Resolution notes are required: PENDING items are never resolved silently."));
    if (!ref.trim()) return setError(new ApiError(422, "A governance reference is required: a PENDING item is resolved by a ruling, never in code."));
    setBusy(true);
    setError(null);
    try {
      if (live) await governance.resolvePending(item.id, notes.trim(), ref.trim());
      onDone(notes.trim(), ref.trim());
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet title={`Resolve ${item.item_number ?? "item"}`} subtitle={item.title ?? undefined} onClose={onClose}>
      <p className="zone-note">{item.description}</p>
      <div className="field">
        <label htmlFor="rnotes">Resolution notes</label>
        <textarea id="rnotes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="rref2">Governance reference</label>
        <input id="rref2" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. RI-3" />
        <span className="hint">The ruling that settles it.</span>
      </div>
      <ActionError error={error} />
      <div className="actions">
        <button className="btn btn-primary" disabled={busy} onClick={save}>
          Resolve item
        </button>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </Sheet>
  );
}

function GateSheet({ gate, live, onClose, onDone }: { gate: Gate; live: boolean; onClose(): void; onDone(g: Gate): void }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const run = async (clear: boolean) => {
    if (!clear && !notes.trim()) return setError(new ApiError(422, "Say why the gate is blocked."));
    setBusy(true);
    setError(null);
    try {
      const now = new Date().toISOString();
      const next = live
        ? await (clear ? governance.clearGate(gate.gate_label) : governance.blockGate(gate.gate_label, notes.trim()))
        : clear
          ? { ...gate, status: "CLEARED", cleared_at: now, cleared_by: "Admin" }
          : { ...gate, status: "BLOCKED", notes: notes.trim() };
      onDone(next);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet title={`Gate ${gate.gate_label}`} subtitle={gate.criteria ?? undefined} onClose={onClose}>
      <p className="zone-note">Clear the gate only when its criteria are met. Blocking records why.</p>
      <div className="field">
        <label htmlFor="gnotes">Notes</label>
        <textarea id="gnotes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Required to block" />
      </div>
      <ActionError error={error} />
      <div className="actions">
        <button className="btn btn-primary" disabled={busy} onClick={() => run(true)}>
          Clear gate
        </button>
        <button className="btn btn-danger" disabled={busy} onClick={() => run(false)}>
          Block gate
        </button>
      </div>
    </Sheet>
  );
}
