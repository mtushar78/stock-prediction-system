'use client';

/**
 * PatternScope — the multi-week CHART-pattern scanner (Bulkowski engine).
 *
 * Reads /api/chart-analysis/patterns and lists every stock with an active
 * classical formation (double bottom, head-and-shoulders, triangle, flag,
 * dead-cat bounce…), its measure-rule target, and Bulkowski's win-rate.
 * Clicking a row opens ChartDetailModal, which draws the pattern geometry.
 *
 * This is distinct from ChartScope (the candlestick engine).
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ChartPatternScanRow } from '../types';
import { Crosshair, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2, Clock, Target, Info } from 'lucide-react';

interface PatternScopeProps {
  apiUrl: string;
  onRowClick: (ticker: string) => void;
}

type Tab = 'ALL' | 'CONFIRMED' | 'BULLISH' | 'BEARISH' | 'WARN';
type SortKey = 'target' | 'confidence' | 'ticker' | 'price' | 'pattern';
type SortDir = 'asc' | 'desc';

const confRank: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 };

const biasBadge = (bias: string) =>
  bias === 'bullish'
    ? 'bg-emerald-700/40 text-emerald-300 border-emerald-700'
    : bias === 'bearish'
    ? 'bg-red-900/40 text-red-300 border-red-800'
    : 'bg-gray-700 text-gray-300 border-gray-600';

const confidenceBadge = (c: string) =>
  c === 'HIGH'
    ? 'bg-purple-700 text-white'
    : c === 'MEDIUM'
    ? 'bg-blue-700 text-white'
    : c === 'LOW'
    ? 'bg-gray-600 text-gray-200'
    : 'bg-gray-800 text-gray-500';

export default function PatternScope({ apiUrl, onRowClick }: PatternScopeProps) {
  const [rows, setRows] = useState<ChartPatternScanRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('confidence');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await axios.get<ChartPatternScanRow[]>(`${apiUrl}/api/chart-analysis/patterns`);
        if (cancelled) return;
        setRows(Array.isArray(res.data) ? res.data : []);
      } catch {
        if (!cancelled) setError('Could not load chart-pattern scan');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetch();
    const id = setInterval(fetch, 60000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiUrl]);

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (tab === 'CONFIRMED') return r.status === 'confirmed';
      if (tab === 'BULLISH') return r.bias === 'bullish';
      if (tab === 'BEARISH') return r.bias === 'bearish';
      if (tab === 'WARN') return r.has_dcb;
      return true;
    });
  }, [rows, tab]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let av: number | string = 0;
      let bv: number | string = 0;
      switch (sortKey) {
        case 'target':
          av = a.target_pct ?? -999;
          bv = b.target_pct ?? -999;
          break;
        case 'confidence':
          av = confRank[a.confidence] ?? 0;
          bv = confRank[b.confidence] ?? 0;
          break;
        case 'ticker':
          av = a.ticker;
          bv = b.ticker;
          break;
        case 'price':
          av = a.price ?? 0;
          bv = b.price ?? 0;
          break;
        case 'pattern':
          av = a.top_name;
          bv = b.top_name;
          break;
      }
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const an = Number(av) || 0;
      const bn = Number(bv) || 0;
      return sortDir === 'asc' ? an - bn : bn - an;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    else {
      setSortKey(k);
      setSortDir('desc');
    }
  };
  const arrow = (k: SortKey) => (sortKey === k ? (sortDir === 'desc' ? ' ▼' : ' ▲') : '');

  const cAll = rows.length;
  const cConf = rows.filter((r) => r.status === 'confirmed').length;
  const cBull = rows.filter((r) => r.bias === 'bullish').length;
  const cBear = rows.filter((r) => r.bias === 'bearish').length;
  const cWarn = rows.filter((r) => r.has_dcb).length;

  const TabBtn = ({ id, label, count, cls }: { id: Tab; label: string; count: number; cls?: string }) => (
    <button
      onClick={() => setTab(id)}
      className={`px-3 py-1 rounded text-xs ${
        tab === id ? cls ?? 'bg-purple-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
      }`}
    >
      {label} ({count})
    </button>
  );

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-cyan-800/40 mb-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-cyan-300 flex items-center gap-2">
            <Crosshair className="w-5 h-5" /> Chart-Pattern Scanner
          </h2>
          <span className="text-[10px] text-gray-500 border border-cyan-800/60 rounded px-1.5 py-0.5 text-cyan-300/80">
            Bulkowski · multi-week formations + price targets
          </span>
          <button onClick={() => setShowHelp((x) => !x)} className="text-gray-500 hover:text-gray-200 ml-1" title="What is this?">
            <Info className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-1 flex-wrap">
          <TabBtn id="ALL" label="ALL" count={cAll} />
          <TabBtn id="CONFIRMED" label="✓ CONFIRMED" count={cConf} cls="bg-emerald-700 text-white" />
          <TabBtn id="BULLISH" label="BULLISH" count={cBull} cls="bg-emerald-700 text-white" />
          <TabBtn id="BEARISH" label="BEARISH" count={cBear} cls="bg-red-700 text-white" />
          <TabBtn id="WARN" label="⚠ WARNINGS" count={cWarn} cls="bg-red-800 text-white" />
        </div>
      </div>

      {showHelp && (
        <div className="mb-3 bg-gray-900 border border-cyan-800/40 rounded p-3 text-xs text-gray-300 space-y-2">
          <div>
            The <span className="text-cyan-300 font-bold">Chart-Pattern Scanner</span> detects classical
            multi-week formations from Bulkowski&apos;s <i>Encyclopedia of Chart Patterns</i> — double
            bottoms/tops, head-and-shoulders, triangles, rectangles, wedges, cups, flags, pipes and the
            dead-cat-bounce warning.
          </div>
          <div>
            Each row shows the <b>measure-rule price target</b> and, in the detail view, Bulkowski&apos;s real
            bull-market <b>average move</b>, <b>failure rate</b> and <b>hit-target %</b>. A
            <span className="text-emerald-300 font-bold"> CONFIRMED</span> pattern has already broken out;
            <span className="text-amber-300 font-bold"> FORMING</span> is still coiling at the breakout line.
          </div>
          <div className="text-gray-500">Click any row to see the pattern drawn on the candlestick chart.</div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-200 rounded p-2 text-xs mb-2">{error}</div>
      )}

      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[820px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th onClick={() => toggleSort('ticker')} className="pb-3 pr-4 cursor-pointer hover:text-gray-300">TICKER{arrow('ticker')}</th>
              <th onClick={() => toggleSort('price')} className="pb-3 pr-4 cursor-pointer hover:text-gray-300">PRICE{arrow('price')}</th>
              <th onClick={() => toggleSort('pattern')} className="pb-3 pr-4 cursor-pointer hover:text-gray-300">PATTERN{arrow('pattern')}</th>
              <th className="pb-3 pr-4">STATUS</th>
              <th className="pb-3 pr-4">BIAS</th>
              <th onClick={() => toggleSort('confidence')} className="pb-3 pr-4 cursor-pointer hover:text-gray-300">CONF{arrow('confidence')}</th>
              <th onClick={() => toggleSort('target')} className="pb-3 pr-4 cursor-pointer hover:text-gray-300" title="Measure-rule target (% from current price)">TARGET{arrow('target')}</th>
              <th className="pb-3 pr-2">#</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr
                key={r.ticker}
                className="border-b border-gray-700/50 hover:bg-cyan-900/10 transition cursor-pointer h-10"
                onClick={() => onRowClick(r.ticker)}
                title="Click for the full chart with the pattern drawn on it"
              >
                <td className="py-2 pr-4 font-bold text-cyan-300 whitespace-nowrap">
                  <span className="inline-flex items-center gap-1.5">
                    {r.ticker}
                    {r.has_dcb && (
                      <span title="Dead-cat-bounce warning" className="text-[9px] bg-red-700 text-white px-1 py-0.5 rounded font-bold">
                        ⚠
                      </span>
                    )}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap text-gray-200">{r.price?.toFixed(1) ?? '-'}</td>
                <td className="py-2 pr-4 whitespace-nowrap text-gray-100">
                  <span className="inline-flex items-center gap-1.5">
                    {r.bias === 'bullish' ? (
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                    ) : r.bias === 'bearish' ? (
                      <TrendingDown className="w-3.5 h-3.5 text-red-400" />
                    ) : null}
                    {r.top_name}
                    {r.pattern_count > 1 && <span className="text-gray-500 text-[10px]">+{r.pattern_count - 1}</span>}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {r.status === 'confirmed' ? (
                    <span className="inline-flex items-center gap-1 text-[11px] text-emerald-300">
                      <CheckCircle2 className="w-3.5 h-3.5" /> confirmed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] text-amber-300">
                      <Clock className="w-3.5 h-3.5" /> forming
                    </span>
                  )}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold border ${biasBadge(r.bias)}`}>
                    {r.bias.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${confidenceBadge(r.confidence)}`}>
                    {r.confidence}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {r.target != null ? (
                    (() => {
                      // A confirmed move can already have passed its measure-rule
                      // target — show that plainly instead of a wrong-side %.
                      const reached =
                        r.target_pct != null &&
                        ((r.bias === 'bullish' && r.target_pct <= 0) ||
                          (r.bias === 'bearish' && r.target_pct >= 0));
                      return (
                        <span className="inline-flex items-center gap-1">
                          <Target className="w-3 h-3 text-cyan-400" />
                          <span className="text-gray-200">{r.target}</span>
                          {reached ? (
                            <span className="text-emerald-400 text-xs">✓ hit</span>
                          ) : (
                            r.target_pct != null && (
                              <span className={r.bias === 'bullish' ? 'text-emerald-400 text-xs' : 'text-red-400 text-xs'}>
                                ({r.target_pct > 0 ? '+' : ''}
                                {r.target_pct}%)
                              </span>
                            )
                          )}
                        </span>
                      );
                    })()
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </td>
                <td className="py-2 pr-2 text-gray-300">{r.pattern_count}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-gray-600">
                  {loading ? 'Scanning for chart patterns…' : 'No active chart patterns in the latest session.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {cWarn > 0 && tab !== 'WARN' && (
        <div className="mt-2 text-[11px] text-red-300/80 flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5" /> {cWarn} ticker(s) under a dead-cat-bounce warning — see the ⚠ WARNINGS tab.
        </div>
      )}
    </section>
  );
}
