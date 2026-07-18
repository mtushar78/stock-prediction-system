'use client';

/**
 * /momentum — Stage-2 Momentum Watchlist (techno-funda).
 *
 * The medium-term (3-9 month) momentum framework distilled from three DSE
 * strategy videos (docs/MOMENTUM_STRATEGY.md): filter the universe to
 * fundamentally-clean stocks in an early Stage-2 advance on the MONTHLY chart,
 * then time entries on the DAILY chart (volume breakout / launchpad / pullback).
 *
 * Two surfaces:
 *   1. THIS MONTH'S LOCKED WATCHLIST — the monthly-locked cohort (anti-churn
 *      discipline). Chosen once per calendar month; each name's live entry
 *      status updates daily.
 *   2. CANDIDATES — the full live scan, filterable/sortable.
 *
 * HONEST FRAMING: a structural screen, not a validated buy list. The one
 * combination that showed a real forward edge in the point-in-time backtest is a
 * daily breakout TRIGGER inside Stage-2 — those rows are badged ⚡ SETUP.
 *
 * Reads /api/momentum (src/momentum_scanner.py).
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Zap, RefreshCw, ArrowDownWideNarrow, Search, Lock, Info,
} from 'lucide-react';
import FullAnalysisModal from '../components/FullAnalysisModal';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const f1 = (n: number | null | undefined) => (n == null ? '—' : n.toFixed(1));

type Stage = 'EARLY_STAGE_2' | 'STAGE_2' | 'STAGE_1' | 'STAGE_3' | 'STAGE_4' | 'NEUTRAL';
type MaStack = 'STACKED_BULL' | 'PARTIAL' | 'ABOVE_20' | 'BELOW';
type Entry = 'TRIGGER' | 'LAUNCHPAD' | 'PULLBACK' | 'EXTENDED' | 'WAITING';

interface Momo {
  ticker: string;
  sector: string | null;
  price: number;
  score: number;
  grade: string;
  stage: Stage;
  stage_label: string;
  stage_confidence: string;
  months_since_cross: number | null;
  above_sma10_m: boolean;
  above_sma20_m: boolean;
  sma10_m_rising: boolean;
  broke_base: boolean;
  ma_stack: MaStack;
  launchpad: boolean;
  cluster_spread_pct: number | null;
  entry_status: Entry;
  breakout_trigger: boolean;
  ext_20d_high_pct: number | null;
  rvol: number | null;
  avg_vol20: number;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  sma20_rising: boolean;
  extended: boolean;
  pullback: boolean;
  ret_1m: number | null;
  ret_3m: number | null;
  rsi: number | null;
  category: string | null;
  eps: number | null;
  pe: number | null;
  market_cap_cr: number | null;
  is_insurer: boolean;
  techno_funda_pass: boolean;
  recent_dividend: boolean;
  adjusted_for_action: boolean;
  action_dates: string[];
  reasons: string[];
  spark: number[];
}

interface Locked {
  ticker: string;
  rank: number | null;
  locked_at: string | null;
  locked_as_of: string | null;
  locked_snapshot: Momo;
  live: Momo | null;
  in_scan: boolean;
}

interface Market {
  breadth_pct: number | null;
  label: string;
  above: number;
  total: number;
}

interface MomoResponse {
  as_of: string | null;
  cohort_month: string | null;
  universe: number;
  count: number;
  counts: {
    early_stage2: number; stage2: number; stage1: number;
    launchpad: number; trigger: number; techno_funda_pass: number;
  };
  watchlist_size: number;
  locked: Locked[];
  candidates: Momo[];
  market?: Market | null;
}

type SortKey = 'score' | 'ret_3m' | 'ret_1m' | 'rvol' | 'pe';

const gradeColor = (g: string) =>
  g === 'A' ? 'bg-emerald-600 text-white'
  : g === 'B' ? 'bg-lime-600 text-black'
  : g === 'C' ? 'bg-yellow-600 text-black'
  : 'bg-orange-600 text-black';

/** The single combination with a validated forward edge in the PIT backtest. */
const isValidatedSetup = (r: Momo) =>
  r.breakout_trigger && (r.stage === 'EARLY_STAGE_2' || r.stage === 'STAGE_2');

