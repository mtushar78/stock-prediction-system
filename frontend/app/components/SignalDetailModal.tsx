import { Signal } from '../types';

interface SignalDetailModalProps {
  signal: Signal;
  onClose: () => void;
}

export default function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={onClose}>
      <div 
        className="bg-gray-950 border border-green-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[500px]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4 border-b border-gray-700 pb-3">
          <div>
            <h3 className="text-lg font-bold text-green-400">{signal.Ticker}</h3>
            <div className="text-xs text-gray-500">Trading Signal Details</div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-2xl font-bold">
            ×
          </button>
        </div>

        <div className="space-y-4 text-sm">
          {/* Price & Signal Strength */}
          <div className="bg-gray-900 p-4 rounded">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-500 text-xs">Current Price</div>
                <div className="text-white font-bold text-lg">৳{signal.Price}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">Signal Score</div>
                <div className={`font-bold text-lg ${
                  signal.Score >= 80 ? 'text-green-400' : 
                  signal.Score >= 45 ? 'text-yellow-400' : 'text-red-400'
                }`}>{signal.Score}/100</div>
              </div>
            </div>
          </div>

          {/* v4: TREND STATUS */}
          {signal.TrendStatus && (
            <div className={`p-4 rounded border-2 ${
              signal.TrendStatus === 'UPTREND' 
                ? 'bg-green-900/20 border-green-600' 
                : 'bg-red-900/20 border-red-600'
            }`}>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-bold text-gray-400">📊 TREND (v4)</div>
                <div className={`text-lg font-bold ${
                  signal.TrendStatus === 'UPTREND' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {signal.TrendStatus === 'UPTREND' ? '⬆️ UPTREND' : '⬇️ DOWNTREND'}
                </div>
              </div>
              <div className="text-xs text-gray-400">
                Price vs 200 SMA: ৳{signal.Price} {signal.TrendStatus === 'UPTREND' ? '>' : '<'} ৳{signal.SMA200?.toFixed(2)}
              </div>
            </div>
          )}

          {/* v4: TRADING LEVELS */}
          {(signal.NearestSupport || signal.NearestResistance || signal.RecommendedStopLoss) && (
            <div className="bg-blue-900/20 border border-blue-700 p-4 rounded">
              <div className="text-xs font-bold text-blue-400 mb-3">🎯 TRADING LEVELS (v4)</div>
              <div className="space-y-2">
                {signal.NearestSupport && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Support (Buy Zone)</span>
                    <span className="text-green-400 font-bold">৳{signal.NearestSupport.toFixed(2)}</span>
                  </div>
                )}
                {signal.NearestResistance && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Resistance (Target)</span>
                    <span className="text-red-400 font-bold">৳{signal.NearestResistance.toFixed(2)}</span>
                  </div>
                )}
                {signal.RecommendedStopLoss && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Stop Loss</span>
                    <span className="text-orange-400 font-bold">৳{signal.RecommendedStopLoss.toFixed(2)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* v4: REWARD:RISK RATIO */}
          {signal.RewardRiskRatio !== undefined && signal.RewardRiskRatio !== null && (
            <div className={`p-4 rounded border-2 ${
              signal.RewardRiskRatio >= 2.0 
                ? 'bg-green-900/20 border-green-600' 
                : 'bg-yellow-900/20 border-yellow-600'
            }`}>
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-gray-400">⚖️ REWARD:RISK (v4)</div>
                <div className={`text-xl font-bold ${
                  signal.RewardRiskRatio >= 2.0 ? 'text-green-400' : 'text-yellow-400'
                }`}>
                  {signal.RewardRiskRatio.toFixed(1)}:1
                </div>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {signal.RewardRiskRatio >= 2.0 
                  ? '✅ Good - Profit potential is 2× the risk' 
                  : '⚠️ Poor - Risk too high for potential reward'}
              </div>
            </div>
          )}

          {/* Score Calculation Breakdown */}
          <div className="bg-purple-900/20 border border-purple-700 p-4 rounded">
            <div className="text-xs font-bold text-purple-400 mb-3">🎲 SCORE CALCULATION</div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center pb-2 border-b border-gray-700">
                <span className="text-gray-400">Base Score</span>
                <span className="text-white font-bold">0</span>
              </div>
              
              {signal.RVOL > 2.5 && (
                <div className="flex justify-between items-center">
                  <span className="text-green-400">✅ RVOL {'>'} 2.5 ({signal.RVOL.toFixed(2)}x)</span>
                  <span className="text-green-400 font-bold">+50</span>
                </div>
              )}
              
              {signal.RVOL > 2.5 && Math.abs(signal.PriceChange || 0) < 2 && (
                <div className="flex justify-between items-center">
                  <span className="text-green-400">✅ Quiet Accumulation (Price Δ: {signal.PriceChange?.toFixed(2)}%)</span>
                  <span className="text-green-400 font-bold">+20</span>
                </div>
              )}
              
              {signal.Price > (signal.SMA200 || 0) ? (
                <div className="flex justify-between items-center">
                  <span className="text-green-400">✅ Above 200 SMA (₳{signal.Price} {'>'} ₳{signal.SMA200?.toFixed(2)})</span>
                  <span className="text-green-400 font-bold">+10</span>
                </div>
              ) : (
                <div className="flex justify-between items-center">
                  <span className="text-red-400">❌ Below 200 SMA (₳{signal.Price} {'<'} ₳{signal.SMA200?.toFixed(2)})</span>
                  <span className="text-red-400 font-bold">-50</span>
                </div>
              )}
              
              <div className="flex justify-between items-center pt-2 border-t-2 border-gray-600 mt-2">
                <span className="text-white font-bold">FINAL SCORE</span>
                <span className={`text-xl font-bold ${
                  signal.Score >= 80 ? 'text-green-400' : 
                  signal.Score >= 45 ? 'text-yellow-400' : 'text-red-400'
                }`}>{signal.Score}/100</span>
              </div>
              
              <div className="text-gray-500 text-xs italic mt-2">
                {signal.Score >= 80 && '✅ Strong BUY - High confidence signal'}
                {signal.Score >= 45 && signal.Score < 80 && '⚠️ WAIT - Monitor closely'}
                {signal.Score < 45 && '❌ PASS - Not recommended'}
              </div>
            </div>
          </div>

          {/* Volume Info */}
          <div className="bg-gray-900 p-4 rounded">
            <div className="text-xs font-bold text-gray-400 mb-2">📈 VOLUME ANALYSIS</div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">RVOL (Relative Volume)</span>
                <span className="text-yellow-400 font-bold">{signal.RVOL}x</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Today's Volume</span>
                <span className="text-white">{(signal.Volume || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">20-Day Avg Volume</span>
                <span className="text-white">{(signal.AvgVolume20 || 0).toLocaleString()}</span>
              </div>
              <div className="text-gray-500 mt-2 italic">
                {signal.RVOL > 2.5 ? '✅ High volume - Syndicate activity detected' : '⚠️ Normal volume'}
              </div>
            </div>
          </div>

          {/* Action Button */}
          <button 
            onClick={onClose}
            className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 rounded transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
