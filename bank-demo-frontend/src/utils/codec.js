// The bank engine (P3/P4) serializes dataclasses/enums/datetimes/sets/tuples
// through tagged JSON markers so type survives the trip through SQLite.
// See "§12.1 The event codec" in the API reference.
//
// P1 demo state and P1 candidate rows are ALREADY plain JSON — do not run
// them through this. Only P3 and P4 GET responses need unwrapping.

/** Unwrap a single codec-tagged value into a display-safe primitive. */
export function asText(value, fallback = "—") {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "object") {
    if ("value" in value && "__enum__" in value) return String(value.value);
    if ("__dt__" in value) return String(value.__dt__);
    if ("__set__" in value) return value.__set__.map((v) => asText(v)).join(", ");
    if ("__tuple__" in value) return value.__tuple__.map((v) => asText(v)).join(", ");
    return JSON.stringify(value);
  }
  return String(value);
}

/**
 * Recursively unwrap an entire object graph returned by P3/P4, so nested
 * fields (audit rows, facility objects, ledger rows) can be rendered or
 * destructured normally without per-field asText() calls.
 */
export function unwrapDeep(value) {
  if (value === null || value === undefined) return value;

  if (Array.isArray(value)) {
    return value.map(unwrapDeep);
  }

  if (typeof value === "object") {
    if ("__enum__" in value && "value" in value) return value.value;
    if ("__dt__" in value) return value.__dt__;
    if ("__set__" in value) return value.__set__.map(unwrapDeep);
    if ("__tuple__" in value) return value.__tuple__.map(unwrapDeep);
    if ("__dc__" in value) {
      const { __dc__, ...rest } = value;
      const out = { __type: __dc__ };
      for (const k of Object.keys(rest)) out[k] = unwrapDeep(rest[k]);
      return out;
    }
    const out = {};
    for (const k of Object.keys(value)) out[k] = unwrapDeep(value[k]);
    return out;
  }

  return value;
}

/** Title-case a SNAKE_CASE or camelCase status/event string for display. */
export function humanize(str) {
  if (!str) return "";
  return String(str)
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function formatMoney(n, currency = "USD") {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `$${Math.round(n).toLocaleString()}`;
  }
}

export function formatPct(n, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}
