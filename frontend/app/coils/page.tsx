'use client';

/**
 * /coils — "Coiled Springs" early-potential watchlist.
 *
 * The page the user asked for after watching ATLASBANG go 69→93 and GENEXIL
 * 28→42 without a heads-up: stocks with the potential to go high that have NOT
 * gone high yet. Built from the winner-anatomy study (docs/WINNER_ANATOMY.md)
 * and kept only where the point-in-time backtest (backtest_coil.py) confirmed
 * an edge: a tight, quiet base sitting on the 20-day average, above the
 * 200-day, upper 1-yr range with headroom, neutral RSI, not already running.
 *
 * Reads /api/coils (src/coil_scanner.py). Click a row → full manual analysis.
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Sprout, RefreshCw, Search } from 'lucide-react';
import FullAnalysisModal from '../components/FullAnalysisModal';
import MarketHealthMeter, { MarketHealth } from '../components/MarketHealthMeter';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const f1 = (n: number | null | undefined) => (n == null ? '—' : n.toFixed(1));

interface Coil {
  ticker: string;
  sector: string | null;
  price: number;
  stage: 'COILED' | 'CREEPING' | 'IGNITING';
  tier: 'TIGHT' | 'WIDE';
  score: number;
  grade: string;
  dist_sma20_pct: number | null;
  base_range20_pct: number | null;
  contraction: number | null;
  pos_1y: number | null;
  ath: number | null;
  ath_room_pct: number | null;
  rsi: number | null;
  rvol: number | null;
  rvol5: number | null;
  day_pct: number | null;
  ret_5d: number | null;
  ret_20d: number | null;
  sma200_rising: boolean;
  sma20_rising: boolean;
  sma50_rising: boolean;
  avg_vol20: number;
  target?: number | null;
  target_pct?: number | null;
  adjusted_for_action?: boolean;
  action_dates?: string[];
  reasons: string[];
  spark: number[];
}

interface CoilResponse {
  as_of: string | null;
  universe: number;
  count: number;
  counts?: { igniting?: number; creeping?: number; coiled?: number; tight?: number; wide?: number };
  stocks: Coil[];
  market?: MarketHealth | null;
}

const gradeColor = (g: string) =>
  g === 'A' ? 'bg-emerald-600 text-white'
  : g === 'B' ? 'bg-lime-600 text-black'
  : g === 'C' ? 'bg-yellow-600 text-black'
  : 'bg-orange-600 text-black';

/** Flat-then-now sparkline of the last ~6 months of closes. */
function Spark({ data }: { data: number[] }) {
  if (!data || data.length < 2) return <span className="text-gray-600 text-xs">—</span>;
  const w = 96, h = 30, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const px = (i: number) => pad + (i / (data.length - 1)) * (w - 2 * pad);
  const py = (v: number) => pad + (1 - (v - min) / rng) * (h - 2 * pad);
  const pts = data.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(' ');
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke="#e879f9" strokeWidth={1.5} />
      <circle cx={px(data.length - 1)} cy={py(data[data.length - 1])} r={2} fill="#f59e0b" />
    </svg>
  );
}

const STAGE_BADGE: Record<Coil['stage'], { label: string; cls: string; tip: string }> = {
  IGNITING: {
    label: '🔥 IGNITING',
    cls: 'bg-orange-900/60 text-orange-300 border-orange-600/60',
    tip: 'Volume just arrived (≥1.5x normal) on an up day while price is still near the coil — the catchable launch window is the first 1-2 days. Act fast or skip.',
  },
  CREEPING: {
    label: '🐢 CREEPING',
    cls: 'bg-lime-900/50 text-lime-300 border-lime-700/60',
    tip: 'Price has started rising quietly off the coil (2+ green closes, no volume tell) — the launch type that never confirms with volume. Aggressive.',
  },
  COILED: {
    label: '🧨 COILED',
    cls: 'bg-fuchsia-900/50 text-fuchsia-300 border-fuchsia-700/60',
    tip: 'Matches the winner launch DNA but has not started moving. A watchlist candidate — the trigger (news/operators) is invisible in the chart, so watch daily.',
  },
};

