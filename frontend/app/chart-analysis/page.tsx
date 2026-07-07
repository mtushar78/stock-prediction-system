'use client';

/**
 * /chart-analysis — dedicated route for the candlestick-pattern engine.
 *
 * Kept fully separate from the main dashboard so the two scoring
 * methodologies remain visually and structurally independent. Same
 * data fetching pattern as the rest of the app (axios, 60s poll).
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import { Activity, RefreshCw, TrendingUp, Search, Crosshair, CandlestickChart, GraduationCap } from 'lucide-react';
import ChartScope from '../components/ChartScope';
import PatternScope from '../components/PatternScope';
import ChartDetailModal from '../components/ChartDetailModal';
import DataFreshnessBadge from '../components/DataFreshnessBadge';
import TutorialView from '../components/TutorialView';
import { TUTORIAL_ORDER } from '../tutorials';
import { SystemStatus } from '../types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ChartAnalysisPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [tickers, setTickers] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [searchError, setSearchError] = useState<string | null>(null);
  const [view, setView] = useState<'patterns' | 'candles' | 'tutorial'>('patterns');
  const [tutorialCode, setTutorialCode] = useState<string>(TUTORIAL_ORDER[0]);

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await axios.get<SystemStatus>(`${API_URL}/`);
        if (!cancelled) setSystemStatus(res.data);
      } catch {
        /* non-fatal */
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 60000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Load the autocomplete ticker list once
  useEffect(() => {
    let cancelled = false;
    axios
      .get<string[]>(`${API_URL}/api/tickers`)
      .then((res) => {
        if (!cancelled) setTickers(res.data || []);
      })
      .catch(() => {
        /* non-fatal */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submitSearch = () => {
    const t = (searchInput || '').trim().toUpperCase();
    if (!t) return;
    // Open the modal — the modal itself fetches the chart analysis and
    // will surface a 404 if the ticker truly has no usable history.
    setSearchError(null);
    setActiveTicker(t);
  };

  return (
    <main className="min-h-screen bg-gray-900 text-white p-4 sm:p-6 lg:p-8">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-purple-300 flex items-center gap-2">
            <Activity className="w-8 h-8" /> Chart Analyst
          </h1>
          <p className="text-gray-500 text-sm">
            Independent second opinion · Bulkowski chart patterns + candlestick context
          </p>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <nav className="flex gap-1 text-sm">
            <Link
              href="/"
              className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition flex items-center gap-1.5"
            >
              <TrendingUp className="w-4 h-4" /> Dashboard
            </Link>
            <Link
              href="/chart-analysis"
              className="px-3 py-1.5 rounded bg-purple-700 text-white border border-purple-600 flex items-center gap-1.5"
            >
              <Activity className="w-4 h-4" /> Chart Analyst
            </Link>
            <Link
              href="/analyze"
              className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition"
            >
              Manual Analyze
            </Link>
          </nav>
          <div className="bg-gray-800 px-3 py-1.5 rounded border border-gray-700">
            <span className="text-gray-400 text-[10px] block">SYSTEM</span>
            <span
              className={`font-bold text-sm ${
                systemStatus?.status === 'ONLINE' ? 'text-green-500' : 'text-red-500'
              }`}
            >
              ● {systemStatus?.status || 'LOADING'}
            </span>
          </div>
          <DataFreshnessBadge systemStatus={systemStatus} />
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded flex items-center gap-2 transition text-sm"
            title="Force refresh"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </header>

      {/* Stale-data kill-switch banner: if the newest bar is old, every row,
          grade and verdict below is old too — say it before the user reads them. */}
      {systemStatus?.data_stale && (
        <div className="mb-4 bg-red-950/70 border border-red-600 text-red-100 rounded-lg p-3 text-sm">
          <b>⚠ Price data is {systemStatus.data_age_days} days old (last bar {String(systemStatus.last_update).slice(0, 10)}).</b>{' '}
          Every setup, grade and verdict on this page was computed on that data — patterns may have broken
          out, failed or expired since. Update the data before acting on anything here.
        </div>
      )}

      <section className="mb-4 bg-gray-800 border border-gray-700 rounded-lg p-4">
        <div className="flex flex-col sm:flex-row gap-2 items-start sm:items-center">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Search className="w-4 h-4 text-purple-300" />
            <span>Search any ticker:</span>
          </div>
          <input
            list="chart-analysis-tickers"
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setSearchError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitSearch();
            }}
            placeholder="e.g. SHAHJABANK"
            className="bg-gray-900 border border-gray-700 focus:border-purple-500 outline-none rounded px-3 py-1.5 text-sm text-white w-full sm:w-72 placeholder-gray-600"
          />
          <datalist id="chart-analysis-tickers">
            {tickers.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <button
            onClick={submitSearch}
            disabled={!searchInput.trim()}
            className="px-3 py-1.5 rounded bg-purple-700 hover:bg-purple-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm transition"
          >
            Analyze chart
          </button>
          {searchInput && tickers.length > 0 && !tickers.includes(searchInput.trim().toUpperCase()) && (
            <span className="text-xs text-yellow-400">Unknown ticker — will still try</span>
          )}
          {searchError && <span className="text-xs text-red-300">{searchError}</span>}
          <div className="text-[11px] text-gray-500 sm:ml-auto">
            Search works even for tickers not in today&apos;s pattern list.
          </div>
        </div>
      </section>

      {/* View toggle: multi-week chart patterns (Bulkowski) vs candlesticks */}
      <div className="flex gap-1 mb-3 text-sm">
        <button
          onClick={() => setView('patterns')}
          className={`px-3 py-1.5 rounded flex items-center gap-1.5 border transition ${
            view === 'patterns'
              ? 'bg-cyan-700 text-white border-cyan-600'
              : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700'
          }`}
        >
          <Crosshair className="w-4 h-4" /> Chart patterns
        </button>
        <button
          onClick={() => setView('candles')}
          className={`px-3 py-1.5 rounded flex items-center gap-1.5 border transition ${
            view === 'candles'
              ? 'bg-purple-700 text-white border-purple-600'
              : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700'
          }`}
        >
          <CandlestickChart className="w-4 h-4" /> Candlesticks
        </button>
        <button
          onClick={() => setView('tutorial')}
          className={`px-3 py-1.5 rounded flex items-center gap-1.5 border transition ${
            view === 'tutorial'
              ? 'bg-indigo-700 text-white border-indigo-600'
              : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-700'
          }`}
        >
          <GraduationCap className="w-4 h-4" /> Tutorial
        </button>
      </div>

      {view !== 'tutorial' && (
        <div className="mb-4 bg-amber-950/25 border border-amber-700/50 rounded-lg p-3 text-xs text-amber-200/90 leading-relaxed">
          <b className="text-amber-200">📊 Read this as context, not a buy/sell list.</b>{' '}
          A dense DSE validation (24,781 point-in-time samples, 2022–2026) found that <b>confirmed bullish
          chart patterns returned the same as a random stock</b> (−0.2% before costs, ≈−1.0% after) — the
          pattern layer carries no tradable edge here, and it does not improve in any market regime. Patterns
          feel like they work in a strong market because <i>everything</i> rises. Use this page to <b>read structure,
          support/resistance, and risk</b>, and to learn the shapes — then take actual buys from the{' '}
          <Link href="/" className="underline hover:text-amber-100">Reversals list</Link>, the one signal with a
          validated net edge. Each pattern below shows its real DSE-measured return, not just the US textbook target.
        </div>
      )}

      {view === 'patterns' && (
        <PatternScope
          key={`p${refreshKey}`}
          apiUrl={API_URL}
          onRowClick={(ticker) => setActiveTicker(ticker)}
          onLearn={(code) => {
            setTutorialCode(code);
            setView('tutorial');
          }}
        />
      )}
      {view === 'candles' && (
        <ChartScope key={`c${refreshKey}`} apiUrl={API_URL} onRowClick={(ticker) => setActiveTicker(ticker)} />
      )}
      {view === 'tutorial' && (
        <section className="bg-gray-800 rounded-lg p-6 border border-indigo-800/40 mb-4">
          <TutorialView activeCode={tutorialCode} onSelect={setTutorialCode} />
        </section>
      )}

      {activeTicker && (
        <ChartDetailModal
          apiUrl={API_URL}
          ticker={activeTicker}
          onClose={() => setActiveTicker(null)}
        />
      )}
    </main>
  );
}
