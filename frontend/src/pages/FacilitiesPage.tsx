import { useEffect, useMemo, useState } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { demoFacilities, demoReconcile } from "../api/areaFixtures";
import type { FacilityDemo } from "../api/areaFixtures";
import { p3 } from "../api/areas";
import type { AuditRecord, Facility, FacilityAction, LedgerPosting, Posting, Reconcile } from "../api/areas";
import { ApiError } from "../api/client";
import type { Candidate } from "../api/types";
import { ActionError, Sheet } from "../components/Sheet";
import { StateLine } from "../components/StateLine";
import { DateRange, inRange, Pager, SearchField, SortHeader, TableEmpty, usePagedSort } from "../components/table/tableKit";
import type { LineStop } from "../components/StateLine";
import { money, productLabel } from "../lib/format";
import { useBoard } from "../state/board";
import { useArea } from "../state/useArea";

// Facility state strings are not enumerated in the schema; map what the API sends onto the lifecycle.
type Phase = "originated" | "performing" | "delinquent" | "defaulted" | "recovery" | "restructured" | "closed" | "other";

export function phaseOf(state: string): Phase {
  const s = state.toLowerCase();
  if (s.includes("clos")) return "closed";
  if (s.includes("restruct")) return "restructured";
  if (s.includes("recover")) return "recovery";
  if (s.includes("default") || s.includes("write")) return "defaulted";
  if (s.includes("delinq")) return "delinquent";
  if (s.includes("disburs") || s.includes("active") || s.includes("perform")) return "performing";
  if (s.includes("originat") || s.includes("open")) return "originated";
  return "other";
}

const PHASE_LABEL: Record<Phase, string> = {
  originated: "Originated",
  performing: "Performing",
  delinquent: "Delinquent",
  defaulted: "Defaulted",
  recovery: "Recovery",
  restructured: "Restructured",
  closed: "Closed",
  other: "Other",
};

/** What the admin can do from each phase; the API stays the authority and answers 409 otherwise. */
const ACTIONS: Record<Phase, FacilityAction[]> = {
  originated: [],
  performing: ["repayment", "mark-delinquent", "close"],
  delinquent: ["repayment", "mark-default", "restructure"],
  defaulted: ["recovery", "restructure"],
  recovery: ["recovery", "close"],
  restructured: ["repayment", "mark-delinquent", "close"],
  closed: [],
  other: ["repayment", "mark-delinquent", "mark-default", "restructure", "recovery", "close"],
};

const ACTION_LABEL: Record<FacilityAction, string> = {
  repayment: "Record repayment",
  "mark-delinquent": "Mark delinquent",
  "mark-default": "Mark defaulted",
  restructure: "Restructure",
  recovery: "Record recovery",
  close: "Close facility",
};

const NEXT_STATE: Record<FacilityAction, string | null> = {
  repayment: null,
  "mark-delinquent": "DELINQUENT",
  "mark-default": "DEFAULTED",
  restructure: "RESTRUCTURED",
  recovery: "RECOVERY",
  close: "CLOSED",
};

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const fmtDate = (iso: string | null | undefined) => (iso ? dateFmt.format(new Date(iso)) : "–");
const eventLabel = (t: string) => t.replace(/_/g, " ").toLowerCase().replace(/^\w/, (m) => m.toUpperCase());

interface Data extends FacilityDemo {
  reconcile: Reconcile;
}

