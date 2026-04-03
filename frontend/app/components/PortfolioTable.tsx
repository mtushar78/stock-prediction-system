import { PortfolioItem } from '../types';
import { Wallet, AlertCircle, Info, History } from 'lucide-react';

interface PortfolioTableProps {
  portfolio: PortfolioItem[];
  onVolumeClick: (ticker: string, volume: number) => void;
  onHistoryClick: (ticker: string) => Promise<void>;
  onInfoClick: (index: number) => void;
  onPriceInfoClick: (ticker: string, currentPrice: number) => void;
  onRemove: (ticker: string) => void;
  activeModalIndex: number | null;
}

export default function PortfolioTable({ 
  portfolio, 
  onVolumeClick,
  onHistoryClick,
  onInfoClick,
  onPriceInfoClick,
  onRemove,
  activeModalIndex
}: PortfolioTableProps) {
  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4 text-blue-300 flex items-center gap-2">
        <Wallet className="w-6 h-6" /> Current Holdings
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th className="pb-3 pr-4">TICKER</th>
              <th className="pb-3 pr-4">AVG COST</th>
              <th className="pb-3 pr-4">CURRENT</th>
              <th className="pb-3 pr-4">VOLUME</th>
              <th className="pb-3 pr-4">QTY</th>
              <th className="pb-3 pr-4">TOTAL COST</th>
              <th className="pb-3 pr-4">PROFIT</th>
              <th className="pb-3 pr-4">STATUS</th>
              <th className="pb-3">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.map((item, i) => (
              <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition">
                <td className="py-3 pr-4 font-bold flex items-center gap-1">
                  {item.ticker}
                  <button
                    onClick={() => onHistoryClick(item.ticker)}
                    className="inline-flex items-center justify-center hover:text-purple-400 transition-colors"
                    title="Purchase History"
                  >
                    <History className="w-3 h-3 text-purple-400" />
                  </button>
                </td>
                <td className="py-3 pr-4">{item.buy_price.toFixed(2)}</td>
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <span>{item.current_price.toFixed(2)}</span>
                    <button
                      onClick={() => onPriceInfoClick(item.ticker, item.current_price)}
                      className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors"
                      title="View last 20 days OHLC"
                    >
                      <Info className="w-3.5 h-3.5 text-gray-500 hover:text-emerald-400" />
                    </button>
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <button 
                    onClick={() => onVolumeClick(item.ticker, item.volume)}
                    className="flex items-center gap-1 hover:text-cyan-400 transition"
                  >
                    <span className="text-white">{item.volume.toLocaleString()}</span>
                    <AlertCircle className="w-3.5 h-3.5 text-cyan-400" />
                  </button>
                </td>
                <td className="py-3 pr-4">{item.quantity}</td>
                <td className="py-3 pr-4">
                  <span className="text-orange-400">{item.total_cost?.toFixed(2) || (item.buy_price * item.quantity).toFixed(2)}</span>
                  <div className="text-xs text-gray-500">
                    +{item.commission_paid?.toFixed(2) || '0.00'} comm
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <span className={item.profit_pct >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {item.profit_pct >= 0 ? '+' : ''}{item.profit_pct.toFixed(2)}%
                  </span>
                  <div className="text-xs text-gray-500">
                    {item.profit_amount >= 0 ? '+' : ''}{item.profit_amount.toFixed(0)} BDT
                  </div>
                </td>
                <td className="py-3 pr-4 relative">
                  <div className="flex items-center gap-2">
                    <span className={`${
                      item.status === 'STOP_LOSS' ? 'text-red-500' :
                      item.status === 'TAKE_PROFIT' ? 'text-yellow-500' :
                      item.status === 'ZOMBIE_WARNING' ? 'text-orange-500' :
                      'text-green-500'
                    }`}>{item.status}</span>
                    <button
                      onClick={() => onInfoClick(i)}
                      className="inline-flex items-center justify-center w-4 h-4 rounded-full hover:bg-gray-700 transition-colors"
                    >
                      <Info className={`w-3.5 h-3.5 transition-colors ${activeModalIndex === i ? 'text-blue-400' : 'text-gray-500'}`} />
                    </button>
                  </div>
                </td>
                <td className="py-3">
                  <button 
                    onClick={() => onRemove(item.ticker)}
                    className="text-red-400 hover:text-red-300 text-xs underline"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {portfolio.length === 0 && (
              <tr><td colSpan={9} className="py-6 text-center text-gray-600">
                Portfolio is empty. Add your first trade →
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
