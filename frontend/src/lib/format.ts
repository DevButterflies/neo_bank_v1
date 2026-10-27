import type { DecisioningZone } from "../api/types";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const money = (n: number | null | undefined) => (n == null ? "–" : usd.format(n));
export const pct = (n: number | null | undefined) => (n == null ? "–" : `${(n * 100).toFixed(1)}%`);

export const PRODUCT_LABELS: Record<string, string> = {
  invoice_discounting: "Invoice discounting",
  supply_chain_finance: "Supply chain finance",
  working_capital_line: "Working capital line",
  term_loan: "Term loan",
  growth_loan: "Growth loan",
  auto_loan: "Auto loan",
};

export const productLabel = (p: string) =>
  PRODUCT_LABELS[p.toLowerCase()] ?? p.replace(/_/g, " ").replace(/^\w/, (m) => m.toUpperCase());

export const ZONES: Record<DecisioningZone, { label: string; color: string; note: string }> = {
  AUTO_APPROVE: {
    label: "Auto approve",
    color: "var(--p2)",
    note: "The model recommends approval. Your approval is still required before a facility opens.",
  },
  AUGMENTED_DECISION: {
    label: "Augmented",
    color: "var(--p3)",
    note: "The model scores the case; weigh it with your own judgement before deciding.",
  },
  MANUAL_REVIEW: {
    label: "Manual review",
    color: "var(--p4)",
    note: "The model defers to you: review the borrower in full before deciding.",
  },
};
