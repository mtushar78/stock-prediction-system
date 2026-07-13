'use client';

/**
 * /rebounds — "Turning Up" watchlist.
 *
 * Surfaces stocks that fell a long way from a prior high, based out over time,
 * and are NOW curving back up (the "was 120 → ground down to a 50-60 base →
 * ticking to 61-62" shape the user described). This is a TRACKING list, not a
 * buy list: a curl off a base can fail. Each row shows the fall→base→turn story
 * plus a sparkline; clicking opens the full manual analysis in a modal.
 *
 * Reads /api/rebounds (src/rebound_scanner.py).
 */

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import {
  TrendingUp, RefreshCw, Activity, Rocket, ArrowDownWideNarrow, Search,
} from 'lucide-react';
import FullAnalysisModal from '../components/FullAnalysisModal';
import MarketHealthMeter, { MarketHealth } from '../components/MarketHealthMeter';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Round a number for display (percentages, multiples); '—' when missing. */
const f1 = (n: number | null | undefined) => (n == null ? '—' : n.toFixed(1));

interface Rebound {
  ticker: string;
  sector: string | null;
  price: number;
  peak: number;
  peak_date: string;
  trough: number;
  trough_date: string;
  drawdown_pct: number;
  off_low_pct: number;
  from_peak_pct: number;
  recovery_room_pct: number;
  target?: number | null;
  target_pct?: number | null;
  days_since_trough: number;
  fall_span_bars: number;
  ret_5d: number | null;
  ret_10d: number | null;
  sma20: number | null;
  above_sma20: boolean;
  sma20_rising: boolean;
  range_pos: number | null;
  rsi: number | null;
  avg_vol20: number;
  rvol: number | null;
  vol_pickup: number | null;
  curl_score: number;
  stage?: 'TURNING' | 'EARLY' | 'FRESH';
  score: number;
  grade: string;
  is_reversal?: boolean;
  adjusted_for_action?: boolean;
  action_dates?: string[];
  reasons: string[];
  spark: number[];
  spark_low_idx?: number;
}

interface RebResponse {
  as_of: string | null;
  universe: number;
  count: number;
  fresh?: number;
  turning?: number;
  early?: number;
  stocks: Rebound[];
  market?: MarketHealth | null;
}

type SortKey = 'score' | 'off_low_pct' | 'drawdown_pct' | 'recovery_room_pct' | 'ret_10d';

const gradeColor = (g: string) =>
  g === 'A' ? 'bg-emerald-600 text-white'
  : g === 'B' ? 'bg-lime-600 text-black'
  : g === 'C' ? 'bg-yellow-600 text-black'
  : 'bg-orange-600 text-black';

/** Tiny inline sparkline of the price path from the prior peak to now (fall +
 *  base + curl). `lowIdx` is the base-low position supplied by the backend. */
function Spark({ data, up, lowIdx }: { data: number[]; up: boolean; lowIdx?: number }) {
  if (!data || data.length < 2) return <span className="text-gray-600 text-xs">—</span>;
  const w = 96, h = 30, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const px = (i: number) => pad + (i / (data.length - 1)) * (w - 2 * pad);
  const py = (v: number) => pad + (1 - (v - min) / rng) * (h - 2 * pad);
  const pts = data.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(' ');
  const stroke = up ? '#34d399' : '#f87171';
  // Mark the base low (the trough we're recovering from). Fall back to the
  // series minimum if the backend didn't supply an index.
  const li = (lowIdx != null && lowIdx >= 0 && lowIdx < data.length) ? lowIdx : data.indexOf(min);
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth={1.5} />
      <circle cx={px(li)} cy={py(data[li])} r={2} fill="#f59e0b" />
    </svg>
  );
}

