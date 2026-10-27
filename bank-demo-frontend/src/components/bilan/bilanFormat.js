/** Pure helpers and rubrique layout for the Bilan screen.
 *
 *  Kept out of BilanColumn.jsx on purpose: `react/only-export-components`
 *  (see .oxlintrc.json) flags any non-component export from a component file.
 *  This module exports no component, so it is exempt.
 */

/** French accounting format — 102 849,36 (space thousands, comma decimals,
 *  no currency symbol), exactly as a plan-comptable balance sheet prints it. */
export const fmt = (n) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(n));
};

/** Rubriques of the classic French plan comptable. The backend returns a flat
 *  list of lines; grouping happens client-side so no API shape changes. */
export const ACTIF_RUBRIQUES = [
  { key: "imm", title: "Actif immobilisé", comptes: ["2180"] },
  { key: "cre", title: "Créances", comptes: ["4110", "4190"] },
  { key: "tre", title: "Trésorerie", comptes: ["5120"] },
];

export const PASSIF_RUBRIQUES = [
  { key: "cap", title: "Capitaux propres", comptes: ["1010", "1180", "1190"] },
  { key: "pro", title: "Provisions pour risques et aléas", comptes: ["4280"] },
  { key: "det", title: "Dettes", comptes: ["2670", "4210", "4260"] },
];

/** Bucket the backend's flat line list into the rubriques above, in rubrique
 *  order, appending an "Autres" bucket for any compte the table doesn't claim. */
export function groupLines(lines, rubriques) {
  const claimed = new Set();
  const groups = rubriques.map((rubrique) => {
    const rows = rubrique.comptes
      .map((code) => lines.find((line) => line.compte === code))
      .filter(Boolean);
    rows.forEach((row) => claimed.add(row.compte));
    return {
      ...rubrique,
      rows,
      total: rows.reduce((sum, row) => sum + Number(row.montant || 0), 0),
    };
  });

  const unclaimed = lines.filter((line) => !claimed.has(line.compte));
  if (unclaimed.length) {
    groups.push({
      key: "aut",
      title: "Autres",
      rows: unclaimed,
      total: unclaimed.reduce((sum, row) => sum + Number(row.montant || 0), 0),
    });
  }
  return groups;
}
