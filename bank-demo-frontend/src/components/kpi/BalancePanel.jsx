import { formatMoney } from "../../utils/codec";
import { StatLine } from "../shared/Atoms";

export function BalancePanel({ candidates = [], balances }) {
  const bookByStatus = candidates.reduce((acc, c) => {
    if (["disbursed", "delinquent", "defaulted"].includes(c.status)) {
      acc[c.status] = (acc[c.status] || 0) + (c.outstanding || 0);
    }
    return acc;
  }, {});
  const totalBook = Object.values(bookByStatus).reduce((a, b) => a + b, 0);
  const b = balances || { el_pool: 0, ula_buffer: 0, liquidity_reserve: 0, rp_pool: 0 };
  const totalBuffer = b.el_pool + b.ula_buffer + b.liquidity_reserve + b.rp_pool;

  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <div className="text-[11px] text-faint mb-2 uppercase tracking-wide">Loan book (gross, by state)</div>
        <StatLine label="Disbursed / performing" value={formatMoney(bookByStatus.disbursed || 0)} tone="ledger" />
        <StatLine label="Delinquent" value={formatMoney(bookByStatus.delinquent || 0)} tone="amber" />
        <StatLine label="Defaulted" value={formatMoney(bookByStatus.defaulted || 0)} tone="danger" />
        <div className="flex items-baseline justify-between pt-2 mt-1 border-t border-line">
          <span className="text-xs text-text font-medium">Total outstanding</span>
          <span className="font-mono text-sm text-text">{formatMoney(totalBook)}</span>
        </div>
      </div>
      <div>
        <div className="text-[11px] text-faint mb-2 uppercase tracking-wide">Prudential buffer (4 sub-accounts)</div>
        <StatLine label="EL Pool (IFRS9 provisions)" value={formatMoney(b.el_pool)} />
        <StatLine label="ULA Buffer (unexpected loss)" value={formatMoney(b.ula_buffer)} />
        <StatLine label="Liquidity reserve" value={formatMoney(b.liquidity_reserve)} />
        <StatLine label="RP Pool (risk-premium income)" value={formatMoney(b.rp_pool)} />
        <div className="flex items-baseline justify-between pt-2 mt-1 border-t border-line">
          <span className="text-xs text-text font-medium">Total buffer</span>
          <span className="font-mono text-sm text-text">{formatMoney(totalBuffer)}</span>
        </div>
      </div>
    </div>
  );
}