export default function ReboundsPage() {
  const [data, setData] = useState<RebResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('score');
  const [stageFilter, setStageFilter] = useState<'ALL' | 'FRESH' | 'EARLY' | 'TURNING'>('ALL');
  const [active, setActive] = useState<string | null>(null);

  const fetchList = () => {
    setLoading(true);
    setError(null);
    axios
      .get<RebResponse>(`${API_URL}/api/rebounds`)
      .then((res) => setData(res.data))
      .catch(() => setError('Could not load the rebounds list.'))
      .finally(() => setLoading(false));
  };

  useEffect(fetchList, []);

  const rows = useMemo(() => data?.stocks ?? [], [data]);

  const sectorList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) counts.set(r.sector || 'Unknown', (counts.get(r.sector || 'Unknown') || 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    let out = rows;
    if (stageFilter !== 'ALL') out = out.filter((r) => (r.stage || 'TURNING') === stageFilter);
    if (sectorFilter !== 'ALL') out = out.filter((r) => (r.sector || 'Unknown') === sectorFilter);
    if (q) out = out.filter((r) => r.ticker.includes(q));
    return [...out].sort((a, b) => {
      // Sort purely by the chosen key. The backend score already rewards a fresh
      // green turn right off the low and penalises names that have "already gone
      // high", so the default (score) surfaces the aggressive just-turning
      // candidates first — stage is a badge, not a sort gate.
      const av = (a[sortBy] as number) ?? -9999;
      const bv = (b[sortBy] as number) ?? -9999;
      // off_low: smaller is "earlier / better", so ascending; others descending.
      if (sortBy === 'off_low_pct') return av - bv;
      return bv - av || b.score - a.score;
    });
  }, [rows, sectorFilter, search, sortBy, stageFilter]);

  return (
    <main className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-teal-300 flex items-center gap-2">
            <TrendingUp className="w-8 h-8" /> Turning Up — Rebound Watchlist
          </h1>
          <p className="text-gray-500 text-sm">
            Fallen from a high · based out · now curving back up — stocks worth tracking
          </p>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <nav className="flex gap-1 text-sm">
            <Link href="/" className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4" /> Dashboard
            </Link>
            <Link href="/chart-analysis" className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-purple-900/40 hover:text-purple-200 transition flex items-center gap-1.5">
              <Activity className="w-4 h-4" /> Chart Analyst
            </Link>
            <Link href="/rebounds" className="px-3 py-1.5 rounded bg-teal-700 text-white border border-teal-600 flex items-center gap-1.5">
              <Rocket className="w-4 h-4" /> Rebounds
            </Link>
          </nav>
          {data && <span className="text-gray-500 text-sm">as of {data.as_of}</span>}
          <button
            onClick={fetchList}
            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded flex items-center gap-2 transition text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </header>

      {/* Market SEASON — mean-reversion turns only pay in weak tape (weekly-system
          study). This is the single most important context for acting on the list. */}
      <MarketHealthMeter data={data?.market ?? null} asOf={data?.as_of} />

      {/* What this list is (and is not) */}
      <div className="mb-4 bg-teal-950/25 border border-teal-700/50 rounded-lg p-3 text-xs text-teal-100/90 leading-relaxed">
        <b>🔭 A watchlist of turns, not a buy list.</b> Stocks that pulled back and are <b>starting to turn back up</b>.
        Three stages, most aggressive first:{' '}
        <b className="text-green-300">⚡ FRESH</b> = a short-term dip that printed a low in the last 1-5 days and is
        putting in <b>green candles right off that low</b> — the freshest, most aggressive turns (no deep fall required);{' '}
        <b className="text-amber-300">🌱 EARLY</b> = fell hard, based out, and is just showing the first 1-2 days of
        strength before the averages confirm;{' '}
        <b className="text-teal-300">🚀 TURNING</b> = the established curl (reclaimed/rising short-term average,
        momentum positive) — higher conviction. The <b>TARGET</b> column is the first overhead resistance the price
        must reclaim. Neither the stages nor the target promise anything — a turn can roll over. Use this to{' '}
        <b>catch turns early and track them</b>, then click any row for the full manual analysis before deciding. The{' '}
        <span className="text-amber-400">●</span> dot on each sparkline marks the low.
      </div>

      {error && <div className="mb-4 bg-red-950/40 border border-red-700 rounded p-3 text-sm text-red-300">{error}</div>}

      {/* Controls */}
      <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-gray-500">
            {loading && !data ? 'Scanning the market…' : (
              <><b className="text-teal-300">{filtered.length}</b> shown{data && <> · {data.universe} scanned</>}</>
            )}
          </span>
          {/* Stage filter: freshest turns first, then early-at-the-base, then mature */}
          {([
            ['ALL', `All (${rows.length})`],
            ['FRESH', `⚡ Fresh (${data?.fresh ?? 0})`],
            ['EARLY', `🌱 Early (${data?.early ?? 0})`],
            ['TURNING', `🚀 Turning (${data?.turning ?? 0})`],
          ] as ['ALL' | 'FRESH' | 'EARLY' | 'TURNING', string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setStageFilter(key)}
              title={key === 'FRESH'
                ? 'Most aggressive: dipped over the last few days, printed a low in the last 1-5 sessions, and is putting in green candles right off that low — the freshest turns (no deep fall required)'
                : key === 'EARLY'
                ? 'Aggressive bucket: fell hard, based out, and is just showing the first signs of turning up (averages not yet confirmed) — more speculative'
                : key === 'TURNING'
                ? 'Established turns: reclaimed/rising short-term average with momentum turning positive'
                : 'Every stage'}
              className={`px-2 py-1 rounded border transition ${
                stageFilter === key
                  ? (key === 'FRESH' ? 'bg-green-800 text-green-100 border-green-600'
                    : key === 'EARLY' ? 'bg-amber-800 text-amber-100 border-amber-600'
                    : 'bg-teal-800 text-teal-100 border-teal-600')
                  : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="find ticker…"
              className="bg-gray-900 border border-gray-700 focus:border-teal-500 outline-none rounded pl-7 pr-2 py-1 text-white w-32 placeholder-gray-600"
            />
          </div>
          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            className="bg-gray-800 text-gray-200 rounded px-2 py-1 border border-gray-700 max-w-[180px]"
          >
            <option value="ALL">All sectors ({rows.length})</option>
            {sectorList.map(([s, n]) => (
              <option key={s} value={s}>{s} ({n})</option>
            ))}
          </select>
          <div className="flex items-center gap-1">
            <ArrowDownWideNarrow className="w-4 h-4 text-gray-500" />
            <span className="text-gray-500 mr-1">Sort:</span>
            {([
              ['score', 'Best turn'],
              ['off_low_pct', 'Earliest'],
              ['drawdown_pct', 'Biggest fall'],
              ['recovery_room_pct', 'Most upside'],
              ['ret_10d', '10d momentum'],
            ] as [SortKey, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setSortBy(key)}
                className={`px-2 py-1 rounded border transition ${
                  sortBy === key
                    ? 'bg-teal-800 text-teal-100 border-teal-600'
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {(sectorFilter !== 'ALL' || search) && (
        <div className="mb-2 text-xs text-teal-300/80">
          Filtered · <button onClick={() => { setSectorFilter('ALL'); setSearch(''); }} className="underline hover:text-teal-200">clear</button>
        </div>
      )}

      <div className="overflow-x-auto bg-gray-800/40 border border-gray-700 rounded-lg">
        <table className="text-left text-sm min-w-[1080px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="p-3" title="0-100 quality of the turn: MA reclaim/slope + momentum + how early + volume pickup + base quality">GRADE</th>
              <th className="p-3" title="TURNING = established curl (averages turned up). EARLY = still at the base, just starting to move up — more aggressive/speculative.">STAGE</th>
              <th className="p-3">TICKER</th>
              <th className="p-3">SECTOR</th>
              <th className="p-3 text-right">PRICE</th>
              <th className="p-3 text-right" title="First upside objective — the nearest overhead resistance the price must reclaim (capped at the old high). Context, not a promise.">TARGET</th>
              <th className="p-3" title="Recent price path — the ● marks the base low">SHAPE</th>
              <th className="p-3 text-right" title="Peak → trough fall">FELL</th>
              <th className="p-3 text-right" title="How far price has bounced off the base low (smaller = earlier)">OFF LOW</th>
              <th className="p-3 text-right" title="How far price still sits below the old high">VS HIGH</th>
              <th className="p-3 text-right" title="Upside back to the old high (context, not a target)">ROOM</th>
              <th className="p-3" title="Why it's flagged as turning up">THE TURN</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={r.ticker}
                onClick={() => setActive(r.ticker)}
                className="border-b border-gray-700/50 hover:bg-teal-900/10 transition cursor-pointer"
                title="Click for the full analysis"
              >
                <td className="p-3">
                  <span className={`inline-flex items-center justify-center w-8 h-6 rounded font-bold ${gradeColor(r.grade)}`} title={`Score ${r.score}/100`}>
                    {r.grade}
                  </span>
                </td>
                <td className="p-3">
                  {r.stage === 'FRESH' ? (
                    <span className="text-[10px] bg-green-900/50 text-green-300 border border-green-700/60 px-1.5 py-0.5 rounded font-bold whitespace-nowrap"
                      title="Freshest turn — dipped over the last few days, low in the last 1-5 sessions, green candles right off it. Most aggressive.">
                      ⚡ FRESH
                    </span>
                  ) : r.stage === 'EARLY' ? (
                    <span className="text-[10px] bg-amber-900/50 text-amber-300 border border-amber-700/60 px-1.5 py-0.5 rounded font-bold whitespace-nowrap"
                      title="At the base, just starting to turn up — averages not yet confirmed. Aggressive / speculative.">
                      🌱 EARLY
                    </span>
                  ) : (
                    <span className="text-[10px] bg-teal-900/50 text-teal-300 border border-teal-700/60 px-1.5 py-0.5 rounded font-bold whitespace-nowrap"
                      title="Established turn — reclaimed/rising short-term average with momentum turning positive.">
                      🚀 TURNING
                    </span>
                  )}
                </td>
                <td className="p-3 font-bold text-teal-300 whitespace-nowrap">
                  {r.ticker}
                  {r.is_reversal && (
                    <span className="ml-1.5 text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded align-middle" title="Also firing on the validated v10 reversal signal — the strongest overlap on this list">
                      REVERSAL ✓
                    </span>
                  )}
                  {r.rvol != null && r.rvol >= 2 && (
                    <span className="ml-1.5 text-[9px] bg-yellow-700/60 text-yellow-200 px-1 py-0.5 rounded align-middle" title={`Volume ${f1(r.rvol)}x average today`}>
                      {f1(r.rvol)}x vol
                    </span>
                  )}
                </td>
                <td className="p-3 text-gray-400 text-xs max-w-[130px] truncate">{r.sector || '—'}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  <span className="text-gray-100 font-bold">{r.price}</span>
                  {r.ret_10d != null && (
                    <div className={`text-[10px] ${r.ret_10d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {r.ret_10d >= 0 ? '+' : ''}{f1(r.ret_10d)}% / 10d
                    </div>
                  )}
                </td>
                <td className="p-3 text-right whitespace-nowrap">
                  {r.target != null ? (
                    <>
                      <span className="text-amber-300 font-bold">{r.target}</span>
                      {r.target_pct != null && (
                        <div className="text-[10px] text-sky-300">+{f1(r.target_pct)}% upside</div>
                      )}
                    </>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </td>
                <td className="p-3"><Spark data={r.spark} up={(r.ret_10d ?? 0) >= 0} lowIdx={r.spark_low_idx} /></td>
                <td className="p-3 text-right whitespace-nowrap">
                  <span className="text-red-300 font-bold">−{f1(r.drawdown_pct)}%</span>
                  {r.adjusted_for_action && (
                    <span
                      className="ml-1 text-[9px] bg-purple-900/50 text-purple-300 border border-purple-800/60 px-1 py-0.5 rounded align-middle"
                      title={`Fall back-adjusted for a corporate action (${(r.action_dates || []).join(', ')}) so an ex-dividend/bonus drop isn't counted as selling`}
                    >
                      adj
                    </span>
                  )}
                  <div className="text-[10px] text-gray-500">{f1(r.peak)} → {f1(r.trough)}</div>
                </td>
                <td className="p-3 text-right whitespace-nowrap text-emerald-300 font-bold">+{f1(r.off_low_pct)}%</td>
                <td className="p-3 text-right whitespace-nowrap text-gray-300">{f1(r.from_peak_pct)}%</td>
                <td className="p-3 text-right whitespace-nowrap text-sky-300">+{f1(r.recovery_room_pct)}%</td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-1 max-w-[280px]">
                    {r.above_sma20 && <span className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded">&gt; 20-MA</span>}
                    {r.sma20_rising && <span className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded">20-MA ↑</span>}
                    {r.vol_pickup != null && r.vol_pickup >= 1.3 && <span className="text-[9px] bg-sky-900/50 text-sky-300 border border-sky-800/60 px-1 py-0.5 rounded">vol {f1(r.vol_pickup)}x</span>}
                    {r.rsi != null && <span className="text-[9px] bg-gray-700/60 text-gray-300 border border-gray-600 px-1 py-0.5 rounded">RSI {Math.round(r.rsi)}</span>}
                    <span className="text-[9px] bg-gray-700/60 text-gray-400 border border-gray-600 px-1 py-0.5 rounded" title="Trading days since the base low">{r.days_since_trough}d off low</span>
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && !loading && (
              <tr>
                <td colSpan={12} className="py-10 text-center text-gray-600">
                  No stocks are turning up off a base right now — the market isn&apos;t offering clean rebounds.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 text-xs text-gray-600 leading-relaxed">
        ⚠️ Honesty note: this is a <b>structural filter</b>, not a validated edge. A stock curling off a base is
        catching a falling knife by design — many turns fail and roll back over. Treat these as candidates to
        <b> watch and research</b>, size small if you act, and always check the full analysis (and why it fell) first.
        Prices as of {data?.as_of ?? 'the last scrape'}.
      </div>

      {active && (
        <FullAnalysisModal apiUrl={API_URL} ticker={active} onClose={() => setActive(null)} />
      )}
    </main>
  );
}
