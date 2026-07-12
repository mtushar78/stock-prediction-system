'use client';

/**
 * UniverseScope — browse the ENTIRE market on the Chart Analyst page.
 *
 * Unlike the pattern scanner (which only lists tickers that fired a Bulkowski
 * formation today), this view shows EVERY tradable stock with its latest price,
 * day change and sector, so the sector filter can surface all stocks in a
 * category. When a stock also has an active chart pattern, its grade/verdict is
 * shown inline. Clicking any row opens the full ChartDetailModal (on-demand
 * analysis), same as the rest of the page.
 *
 * Reads /api/chart-analysis/universe.
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Globe, Search, TrendingUp, TrendingDown, Rocket } from 'lucide-react';

interface UniverseRow {
  ticker: string;
  sector: string;
  price: number;
  change_pct: number | null;
  avg_vol20: number | null;
  grade: string | null;
  verdict: string | null;
  top_name: string | null;
  bias: string | null;
  edge: number | null;
  pattern_status: string | null;
  has_pattern: boolean;
  confluence: 'reversal' | 'breakout' | null;
}

interface UniverseResponse {
  as_of: string | null;
  count: number;
  stocks: UniverseRow[];
}

interface Props {
  apiUrl: string;
  onRowClick: (ticker: string) => void;
}

type SortKey = 'ticker' | 'price' | 'change' | 'sector' | 'grade' | 'volume';
type SortDir = 'asc' | 'desc';

const gradeCls = (g: string | null) => {
  switch (g) {
    case 'A': return 'bg-emerald-500 text-black';
    case 'B': return 'bg-lime-500 text-black';
    case 'C': return 'bg-yellow-500 text-black';
    case 'D': return 'bg-orange-500 text-black';
    case 'F': return 'bg-red-600 text-white';
    default: return 'bg-gray-700 text-gray-400';
  }
};

const verdictCls = (v: string | null) =>
  v === 'BUY SETUP' ? 'text-emerald-300'
  : v === 'WATCH' ? 'text-blue-300'
  : v === 'DANGER' || v === 'EXIT / AVOID' ? 'text-red-300'
  : 'text-gray-400';

export default function UniverseScope({ apiUrl, onRowClick }: Props) {
  const [data, setData] = useState<UniverseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [onlyPatterns, setOnlyPatterns] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('ticker');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await axios.get<UniverseResponse>(`${apiUrl}/api/chart-analysis/universe`);
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setError('Could not load the market universe.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    const id = setInterval(fetchData, 60000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiUrl]);

  const rows = useMemo(() => data?.stocks ?? [], [data]);

  const sectorList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) counts.set(r.sector, (counts.get(r.sector) || 0) + 1);
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [rows]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    let out = rows;
    if (sectorFilter !== 'ALL') out = out.filter((r) => r.sector === sectorFilter);
    if (onlyPatterns) out = out.filter((r) => r.has_pattern);
    if (q) out = out.filter((r) => r.ticker.includes(q));
    const copy = [...out];
    copy.sort((a, b) => {
      let av: number | string = 0, bv: number | string = 0;
      switch (sortKey) {
        case 'ticker': av = a.ticker; bv = b.ticker; break;
        case 'sector': av = a.sector; bv = b.sector; break;
        case 'price': av = a.price ?? 0; bv = b.price ?? 0; break;
        case 'change': av = a.change_pct ?? -9999; bv = b.change_pct ?? -9999; break;
        case 'volume': av = a.avg_vol20 ?? 0; bv = b.avg_vol20 ?? 0; break;
        case 'grade': {
          const rank = (g: string | null) => (g ? 'FEDCBA'.indexOf(g) : -1);
          av = rank(a.grade); bv = rank(b.grade); break;
        }
      }
      if (typeof av === 'string' && typeof bv === 'string')
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === 'asc' ? (Number(av) - Number(bv)) : (Number(bv) - Number(av));
    });
    return copy;
  }, [rows, sectorFilter, onlyPatterns, search, sortKey, sortDir]);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortKey(k); setSortDir(k === 'ticker' || k === 'sector' ? 'asc' : 'desc'); }
  };
  const arrow = (k: SortKey) => (sortKey === k ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '');

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-sky-800/40 mb-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-sky-300 flex items-center gap-2">
            <Globe className="w-5 h-5" /> All Stocks
          </h2>
          <span className="text-[10px] text-gray-500 border border-sky-800/60 rounded px-1.5 py-0.5 text-sky-300/80">
            whole market · filter by sector · click for full analysis
          </span>
        </div>
        <div className="flex gap-1 flex-wrap items-center">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="find ticker…"
              className="bg-gray-900 border border-gray-700 focus:border-sky-500 outline-none rounded pl-7 pr-2 py-1 text-xs text-white w-32 placeholder-gray-600"
            />
          </div>
          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            title="Filter by sector / category"
            className="bg-gray-700 text-gray-200 text-xs rounded px-2 py-1 border border-gray-600 max-w-[190px]"
          >
            <option value="ALL">All sectors ({rows.length})</option>
            {sectorList.map(([s, n]) => (
              <option key={s} value={s}>{s} ({n})</option>
            ))}
          </select>
          <button
            onClick={() => setOnlyPatterns((x) => !x)}
            title="Show only stocks with an active chart pattern today"
            className={`px-2 py-1 rounded text-xs border transition ${
              onlyPatterns
                ? 'bg-cyan-700 text-white border-cyan-600'
                : 'bg-gray-700 text-gray-300 border-gray-600 hover:bg-gray-600'
            }`}
          >
            ⬦ pattern only
          </button>
        </div>
      </div>

      {(sectorFilter !== 'ALL' || search || onlyPatterns) && (
        <div className="mb-2 text-xs text-sky-300/80">
          Showing <b>{filtered.length}</b> stock{filtered.length === 1 ? '' : 's'}
          {sectorFilter !== 'ALL' && <> in <b>{sectorFilter}</b></>}
          {onlyPatterns && <> with a pattern</>}
          {' · '}
          <button
            onClick={() => { setSectorFilter('ALL'); setSearch(''); setOnlyPatterns(false); }}
            className="underline hover:text-sky-200"
          >clear filters</button>
        </div>
      )}

      {error && <div className="bg-red-900/40 border border-red-700 text-red-200 rounded p-2 text-xs mb-2">{error}</div>}

      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[720px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th onClick={() => toggleSort('ticker')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300">TICKER{arrow('ticker')}</th>
              <th onClick={() => toggleSort('sector')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300">SECTOR{arrow('sector')}</th>
              <th onClick={() => toggleSort('price')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300 text-right">PRICE{arrow('price')}</th>
              <th onClick={() => toggleSort('change')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300 text-right">CHG%{arrow('change')}</th>
              <th onClick={() => toggleSort('volume')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300 text-right hidden sm:table-cell">AVG VOL{arrow('volume')}</th>
              <th onClick={() => toggleSort('grade')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300" title="Bulkowski chart-pattern grade (if a pattern is active today)">PATTERN{arrow('grade')}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={r.ticker}
                onClick={() => onRowClick(r.ticker)}
                className="border-b border-gray-700/50 hover:bg-sky-900/10 transition cursor-pointer h-10"
                title="Click for the full chart analysis"
              >
                <td className="py-2 pr-3 font-bold text-sky-300 whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5">
                    {r.ticker}
                    {r.confluence === 'reversal' && (
                      <span title="Quant REVERSAL signal fires here — the one signal with a validated net edge" className="text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded font-bold">
                        🚀 REV
                      </span>
                    )}
                  </span>
                </td>
                <td className="py-2 pr-3 text-gray-400 text-xs max-w-[150px] truncate">{r.sector}</td>
                <td className="py-2 pr-3 text-right text-gray-200 whitespace-nowrap">{r.price?.toFixed(1) ?? '-'}</td>
                <td className={`py-2 pr-3 text-right whitespace-nowrap ${(r.change_pct ?? 0) > 0 ? 'text-green-400' : (r.change_pct ?? 0) < 0 ? 'text-red-400' : 'text-gray-500'}`}>
                  {r.change_pct == null ? '-' : (
                    <span className="inline-flex items-center gap-0.5 justify-end">
                      {r.change_pct > 0 ? <TrendingUp className="w-3 h-3" /> : r.change_pct < 0 ? <TrendingDown className="w-3 h-3" /> : null}
                      {r.change_pct > 0 ? '+' : ''}{r.change_pct.toFixed(2)}%
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3 text-right text-gray-400 text-xs whitespace-nowrap hidden sm:table-cell">
                  {r.avg_vol20 != null ? `${Math.round(r.avg_vol20 / 1000)}k` : '-'}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">
                  {r.has_pattern ? (
                    <span className="inline-flex items-center gap-1.5">
                      {r.grade && (
                        <span className={`inline-flex w-5 h-5 rounded items-center justify-center font-black text-[11px] ${gradeCls(r.grade)}`}>
                          {r.grade}
                        </span>
                      )}
                      <span className={`text-xs ${verdictCls(r.verdict)}`}>{r.verdict ?? r.top_name}</span>
                      {r.confluence === 'reversal' && <Rocket className="w-3 h-3 text-sky-400" />}
                    </span>
                  ) : (
                    <span className="text-gray-600 text-xs">—</span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-600">
                  {loading ? 'Loading the market…' : 'No stocks match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {data?.as_of && (
        <div className="mt-2 text-[11px] text-gray-600">
          {rows.length} stocks · prices as of {data.as_of}. Sector comes from the weekly fundamentals scrape;
          a stock with no pattern still opens its full chart on click.
        </div>
      )}
    </section>
  );
}
