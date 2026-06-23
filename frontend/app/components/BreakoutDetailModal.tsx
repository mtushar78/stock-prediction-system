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
                {q.grade === 'A' ? '(~54% win historically)' : q.grade === 'D' ? '(~42% win)' : '(mid-tier)'}
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
              Higher grade = historically better odds (not a guarantee). Drivers: market regime, tighter base, calmer volatility, non-extreme volume.
            </div>
          </div>

          <p className="text-sm text-gray-400 mb-3">
            All five entry conditions passed — the exact values:
          </p>

          <BreakoutCriteria checks={signal.BreakoutChecks} fallbackPrice={signal.Price} />

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
