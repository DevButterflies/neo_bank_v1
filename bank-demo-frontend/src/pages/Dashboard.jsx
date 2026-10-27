import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { useDemoStatePoll, useP4Capital, useP4Adequacy, useP4Ifrs9 } from "../data/hooks";
import { useKpiHistory } from "../data/useKpiHistory";
import { Panel } from "../components/shared/Atoms";
import { KpiCard } from "../components/kpi/KpiCard";
import { RatioGauge } from "../components/kpi/RatioGauge";
import { PortfolioDonut } from "../components/kpi/PortfolioDonut";
import { BalancePanel } from "../components/kpi/BalancePanel";
import { formatMoney, unwrapDeep } from "../utils/codec";

export default function Dashboard() {
  const { data: state } = useDemoStatePoll();
  const { data: capital } = useP4Capital();
  const { data: adequacy } = useP4Adequacy();
  const { data: ifrs9raw } = useP4Ifrs9();
  const history = useKpiHistory(state);

  const candidates = state?.candidates || [];
  const totalOutstanding = candidates
    .filter((c) => ["disbursed", "delinquent", "defaulted"].includes(c.status))
    .reduce((s, c) => s + (c.outstanding || 0), 0);
  const activeCount = candidates.filter((c) => ["disbursed", "delinquent"].includes(c.status)).length;
  const defaultedCount = candidates.filter((c) => c.status === "defaulted").length;

  const ifrs9 = unwrapDeep(ifrs9raw || {});
  const stageCounts = Object.values(ifrs9).reduce(
    (acc, f) => {
      acc[f.stage] = (acc[f.stage] || 0) + 1;
      return acc;
    },
    { 1: 0, 2: 0, 3: 0 }
  );

  return (
    <div className="space-y-6 rise-in">
      <div>
        <h1 className="font-head text-xl font-medium">Control tower</h1>
        <p className="text-sm text-muted mt-0.5">
          Live portfolio posture — updates on every simulated month and every lifecycle action.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Total outstanding" value={formatMoney(totalOutstanding)} sub={`${activeCount} performing loans`} accent="ledger" />
        <KpiCard
          label="Portfolio expected loss"
          value={capital ? `${(capital.portfolio_el * 100).toFixed(2)}%` : "—"}
          sub="budget ≤ 2.00%"
          accent={capital && capital.portfolio_el > (capital.budgeted_loss ?? 0.02) ? "danger" : "ledger"}
        />
        <KpiCard
          label="Tier D / RWA"
          value={capital && !(capital.rwa > 0) ? "—" : capital ? `${(capital.tier_d_over_rwa * 100).toFixed(1)}%` : "—"}
          sub={capital ? `${formatMoney(capital.tier_d_amount)} Tier D` : "—"}
          accent={capital && capital.rwa > 0 && capital.tier_d_over_rwa < (capital.tier_d_floor ?? 0.12) ? "danger" : "ledger"}
        />
        <KpiCard
          label="Defaulted facilities"
          value={defaultedCount}
          sub={`of ${candidates.length} total candidates`}
          accent={defaultedCount > 0 ? "amber" : "ledger"}
        />
      </div>

      <div className="grid grid-cols-3 gap-6">
        <Panel title="Prudential ratios" eyebrow="Pillar 4 — capital snapshot" className="col-span-1">
          <div className="grid grid-cols-2 gap-2">
            <RatioGauge label="Tier D / RWA" value={capital?.rwa > 0 ? capital?.tier_d_over_rwa : null} threshold={capital?.tier_d_floor ?? 0.12} direction="floor" />
            <RatioGauge label="Portfolio EL" value={capital?.portfolio_el} threshold={capital?.budgeted_loss_ratio ?? 0.02} direction="ceiling" max={0.06} />
            <RatioGauge
              label="Guarantees granted / received"
              value={capital?.guarantees_granted_over_received ?? 0}
              threshold={1.0}
              direction="ceiling"
              max={1.5}
            />
            <div className="flex flex-col items-center justify-center text-center px-2">
              <div className="text-[11px] text-faint mb-1">Guarantee pool received</div>
              <div className="font-mono text-lg text-text">{formatMoney(adequacy?.received)}</div>
              <div className="text-[10px] text-muted mt-1">required {formatMoney(adequacy?.required_amount)}</div>
            </div>
          </div>
        </Panel>

        <Panel title="Portfolio mix" eyebrow="By lifecycle status" className="col-span-1 flex flex-col items-center justify-center">
          <PortfolioDonut candidates={candidates} />
        </Panel>

        <Panel title="IFRS9 staging" eyebrow="Pillar 4 — provisioning" className="col-span-1">
          <div className="space-y-3 mt-2">
            <StageBar label="Stage 1 — performing" count={stageCounts[1]} total={Object.keys(ifrs9).length} tone="ledger" />
            <StageBar label="Stage 2 — deteriorated" count={stageCounts[2]} total={Object.keys(ifrs9).length} tone="amber" />
            <StageBar label="Stage 3 — default" count={stageCounts[3]} total={Object.keys(ifrs9).length} tone="danger" />
          </div>
        </Panel>
      </div>

      <Panel title="Balance sheet (management view)" eyebrow="Illustrative — loan book vs. guarantee buffer">
        <BalancePanel candidates={candidates} balances={state?.p4?.balances} />
      </Panel>

      <Panel title="Outstanding balance over simulated time" eyebrow={`Sim month ${state?.sim_month ?? 0} · client-accumulated`}>
        {history.length < 2 ? (
          <div className="h-[220px] flex items-center justify-center text-faint text-xs">
            Advance the simulation (bottom-right) to build up a trend.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={history} margin={{ left: 0, right: 10, top: 10 }}>
              <CartesianGrid stroke="#243039" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: "#8697A6", fontSize: 11 }} tickFormatter={(m) => `M${m}`} />
              <YAxis tick={{ fill: "#8697A6", fontSize: 11 }} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} width={50} />
              <Tooltip
                contentStyle={{ background: "#182229", border: "1px solid #243039", fontSize: 12, borderRadius: 4 }}
                labelFormatter={(m) => `Month ${m}`}
                formatter={(v) => [formatMoney(v), "Outstanding"]}
              />
              <Line type="monotone" dataKey="total" stroke="#2FBF9F" strokeWidth={2} dot={{ r: 3, fill: "#2FBF9F" }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Panel>
    </div>
  );
}

function StageBar({ label, count, total, tone }) {
  const pct = total ? (count / total) * 100 : 0;
  const color = { ledger: "#2FBF9F", amber: "#E8A33D", danger: "#E5566A" }[tone];
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs mb-1">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-text">{count ?? 0}</span>
      </div>
      <div className="h-1.5 bg-raised rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
