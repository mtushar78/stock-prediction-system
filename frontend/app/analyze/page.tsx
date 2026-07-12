'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import ManualAnalysisView from '../components/ManualAnalysisView';

// API Base URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AnalyzeTickerPage() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [tickerInput, setTickerInput] = useState('');
  const [loadingTickers, setLoadingTickers] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The ticker actually submitted for analysis (drives ManualAnalysisView).
  const [submittedTicker, setSubmittedTicker] = useState<string | null>(null);

  // Fetch tickers for datalist
  useEffect(() => {
    const load = async () => {
      try {
        setLoadingTickers(true);
        const res = await axios.get<string[]>(`${API_URL}/api/tickers`);
        setTickers(res.data || []);
      } catch (e) {
        console.error(e);
        setTickers([]);
      } finally {
        setLoadingTickers(false);
      }
    };
    load();
  }, []);

  const normalizedTicker = useMemo(() => tickerInput.trim().toUpperCase(), [tickerInput]);

  const analyze = () => {
    setError(null);
    if (!normalizedTicker) {
      setError('Please select / type a ticker first.');
      setSubmittedTicker(null);
      return;
    }
    setSubmittedTicker(normalizedTicker);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8 font-mono">
      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap border-b border-gray-700 pb-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-green-400">Manual Ticker Analysis</h1>
          <p className="text-gray-500 text-sm">Pick any stock from DB or type manually. See every step of the calculation.</p>
        </div>

        <Link
          href="/"
          className="bg-gray-800 hover:bg-gray-700 border border-gray-700 px-4 py-2 rounded text-sm transition"
        >
          ← Back to Dashboard
        </Link>
      </div>

      {/* Upper section: select/search */}
      <section className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
        <h2 className="text-lg font-bold mb-4 text-blue-300">Select Stock</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          <div className="md:col-span-2">
            <label className="block text-xs text-gray-400 mb-2">Ticker (dropdown + autocomplete)</label>
            <input
              className="w-full bg-gray-950 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500"
              list="tickers"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') analyze(); }}
              placeholder={loadingTickers ? 'Loading tickers…' : 'Type e.g. GP or click to choose'}
            />
            <datalist id="tickers">
              {tickers.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
            <div className="text-xs text-gray-600 mt-2">
              {tickers.length > 0 ? `Loaded ${tickers.length} tickers.` : 'No tickers loaded yet.'}
            </div>
          </div>

          <button
            onClick={analyze}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-400 px-4 py-2 rounded font-bold transition"
          >
            Analyze
          </button>
        </div>

        {error && <div className="mt-4 text-sm text-red-300">❌ {error}</div>}
      </section>

      {/* Result section */}
      <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        {!submittedTicker && <div className="text-gray-600 text-sm">Select a ticker and click Analyze.</div>}
        {submittedTicker && <ManualAnalysisView apiUrl={API_URL} ticker={submittedTicker} />}
      </section>
    </div>
  );
}
