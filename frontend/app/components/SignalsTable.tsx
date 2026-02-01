import { Signal } from '../types';
import { AlertCircle, Info } from 'lucide-react';

interface SignalsTableProps {
  signals: Signal[];
  loading: boolean;
  onVolumeClick: (signal: Signal) => void;
  onInfoClick: (index: number) => void;
  activeModalIndex: number | null;
}

export default function SignalsTable({ 
  signals, 
  loading, 
  onVolumeClick, 
  onInfoClick,
  activeModalIndex 
}: SignalsTableProps) {
  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4 text-green-300">🔭 Sniper Scope (Buy Signals)</h2>
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
              <th className="pb-3 pr-4">SCORE</th>
              <th className="pb-3">REASON</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((sig, i) => (
              <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition">
                <td className="py-3 pr-4 font-bold text-green-400">{sig.Ticker}</td>
                <td className="py-3 pr-4">{sig.Price}</td>
                <td className="py-3 pr-4">
                  {sig.TrendStatus ? (
                    <span className={`text-xs font-bold ${sig.TrendStatus === 'UPTREND' ? 'text-green-400' : 'text-red-400'}`}>
                      {sig.TrendStatus === 'UPTREND' ? '⬆️' : '⬇️'}
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
                  <span className={`${sig.IsMarketOpen ? 'text-green-400' : 'text-gray-500'}`}>
                    {sig.IsMarketOpen ? (sig.CurrentVol || 0).toLocaleString() : (sig.LastClosingVol || sig.Volume || 0).toLocaleString()}
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
                  <span className={`px-2 py-1 rounded text-xs font-bold ${
                    sig.Score >= 80 ? 'bg-green-900 text-green-300' : 
                    sig.Score >= 45 ? 'bg-yellow-900 text-yellow-300' : 
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
            {signals.length === 0 && (
              <tr><td colSpan={9} className="py-6 text-center text-gray-600">
                {loading ? 'Loading signals...' : 'No signals today. Market is sleeping.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