function StageBadge({ stage, label }: { stage: Stage; label: string }) {
  const map: Record<Stage, string> = {
    EARLY_STAGE_2: 'bg-emerald-900/60 text-emerald-200 border-emerald-600/70',
    STAGE_2: 'bg-teal-900/50 text-teal-200 border-teal-700/60',
    STAGE_1: 'bg-amber-900/40 text-amber-200 border-amber-700/60',
    STAGE_3: 'bg-orange-900/40 text-orange-200 border-orange-700/60',
    STAGE_4: 'bg-red-950/50 text-red-300 border-red-800/60',
    NEUTRAL: 'bg-gray-800 text-gray-400 border-gray-700',
  };
  const short: Record<Stage, string> = {
    EARLY_STAGE_2: '🚀 Early Stage 2', STAGE_2: 'Stage 2', STAGE_1: 'Stage 1 (base)',
    STAGE_3: 'Stage 3 (top)', STAGE_4: 'Stage 4 (down)', NEUTRAL: 'Neutral',
  };
  return (
    <span title={label} className={`text-[10px] px-1.5 py-0.5 rounded border font-bold whitespace-nowrap ${map[stage]}`}>
      {short[stage]}
    </span>
  );
}

function EntryBadge({ status }: { status: Entry }) {
  const map: Record<Entry, [string, string, string]> = {
    TRIGGER: ['⚡ Trigger', 'bg-green-800 text-green-100 border-green-600', 'Broke the 20-day high on ≥1.5x volume TODAY — the entry the backtest validated inside Stage-2'],
    LAUNCHPAD: ['◎ Launchpad', 'bg-purple-900/50 text-purple-200 border-purple-700/60', 'Daily 10/20/50 averages compressed into a tight cluster — coiled, volatility dried up. Watch for the breakout'],
    PULLBACK: ['↩ Pullback', 'bg-sky-900/50 text-sky-200 border-sky-700/60', 'Pulled back to a rising 20-day average — a lower-risk entry zone within the uptrend'],
    EXTENDED: ['▲ Extended', 'bg-orange-900/50 text-orange-200 border-orange-700/60', 'Well above its averages — too late to chase (FOMO). Wait for a pullback'],
    WAITING: ['· Waiting', 'bg-gray-800 text-gray-400 border-gray-700', 'No daily trigger yet — on the watchlist, waiting for a volume breakout'],
  };
  const [txt, cls, title] = map[status];
  return <span title={title} className={`text-[10px] px-1.5 py-0.5 rounded border font-bold whitespace-nowrap ${cls}`}>{txt}</span>;
}

function StackBadge({ s }: { s: MaStack }) {
  if (s === 'STACKED_BULL')
    return <span title="Price > 10 > 20 > 50 > 200-day averages — perfect momentum alignment" className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded whitespace-nowrap">10&gt;20&gt;50&gt;200</span>;
  if (s === 'PARTIAL')
    return <span title="Short/medium averages aligned bullishly, above the 50-day" className="text-[9px] bg-lime-900/40 text-lime-300 border border-lime-800/60 px-1 py-0.5 rounded whitespace-nowrap">short aligned</span>;
  if (s === 'ABOVE_20')
    return <span title="Above the 20-day average only" className="text-[9px] bg-gray-700/60 text-gray-300 border border-gray-600 px-1 py-0.5 rounded whitespace-nowrap">&gt; 20d</span>;
  return <span title="Below its averages" className="text-[9px] bg-gray-800 text-gray-500 border border-gray-700 px-1 py-0.5 rounded whitespace-nowrap">below</span>;
}

/** Monthly-close sparkline — the macro Stage story. */
function Spark({ data }: { data: number[] }) {
  if (!data || data.length < 2) return <span className="text-gray-600 text-xs">—</span>;
  const w = 96, h = 30, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const px = (i: number) => pad + (i / (data.length - 1)) * (w - 2 * pad);
  const py = (v: number) => pad + (1 - (v - min) / rng) * (h - 2 * pad);
  const pts = data.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(' ');
  const up = data[data.length - 1] >= data[0];
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={up ? '#818cf8' : '#f87171'} strokeWidth={1.5} />
    </svg>
  );
}

