import { useState } from "react";
import type { CSSProperties } from "react";
import { CircleAlert, CircleCheck, OctagonAlert } from "lucide-react";
import { demoPrudential } from "../api/areaFixtures";
import type { PrudentialDemo } from "../api/areaFixtures";
import { p4 } from "../api/areas";
import type { Buffers } from "../api/areas";
import { ApiError } from "../api/client";
import { Meter } from "../components/Meter";
import { ActionError, Sheet } from "../components/Sheet";
import { money } from "../lib/format";
import { useBoard } from "../state/board";
import { useArea } from "../state/useArea";

const BUFFERS: { key: keyof Buffers; name: string; what: string }[] = [
  { key: "el_pool", name: "EL Pool", what: "IFRS 9 ECL provisions" },
  { key: "ula_buffer", name: "ULA Buffer", what: "Loss capacity beyond Budgeted Loss" },
  { key: "liquidity_reserve", name: "Liquidity Reserve", what: "Funding-side liquidity" },
  { key: "rp_pool", name: "RP Pool", what: "Risk-premium income" },
];

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const fmtDate = (iso: string | null) => (iso ? dateFmt.format(new Date(iso)) : "–");
const label = (t: string) => t.replace(/_/g, " ").toLowerCase().replace(/^\w/, (m) => m.toUpperCase());

type SheetKind = "lift" | "mode" | null;

