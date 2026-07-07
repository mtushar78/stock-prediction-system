'use client';

import { Activity, Sprout, ShieldCheck, BellRing } from 'lucide-react';

export interface MarketHealth {
  date?: string | null;
  breadth_pct?: number | null;
  above?: number;
  total?: number;
  label?: string;
  healthy?: boolean;
  season?: 'REVERSAL' | 'PRESERVATION' | null;
  season_note?: string | null;
  prev_season?: 'REVERSAL' | 'PRESERVATION' | null;
  season_changed?: boolean;
}

/** Market-regime gauge: % of liquid stocks above their 50-day average.
 *
 *  SEASON is the master switch (weekly-system + regime studies, 2026-07):
 *  the reversal signal — the ONLY validated net-of-cost edge on DSE — pays in
 *  WEAK tape (breadth <45) and is ≈0 in STRONG tape (breadth >=45). So we frame
 *  the market by SEASON, not by an (inverted) "good for buying" health score. */
export default function MarketHealthMeter({ data, asOf }: { data: MarketHealth | null; asOf?: string | null }) {
  if (!data || data.breadth_pct == null) return null;
  const pct = data.breadth_pct;
  const season = data.season || (pct < 45 ? 'REVERSAL' : 'PRESERVATION');
  const isReversal = season === 'REVERSAL';

  // Reversal season = opportunity (green); Preservation = caution/patience (amber).
  const bar = isReversal ? 'bg-emerald-500' : 'bg-amber-500';
  const txt = isReversal ? 'text-emerald-300' : 'text-amber-300';
  const ring = isReversal ? 'border-emerald-600/60 bg-emerald-950/20' : 'border-amber-600/50 bg-amber-950/20';
  const title = isReversal ? 'REVERSAL SEASON' : 'PRESERVATION SEASON';
  const Icon = isReversal ? Sprout : ShieldCheck;
  const note = data.season_note || (isReversal
    ? 'Deep-oversold bounces have a real net edge in weak tape. Trade reversal fires — this is where the money is made.'
    : 'The reversal edge is ≈0 when the market is this strong. Ride winners, build the watchlist, do NOT force new buys.');

  return (
    <div className={`mb-4 border rounded p-3 ${ring}`}>
      {/* Season-just-flipped bell */}
      {data.season_changed && (
        <div className="mb-2 flex items-center gap-2 text-sm font-bold text-yellow-200 bg-yellow-900/30 border border-yellow-600/60 rounded px-2 py-1.5">
          <BellRing className="w-4 h-4 shrink-0" />
          Season just changed: {data.prev_season} → {season} today.
          {isReversal ? ' Reversal hunting is ON.' : ' Time to protect gains, not chase.'}
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-2 text-sm mb-2">
        <span className={`flex items-center gap-2 font-bold ${txt}`}>
          <Icon className="w-4 h-4" /> {title}
          {asOf && <span className="text-xs text-amber-300/70">(as of {asOf})</span>}
        </span>
        <span className="flex items-center gap-2 text-gray-300">
          <Activity className="w-3.5 h-3.5 text-gray-500" />
          <span className="font-bold">{pct}%</span>
          <span className="text-xs text-gray-500">breadth</span>
        </span>
      </div>

      <div className="w-full h-2 bg-gray-900 rounded-full overflow-hidden relative">
        {/* 45% season line */}
        <div className="absolute top-0 bottom-0 w-px bg-gray-500/70" style={{ left: '45%' }} />
        <div className={`h-full ${bar} transition-all`} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
      </div>

      <div className="text-xs text-gray-400 mt-1.5">
        {data.above} of {data.total} liquid stocks are above their 50-day average
        <span className="text-gray-600"> · season flips at 45% breadth</span>. {note}
      </div>
    </div>
  );
}
