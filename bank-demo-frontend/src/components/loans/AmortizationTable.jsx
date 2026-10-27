import { formatMoney } from "../../utils/codec";

export function AmortizationTable({ behavior, paymentsMade, currentMonth }) {
  if (!behavior) return <div className="text-xs text-faint">No payment schedule on file.</div>;
  const { repayments = [], delinquent_month, default_month } = behavior;

  return (
    <div className="max-h-80 overflow-y-auto scrollbar-thin">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-panel">
          <tr className="text-faint text-left border-b border-line">
            <th className="py-2 font-normal">Month</th>
            <th className="py-2 font-normal text-right">Principal</th>
            <th className="py-2 font-normal text-right">Interest</th>
            <th className="py-2 font-normal text-right">Status</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {repayments.map((r) => {
            const paid = r.month <= paymentsMade;
            const isDelinquent = r.month === delinquent_month;
            const isDefault = r.month === default_month;
            return (
              <tr key={r.month} className="border-b border-line/50">
                <td className="py-1.5">{r.month}</td>
                <td className="py-1.5 text-right">{formatMoney(r.principal)}</td>
                <td className="py-1.5 text-right">{formatMoney(r.interest)}</td>
                <td className="py-1.5 text-right">
                  {isDefault ? (
                    <span className="text-danger">defaulted</span>
                  ) : isDelinquent ? (
                    <span className="text-amber">missed</span>
                  ) : paid ? (
                    <span className="text-ledger">paid</span>
                  ) : (
                    <span className="text-faint">upcoming</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
