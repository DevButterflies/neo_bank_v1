import { useState } from "react";
import { CircleAlert, CircleCheck, Settings2 } from "lucide-react";
import { demoBilan, demoBilanConfig } from "../api/areaFixtures";
import { bilanApi } from "../api/areas";
import type { Bilan, BilanConfig, BilanLine } from "../api/areas";
import { ApiError } from "../api/client";
import { ActionError, Sheet } from "../components/Sheet";
import { money } from "../lib/format";
import { useArea } from "../state/useArea";

interface Data {
  bilan: Bilan;
  config: BilanConfig;
}

const HORS_BILAN_LABEL: Record<string, string> = {
  garanties_recues: "Guarantees received",
  garanties_consenties: "Guarantees granted",
  niveau_requis_garanties: "Required guarantee level",
  el_pool: "EL Pool",
  ula_buffer: "ULA Buffer",
  liquidity_reserve: "Liquidity Reserve",
  rp_pool: "RP Pool",
  rwa: "Risk-weighted assets",
  tier_d_over_rwa: "Tier D / RWA",
};

const MOUVEMENT_LABEL: Record<string, string> = {
  decaisses: "Disbursed",
  remboursements: "Repaid",
  interets: "Interest",
  frais: "Fees",
  sinistres: "Losses",
  recouvrements: "Recoveries",
  radiations: "Write-offs",
};

const CONFIG_LABEL: Record<string, string> = {
  immobilisations: "Fixed assets",
  autres_creances: "Other receivables",
  apport_reserve: "Reserve contribution",
  resultat_anterieur: "Retained earnings",
  sid: "SID",
  tier_c: "Tier C borrowing",
  autres_emprunts: "Other borrowing",
  depots_clients: "Customer deposits",
  autres_dettes: "Other liabilities",
  tresorerie_ouverture: "Opening treasury",
};

const human = (k: string) => k.replace(/_/g, " ").replace(/^\w/, (m) => m.toUpperCase());

