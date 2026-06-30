'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { ClipboardList, TrendingDown } from 'lucide-react';

interface TrackerSignal {
  ticker: string; fire_date: string; entry_price: number; deep_value?: number;
  days_held?: number; cur_ret?: number | null; peak_ret?: number | null;
  r10?: number | null; status?: string; exit_ret?: number | null; exit_reason?: string | null;
}
interface Summary {
  total: number; open: number; closed: number;
  win_rate_realized?: number | null; avg_realized?: number | null;
  win_rate_10d?: number | null; avg_10d?: number | null;
  win_rate_dv_10d?: number | null; win_rate_reg_10d?: number | null;
}

const pct = (n?: number | null) => (typeof n === 'number' ? `${n > 0 ? '+' : ''}${n.toFixed(1)}%` : '—');
const retColor = (n?: number | null) => (typeof n !== 'number' ? 'text-gray-500' : n > 0 ? 'text-emerald-400' : n < 0 ? 'text-red-400' : 'text-gray-300');
const statusChip = (s?: string) => {
  const m: Record<string, string> = {
    OPEN: 'bg-sky-900/50 text-sky-200 border-sky-700',
    TARGET: 'bg-emerald-700 text-white border-emerald-500',
    STOPPED: 'bg-red-800 text-red-100 border-red-600',
    EXPIRED: 'bg-gray-700 text-gray-300 border-gray-600',
  };
  return m[s || ''] || 'bg-gray-700 text-gray-300 border-gray-600';
};

export default function ReversalTracker({ apiUrl }: { apiUrl: string }) {
  const [data, setData] = useState<{ signals: TrackerSignal[]; summary: Summary } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${apiUrl}/api/reversal-tracker`)
      .then((r) => setData(r.data))
      .catch(() => setData({ signals: [], summary: { total: 0, open: 0, closed: 0 } }))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  const s = data?.summary;

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-amber-800/40 mt-6">
      <div className="flex items-center gap-2 mb-1">
        <ClipboardList className="w-5 h-5 text-amber-300" />
        <h2 className="text-lg font-bold text-amber-200">Reversal — Live Track Record</h2>
        <span className="text-[10px] text-gray-500 border border-gray-700 rounded px-1.5 py-0.5">the honest verdict</span>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Every reversal signal is logged the moment it fires and its <b>real</b> outcome tracked under a
        −7% stop / +25% target / 40-day rule. No backtest claims — this is what actually happened.
      </p>

      {loading ? (
        <div className="text-gray-500 text-sm py-6 text-center">Loading…</div>
      ) : !s || s.total === 0 ? (
        <div className="text-gray-500 text-sm py-6 text-center">
          No signals logged yet. The journal fills as reversals fire — it&apos;s empty on calm/bull markets.
        </div>
      ) : (
        <>
          {/* summary chips */}
          <div className="flex flex-wrap gap-2 mb-4 text-xs">
            <span className="bg-gray-900 border border-gray-700 rounded px-2.5 py-1">Logged <b className="text-gray-200">{s.total}</b></span>
            <span className="bg-gray-900 border border-gray-700 rounded px-2.5 py-1">Open <b className="text-sky-300">{s.open}</b> · Closed <b className="text-gray-200">{s.closed}</b></span>
            {typeof s.win_rate_realized === 'number' && (
              <span className="bg-gray-900 border border-gray-700 rounded px-2.5 py-1">
                Realized win <b className={s.win_rate_realized >= 55 ? 'text-emerald-400' : s.win_rate_realized >= 45 ? 'text-yellow-400' : 'text-red-400'}>{s.win_rate_realized}%</b>
                {typeof s.avg_realized === 'number' && <span className={`ml-1 ${retColor(s.avg_realized)}`}>({pct(s.avg_realized)}/trade)</span>}
              </span>
            )}
            {typeof s.win_rate_10d === 'number' && (
              <span className="bg-gray-900 border border-gray-700 rounded px-2.5 py-1">+10d win <b className="text-gray-200">{s.win_rate_10d}%</b> <span className={retColor(s.avg_10d)}>({pct(s.avg_10d)})</span></span>
            )}
            {typeof s.win_rate_dv_10d === 'number' && (
              <span className="bg-gray-900 border border-emerald-800/50 rounded px-2.5 py-1">deep-value +10d win <b className="text-emerald-300">{s.win_rate_dv_10d}%</b></span>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="text-left text-sm min-w-[680px] w-full">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-700">
                  <th className="pb-2 pr-4">TICKER</th>
                  <th className="pb-2 pr-4">FIRED</th>
                  <th className="pb-2 pr-4">ENTRY</th>
                  <th className="pb-2 pr-4">+10d</th>
                  <th className="pb-2 pr-4">PEAK</th>
                  <th className="pb-2 pr-4">NOW/EXIT</th>
                  <th className="pb-2 pr-4">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {data!.signals.map((sig) => {
                  const closed = sig.status && sig.status !== 'OPEN';
                  const outcome = closed ? sig.exit_ret : sig.cur_ret;
                  return (
                    <tr key={`${sig.ticker}-${sig.fire_date}`} className="border-b border-gray-700/50 h-10">
                      <td className="py-2 pr-4 font-bold text-amber-200 whitespace-nowrap">
                        {sig.ticker}
                        {sig.deep_value === 1 && <span className="ml-1.5 text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded font-bold">DV</span>}
                      </td>
                      <td className="py-2 pr-4 text-gray-400 whitespace-nowrap">{sig.fire_date}</td>
                      <td className="py-2 pr-4 text-gray-300">{sig.entry_price?.toFixed(1)}</td>
                      <td className={`py-2 pr-4 ${retColor(sig.r10)}`}>{pct(sig.r10)}</td>
                      <td className={`py-2 pr-4 ${retColor(sig.peak_ret)}`}>{pct(sig.peak_ret)}</td>
                      <td className={`py-2 pr-4 font-bold ${retColor(outcome)}`}>{pct(outcome)}</td>
                      <td className="py-2 pr-4">
                        <span className={`text-[10px] border rounded px-1.5 py-0.5 font-bold ${statusChip(sig.status)}`} title={sig.exit_reason || ''}>
                          {sig.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-gray-600 mt-3 flex items-center gap-1">
            <TrendingDown className="w-3 h-3" /> Judge the signal on this growing record over months — not on any single row.
          </p>
        </>
      )}
    </section>
  );
}
