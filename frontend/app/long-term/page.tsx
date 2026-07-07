'use client';

/**
 * /long-term — the "Dividend Fortress" buy-and-hold shortlist.
 *
 * Ranks liquid, consistently dividend-paying DSE companies by reliability,
 * yield, growth and balance-sheet quality (docs/LONG_TERM_STRATEGY.md).
 * Data: dividend_history (scraped from the DSE company pages, refreshed with
 * the weekly Saturday fundamentals scrape) + fundamentals + latest close.
 *
 * This is an INVESTING list (years), deliberately separate from the trading
 * dashboard (days/weeks) so the two mindsets never blur.
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import { Landmark, RefreshCw, ChevronDown, ChevronUp, BadgeCheck } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DivYear {
  year: number;
  cash: number | null;
  stock: number | null;
}

interface LtStock {
  ticker: string;
  sector: string | null;
  category: string | null;
  price: number;
  face_value: number;
  latest_div_year: number;
  latest_cash_pct: number;
  latest_stock_pct: number | null;
  dps: number;
  yield_pct: number;
  paid_5y: number;
  streak_years: number;
  div_growth_5y_pct: number | null;
  payout_pct: number | null;
  eps: number | null;
  pe: number | null;
  nav: number | null;
  p_nav: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  sponsor_pct: number | null;
  market_cap_cr: number | null;
  avg_vol20: number;
  history_5y: DivYear[];
  total_div_years: number;
  score: number;
  grade: string;
  score_parts: Record<string, number>;
}

interface LtResponse {
  as_of: string;
  universe: number;
  qualified: number;
  stocks: LtStock[];
}

interface FullDivHistory {
  ticker: string;
  history: { year: number; cash_pct: number | null; stock_pct: number | null }[];
}

const gradeColor = (g: string) =>
  g === 'A' ? 'bg-emerald-700 text-emerald-100'
  : g === 'B' ? 'bg-sky-700 text-sky-100'
  : g === 'C' ? 'bg-yellow-700 text-yellow-100'
  : 'bg-gray-700 text-gray-300';

const PART_LABELS: Record<string, [string, number]> = {
  reliability: ['Paid 5-yr reliability', 25],
  streak: ['Unbroken streak', 15],
  yield: ['Dividend yield', 20],
  growth: ['5-yr dividend growth', 10],
  earnings: ['Earnings quality (EPS/payout/ROE)', 20],
  balance: ['Balance sheet + governance', 10],
};

export default function LongTermPage() {
  const [data, setData] = useState<LtResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openRow, setOpenRow] = useState<string | null>(null);
  const [fullHist, setFullHist] = useState<Record<string, FullDivHistory>>({});

  const fetchList = () => {
    setLoading(true);
    setError(null);
    axios
      .get<LtResponse>(`${API_URL}/api/long-term`)
      .then((res) => setData(res.data))
      .catch(() => setError('Could not load the long-term list.'))
      .finally(() => setLoading(false));
  };

  useEffect(fetchList, []);

  const toggleRow = (ticker: string) => {
    const next = openRow === ticker ? null : ticker;
    setOpenRow(next);
    if (next && !fullHist[next]) {
      axios
        .get<FullDivHistory>(`${API_URL}/api/long-term/${next}/dividends`)
        .then((res) => setFullHist((m) => ({ ...m, [next]: res.data })))
        .catch(() => { /* non-fatal — the 5y row still shows */ });
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8 font-mono">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <h1 className="text-2xl font-bold flex items-center gap-2 text-emerald-300">
          <Landmark className="w-6 h-6" /> Long-Term Investing — Dividend Fortress
        </h1>
        <div className="flex items-center gap-3 text-sm">
          {data && <span className="text-gray-500">as of {data.as_of}</span>}
          <button
            onClick={fetchList}
            className="bg-gray-800 hover:bg-gray-700 border border-gray-700 px-3 py-1.5 rounded flex items-center gap-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          <Link href="/" className="bg-gray-800 hover:bg-gray-700 border border-gray-700 px-3 py-1.5 rounded">
            ← Dashboard
          </Link>
        </div>
      </div>

      {/* What this list is (and is not) */}
      <div className="mb-4 bg-emerald-950/25 border border-emerald-700/50 rounded-lg p-3 text-xs text-emerald-100/90 leading-relaxed">
        <b>🏛️ Buy-and-hold shortlist, not a trading signal.</b> In a manipulated market, a long unbroken{' '}
        <b>cash-dividend record is the hardest thing to fake</b> — it costs the sponsors real taka every year.
        This list ranks every liquid, non-Z, profitable company that paid cash dividends in at least 3 of the
        last 5 years, by: reliability (25) + streak (15) + yield (20) + growth (10) + earnings quality (20) +
        balance sheet (10). <b>Grade A ≥ 75.</b> Data refreshes with the Saturday fundamentals scrape.
        Compare yield against bank FDR rates (~8–9%) — a fortress at a 6%+ cash yield pays you to wait.
        Full method: <span className="text-emerald-300">docs/LONG_TERM_STRATEGY.md</span>.
      </div>

      {error && <div className="mb-4 bg-red-950/40 border border-red-700 rounded p-3 text-sm text-red-300">{error}</div>}
      {loading && !data && <div className="text-gray-500 text-sm p-8 text-center">Loading…</div>}

      {data && (
        <>
          <div className="mb-3 text-xs text-gray-500">
            {data.qualified} of {data.universe} listed companies pass the gates (liquid · non-Z · EPS &gt; 0 ·
            paid ≥3 of last 5 years · paid last year).
          </div>

          <div className="overflow-x-auto bg-gray-800/40 border border-gray-700 rounded-lg">
            <table className="text-left text-sm min-w-[980px] w-full">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-700">
                  <th className="p-3" title="Composite 0–100: reliability 25 + streak 15 + yield 20 + growth 10 + earnings 20 + balance sheet 10">GRADE</th>
                  <th className="p-3">TICKER</th>
                  <th className="p-3">SECTOR</th>
                  <th className="p-3">PRICE</th>
                  <th className="p-3" title="Latest cash dividend ÷ price. DSE dividends are % of face value.">YIELD</th>
                  <th className="p-3" title="Latest declared cash dividend (% of face value) and taka per share">LATEST DIV</th>
                  <th className="p-3" title="Cash dividend % by year — the showcase row">LAST 5 YEARS</th>
                  <th className="p-3" title="Consecutive years with a cash dividend, ending at the latest">STREAK</th>
                  <th className="p-3" title="Dividend per share ÷ EPS — under 80% is sustainable">PAYOUT</th>
                  <th className="p-3">P/E</th>
                  <th className="p-3">ROE</th>
                  <th className="p-3" title="Sponsor/Director holding — skin in the game">SPONSOR</th>
                  <th className="p-3 text-center">MORE</th>
                </tr>
              </thead>
              <tbody>
                {data.stocks.map((s) => (
                  <>
                    <tr
                      key={s.ticker}
                      className="border-b border-gray-700/50 hover:bg-emerald-900/10 transition cursor-pointer"
                      onClick={() => toggleRow(s.ticker)}
                    >
                      <td className="p-3">
                        <span className={`inline-flex items-center justify-center w-8 h-6 rounded font-bold ${gradeColor(s.grade)}`} title={`Score ${s.score}/100`}>
                          {s.grade}
                        </span>
                      </td>
                      <td className="p-3 font-bold text-emerald-300 whitespace-nowrap">
                        {s.ticker}
                        {s.streak_years >= 10 && (
                          <BadgeCheck className="w-3.5 h-3.5 inline ml-1 text-emerald-400" aria-label="10+ year dividend streak" />
                        )}
                      </td>
                      <td className="p-3 text-gray-400 text-xs max-w-[130px] truncate">{s.sector || '—'}</td>
                      <td className="p-3">{s.price}</td>
                      <td className="p-3 font-bold text-emerald-200">{s.yield_pct}%</td>
                      <td className="p-3 whitespace-nowrap">
                        {s.latest_cash_pct}%{s.latest_stock_pct ? ` +${s.latest_stock_pct}%B` : ''}
                        <span className="text-gray-500 text-xs"> ({s.dps} tk)</span>
                      </td>
                      <td className="p-3 whitespace-nowrap text-xs">
                        {s.history_5y.map((h) => (
                          <span key={h.year} className={`inline-block mr-1.5 ${h.cash ? 'text-gray-200' : 'text-red-400/70'}`}
                            title={`${h.year}: ${h.cash ? `${h.cash}% cash` : 'no cash dividend'}${h.stock ? ` + ${h.stock}% stock` : ''}`}>
                            <span className="text-gray-600">&apos;{String(h.year).slice(2)}</span> {h.cash ?? '·'}
                          </span>
                        ))}
                      </td>
                      <td className="p-3">{s.streak_years}y</td>
                      <td className="p-3">{s.payout_pct != null ? `${s.payout_pct}%` : '—'}</td>
                      <td className="p-3">{s.pe ?? '—'}</td>
                      <td className="p-3">{s.roe != null ? `${s.roe}%` : '—'}</td>
                      <td className="p-3">{s.sponsor_pct != null ? `${s.sponsor_pct}%` : '—'}</td>
                      <td className="p-3 text-center text-gray-500">
                        {openRow === s.ticker ? <ChevronUp className="w-4 h-4 inline" /> : <ChevronDown className="w-4 h-4 inline" />}
                      </td>
                    </tr>

                    {openRow === s.ticker && (
                      <tr key={`${s.ticker}-detail`} className="border-b border-gray-700/50 bg-gray-900/60">
                        <td colSpan={13} className="p-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                            {/* Score breakdown */}
                            <div>
                              <div className="text-gray-400 font-bold mb-2">SCORE BREAKDOWN — {s.score}/100</div>
                              {Object.entries(PART_LABELS).map(([k, [label, max]]) => (
                                <div key={k} className="flex justify-between border-b border-gray-800 py-0.5">
                                  <span className="text-gray-400">{label}</span>
                                  <span className={s.score_parts[k] > 0 ? 'text-emerald-300' : 'text-gray-600'}>
                                    {s.score_parts[k] ?? 0}/{max}
                                  </span>
                                </div>
                              ))}
                              <div className="mt-2 text-gray-500">
                                Market cap: {s.market_cap_cr ? `${s.market_cap_cr} Cr` : '—'} · NAV {s.nav ?? '—'}
                                {s.p_nav ? ` (P/NAV ${s.p_nav})` : ''} · D/E {s.debt_to_equity != null ? `${s.debt_to_equity}%` : '—'} ·
                                Vol20 {Math.round(s.avg_vol20 / 1000)}k/day · Category {s.category || '—'}
                              </div>
                            </div>

                            {/* Full dividend history */}
                            <div className="md:col-span-2">
                              <div className="text-gray-400 font-bold mb-2">
                                FULL CASH-DIVIDEND HISTORY ({s.total_div_years} paying years)
                              </div>
                              {fullHist[s.ticker] ? (
                                <div className="flex flex-wrap gap-1.5">
                                  {fullHist[s.ticker].history.map((h) => (
                                    <div key={h.year}
                                      className={`px-2 py-1 rounded border text-center ${h.cash_pct ? 'border-emerald-800/60 bg-emerald-950/30' : 'border-gray-700 bg-gray-800/40'}`}
                                      title={`${h.year}: cash ${h.cash_pct ?? 0}%${h.stock_pct ? `, stock ${h.stock_pct}%` : ''}`}>
                                      <div className="text-gray-500">{h.year}</div>
                                      <div className={h.cash_pct ? 'text-emerald-300 font-bold' : 'text-gray-600'}>
                                        {h.cash_pct ? `${h.cash_pct}%` : '—'}
                                      </div>
                                      {h.stock_pct ? <div className="text-sky-400/80">+{h.stock_pct}%B</div> : null}
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="text-gray-600">Loading history…</div>
                              )}
                              <div className="mt-2 text-gray-600">
                                B = bonus (stock) dividend. Percentages are of face value ({s.face_value} tk) —
                                {' '}{s.latest_cash_pct}% = {s.dps} tk/share on today&apos;s {s.price} tk price = {s.yield_pct}% yield.
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 text-xs text-gray-600 leading-relaxed">
            ⚠️ Honesty notes: dividend history comes from the DSE company pages (declared totals per year; the
            page is the source of truth). EPS/ROE/P/E are the latest audited figures, refreshed weekly — check a
            company&apos;s newest quarterly report before committing serious money. A high yield can also mean a
            falling price — always ask <i>why</i> it&apos;s cheap. Diversify across 8–12 names and sectors; even
            fortresses crack.
          </div>
        </>
      )}
    </main>
  );
}
