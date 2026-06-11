import { Signal } from '../types';
import { AlertCircle, Info, Flame, Eye } from 'lucide-react';
import { useState } from 'react';

interface SignalsTableProps {
  signals: Signal[];
  loading: boolean;
  onVolumeClick: (signal: Signal) => void;
  onInfoClick: (index: number) => void;
  onPriceInfoClick: (signal: Signal) => void;
  activeModalIndex: number | null;
}

type ViewTab = 'ALL' | 'EARLY' | 'BUY' | 'FRESH';

export default function SignalsTable({
  signals,
  loading,
  onVolumeClick,
  onInfoClick,
  onPriceInfoClick,
  activeModalIndex,
}: SignalsTableProps) {
  const [tab, setTab] = useState<ViewTab>('ALL');

  // v7: filter by tab
  const filtered = signals.filter((s) => {
    if (tab === 'EARLY') return s.EarlySignal === 'EARLY' || s.EarlySignal === 'WATCH';
    if (tab === 'BUY') return s.Signal === 'BUY';
    if (tab === 'FRESH') return s.IsFreshBuy || s.IsFreshEarly;
    return true;
  });

  // v7: sort by SignalStrength desc when available, else Score desc
  const sorted = [...filtered].sort((a, b) => {
    const av = a.SignalStrength ?? a.Score ?? 0;
    const bv = b.SignalStrength ?? b.Score ?? 0;
    return bv - av;
  });

  const countEarly = signals.filter((s) => s.EarlySignal === 'EARLY' || s.EarlySignal === 'WATCH').length;
  const countBuy = signals.filter((s) => s.Signal === 'BUY').length;
  const countFresh = signals.filter((s) => s.IsFreshBuy || s.IsFreshEarly).length;

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="text-xl font-bold text-green-300">🔭 Sniper Scope (v7)</h2>
        <div className="flex gap-1 text-xs">
          <button
            onClick={() => setTab('ALL')}
            className={`px-3 py-1 rounded ${tab === 'ALL' ? 'bg-emerald-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >ALL ({signals.length})</button>
          <button
            onClick={() => setTab('EARLY')}
            className={`px-3 py-1 rounded flex items-center gap-1 ${tab === 'EARLY' ? 'bg-orange-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
            title="Pre-breakout setups detected before the move"
          ><Flame className="w-3 h-3" /> EARLY ({countEarly})</button>
          <button
            onClick={() => setTab('BUY')}
            className={`px-3 py-1 rounded ${tab === 'BUY' ? 'bg-green-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
          >BUY ({countBuy})</button>
          <button
            onClick={() => setTab('FRESH')}
            className={`px-3 py-1 rounded flex items-center gap-1 ${tab === 'FRESH' ? 'bg-yellow-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
            title="Day-1 signals (yesterday was NOT BUY/EARLY)"
          ><Eye className="w-3 h-3" /> FRESH ({countFresh})</button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">PRICE</th>
              <th className="pb-3 pr-4">TREND</th>
              <th className="pb-3 pr-4">LAST CLOSING VOL</th>
              <th className="pb-3 pr-4">CURRENT VOL</th>
              <th className="pb-3 pr-4">PROJECTED VOL</th>
              <th className="pb-3 pr-4">RVOL</th>
              <th className="pb-3 pr-4">EARLY</th>
              <th className="pb-3 pr-4">SCORE</th>
              <th className="pb-3">REASON</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((sig, i) => (
              <tr key={i} className={`border-b border-gray-700/50 hover:bg-gray-700/30 transition ${
                sig.IsFreshEarly ? 'bg-orange-900/10' : sig.IsFreshBuy ? 'bg-green-900/10' : ''
              }`}>
                <td className="py-3 pr-4 font-bold text-green-400">
                  <div className="flex items-center gap-1">
                    <span>{sig.Ticker}</span>
                    {sig.IsFreshEarly && (
                      <span title="Fresh EARLY signal — first-day pre-breakout setup"
                            className="text-[10px] bg-orange-700 text-white px-1.5 py-0.5 rounded font-bold">
                        FRESH
                      </span>
                    )}
                    {sig.IsFreshBuy && !sig.IsFreshEarly && (
                      <span title="Fresh BUY signal — first day above BUY threshold"
                            className="text-[10px] bg-green-700 text-white px-1.5 py-0.5 rounded font-bold">
                        NEW
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <span>{sig.Price}</span>
                    <button
                      onClick={() => onPriceInfoClick(sig)}
                      className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors"
                      title="View last 20 days OHLC"
                    >
                      <Info className="w-3.5 h-3.5 text-gray-500 hover:text-emerald-400" />
                    </button>
                  </div>
                </td>
                <td className="py-3 pr-4">
                  {sig.TrendStatus ? (
                    <span className={`text-xs font-bold ${
                      sig.TrendStatus === 'UPTREND' ? 'text-green-400' :
                      sig.TrendStatus === 'NEAR_SMA' ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {sig.TrendStatus === 'UPTREND' ? '⬆️' : sig.TrendStatus === 'NEAR_SMA' ? '↔️' : '⬇️'}
                    </span>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
                <td className="py-3 pr-4">
                  <button onClick={() => onVolumeClick(sig)} className="flex items-center gap-1 hover:text-cyan-400 transition">
                    <span className="text-white">{(sig.LastClosingVol || sig.Volume || 0).toLocaleString()}</span>
                    <AlertCircle className="w-3.5 h-3.5 text-cyan-400" />
                  </button>
                </td>
                <td className="py-3 pr-4">
                  <span className={`${sig.IsMarketOpen ? 'text-green-400' : 'text-white'}`}>
                    {(sig.CurrentVol || 0).toLocaleString()}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  {sig.IsMarketOpen && sig.ProjectedVol ? (
                    <span className="text-yellow-400">{sig.ProjectedVol.toLocaleString()}</span>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
                <td className="py-3 pr-4 font-bold text-yellow-400">{sig.RVOL}x</td>
                <td className="py-3 pr-4">
                  {typeof sig.EarlyScore === 'number' ? (
                    <span
                      title={sig.EarlyReasons && sig.EarlyReasons.length > 0 ? sig.EarlyReasons.join(', ') : ''}
                      className={`px-2 py-1 rounded text-xs font-bold ${
                        sig.EarlySignal === 'EARLY' ? 'bg-orange-700 text-white' :
                        sig.EarlySignal === 'WATCH' ? 'bg-amber-900 text-amber-200' :
                        'bg-gray-700 text-gray-500'
                      }`}>
                      {sig.EarlyScore}
                      {sig.EarlySignal === 'EARLY' && <span className="ml-1">FIRE</span>}
                    </span>
                  ) : <span className="text-gray-600">-</span>}
                </td>
                <td className="py-3 pr-4">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${
                    sig.Score >= 50 ? 'bg-green-900 text-green-300' :
                    sig.Score >= 28 ? 'bg-yellow-900 text-yellow-300' :
                    'bg-gray-700 text-gray-300'
                  }`}>
                    {sig.Score}
                  </span>
                </td>
                <td className="py-3 text-xs text-gray-400 relative">
                  <div className="flex items-center gap-2">
                    <span>{sig.Reason}</span>
                    <button
                      onClick={() => onInfoClick(i)}
                      className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors"
                    >
                      <Info className={`w-3.5 h-3.5 transition-colors ${activeModalIndex === i ? 'text-green-400' : 'text-gray-500'}`} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
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
