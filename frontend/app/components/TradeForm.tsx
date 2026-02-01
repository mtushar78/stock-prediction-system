import { PlusCircle } from 'lucide-react';

interface TradeFormProps {
  ticker: string;
  price: string;
  qty: string;
  submitting: boolean;
  onTickerChange: (value: string) => void;
  onPriceChange: (value: string) => void;
  onQtyChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
}

export default function TradeForm({
  ticker,
  price,
  qty,
  submitting,
  onTickerChange,
  onPriceChange,
  onQtyChange,
  onSubmit
}: TradeFormProps) {
  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4 text-gray-100 flex items-center gap-2">
        <PlusCircle className="w-6 h-6" /> Record Trade
      </h2>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">TICKER SYMBOL</label>
          <input 
            type="text" 
            value={ticker}
            onChange={e => onTickerChange(e.target.value.toUpperCase())}
            className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:border-green-500 outline-none"
            placeholder="e.g. ACI"
            disabled={submitting}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">BUY PRICE</label>
            <input 
              type="number" 
              step="0.01"
              value={price}
              onChange={e => onPriceChange(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:border-green-500 outline-none"
              placeholder="0.00"
              disabled={submitting}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">QTY</label>
            <input 
              type="number" 
              value={qty}
              onChange={e => onQtyChange(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:border-green-500 outline-none"
              placeholder="0"
              disabled={submitting}
            />
          </div>
        </div>
        <button 
          type="submit" 
          disabled={submitting}
          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white font-bold py-3 rounded transition"
        >
          {submitting ? 'ADDING...' : 'ADD TO PORTFOLIO'}
        </button>
      </form>
    </section>
  );
}
