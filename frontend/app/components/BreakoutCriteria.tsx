'use client';

import { Check, X, Minus } from 'lucide-react';

export interface BreakoutChecksShape {
  close?: number; high_20d?: number; dist_to_high_pct?: number; lookback?: number; tol_pct?: number;
  uptrend?: boolean; sma200?: number; ret_20d?: number; max_ext_20d?: number;
  rvol?: number; min_rvol?: number; avg_vol20?: number; min_avg_vol20?: number; min_price?: number;
}

const num = (n: number | undefined | null, d = 2) =>
  typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—';

/** The five breakout rules with the stock's actual value vs the threshold, and a
 *  ✓ / ✗ for each (so it works both for confirmed breakouts and as a "why it
 *  didn't qualify" view in the manual analyzer). */
export default function BreakoutCriteria({ checks }: { checks?: BreakoutChecksShape }) {
  const c = checks || {};
  const lookback = c.lookback ?? 20, tol = c.tol_pct ?? 1, maxExt = c.max_ext_20d ?? 12;
  const minRvol = c.min_rvol ?? 1.5, minVol = c.min_avg_vol20 ?? 50000, minPrice = c.min_price ?? 5;
  const price = c.close;
  const liquidOk = (typeof c.avg_vol20 === 'number' ? c.avg_vol20 >= minVol : undefined);
  const priceOk = (typeof price === 'number' ? price >= minPrice : undefined);

  const rows: { ok: boolean | undefined; label: string; detail: string; rule: string }[] = [
    {
      ok: typeof c.dist_to_high_pct === 'number' ? c.dist_to_high_pct > -tol : undefined,
      label: `Breaking the ${lookback}-day high`,
      detail: `Price ${num(price)} vs ${lookback}-day high ${num(c.high_20d)}${typeof c.dist_to_high_pct === 'number' ? `  (${c.dist_to_high_pct > 0 ? '+' : ''}${num(c.dist_to_high_pct)}% from it)` : ''}`,
      rule: `at or within ${tol}% of the ${lookback}-day high`,
    },
    {
      ok: typeof c.ret_20d === 'number' ? c.ret_20d < maxExt : undefined,
      label: 'Early in the move — not extended',
      detail: `Up ${num(c.ret_20d, 1)}% over the last 20 days`,
      rule: `under ${maxExt}% (avoids an exhausted run)`,
    },
    {
      ok: c.uptrend === true ? true : c.uptrend === false ? false
        : (typeof price === 'number' && typeof c.sma200 === 'number' ? price > c.sma200 : undefined),
      label: 'Confirmed uptrend',
      detail: `Price ${num(price)} vs 200-day average ${num(c.sma200)}`,
      rule: 'must trade above the 200-day SMA',
    },
    {
      ok: typeof c.rvol === 'number' ? c.rvol >= minRvol : undefined,
      label: 'Real volume confirmation',
      detail: `Today's volume is ${num(c.rvol, 1)}× the 20-day average (RVOL)`,
      rule: `at least ${minRvol}×`,
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
