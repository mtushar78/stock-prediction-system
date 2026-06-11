import { PlusCircle, AlertTriangle } from 'lucide-react';

interface TradeFormProps {
  ticker: string;
  price: string;
  qty: string;
  submitting: boolean;
  error?: string | null;
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
  error,
  onTickerChange,
  onPriceChange,
  onQtyChange,
  onSubmit,
}: TradeFormProps) {
  // Live validity for cheap feedback
  const priceNum = parseFloat(price);
  const qtyNum = parseInt(qty, 10);
  const priceValid = !Number.isNaN(priceNum) && priceNum > 0;
  const qtyValid = !Number.isNaN(qtyNum) && qtyNum > 0;
  const tickerValid = ticker.trim().length > 0;
  const canSubmit = priceValid && qtyValid && tickerValid && !submitting;
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
              min="0.01"
              value={price}
              onChange={e => onPriceChange(e.target.value)}
              className={`w-full bg-gray-900 border rounded p-2 text-white focus:border-green-500 outline-none ${
                price && !priceValid ? 'border-red-500' : 'border-gray-600'
              }`}
              placeholder="0.00"
              disabled={submitting}
            />
            {price && !priceValid && (
              <div className="text-[10px] text-red-400 mt-1">Price must be greater than 0</div>
            )}
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">QTY</label>
            <input
              type="number"
              min="1"
              step="1"
              value={qty}
              onChange={e => onQtyChange(e.target.value)}
              className={`w-full bg-gray-900 border rounded p-2 text-white focus:border-green-500 outline-none ${
                qty && !qtyValid ? 'border-red-500' : 'border-gray-600'
              }`}
              placeholder="0"
              disabled={submitting}
            />
            {qty && !qtyValid && (
              <div className="text-[10px] text-red-400 mt-1">Quantity must be a positive whole number</div>
            )}
          </div>
        </div>
        {error && (
          <div className="flex items-start gap-2 bg-red-900/30 border border-red-700 rounded p-2 text-xs text-red-300">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-bold py-3 rounded transition"
          title={!canSubmit && !submitting ? 'Fill ticker, valid price (>0) and quantity (>0)' : undefined}
        >
          {submitting ? 'ADDING...' : 'ADD TO PORTFOLIO'}
        </button>
      </form>
    </section>
  );
}
