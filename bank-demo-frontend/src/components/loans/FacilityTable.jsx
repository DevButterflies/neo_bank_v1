import { useNavigate } from "react-router-dom";
import { formatMoney } from "../../utils/codec";
import { StatusBadge } from "../shared/Atoms";

export function FacilityTable({ candidates }) {
  const navigate = useNavigate();
  const rows = candidates.filter((c) => c.facility_id);

  if (rows.length === 0) {
    return <div className="text-xs text-faint py-8 text-center">No facilities originated yet — approve and disburse a candidate in the Pipeline tab.</div>;
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-[11px] text-faint border-b border-line">
          <th className="py-2 font-normal">Borrower</th>
          <th className="py-2 font-normal">Facility</th>
          <th className="py-2 font-normal">Status</th>
          <th className="py-2 font-normal text-right">Outstanding</th>
          <th className="py-2 font-normal text-right">Payments made</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => (
          <tr
            key={c.id}
            onClick={() => navigate(`/loans/${c.facility_id}`)}
            className="border-b border-line/60 hover:bg-raised cursor-pointer transition"
          >
            <td className="py-2.5">{c.display_name}</td>
            <td className="py-2.5 font-mono text-xs text-muted">{c.facility_id}</td>
            <td className="py-2.5">
              <StatusBadge value={c.status} label={c.status} />
            </td>
            <td className="py-2.5 text-right font-mono">{formatMoney(c.outstanding)}</td>
            <td className="py-2.5 text-right font-mono text-muted">{c.payments_made}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
