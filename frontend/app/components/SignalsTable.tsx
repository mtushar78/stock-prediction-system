import { Signal } from '../types';
import { AlertCircle, Info, Flame, Sparkles, HelpCircle, Rocket, ChevronDown, ChevronRight, TrendingDown } from 'lucide-react';
import { useState } from 'react';
import { breakoutGrade, gradeColor } from './breakoutGrade';
import { reversalGrade } from './reversalGrade';

interface SignalsTableProps {
  signals: Signal[];
  loading: boolean;
  marketHealthy?: boolean;
  marketBreadth?: number | null;
  /** ticker → 6-step Graham quality score (0–6), from /api/quality-screen */
  qualityMap?: Record<string, number>;
  onVolumeClick: (signal: Signal) => void;
  onInfoClick: (signal: Signal) => void;
  onBreakoutInfoClick: (signal: Signal) => void;
  onReversalInfoClick: (signal: Signal) => void;
  onOverheatedInfoClick: (signal: Signal) => void;
  onPriceInfoClick: (signal: Signal) => void;
  activeTicker: string | null;
}

type ViewTab = 'ALL' | 'EARLY' | 'BUY' | 'FRESH';
type SortKey = 'Score' | 'EarlyScore' | 'RVOL' | 'Price' | 'Ticker';
type SortDir = 'asc' | 'desc';

