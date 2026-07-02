'use client';

import { Signal } from '../types';
import { X, TrendingDown } from 'lucide-react';
import ReversalCriteria from './ReversalCriteria';
import { reversalGrade, gradeColor } from './reversalGrade';

interface Props {
  signal: Signal;
  onClose: () => void;
}

const dotColor = (g: 'good' | 'ok' | 'weak') =>
  g === 'good' ? 'text-emerald-400' : g === 'ok' ? 'text-yellow-400' : 'text-red-400';

/** Plain-English breakdown of WHY a stock fired the reversal signal — the
 *  quality grade, then each of the 5 rules with actual value vs threshold. */
export default function ReversalDetailModal({ signal, onClose }: Props) {
  const q = reversalGrade(signal.ReversalChecks);
  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-gray-900 border border-amber-700 rounded-xl max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-900">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-amber-400" />
            <span className="text-lg font-bold text-amber-300">{signal.Ticker}</span>
            <span className="text-xs text-amber-200/70 bg-amber-900/40 border border-amber-800 rounded px-2 py-0.5">
              REVERSAL{signal.IsFreshReversal ? ' · fresh (day 1)' : ''}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-4">
          {/* Quality grade — how this reversal ranks vs other reversals */}
          <div className="mb-4 bg-gray-800/60 border border-gray-700 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className={`inline-flex items-center justify-center w-8 h-7 rounded font-bold ${gradeColor(q.grade)}`}>{q.grade}</span>
              <span className="text-sm font-bold text-gray-200">Quality grade — {q.score}/100</span>
              <span className="text-xs text-gray-500">
                {q.grade === 'A' ? '(~82% win historically)' : q.grade === 'D' ? '(~58% win)' : '(mid-tier)'}
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
              Higher grade = historically better odds (not a guarantee). Drivers: deeper oversold, further below the 50-day average, sharper recent drop, stronger turn volume.
            </div>
          </div>

          {signal.ReversalChecks?.deep_value && (
            <div className="mb-3 bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3 text-xs text-emerald-200/90">
              <b className="text-emerald-300">★ DEEP VALUE</b> — near its 1-year low
              {typeof signal.ReversalChecks.room_life === 'number' ? ` with ${Math.round(signal.ReversalChecks.room_life)}% room back to its lifetime high` : ' with big lifetime headroom'}.
              These reversals historically win <b>~70%</b> (vs ~63% for a regular one) — the strongest reversals on the list.
            </div>
          )}

          <p className="text-sm text-gray-400 mb-3">
            All five entry conditions passed — the exact values:
          </p>

          <ReversalCriteria checks={signal.ReversalChecks} fallbackPrice={signal.Price} />

          <div className="mt-4 text-xs text-amber-200/80 bg-amber-900/20 border border-amber-800/50 rounded-lg p-3">
            <b className="text-amber-300">Why trust this:</b> in a 2019–2026 walk-forward backtest this
            reversal rule won <b>68.5%</b> at +10 days (+6.2% avg gross, <b>+5.1% net of commission</b>); Grade A won ~<b>82%</b>.
            It buys a confirmed bottom in a mean-reverting market — the strongest measured edge in the system.
            <div className="mt-1.5 text-amber-300/70">
              📋 Exit plan: <b>−10% stop</b> (wider than a breakout&apos;s — this entry is a falling knife by design,
              and a −7% stop shook out recoveries), <b>+25% target</b>, or exit after ~<b>20 trading days</b> —
              the edge is realized by +10 to +20 days.
            </div>
            <div className="mt-1.5 text-amber-300/70">⚠️ Edge case: in a sustained market downtrend it weakens (2023/2025 were poor). Don&apos;t average down.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
