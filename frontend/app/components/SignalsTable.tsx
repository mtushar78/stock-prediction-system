import { Signal } from '../types';
import { AlertCircle, Info, Flame, Sparkles, HelpCircle } from 'lucide-react';
import { useState } from 'react';

interface SignalsTableProps {
  signals: Signal[];
  loading: boolean;
  onVolumeClick: (signal: Signal) => void;
  onInfoClick: (signal: Signal) => void;
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

export default function SignalsTable({
  signals,
  loading,
  onVolumeClick,
  onInfoClick,
  onPriceInfoClick,
  activeTicker,
}: SignalsTableProps) {
  const [tab, setTab] = useState<ViewTab>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('Score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showLegend, setShowLegend] = useState(false);

  // Filter by tab
  const filtered = signals.filter((s) => {
    if (tab === 'EARLY') return s.EarlySignal === 'EARLY' || s.EarlySignal === 'WATCH';
    if (tab === 'BUY') return s.Signal === 'BUY';
    if (tab === 'FRESH') return s.IsFreshBuy || s.IsFreshEarly;
    return true;
  });

  // Sort
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
    <th
      onClick={() => toggleSort(k)}
      title={title || `Sort by ${label}`}
      className={`pb-3 pr-4 cursor-pointer select-none whitespace-nowrap hover:text-gray-300 ${sortKey === k ? 'text-gray-300' : ''}`}
    >
      {label}{arrow(k)}
    </th>
  );

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-green-300">🔭 Sniper Scope</h2>
          <span className="text-[10px] text-gray-500 border border-gray-700 rounded px-1.5 py-0.5">v7</span>
          <button
            onClick={() => setShowLegend((x) => !x)}
            className="text-gray-500 hover:text-gray-200 ml-1"
            title="Show legend"
          ><HelpCircle className="w-4 h-4" /></button>
        </div>
        <div className="flex gap-1 text-xs flex-wrap">
          <button
            onClick={() => setTab('ALL')}
            className={`px-3 py-1 rounded ${tab === 'ALL' ? 'bg-emerald-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >ALL ({signals.length})</button>
          <button
            onClick={() => setTab('EARLY')}
            className={`px-3 py-1 rounded flex items-center gap-1 ${tab === 'EARLY' ? 'bg-orange-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
            title="Pre-breakout setups: tight base + first volume tell + not extended. Best entry window."
          ><Flame className="w-3 h-3" /> EARLY ({countEarly})</button>
          <button
            onClick={() => setTab('BUY')}
            className={`px-3 py-1 rounded ${tab === 'BUY' ? 'bg-green-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
            title="Main score ≥ 50 — multi-factor confirmation"
          >BUY ({countBuy})</button>
          <button
            onClick={() => setTab('FRESH')}
            className={`px-3 py-1 rounded flex items-center gap-1 ${tab === 'FRESH' ? 'bg-yellow-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
            title="Day-1 signals — yesterday was NOT BUY/EARLY. These are the freshest opportunities."
          ><Sparkles className="w-3 h-3" /> FRESH ({countFresh})</button>
        </div>
      </div>

      {showLegend && (
        <div className="mb-3 bg-gray-900 border border-gray-700 rounded p-3 text-xs text-gray-300 space-y-2">
          <div><span className="text-green-400 font-bold">SCORE</span> — main multi-factor score (0–100). ≥ 50 = <b className="text-green-300">BUY</b>, ≥ 28 = <b className="text-yellow-300">WAIT</b>, &lt; 28 = IGNORE. Late-entry penalty automatically reduces this for stocks that already moved.</div>
          <div><span className="text-orange-400 font-bold">EARLY</span> — pre-breakout score (0–100). ≥ 60 = <b className="text-orange-300">EARLY</b> (act now), ≥ 40 = <b className="text-amber-200">WATCH</b> (setting up). Built from <i>tight base + volume tell + closing tell + near 10d high + not extended</i>.</div>
          <div><span className="text-yellow-300 font-bold">FRESH</span> badge — first day this signal fired (yesterday was not BUY/EARLY). Fresh signals are the highest-quality entries.</div>
          <div className="text-gray-500">Click any column header to sort. Click <Info className="inline w-3 h-3" /> in the REASON column for the full breakdown.</div>
        </div>
      )}

      <div className="overflow-x-auto">
        {/* min-w on the table forces horizontal scroll on small screens instead
            of letting columns collapse — important for mobile where REASON
            could otherwise lose its width entirely under table-fixed. */}
        <table className="text-left text-sm table-fixed min-w-[1180px] w-full">
          <colgroup>
            <col style={{ width: '120px' }} />  {/* TICKER */}
            <col style={{ width: '90px' }} />   {/* PRICE */}
            <col style={{ width: '60px' }} />   {/* TREND */}
            <col style={{ width: '130px' }} />  {/* LAST CLOSING VOL */}
            <col style={{ width: '110px' }} />  {/* CURRENT VOL */}
            <col style={{ width: '110px' }} />  {/* PROJECTED VOL */}
            <col style={{ width: '70px' }} />   {/* RVOL */}
            <col style={{ width: '100px' }} />  {/* EARLY */}
            <col style={{ width: '80px' }} />   {/* SCORE */}
            <col style={{ width: '310px' }} />  {/* REASON — explicit width so cell + icon are always visible */}
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
              {sortableHeader('EarlyScore', 'EARLY', 'Pre-breakout score 0–100. ≥60=EARLY, ≥40=WATCH')}
              {sortableHeader('Score', 'SCORE', 'Main confirmation score 0–100. ≥50=BUY, ≥28=WAIT')}
              <th className="pb-3 whitespace-nowrap">REASON</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((sig, i) => {
              const reasonText = reasonsToString(sig.Reason);
              return (
              <tr
                key={`${sig.Ticker}-${i}`}
                className={`border-b border-gray-700/50 hover:bg-gray-700/30 transition h-10 ${
                  sig.IsFreshEarly ? 'bg-orange-900/10' : sig.IsFreshBuy ? 'bg-green-900/10' : ''
                }`}
              >
                <td className="py-2 pr-4 font-bold text-green-400 whitespace-nowrap overflow-hidden">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate">{sig.Ticker}</span>
                    {/* !! coerces (so an int 0 from the API never renders as text "0") */}
                    {!!sig.IsFreshEarly && (
                      <span title="FRESH — first day this EARLY signal fired (yesterday was not EARLY). Highest quality entry."
                            className="text-[9px] bg-orange-600 text-white px-1 py-0.5 rounded font-bold shrink-0">
                        FRESH
                      </span>
                    )}
                    {!!sig.IsFreshBuy && !sig.IsFreshEarly && (
                      <span title="FRESH — first day this BUY signal fired (yesterday was below BUY threshold)."
                            className="text-[9px] bg-green-600 text-white px-1 py-0.5 rounded font-bold shrink-0">
                        FRESH
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span>{sig.Price}</span>
                    <button
                      onClick={() => onPriceInfoClick(sig)}
                      className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors shrink-0"
                      title="View last 20 days OHLC"
                    >
                      <Info className="w-3.5 h-3.5 text-gray-500 hover:text-emerald-400" />
                    </button>
                  </div>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {sig.TrendStatus ? (
                    <span className={`text-xs font-bold ${
                      sig.TrendStatus === 'UPTREND' ? 'text-green-400' :
                      sig.TrendStatus === 'NEAR_SMA' ? 'text-yellow-400' : 'text-red-400'
                    }`}
                    title={`${sig.TrendStatus} (vs 200 SMA ${sig.SMA200?.toFixed(2) ?? '-'})`}>
                      {sig.TrendStatus === 'UPTREND' ? '⬆️' : sig.TrendStatus === 'NEAR_SMA' ? '↔️' : '⬇️'}
                    </span>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <button onClick={() => onVolumeClick(sig)} className="flex items-center gap-1 hover:text-cyan-400 transition">
                    <span className="text-white">{(sig.LastClosingVol || sig.Volume || 0).toLocaleString()}</span>
                    <AlertCircle className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  </button>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span className={`${sig.IsMarketOpen ? 'text-green-400' : 'text-white'}`}>
                    {(sig.CurrentVol || 0).toLocaleString()}
                  </span>
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {sig.IsMarketOpen && sig.ProjectedVol ? (
                    <span className="text-yellow-400">{sig.ProjectedVol.toLocaleString()}</span>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
                <td className="py-2 pr-4 font-bold text-yellow-400 whitespace-nowrap">{sig.RVOL}x</td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  {typeof sig.EarlyScore === 'number' ? (
                    <span
                      title={`EarlyScore ${sig.EarlyScore}/100 — ${sig.EarlySignal}. ${
                        Array.isArray(sig.EarlyReasons) ? sig.EarlyReasons.join(', ') : ''
                      }`}
                      className={`px-2 py-0.5 rounded text-xs font-bold ${
                        sig.EarlySignal === 'EARLY' ? 'bg-orange-700 text-white' :
                        sig.EarlySignal === 'WATCH' ? 'bg-amber-900 text-amber-200' :
                        'bg-gray-700 text-gray-500'
                      }`}>
                      {sig.EarlyScore}
                      <span className="ml-1 text-[10px]">{sig.EarlySignal}</span>
                    </span>
                  ) : <span className="text-gray-600">-</span>}
                </td>
                <td className="py-2 pr-4 whitespace-nowrap">
                  <span
                    title={`Score ${sig.Score}/100 — ${sig.Signal}`}
                    className={`px-2 py-0.5 rounded text-xs font-bold ${
                      sig.Score >= 50 ? 'bg-green-900 text-green-300' :
                      sig.Score >= 28 ? 'bg-yellow-900 text-yellow-300' :
                      'bg-gray-700 text-gray-300'
                    }`}>
                    {sig.Score}
                  </span>
                </td>
                <td className="py-2 pr-2 text-xs text-gray-400 overflow-hidden">
                  <div className="flex items-center gap-2 min-w-0">
                    {/* Always-visible Info button so the user can open the
                        full breakdown even when the truncated reason text
                        is empty or the column is narrow. */}
                    <button
                      onClick={() => onInfoClick(sig)}
                      className={`shrink-0 inline-flex items-center justify-center w-6 h-6 rounded border transition-colors ${
                        activeTicker === sig.Ticker
                          ? 'border-green-500 bg-green-900/30 text-green-300'
                          : 'border-gray-600 bg-gray-800 text-emerald-400 hover:border-emerald-400 hover:bg-emerald-900/20'
                      }`}
                      title="Open full breakdown"
                      aria-label="Open full breakdown"
                    >
                      <Info className="w-3.5 h-3.5" />
                    </button>
                    <span
                      className="truncate flex-1 min-w-0"
                      title={reasonText}
                    >
                      {reasonText || <span className="text-gray-600 italic">no reasons fired</span>}
                    </span>
                  </div>
                </td>
              </tr>
            );})}
            {sorted.length === 0 && (
              <tr><td colSpan={10} className="py-6 text-center text-gray-600">
                {loading ? 'Loading signals...' :
                  tab === 'EARLY' ? 'No EARLY/WATCH setups right now.' :
                  tab === 'BUY'   ? 'No BUY signals today.' :
                  tab === 'FRESH' ? 'No fresh (day-1) signals today.' :
                                    'No signals today. Market is sleeping.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