/** One row, shared by the locked table and the candidates table. */
function Row({ r, onClick, rank }: { r: Momo; onClick: () => void; rank?: number | null }) {
  const validated = isValidatedSetup(r);
  return (
    <tr
      onClick={onClick}
      className={`border-b border-gray-700/50 hover:bg-indigo-900/10 transition cursor-pointer ${validated ? 'bg-emerald-950/20' : ''}`}
      title="Click for the full analysis"
    >
      {rank !== undefined && (
        <td className="p-3 text-gray-500 text-xs text-center">{rank ?? '—'}</td>
      )}
      <td className="p-3">
        <span className={`inline-flex items-center justify-center w-8 h-6 rounded font-bold ${gradeColor(r.grade)}`} title={`Score ${r.score}/100`}>
          {r.grade}
        </span>
      </td>
      <td className="p-3"><StageBadge stage={r.stage} label={r.stage_label} /></td>
      <td className="p-3"><EntryBadge status={r.entry_status} /></td>
      <td className="p-3 font-bold text-indigo-300 whitespace-nowrap">
        {r.ticker}
        {validated && (
          <span className="ml-1.5 text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded align-middle" title="Breakout trigger inside a Stage-2 advance — the one combination that showed a real forward edge in the point-in-time backtest (+8% over 3 months vs +2% baseline). Still not a guarantee.">
            ⚡ SETUP
          </span>
        )}
        {r.techno_funda_pass && (
          <span className="ml-1.5 text-[9px] bg-blue-900/60 text-blue-200 border border-blue-700/60 px-1 py-0.5 rounded align-middle" title="Techno-funda clean: A-category, positive EPS, sane P/E, recent dividend. Hygiene / capital-protection context — not the return driver in testing.">
            TF ✓
          </span>
        )}
      </td>
      <td className="p-3 text-gray-400 text-xs max-w-[130px] truncate">{r.sector || '—'}</td>
      <td className="p-3 text-right whitespace-nowrap">
        <span className="text-gray-100 font-bold">{r.price}</span>
        {r.ret_3m != null && (
          <div className={`text-[10px] ${r.ret_3m >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {r.ret_3m >= 0 ? '+' : ''}{f1(r.ret_3m)}% / 3mo
          </div>
        )}
      </td>
      <td className="p-3"><Spark data={r.spark} /></td>
      <td className="p-3"><StackBadge s={r.ma_stack} /></td>
      <td className="p-3 text-right whitespace-nowrap text-xs">
        {r.pe != null ? <span className="text-gray-300">P/E {f1(r.pe)}</span> : <span className="text-gray-600">—</span>}
        {r.market_cap_cr != null && <div className="text-[10px] text-gray-500">{Math.round(r.market_cap_cr)} Cr</div>}
      </td>
      <td className="p-3">
        <div className="flex flex-wrap gap-1 max-w-[300px]">
          {r.launchpad && <span className="text-[9px] bg-purple-900/50 text-purple-300 border border-purple-800/60 px-1 py-0.5 rounded" title={`Averages compressed within ${f1(r.cluster_spread_pct)}%`}>launchpad</span>}
          {r.broke_base && <span className="text-[9px] bg-emerald-900/50 text-emerald-300 border border-emerald-800/60 px-1 py-0.5 rounded">base broken</span>}
          {r.rvol != null && r.rvol >= 1.5 && <span className="text-[9px] bg-yellow-800/50 text-yellow-200 border border-yellow-700/60 px-1 py-0.5 rounded">{f1(r.rvol)}x vol</span>}
          {r.rsi != null && <span className="text-[9px] bg-gray-700/60 text-gray-300 border border-gray-600 px-1 py-0.5 rounded">RSI {Math.round(r.rsi)}</span>}
          {r.months_since_cross != null && <span className="text-[9px] bg-gray-700/60 text-gray-400 border border-gray-600 px-1 py-0.5 rounded" title="Months the 10-month average has held above the 20-month">{r.months_since_cross}mo cross</span>}
        </div>
      </td>
    </tr>
  );
}

const TH = (
  <thead>
    <tr className="text-gray-500 text-xs border-b border-gray-700">
      <th className="p-3" title="0-100: monthly stage + structure + daily MA stack + launchpad + techno-funda quality. A ranking heuristic, not a return forecast.">GRADE</th>
      <th className="p-3" title="Weinstein stage on the MONTHLY chart. Early Stage 2 = a fresh breakout from a base. Stage 3/4 = topping/declining (avoid).">STAGE</th>
      <th className="p-3" title="Daily entry timing: Trigger (breakout now), Launchpad (coiled), Pullback (buyable dip), Extended (too late), Waiting.">ENTRY</th>
      <th className="p-3">TICKER</th>
      <th className="p-3">SECTOR</th>
      <th className="p-3 text-right">PRICE</th>
      <th className="p-3" title="Monthly close path — the macro Stage story">SHAPE</th>
      <th className="p-3" title="Daily moving-average alignment">MA STACK</th>
      <th className="p-3 text-right">VALUATION</th>
      <th className="p-3" title="Supporting signals">SIGNALS</th>
    </tr>
  </thead>
);

export default function MomentumPage() {
  const [data, setData] = useState<MomoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('score');
  const [stageFilter, setStageFilter] = useState<'ALL' | 'EARLY_STAGE_2' | 'STAGE_2' | 'STAGE_1' | 'SETUP'>('ALL');
  const [tfOnly, setTfOnly] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  const fetchList = () => {
    setLoading(true);
    setError(null);
    axios
      .get<MomoResponse>(`${API_URL}/api/momentum`)
      .then((res) => setData(res.data))
      .catch(() => setError('Could not load the momentum list.'))
      .finally(() => setLoading(false));
  };

  useEffect(fetchList, []);

  const rows = useMemo(() => data?.candidates ?? [], [data]);

  const sectorList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) counts.set(r.sector || 'Unknown', (counts.get(r.sector || 'Unknown') || 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    let out = rows;
    if (stageFilter === 'SETUP') out = out.filter(isValidatedSetup);
    else if (stageFilter !== 'ALL') out = out.filter((r) => r.stage === stageFilter);
    if (tfOnly) out = out.filter((r) => r.techno_funda_pass);
    if (sectorFilter !== 'ALL') out = out.filter((r) => (r.sector || 'Unknown') === sectorFilter);
    if (q) out = out.filter((r) => r.ticker.includes(q));
    return [...out].sort((a, b) => {
      const av = (a[sortBy] as number) ?? -9999;
      const bv = (b[sortBy] as number) ?? -9999;
      if (sortBy === 'pe') return (av <= 0 ? 9999 : av) - (bv <= 0 ? 9999 : bv); // cheapest first
      return bv - av || b.score - a.score;
    });
  }, [rows, stageFilter, tfOnly, sectorFilter, search, sortBy]);

  const market = data?.market;
  // Momentum wants HEALTHY breadth (the opposite of the reversal edge). Reframe
  // the breadth read for trend-following instead of reusing the reversal banner.
  const breadth = market?.breadth_pct ?? null;
  const favorable = breadth != null && breadth >= 55;

  return (
    <main className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-indigo-300 flex items-center gap-2">
            <Zap className="w-8 h-8" /> Momentum — Stage-2 Watchlist
          </h1>
          <p className="text-gray-500 text-sm">
            Fundamentally clean stocks in an early Stage-2 advance on the monthly chart · timed on the daily
          </p>
        </div>
        <div className="flex gap-3 flex-wrap items-center">
          {data && <span className="text-gray-500 text-sm">as of {data.as_of}</span>}
          <button
            onClick={fetchList}
            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded flex items-center gap-2 transition text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </header>

      {/* Momentum breadth banner — trend-following wants a HEALTHY tape. */}
      {breadth != null && (
        <div className={`mb-4 rounded-lg p-3 text-sm border flex items-center gap-3 ${
          favorable ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-100'
                    : 'bg-amber-950/30 border-amber-700/50 text-amber-100'}`}>
          <span className="text-2xl">{favorable ? '🟢' : '🟡'}</span>
          <div>
            <b>{favorable ? 'Favorable tape for momentum' : 'Cautious tape for momentum'}</b> —{' '}
            {f1(breadth)}% of liquid stocks are above their 50-day average ({market?.above}/{market?.total}).{' '}
            {favorable
              ? 'Trend-following breakouts work best when breadth is broad like this. New Stage-2 entries are in season.'
              : 'Breadth is thin — breakouts fail more often here. Favour the strongest names, size down, and let the launchpads mature.'}
            <span className="block text-[11px] text-gray-400 mt-0.5">
              Note: this is the inverse of the Rebounds page — mean-reversion pays in weak tape, momentum in strong tape.
            </span>
          </div>
        </div>
      )}

      {/* What this is (and is not) */}
      <div className="mb-4 bg-indigo-950/25 border border-indigo-700/50 rounded-lg p-3 text-xs text-indigo-100/90 leading-relaxed">
        <b>⚡ A monthly-commitment watchlist, not a buy list.</b> The framework (from your three strategy videos):
        filter to fundamentally-clean stocks in an <b>early Stage-2 advance</b> on the monthly chart, then time the
        entry on the daily chart. <b className="text-emerald-300">Stage badges</b> come from the 10/20-month averages;{' '}
        <b className="text-green-300">⚡ Trigger</b> = a volume breakout fired today. The point-in-time backtest is
        blunt about what works: the macro <b>stage is mainly an <i>avoidance</i> filter</b> (Stage 3/4 underperform),
        and the one combination with a real forward edge was a <b className="text-emerald-300">breakout Trigger inside
        Stage-2</b> (badged <b className="text-emerald-300">⚡ SETUP</b>, ~+8% over 3 months vs +2% baseline). The{' '}
        <b className="text-blue-300">TF ✓</b> techno-funda flag is <b>hygiene only</b> — it did <i>not</i> add returns
        in testing, so treat it as capital-protection context, not a buy reason. Click any row for the full analysis.
      </div>

      {error && <div className="mb-4 bg-red-950/40 border border-red-700 rounded p-3 text-sm text-red-300">{error}</div>}

      {/* ============ THIS MONTH'S LOCKED WATCHLIST ============ */}
      <section className="mb-8">
        <div className="flex items-center gap-2 mb-2">
          <Lock className="w-4 h-4 text-indigo-300" />
          <h2 className="text-lg font-bold text-indigo-200">This Month&apos;s Watchlist</h2>
          {data?.cohort_month && (
            <span className="text-xs bg-indigo-900/50 text-indigo-200 border border-indigo-700/60 px-2 py-0.5 rounded">
              {data.cohort_month} · {data.watchlist_size} names · locked
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500 mb-2 flex items-start gap-1">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          The anti-churn discipline from the videos: the list is chosen once per calendar month and committed to for the
          month. Each name&apos;s <b className="text-gray-400">&nbsp;live entry status&nbsp;</b> below still updates daily —
          you wait for a name to reach a Trigger, you don&apos;t swap the list around.
        </p>
        <div className="overflow-x-auto bg-gray-800/40 border border-indigo-800/40 rounded-lg">
          <table className="text-left text-sm min-w-[1120px] w-full">
            <thead>
              <tr className="text-gray-500 text-xs border-b border-gray-700">
                <th className="p-3 text-center" title="Rank at lock time">#</th>
                <th className="p-3">GRADE</th>
                <th className="p-3">STAGE</th>
                <th className="p-3">ENTRY</th>
                <th className="p-3">TICKER</th>
                <th className="p-3">SECTOR</th>
                <th className="p-3 text-right">PRICE</th>
                <th className="p-3">SHAPE</th>
                <th className="p-3">MA STACK</th>
                <th className="p-3 text-right">VALUATION</th>
                <th className="p-3">SIGNALS</th>
              </tr>
            </thead>
            <tbody>
              {(data?.locked ?? []).map((lr) => {
                const r = lr.live ?? lr.locked_snapshot;
                return (
                  <Row
                    key={lr.ticker}
                    r={r}
                    rank={lr.rank}
                    onClick={() => setActive(lr.ticker)}
                  />
                );
              })}
              {(!data || data.locked.length === 0) && !loading && (
                <tr><td colSpan={11} className="py-8 text-center text-gray-600">
                  No watchlist locked yet for this month — it locks on the first load of a new calendar month.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ============ CANDIDATES (live scan) ============ */}
      <section>
        <h2 className="text-lg font-bold text-gray-200 mb-2">Candidates — full live scan</h2>

        {/* Controls */}
        <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <span className="text-gray-500">
              {loading && !data ? 'Scanning the market…' : (
                <><b className="text-indigo-300">{filtered.length}</b> shown{data && <> · {data.universe} scanned</>}</>
              )}
            </span>
            {([
              ['ALL', `All (${rows.length})`],
              ['SETUP', `⚡ Setup (${rows.filter(isValidatedSetup).length})`],
              ['EARLY_STAGE_2', `🚀 Early S2 (${data?.counts.early_stage2 ?? 0})`],
              ['STAGE_2', `Stage 2 (${data?.counts.stage2 ?? 0})`],
              ['STAGE_1', `Stage 1 (${data?.counts.stage1 ?? 0})`],
            ] as ['ALL' | 'SETUP' | 'EARLY_STAGE_2' | 'STAGE_2' | 'STAGE_1', string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setStageFilter(key)}
                className={`px-2 py-1 rounded border transition ${
                  stageFilter === key
                    ? (key === 'SETUP' ? 'bg-emerald-800 text-emerald-100 border-emerald-600'
                      : 'bg-indigo-800 text-indigo-100 border-indigo-600')
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
            <button
              onClick={() => setTfOnly((v) => !v)}
              title="Show only techno-funda-clean names (A-category, positive EPS, sane P/E, recent dividend). Hygiene filter — did not add returns in testing."
              className={`px-2 py-1 rounded border transition ${
                tfOnly ? 'bg-blue-800 text-blue-100 border-blue-600' : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'
              }`}
            >
              TF ✓ only ({data?.counts.techno_funda_pass ?? 0})
            </button>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="find ticker…"
                className="bg-gray-900 border border-gray-700 focus:border-indigo-500 outline-none rounded pl-7 pr-2 py-1 text-white w-32 placeholder-gray-600"
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
                ['score', 'Best'],
                ['ret_3m', '3mo momentum'],
                ['ret_1m', '1mo momentum'],
                ['rvol', 'Volume'],
                ['pe', 'Cheapest P/E'],
              ] as [SortKey, string][]).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setSortBy(key)}
                  className={`px-2 py-1 rounded border transition ${
                    sortBy === key
                      ? 'bg-indigo-800 text-indigo-100 border-indigo-600'
                      : 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {(sectorFilter !== 'ALL' || search || stageFilter !== 'ALL' || tfOnly) && (
          <div className="mb-2 text-xs text-indigo-300/80">
            Filtered · <button onClick={() => { setSectorFilter('ALL'); setSearch(''); setStageFilter('ALL'); setTfOnly(false); }} className="underline hover:text-indigo-200">clear</button>
          </div>
        )}

        <div className="overflow-x-auto bg-gray-800/40 border border-gray-700 rounded-lg">
          <table className="text-left text-sm min-w-[1080px] w-full">
            {TH}
            <tbody>
              {filtered.map((r) => (
                <Row key={r.ticker} r={r} onClick={() => setActive(r.ticker)} />
              ))}
              {filtered.length === 0 && !loading && (
                <tr><td colSpan={10} className="py-10 text-center text-gray-600">
                  Nothing matches — try clearing the filters.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="mt-4 text-xs text-gray-600 leading-relaxed">
        ⚠️ Honesty note: this is a <b>structural + techno-funda screen</b>, not a validated edge. In the point-in-time
        backtest, Stage-2 membership alone ≈ the market average; only a <b>breakout Trigger inside Stage-2</b> beat it,
        and the fundamentals gate did not add returns. Use this to <b>build a disciplined monthly watchlist</b> and catch
        Stage-2 launches early — size small, honour a stop, and check the full analysis first. See
        docs/MOMENTUM_STRATEGY.md. Prices as of {data?.as_of ?? 'the last scrape'}.
      </div>

      {active && (
        <FullAnalysisModal apiUrl={API_URL} ticker={active} onClose={() => setActive(null)} />
      )}
    </main>
  );
}
