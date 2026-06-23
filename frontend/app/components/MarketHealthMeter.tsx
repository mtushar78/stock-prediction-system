'use client';

import { Activity } from 'lucide-react';

export interface MarketHealth {
  date?: string | null;
  breadth_pct?: number | null;
  above?: number;
  total?: number;
  label?: string;
  healthy?: boolean;
}

/** Market-regime gauge: % of liquid stocks above their 50-day average.
 *  Breakouts fire PRIME when this is HEALTHY (the regime filter from the study). */
export default function MarketHealthMeter({ data, asOf }: { data: MarketHealth | null; asOf?: string | null }) {
  if (!data || data.breadth_pct == null) return null;
  const pct = data.breadth_pct;
  const label = data.label || 'UNKNOWN';
  const bar = label === 'HEALTHY' ? 'bg-emerald-500' : label === 'MIXED' ? 'bg-yellow-500' : 'bg-red-500';
  const txt = label === 'HEALTHY' ? 'text-emerald-300' : label === 'MIXED' ? 'text-yellow-300' : 'text-red-300';
  const note = label === 'HEALTHY' ? 'Good for breakouts — today’s breakouts are PRIME setups.'
    : label === 'MIXED' ? 'Mixed conditions — breakouts still work, but be selective.'
    : 'Weak market — breakouts fail more often here. Trade light / wait.';

  return (
    <div className="mb-4 bg-gray-800/50 border border-gray-700 rounded p-3">
      <div className="flex items-center justify-between flex-wrap gap-2 text-sm mb-2">
        <span className="flex items-center gap-2 font-bold text-gray-200">
          <Activity className="w-4 h-4" /> Market Health
          {asOf && <span className="text-xs text-amber-300/70">(as of {asOf})</span>}
        </span>
        <span className={`font-bold ${txt}`}>{pct}% · {label}</span>
      </div>
      <div className="w-full h-2 bg-gray-900 rounded-full overflow-hidden">
        <div className={`h-full ${bar} transition-all`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
      </div>
      <div className="text-xs text-gray-500 mt-1.5">
        {data.above} of {data.total} liquid stocks are above their 50-day average. {note}
      </div>
    </div>
  );
}
