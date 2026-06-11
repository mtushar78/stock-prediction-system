'use client';

/**
 * ChartScope — independent second-opinion view of today's candlestick
 * pattern signals. Reads from /api/chart-analysis/signals, displays a
 * sortable/filterable table; clicking any row opens ChartDetailModal
 * with the full candlestick chart and pattern annotations.
 *
 * Visually distinct from the quant SignalsTable to make it clear the
 * two engines are independent.
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ChartSignal } from '../types';
import { Activity, TrendingUp, Layers, Info } from 'lucide-react';

interface ChartScopeProps {
  apiUrl: string;
  onRowClick: (ticker: string) => void;
}

type Tab = 'ALL' | 'HIGH' | 'BULLISH' | 'MULTI';
type SortKey = 'score' | 'patterns' | 'ticker' | 'price';
type SortDir = 'asc' | 'desc';

const biasBadge = (bias: string) => {
  switch (bias) {
    case 'bullish':
      return 'bg-emerald-700/40 text-emerald-300 border-emerald-700';
    case 'bearish':
      return 'bg-red-900/40 text-red-300 border-red-800';
    default:
      return 'bg-gray-700 text-gray-300 border-gray-600';
  }
};

const confidenceBadge = (conf: string) => {
  switch (conf) {
    case 'HIGH':
      return 'bg-purple-700 text-white';
    case 'MEDIUM':
      return 'bg-blue-700 text-white';
    case 'LOW':
      return 'bg-gray-600 text-gray-200';
    default:
      return 'bg-gray-800 text-gray-500';
  }
};

const scoreColor = (s: number) =>
  s >= 80
    ? 'text-purple-300'
    : s >= 50
    ? 'text-emerald-300'
    : s >= 25
    ? 'text-yellow-300'
    : 'text-gray-400';

export default function ChartScope({ apiUrl, onRowClick }: ChartScopeProps) {
  const [signals, setSignals] = useState<ChartSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await axios.get<ChartSignal[]>(`${apiUrl}/api/chart-analysis/signals`);
        if (cancelled) return;
        setSignals(Array.isArray(res.data) ? res.data : []);
      } catch (e) {
        if (cancelled) return;
        setError('Could not load chart analysis');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetch();
    const interval = setInterval(fetch, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [apiUrl]);

  const filtered = useMemo(() => {
    return signals.filter((s) => {
      if (tab === 'HIGH') return s.confidence === 'HIGH';
      if (tab === 'BULLISH') return s.overall_bias === 'bullish';
      if (tab === 'MULTI') return s.pattern_count >= 2;
      return true;
    });
  }, [signals, tab]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let av: number | string = 0;
      let bv: number | string = 0;
      switch (sortKey) {
        case 'score':
          av = a.overall_score;
          bv = b.overall_score;
          break;
        case 'patterns':
          av = a.pattern_count;
          bv = b.pattern_count;
          break;
        case 'ticker':
          av = a.ticker;
          bv = b.ticker;
          break;
        case 'price':
          av = a.price ?? 0;
          bv = b.price ?? 0;
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

  const countAll = signals.length;
  const countHigh = signals.filter((s) => s.confidence === 'HIGH').length;
  const countBullish = signals.filter((s) => s.overall_bias === 'bullish').length;
  const countMulti = signals.filter((s) => s.pattern_count >= 2).length;

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-purple-800/40">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-purple-300 flex items-center gap-2">
            <Activity className="w-5 h-5" /> Chart Analyst
          </h2>
          <span className="text-[10px] text-gray-500 border border-purple-800/60 rounded px-1.5 py-0.5 text-purple-300/80">
            independent · candlestick patterns
          </span>
          <button
            onClick={() => setShowHelp((x) => !x)}
            className="text-gray-500 hover:text-gray-200 ml-1"
            title="What is this?"
          >
            <Info className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-1 text-xs flex-wrap">
          <button
            onClick={() => setTab('ALL')}
            className={`px-3 py-1 rounded ${
              tab === 'ALL'
                ? 'bg-purple-700 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            ALL ({countAll})
          </button>
          <button
            onClick={() => setTab('HIGH')}
            className={`px-3 py-1 rounded flex items-center gap-1 ${
              tab === 'HIGH'
                ? 'bg-purple-700 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            title="HIGH confidence: score ≥ 80 with ≥ 2 patterns simultaneously"
          >
            <Layers className="w-3 h-3" /> HIGH ({countHigh})
          </button>
          <button
            onClick={() => setTab('BULLISH')}
            className={`px-3 py-1 rounded flex items-center gap-1 ${
              tab === 'BULLISH'
                ? 'bg-emerald-700 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            title="All bullish-bias setups"
          >
            <TrendingUp className="w-3 h-3" /> BULLISH ({countBullish})
          </button>
          <button
            onClick={() => setTab('MULTI')}
            className={`px-3 py-1 rounded ${
              tab === 'MULTI'
                ? 'bg-purple-700 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            title="Multiple patterns firing on the same day"
          >
            MULTI ({countMulti})
          </button>
        </div>
      </div>

      {showHelp && (
        <div className="mb-3 bg-gray-900 border border-purple-800/40 rounded p-3 text-xs text-gray-300 space-y-2">
          <div>
            <span className="text-purple-300 font-bold">Chart Analyst</span> is a
            second, independent engine. It scans every stock for 8 classical
            candlestick patterns (Bullish Engulfing, Hammer, Morning Star, etc.)
            and adjusts each pattern&apos;s strength based on trend, support/resistance,
            and volume context.
          </div>
          <div>
            <span className="text-purple-300 font-bold">SCORE</span> aggregates all
            detected patterns (0–100). <b>HIGH</b> confidence = score ≥ 80 with ≥ 2
            patterns firing together. <b>MEDIUM</b> = ≥ 50. <b>LOW</b> = ≥ 25.
          </div>
          <div className="text-gray-500">
            Click any row to see the full candlestick chart with pattern markers
            and a plain-English breakdown.
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-200 rounded p-2 text-xs mb-2">
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="text-left text-sm table-fixed min-w-[900px] w-full">
          <colgroup>
            <col style={{ width: '140px' }} />
            <col style={{ width: '90px' }} />
            <col style={{ width: '90px' }} />
            <col style={{ width: '90px' }} />
            <col style={{ width: '90px' }} />
            <col style={{ width: '90px' }} />
            <col style={{ width: '90px' }} />
            <col style={{ width: 'auto' }} />
          </colgroup>
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th
                onClick={() => toggleSort('ticker')}
                className="pb-3 pr-4 cursor-pointer select-none hover:text-gray-300"
              >
                TICKER{arrow('ticker')}
              </th>
              <th
                onClick={() => toggleSort('price')}
                className="pb-3 pr-4 cursor-pointer select-none hover:text-gray-300"
              >
                PRICE{arrow('price')}
              </th>
              <th className="pb-3 pr-4 whitespace-nowrap">BIAS</th>
              <th
                onClick={() => toggleSort('score')}
                className="pb-3 pr-4 cursor-pointer select-none hover:text-gray-300"
                title="Aggregate strength of all detected patterns (0–100)"
              >
                SCORE{arrow('score')}
              </th>
              <th className="pb-3 pr-4 whitespace-nowrap">CONFIDENCE</th>
              <th
                onClick={() => toggleSort('patterns')}
                className="pb-3 pr-4 cursor-pointer select-none hover:text-gray-300"
              >
                #{arrow('patterns')}
              </th>
              <th className="pb-3 pr-4 whitespace-nowrap">TREND</th>
              <th className="pb-3 pr-2 whitespace-nowrap">PATTERNS DETECTED</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((sig) => (
              <tr
                key={sig.ticker}
                className="border-b border-gray-700/50 hover:bg-purple-900/10 transition cursor-pointer h-10"
                onClick={() => onRowClick(sig.ticker)}
                title="Click to view full chart + pattern breakdown"
              >
                <td className="py-2 pr-4 font-bold text-purple-300 whitespace-nowrap overflow-hidden">
                  {sig.ticker}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap text-gray-200">
                  {sig.price?.toFixed(1) ?? '-'}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-bold border ${biasBadge(
                      sig.overall_bias,
                    )}`}
                  >
                    {sig.overall_bias.toUpperCase()}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span className={`font-bold ${scoreColor(sig.overall_score)}`}>
                    {sig.overall_score}
                  </span>
                  <span className="text-gray-600 text-xs ml-0.5">/100</span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${confidenceBadge(
                      sig.confidence,
                    )}`}
                  >
                    {sig.confidence}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap text-gray-300">
                  {sig.pattern_count}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span
                    className={`text-xs ${
                      sig.context?.trend === 'uptrend'
                        ? 'text-green-400'
                        : sig.context?.trend === 'downtrend'
                        ? 'text-red-400'
                        : 'text-yellow-400'
                    }`}
                    title={`${sig.context?.trend ?? '?'} (${sig.context?.trend_slope_pct?.toFixed?.(1) ?? '0.0'}% slope)`}
                  >
                    {sig.context?.trend === 'uptrend'
                      ? '⬆️'
                      : sig.context?.trend === 'downtrend'
                      ? '⬇️'
                      : '↔️'}
                  </span>
                </td>
                <td className="py-2 pr-2 text-xs text-gray-300">
                  <div className="flex gap-1 flex-wrap">
                    {sig.patterns.slice(0, 3).map((p, i) => (
                      <span
                        key={i}
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          p.bias === 'bullish'
                            ? 'bg-emerald-900/50 text-emerald-200 border border-emerald-800'
                            : 'bg-red-900/50 text-red-200 border border-red-800'
                        }`}
                        title={p.plain}
                      >
                        {p.name} · {p.final_strength}
                      </span>
                    ))}
                    {sig.patterns.length > 3 && (
                      <span className="text-gray-500 text-[10px]">
                        +{sig.patterns.length - 3} more
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="py-6 text-center text-gray-600">
                  {loading
                    ? 'Loading chart analysis...'
                    : tab === 'HIGH'
                    ? 'No HIGH-confidence setups today.'
                    : tab === 'BULLISH'
                    ? 'No bullish patterns detected.'
                    : tab === 'MULTI'
                    ? 'No stocks with multiple simultaneous patterns.'
                    : 'No patterns detected in the latest session.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
