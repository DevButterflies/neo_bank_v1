import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from "lucide-react";

export type SortDir = "asc" | "desc";
export interface Sort<K extends string> {
  key: K;
  dir: SortDir;
}

export const PAGE_SIZES = [10, 25, 50];

/** Sorting and pagination over an already-filtered list; any change to `resetKey` returns to page 1. */
export function usePagedSort<T, K extends string>(
  rows: T[],
  initial: Sort<K>,
  value: (row: T, key: K) => string | number,
  resetKey: string,
) {
  const [sort, setSort] = useState<Sort<K>>(initial);
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [page, setPage] = useState(1);

  useEffect(() => setPage(1), [resetKey, pageSize, sort.key, sort.dir]);

  const sorted = useMemo(() => {
    const dir = sort.dir === "asc" ? 1 : -1;
    return rows.slice().sort((a, b) => {
      const va = value(a, sort.key);
      const vb = value(b, sort.key);
      return va < vb ? -dir : va > vb ? dir : 0;
    });
    // value is a stable mapping supplied by the caller
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pages);
  return {
    sort,
    setSort,
    pageSize,
    setPageSize,
    page: current,
    setPage,
    pages,
    total: sorted.length,
    shown: sorted.slice((current - 1) * pageSize, current * pageSize),
  };
}

/** A sortable column header; a new column starts descending, except text columns passed as `ascFirst`. */
export function SortHeader<K extends string>({
  sortKey,
  label,
  sort,
  onSort,
  align,
  ascFirst,
}: {
  sortKey: K;
  label: string;
  sort: Sort<K>;
  onSort(s: Sort<K>): void;
  align?: "end";
  ascFirst?: boolean;
}) {
  const active = sort.key === sortKey;
  const next: SortDir = active ? (sort.dir === "asc" ? "desc" : "asc") : ascFirst ? "asc" : "desc";
  return (
    <th aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} data-align={align}>
      <button className="th-sort" onClick={() => onSort({ key: sortKey, dir: next })}>
        {label}
        {active && (sort.dir === "asc" ? <ArrowUp size={13} aria-hidden="true" /> : <ArrowDown size={13} aria-hidden="true" />)}
      </button>
    </th>
  );
}

export function SearchField({ id, value, onChange, placeholder }: { id: string; value: string; onChange(v: string): void; placeholder: string }) {
  return (
    <div className="field filter-search">
      <label htmlFor={id}>Search</label>
      <span className="input-icon">
        <Search size={15} aria-hidden="true" />
        <input id={id} type="search" placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
      </span>
    </div>
  );
}

/** From/to date inputs on one field label pair; values are yyyy-mm-dd strings. */
export function DateRange({
  idPrefix,
  label,
  from,
  to,
  onFrom,
  onTo,
}: {
  idPrefix: string;
  label: string;
  from: string;
  to: string;
  onFrom(v: string): void;
  onTo(v: string): void;
}) {
  return (
    <>
      <div className="field">
        <label htmlFor={`${idPrefix}-from`}>{label} from</label>
        <input id={`${idPrefix}-from`} type="date" value={from} max={to || undefined} onChange={(e) => onFrom(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={`${idPrefix}-to`}>{label} to</label>
        <input id={`${idPrefix}-to`} type="date" value={to} min={from || undefined} onChange={(e) => onTo(e.target.value)} />
      </div>
    </>
  );
}

export const inRange = (iso: string, from: string, to: string) => {
  const day = iso.slice(0, 10);
  return (!from || day >= from) && (!to || day <= to);
};

/** Page numbers with the ends and a window around the current page, gaps shown as an ellipsis. */
function pageList(current: number, pages: number): (number | "gap")[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const keep = new Set([1, pages, current - 1, current, current + 1]);
  const out: (number | "gap")[] = [];
  for (let n = 1; n <= pages; n++) {
    if (keep.has(n)) out.push(n);
    else if (out[out.length - 1] !== "gap") out.push("gap");
  }
  return out;
}

export function Pager({
  idPrefix,
  noun,
  page,
  pages,
  total,
  pageSize,
  onPage,
  onPageSize,
}: {
  idPrefix: string;
  noun: string;
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPage(n: number): void;
  onPageSize(n: number): void;
}) {
  return (
    <div className="pager">
      <p aria-live="polite">
        {total === 0 ? `0 ${noun}` : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}
      </p>
      <div className="field pager-size">
        <label htmlFor={`${idPrefix}-size`}>Rows</label>
        <select id={`${idPrefix}-size`} value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
          {PAGE_SIZES.map((n) => (
            <option key={n}>{n}</option>
          ))}
        </select>
      </div>
      <nav className="pager-pages" aria-label="Pages">
        <button className="icon-btn" disabled={page === 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
          <ChevronLeft size={17} aria-hidden="true" />
        </button>
        {pageList(page, pages).map((n, i) =>
          n === "gap" ? (
            <span key={`gap-${i}`} className="page-gap" aria-hidden="true">
              …
            </span>
          ) : (
            <button key={n} className="page-btn" aria-current={n === page ? "page" : undefined} onClick={() => onPage(n)}>
              {n}
            </button>
          ),
        )}
        <button className="icon-btn" disabled={page === pages} onClick={() => onPage(page + 1)} aria-label="Next page">
          <ChevronRight size={17} aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
}

/** The empty state under a table: explains why and offers the way out. */
export function TableEmpty({ filtering, empty, onClear }: { filtering: boolean; empty: ReactNode; onClear(): void }) {
  return (
    <div className="table-empty">
      <p>{filtering ? "Nothing matches these filters." : empty}</p>
      {filtering && (
        <button className="btn btn-small" onClick={onClear}>
          Clear filters
        </button>
      )}
    </div>
  );
}