export default function CoilsPage() {
  const [data, setData] = useState<CoilResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<'ALL' | 'IGNITING' | 'CREEPING' | 'COILED'>('ALL');
  const [tierFilter, setTierFilter] = useState<'ALL' | 'TIGHT' | 'WIDE'>('ALL');
  const [active, setActive] = useState<string | null>(null);

  // silent = background poll; backend caches on a data-freshness fingerprint so
  // between scrapes these are a cheap cache hit (same pattern as /rebounds).
  const fetchList = (silent = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    axios
      .get<CoilResponse>(`${API_URL}/api/coils`)
      .then((res) => setData(res.data))
      .catch(() => { if (!silent) setError('Could not load the coiled-springs list.'); })
      .finally(() => { if (!silent) setLoading(false); });
  };

  useEffect(() => {
    fetchList();
    const id = setInterval(() => fetchList(true), 60000);
    return () => clearInterval(id);
  }, []);

  const rows = useMemo(() => data?.stocks ?? [], [data]);

  const sectorList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) counts.set(r.sector || 'Unknown', (counts.get(r.sector || 'Unknown') || 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    let out = rows;
    if (stageFilter !== 'ALL') out = out.filter((r) => r.stage === stageFilter);
    if (tierFilter !== 'ALL') out = out.filter((r) => r.tier === tierFilter);
    if (sectorFilter !== 'ALL') out = out.filter((r) => (r.sector || 'Unknown') === sectorFilter);
    if (q) out = out.filter((r) => r.ticker.includes(q));
    return out; // backend order: TIGHT first, then stage, then score
  }, [rows, stageFilter, tierFilter, sectorFilter, search]);

  return (
    <main className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-fuchsia-300 flex items-center gap-2">
            <Sprout className="w-8 h-8" /> Coiled Springs — Not High Yet
          </h1>
          <p className="text-gray-500 text-sm">
            Stocks matching the launch DNA of past big winners — quiet, tight, with room to run — BEFORE the move
          </p>
        </div>
        <div className="flex gap-3 flex-wrap items-center">
          {data && <span className="text-gray-500 text-sm">as of {data.as_of}</span>}
          <button
            onClick={() => fetchList()}
            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded flex items-center gap-2 transition text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </header>

      <MarketHealthMeter data={data?.market ?? null} asOf={data?.as_of} />

      {/* What this list is (and is not) — the honest contract */}
      <div className="mb-4 bg-fuchsia-950/25 border border-fuchsia-700/50 rounded-lg p-3 text-xs text-fuchsia-100/90 leading-relaxed">
        <b>🧨 The &ldquo;wish I&apos;d known at 69, not 93&rdquo; list.</b> We reverse-engineered every big DSE winner
        (docs/WINNER_ANATOMY.md): before they ran, most sat <b>quiet and tight on their 20-day average</b>, in the
        upper part of their yearly range, with headroom above and a neutral RSI — a <b>coiled spring</b>. This page
        lists every stock matching that DNA <b>right now</b>, before any move. The profile was then forward-tested
        point-in-time (2023-2026): a <b className="text-fuchsia-300">TIGHT</b> coil ran +20% within 30 sessions{' '}
        <b>18.5% of the time vs 15.6% for the market</b> — but its real, proven edge is safety: only a{' '}
        <b>7.9% chance of a −15% hit vs 18%</b> for the market, and <b>+10.5% vs +0.6%</b> average 3-month return.{' '}
        <b className="text-amber-300">WIDE</b> (12-15% base) keeps the winner odds at market-average risk — the
        aggressive tier. <b>What the chart cannot tell you is WHICH coil ignites</b> — the spark is news/operators,
        invisible in advance. So: watch the list daily, and when a coil turns{' '}
        <b className="text-orange-300">🔥 IGNITING</b> (volume just arrived on an up day), that is the study&apos;s
        act-in-the-first-1-2-days window. Never chase one that already left.
      </div>

      {error && <div className="mb-4 bg-red-950/40 border border-red-700 rounded p-3 text-sm text-red-300">{error}</div>}

      {/* Controls */}
      <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-gray-500">
            {loading && !data ? 'Scanning the market…' : (
              <><b className="text-fuchsia-300">{filtered.length}</b> shown{data && <> · {data.universe} scanned</>}</>
            )}
          </span>
          {([
            ['ALL', `All (${rows.length})`],
            ['IGNITING', `🔥 Igniting (${data?.counts?.igniting ?? 0})`],
            ['CREEPING', `🐢 Creeping (${data?.counts?.creeping ?? 0})`],
            ['COILED', `🧨 Coiled (${data?.counts?.coiled ?? 0})`],
          ] as ['ALL' | 'IGNITING' | 'CREEPING' | 'COILED', string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setStageFilter(key)}
              title={key === 'ALL' ? 'Every stage' : STAGE_BADGE[key].tip}
              className={`px-2 py-1 rounded border transition ${
                stageFilter === key
                  ? (key === 'IGNITING' ? 'bg-orange-800 text-orange-100 border-orange-600'
                    : key === 'CREEPING' ? 'bg-lime-800 text-lime-100 border-lime-600'
                    : 'bg-fuchsia-800 text-fuchsia-100 border-fuchsia-600')
                  : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
          <span className="text-gray-700">|</span>
          {([
            ['ALL', 'Both tiers'],
            ['TIGHT', `TIGHT (${data?.counts?.tight ?? 0})`],
            ['WIDE', `WIDE (${data?.counts?.wide ?? 0})`],
          ] as ['ALL' | 'TIGHT' | 'WIDE', string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTierFilter(key)}
              title={key === 'TIGHT'
                ? 'Base range ≤12% — the validated tier: fewer than half the market\'s −15% hits, +10.5% avg 3-month return'
                : key === 'WIDE'
                ? 'Base range 12-15% — same winner odds as TIGHT but market-average downside. Aggressive.'
                : 'Both tiers'}
              className={`px-2 py-1 rounded border transition ${
                tierFilter === key
                  ? 'bg-purple-800 text-purple-100 border-purple-600'
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
              className="bg-gray-900 border border-gray-700 focus:border-fuchsia-500 outline-none rounded pl-7 pr-2 py-1 text-white w-32 placeholder-gray-600"
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
        </div>
      </div>

      <div className="overflow-x-auto bg-gray-800/40 border border-gray-700 rounded-lg">
        <table className="text-left text-sm min-w-[1120px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="p-3" title="0-100 setup quality: base tightness (heaviest), coiled at the mean, volatility contraction, range position, neutral RSI, quiet volume, rising averages">GRADE</th>
              <th className="p-3" title="TIGHT = base ≤12% (the validated tier). WIDE = 12-15% (aggressive).">TIER</th>
              <th className="p-3" title="COILED = quiet setup · CREEPING = rising quietly · IGNITING = volume just arrived (act window)">STAGE</th>
              <th className="p-3">TICKER</th>
              <th className="p-3">SECTOR</th>
              <th className="p-3 text-right">PRICE</th>
              <th className="p-3 text-right" title="First upside objective — the nearest overhead resistance (same canonical number the chart shows). Context, not a promise.">TARGET</th>
              <th className="p-3" title="Last ~6 months of closes — a good coil looks FLAT">SHAPE</th>
              <th className="p-3 text-right" title="20-day high-low range as % of price. ≤12% = TIGHT (the trait that halves downside risk)">BASE</th>
              <th className="p-3 text-right" title="Distance from the 20-day average — every past winner launched within ±10%">VS 20-MA</th>
              <th className="p-3 text-right" title="Position in the 1-year range (0 = at the low, 1 = at the high). Sweet spot 0.55-0.75">1Y POS</th>
              <th className="p-3 text-right" title="Headroom back up to the old high — the room the spring can run">ROOM</th>
              <th className="p-3" title="Why it's on the list">WHY</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={r.ticker}
                onClick={() => setActive(r.ticker)}
                className="border-b border-gray-700/50 hover:bg-fuchsia-900/10 transition cursor-pointer"
                title="Click for the full analysis"
              >
                <td className="p-3">
                  <span className={`inline-flex items-center justify-center w-8 h-6 rounded font-bold ${gradeColor(r.grade)}`} title={`Score ${r.score}/100`}>
                    {r.grade}
                  </span>
                </td>
                <td className="p-3">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap border ${
                    r.tier === 'TIGHT'
                      ? 'bg-purple-900/50 text-purple-200 border-purple-600/60'
                      : 'bg-amber-900/40 text-amber-300 border-amber-700/60'
                  }`}
                    title={r.tier === 'TIGHT'
                      ? 'Validated tier: ≤12% base — half the market\'s downside risk in the backtest'
                      : 'Aggressive tier: 12-15% base — winner odds kept, market-average downside'}>
                    {r.tier}
                  </span>
                </td>
                <td className="p-3">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap border ${STAGE_BADGE[r.stage].cls}`}
                    title={STAGE_BADGE[r.stage].tip}>
                    {STAGE_BADGE[r.stage].label}
                  </span>
                </td>
                <td className="p-3 font-bold text-fuchsia-300 whitespace-nowrap">
                  {r.ticker}
                  {r.stage === 'IGNITING' && r.rvol != null && (
                    <span className="ml-1.5 text-[9px] bg-orange-700/70 text-orange-100 px-1 py-0.5 rounded align-middle" title={`Volume ${f1(r.rvol)}x normal today`}>
                      {f1(r.rvol)}x vol
                    </span>
                  )}
                </td>
                <td className="p-3 text-gray-400 text-xs max-w-[130px] truncate">{r.sector || '—'}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  <span className="text-gray-100 font-bold">{r.price}</span>
                  {r.day_pct != null && (
                    <div className={`text-[10px] ${r.day_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {r.day_pct >= 0 ? '+' : ''}{f1(r.day_pct)}% today
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
                <td className="p-3"><Spark data={r.spark} /></td>
                <td className="p-3 text-right whitespace-nowrap">
                  <span className={`font-bold ${(r.base_range20_pct ?? 99) <= 12 ? 'text-purple-300' : 'text-amber-300'}`}>
                    {f1(r.base_range20_pct)}%
                  </span>
                  {r.contraction != null && r.contraction <= 0.6 && (
                    <div className="text-[10px] text-gray-500" title="20-day range vs 60-day range — smaller = the spring is winding tighter">
                      wound {Math.round(r.contraction * 100)}%
                    </div>
                  )}
                </td>
                <td className="p-3 text-right whitespace-nowrap text-gray-300">
                  {r.dist_sma20_pct != null && r.dist_sma20_pct >= 0 ? '+' : ''}{f1(r.dist_sma20_pct)}%
                </td>
                <td className="p-3 text-right whitespace-nowrap text-gray-300">{r.pos_1y == null ? '—' : r.pos_1y.toFixed(2)}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  <span className="text-sky-300">+{f1(r.ath_room_pct)}%</span>
                  {(r.ath_room_pct ?? 0) > 100 && (
                    <div className="text-[10px] text-red-400" title="Very large headroom forward-tested as the risky class — speculative">⚠ spec</div>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-1 max-w-[280px]">
                    {r.rsi != null && <span className="text-[9px] bg-gray-700/60 text-gray-300 border border-gray-600 px-1 py-0.5 rounded">RSI {Math.round(r.rsi)}</span>}
                    {r.rvol5 != null && r.rvol5 <= 1.0 && <span className="text-[9px] bg-fuchsia-900/50 text-fuchsia-300 border border-fuchsia-800/60 px-1 py-0.5 rounded" title="Recent volume at/below normal — winners launched quiet">quiet {f1(r.rvol5)}x</span>}
                    {r.sma20_rising && <span className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded">20-MA ↑</span>}
                    {r.sma50_rising && <span className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded">50-MA ↑</span>}
                    {r.sma200_rising && <span className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded">200-MA ↑</span>}
                    {r.ret_20d != null && <span className="text-[9px] bg-gray-700/60 text-gray-400 border border-gray-600 px-1 py-0.5 rounded" title="20-session return — a good coil is FLAT">{r.ret_20d >= 0 ? '+' : ''}{f1(r.ret_20d)}%/20d</span>}
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && !loading && (
              <tr>
                <td colSpan={13} className="py-10 text-center text-gray-600">
                  No coiled springs match right now — the market isn&apos;t offering quiet tight setups.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 text-xs text-gray-600 leading-relaxed">
        ⚠️ Honesty note: the coil profile <b>narrows the field — it cannot pick the winner</b>. In the forward test
        roughly 1 in 5 of the TIGHT names ran +20% within 30 sessions; the rest mostly drifted (but rarely fell hard
        — that safety is the validated part). The spark that ignites a coil is news, results, or operator buying:
        <b> invisible in the chart in advance</b>. Watch the 🔥 IGNITING stage daily, click through for the full
        analysis, size small, and never chase a name that has already left its base. Prices as of {data?.as_of ?? 'the last scrape'}.
      </div>

      {active && (
        <FullAnalysisModal apiUrl={API_URL} ticker={active} onClose={() => setActive(null)} />
      )}
    </main>
  );
}
