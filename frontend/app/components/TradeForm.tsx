import { PlusCircle, AlertTriangle, Loader2, CheckCircle2 } from 'lucide-react';
import { EntryGuidance } from '../types';

interface TradeFormProps {
  ticker: string;
  price: string;
  qty: string;
  submitting: boolean;
  error?: string | null;
  tickers?: string[];
  priceLoading?: boolean;
  priceSource?: 'auto' | 'manual' | null;
  priceFetchError?: string | null;
  guidance?: EntryGuidance | null;
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
  tickers = [],
  priceLoading = false,
  priceSource = null,
  priceFetchError = null,
  guidance = null,
  onTickerChange,
  onPriceChange,
  onQtyChange,
  onSubmit,
}: TradeFormProps) {
  const priceNum = parseFloat(price);
  const qtyNum = parseInt(qty, 10);
  const priceValid = !Number.isNaN(priceNum) && priceNum > 0;
  const qtyValid = !Number.isNaN(qtyNum) && qtyNum > 0;
  const tickerNorm = ticker.trim().toUpperCase();
  const tickerValid = tickerNorm.length > 0;
  const tickerInList = tickers.length === 0 || tickers.includes(tickerNorm);
  const canSubmit = priceValid && qtyValid && tickerValid && !submitting;

  // Live entry-quality note: where does the price you're about to enter sit
  // inside today's range? Warn (never block) when it isn't near the low.
  let entryNote: { tone: 'good' | 'fair' | 'high'; text: string } | null = null;
  if (guidance && guidance.day_high > guidance.day_low && priceValid) {
    const { day_low: lo, day_high: hi, recommended_entry: rec } = guidance;
    const pos = Math.max(0, Math.min(1, (priceNum - lo) / (hi - lo)));
    const pct = Math.round(pos * 100);
    const range = `৳${lo.toFixed(2)}–৳${hi.toFixed(2)}`;
    if (pos <= 0.33) {
      entryNote = { tone: 'good', text: `Good entry — ৳${priceNum.toFixed(2)} is near today's low (~${pct}% up the ${range} range).` };
    } else if (pos <= 0.55) {
      entryNote = { tone: 'fair', text: `Mid-range — ৳${priceNum.toFixed(2)} sits ~${pct}% up today's range (${range}). A dip toward ৳${rec.toFixed(2)} would be a safer entry.` };
    } else {
      entryNote = { tone: 'high', text: `Not near the day's low — ৳${priceNum.toFixed(2)} is ~${pct}% up today's range (${range}). Buying here may give a short-term loss; consider a limit near ৳${rec.toFixed(2)}.` };
    }
  }

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4 text-gray-100 flex items-center gap-2">
        <PlusCircle className="w-6 h-6" /> Record Trade
      </h2>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            TICKER SYMBOL
            {tickers.length > 0 && (
              <span className="text-gray-600 normal-case ml-2">({tickers.length} available)</span>
            )}
          </label>
          <input
            type="text"
            list="trade-tickers"
            value={ticker}
            onChange={e => onTickerChange(e.target.value.toUpperCase())}
            className={`w-full bg-gray-900 border rounded p-2 text-white focus:border-green-500 outline-none ${
              ticker && !tickerInList ? 'border-yellow-600' : 'border-gray-600'
            }`}
            placeholder={tickers.length > 0 ? 'Type or pick — e.g. ACIFORMULA' : 'e.g. ACIFORMULA'}
            disabled={submitting}
            autoComplete="off"
          />
          <datalist id="trade-tickers">
            {tickers.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          {ticker && !tickerInList && tickers.length > 0 && (
            <div className="text-[10px] text-yellow-500 mt-1">
              &ldquo;{tickerNorm}&rdquo; isn&rsquo;t in the database. Submit anyway, or pick from the list.
            </div>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1">
              <span>BUY PRICE (৳)</span>
              {priceLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
              {!priceLoading && priceSource === 'auto' && (
                <span title="Pre-filled from last close. Edit if you bought at a different price.">
                  <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                </span>
              )}
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={price}
              onChange={e => onPriceChange(e.target.value)}
              className={`w-full bg-gray-900 border rounded p-2 text-white focus:border-green-500 outline-none ${
                price && !priceValid ? 'border-red-500' :
                priceSource === 'auto' ? 'border-emerald-700' :
                'border-gray-600'
              }`}
              placeholder={priceLoading ? 'Fetching…' : '0.00'}
              disabled={submitting || priceLoading}
            />
            {priceSource === 'auto' && priceValid && (
              <div className="text-[10px] text-emerald-500 mt-1">
                Auto-filled from last close. You can override it.
              </div>
            )}
            {priceFetchError && !priceLoading && (
              <div className="text-[10px] text-yellow-500 mt-1">
                Couldn&rsquo;t auto-fill price — enter manually.
              </div>
            )}
            {price && !priceValid && (
              <div className="text-[10px] text-red-400 mt-1">Price must be greater than 0</div>
            )}
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">QTY (shares)</label>
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
              autoFocus={!!priceValid && priceSource === 'auto' && !qty}
            />
            {qty && !qtyValid && (
              <div className="text-[10px] text-red-400 mt-1">Quantity must be a positive whole number</div>
            )}
          </div>
        </div>
        {guidance && (
          <div className="text-xs bg-gray-900 border border-gray-700 rounded p-2 space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Prev close</span>
              <span className="text-gray-300">{guidance.prev_close != null ? `৳${guidance.prev_close.toFixed(2)}` : '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Current price</span>
              <span className="text-gray-300">৳{guidance.current_price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Today&rsquo;s range</span>
              <span className="text-gray-300">৳{guidance.day_low.toFixed(2)} – ৳{guidance.day_high.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Recommended buy</span>
              <span className="flex items-center gap-2">
                <span className="text-emerald-400 font-bold">≤ ৳{guidance.recommended_entry.toFixed(2)}</span>
                <button
                  type="button"
                  onClick={() => onPriceChange(String(guidance.recommended_entry))}
                  disabled={submitting}
                  className="text-[10px] uppercase tracking-wide text-emerald-500 hover:text-emerald-300 border border-emerald-800 rounded px-1.5 py-0.5"
                >
                  use
                </button>
              </span>
            </div>
          </div>
        )}
        {entryNote && (
          <div className={`flex items-start gap-2 rounded p-2 text-xs border ${
            entryNote.tone === 'high' ? 'bg-red-900/30 border-red-700 text-red-300' :
            entryNote.tone === 'fair' ? 'bg-yellow-900/20 border-yellow-700 text-yellow-300' :
            'bg-emerald-900/20 border-emerald-700 text-emerald-300'
          }`}>
            {entryNote.tone === 'good'
              ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
              : <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />}
            <span>{entryNote.text}</span>
          </div>
        )}
        {priceValid && qtyValid && (
          <div className="text-xs text-gray-500 bg-gray-900 border border-gray-700 rounded p-2">
            Trade value: <span className="text-white font-bold">৳{(priceNum * qtyNum).toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
            <span className="text-gray-600 ml-2">+ 0.40% commission ≈ ৳{(priceNum * qtyNum * 0.004).toFixed(2)}</span>
          </div>
        )}
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
          title={!canSubmit && !submitting ? 'Pick a ticker, valid price (>0) and quantity (>0)' : undefined}
        >
          {submitting ? 'ADDING…' : 'ADD TO PORTFOLIO'}
        </button>
      </form>
    </section>
  );
}
