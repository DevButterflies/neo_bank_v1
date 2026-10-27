import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { formatPct } from "../../utils/codec";

// direction: "floor" means value must stay ABOVE threshold (e.g. Tier D/RWA >= 12%)
//            "ceiling" means value must stay BELOW threshold (e.g. Portfolio EL <= 2%)
export function RatioGauge({ label, value, threshold, direction = "floor", max }) {
  if (value === undefined || value === null) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-faint text-sm">—</div>
    );
  }
  const safe = direction === "floor" ? value >= threshold : value <= threshold;
  const domainMax = max ?? Math.max(threshold * 2, value * 1.3, 0.01);
  const color = safe ? "#2FBF9F" : "#E5566A";

  const data = [{ name: label, value: Math.min(value, domainMax), fill: color }];

  return (
    <div className="flex flex-col items-center">
      <RadialBarChart
        width={140}
        height={100}
        cx="50%"
        cy="90%"
        innerRadius="140%"
        outerRadius="220%"
        barSize={10}
        data={data}
        startAngle={180}
        endAngle={0}
      >
        <PolarAngleAxis type="number" domain={[0, domainMax]} angleAxisId={0} tick={false} />
        <RadialBar background={{ fill: "#182229" }} dataKey="value" cornerRadius={5} />
      </RadialBarChart>
      <div className="-mt-9 font-mono text-lg" style={{ color }}>
        {formatPct(value, 1)}
      </div>
      <div className="text-[11px] text-faint mt-3 text-center leading-tight">{label}</div>
      <div className="text-[10px] text-muted mt-0.5">
        {direction === "floor" ? "floor" : "budget"} {formatPct(threshold, 0)}
      </div>
    </div>
  );
}
