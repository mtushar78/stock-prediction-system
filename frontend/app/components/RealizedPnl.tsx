'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { ChevronDown, ChevronRight, BookOpenCheck } from 'lucide-react';

interface SaleRow {
  ticker: string;
  sell_price: number;
  quantity: number;
  proceeds: number;
  cost_basis: number;
  realized_pnl: number;
  buy_price: number | null;
  purchase_date: string | null;
  sale_date: string;
  notes: string | null;
}

interface SaleHistory {
  sales: SaleRow[];
  total_realized_pnl: number;
  trades: number;
  wins: number;
  win_rate_pct: number | null;
}

/** Realized-P&L journal — every recorded sell, so the track record is auditable.
 *  (Before this existed, sells silently deleted the position and the outcome
 *  was lost — you can't improve what you don't measure.) */
export default function RealizedPnl({ apiUrl, refreshKey }: { apiUrl: string; refreshKey?: number }) {
  const [data, setData] = useState<SaleHistory | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    axios.get<SaleHistory>(`${apiUrl}/api/sale-history`)
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => { /* non-fatal */ });
    return () => { cancelled = true; };
  }, [apiUrl, refreshKey]);

  if (!data || data.trades === 0) return null;

  const pos = data.total_realized_pnl >= 0;
  return (
    <section className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <button onClick={() => setOpen((x) => !x)} className="w-full flex items-center justify-between text-left">
        <div className="flex items-center gap-2">
          <BookOpenCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-bold text-gray-200">Realized P/L</span>
          <span className={`text-sm font-bold ${pos ? 'text-green-400' : 'text-red-400'}`}>
            {pos ? '+' : ''}{data.total_realized_pnl.toLocaleString()} tk
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{data.trades} closed · {data.win_rate_pct ?? 0}% win</span>
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </button>

      {open && (
        <div className="mt-3 overflow-x-auto">
          <table className="text-left text-xs w-full">
            <thead>
              <tr className="text-gray-500 border-b border-gray-700">
                <th className="pb-2 pr-3">DATE</th>
                <th className="pb-2 pr-3">TICKER</th>
                <th className="pb-2 pr-3">BUY→SELL</th>
                <th className="pb-2 pr-3">QTY</th>
                <th className="pb-2 text-right">P/L</th>
              </tr>
            </thead>
            <tbody>
              {data.sales.map((s, i) => (
                <tr key={`${s.ticker}-${s.sale_date}-${i}`} className="border-b border-gray-700/40">
                  <td className="py-1.5 pr-3 text-gray-400 whitespace-nowrap">{s.sale_date}</td>
                  <td className="py-1.5 pr-3 font-bold text-gray-200">{s.ticker}</td>
                  <td className="py-1.5 pr-3 text-gray-400 whitespace-nowrap">
                    {s.buy_price ?? '?'} → {s.sell_price}
                  </td>
                  <td className="py-1.5 pr-3 text-gray-400">{s.quantity}</td>
                  <td className={`py-1.5 text-right font-bold whitespace-nowrap ${s.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {s.realized_pnl >= 0 ? '+' : ''}{s.realized_pnl.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 text-[10px] text-gray-600">
            Net of 0.4% commission each side. Recorded automatically when you sell a position.
          </div>
        </div>
      )}
    </section>
  );
}