export function BilanPage() {
  const area = useArea<Data>(
    async () => ({ bilan: await bilanApi.get(), config: await bilanApi.config() }),
    () => ({ bilan: demoBilan(), config: demoBilanConfig() }),
  );
  const [editing, setEditing] = useState(false);
  const d = area.data;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Bilan</h1>
          <p>
            Balance sheet in the French chart of accounts, computed live from Pillar 3 and 4
            {d ? ` · as of ${new Date(d.bilan.as_of).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}` : ""}.
          </p>
        </div>
        <button className="btn" onClick={() => setEditing(true)} disabled={!d}>
          <Settings2 size={16} aria-hidden="true" />
          Opening configuration
        </button>
      </div>

      {area.error && <ActionError error={area.error} />}
      {!d && !area.error && <p className="empty">Computing the balance sheet…</p>}

      {d && (
        <>
          <div className="balance-check" data-ok={d.bilan.balanced}>
            {d.bilan.balanced ? <CircleCheck size={18} aria-hidden="true" /> : <CircleAlert size={18} aria-hidden="true" />}
            <p>
              <b>{d.bilan.balanced ? "Balanced." : "Not balanced."}</b> Actif {money(d.bilan.totaux.actif)} · Passif{" "}
              {money(d.bilan.totaux.passif)} · écart {money(d.bilan.ecart)}
              {!d.bilan.reliable && " · figures marked unreliable by the backend"}
            </p>
          </div>

          {d.bilan.warnings.length > 0 && (
            <ul className="warnings">
              {d.bilan.warnings.map((w) => (
                <li key={w}>
                  <CircleAlert size={15} aria-hidden="true" /> {w}
                </li>
              ))}
            </ul>
          )}

          <div className="two-col">
            <Side title="Actif" lines={d.bilan.actif} total={d.bilan.totaux.actif} />
            <Side title="Passif" lines={d.bilan.passif} total={d.bilan.totaux.passif} />
          </div>

          <div className="two-col">
            <section className="card" aria-labelledby="hb-title">
              <h2 className="card-title" id="hb-title">
                Hors bilan
              </h2>
              <p className="card-note">Memo items, reported alongside and never added to either side.</p>
              <dl className="facts">
                {Object.entries(d.bilan.hors_bilan).map(([k, v]) => (
                  <div className="facts-row" key={k}>
                    <dt>{HORS_BILAN_LABEL[k] ?? human(k)}</dt>
                    <dd>{v == null ? "–" : k === "tier_d_over_rwa" ? `${(v * 100).toFixed(1)}%` : money(v)}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section className="card" aria-labelledby="mv-title">
              <h2 className="card-title" id="mv-title">
                Movements and checks
              </h2>
              <dl className="facts">
                {Object.entries(d.bilan.mouvements)
                  .filter(([, v]) => typeof v === "number")
                  .map(([k, v]) => (
                    <div className="facts-row" key={k}>
                      <dt>{MOUVEMENT_LABEL[k] ?? human(k)}</dt>
                      <dd>{money(v as number)}</dd>
                    </div>
                  ))}
              </dl>
              <ul className="checks">
                {d.bilan.checks.map((c, i) => {
                  const ok = c.ok ?? c.passed ?? false;
                  return (
                    <li key={i} data-ok={ok}>
                      {ok ? <CircleCheck size={15} aria-hidden="true" /> : <CircleAlert size={15} aria-hidden="true" />}
                      {c.name ?? c.message ?? c.detail ?? `Check ${i + 1}`}
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>
        </>
      )}

      {editing && d && (
        <ConfigSheet
          config={d.config}
          live={area.live}
          onClose={() => setEditing(false)}
          onSaved={(config) => (area.live ? area.reload() : area.setData((x) => ({ ...x, config })))}
        />
      )}
    </main>
  );
}

function Side({ title, lines, total }: { title: string; lines: BilanLine[]; total: number }) {
  return (
    <section className="card card-flush" aria-labelledby={`side-${title}`}>
      <h2 className="card-title" id={`side-${title}`}>
        {title}
      </h2>
      <table className="table table-tight">
        <thead>
          <tr>
            <th>Compte</th>
            <th>Libellé</th>
            <th data-align="end">Montant</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => (
            <tr key={`${l.compte}-${l.libelle}`}>
              <td>{l.compte}</td>
              <td>{l.libelle}</td>
              <td data-align="end" data-negative={l.montant < 0 || undefined}>
                {money(l.montant)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={2}>Total {title.toLowerCase()}</td>
            <td data-align="end">{money(total)}</td>
          </tr>
        </tfoot>
      </table>
    </section>
  );
}

function ConfigSheet({
  config,
  live,
  onClose,
  onSaved,
}: {
  config: BilanConfig;
  live: boolean;
  onClose(): void;
  onSaved(c: BilanConfig): void;
}) {
  const numeric = Object.entries(config).filter(([, v]) => typeof v === "number") as [string, number][];
  const [values, setValues] = useState<Record<string, string>>(Object.fromEntries(numeric.map(([k, v]) => [k, String(v)])));
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const save = async () => {
    const patch: Record<string, number> = {};
    for (const [k, v] of numeric) if (Number(values[k]) !== v) patch[k] = Number(values[k]) || 0;
    if (!Object.keys(patch).length) return onClose();
    if (live && !token.trim()) return setError(new ApiError(422, "Enter the admin token. Every change leaves an audit row."));
    setBusy(true);
    setError(null);
    try {
      onSaved(live ? await bilanApi.saveConfig(patch, token.trim()) : { ...config, ...patch });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title="Opening configuration" subtitle="Values the ledger cannot know: opening balances and funding." onClose={onClose}>
      {numeric.map(([k]) => (
        <div className="field" key={k}>
          <label htmlFor={`cfg-${k}`}>{CONFIG_LABEL[k] ?? human(k)} (USD)</label>
          <input
            id={`cfg-${k}`}
            type="number"
            inputMode="decimal"
            value={values[k]}
            onChange={(e) => setValues({ ...values, [k]: e.target.value })}
          />
        </div>
      ))}
      <div className="field">
        <label htmlFor="cfg-token">Admin token</label>
        <input id="cfg-token" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} />
        <span className="hint">Sent as the X-Admin-Token header. Never stored.</span>
      </div>
      <ActionError error={error} />
      <div className="actions">
        <button className="btn btn-primary" disabled={busy} onClick={save}>
          Save changes
        </button>
        <button className="btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </Sheet>
  );
}
