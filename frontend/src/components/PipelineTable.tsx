import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Candidate, CandidateStatus } from "../api/types";
import { money, pct, productLabel } from "../lib/format";
import { DateRange, inRange, Pager, SearchField, SortHeader, TableEmpty, usePagedSort } from "./table/tableKit";
import { ZoneMark } from "./ZoneMark";

export type StatusFilter = CandidateStatus | "all";

const STATUS_LABEL: Record<CandidateStatus, string> = {
  new: "New",
  submitted: "Scored",
  approved: "Approved",
  disbursed: "Disbursed",
  rejected: "Rejected",
};
const STATUS_ORDER: Record<CandidateStatus, number> = { new: 0, submitted: 1, approved: 2, disbursed: 3, rejected: 4 };

type SortKey = "name" | "status" | "amount" | "brr" | "created";

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });

const sortValue = (c: Candidate, key: SortKey): string | number => {
  switch (key) {
    case "name":
      return c.display_name.toLowerCase();
    case "status":
      return STATUS_ORDER[c.status];
    case "amount":
      return c.requested_amount;
    case "brr":
      return c.p2_brr ?? 99;
    case "created":
      return c.created_at;
  }
};

interface Props {
  candidates: Candidate[];
  status: StatusFilter;
  onStatus(s: StatusFilter): void;
  selectedId: string | undefined;
  moved: Set<string>;
  frozen: Set<string>;
  /** the row action for a candidate (Submit, Decide, Disburse), or nothing */
  actionFor(c: Candidate): ReactNode;
  onOpen(id: string): void;
}

export function PipelineTable({ candidates, status, onStatus, selectedId, moved, frozen, actionFor, onOpen }: Props) {
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return candidates.filter(
      (c) =>
        (status === "all" || c.status === status) &&
        (!q || c.display_name.toLowerCase().includes(q) || (c.national_id ?? "").toLowerCase().includes(q)) &&
        inRange(c.created_at, from, to),
    );
  }, [candidates, status, query, from, to]);

  const t = usePagedSort<Candidate, SortKey>(filtered, { key: "created", dir: "desc" }, sortValue, `${query}|${from}|${to}|${status}`);
  const filtering = query !== "" || from !== "" || to !== "" || status !== "all";

  const clear = () => {
    setQuery("");
    setFrom("");
    setTo("");
    onStatus("all");
  };

  return (
    <section className="table-card" aria-label="Candidates">
      <div className="filters">
        <SearchField id="f-q" value={query} onChange={setQuery} placeholder="Borrower or national ID" />
        <div className="field">
          <label htmlFor="f-status">Station</label>
          <select id="f-status" value={status} onChange={(e) => onStatus(e.target.value as StatusFilter)}>
            <option value="all">All stations</option>
            {(Object.keys(STATUS_LABEL) as CandidateStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </div>
        <DateRange idPrefix="f-created" label="Created" from={from} to={to} onFrom={setFrom} onTo={setTo} />
        {filtering && (
          <button className="btn btn-small filters-clear" onClick={clear}>
            Clear filters
          </button>
        )}
      </div>

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <SortHeader sortKey="name" label="Borrower" sort={t.sort} onSort={t.setSort} ascFirst />
              <SortHeader sortKey="status" label="Station" sort={t.sort} onSort={t.setSort} ascFirst />
              <SortHeader sortKey="amount" label="Amount" sort={t.sort} onSort={t.setSort} align="end" />
              <SortHeader sortKey="brr" label="BRR" sort={t.sort} onSort={t.setSort} align="end" />
              <th data-align="end">PD</th>
              <th>Zone</th>
              <SortHeader sortKey="created" label="Created" sort={t.sort} onSort={t.setSort} />
              <th>
                <span className="sr-only">Action</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {t.shown.map((c) => {
              const isFrozen = c.facility_id != null && frozen.has(c.facility_id);
              return (
                <tr key={c.id} aria-current={selectedId === c.id} data-moved={moved.has(c.id)} data-void={c.status === "rejected"}>
                  <td>
                    <button className="row-main" onClick={() => onOpen(c.id)}>
                      <span className="row-name">{c.display_name}</span>
                      <span className="row-meta">{productLabel(c.product)}</span>
                    </button>
                  </td>
                  <td>
                    <span className="status" data-status={c.status}>
                      <i aria-hidden="true" />
                      {STATUS_LABEL[c.status]}
                    </span>
                    {isFrozen && (
                      <span className="frozen">
                        <i aria-hidden="true" />
                        Frozen · Track 2
                      </span>
                    )}
                  </td>
                  <td data-align="end" className="amount-cell">
                    <span className="amount">{money(c.requested_amount)}</span>
                  </td>
                  <td data-align="end">{c.p2_brr ?? "–"}</td>
                  <td data-align="end">{pct(c.p2_pd)}</td>
                  <td>{c.p2_zone ? <ZoneMark zone={c.p2_zone} /> : <span className="muted">Not scored</span>}</td>
                  <td>
                    <time dateTime={c.created_at}>{dateFmt.format(new Date(c.created_at))}</time>
                  </td>
                  <td data-align="end" className="action-cell">
                    {actionFor(c)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {t.shown.length === 0 && <TableEmpty filtering={filtering} empty="No candidates yet. Add one with New candidate." onClear={clear} />}
      </div>

      <Pager
        idPrefix="f"
        noun="candidates"
        page={t.page}
        pages={t.pages}
        total={t.total}
        pageSize={t.pageSize}
        onPage={t.setPage}
        onPageSize={t.setPageSize}
      />
    </section>
  );
}
