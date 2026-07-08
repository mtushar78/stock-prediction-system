'use client';

/**
 * SectorHealth — "where is the money and how healthy is each sector" panel.
 *
 * Answers the user's two questions: which sectors have the MOST TRADES
 * (turnover share) and their CONDITION (breadth + trend). Sector breadth is
 * the market-breadth regime dial (the one validated switch) sliced by sector —
 * descriptive context for where to focus, NOT a per-sector buy signal.
 *
 * Reads /api/sector-health. Fetched once on mount + on manual refresh (it's a
 * heavier query, so it is NOT in the 60s dashboard poll).
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { Layers, RefreshCw, ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { SectorHealth as SectorHealthData, SectorHealthRow } from '../types';

const CONDITION_CLS: Record<string, string> = {
  STRONG: 'bg-emerald-700 text-emerald-100',
  FIRM: 'bg-sky-700 text-sky-100',
  SOFT: 'bg-yellow-700 text-yellow-100',
  WEAK: 'bg-red-800 text-red-100',
};

type SortKey = 'turnover_share' | 'strength' | 'ret20';

export default function SectorHealth({ apiUrl }: { apiUrl: string }) {
  const [data, setData] = useState<SectorHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortKey>('turnover_share');
  const [open, setOpen] = useState(true);

  const fetchData = () => {
    setLoading(true);
    axios
      .get<SectorHealthData>(`${apiUrl}/api/sector-health`)
      .then((res) => setData(res.data))
      .catch(() => { /* non-fatal */ })
      .finally(() => setLoading(false));
  };

  useEffect(fetchData, [apiUrl]);

  if (!data || data.sectors.length === 0) return null;

  const sorted = [...data.sectors].sort((a, b) => (b[sortBy] ?? -Infinity) - (a[sortBy] ?? -Infinity));
  const maxTurn = Math.max(...data.sectors.map((s) => s.turnover_share), 1);

  const trendIcon = (t: SectorHealthRow['trend']) =>
    t === 'up' ? <ArrowUp className="w-3.5 h-3.5 text-emerald-400 inline" />
    : t === 'down' ? <ArrowDown className="w-3.5 h-3.5 text-red-400 inline" />
    : <Minus className="w-3.5 h-3.5 text-gray-500 inline" />;

  const ret = (v: number | null) =>
    v == null ? <span className="text-gray-600">—</span>
    : <span className={v >= 0 ? 'text-emerald-300' : 'text-red-300'}>{v >= 0 ? '+' : ''}{v}%</span>;

  const leader = sorted[0];

  return (
    <div className="mb-4 bg-gray-800/50 border border-gray-700 rounded p-3">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-2 font-bold text-gray-200 text-sm">
          <Layers className="w-4 h-4 text-indigo-300" /> Sector Rotation — where the money is
          <span className="text-gray-500 text-xs">{open ? '▲' : '▼'}</span>
        </button>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500 mr-1">Sort:</span>
          {([['turnover_share', 'Trades'], ['strength', 'Health'], ['ret20', '20d return']] as [SortKey, string][]).map(
            ([k, label]) => (
              <button key={k} onClick={() => setSortBy(k)}
                className={`px-2 py-0.5 rounded border transition ${
                  sortBy === k ? 'bg-indigo-800 text-indigo-100 border-indigo-600'
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'}`}>
                {label}
              </button>
            ),
          )}
          <button onClick={fetchData} title="Refresh" className="text-gray-500 hover:text-gray-200 ml-1">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* One-line takeaway */}
      <div className="text-xs text-gray-400 mb-2">
        <b className="text-indigo-300">{leader.sector}</b> is the most active sector today
        ({leader.turnover_share}% of turnover, {leader.condition.toLowerCase()}).
        {' '}Total market turnover ৳{Math.round(data.total_turnover_mn).toLocaleString()}mn.
        <span className="text-gray-600"> Health = % of the sector above its 50-day average (same dial as market breadth).</span>
      </div>

      {open && (
        <div className="overflow-x-auto">
          <table className="text-left text-xs min-w-[620px] w-full">
            <thead>
              <tr className="text-gray-500 border-b border-gray-700">
                <th className="pb-2 pr-2">SECTOR</th>
                <th className="pb-2 pr-2" title="Condition = 60% breadth + 40% 20-day momentum">CONDITION</th>
                <th className="pb-2 pr-2" title="Share of today's total traded value — where the money is flowing">TRADES</th>
                <th className="pb-2 pr-2" title="% of the sector's liquid stocks above their 50-day average">HEALTH</th>
                <th className="pb-2 pr-2" title="Median 5-day return">5D</th>
                <th className="pb-2 pr-2" title="Median 20-day return">20D</th>
                <th className="pb-2 pr-2" title="% of the sector green today">ADV</th>
                <th className="pb-2 pr-2">#</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => (
                <tr key={s.sector} className="border-b border-gray-800/70 hover:bg-gray-900/40">
                  <td className="py-1.5 pr-2 text-gray-200 whitespace-nowrap">{trendIcon(s.trend)} {s.sector}</td>
                  <td className="py-1.5 pr-2">
                    <span className={`px-1.5 py-0.5 rounded font-bold ${CONDITION_CLS[s.condition]}`}>{s.condition}</span>
                  </td>
                  <td className="py-1.5 pr-2 min-w-[90px]">
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 bg-gray-900 rounded-full overflow-hidden w-14">
                        <div className="h-full bg-indigo-500" style={{ width: `${(s.turnover_share / maxTurn) * 100}%` }} />
                      </div>
                      <span className="text-gray-300">{s.turnover_share}%</span>
                    </div>
                  </td>
                  <td className="py-1.5 pr-2">
                    <span className={s.breadth_pct >= 60 ? 'text-emerald-300'
                      : s.breadth_pct >= 45 ? 'text-yellow-300' : 'text-red-300'}>
                      {s.breadth_pct}%
                    </span>
                  </td>
                  <td className="py-1.5 pr-2">{ret(s.ret5)}</td>
                  <td className="py-1.5 pr-2">{ret(s.ret20)}</td>
                  <td className="py-1.5 pr-2 text-gray-400">{s.advancers_pct}%</td>
                  <td className="py-1.5 pr-2 text-gray-500">{s.stocks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
