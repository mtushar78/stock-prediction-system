'use client';

/**
 * DataFreshnessBadge — "how old is the data behind every verdict on this page?"
 *
 * Every signal, grade, and verdict in the app is computed from the newest
 * OHLCV bar in the DB. If the scraper lags, every page silently shows stale
 * conclusions (a pattern that has since broken out, failed, or expired).
 * This badge makes that impossible to miss: green when current, red with a
 * days-old count when not.
 */

import { Database } from 'lucide-react';
import { SystemStatus } from '../types';

export default function DataFreshnessBadge({ systemStatus }: { systemStatus: SystemStatus | null }) {
  const date = systemStatus?.last_update ? String(systemStatus.last_update).slice(0, 10) : null;
  const age = systemStatus?.data_age_days ?? null;
  const stale = systemStatus?.data_stale === true;

  const cls = !date
    ? 'text-gray-500'
    : stale
    ? 'text-red-400'
    : 'text-green-500';

  return (
    <div
      className={`bg-gray-800 px-3 py-1.5 rounded border ${
        stale ? 'border-red-700 animate-pulse' : 'border-gray-700'
      }`}
      title={
        stale
          ? `Price data is ${age} days old — every signal and verdict on this page was computed on ${date}, not today's prices. Run a data update before acting on anything.`
          : 'Age of the newest price bar — all signals/verdicts are computed from this data.'
      }
    >
      <span className="text-gray-400 text-[10px] block flex items-center gap-1">
        <Database className="w-2.5 h-2.5" /> DATA
      </span>
      <span className={`font-bold text-sm whitespace-nowrap ${cls}`}>
        {date ?? '—'}
        {age != null && (
          <span className={`ml-1 text-[10px] font-normal ${stale ? 'text-red-300' : 'text-gray-500'}`}>
            {age === 0 ? 'today' : age === 1 ? '1d old' : `${age}d old${stale ? ' ⚠' : ''}`}
          </span>
        )}
      </span>
    </div>
  );
}
