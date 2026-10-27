import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { formatMoney } from "../../utils/codec";

export function BalanceChart({ behavior, paymentsMade }) {
  if (!behavior) return null;
  const { repayments = [], disbursed = 0 } = behavior;
  let running = disbursed;
  const data = [{ month: 0, balance: disbursed }];
  repayments.forEach((r) => {
    if (r.month <= paymentsMade) running -= r.principal;
    data.push({ month: r.month, balance: Math.max(running, 0) });
  });

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ left: 0, right: 10, top: 10 }}>
        <CartesianGrid stroke="#243039" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" tick={{ fill: "#8697A6", fontSize: 11 }} tickFormatter={(m) => `M${m}`} />
        <YAxis tick={{ fill: "#8697A6", fontSize: 11 }} tickFormatter={(v) => `$${Math.round(v / 1000)}k`} width={45} />
        <Tooltip
          contentStyle={{ background: "#182229", border: "1px solid #243039", fontSize: 12, borderRadius: 4 }}
          formatter={(v) => [formatMoney(v), "Outstanding"]}
          labelFormatter={(m) => `Month ${m}`}
        />
        <Line type="stepAfter" dataKey="balance" stroke="#5B8DEF" strokeWidth={2} dot={{ r: 2, fill: "#5B8DEF" }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