function reasonsToString(r: unknown): string {
  if (Array.isArray(r)) return r.join(', ');
  if (typeof r === 'string') return r.replace(/^\[|\]$/g, '').replace(/'/g, '');
  return '';
}

/** Short "why it fired" summary for the breakout table row. */
function breakoutWhy(sig: Signal): string {
  const c = sig.BreakoutChecks || {};
  const parts: string[] = [`New ${c.lookback ?? 20}d high`];
  if (typeof c.ret_20d === 'number') parts.push(`+${Math.round(c.ret_20d)}%/20d`);
  if (sig.RVOL) parts.push(`RVOL ${sig.RVOL}×`);
  parts.push('uptrend');
  return parts.join(' · ');
}

/** Short "why it fired" summary for the reversal table row. */
function reversalWhy(sig: Signal): string {
  const c = sig.ReversalChecks || {};
  const parts: string[] = [];
  if (typeof c.rsi === 'number') parts.push(`RSI ${Math.round(c.rsi)} oversold`);
  if (typeof c.room_pct === 'number') parts.push(`${Math.round(c.room_pct)}% below 120d high`);
  if (typeof c.ret5 === 'number') parts.push(`${Math.round(c.ret5)}%/5d`);
  if (sig.RVOL) parts.push(`RVOL ${sig.RVOL}×`);
  parts.push('green day');
  return parts.join(' · ');
}

/** Heat badge color by level (EXTREME hottest). */
function heatColor(level?: string): string {
  return level === 'EXTREME' ? 'bg-red-600 text-white'
    : level === 'HOT' ? 'bg-orange-600 text-white'
    : 'bg-amber-700 text-amber-100';
}

/** Short "why it's hot" summary for the overheated row. */
function overheatedWhy(sig: Signal): string {
  const r = sig.OverheatedReasons;
  if (Array.isArray(r) && r.length) return r.join(' · ');
  const c = sig.OverheatedChecks || {};
  const parts: string[] = [];
  if (typeof c.rsi === 'number') parts.push(`RSI ${Math.round(c.rsi)}`);
  if (typeof c.ret20 === 'number') parts.push(`+${Math.round(c.ret20)}%/20d`);
  return parts.join(' · ');
}

/** Short "why it's moving" summary for the cheap-movers row. */
function momentumWhy(sig: Signal): string {
  const r = sig.MomentumReasons;
  if (Array.isArray(r) && r.length) return r.join(' · ');
  const c = sig.MomentumChecks || {};
  const parts: string[] = [];
  if (typeof c.ret5 === 'number') parts.push(`+${Math.round(c.ret5)}%/5d`);
  if (sig.RVOL) parts.push(`RVOL ${sig.RVOL}×`);
  return parts.join(' · ');
}

export default function SignalsTable({
  signals,
  loading,
  marketHealthy,
  marketBreadth,
  qualityMap,
  onVolumeClick,
  onInfoClick,
  onBreakoutInfoClick,
  onReversalInfoClick,
  onOverheatedInfoClick,
  onPriceInfoClick,
  activeTicker,
}: SignalsTableProps) {
  const [legacy, setLegacy] = useState(false);
  // REVERSAL is the default list: it is the one signal with a strong edge net
  // of commission (+5.1%/trade, 65% win vs breakout's +0.3%) — see
  // docs/PROFITABILITY_AUDIT.md.
  const [list, setList] = useState<'BREAKOUT' | 'REVERSAL' | 'OVERHEATED' | 'MOVERS'>('REVERSAL');
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<ViewTab>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('Score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showLegend, setShowLegend] = useState(false);

  const breakouts = signals
    .filter((s) => s.BreakoutSignal)
    .map((s) => ({ s, g: breakoutGrade(s.BreakoutChecks, marketBreadth) }))
    .sort((a, b) => b.g.score - a.g.score
      || Number(b.s.IsFreshBreakout) - Number(a.s.IsFreshBreakout)
      || (b.s.RVOL || 0) - (a.s.RVOL || 0));

  // v10 REVERSAL list — buy-the-bottom, ranked best-first by reversal grade.
  const reversals = signals
    .filter((s) => s.ReversalSignal)
    .map((s) => ({ s, g: reversalGrade(s.ReversalChecks) }))
    .sort((a, b) => b.g.score - a.g.score
      || Number(b.s.IsFreshReversal) - Number(a.s.IsFreshReversal)
      || (b.s.RVOL || 0) - (a.s.RVOL || 0));

  // v11 OVERHEATED list — the take-profit / avoid warning, hottest first.
  const overheated = signals
    .filter((s) => s.OverheatedSignal)
    .sort((a, b) => (b.OverheatedChecks?.heat_score || 0) - (a.OverheatedChecks?.heat_score || 0));

  // v13 CHEAP MOVERS — cheap (<100 tk) short-term momentum, strongest first.
  const movers = signals
    .filter((s) => s.MomentumSignal && (s.Price || 0) < 100)
    .sort((a, b) => (b.MomentumChecks?.mo_score || 0) - (a.MomentumChecks?.mo_score || 0));

  // ---- ticker search filter (applies to whichever list is active) ----
  const q = search.trim().toUpperCase();
  const fb = q ? breakouts.filter(({ s }) => s.Ticker.includes(q)) : breakouts;
  const fr = q ? reversals.filter(({ s }) => s.Ticker.includes(q)) : reversals;
  const fo = q ? overheated.filter((s) => s.Ticker.includes(q)) : overheated;
  const fm = q ? movers.filter((s) => s.Ticker.includes(q)) : movers;

  // ---- legacy table (only when expanded) ----
  const filtered = signals.filter((s) => {
    if (tab === 'EARLY') return s.EarlySignal === 'EARLY' || s.EarlySignal === 'WATCH';
    if (tab === 'BUY') return s.Signal === 'BUY';
    if (tab === 'FRESH') return s.IsFreshBuy || s.IsFreshEarly;
    return true;
  });
  const sorted = [...filtered].sort((a, b) => {
    const av = (a[sortKey] as number | string | undefined) ?? (typeof a[sortKey] === 'string' ? '' : 0);
    const bv = (b[sortKey] as number | string | undefined) ?? (typeof b[sortKey] === 'string' ? '' : 0);
    if (typeof av === 'string' && typeof bv === 'string') {
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    const an = Number(av) || 0; const bn = Number(bv) || 0;
    return sortDir === 'asc' ? an - bn : bn - an;
  });
  const countEarly = signals.filter((s) => s.EarlySignal === 'EARLY' || s.EarlySignal === 'WATCH').length;
  const countBuy = signals.filter((s) => s.Signal === 'BUY').length;
  const countFresh = signals.filter((s) => s.IsFreshBuy || s.IsFreshEarly).length;

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    else { setSortKey(k); setSortDir('desc'); }
  };
  const arrow = (k: SortKey) => sortKey === k ? (sortDir === 'desc' ? ' ▼' : ' ▲') : '';
  const sortableHeader = (k: SortKey, label: string, title?: string) => (
    <th onClick={() => toggleSort(k)} title={title || `Sort by ${label}`}
      className={`pb-3 pr-4 cursor-pointer select-none whitespace-nowrap hover:text-gray-300 ${sortKey === k ? 'text-gray-300' : ''}`}>
      {label}{arrow(k)}
    </th>
  );

  const trendCell = (sig: Signal) => sig.TrendStatus ? (
    <span className={`text-xs font-bold ${
      sig.TrendStatus === 'UPTREND' ? 'text-green-400' : sig.TrendStatus === 'NEAR_SMA' ? 'text-yellow-400' : 'text-red-400'
    }`} title={`${sig.TrendStatus} (vs 200 SMA ${sig.SMA200?.toFixed(2) ?? '-'})`}>
      {sig.TrendStatus === 'UPTREND' ? '⬆️' : sig.TrendStatus === 'NEAR_SMA' ? '↔️' : '⬇️'}
    </span>
  ) : <span className="text-gray-600">-</span>;

  const priceCell = (sig: Signal) => (
    <div className="flex items-center gap-1.5">
      <span>{sig.Price}</span>
      <button onClick={() => onPriceInfoClick(sig)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors shrink-0"
        title="View last 20 days OHLC">
        <Info className="w-3.5 h-3.5 text-gray-500 hover:text-emerald-400" />
      </button>
    </div>
  );

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-sky-800/50">
      {/* ---- LIST SWITCH: Breakouts (momentum) | Reversals (mean-reversion) ---- */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setList('REVERSAL')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-bold text-sm transition-colors border ${
              list === 'REVERSAL' ? 'bg-amber-900/40 text-amber-200 border-amber-600' : 'bg-gray-900/40 text-gray-400 border-gray-700 hover:text-gray-200'}`}
            title="Mean-reversion — buy a confirmed bottom with room to run. The strongest measured edge: +5.1%/trade net of commission, 65% win.">
            <TrendingDown className="w-4 h-4" /> Reversals
            <span className={`text-xs rounded-full px-2 py-0.5 font-bold ${list === 'REVERSAL' ? 'bg-amber-800 text-amber-100' : 'bg-gray-800 text-gray-400'}`}>{reversals.length}</span>
          </button>
          <button onClick={() => setList('BREAKOUT')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-bold text-sm transition-colors border ${
              list === 'BREAKOUT' ? 'bg-sky-900/40 text-sky-200 border-sky-600' : 'bg-gray-900/40 text-gray-400 border-gray-700 hover:text-gray-200'}`}
            title="Momentum watchlist — nets only ~+0.3%/trade after commission. Watch, don't chase.">
            <Rocket className="w-4 h-4" /> Breakouts
            <span className={`text-xs rounded-full px-2 py-0.5 font-bold ${list === 'BREAKOUT' ? 'bg-sky-800 text-sky-100' : 'bg-gray-800 text-gray-400'}`}>{breakouts.length}</span>
          </button>
          <button onClick={() => setList('OVERHEATED')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-bold text-sm transition-colors border ${
              list === 'OVERHEATED' ? 'bg-red-900/40 text-red-200 border-red-600' : 'bg-gray-900/40 text-gray-400 border-gray-700 hover:text-gray-200'}`}
            title="Overheated — run too hot, elevated pullback risk. Avoid buying / take profit if you hold.">
            <Flame className="w-4 h-4" /> Overheated
            <span className={`text-xs rounded-full px-2 py-0.5 font-bold ${list === 'OVERHEATED' ? 'bg-red-800 text-red-100' : 'bg-gray-800 text-gray-400'}`}>{overheated.length}</span>
          </button>
          <button onClick={() => setList('MOVERS')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-bold text-sm transition-colors border ${
              list === 'MOVERS' ? 'bg-purple-900/40 text-purple-200 border-purple-600' : 'bg-gray-900/40 text-gray-400 border-gray-700 hover:text-gray-200'}`}
            title="Cheap movers — low-price stocks on short-term momentum, for a 1-2 week trade">
            <Flame className="w-4 h-4" /> Cheap Movers
            <span className={`text-xs rounded-full px-2 py-0.5 font-bold ${list === 'MOVERS' ? 'bg-purple-800 text-purple-100' : 'bg-gray-800 text-gray-400'}`}>{movers.length}</span>
          </button>
          <button onClick={() => setShowLegend((x) => !x)} className="text-gray-500 hover:text-gray-200" title="What is this?">
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>
        <input
          value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search ticker…"
          className="bg-gray-950 border border-gray-700 rounded px-2.5 py-1 text-xs text-white w-40 focus:outline-none focus:border-sky-500 placeholder-gray-600"
        />
      </div>

      {list === 'BREAKOUT' && (
        <p className="text-xs text-gray-500 mb-3">
          <b className="text-amber-300">⚠ Watchlist, not a buy list.</b> Net of the 0.8% round-trip commission this signal
          historically earns only <b className="text-amber-300">~+0.3%/trade (41% win)</b> — ৳33 on a ৳10,000 position — and buys at the
          20-day high by construction. Edge improves when market breadth ≥ 55% (+0.9% net). Ranked by quality grade (A–D);
          even Grade A nets just ~+0.7%. The Reversals list is where the real edge is.
        </p>
      )}
      {list === 'REVERSAL' && (
        <p className="text-xs text-gray-500 mb-3">
          Mean-reversion signal — buy a <b className="text-gray-400">confirmed bottom</b> (deeply oversold, first green day, room to run).
          The strongest measured edge: <b className="text-amber-300/80">+5.1%/trade net of commission, 65% win</b> (+10d, n=525, 2019–26);
          DEEP VALUE subset +6.4% net, 68%. Grade A won ~82% gross in the study vs ~58% for D.
        </p>
      )}
      {list === 'OVERHEATED' && (
        <p className="text-xs text-gray-500 mb-3">
          🔥 <b className="text-red-300">Take-profit / avoid</b> warning — stocks that have run too hot.
          Historically these pull back ≥20% about <b className="text-red-300">26%</b> of the time (vs ~15% normally) — <b>elevated risk, not a certainty</b>.
          <b className="text-gray-400"> NOT a buy list</b>: don&apos;t chase; consider taking profit if you hold one. Ranked hottest-first.
        </p>
      )}
      {list === 'MOVERS' && (
        <p className="text-xs text-gray-500 mb-3">
          ⚡ <b className="text-purple-300">Cheap stocks (&lt; 100 tk) moving now</b> — near a 20-day high, in an uptrend, on volume. For a quick
          <b> 1–2 week trade</b>. Backtest: ~<b className="text-purple-300">1 in 3 pops +7%</b> within 10 days — <b>but ~1 in 8 crashes −10%</b>.
          <b className="text-red-300"> High risk</b>: always set a −7% stop, take profit fast, and trade a *basket*, never one name.
        </p>
      )}

      {showLegend && list === 'BREAKOUT' && (
        <div className="mb-3 bg-gray-900 border border-sky-800/50 rounded p-3 text-xs text-gray-300 space-y-1.5">
          <div><span className="text-sky-300 font-bold">🚀 BREAKOUT</span> fires only when a stock (1) breaks its 20-day high, (2) isn&apos;t already extended (&lt;12%/20d), (3) trades above its 200-day average, (4) has real volume (RVOL ≥ 1.5×), and (5) is liquid.</div>
          <div className="text-amber-300/80">⚠ Honest numbers (2019–2026, net of 0.8% commission): <b>+0.33%/trade, 41% win</b>, negative in 4 of 8 years. It beat the raw market average gross, but the edge is too thin to survive costs — DSE rarely rewards buying strength. Treat as a watchlist; buying the same names later as <b>Reversals</b> paid ~15× more per trade.</div>
          <div className="text-gray-500">It&apos;s normal to see <b>0</b> on quiet days — that just means nothing is breaking out. Don&apos;t force a trade.</div>
        </div>
      )}
      {showLegend && list === 'REVERSAL' && (
        <div className="mb-3 bg-gray-900 border border-amber-800/50 rounded p-3 text-xs text-gray-300 space-y-1.5">
          <div><span className="text-amber-300 font-bold">📉 REVERSAL</span> fires when a stock is (1) deeply oversold (RSI &lt; 30), (2) prints its first green day (the turn), (3) on real volume (RVOL ≥ 1.5×), (4) sits ≥ 15% below its 120-day high (room to run), and (5) is liquid. The buy-low edge in a mean-reverting market.</div>
          <div className="text-amber-300/70">⚠️ Edge case: in a sustained market downtrend, oversold can get more oversold (2023 &amp; 2025 backtest were weak). Exit plan: <b>−10% stop</b> (wider than breakouts — the entry is a falling knife by design), +25% target, or time out after ~20 trading days; don&apos;t average down.</div>
          <div className="text-gray-500">Empty on calm days — reversals cluster around selloffs.</div>
        </div>
      )}
      {showLegend && list === 'OVERHEATED' && (
        <div className="mb-3 bg-gray-900 border border-red-800/50 rounded p-3 text-xs text-gray-300 space-y-1.5">
          <div><span className="text-red-300 font-bold">🔥 OVERHEATED</span> flags a stock that has run too far, too fast: overbought (RSI ≥ 75), and/or parabolic (+50% in 20 days), and/or stretched (≥ 25% above its 20-day average), often on climax volume. Reverse-engineered from how DSE tops form (see docs/WINNER_ANATOMY.md).</div>
          <div className="text-red-300/80">This is a <b>RISK flag, not a sell-now command</b> — strong stocks can stay hot a while. Use it to avoid buying tops and to take profit on names you hold. The chart predicts falls far better than rises.</div>
        </div>
      )}
      {showLegend && list === 'MOVERS' && (
        <div className="mb-3 bg-gray-900 border border-purple-800/50 rounded p-3 text-xs text-gray-300 space-y-1.5">
          <div><span className="text-purple-300 font-bold">⚡ CHEAP MOVERS</span> = a low-price (&lt;100tk) stock at/near its 20-day high, above its 20 &amp; 200-day averages, on real volume (RVOL ≥ 1.5×), not already blown off (RSI &lt; 80). It&apos;s <b>moving right now</b> — for a short 1–2 week trade, then sell.</div>
          <div className="text-red-300/80">⚠️ This is the <b>highest-variance</b> list — cheap momentum is where both the fast gains and the pump-and-dumps live. It only makes money <b>with discipline</b>: −7% stop, take profit at +7–10%, spread across several names. Never go all-in on one.</div>
        </div>
      )}

      {/* ---- BREAKOUT TABLE (momentum) ---- */}
      {list === 'BREAKOUT' && (
      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[640px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-3" title="Quality grade A–D, driven mainly by market breadth (the only factor with real predictive weight). Net of commission even Grade A earns only ~+0.7%/trade (48% win) vs ~0% for D.">GRADE</th>
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">PRICE</th>
              <th className="pb-3 pr-4">TREND</th>
              <th className="pb-3 pr-4">RVOL</th>
              <th className="pb-3 pr-4">WHY IT FIRED</th>
              <th className="pb-3 text-center">DETAIL</th>
            </tr>
          </thead>
          <tbody>
            {fb.map(({ s: sig, g }, i) => (
              <tr key={`${sig.Ticker}-${i}`} className="border-b border-gray-700/50 hover:bg-sky-900/10 transition h-11">
                <td className="py-2 pr-3">
                  <span className={`inline-flex items-center justify-center w-7 h-6 rounded font-bold text-sm ${gradeColor(g.grade)}`}
                    title={`Quality ${g.score}/100 — ${g.factors.map((f) => `${f.label}: ${f.value}`).join('; ')}`}>
                    {g.grade}
                  </span>
                </td>
                <td className="py-2 pr-4 font-bold text-sky-300 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span>{sig.Ticker}</span>
                    {marketHealthy && (
                      <span className="text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded font-bold" title="PRIME — fired in a healthy market (more breakouts work here)">PRIME</span>
                    )}
                    {!!sig.IsFreshBreakout && (
                      <span className="text-[9px] bg-sky-600 text-white px-1 py-0.5 rounded font-bold" title="First day this breakout fired">FRESH</span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">{priceCell(sig)}</td>
                <td className="py-2 pr-4 whitespace-nowrap">{trendCell(sig)}</td>
                <td className="py-2 pr-4 font-bold text-yellow-400 whitespace-nowrap">{sig.RVOL}×</td>
                <td className="py-2 pr-4 text-gray-300 text-xs">{breakoutWhy(sig)}</td>
                <td className="py-2 text-center">
                  <button onClick={() => onBreakoutInfoClick(sig)}
                    className="inline-flex items-center justify-center w-7 h-7 rounded border border-sky-700 bg-sky-900/20 text-sky-300 hover:border-sky-400 hover:bg-sky-900/40 transition-colors"
                    title="Why this fired — exact calculation">
                    <Info className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {fb.length === 0 && (
              <tr><td colSpan={7} className="py-8 text-center text-gray-500">
                {loading ? 'Loading…' : (
                  <>No breakouts right now — nothing is breaking out today.<br />
                  <span className="text-gray-600 text-xs">That&apos;s normal on quiet days. Use the Time Machine above to study past breakouts.</span></>
                )}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {/* ---- REVERSAL TABLE (mean-reversion / buy-the-bottom) ---- */}
      {list === 'REVERSAL' && (
      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[640px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-3" title="Reversal quality grade A–D. Higher = historically better odds (A ~82% win vs D ~58%). From oversold depth + distance below 50-SMA + capitulation + turn volume.">GRADE</th>
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">PRICE</th>
              <th className="pb-3 pr-4">RSI</th>
              <th className="pb-3 pr-4">RVOL</th>
              <th className="pb-3 pr-4">WHY IT FIRED</th>
              <th className="pb-3 text-center">DETAIL</th>
            </tr>
          </thead>
          <tbody>
            {fr.map(({ s: sig, g }, i) => (
              <tr key={`${sig.Ticker}-${i}`} className="border-b border-gray-700/50 hover:bg-amber-900/10 transition h-11">
                <td className="py-2 pr-3">
                  <span className={`inline-flex items-center justify-center w-7 h-6 rounded font-bold text-sm ${gradeColor(g.grade)}`}
                    title={`Quality ${g.score}/100 — ${g.factors.map((f) => `${f.label}: ${f.value}`).join('; ')}`}>
                    {g.grade}
                  </span>
                </td>
                <td className="py-2 pr-4 font-bold text-amber-200 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span>{sig.Ticker}</span>
                    {sig.ReversalChecks?.deep_value && (
                      <span className="text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded font-bold"
                        title="DEEP VALUE — near its 1-year low with big room to its lifetime high. Historically wins ~70% vs ~63% for a regular reversal.">DEEP VALUE</span>
                    )}
                    {(qualityMap?.[sig.Ticker] ?? 0) >= 4 && (
                      <span className="text-[9px] bg-teal-700 text-teal-100 px-1 py-0.5 rounded font-bold"
                        title={`Fundamental quality ${qualityMap![sig.Ticker]}/6 on the Graham screen — a falling knife with sound fundamentals (the Lynch setup: quality on sale)`}>
                        Q{qualityMap![sig.Ticker]}/6
                      </span>
                    )}
                    {!!sig.IsFreshReversal && (
                      <span className="text-[9px] bg-amber-600 text-white px-1 py-0.5 rounded font-bold" title="First day this reversal fired">FRESH</span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">{priceCell(sig)}</td>
                <td className="py-2 pr-4 font-bold text-emerald-400 whitespace-nowrap"
                  title="Wilder RSI(14) — below 30 = deeply oversold">
                  {typeof sig.ReversalChecks?.rsi === 'number' ? Math.round(sig.ReversalChecks.rsi) : '-'}
                </td>
                <td className="py-2 pr-4 font-bold text-yellow-400 whitespace-nowrap">{sig.RVOL}×</td>
                <td className="py-2 pr-4 text-gray-300 text-xs">{reversalWhy(sig)}</td>
                <td className="py-2 text-center">
                  <button onClick={() => onReversalInfoClick(sig)}
                    className="inline-flex items-center justify-center w-7 h-7 rounded border border-amber-700 bg-amber-900/20 text-amber-300 hover:border-amber-400 hover:bg-amber-900/40 transition-colors"
                    title="Why this fired — the 5 reversal rules + grade">
                    <Info className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {fr.length === 0 && (
              <tr><td colSpan={7} className="py-8 text-center text-gray-500">
                {loading ? 'Loading…' : (
                  <>No reversals right now — nothing has bottomed-and-turned today.<br />
                  <span className="text-gray-600 text-xs">Reversals cluster around selloffs. Use the Time Machine above to study past ones.</span></>
                )}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {/* ---- OVERHEATED TABLE (take-profit / avoid warning) ---- */}
      {list === 'OVERHEATED' && (
      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[680px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-3" title="Heat = how dangerously extended (0–100). EXTREME ≥ 65, HOT ≥ 40.">HEAT</th>
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">PRICE</th>
              <th className="pb-3 pr-4" title="RSI — overbought above 70">RSI</th>
              <th className="pb-3 pr-4" title="Run-up over the last 20 trading days">RUN-UP 20d</th>
              <th className="pb-3 pr-4" title="How far above its 20-day average">vs 20-SMA</th>
              <th className="pb-3 pr-4">WHY IT'S HOT</th>
              <th className="pb-3 text-center">DETAIL</th>
            </tr>
          </thead>
          <tbody>
            {fo.map((sig, i) => {
              const c = sig.OverheatedChecks || {};
              return (
              <tr key={`${sig.Ticker}-${i}`} className="border-b border-gray-700/50 hover:bg-red-900/10 transition h-11">
                <td className="py-2 pr-3">
                  <span className={`inline-flex items-center justify-center px-2 h-6 rounded font-bold text-[11px] ${heatColor(c.heat_level)}`}
                    title={`Heat ${c.heat_score ?? '?'}/100 — ${c.heat_level ?? ''}`}>
                    {c.heat_level ?? '—'}
                  </span>
                </td>
                <td className="py-2 pr-4 font-bold text-red-200 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span>{sig.Ticker}</span>
                    {!!sig.IsFreshOverheated && (
                      <span className="text-[9px] bg-red-600 text-white px-1 py-0.5 rounded font-bold" title="First day it turned overheated">NEW</span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">{priceCell(sig)}</td>
                <td className="py-2 pr-4 font-bold text-orange-300 whitespace-nowrap">{typeof c.rsi === 'number' ? Math.round(c.rsi) : '-'}</td>
                <td className="py-2 pr-4 font-bold text-red-300 whitespace-nowrap">{typeof c.ret20 === 'number' ? `+${Math.round(c.ret20)}%` : '-'}</td>
                <td className="py-2 pr-4 text-red-300 whitespace-nowrap">{typeof c.ext20 === 'number' ? `+${Math.round(c.ext20)}%` : '-'}</td>
                <td className="py-2 pr-4 text-gray-300 text-xs">{overheatedWhy(sig)}</td>
                <td className="py-2 text-center">
                  <button onClick={() => onOverheatedInfoClick(sig)}
                    className="inline-flex items-center justify-center w-7 h-7 rounded border border-red-700 bg-red-900/20 text-red-300 hover:border-red-400 hover:bg-red-900/40 transition-colors"
                    title="Why it's flagged hot — the breakdown">
                    <Info className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            );})}
            {fo.length === 0 && (
              <tr><td colSpan={8} className="py-8 text-center text-gray-500">
                {loading ? 'Loading…' : (
                  <>Nothing overheated right now — no stock has run dangerously hot today.<br />
                  <span className="text-gray-600 text-xs">Good — fewer tops to avoid. This fills up in frothy/euphoric markets.</span></>
                )}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {/* ---- CHEAP MOVERS TABLE (short-term momentum, price < 100) ---- */}
      {list === 'MOVERS' && (
      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[680px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-3" title="Momentum strength 0–100 (volume + 5-day thrust + closeness to the 20-day high)">MO</th>
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">PRICE</th>
              <th className="pb-3 pr-4" title="Up over the last 5 trading days">5d</th>
              <th className="pb-3 pr-4">RVOL</th>
              <th className="pb-3 pr-4">WHY IT'S MOVING</th>
              <th className="pb-3 text-center">DETAIL</th>
            </tr>
          </thead>
          <tbody>
            {fm.map((sig, i) => {
              const c = sig.MomentumChecks || {};
              const mo = c.mo_score ?? 0;
              return (
              <tr key={`${sig.Ticker}-${i}`} className="border-b border-gray-700/50 hover:bg-purple-900/10 transition h-11">
                <td className="py-2 pr-3">
                  <span className={`inline-flex items-center justify-center w-8 h-6 rounded font-bold text-xs ${mo >= 60 ? 'bg-purple-600 text-white' : mo >= 35 ? 'bg-purple-800 text-purple-100' : 'bg-gray-700 text-gray-300'}`}
                    title={`Momentum ${mo}/100`}>{mo}</span>
                </td>
                <td className="py-2 pr-4 font-bold text-purple-200 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span>{sig.Ticker}</span>
                    {!!sig.IsFreshMomentum && (
                      <span className="text-[9px] bg-purple-600 text-white px-1 py-0.5 rounded font-bold" title="First day it started moving">NEW</span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">{priceCell(sig)}</td>
                <td className={`py-2 pr-4 font-bold whitespace-nowrap ${(c.ret5 || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {typeof c.ret5 === 'number' ? `${c.ret5 > 0 ? '+' : ''}${Math.round(c.ret5)}%` : '-'}
                </td>
                <td className="py-2 pr-4 font-bold text-yellow-400 whitespace-nowrap">{sig.RVOL}×</td>
                <td className="py-2 pr-4 text-gray-300 text-xs">{momentumWhy(sig)}</td>
                <td className="py-2 text-center">
                  <button onClick={() => onInfoClick(sig)}
                    className="inline-flex items-center justify-center w-7 h-7 rounded border border-purple-700 bg-purple-900/20 text-purple-300 hover:border-purple-400 hover:bg-purple-900/40 transition-colors"
                    title="Details">
                    <Info className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            );})}
            {fm.length === 0 && (
              <tr><td colSpan={7} className="py-8 text-center text-gray-500">
                {loading ? 'Loading…' : (
                  <>No cheap movers right now — no low-price stock is on strong momentum today.<br />
                  <span className="text-gray-600 text-xs">Fills up when cheap stocks start running. Use the Time Machine to study past ones.</span></>
                )}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {/* ---- LEGACY (collapsed by default) ---- */}
      <div className="mt-4 border-t border-gray-700/60 pt-3">
        <button onClick={() => setLegacy((x) => !x)}
          className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1">
          {legacy ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          {legacy ? 'Hide' : 'Show'} legacy signals (Score / Early / Buy — low reliability)
        </button>

        {legacy && (
          <div className="mt-3">
            <div className="mb-2 text-[11px] text-red-300/80 bg-red-900/10 border border-red-800/40 rounded px-2 py-1">
              🚫 Do NOT trade these. Backtest: <b>−1.2%/trade, 20% win</b> — the score is inversely related to forward returns.
              Shown for reference only; the Reversals list above is the one with a real edge.
            </div>
            <div className="flex gap-1 text-xs flex-wrap mb-3">
              <button onClick={() => setTab('ALL')} className={`px-3 py-1 rounded ${tab === 'ALL' ? 'bg-emerald-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>ALL ({signals.length})</button>
              <button onClick={() => setTab('EARLY')} className={`px-3 py-1 rounded flex items-center gap-1 ${tab === 'EARLY' ? 'bg-orange-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}><Flame className="w-3 h-3" /> EARLY ({countEarly})</button>
              <button onClick={() => setTab('BUY')} className={`px-3 py-1 rounded ${tab === 'BUY' ? 'bg-green-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>BUY ({countBuy})</button>
              <button onClick={() => setTab('FRESH')} className={`px-3 py-1 rounded flex items-center gap-1 ${tab === 'FRESH' ? 'bg-yellow-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}><Sparkles className="w-3 h-3" /> FRESH ({countFresh})</button>
            </div>

            <div className="overflow-x-auto">
              <table className="text-left text-sm table-fixed min-w-[930px] w-full">
                <colgroup>
                  <col style={{ width: '120px' }} /><col style={{ width: '90px' }} /><col style={{ width: '60px' }} />
                  <col style={{ width: '130px' }} /><col style={{ width: '110px' }} /><col style={{ width: '110px' }} />
                  <col style={{ width: '70px' }} /><col style={{ width: '100px' }} /><col style={{ width: '80px' }} /><col style={{ width: '60px' }} />
                </colgroup>
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-700">
                    {sortableHeader('Ticker', 'TICKER')}
                    {sortableHeader('Price', 'PRICE')}
                    <th className="pb-3 pr-4 whitespace-nowrap">TREND</th>
                    <th className="pb-3 pr-4 whitespace-nowrap">LAST CLOSING VOL</th>
                    <th className="pb-3 pr-4 whitespace-nowrap">CURRENT VOL</th>
                    <th className="pb-3 pr-4 whitespace-nowrap">PROJECTED VOL</th>
                    {sortableHeader('RVOL', 'RVOL')}
                    {sortableHeader('EarlyScore', 'EARLY', 'Pre-breakout score 0–100')}
                    {sortableHeader('Score', 'SCORE', 'Main confirmation score 0–100')}
                    <th className="pb-3 whitespace-nowrap text-center">INFO</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((sig, i) => (
                    <tr key={`${sig.Ticker}-${i}`} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition h-10">
                      <td className="py-2 pr-4 font-bold text-green-400 whitespace-nowrap overflow-hidden">
                        <span className="truncate">{sig.Ticker}</span>
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">{priceCell(sig)}</td>
                      <td className="py-2 pr-4 whitespace-nowrap">{trendCell(sig)}</td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        <button onClick={() => onVolumeClick(sig)} className="flex items-center gap-1 hover:text-cyan-400 transition">
                          <span className="text-white">{(sig.LastClosingVol || sig.Volume || 0).toLocaleString()}</span>
                          <AlertCircle className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        </button>
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        <span className={`${sig.IsMarketOpen ? 'text-green-400' : 'text-white'}`}>{(sig.CurrentVol || 0).toLocaleString()}</span>
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        {sig.IsMarketOpen && sig.ProjectedVol ? <span className="text-yellow-400">{sig.ProjectedVol.toLocaleString()}</span> : <span className="text-gray-600">-</span>}
                      </td>
                      <td className="py-2 pr-4 font-bold text-yellow-400 whitespace-nowrap">{sig.RVOL}x</td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        {typeof sig.EarlyScore === 'number' ? (
                          <span title={`EarlyScore ${sig.EarlyScore}/100 — ${sig.EarlySignal}`}
                            className={`px-2 py-0.5 rounded text-xs font-bold ${sig.EarlySignal === 'EARLY' ? 'bg-orange-700 text-white' : sig.EarlySignal === 'WATCH' ? 'bg-amber-900 text-amber-200' : 'bg-gray-700 text-gray-500'}`}>
                            {sig.EarlyScore}<span className="ml-1 text-[10px]">{sig.EarlySignal}</span>
                          </span>
                        ) : <span className="text-gray-600">-</span>}
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        <span title={`Score ${sig.Score}/100 — ${sig.Signal}`}
                          className={`px-2 py-0.5 rounded text-xs font-bold ${sig.Score >= 50 ? 'bg-green-900 text-green-300' : sig.Score >= 28 ? 'bg-yellow-900 text-yellow-300' : 'bg-gray-700 text-gray-300'}`}>
                          {sig.Score}
                        </span>
                      </td>
                      <td className="py-2 pr-2 text-center">
                        <button onClick={() => onInfoClick(sig)}
                          className={`inline-flex items-center justify-center w-7 h-7 rounded border transition-colors ${activeTicker === sig.Ticker ? 'border-green-500 bg-green-900/30 text-green-300' : 'border-gray-600 bg-gray-800 text-emerald-400 hover:border-emerald-400 hover:bg-emerald-900/20'}`}
                          title={reasonsToString(sig.Reason) ? `Full breakdown — ${reasonsToString(sig.Reason)}` : 'Open full breakdown'}>
                          <Info className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {sorted.length === 0 && (
                    <tr><td colSpan={10} className="py-6 text-center text-gray-600">
                      {loading ? 'Loading signals...' : 'No signals in this view.'}
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
