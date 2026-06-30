'use client';

import { Signal } from '../types';
import { X, Flame, Check, Minus } from 'lucide-react';

interface Props {
  signal: Signal;
  onClose: () => void;
}

const heatColor = (level?: string) =>
  level === 'EXTREME' ? 'bg-red-600 text-white'
  : level === 'HOT' ? 'bg-orange-600 text-white'
  : 'bg-amber-700 text-amber-100';

const num = (n: number | undefined | null, d = 1) =>
  typeof n === 'number' ? n.toLocaleString(undefined, { maximumFractionDigits: d }) : '—';

/** Why a stock is flagged overheated — the heat level + each danger axis vs its threshold. */
export default function OverheatedDetailModal({ signal, onClose }: Props) {
  const c = signal.OverheatedChecks || {};
  const rsiT = c.rsi_thresh ?? 75, retT = c.ret20_thresh ?? 50, extT = c.ext20_thresh ?? 25;

  const rows: { hit: boolean; label: string; detail: string; rule: string }[] = [
    {
      hit: typeof c.rsi === 'number' && c.rsi >= rsiT,
      label: 'Overbought', detail: `RSI is ${num(c.rsi, 0)}`, rule: `danger ≥ ${rsiT}`,
    },
    {
      hit: typeof c.ret20 === 'number' && c.ret20 >= retT,
      label: 'Parabolic run-up', detail: `Up ${num(c.ret20)}% over the last 20 days`, rule: `danger ≥ +${retT}%`,
    },
    {
      hit: typeof c.ext20 === 'number' && c.ext20 >= extT,
      label: 'Stretched above its average', detail: `${num(c.ext20)}% above its 20-day average`, rule: `danger ≥ +${extT}%`,
    },
    {
      hit: typeof c.rvol === 'number' && c.rvol >= 2,
      label: 'Climax volume', detail: `Volume ${num(c.rvol)}× the 20-day average`, rule: 'distribution tell ≥ 2×',
    },
    {
      hit: c.new_high === true,
      label: 'At a new high', detail: c.new_high ? 'Printing a fresh high — blow-off risk' : 'Not at a new high', rule: 'exhaustion top tell',
    },
  ];

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-gray-900 border border-red-700 rounded-xl max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-gray-700 sticky top-0 bg-gray-900">
          <div className="flex items-center gap-2">
            <Flame className="w-5 h-5 text-red-400" />
            <span className="text-lg font-bold text-red-300">{signal.Ticker}</span>
            <span className={`text-xs rounded px-2 py-0.5 font-bold ${heatColor(c.heat_level)}`}>
              {c.heat_level ?? 'HOT'} · heat {c.heat_score ?? '?'}/100
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-4">
          <div className="mb-3 text-xs text-red-200/90 bg-red-900/20 border border-red-800/50 rounded-lg p-3">
            <b className="text-red-300">⚠️ Elevated pullback risk — not a sell command.</b> Stocks in this danger zone
            historically fall ≥20% about <b>26%</b> of the time (vs ~15% normally). Strong stocks can stay hot a while,
            so use this to <b>avoid buying the top</b> and to <b>take profit</b> on names you already hold — not to short blindly.
          </div>

          <p className="text-sm text-gray-400 mb-3">Which danger signals are firing:</p>
          <div className="space-y-2">
            {rows.map((r) => (
              <div key={r.label} className="flex gap-2.5 bg-gray-800/60 border border-gray-700 rounded-lg p-2.5">
                <span className={`mt-0.5 shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${r.hit ? 'bg-red-600' : 'bg-gray-600'}`}>
                  {r.hit ? <Check className="w-3.5 h-3.5 text-white" /> : <Minus className="w-3.5 h-3.5 text-white" />}
                </span>
                <div>
                  <div className="text-sm font-bold text-gray-100">{r.label}</div>
                  <div className="text-sm text-gray-300">{r.detail}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{r.rule}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 text-xs text-gray-500">
            Reverse-engineered from how DSE tops form (22-decliner study, <code>docs/WINNER_ANATOMY.md</code>): the chart
            predicts <b>falls</b> far more reliably than rises, so avoiding overheated tops is the dependable edge.
          </div>
        </div>
      </div>
    </div>
  );
}
