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
import { Activity, RefreshCw, TrendingUp } from 'lucide-react';
import ChartScope from '../components/ChartScope';
import ChartDetailModal from '../components/ChartDetailModal';
import { SystemStatus } from '../types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ChartAnalysisPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

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

  return (
    <main className="min-h-screen bg-gray-900 text-white p-4 sm:p-6 lg:p-8">
      <header className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-700 pb-4 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-purple-300 flex items-center gap-2">
            <Activity className="w-8 h-8" /> Chart Analyst
          </h1>
          <p className="text-gray-500 text-sm">
            Independent second opinion · classical candlestick patterns + chart context
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
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded flex items-center gap-2 transition text-sm"
            title="Force refresh"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </header>

      <ChartScope
        key={refreshKey}
        apiUrl={API_URL}
        onRowClick={(ticker) => setActiveTicker(ticker)}
      />

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
