'use client';

import { History, ChevronLeft, ChevronRight, Radio } from 'lucide-react';

interface Props {
  dates: string[];          // trading days, newest-first
  value: string | null;     // selected historical date, null = live
  loading: boolean;
  error: string | null;
  onPick: (date: string) => void;
  onLive: () => void;
}

/**
 * Time-machine bar: replay any past trading day's signals and step forward
 * day-by-day to watch how they played out. dates[] is newest-first, so a
 * smaller index = a more recent day → "Next" (forward in time) = idx-1.
 */
export default function DateReplayBar({ dates, value, loading, error, onPick, onLive }: Props) {
  const idx = value ? dates.indexOf(value) : -1;
  const newer = idx > 0 ? dates[idx - 1] : null;                       // forward in time
  const older = idx >= 0 && idx < dates.length - 1 ? dates[idx + 1] : null; // back in time
  const minDate = dates.length ? dates[dates.length - 1] : undefined;
  const maxDate = dates.length ? dates[0] : undefined;

  return (
    <div className={`mb-4 rounded border p-3 ${value ? 'bg-amber-900/20 border-amber-600' : 'bg-gray-800/50 border-gray-700'}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <History className={`w-4 h-4 ${value ? 'text-amber-400' : 'text-gray-400'}`} />
        <span className={value ? 'text-amber-300 font-bold' : 'text-gray-300 font-bold'}>
          {value ? 'REPLAY MODE' : 'Time Machine'}
        </span>

        <button
          disabled={!older || loading}
          onClick={() => older && onPick(older)}
          className="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-30 flex items-center gap-1"
          title="Previous trading day (back in time)"
        ><ChevronLeft className="w-3 h-3" /> Prev</button>

        <input
          type="date"
          value={value || maxDate || ''}
          min={minDate}
          max={maxDate}
          disabled={loading}
          onChange={(e) => e.target.value && onPick(e.target.value)}
          className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-gray-100"
          title="Pick any past trading day"
        />

        <button
          disabled={!newer || loading}
          onClick={() => newer && onPick(newer)}
          className="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-30 flex items-center gap-1"
          title="Next trading day (forward in time)"
        >Next <ChevronRight className="w-3 h-3" /></button>

        {value && (
          <button
            onClick={onLive}
            className="px-3 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white flex items-center gap-1"
            title="Return to today's live signals"
          ><Radio className="w-3 h-3" /> Back to Live</button>
        )}

        {loading && (
          <span className="text-amber-400 animate-pulse">
            computing {value}… (first view of a day takes ~1 min, then instant)
          </span>
        )}
        {!loading && error && <span className="text-red-400">{error}</span>}
      </div>

      {value && !loading && !error && (
        <div className="mt-2 text-xs text-amber-200/80">
          Showing the signals the system would have given on <b>{value}</b> (computed with only the data
          available that day — no hindsight). Use <b>Next ▶</b> to step forward and watch how they played out.
        </div>
      )}
    </div>
  );
}
