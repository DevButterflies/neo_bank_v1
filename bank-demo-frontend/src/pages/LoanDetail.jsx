import { useParams, Link } from "react-router-dom";
import { useDemoStatePoll, useCandidate, useFacility, useFacilityAudit } from "../data/hooks";
import { Panel, StatLine, StatusBadge } from "../components/shared/Atoms";
import { AmortizationTable } from "../components/loans/AmortizationTable";
import { BalanceChart } from "../components/loans/BalanceChart";
import { AuditTimeline } from "../components/loans/AuditTimeline";
import { formatMoney, unwrapDeep } from "../utils/codec";

export default function LoanDetail() {
  const { facilityId } = useParams();
  const { data: state } = useDemoStatePoll();
  const summary = (state?.candidates || []).find((c) => c.facility_id === facilityId);

  const { data: candidate } = useCandidate(summary?.id);
  const { data: facilityRaw } = useFacility(facilityId);
  const { data: auditRaw } = useFacilityAudit(facilityId);

  const facility = unwrapDeep(facilityRaw || {});

  if (!summary) {
    return (
      <div className="text-sm text-muted">
        Facility not found in the current session.{" "}
        <Link to="/loans" className="text-ledger hover:underline">
          Back to loans
        </Link>
      </div>
    );
  }

  const behavior = candidate?.payment_behavior;

  return (
    <div className="space-y-6 rise-in">
      <div>
        <Link to="/loans" className="text-xs text-faint hover:text-muted">
          ← All loans
        </Link>
        <div className="flex items-center gap-3 mt-1">
          <h1 className="font-head text-xl font-medium">{summary.display_name}</h1>
          <StatusBadge value={summary.status} label={summary.status} />
          {facility.veto_frozen && <StatusBadge value="frozen" label="veto frozen" />}
        </div>
        <p className="text-sm text-faint font-mono mt-0.5">{facilityId}</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <MiniStat label="Outstanding" value={formatMoney(summary.outstanding)} />
        <MiniStat label="Disbursed" value={formatMoney(behavior?.disbursed)} />
        <MiniStat label="Payments made" value={summary.payments_made ?? 0} />
        <MiniStat label="Collateral pledged" value={facility.collateral_count ?? facility.collateral_objects?.length ?? 0} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Panel title="Amortization schedule" eyebrow="Payment tracking">
          <AmortizationTable behavior={behavior} paymentsMade={summary.payments_made} />
        </Panel>
        <Panel title="Outstanding balance" eyebrow="Per-loan trend">
          <BalanceChart behavior={behavior} paymentsMade={summary.payments_made} />
          <div className="mt-3 pt-3 border-t border-line">
            <StatLine label="Interest rate" value={behavior ? `${(behavior.interest_rate_bps / 100).toFixed(2)}%` : "—"} />
            <StatLine label="Delinquent month" value={behavior?.delinquent_month ?? "—"} tone={behavior?.delinquent_month ? "amber" : "text"} />
            <StatLine label="Default month" value={behavior?.default_month ?? "—"} tone={behavior?.default_month ? "danger" : "text"} />
            <StatLine label="Recovered amount" value={formatMoney(behavior?.recovered_amount || 0)} />
          </div>
        </Panel>
      </div>

      <Panel title="Lifecycle & audit trail" eyebrow="Append-only — every action produces exactly one record">
        <AuditTimeline records={auditRaw} />
      </Panel>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="bg-panel border border-line rounded-md px-4 py-3">
      <div className="text-[11px] text-faint mb-1">{label}</div>
      <div className="font-mono text-lg text-text">{value}</div>
    </div>
  );
}