export function FacilitiesPage() {
  const { board } = useBoard();
  const area = useArea<Data>(
    async () => {
      const [facilities, postings, ledger, reconcile] = await Promise.all([p3.facilities(), p3.postings(), p3.ledger(), p3.reconcile()]);
      return { facilities, postings, ledger, reconcile, audit: {} };
    },
    (b) => {
      const d = demoFacilities(b);
      return { ...d, reconcile: demoReconcile(d.postings, d.ledger) };
    },
  );
  const [tab, setTab] = useState<"facilities" | "ledger">("facilities");
  const [phase, setPhase] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const byFacility = useMemo(() => {
    const m = new Map<string, Candidate>();
    for (const c of board?.candidates ?? []) if (c.facility_id) m.set(c.facility_id, c);
    return m;
  }, [board]);

  const data = area.data;
  const counts = useMemo(() => {
    const c: Record<Phase, number> = { originated: 0, performing: 0, delinquent: 0, defaulted: 0, recovery: 0, restructured: 0, closed: 0, other: 0 };
    for (const f of data?.facilities ?? []) c[phaseOf(f.state)]++;
    return c;
  }, [data]);

  const stops: LineStop[] = [
    { id: "performing", name: "Performing", count: counts.performing + counts.originated, color: "var(--p3)" },
    { id: "delinquent", name: "Delinquent", count: counts.delinquent, color: "var(--p3)" },
    { id: "defaulted", name: "Defaulted", count: counts.defaulted, color: "var(--p4)" },
    { id: "recovery", name: "Recovery", count: counts.recovery, color: "var(--p3)" },
    { id: "closed", name: "Closed", count: counts.closed, color: "var(--p3)" },
  ];

  const open = data?.facilities.find((f) => f.facility_id === openId) ?? null;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Facilities</h1>
          <p>Approved loans executed by Pillar 3. Core banking is the system of record.</p>
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label="Facilities views">
        <button role="tab" aria-selected={tab === "facilities"} onClick={() => setTab("facilities")}>
          Facilities
        </button>
        <button role="tab" aria-selected={tab === "ledger"} onClick={() => setTab("ledger")}>
          Ledger and reconciliation
        </button>
      </div>

      {area.error && <ActionError error={area.error} />}
      {!data && !area.error && <p className="empty">Loading facilities…</p>}

      {data && tab === "facilities" && (
        <>
          <section className="map map-compact" aria-label="Facility lifecycle">
            <StateLine
              label="Filter by lifecycle state"
              stops={stops}
              spur={{ id: "restructured", name: "Restructured", count: counts.restructured, color: "var(--p3)" }}
              selected={phase}
              onSelect={setPhase}
            />
          </section>

          <FacilityTable
            facilities={data.facilities}
            byFacility={byFacility}
            phase={phase}
            onPhase={setPhase}
            openId={openId}
            onOpen={setOpenId}
          />
        </>
      )}

      {data && tab === "ledger" && <LedgerView postings={data.postings} ledger={data.ledger} reconcile={data.reconcile} />}

      {open && data && (
        <FacilitySheet
          facility={open}
          candidate={byFacility.get(open.facility_id)}
          demoAudit={data.audit[open.facility_id]}
          postings={data.postings.filter((p) => p.facility_id === open.facility_id)}
          live={area.live}
          onClose={() => setOpenId(null)}
          onDone={(action, amount) => {
            if (area.live) return area.reload();
            // offline: apply the transition locally so the demo can be driven
            const now = new Date().toISOString();
            area.setData((d) => ({
              ...d,
              facilities: d.facilities.map((f) =>
                f.facility_id === open.facility_id ? { ...f, state: NEXT_STATE[action] ?? f.state, updated_at: now } : f,
              ),
              postings:
                amount > 0
                  ? [...d.postings, { event_id: `evt-${Date.now()}`, facility_id: open.facility_id, event_type: action.toUpperCase().replace(/-/g, "_"), amount, currency: "USD", occurred_at: now, routes_allocation_question_to_p4: action !== "recovery", memo: null }]
                  : d.postings,
              audit: {
                ...d.audit,
                [open.facility_id]: [
                  ...(d.audit[open.facility_id] ?? []),
                  { record_id: `aud-${Date.now()}`, facility_id: open.facility_id, event_type: action.toUpperCase().replace(/-/g, "_"), timestamp: now, actor_reference: "ADMIN-1", p2_packet_version: "3.0", maturity_stage: "SANDBOX", brr_pd_grid_version: "BRRPD-2.5.1", p4_veto_status: open.veto_frozen ? "FROZEN" : "CLEAR" },
                ],
              },
            }));
          }}
        />
      )}
    </main>
  );
}

