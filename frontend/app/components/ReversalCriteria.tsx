'use client';

import { Check, X, Minus } from 'lucide-react';
import { ReversalChecksShape } from './reversalGrade';

const num = (n: number | undefined | null, d = 2) =>
  typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—';

/** The five reversal rules with the stock's actual value vs the threshold, and a
 *  ✓ / ✗ for each (works both for confirmed reversals and as a "why it didn't
 *  qualify" view). */
export default function ReversalCriteria({ checks, fallbackPrice }: { checks?: ReversalChecksShape; fallbackPrice?: number }) {
  const c = checks || {};
  const maxRsi = c.max_rsi ?? 30, minRvol = c.min_rvol ?? 1.5;
  const minRoom = c.min_room_pct ?? 15, minVol = c.min_avg_vol20 ?? 50000, minPrice = c.min_price ?? 5;
  const price = typeof c.close === 'number' ? c.close : fallbackPrice;
  const liquidOk = (typeof c.avg_vol20 === 'number' ? c.avg_vol20 >= minVol : undefined);
  const priceOk = (typeof price === 'number' ? price >= minPrice : undefined);

  const rows: { ok: boolean | undefined; label: string; detail: string; rule: string }[] = [
    {
      ok: typeof c.rsi === 'number' ? c.rsi < maxRsi : undefined,
      label: 'Deeply oversold',
      detail: `RSI(14) is ${num(c.rsi, 0)}${typeof c.ret5 === 'number' ? `  (${c.ret5 > 0 ? '+' : ''}${num(c.ret5, 1)}% over 5 days)` : ''}`,
      rule: `below ${maxRsi} — washed-out, sellers exhausted`,
    },
    {
      ok: c.green_day === true ? true : c.green_day === false ? false : undefined,
      label: 'The turn has started (green day)',
      detail: typeof c.prev_close === 'number'
        ? `Today ${num(price)} closed above yesterday's ${num(c.prev_close)}`
        : `Today closed above the prior day`,
      rule: 'first up-close — confirms a bounce, not a falling knife',
    },
    {
      ok: typeof c.rvol === 'number' ? c.rvol >= minRvol : undefined,
      label: 'Real volume on the turn',
      detail: `Today's volume is ${num(c.rvol, 1)}× the 20-day average (RVOL)`,
      rule: `at least ${minRvol}× — buyers are stepping in`,
    },
    {
      ok: typeof c.room_pct === 'number' ? c.room_pct <= -minRoom : undefined,
      label: 'Room to run',
      detail: `Price ${num(price)} is ${num(c.room_pct, 0)}% below its 120-day high${typeof c.high_120 === 'number' ? ` (${num(c.high_120)})` : ''}`,
      rule: `at least ${minRoom}% below the 120-day high — upside headroom`,
    },
    {
      ok: liquidOk === undefined || priceOk === undefined ? undefined : (liquidOk && priceOk),
      label: 'Liquid & tradeable',
      detail: `20-day avg volume ${num(c.avg_vol20, 0)} · price ${num(price)}`,
      rule: `avg vol ≥ ${num(minVol, 0)} and price ≥ ${minPrice}`,
    },
  ];

  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="flex gap-2.5 bg-gray-800/60 border border-gray-700 rounded-lg p-2.5">
          <span className={`mt-0.5 shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${
            r.ok === false ? 'bg-red-600' : r.ok ? 'bg-emerald-600' : 'bg-gray-600'}`}>
            {r.ok === false ? <X className="w-3.5 h-3.5 text-white" />
              : r.ok ? <Check className="w-3.5 h-3.5 text-white" />
              : <Minus className="w-3.5 h-3.5 text-white" />}
          </span>
          <div>
            <div className="text-sm font-bold text-gray-100">{r.label}</div>
            <div className="text-sm text-gray-300">{r.detail}</div>
            <div className="text-xs text-gray-500 mt-0.5">Rule: {r.rule}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
