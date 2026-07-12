'use client';

/**
 * FullAnalysisModal — opens the COMPLETE manual analysis for one ticker in an
 * overlay (breakout verdict, 60-day score history, fundamentals, legacy score
 * engine, and the full chart analysis). Used by the Rebounds page so clicking a
 * candidate shows exactly what the /analyze page shows, without leaving the list.
 */

import { useEffect } from 'react';
import { X } from 'lucide-react';
import ManualAnalysisView from './ManualAnalysisView';

interface Props {
  apiUrl: string;
  ticker: string;
  onClose: () => void;
}

export default function FullAnalysisModal({ apiUrl, ticker, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/75 p-2 sm:p-4 overflow-y-auto" onClick={onClose}>
      <div
        className="bg-gray-900 rounded-lg shadow-2xl border border-green-800/40 w-full max-w-[1200px] my-4 font-mono"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between sticky top-0 bg-gray-900 z-10 rounded-t-lg">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-2xl font-bold text-green-400">{ticker.toUpperCase()}</h2>
            <span className="text-xs text-gray-500 border border-green-800/60 rounded px-1.5 py-0.5">
              Full Analysis
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white" title="Close (Esc)">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="p-4 sm:p-6">
          <ManualAnalysisView apiUrl={apiUrl} ticker={ticker} />
        </div>
      </div>
    </div>
  );
}