function LedgerView({ postings, ledger, reconcile }: { postings: Posting[]; ledger: LedgerPosting[]; reconcile: Reconcile }) {
  const unmatched = new Set(reconcile.unmatched_p3_event_ids);
  return (
    <>
      <section className="recon" aria-label="Reconciliation">
        <div className="recon-figures">
          <div>
            <p className="recon-label">Pillar 3 posting events</p>
            <p className="recon-value">{money(reconcile.p3_event_total)}</p>
          </div>
          <div>
            <p className="recon-label">Core-banking ledger</p>
            <p className="recon-value">{money(reconcile.core_banking_total)}</p>
          </div>
          <div>
            <p className="recon-label">Discrepancy</p>
            <p className="recon-value">{money(reconcile.discrepancy)}</p>
          </div>
        </div>
        <p className="recon-status" data-ok={reconcile.within_tolerance}>
          {reconcile.within_tolerance ? <CircleCheck size={16} aria-hidden="true" /> : <CircleAlert size={16} aria-hidden="true" />}
          {reconcile.within_tolerance
            ? `Reconciled within tolerance (${money(reconcile.tolerance)}).`
            : `${reconcile.unmatched_p3_event_ids.length} Pillar 3 events do not match the ledger. The ledger wins; fix the events.`}
        </p>
      </section>

      <section className="table-card" aria-label="Postings">
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Facility</th>
                <th>Type</th>
                <th data-align="end">Amount</th>
                <th>Ledger posting</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {postings
                .slice()
                .reverse()
                .slice(0, 50)
                .map((p) => {
                  const posted = ledger.find((l) => l.source_event_id === p.event_id);
                  return (
                    <tr key={p.event_id}>
                      <td>{p.event_id}</td>
                      <td>{p.facility_id}</td>
                      <td>
                        {eventLabel(p.event_type)}
                        {p.routes_allocation_question_to_p4 && <span className="row-meta">Allocation routed to Pillar 4</span>}
                      </td>
                      <td data-align="end" className="amount-cell">
                        {money(p.amount)}
                      </td>
                      <td>
                        {posted && !unmatched.has(p.event_id) ? (
                          posted.posting_id
                        ) : (
                          <span className="frozen">
                            <CircleAlert size={13} aria-hidden="true" /> Not on the ledger
                          </span>
                        )}
                      </td>
                      <td>{fmtDate(p.occurred_at)}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          {postings.length === 0 && <p className="table-empty">No posting events yet.</p>}
        </div>
        {postings.length > 50 && <p className="pager">Showing the 50 most recent of {postings.length} events.</p>}
      </section>
    </>
  );
}

function FacilitySheet({
  facility,
  candidate,
  demoAudit,
  postings,
  live,
  onClose,
  onDone,
}: {
  facility: Facility;
  candidate: Candidate | undefined;
  demoAudit: AuditRecord[] | undefined;
  postings: Posting[];
  live: boolean;
  onClose(): void;
  onDone(action: FacilityAction, amount: number): void;
}) {
  const phase = phaseOf(facility.state);
  const [action, setAction] = useState<FacilityAction | null>(null);
  const [interest, setInterest] = useState("");
  const [principal, setPrincipal] = useState("");
  const [amount, setAmount] = useState("");
  const [authorised, setAuthorised] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [liveAudit, setLiveAudit] = useState<AuditRecord[] | null>(null);

  // the live audit trail is fetched per facility; refetch after an action changes the state
  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    p3.audit(facility.facility_id).then(
      (a) => !cancelled && setLiveAudit(a),
      () => !cancelled && setLiveAudit([]),
    );
    return () => {
      cancelled = true;
    };
  }, [live, facility.facility_id, facility.state]);
  const audit = (live ? liveAudit : demoAudit) ?? [];

  const submit = async () => {
    if (!action) return;
    const n = (v: string) => Number(v) || 0;
    let params: Record<string, string | number> = {};
    let moved = 0;
    if (action === "repayment") {
      if (n(interest) + n(principal) <= 0) return setError(new ApiError(422, "Enter the interest and principal received."));
      params = { interest_amount: n(interest), principal_amount: n(principal), currency: "USD" };
      moved = n(interest) + n(principal);
    } else if (action === "mark-default") {
      params = { loss_amount: n(amount), currency: "USD" };
      moved = n(amount);
    } else if (action === "recovery") {
      if (n(amount) <= 0) return setError(new ApiError(422, "Enter the amount recovered."));
      params = { recovered_amount: n(amount), currency: "USD" };
      moved = n(amount);
    } else if (action === "restructure" && !authorised) {
      return setError(new ApiError(422, "Restructuring needs your workout authorisation, separate from the original approval."));
    }
    setBusy(true);
    setError(null);
    try {
      if (live) await p3.act(action, facility.facility_id, params, action === "restructure");
      onDone(action, moved);
      setAction(null);
      setInterest("");
      setPrincipal("");
      setAmount("");
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, "The API could not be reached."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title={facility.facility_id} subtitle={`${candidate?.display_name ?? "Facility"} · ${PHASE_LABEL[phase] === "Other" ? facility.state : PHASE_LABEL[phase]}`} onClose={onClose}>
      <section className="panel-section">
        <h3>Facility</h3>
        <dl className="facts">
          <dt>Borrower</dt>
          <dd>{candidate?.display_name ?? "–"}</dd>
          <dt>Product</dt>
          <dd>{candidate ? productLabel(candidate.product) : "–"}</dd>
          <dt>Approved amount</dt>
          <dd>{candidate ? money(candidate.requested_amount) : "–"}</dd>
          <dt>Collateral objects</dt>
          <dd>{facility.collateral_count}</dd>
          <dt>Origination packet</dt>
          <dd>{facility.origination_packet_id ?? "–"}</dd>
          <dt>Veto</dt>
          <dd>{facility.veto_frozen ? "Frozen · Track 2" : "Clear"}</dd>
        </dl>
      </section>

      {phase === "originated" && (
        <p className="zone-note">Opened and waiting for disbursement. Disburse it from the origination line.</p>
      )}

      {ACTIONS[phase].length > 0 && (
        <section className="panel-section">
          <h3>Lifecycle action</h3>
          <div className="choice-row" role="radiogroup" aria-label="Action">
            {ACTIONS[phase].map((a) => (
              <button
                key={a}
                role="radio"
                aria-checked={action === a}
                className="choice"
                onClick={() => {
                  setAction(a);
                  setError(null);
                }}
              >
                {ACTION_LABEL[a]}
              </button>
            ))}
          </div>
          {action === "repayment" && (
            <div className="grid-2 action-fields">
              <div className="field">
                <label htmlFor="interest">Interest (USD)</label>
                <input id="interest" type="number" inputMode="decimal" value={interest} onChange={(e) => setInterest(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="principal">Principal (USD)</label>
                <input id="principal" type="number" inputMode="decimal" value={principal} onChange={(e) => setPrincipal(e.target.value)} />
              </div>
            </div>
          )}
          {(action === "mark-default" || action === "recovery") && (
            <div className="field action-fields">
              <label htmlFor="amount">{action === "recovery" ? "Amount recovered (USD)" : "Loss amount (USD)"}</label>
              <input id="amount" type="number" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <span className="hint">
                {action === "recovery"
                  ? "Collateral-leg proceeds. Pillar 4 credits the EL Pool and ULA Buffer separately."
                  : "The guarantee leg is settled by Pillar 4; this records the collateral leg only."}
              </span>
            </div>
          )}
          {action === "restructure" && (
            <label className="check action-fields">
              <input type="checkbox" checked={authorised} onChange={(e) => setAuthorised(e.target.checked)} />I authorise this
              workout. It is a separate act from the original approval.
            </label>
          )}
          {action === "close" && <p className="zone-note action-fields">Close only after final settlement.</p>}
          {action === "mark-delinquent" && <p className="zone-note action-fields">Pillar 3 marks and routes; Pillar 4 decides provisioning.</p>}
          <ActionError error={error} />
          {action && (
            <div className="actions action-fields">
              <button className="btn btn-primary" disabled={busy} onClick={submit}>
                {ACTION_LABEL[action]}
              </button>
              <button className="btn" onClick={() => setAction(null)}>
                Cancel
              </button>
            </div>
          )}
        </section>
      )}

      <section className="panel-section">
        <h3>Audit trail</h3>
        {audit.length === 0 ? (
          <p className="empty">{live && liveAudit == null ? "Loading…" : "No audit records yet."}</p>
        ) : (
          <ol className="trail">
            {audit
              .slice()
              .reverse()
              .map((r) => (
                <li key={r.record_id}>
                  <span className="trail-mark" aria-hidden="true" />
                  <span className="trail-event">{eventLabel(r.event_type)}</span>
                  <span className="trail-meta">
                    {fmtDate(r.timestamp)} · {r.actor_reference}
                    {r.p4_veto_status && String(r.p4_veto_status).toUpperCase().includes("FROZ") ? " · veto frozen" : ""}
                  </span>
                </li>
              ))}
          </ol>
        )}
      </section>

      <section className="panel-section">
        <h3>Postings</h3>
        {postings.length === 0 ? (
          <p className="empty">No postings yet.</p>
        ) : (
          <dl className="facts">
            {postings
              .slice(-8)
              .reverse()
              .map((p) => (
                <div className="facts-row" key={p.event_id}>
                  <dt>
                    {eventLabel(p.event_type)} · {fmtDate(p.occurred_at)}
                  </dt>
                  <dd>{money(p.amount)}</dd>
                </div>
              ))}
          </dl>
        )}
      </section>
    </Sheet>
  );
}

type FacilitySort = "facility" | "borrower" | "state" | "amount" | "collateral" | "updated";
const PHASE_ORDER: Phase[] = ["originated", "performing", "delinquent", "defaulted", "recovery", "restructured", "closed", "other"];

/** The facility list with the same filters, sorting and pagination as the pipeline table. */
function FacilityTable({
  facilities,
  byFacility,
  phase,
  onPhase,
  openId,
  onOpen,
}: {
  facilities: Facility[];
  byFacility: Map<string, Candidate>;
  phase: string | null;
  onPhase(p: string | null): void;
  openId: string | null;
  onOpen(id: string): void;
}) {
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return facilities.filter((f) => {
      const p = phaseOf(f.state);
      const borrower = byFacility.get(f.facility_id)?.display_name ?? "";
      return (
        (!phase || p === phase || (phase === "performing" && p === "originated")) &&
        (!q || f.facility_id.toLowerCase().includes(q) || borrower.toLowerCase().includes(q)) &&
        inRange(f.updated_at, from, to)
      );
    });
  }, [facilities, byFacility, phase, query, from, to]);

  const value = (f: Facility, key: FacilitySort): string | number => {
    switch (key) {
      case "facility":
        return f.facility_id;
      case "borrower":
        return (byFacility.get(f.facility_id)?.display_name ?? "~").toLowerCase();
      case "state":
        return PHASE_ORDER.indexOf(phaseOf(f.state));
      case "amount":
        return byFacility.get(f.facility_id)?.requested_amount ?? -1;
      case "collateral":
        return f.collateral_count;
      case "updated":
        return f.updated_at;
    }
  };
  const t = usePagedSort<Facility, FacilitySort>(filtered, { key: "updated", dir: "desc" }, value, `${query}|${from}|${to}|${phase}`);
  const filtering = query !== "" || from !== "" || to !== "" || phase != null;
  const clear = () => {
    setQuery("");
    setFrom("");
    setTo("");
    onPhase(null);
  };

  return (
    <section className="table-card" aria-label="Facilities">
      <div className="filters">
        <SearchField id="fac-q" value={query} onChange={setQuery} placeholder="Facility or borrower" />
        <div className="field">
          <label htmlFor="fac-state">State</label>
          <select id="fac-state" value={phase ?? "all"} onChange={(e) => onPhase(e.target.value === "all" ? null : e.target.value)}>
            <option value="all">All states</option>
            {(["performing", "delinquent", "defaulted", "recovery", "restructured", "closed"] as Phase[]).map((p) => (
              <option key={p} value={p}>
                {PHASE_LABEL[p]}
              </option>
            ))}
          </select>
        </div>
        <DateRange idPrefix="fac-updated" label="Updated" from={from} to={to} onFrom={setFrom} onTo={setTo} />
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
              <SortHeader sortKey="facility" label="Facility" sort={t.sort} onSort={t.setSort} ascFirst />
              <SortHeader sortKey="borrower" label="Borrower" sort={t.sort} onSort={t.setSort} ascFirst />
              <SortHeader sortKey="state" label="State" sort={t.sort} onSort={t.setSort} ascFirst />
              <SortHeader sortKey="amount" label="Amount" sort={t.sort} onSort={t.setSort} align="end" />
              <SortHeader sortKey="collateral" label="Collateral" sort={t.sort} onSort={t.setSort} align="end" />
              <SortHeader sortKey="updated" label="Updated" sort={t.sort} onSort={t.setSort} />
            </tr>
          </thead>
          <tbody>
            {t.shown.map((f) => {
              const c = byFacility.get(f.facility_id);
              const p = phaseOf(f.state);
              return (
                <tr key={f.facility_id} aria-current={openId === f.facility_id}>
                  <td>
                    <button className="row-main" onClick={() => onOpen(f.facility_id)}>
                      <span className="row-name">{f.facility_id}</span>
                      <span className="row-meta">{c ? productLabel(c.product) : "Pillar 3 facility"}</span>
                    </button>
                  </td>
                  <td>{c?.display_name ?? "–"}</td>
                  <td>
                    <span className="status" data-status={p}>
                      <i aria-hidden="true" />
                      {p === "other" ? f.state : PHASE_LABEL[p]}
                    </span>
                    {f.veto_frozen && (
                      <span className="frozen">
                        <i aria-hidden="true" />
                        Frozen · Track 2
                      </span>
                    )}
                  </td>
                  <td data-align="end" className="amount-cell">
                    {c ? money(c.requested_amount) : "–"}
                  </td>
                  <td data-align="end">{f.collateral_count}</td>
                  <td>{fmtDate(f.updated_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {t.shown.length === 0 && (
          <TableEmpty filtering={filtering} empty="No facilities yet. Disburse an approved candidate to open one." onClear={clear} />
        )}
      </div>

      <Pager
        idPrefix="fac"
        noun="facilities"
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
