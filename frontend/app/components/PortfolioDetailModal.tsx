import { PortfolioItem } from '../types';

interface PortfolioDetailModalProps {
  item: PortfolioItem;
  onClose: () => void;
}

export default function PortfolioDetailModal({ item, onClose }: PortfolioDetailModalProps) {
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={onClose}>
      <div 
        className="bg-gray-950 border border-blue-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[500px]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4 border-b border-gray-700 pb-3">
          <div>
            <h3 className="text-lg font-bold text-blue-400">{item.ticker}</h3>
            <div className="text-xs text-gray-500">Position Details</div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-2xl font-bold">
            ×
          </button>
        </div>

        <div className="space-y-4 text-sm">
          {/* Profit/Loss Summary */}
          <div className={`p-4 rounded border-2 ${
            item.profit_pct >= 0 
              ? 'bg-green-900/20 border-green-600' 
              : 'bg-red-900/20 border-red-600'
          }`}>
            <div className="text-xs text-gray-400 mb-1">Current P/L</div>
            <div className={`text-3xl font-bold ${item.profit_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {item.profit_pct >= 0 ? '+' : ''}{item.profit_pct.toFixed(2)}%
            </div>
            <div className={`text-lg ${item.profit_amount >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {item.profit_amount >= 0 ? '+' : ''}{item.profit_amount.toFixed(0)} BDT
            </div>
          </div>

          {/* Position Info */}
          <div className="bg-gray-900 p-4 rounded">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-gray-500 text-xs">Buy Price</div>
                <div className="text-white font-bold">৳{item.buy_price.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">Current Price</div>
                <div className="text-white font-bold">৳{item.current_price.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">Quantity</div>
                <div className="text-white font-bold">{item.quantity}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">Days Held</div>
                <div className={`font-bold ${item.days_held > 10 ? 'text-orange-400' : 'text-white'}`}>
                  {item.days_held} days
                </div>
              </div>
            </div>
          </div>

          {/* Stop Loss Levels */}
          <div className="bg-blue-900/20 border border-blue-700 p-4 rounded">
            <div className="text-xs font-bold text-blue-400 mb-3">🛡️ STOP LOSS SYSTEM (v3 UPGRADE)</div>
            <div className="space-y-2">
              <div className="border-b border-gray-700 pb-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Emergency Brake</span>
                  <span className="text-red-400 font-bold">৳{item.stop_loss_price.toFixed(2)}</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">Fixed -7% hard stop (prevents catastrophic loss)</div>
              </div>
              <div className="pt-1">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-gray-400">Trailing Stop (ATR Dynamic)</div>
                    <div className="text-xs text-green-400">✅ v3: Replaced old fixed 7%!</div>
                  </div>
                  <span className="text-yellow-400 font-bold">৳{item.trailing_stop_price.toFixed(2)}</span>
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  Current: {item.stop_type} | ATR: ৳{item.atr.toFixed(2)}
                </div>
              </div>
              {item.rsi && (
                <div className="flex justify-between items-center border-t border-gray-700 pt-2 mt-2">
                  <span className="text-gray-400">RSI (Multiplier Adjustor)</span>
                  <span className={`font-bold ${item.rsi > 70 ? 'text-red-400' : item.rsi < 30 ? 'text-green-400' : 'text-white'}`}>
                    {item.rsi.toFixed(1)}
                  </span>
                </div>
              )}
            </div>
            <div className="mt-3 pt-2 border-t border-gray-700 text-xs bg-gray-900/50 p-2 rounded">
              <div className="font-bold text-white mb-1">🎯 v3 Improvement:</div>
              <div className="text-gray-400">
                <div>❌ <span className="line-through">Old: Fixed 7% trailing stop</span></div>
                <div className="text-green-400 mt-1">✅ New: ATR-based (adapts to volatility)</div>
              </div>
              <div className="mt-2 text-gray-500">
                • RSI {'>'} 80 → 1.0× ATR (tight, lock profits)
                <br/>• RSI 70-80 → 1.5× ATR (medium)
                <br/>• RSI {'<'} 70 → 2.0× ATR (loose, let run)
              </div>
            </div>
          </div>

          {/* v6 Info Box */}
          <div className="bg-purple-900/20 border border-purple-700 p-4 rounded">
            <div className="text-xs font-bold text-purple-400 mb-2">📌 v6 Scoring Engine</div>
            <div className="text-xs text-gray-300 space-y-1">
              <div><strong className="text-white">Portfolio:</strong> ATR-based trailing stops with RSI adjustment</div>
              <div><strong className="text-white">Buy Signals:</strong> 14-component syndicate detection (BUY≥55%, WAIT≥30%)</div>
              <div className="text-gray-500 italic mt-2">v6 adds price squeeze, buying streak, smart money divergence, and VWAP proximity.</div>
            </div>
          </div>

          {/* Status Warning */}
          {item.status !== 'HOLD' && (
            <div className={`p-4 rounded border-2 ${
              item.status === 'STOP_LOSS' || item.status === 'TAKE_PROFIT' || item.status === 'TREND_EXIT'
                ? 'bg-red-900/30 border-red-600'
                : 'bg-orange-900/30 border-orange-600'
            }`}>
              <div className="flex items-center gap-2">
                <span className="text-2xl">⚠️</span>
                <div>
                  <div className={`font-bold ${
                    item.status === 'STOP_LOSS' || item.status === 'TAKE_PROFIT' || item.status === 'TREND_EXIT'
                      ? 'text-red-400'
                      : 'text-orange-400'
                  }`}>
                    {item.status}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {item.status === 'STOP_LOSS' && 'Emergency stop hit! Sell immediately to limit losses.'}
                    {item.status === 'TAKE_PROFIT' && 'Trailing stop hit while in profit — take profit now.'}
                    {item.status === 'TREND_EXIT' && 'Trailing stop hit below your buy price — trend broke, exit to cap the loss.'}
                    {item.status === 'ZOMBIE_WARNING' && `Held ${item.days_held} days with minimal movement. Consider exiting.`}
                    {item.status === 'CLIMAX' && 'High volume spike! Consider taking partial profits.'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Zombie Warning (if applicable) */}
          {item.is_zombie && item.status === 'HOLD' && (
            <div className="bg-orange-900/30 border border-orange-600 p-4 rounded">
              <div className="flex items-center gap-2">
                <span className="text-xl">🧟</span>
                <div>
                  <div className="font-bold text-orange-400">ZOMBIE POSITION</div>
                  <div className="text-xs text-gray-400 mt-1">
                    Minimal movement for {item.days_held} days. Free up capital for better opportunities.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Volume Analysis */}
          <div className="bg-gray-900 p-4 rounded">
            <div className="text-xs font-bold text-gray-400 mb-2">📊 CURRENT STATUS</div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">Volume Today</span>
                <span className="text-white">{item.volume.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">RVOL</span>
                <span className={`font-bold ${item.rvol >= 2.0 ? 'text-yellow-400' : item.rvol >= 1.5 ? 'text-yellow-300' : 'text-gray-400'}`}>
                  {item.rvol.toFixed(2)}x
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">ATR (Volatility)</span>
                <span className="text-cyan-400">৳{item.atr.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Action Button */}
          <button 
            onClick={onClose}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
