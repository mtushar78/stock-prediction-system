'use client';

import { Signal } from '../types';
import { X, Rocket } from 'lucide-react';
import BreakoutCriteria from './BreakoutCriteria';
import { breakoutGrade, gradeColor } from './breakoutGrade';

interface Props {
  signal: Signal;
  breadth?: number | null;
  onClose: () => void;
}

const dotColor = (g: 'good' | 'ok' | 'weak') =>
  g === 'good' ? 'text-emerald-400' : g === 'ok' ? 'text-yellow-400' : 'text-red-400';

/** Precise, plain-English breakdown of WHY a stock fired the breakout signal —
 *  the quality grade, then each of the 5 rules with actual value vs threshold. */
export default function BreakoutDetailModal({ signal, breadth, onClose }: Props) {
  const q = breakoutGrade(signal.BreakoutChecks, breadth);
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
          {/* Quality grade — how this breakout ranks vs other breakouts */}
          <div className="mb-4 bg-gray-800/60 border border-gray-700 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className={`inline-flex items-center justify-center w-8 h-7 rounded font-bold ${gradeColor(q.grade)}`}>{q.grade}</span>
              <span className="text-sm font-bold text-gray-200">Quality grade — {q.score}/100</span>
              <span className="text-xs text-gray-500">
                {q.grade === 'A' ? '(~+0.7%/trade net of costs, 48% win)' : q.grade === 'D' ? '(~0% net — skip)' : '(mid-tier)'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {q.factors.map((f) => (
                <div key={f.label} className="flex items-center justify-between gap-2">
                  <span className="text-gray-400">{f.label}</span>
                  <span className={dotColor(f.good)}>{f.value} ●</span>
                </div>
              ))}
            </div>
            <div className="text-[11px] text-gray-500 mt-2">
              Higher grade = historically better odds (not a guarantee). Market breadth is the only factor with real
              predictive weight; base/ATR are shown for information only.
            </div>
          </div>

          <p className="text-sm text-gray-400 mb-3">
            All five entry conditions passed — the exact values:
          </p>

          <BreakoutCriteria checks={signal.BreakoutChecks} fallbackPrice={signal.Price} />

          <div className="mt-4 text-xs text-amber-200/80 bg-amber-900/20 border border-amber-800/50 rounded-lg p-3">
            <b className="text-amber-300">Honest expectation (2019–2026 backtest, net of the 0.8% round-trip
            commission):</b> +0.33%/trade, 41% win — about ৳33 on a ৳10,000 position, and negative in 4 of 8
            years. This entry buys at the 20-day high by construction, which DSE rarely rewards. Treat it as a
            <b> watchlist</b>: the same stocks pay ~15× more per trade when bought later as <b>Reversals</b>
            (+5.1% net, 65% win). If you do trade it, require market breadth ≥ 55% and Grade A.
          </div>
        </div>
      </div>
    </div>
  );
}
