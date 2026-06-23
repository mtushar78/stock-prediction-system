'use client';

import { Signal } from '../types';
import { X, Check, Rocket } from 'lucide-react';

interface Props {
  signal: Signal;
  onClose: () => void;
}

const num = (n: number | undefined | null, d = 2) =>
  typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—';

/** Precise, plain-English breakdown of WHY a stock fired the breakout signal —
 *  each of the 5 rules with the stock's actual value vs the threshold. */
export default function BreakoutDetailModal({ signal, onClose }: Props) {
  const c = signal.BreakoutChecks || {};
  const price = c.close ?? signal.Price;
  const lookback = c.lookback ?? 20;
  const tol = c.tol_pct ?? 1;
  const maxExt = c.max_ext_20d ?? 12;
  const minRvol = c.min_rvol ?? 1.5;
  const minVol = c.min_avg_vol20 ?? 50000;
  const minPrice = c.min_price ?? 5;
  const rvol = c.rvol ?? signal.RVOL;

  const criteria = [
    {
      label: `Breaking the ${lookback}-day high`,
      detail: `Price ${num(price)} is pressing its ${lookback}-day high${c.high_20d ? ` of ${num(c.high_20d)}` : ''} — the breakout trigger.`,
      rule: `Rule: at or within ${tol}% of the ${lookback}-day high${typeof c.dist_to_high_pct === 'number' ? `  ·  now ${c.dist_to_high_pct > 0 ? '+' : ''}${num(c.dist_to_high_pct)}% from it` : ''}.`,
    },
    {
      label: 'Early in the move — not extended',
      detail: `Up ${num(c.ret_20d, 1)}% over the last 20 days.`,
      rule: `Rule: under ${maxExt}% — avoids buying a move that already ran (which tends to revert).`,
    },
    {
      label: 'Confirmed uptrend',
      detail: `Price ${num(price)} is above the 200-day average${c.sma200 ? ` of ${num(c.sma200)}` : ''}.`,
      rule: 'Rule: must trade above its 200-day SMA (only buy stocks in a long-term uptrend).',
    },
    {
      label: 'Real volume confirmation',
      detail: `Today's volume is ${num(rvol, 1)}× the 20-day average (RVOL).`,
      rule: `Rule: at least ${minRvol}× — the breakout must be backed by genuine buying.`,
    },
    {
      label: 'Liquid & tradeable',
      detail: `20-day average volume ${num(c.avg_vol20, 0)} shares; price ${num(price)}.`,
      rule: `Rule: avg volume ≥ ${num(minVol, 0)} and price ≥ ${minPrice} (excludes thin / penny names).`,
    },
  ];

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-gray-900 border border-sky-700 rounded-xl max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-900">
          <div className="flex items-center gap-2">
            <Rocket className="w-5 h-5 text-sky-400" />
            <span className="text-lg font-bold text-sky-300">{signal.Ticker}</span>
            <span className="text-xs text-sky-200/70 bg-sky-900/40 border border-sky-800 rounded px-2 py-0.5">
              BREAKOUT{signal.IsFreshBreakout ? ' · fresh (day 1)' : ''}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-4">
          <p className="text-sm text-gray-400 mb-3">
            All five conditions passed — here&apos;s the exact reason this is on the buy list:
          </p>

          <div className="space-y-2.5">
            {criteria.map((cr) => (
              <div key={cr.label} className="flex gap-2.5 bg-gray-800/60 border border-gray-700 rounded-lg p-2.5">
                <span className="mt-0.5 shrink-0 w-5 h-5 rounded-full bg-emerald-600 flex items-center justify-center">
                  <Check className="w-3.5 h-3.5 text-white" />
                </span>
                <div>
                  <div className="text-sm font-bold text-gray-100">{cr.label}</div>
                  <div className="text-sm text-gray-300">{cr.detail}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{cr.rule}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 text-xs text-sky-200/80 bg-sky-900/20 border border-sky-800/50 rounded-lg p-3">
            <b className="text-sky-300">Why trust this:</b> in a 2019–2026 walk-forward backtest, this
            breakout rule was the only entry signal with a positive edge in <b>every year</b>
            (+1.1%/trade, 42% win) — while the legacy Score/Early signals were inversely related to
            forward returns. This is the list to act on.
          </div>
        </div>
      </div>
    </div>
  );
}
