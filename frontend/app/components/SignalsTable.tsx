import { Signal } from '../types';
import { AlertCircle, Info, Flame, Sparkles, HelpCircle, Rocket, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { breakoutGrade, gradeColor } from './breakoutGrade';

interface SignalsTableProps {
  signals: Signal[];
  loading: boolean;
  marketHealthy?: boolean;
  marketBreadth?: number | null;
  onVolumeClick: (signal: Signal) => void;
  onInfoClick: (signal: Signal) => void;
  onBreakoutInfoClick: (signal: Signal) => void;
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

export default function SignalsTable({
  signals,
  loading,
  marketHealthy,
  marketBreadth,
  onVolumeClick,
  onInfoClick,
  onBreakoutInfoClick,
  onPriceInfoClick,
  activeTicker,
}: SignalsTableProps) {
  const [legacy, setLegacy] = useState(false);
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
      <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-sky-300 flex items-center gap-2"><Rocket className="w-5 h-5" /> Breakouts</h2>
          <span className="text-[10px] text-sky-300/80 border border-sky-800 rounded px-1.5 py-0.5">v9 · the list to trade</span>
          <span className="text-xs bg-sky-900/50 text-sky-200 border border-sky-700 rounded-full px-2 py-0.5 font-bold">{breakouts.length}</span>
          <button onClick={() => setShowLegend((x) => !x)} className="text-gray-500 hover:text-gray-200 ml-1" title="What is this?">
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        The only signal with a proven, regime-robust edge — ranked best-first by <b className="text-gray-400">quality grade (A–D)</b>.
        Grade A historically wins ~54% vs ~42% for D. Click <Info className="inline w-3 h-3" /> on any row for the grade breakdown + exact reason it fired.
      </p>

      {showLegend && (
        <div className="mb-3 bg-gray-900 border border-sky-800/50 rounded p-3 text-xs text-gray-300 space-y-1.5">
          <div><span className="text-sky-300 font-bold">🚀 BREAKOUT</span> fires only when a stock (1) breaks its 20-day high, (2) isn&apos;t already extended (&lt;12%/20d), (3) trades above its 200-day average, (4) has real volume (RVOL ≥ 1.5×), and (5) is liquid. In a 2019–2026 backtest it beat the market every year.</div>
          <div className="text-gray-500">It&apos;s normal to see <b>0</b> on quiet days — that just means nothing is breaking out. Don&apos;t force a trade.</div>
        </div>
      )}

      {/* ---- BREAKOUT TABLE (primary) ---- */}
      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[640px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-3" title="Quality grade A–D. Higher = historically better odds (A ~54% win vs D ~42%). From market regime + base tightness + low volatility + non-extreme volume.">GRADE</th>
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">PRICE</th>
              <th className="pb-3 pr-4">TREND</th>
              <th className="pb-3 pr-4">RVOL</th>
              <th className="pb-3 pr-4">WHY IT FIRED</th>
              <th className="pb-3 text-center">DETAIL</th>
            </tr>
          </thead>
          <tbody>
            {breakouts.map(({ s: sig, g }, i) => (
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
            {breakouts.length === 0 && (
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

      {/* ---- LEGACY (collapsed by default) ---- */}
      <div className="mt-4 border-t border-gray-700/60 pt-3">
        <button onClick={() => setLegacy((x) => !x)}
          className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1">
          {legacy ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          {legacy ? 'Hide' : 'Show'} legacy signals (Score / Early / Buy — low reliability)
        </button>

        {legacy && (
          <div className="mt-3">
            <div className="mb-2 text-[11px] text-amber-300/70 bg-amber-900/10 border border-amber-800/40 rounded px-2 py-1">
              ⚠️ These signals were inversely related to forward returns in backtest. Shown for reference only — trade the breakouts above.
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
