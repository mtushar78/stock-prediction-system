'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import { DetailedTickerAnalysis, ScoreBreakdownItem, ScoreHistory } from '../types';
import BreakoutCriteria from '../components/BreakoutCriteria';

// API Base URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function Badge({ label, variant }: { label: string; variant: 'green' | 'yellow' | 'red' | 'gray' | 'blue' }) {
  const cls =
    variant === 'green'
      ? 'bg-green-900/30 border-green-700 text-green-300'
      : variant === 'yellow'
        ? 'bg-yellow-900/30 border-yellow-700 text-yellow-300'
        : variant === 'red'
          ? 'bg-red-900/30 border-red-700 text-red-300'
          : variant === 'blue'
            ? 'bg-blue-900/30 border-blue-700 text-blue-300'
            : 'bg-gray-800 border-gray-700 text-gray-300';
  return <span className={`inline-flex items-center px-2 py-1 text-xs border rounded ${cls}`}>{label}</span>;
}

function fmt(n: number | null | undefined, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return '-';
  return n.toFixed(digits);
}

function fmtInt(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return '-';
  return Math.round(n).toLocaleString();
}

function pointsColor(points: number) {
  if (points > 0) return 'text-green-400';
  if (points < 0) return 'text-red-400';
  return 'text-gray-400';
}

function BreakdownRow({ item }: { item: ScoreBreakdownItem }) {
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 border-b border-gray-800 py-2">
      <div className="flex items-center gap-2">
        <span className={`text-sm font-bold ${item.passed ? 'text-green-400' : 'text-gray-300'}`}>{item.passed ? '✅' : '❌'}</span>
        <div>
          <div className="text-sm text-gray-200">{item.name}</div>
          <div className="text-xs text-gray-500">{item.details}</div>
        </div>
      </div>
      <div className={`text-sm font-bold ${pointsColor(item.points)}`}>{item.points > 0 ? `+${item.points}` : `${item.points}`}</div>
    </div>
  );
}

function signalPill(sig: string) {
  const s = (sig || '').toUpperCase();
  const cls =
    s === 'BUY' || s === 'EARLY'
      ? 'bg-green-900/40 text-green-300 border-green-700'
      : s === 'WAIT' || s === 'WATCH'
        ? 'bg-yellow-900/30 text-yellow-300 border-yellow-700'
        : 'bg-gray-800 text-gray-400 border-gray-700';
  return <span className={`inline-block px-1.5 py-0.5 rounded border text-[11px] font-bold ${cls}`}>{s || '-'}</span>;
}

