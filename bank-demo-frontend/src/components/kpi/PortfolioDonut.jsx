import { PieChart, Pie, Cell, Tooltip, Legend } from "recharts";

const COLORS = {
  new: "#5B8DEF",
  scored: "#E8A33D",
  approved: "#7FD9C4",
  disbursed: "#2FBF9F",
  delinquent: "#E8A33D",
  defaulted: "#E5566A",
  closed: "#5C6A76",
  rejected: "#3A2C30",
};

export function PortfolioDonut({ candidates = [] }) {
  const counts = candidates.reduce((acc, c) => {
    acc[c.status] = (acc[c.status] || 0) + 1;
    return acc;
  }, {});
  const data = Object.entries(counts).map(([status, count]) => ({ name: status, value: count }));

  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[220px] text-faint text-xs">No candidates yet</div>;
  }

  return (
    <PieChart width={260} height={220}>
      <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
        {data.map((d) => (
          <Cell key={d.name} fill={COLORS[d.name] || "#5C6A76"} stroke="#0B1014" strokeWidth={2} />
        ))}
      </Pie>
      <Tooltip
        contentStyle={{ background: "#182229", border: "1px solid #243039", fontSize: 12, borderRadius: 4 }}
        itemStyle={{ color: "#E7ECEF" }}
      />
      <Legend
        verticalAlign="bottom"
        height={24}
        formatter={(v) => <span className="text-[11px] text-muted capitalize">{v}</span>}
      />
    </PieChart>
  );
}
