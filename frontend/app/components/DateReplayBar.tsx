'use client';

import { useState, useEffect } from 'react';
import { History, ChevronLeft, ChevronRight, Radio, Play, Check, Zap } from 'lucide-react';
import MiniCalendar from './MiniCalendar';

interface Props {
  dates: string[];          // trading days, newest-first
  analyzed: string[];       // dates already cached (instant replay)
  viewing: string | null;   // the date currently analyzed/shown (null = live)
  loading: boolean;
  error: string | null;
  onAnalyze: (date: string) => void;
  onLive: () => void;
}

/**
 * Time-machine bar. Picking a date / stepping Prev-Next only CHANGES the
 * pending date — nothing runs until "Analyze" is pressed (the compute is slow).
 * dates[] is newest-first, so older = a later array index, newer = earlier.
 */
export default function DateReplayBar({ dates, analyzed, viewing, loading, error, onAnalyze, onLive }: Props) {
  const maxDate = dates.length ? dates[0] : undefined;
  const minDate = dates.length ? dates[dates.length - 1] : undefined;
  const analyzedSet = new Set(analyzed);

  const [pending, setPending] = useState<string>(viewing || maxDate || '');

  // Seed the picker once dates arrive (or follow the viewed date).
  useEffect(() => {
    if (!pending && (viewing || maxDate)) setPending(viewing || maxDate || '');
  }, [viewing, maxDate]); // eslint-disable-line react-hooks/exhaustive-deps

  // Nearest trading day strictly older / newer than `pending` (works even if
  // `pending` is a non-trading day picked from the calendar).
  const olderDate = dates.find((d) => d < pending) || null;          // back in time
  const newerList = dates.filter((d) => d > pending);
  const newerDate = newerList.length ? newerList[newerList.length - 1] : null; // forward in time

  const isTradingDay = dates.includes(pending);
  const isCached = analyzedSet.has(pending);
  const canAnalyze = !!pending && isTradingDay && !loading;

  return (
    <div className={`mb-4 rounded border p-3 ${viewing ? 'bg-amber-900/20 border-amber-600' : 'bg-gray-800/50 border-gray-700'}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <History className={`w-4 h-4 ${viewing ? 'text-amber-400' : 'text-gray-400'}`} />
        <span className={viewing ? 'text-amber-300 font-bold' : 'text-gray-300 font-bold'}>Time Machine</span>
        <span className="text-gray-600">·</span>

        <button
          disabled={!olderDate || loading}
          onClick={() => olderDate && setPending(olderDate)}
          className="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-30 flex items-center gap-1"
          title="Step the date back one trading day"
        ><ChevronLeft className="w-3 h-3" /> Prev</button>

        <MiniCalendar
          value={pending}
          min={minDate}
          max={maxDate}
          tradingDays={new Set(dates)}
          analyzedDays={analyzedSet}
          disabled={loading}
          onChange={setPending}
        />

        <button
          disabled={!newerDate || loading}
          onClick={() => newerDate && setPending(newerDate)}
          className="px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-30 flex items-center gap-1"
          title="Step the date forward one trading day"
        >Next <ChevronRight className="w-3 h-3" /></button>

        <button
          disabled={!canAnalyze}
          onClick={() => onAnalyze(pending)}
          className={`px-4 py-1 rounded text-white font-bold disabled:opacity-40 flex items-center gap-1 ${
            isCached ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-blue-600 hover:bg-blue-500'
          }`}
          title={isCached
            ? 'Already analyzed — loads instantly'
            : 'Run the analysis for the selected day (takes ~1 min the first time)'}
        >
          {isCached ? <Zap className="w-3 h-3" /> : <Play className="w-3 h-3" />}
          {isCached ? 'View · instant' : 'Analyze · ~1 min'}
        </button>

        {isTradingDay && (
          <span className={`text-[11px] px-1.5 py-0.5 rounded flex items-center gap-1 ${
            isCached ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-700'
                     : 'bg-gray-700 text-gray-400 border border-gray-600'}`}>
            {isCached ? <><Check className="w-3 h-3" /> analyzed</> : 'not analyzed'}
          </span>
        )}

        {viewing && (
          <button
            onClick={onLive}
            className="px-3 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white flex items-center gap-1"
            title="Return to today's live signals"
          ><Radio className="w-3 h-3" /> Back to Live</button>
        )}
      </div>

      <div className="mt-2 text-xs">
        {loading && (
          <span className="text-amber-400 animate-pulse">
            Analyzing {pending}… this takes ~1 minute the first time, then it&apos;s instant.
          </span>
        )}
        {!loading && error && <span className="text-red-400">{error}</span>}
        {!loading && !error && pending && !isTradingDay && (
          <span className="text-yellow-500">{pending} isn&apos;t a trading day — use Prev/Next to snap to one.</span>
        )}
        {!loading && !error && isTradingDay && viewing && (
          <span className="text-amber-200/80">
            Viewing <b>{viewing}</b> — signals as the system saw them that day. Press <b>Next ▶</b> then <b>Analyze</b> to step forward.
          </span>
        )}
        {!loading && !error && isTradingDay && !viewing && (
          <span className="text-gray-500">Pick a past trading day {analyzed.length > 0 && '(green = already analyzed) '}and press <b>Analyze</b>.</span>
        )}
      </div>
    </div>
  );
}