function ScoreHistoryTable({ history, loading }: { history: ScoreHistory | null; loading: boolean }) {
  const [pageSize, setPageSize] = useState<number>(20);
  const [page, setPage] = useState(0);

  // newest-first
  const rows = useMemo(() => (history?.history ? [...history.history].reverse() : []), [history]);
  const total = rows.length;
  // reset to first page whenever the data or page size changes
  useEffect(() => { setPage(0); }, [history, pageSize]);

  const perPage = pageSize >= total && total > 0 ? total : pageSize;
  const pageCount = Math.max(1, Math.ceil(total / perPage));
  const curPage = Math.min(page, pageCount - 1);
  const start = curPage * perPage;
  const visible = rows.slice(start, start + perPage);

  return (
    <div className="bg-gray-950 border border-gray-700 rounded p-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h3 className="font-bold text-indigo-300">📅 60-Day Score History (settled replay)</h3>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {total > 0 && <span>{total} days · newest first</span>}
          <label className="flex items-center gap-1">
            Show
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="bg-gray-900 border border-gray-700 rounded px-1.5 py-0.5 text-gray-200"
            >
              {[10, 20, 30, 60].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            per page
          </label>
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-3 italic">
        Day-by-day replay of MAIN score &amp; EarlyScore. Past days use settled volume; today&apos;s row
        reflects live/projected volume during market hours.
      </p>

      {loading && <div className="text-sm text-gray-500 py-4">Loading history…</div>}

      {!loading && (!history || !history.history?.length) && (
        <div className="text-sm text-gray-600 py-4">No history available.</div>
      )}

      {!loading && history && history.history?.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs whitespace-nowrap">
            <thead>
              <tr className="text-gray-500 border-b border-gray-700">
                <th className="py-2 pr-3">DATE</th>
                <th className="py-2 pr-3 text-right">CLOSE</th>
                <th className="py-2 pr-3 text-right">%CHG</th>
                <th className="py-2 pr-3 text-right">RVOL</th>
                <th className="py-2 pr-3 text-right">SCORE</th>
                <th className="py-2 pr-3">SIGNAL</th>
                <th className="py-2 pr-3 text-right">EARLY</th>
                <th className="py-2 pr-3">E-SIG</th>
                <th className="py-2 pr-3 text-right">LATE</th>
                <th className="py-2 pr-3 text-right">5D%</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.date} className="border-b border-gray-800/70 hover:bg-gray-800/40">
                  <td className="py-1.5 pr-3 text-gray-300">
                    {r.date}{r.is_intraday ? <span className="text-yellow-500 ml-1" title="Intraday / projected">●</span> : null}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-200">{fmt(r.close, 2)}</td>
                  <td className={`py-1.5 pr-3 text-right ${(r.price_change_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(r.price_change_pct ?? 0) >= 0 ? '+' : ''}{fmt(r.price_change_pct, 2)}
                  </td>
                  <td className={`py-1.5 pr-3 text-right ${(r.rvol ?? 0) >= 2 ? 'text-yellow-300 font-bold' : 'text-gray-300'}`}>
                    {fmt(r.rvol, 2)}x
                  </td>
                  <td className="py-1.5 pr-3 text-right font-bold text-gray-100">
                    {r.score}<span className="text-gray-600 font-normal"> ({r.raw_score})</span>
                  </td>
                  <td className="py-1.5 pr-3">{signalPill(r.signal)}</td>
                  <td className="py-1.5 pr-3 text-right font-bold text-gray-100">{r.early_score}</td>
                  <td className="py-1.5 pr-3">{signalPill(r.early_signal)}</td>
                  <td className={`py-1.5 pr-3 text-right ${r.late_entry_pts < 0 ? 'text-red-400' : 'text-gray-600'}`}>
                    {r.late_entry_pts < 0 ? r.late_entry_pts : '0'}
                  </td>
                  <td className={`py-1.5 pr-3 text-right ${(r.return_5d_pct ?? 0) >= 0 ? 'text-gray-400' : 'text-red-400'}`}>
                    {r.return_5d_pct == null ? '-' : `${r.return_5d_pct >= 0 ? '+' : ''}${fmt(r.return_5d_pct, 1)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {pageCount > 1 && (
            <div className="flex items-center justify-between mt-3 text-xs">
              <span className="text-gray-600">
                Showing {start + 1}–{Math.min(start + perPage, total)} of {total}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={curPage === 0}
                  className="px-2 py-1 rounded bg-gray-800 border border-gray-700 hover:bg-gray-700 disabled:opacity-30"
                >‹ Prev</button>
                <span className="text-gray-400 px-2">Page {curPage + 1} / {pageCount}</span>
                <button
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  disabled={curPage >= pageCount - 1}
                  className="px-2 py-1 rounded bg-gray-800 border border-gray-700 hover:bg-gray-700 disabled:opacity-30"
                >Next ›</button>
              </div>
            </div>
          )}
          <div className="text-[11px] text-gray-600 mt-2">
            SCORE = MAIN score (raw in parens); BUY ≥ 50. EARLY ≥ 60 = pre-breakout window.
            LATE = late-entry penalty. <span className="text-yellow-500">●</span> = intraday/projected row.
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalyzeTickerPage() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [tickerInput, setTickerInput] = useState('');
  const [loadingTickers, setLoadingTickers] = useState(false);
  const [loadingAnalyze, setLoadingAnalyze] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DetailedTickerAnalysis | null>(null);
  const [history, setHistory] = useState<ScoreHistory | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

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

  const analyze = async () => {
    setError(null);
    setResult(null);
    setHistory(null);
    if (!normalizedTicker) {
      setError('Please select / type a ticker first.');
      return;
    }
    setLoadingAnalyze(true);
    setLoadingHistory(true);
    // Detailed analysis (current snapshot) + 60-day score history in parallel.
    const analyzePromise = axios
      .post<DetailedTickerAnalysis>(`${API_URL}/api/analyze-ticker`, { ticker: normalizedTicker })
      .then((res) => setResult(res.data))
      .catch((err: unknown) => {
        const e = err as { response?: { data?: { detail?: string } }; message?: string };
        setError(e.response?.data?.detail || e.message || 'Analyze failed');
      })
      .finally(() => setLoadingAnalyze(false));

    const historyPromise = axios
      .get<ScoreHistory>(`${API_URL}/api/score-history/${normalizedTicker}?days=60`)
      .then((res) => setHistory(res.data))
      .catch(() => setHistory(null))
      .finally(() => setLoadingHistory(false));

    await Promise.allSettled([analyzePromise, historyPromise]);
  };

  const statusBadge = useMemo(() => {
    if (!result) return null;
    if (result.status === 'error') return <Badge label="ERROR" variant="red" />;
    if (result.status === 'filtered') return <Badge label="FILTERED" variant="yellow" />;
    return <Badge label="OK" variant="green" />;
  }, [result]);

  const breakoutBadge = useMemo(() => {
    if (!result?.breakout) return null;
    return result.breakout.is_breakout
      ? <Badge label="🚀 BREAKOUT" variant="blue" />
      : <Badge label="Not a breakout" variant="gray" />;
  }, [result]);

  const [legacy, setLegacy] = useState(false);

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
            disabled={loadingAnalyze}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-400 px-4 py-2 rounded font-bold transition"
          >
            {loadingAnalyze ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>

        {error && <div className="mt-4 text-sm text-red-300">❌ {error}</div>}
      </section>

      {/* Result section */}
      <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-lg font-bold text-green-300">Result</h2>
            <div className="text-xs text-gray-500 mt-1">Detailed breakdown for the selected ticker</div>
          </div>
          <div className="flex items-center gap-2">
            {statusBadge}
            {breakoutBadge}
          </div>
        </div>

        {!result && <div className="text-gray-600 text-sm mt-6">Select a ticker and click Analyze.</div>}

        {result && (
          <div className="mt-6 space-y-6">
            {/* Top summary */}
            <div className="bg-gray-950 border border-gray-700 rounded p-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-xs text-gray-500">Ticker</div>
                  <div className="text-xl font-bold text-green-400">{result.ticker}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Date</div>
                  <div className="text-sm text-gray-200">{result.meta?.analysis_date || '-'}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Market</div>
                  <div className="text-sm text-gray-200">
                    {result.meta?.is_market_open ? 'OPEN' : 'CLOSED'}{result.meta?.is_intraday ? ' (intraday snapshot)' : ''}
                  </div>
                </div>
              </div>

              {result.message && (
                <div className="mt-3 text-sm">
                  <span className="text-gray-400">Message:</span> <span className="text-yellow-300">{result.message}</span>
                </div>
              )}
            </div>

            {/* Breakout Analysis — the signal that matters (v9) */}
            {result.breakout && (
              <div className={`rounded p-4 border ${result.breakout.is_breakout ? 'bg-sky-950/40 border-sky-700' : 'bg-gray-950 border-gray-700'}`}>
                <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
                  <h3 className="font-bold text-sky-300">🚀 Breakout Analysis</h3>
                  {result.breakout.is_breakout
                    ? <Badge label="✓ BREAKOUT — on the buy list" variant="green" />
                    : <Badge label="✗ Not a breakout" variant="gray" />}
                </div>
                <p className="text-xs text-gray-500 mb-3 italic">
                  The only signal with a proven, regime-robust edge (backtested 2019–2026). All five rules
                  must pass. {result.breakout.is_breakout ? '' : 'The ✗ rows below are why it doesn’t qualify today.'}
                </p>
                <BreakoutCriteria checks={result.breakout.checks} fallbackPrice={result.indicators?.close ?? undefined} />
              </div>
            )}

            {/* 60-day score history */}
            <ScoreHistoryTable history={history} loading={loadingHistory} />

            {/* ---- LEGACY (collapsed) ---- */}
            <div className="border-t border-gray-700/60 pt-3">
              <button onClick={() => setLegacy((x) => !x)} className="text-xs text-gray-500 hover:text-gray-300">
                {legacy ? '▾ Hide' : '▸ Show'} legacy analysis (Score / Early / breakdown — low reliability)
              </button>
            </div>

            {legacy && (<>
            <div className="text-[11px] text-amber-300/70 bg-amber-900/10 border border-amber-800/40 rounded px-2 py-1">
              ⚠️ The Score/Early engine below was inversely related to forward returns in backtest — shown for reference only. Trade the breakout verdict above.
            </div>

            {/* Filters */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-gray-950 border border-gray-700 rounded p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-purple-300">Survival Filters</h3>
                  {result.filters?.survival?.passed ? <Badge label="PASSED" variant="green" /> : <Badge label="FAILED" variant="yellow" />}
                </div>

                <div className="mt-3 text-xs text-gray-500">Reason: {result.filters?.survival?.reason || '-'}</div>

                <div className="mt-4 space-y-3 text-sm">
                  {result.filters?.survival?.rules && (
                    <>
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-gray-200">Ghost Town</div>
                          <div className="text-xs text-gray-500">{result.filters.survival.rules.ghost_town.details}</div>
                        </div>
                        {result.filters.survival.rules.ghost_town.passed ? <Badge label="OK" variant="green" /> : <Badge label="BLOCK" variant="yellow" />}
                      </div>
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-gray-200">Price Stuck</div>
                          <div className="text-xs text-gray-500">{result.filters.survival.rules.price_stuck.details}</div>
                        </div>
                        {result.filters.survival.rules.price_stuck.passed ? <Badge label="OK" variant="green" /> : <Badge label="BLOCK" variant="yellow" />}
                      </div>
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-gray-200">Min Volume</div>
                          <div className="text-xs text-gray-500">{result.filters.survival.rules.min_volume.details}</div>
                        </div>
                        {result.filters.survival.rules.min_volume.passed ? <Badge label="OK" variant="green" /> : <Badge label="BLOCK" variant="yellow" />}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="bg-gray-950 border border-gray-700 rounded p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-cyan-300">Trend Filter (200 SMA)</h3>
                  {result.filters?.trend?.passed === false
                    ? <Badge label="DEEP DOWNTREND" variant="red" />
                    : result.filters?.trend?.close != null && result.filters?.trend?.sma_200 != null && result.filters.trend.close < result.filters.trend.sma_200
                      ? <Badge label="NEAR SMA" variant="yellow" />
                      : <Badge label="UPTREND" variant="green" />}
                </div>
                <div className="mt-3 text-xs text-gray-500">{result.filters?.trend?.reason || '-'}</div>

                <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-gray-900 border border-gray-800 rounded p-3">
                    <div className="text-xs text-gray-500">Close</div>
                    <div className="text-gray-100 font-bold">৳{fmt(result.filters?.trend?.close, 2)}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded p-3">
                    <div className="text-xs text-gray-500">SMA 200</div>
                    <div className="text-gray-100 font-bold">৳{fmt(result.filters?.trend?.sma_200, 2)}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Indicators */}
            <div className="bg-gray-950 border border-gray-700 rounded p-4">
              <h3 className="font-bold text-blue-300 mb-3">Indicators / Inputs</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Close</div>
                  <div className="font-bold">৳{fmt(result.indicators?.close, 2)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">RVOL</div>
                  <div className="font-bold text-yellow-400">{fmt(result.indicators?.rvol, 2)}x</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Avg Vol 20</div>
                  <div className="font-bold">{fmtInt(result.indicators?.avg_volume_20)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Today Vol</div>
                  <div className="font-bold">{fmtInt(result.indicators?.current_vol)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Projected Vol</div>
                  <div className="font-bold text-yellow-300">{result.meta?.is_market_open ? fmtInt(result.indicators?.projected_vol) : '-'}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Price Change %</div>
                  <div className="font-bold">{fmt(result.indicators?.price_change_pct, 2)}%</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">ATR (14)</div>
                  <div className="font-bold">{fmt(result.indicators?.atr, 2)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Daily Range %</div>
                  <div className="font-bold">{fmt(result.indicators?.daily_range_pct, 2)}%</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Close Position Ratio</div>
                  <div className="font-bold text-cyan-300">{fmt(result.indicators?.close_position_ratio, 4)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">OBV Slope (20d)</div>
                  <div className="font-bold">{fmt(result.indicators?.obv_slope_20, 2)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Price Slope (20d)</div>
                  <div className="font-bold">{fmt(result.indicators?.price_slope_20, 4)}</div>
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded p-3">
                  <div className="text-xs text-gray-500">Vol MA 3/10</div>
                  <div className="font-bold">{fmtInt(result.indicators?.vol_ma_3)} / {fmtInt(result.indicators?.vol_ma_10)}</div>
                </div>
              </div>
            </div>

            {/* Support/Resistance + Risk */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-gray-950 border border-gray-700 rounded p-4">
                <h3 className="font-bold text-emerald-300 mb-3">Support / Resistance</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Nearest Support</span>
                    <span className="font-bold text-green-400">৳{fmt(result.support_resistance?.nearest_support, 2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Nearest Resistance</span>
                    <span className="font-bold text-red-400">৳{fmt(result.support_resistance?.nearest_resistance, 2)}</span>
                  </div>
                  <div className="pt-2 border-t border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">All Support Levels</div>
                    <div className="text-xs text-gray-400 break-words">
                      {(result.support_resistance?.all_support_levels || []).length > 0
                        ? result.support_resistance?.all_support_levels.map((x) => fmt(x, 2)).join(', ')
                        : '-'}
                    </div>
                  </div>
                  <div className="pt-2 border-t border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">All Resistance Levels</div>
                    <div className="text-xs text-gray-400 break-words">
                      {(result.support_resistance?.all_resistance_levels || []).length > 0
                        ? result.support_resistance?.all_resistance_levels.map((x) => fmt(x, 2)).join(', ')
                        : '-'}
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gray-950 border border-gray-700 rounded p-4">
                <h3 className="font-bold text-orange-300 mb-3">Risk / Stop Loss / RR</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Stop from Support (support × 0.98)</span>
                    <span className="font-bold">৳{fmt(result.risk?.stop_from_support, 2)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Stop from ATR (close − 1.5×ATR)</span>
                    <span className="font-bold">৳{fmt(result.risk?.stop_from_atr, 2)}</span>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-gray-800">
                    <span className="text-gray-200 font-bold">Recommended Stop Loss</span>
                    <span className="font-bold text-yellow-300">৳{fmt(result.risk?.recommended_stop_loss, 2)}</span>
                  </div>

                  <div className="pt-2 border-t border-gray-800">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Reward:Risk</span>
                      {result.risk?.reward_risk?.valid ? (
                        <Badge
                          label={`${result.risk.reward_risk.ratio.toFixed(2)}:1${result.risk.reward_risk.recommended ? ' ✅' : ' ⚠️'}`}
                          variant={result.risk.reward_risk.recommended ? 'green' : 'yellow'}
                        />
                      ) : (
                        <Badge label="N/A" variant="gray" />
                      )}
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-3 text-xs text-gray-400">
                      <div>
                        <div className="text-gray-500">Risk</div>
                        <div>
                          {result.risk?.reward_risk?.risk_amount !== undefined ? `৳${fmt(result.risk.reward_risk.risk_amount, 2)}` : '-'}
                          {result.risk?.reward_risk?.risk_percent !== undefined ? ` (${fmt(result.risk.reward_risk.risk_percent, 2)}%)` : ''}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500">Reward</div>
                        <div>
                          {result.risk?.reward_risk?.reward_amount !== undefined ? `৳${fmt(result.risk.reward_risk.reward_amount, 2)}` : '-'}
                          {result.risk?.reward_risk?.reward_percent !== undefined ? ` (${fmt(result.risk.reward_risk.reward_percent, 2)}%)` : ''}
                        </div>
                      </div>
                    </div>
                    {!result.risk?.reward_risk?.valid && (
                      <div className="text-xs text-gray-500 mt-2">{result.risk?.reward_risk?.reason || 'Needs ATR + support + resistance'}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* v7: EarlyScore breakdown */}
            {result.early && (
              <div className="bg-gray-950 border border-orange-700/60 rounded p-4">
                <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                  <h3 className="font-bold text-orange-300">🔥 EarlyScore — Pre-Breakout Detector (v7)</h3>
                  <div className="flex items-center gap-2">
                    <Badge label={`Score: ${result.early.score}/100`}
                           variant={result.early.signal === 'EARLY' ? 'green' : result.early.signal === 'WATCH' ? 'yellow' : 'gray'} />
                    <Badge label={result.early.signal}
                           variant={result.early.signal === 'EARLY' ? 'green' : result.early.signal === 'WATCH' ? 'yellow' : 'gray'} />
                  </div>
                </div>
                <div className="text-xs text-gray-400 mb-3 italic">
                  {result.early.signal === 'EARLY' && 'Tight base + volume tell + not extended — best entry window.'}
                  {result.early.signal === 'WATCH' && 'Setting up but missing a volume tell or testing the high — watch closely.'}
                  {result.early.signal === 'NONE' && 'No pre-breakout setup. Either already extended or no volume tell yet.'}
                </div>
                <div>
                  {([
                    ['tight_base', 'Tight Base (10d range)', '25', (c?: { range_pct_10d?: number | null }) => `${c?.range_pct_10d ?? '-'}% — <4% best, <6% good, <8% ok`],
                    ['goldilocks_volume', 'Goldilocks Volume', '25', (c?: { rvol?: number }) => `RVOL ${c?.rvol ?? '-'}x — sweet spot 1.8–3.0x (NOT 5x+)`],
                    ['closing_tell', 'Closing Tell', '20', (c?: { green?: boolean; cpr?: number; above_prev?: boolean }) =>
                      `green=${c?.green ? 'yes' : 'no'}, CPR=${c?.cpr ?? '-'}, above prev=${c?.above_prev ? 'yes' : 'no'}`],
                    ['near_resistance', 'Near 10d High', '15', (c?: { high_10d?: number; distance_pct?: number | null }) =>
                      `${c?.distance_pct ?? '-'}% from 10d high (${c?.high_10d ?? '-'})`],
                    ['not_extended', 'Not Extended', '15', (c?: { return_5d_pct?: number | null }) =>
                      `5d return ${c?.return_5d_pct ?? '-'}% — <8% rewarded, >25% penalised`],
                  ] as const).map(([k, label, max, fmtDetail]) => {
                    const c = (result.early!.components as Record<string, { points?: number } & Record<string, unknown> | undefined>)[k];
                    const pts = c?.points ?? 0;
                    return (
                      <div key={k} className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 border-b border-gray-800 py-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-bold ${pts > 0 ? 'text-green-400' : pts < 0 ? 'text-red-400' : 'text-gray-300'}`}>
                            {pts > 0 ? '✅' : pts < 0 ? '❌' : '⬜'}
                          </span>
                          <div>
                            <div className="text-sm text-gray-200">{label}</div>
                            <div className="text-xs text-gray-500">{fmtDetail(c as never)}</div>
                          </div>
                        </div>
                        <div className={`text-sm font-bold ${pts > 0 ? 'text-green-400' : pts < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                          {pts > 0 ? `+${pts}` : pts} <span className="text-gray-600">/ {max}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {result.early.reasons.length > 0 && (
                  <div className="mt-3 text-xs text-gray-500">
                    <span className="text-gray-400 font-bold">Reasons:</span> {result.early.reasons.join(', ')}
                  </div>
                )}
              </div>
            )}

            {/* Score breakdown */}
            <div className="bg-gray-950 border border-gray-700 rounded p-4">
              <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                <h3 className="font-bold text-pink-300">Score Calculation Breakdown</h3>
                <div className="flex items-center gap-2">
                  {result.score?.raw_score !== undefined && <Badge label={`Raw: ${result.score.raw_score}`} variant="gray" />}
                  {result.score?.final_score !== undefined && <Badge label={`Final: ${result.score.final_score}`} variant="blue" />}
                  {result.score?.signal && (
                    <Badge
                      label={result.score.signal}
                      variant={result.score.signal === 'BUY' ? 'green' : result.score.signal === 'WAIT' ? 'yellow' : 'gray'}
                    />
                  )}
                </div>
              </div>
              <div>
                {(result.score?.breakdown || []).map((item, idx) => (
                  <BreakdownRow key={idx} item={item} />
                ))}
              </div>
              {result.score?.official_reasons && (
                <div className="mt-4 text-xs text-gray-500">
                  <div className="text-gray-400 font-bold mb-1">Official Reasons (from existing analyzer)</div>
                  <div>{result.score.official_reasons.join(', ')}</div>
                </div>
              )}
            </div>

            {/* Official summary (if included) */}
            {result.official && (
              <div className="bg-gray-950 border border-gray-700 rounded p-4">
                <h3 className="font-bold text-gray-200 mb-3">Official Summary (compare)</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div className="bg-gray-900 border border-gray-800 rounded p-3">
                    <div className="text-xs text-gray-500">Official Signal</div>
                    <div className="font-bold">{result.official.signal || '-'}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded p-3">
                    <div className="text-xs text-gray-500">Official Score</div>
                    <div className="font-bold">{result.official.score ?? '-'}</div>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded p-3">
                    <div className="text-xs text-gray-500">Trend</div>
                    <div className="font-bold">{result.official.trend_status || '-'}</div>
                  </div>
                </div>
                {result.official.reasons && (
                  <div className="mt-3 text-xs text-gray-500">
                    <span className="text-gray-400 font-bold">Reasons:</span> {result.official.reasons.join(', ')}
                  </div>
                )}
              </div>
            )}
            </>)}
          </div>
        )}
      </section>
    </div>
  );
}
