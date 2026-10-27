import { useBilan } from "../data/hooks";
import { useSse } from "../components/shared/SseProvider";
import { Panel, StatLine } from "../components/shared/Atoms";
import { BilanColumn } from "../components/bilan/BilanColumn";
import {
  ACTIF_RUBRIQUES,
  PASSIF_RUBRIQUES,
  fmt,
} from "../components/bilan/bilanFormat";

const pct = (v) => (v === null || v === undefined ? "—" : `${fmt(v * 100)} %`);

const stamp = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "medium" });
};

export default function Bilan() {
  const { data: bilan, isLoading } = useBilan();
  const { connected } = useSse();

  const actif = bilan?.actif ?? [];
  const passif = bilan?.passif ?? [];
  const mouvements = bilan?.mouvements ?? {};
  const hors = bilan?.hors_bilan ?? {};
  const balanced = bilan?.balanced ?? true;
  const ecart = bilan?.ecart ?? 0;
  const checks = bilan?.checks ?? [];
  const warnings = bilan?.warnings ?? [];
  const reliable = bilan?.reliable ?? false;

  return (
    <div className="space-y-6 rise-in">
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-head text-xl font-medium">Bilan</h1>
          <p className="text-sm text-muted mt-0.5">
            Établi selon le plan comptable général — recalculé à chaque écriture Pillar 3 et Pillar 4.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-[11px] text-faint">Arrêté au</div>
            <div className="font-mono text-sm text-text">{stamp(bilan?.as_of)}</div>
          </div>
          <div className="text-right">
            <div className="text-[11px] text-faint">Écritures comptabilisées</div>
            <div className="font-mono text-sm text-text">{bilan?.sources?.p3_events ?? "—"}</div>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm border text-[11px] font-mono ${
              connected
                ? "border-ledger/30 bg-ledger/10 text-ledger"
                : "border-amber/30 bg-amber/10 text-amber"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full pulse-dot ${
                connected ? "bg-ledger" : "bg-amber"
              }`}
            />
            {connected ? "Live · SSE" : "Live · poll 5s"}
          </span>
        </div>
      </div>

      {isLoading && !bilan ? (
        <div className="bg-panel border border-line rounded-md p-10 text-center text-xs text-faint">
          Chargement du bilan…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-6">
            <BilanColumn
              side="Actif"
              lines={actif}
              rubriques={ACTIF_RUBRIQUES}
              total={bilan?.totaux?.actif ?? 0}
            />
            <BilanColumn
              side="Passif"
              lines={passif}
              rubriques={PASSIF_RUBRIQUES}
              total={bilan?.totaux?.passif ?? 0}
            />
          </div>

          <div
            className={`flex items-center justify-between gap-4 px-4 py-3 rounded-md border ${
              balanced ? "bg-ledger/10 border-ledger/30" : "bg-danger/10 border-danger/30"
            }`}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <span className={balanced ? "text-ledger" : "text-danger"}>
                {balanced ? "✓" : "✕"}
              </span>
              <span
                className={`text-sm font-medium ${balanced ? "text-ledger" : "text-danger"}`}
              >
                {balanced ? "Bilan équilibré" : "Bilan déséquilibré"}
              </span>
              <span className="text-xs text-muted truncate hidden sm:inline">
                — total général de l'actif et du passif sont égaux
              </span>
            </div>
            <div className="flex items-center gap-6 text-xs text-muted shrink-0">
              <span>
                Écart{" "}
                <span
                  className={`font-mono text-sm ${
                    balanced ? "text-ledger" : "text-danger"
                  }`}
                >
                  {fmt(ecart)}
                </span>
              </span>
              <span>
                Dernière mise à jour{" "}
                <span className="font-mono text-xs text-text">{stamp(bilan?.as_of)}</span>
              </span>
            </div>
          </div>

          <Panel
            title="Contrôles de cohérence"
            eyebrow="Un bilan équilibré ne prouve rien à lui seul — voici ce qui est vérifié"
            right={
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[11px] font-mono ${
                  reliable
                    ? "bg-ledger/10 text-ledger border-ledger/30"
                    : "bg-danger/10 text-danger border-danger/30"
                }`}
              >
                {reliable ? "FIABLE" : "NON FIABLE"}
              </span>
            }
          >
            {checks.length === 0 ? (
              <div className="text-xs text-faint">Aucun contrôle disponible.</div>
            ) : (
              <ul className="space-y-1.5">
                {checks.map((c) => (
                  <li key={c.id} className="flex items-start gap-2.5 text-xs">
                    <span className={c.ok ? "text-ledger" : "text-danger"}>
                      {c.ok ? "✓" : "✕"}
                    </span>
                    <span className="font-mono text-[11px] text-muted w-60 shrink-0">
                      {c.id}
                    </span>
                    <span className={c.ok ? "text-muted" : "text-danger"}>{c.detail}</span>
                  </li>
                ))}
              </ul>
            )}
            {warnings.length > 0 && (
              <div className="mt-4 border-t border-line/60 pt-3">
                <div className="text-[11px] text-faint tracking-wide mb-1.5">
                  Avertissements — décisions à trancher, jamais devinées
                </div>
                <ul className="space-y-1">
                  {warnings.map((w, i) => (
                    <li key={`${i}-${w}`} className="text-xs text-amber">
                      • {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Panel>

          <div className="grid grid-cols-2 gap-6">
            <Panel
              title="Mouvements de la période"
              eyebrow="Pillar 3 — écritures de trésorerie et de résultat"
            >
              <StatLine label="Décaissements (1) — déblocages" value={fmt(mouvements.decaisses)} />
              <StatLine label="Remboursements (2) — principal" value={fmt(mouvements.remboursements)} tone="ledger" />
              <StatLine label="Intérêts perçus (4)" value={fmt(mouvements.interets)} tone="ledger" />
              <StatLine label="Frais de dossier (6)" value={fmt(mouvements.frais)} />
              <StatLine label="Radiations — mises en perte (7)" value={fmt(mouvements.radiations)} tone={mouvements.radiations ? "danger" : "muted"} />
              <StatLine label="Recouvrements (8)" value={fmt(mouvements.recouvrements)} tone={mouvements.recouvrements ? "ledger" : "muted"} />
              <StatLine label="Trésorerie d'ouverture" value={fmt(mouvements.tresorerie_ouverture)} />
            </Panel>

            <Panel
              title="Éléments hors bilan"
              eyebrow="Mémorisation — n'entrent dans aucun des deux totaux"
            >
              <StatLine label="RWA (somme des EAD)" value={fmt(hors.rwa)} />
              <StatLine
                label="Tier D / RWA"
                value={pct(hors.tier_d_over_rwa)}
                tone={
                  typeof hors.tier_d_over_rwa === "number" && hors.tier_d_over_rwa < 0.12
                    ? "danger"
                    : "ledger"
                }
              />
              <StatLine label="Provision ULA (4285)" value={fmt(hors.ula_buffer)} />
              <StatLine label="Compte de résultat technique (RP Pool)" value={fmt(hors.rp_pool)} />
              <StatLine label="Réserve de liquidité" value={fmt(hors.liquidity_reserve)} />
              <StatLine label="EL Pool (buffer prudentiel)" value={fmt(hors.el_pool)} tone="amber" />
              <StatLine label="Garanties consenties" value={fmt(hors.garanties_consenties)} tone="amber" />
              <StatLine label="Garanties reçues" value={fmt(hors.garanties_recues)} tone="ledger" />
              <StatLine label="Niveau de garanties requis" value={fmt(hors.niveau_requis_garanties)} />
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