export function PrudentialPage() {
  const { board, source } = useBoard();
  const area = useArea<PrudentialDemo>(
    async () => {
      const [buffers, capital, adequacy, ifrs9, events, notifications] = await Promise.all([
        p4.buffers(),
        p4.capital(),
        p4.adequacy(),
        p4.ifrs9(),
        p4.events(),
        p4.notifications(),
      ]);
      return { buffers, capital, adequacy, ifrs9, events, notifications };
    },
    demoPrudential,
  );
  const [sheet, setSheet] = useState<SheetKind>(null);
  const d = area.data;
  if (!board) return null;

  const veto = board.veto;
  const adaptive = board.mode.adaptive;
  const track2 = board.frozenFacilityIds.length;
  const maxBuffer = d ? Math.max(...BUFFERS.map((b) => d.buffers[b.key]), 1) : 1;
  const stages = [1, 2, 3].map((s) => {
    const rows = d?.ifrs9.filter((r) => r.stage === s) ?? [];
    return { stage: s, count: rows.length, ecl: rows.reduce((t, r) => t + (r.ecl ?? 0), 0) };
  });
  const floor = d?.capital.tier_d_floor ?? 0.12;
  const budget = d?.capital.budgeted_loss_ratio ?? 0.02;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Prudential</h1>
          <p>Pillar 4 protects the bank's capital and can freeze new lending.</p>
        </div>
      </div>

      {area.error && <ActionError error={area.error} />}

      <section className="status-row" aria-label="Veto and mode">
        <div className="status-tile" data-alert={veto.track1_frozen || undefined}>
          <p className="tile-label">Track 1 · portfolio</p>
          <p className="tile-value">
            {veto.track1_frozen ? <OctagonAlert size={18} aria-hidden="true" /> : <CircleCheck size={18} aria-hidden="true" />}
            {veto.track1_frozen ? "Frozen" : "Clear"}
          </p>
          <p className="tile-note">
            {veto.track1_frozen
              ? veto.track1_triggers.join(", ") || "Origination is frozen bank-wide."
              : "Origination is open."}
          </p>
          {veto.track1_frozen && (
            <button className="btn btn-small" onClick={() => setSheet("lift")}>
              Lift freeze…
            </button>
          )}
        </div>
        <div className="status-tile" data-alert={track2 > 0 || undefined}>
          <p className="tile-label">Track 2 · facilities</p>
          <p className="tile-value">
            {track2 > 0 ? <CircleAlert size={18} aria-hidden="true" /> : <CircleCheck size={18} aria-hidden="true" />}
            {track2 > 0 ? `${track2} frozen` : "None frozen"}
          </p>
          <p className="tile-note">{track2 > 0 ? board.frozenFacilityIds.join(", ") : "No facility breaches Pillar 4 policy."}</p>
        </div>
        <div className="status-tile">
          <p className="tile-label">Operating mode</p>
          <p className="tile-value">{adaptive ? "Adaptive" : "Conventional"}</p>
          <p className="tile-note">
            {adaptive ? "CASS scoring and ABSF, sandbox-gated." : "Static tiers, classical foreclosure. The permanent floor."}
          </p>
          <button className="btn btn-small" onClick={() => setSheet("mode")}>
            {adaptive ? "Fall back to Conventional…" : "Activate Adaptive…"}
          </button>
        </div>
      </section>

      {!d && !area.error && <p className="empty">Loading the prudential layer…</p>}

      {d && (
        <>
          <h2 className="section-title">Capital and guarantees</h2>
          <section className="meters" aria-label="Prudential ratios">
            <Meter
              label="Tier D / RWA"
              value={d.capital.tier_d_over_rwa}
              limit={floor}
              kind="floor"
              limitLabel={`the ${(floor * 100).toFixed(0)}% floor`}
              max={0.25}
              note={`Tier D ${money(d.capital.tier_d_amount)} over RWA ${money(d.capital.rwa)}`}
            />
            <Meter
              label="Portfolio expected loss"
              value={d.capital.portfolio_el}
              limit={budget}
              kind="ceiling"
              limitLabel={`the ${(budget * 100).toFixed(0)}% Budgeted Loss`}
              max={0.04}
              note={`EL Pool holds ${money(d.capital.el_pool_balance)}`}
            />
            <Meter
              label="Guarantee pool, received against required"
              value={d.adequacy.required > 0 ? d.adequacy.received / d.adequacy.required : null}
              limit={1}
              kind="floor"
              limitLabel="the required level"
              max={1.25}
              format={(v) => `${(v * 100).toFixed(0)}%`}
              note={`${money(d.adequacy.received)} received of ${money(d.adequacy.required)}${
                d.adequacy.shortfall_amount > 0 ? ` · shortfall ${money(d.adequacy.shortfall_amount)} paces origination` : ""
              }`}
            />
          </section>

          <div className="two-col">
            <section className="card" aria-labelledby="buffers-title">
              <h2 className="card-title" id="buffers-title">
                Buffer sub-accounts
              </h2>
              <ul className="bars">
                {BUFFERS.map((b) => {
                  const v = d.buffers[b.key];
                  return (
                    <li key={b.key} title={`${b.name}: ${money(v)}`}>
                      <span className="bar-label">
                        {b.name}
                        <small>{b.what}</small>
                      </span>
                      <span className="bar-track">
                        <span className="bar-fill" style={{ "--w": `${(v / maxBuffer) * 100}%` } as CSSProperties} />
                      </span>
                      <span className="bar-value">{money(v)}</span>
                    </li>
                  );
                })}
              </ul>
              <p className="card-note">
                Guarantees granted / received: {d.capital.guarantees_granted_over_received?.toFixed(2) ?? "–"} · given book{" "}
                {money(d.capital.given_book)} · received book {money(d.capital.received_book)}
              </p>
            </section>

            <section className="card" aria-labelledby="ifrs-title">
              <h2 className="card-title" id="ifrs-title">
                IFRS 9 staging
              </h2>
              <div className="stage-tiles">
                {stages.map((s) => (
                  <div key={s.stage} className="stage-tile" data-stage={s.stage}>
                    <p className="tile-label">Stage {s.stage}</p>
                    <p className="stage-count">{s.count}</p>
                    <p className="tile-note">ECL {money(s.ecl)}</p>
                  </div>
                ))}
              </div>
              <table className="table table-tight">
                <thead>
                  <tr>
                    <th>Facility</th>
                    <th>Stage</th>
                    <th data-align="end">EAD</th>
                    <th data-align="end">ECL</th>
                  </tr>
                </thead>
                <tbody>
                  {d.ifrs9.map((r) => (
                    <tr key={r.facility_ref} data-stage={r.stage}>
                      <td>{r.facility_ref}</td>
                      <td>
                        <span className="stage-chip">Stage {r.stage}</span>
                      </td>
                      <td data-align="end">{money(r.ead)}</td>
                      <td data-align="end">{money(r.ecl)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {d.ifrs9.length === 0 && <p className="table-empty">No staged facilities yet.</p>}
              <p className="card-note">Staging is a provisioning event fed by Pillar 2. It never freezes a facility.</p>
            </section>
          </div>

          <div className="two-col">
            <section className="card" aria-labelledby="notif-title">
              <h2 className="card-title" id="notif-title">
                Veto notifications
              </h2>
              {d.notifications.length === 0 ? (
                <p className="empty">No freeze has been notified to the Orchestrator.</p>
              ) : (
                <ol className="trail">
                  {d.notifications.map((n, i) => (
                    <li key={i} data-tone={n.event === "veto_lift" ? undefined : "veto"}>
                      <span className="trail-mark" aria-hidden="true" />
                      <span className="trail-event">
                        {label(n.track)} {n.event === "veto_lift" ? "lifted" : "freeze"}
                      </span>
                      <span className="trail-meta">
                        {n.triggers.length ? n.triggers.map(label).join(", ") : "No trigger named"} ·{" "}
                        {n.governance_ref ?? "Governance review open"}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
            <section className="card" aria-labelledby="events-title">
              <h2 className="card-title" id="events-title">
                Pillar 4 event log
              </h2>
              {d.events.length === 0 ? (
                <p className="empty">No events yet.</p>
              ) : (
                <ol className="trail">
                  {d.events
                    .slice()
                    .reverse()
                    .map((e, i) => (
                      <li key={i}>
                        <span className="trail-mark" aria-hidden="true" />
                        <span className="trail-event">{label(e.type)}</span>
                        <span className="trail-meta">
                          {e.payload
                            ? Object.entries(e.payload)
                                .filter(([, v]) => v != null)
                                .map(([k, v]) => `${label(k)} ${typeof v === "number" && v > 100 ? money(v) : String(v)}`)
                                .join(" · ")
                            : ""}
                          {e.occurred_at ? ` · ${fmtDate(e.occurred_at)}` : ""}
                        </span>
                      </li>
                    ))}
                </ol>
              )}
            </section>
          </div>
        </>
      )}

      {sheet === "lift" && <LiftSheet live={source === "live"} onClose={() => setSheet(null)} onDone={area.reload} />}
      {sheet === "mode" && <ModeSheet adaptive={adaptive} live={source === "live"} onClose={() => setSheet(null)} onDone={area.reload} />}
    </main>
  );
}

function useAction(onDone: () => void, onClose: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onDone();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached."));
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, setError, run };
}

const OFFLINE = () => Promise.reject(new ApiError(409, "Governance rulings need the live API; the demo data cannot record them."));

function LiftSheet({ live, onClose, onDone }: { live: boolean; onClose(): void; onDone(): void }) {
  const [ref, setRef] = useState("");
  const { busy, error, setError, run } = useAction(onDone, onClose);
  return (
    <Sheet title="Lift the Track 1 freeze" subtitle="Governance only. Pillar 2 and 3 cannot override it." onClose={onClose}>
      <div className="field">
        <label htmlFor="gref">Governance reference</label>
        <input id="gref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. RI-5" />
        <span className="hint">The ruling that authorises the restart. It is recorded with the lift.</span>
      </div>
      <ActionError error={error} />
      <div className="actions">
        <button
          className="btn btn-primary"
          disabled={busy}
          onClick={() => (ref.trim() ? run(() => (live ? p4.liftTrack1(ref.trim()) : OFFLINE())) : setError(new ApiError(422, "Enter the governance reference.")))}
        >
          Lift freeze
        </button>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </Sheet>
  );
}

function ModeSheet({ adaptive, live, onClose, onDone }: { adaptive: boolean; live: boolean; onClose(): void; onDone(): void }) {
  const [ruling, setRuling] = useState({ ruling_ref: "", rule_type: "GOVERNANCE_RULING", signed_by: "", detail: "" });
  const { busy, error, setError, run } = useAction(onDone, onClose);
  const set = (k: keyof typeof ruling) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setRuling({ ...ruling, [k]: e.target.value });
  const submit = () => {
    if (!ruling.ruling_ref.trim() || !ruling.signed_by.trim()) return setError(new ApiError(422, "Enter the ruling reference and who signed it."));
    run(() => (live ? (adaptive ? p4.fallbackConventional(ruling) : p4.activateAdaptive(ruling)) : OFFLINE()));
  };
  return (
    <Sheet
      title={adaptive ? "Fall back to Conventional Mode" : "Activate Adaptive Mode"}
      subtitle={
        adaptive
          ? "Deactivation is not deletion: no rebuild, no book unwind, no contract change."
          : "Requires Gate G1. The CASS methodology is still PENDING, so this runs in the sandbox only."
      }
      onClose={onClose}
    >
      <div className="field">
        <label htmlFor="rref">Ruling reference</label>
        <input id="rref" value={ruling.ruling_ref} onChange={set("ruling_ref")} />
      </div>
      <div className="field">
        <label htmlFor="rsig">Signed by</label>
        <input id="rsig" value={ruling.signed_by} onChange={set("signed_by")} />
      </div>
      <div className="field">
        <label htmlFor="rdet">Detail</label>
        <textarea id="rdet" rows={3} value={ruling.detail} onChange={set("detail")} />
      </div>
      <ActionError error={error} />
      <div className="actions">
        <button className="btn btn-primary" disabled={busy} onClick={submit}>
          {adaptive ? "Fall back" : "Activate"}
        </button>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </Sheet>
  );
}
