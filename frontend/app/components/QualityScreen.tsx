'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { ShieldCheck, Check, X, Minus } from 'lucide-react';

interface Step { value: number | null; pass: boolean }
interface QStock {
  ticker: string; sector?: string; passed: number; have_data: number;
  steps: { market_cap: Step; sponsor: Step; eps_growth: Step; roe: Step; debt_equity: Step; pe: Step };
}
interface QData { stocks: QStock[]; total: number; perfect: number; strong: number }

const COLS: { key: keyof QStock['steps']; label: string; fmt: (v: number | null) => string; rule: string }[] = [
  { key: 'market_cap', label: 'Mkt Cap', fmt: (v) => (v == null ? '—' : `${Math.round(v / 10).toLocaleString()} Cr`), rule: '> 1,000 Cr' },
  { key: 'sponsor', label: 'Sponsor', fmt: (v) => (v == null ? '—' : `${v.toFixed(0)}%`), rule: '≥ 30%' },
  { key: 'eps_growth', label: 'EPS Growth', fmt: (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(0)}%/yr`), rule: '≥ 10%/yr' },
  { key: 'roe', label: 'ROE', fmt: (v) => (v == null ? '—' : `${v.toFixed(0)}%`), rule: '≥ 15%' },
  { key: 'debt_equity', label: 'Debt/Eq', fmt: (v) => (v == null ? '—' : `${v.toFixed(0)}%`), rule: '< 50%' },
  { key: 'pe', label: 'P/E', fmt: (v) => (v == null ? '—' : v.toFixed(1)), rule: '< 15' },
];

function Cell({ s, fmt }: { s: Step; fmt: (v: number | null) => string }) {
  const color = s.value == null ? 'text-gray-500' : s.pass ? 'text-emerald-300' : 'text-red-300/80';
  const Icon = s.value == null ? Minus : s.pass ? Check : X;
  const ic = s.value == null ? 'text-gray-600' : s.pass ? 'text-emerald-400' : 'text-red-500';
  return (
    <td className={`py-2 pr-4 whitespace-nowrap ${color}`}>
      <span className="inline-flex items-center gap-1"><Icon className={`w-3.5 h-3.5 ${ic}`} />{fmt(s.value)}</span>
    </td>
  );
}

export default function QualityScreen({ apiUrl }: { apiUrl: string }) {
  const [data, setData] = useState<QData | null>(null);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(5);

  useEffect(() => {
    axios.get(`${apiUrl}/api/quality-screen`)
      .then((r) => setData(r.data))
      .catch(() => setData({ stocks: [], total: 0, perfect: 0, strong: 0 }))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  const shown = (data?.stocks || []).filter((s) => s.passed >= minScore);

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-emerald-800/40 mt-6">
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <ShieldCheck className="w-5 h-5 text-emerald-300" />
        <h2 className="text-lg font-bold text-emerald-200">Fundamental Quality</h2>
        <span className="text-[10px] text-gray-500 border border-gray-700 rounded px-1.5 py-0.5">v12 · 6-step Graham screen</span>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        The companies worth <b className="text-gray-400">owning</b> — strong fundamentals, not chart timing.
        Six checks: Market Cap &gt; 1,000 Cr · Sponsor ≥ 30% · EPS growth ≥ 10%/yr · ROE ≥ 15% · Debt/Equity &lt; 50% · P/E &lt; 15.
        A great long-term portfolio is ~10–15 names scoring <b className="text-emerald-300">5–6/6</b>.
      </p>

      {loading ? (
        <div className="text-gray-500 text-sm py-6 text-center">Loading…</div>
      ) : !data || data.total === 0 ? (
        <div className="text-gray-500 text-sm py-6 text-center">
          No fundamentals loaded yet — run the fundamentals backfill, then this fills in.
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4 text-xs">
            <span className="bg-gray-900 border border-gray-700 rounded px-2.5 py-1">Scanned <b className="text-gray-200">{data.total}</b></span>
            <span className="bg-gray-900 border border-emerald-800/50 rounded px-2.5 py-1">Pass all 6: <b className="text-emerald-300">{data.perfect}</b></span>
            <span className="bg-gray-900 border border-emerald-800/50 rounded px-2.5 py-1">Pass 5+: <b className="text-emerald-300">{data.strong}</b></span>
            <div className="ml-auto flex items-center gap-1">
              {[6, 5, 4, 0].map((n) => (
                <button key={n} onClick={() => setMinScore(n)}
                  className={`px-2 py-1 rounded ${minScore === n ? 'bg-emerald-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                  {n === 0 ? 'All' : `${n}+/6`}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="text-left text-sm min-w-[760px] w-full">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-700">
                  <th className="pb-3 pr-4">TICKER</th>
                  {COLS.map((c) => <th key={c.key} className="pb-3 pr-4" title={`Rule: ${c.rule}`}>{c.label}</th>)}
                  <th className="pb-3 pr-2 text-center">SCORE</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((s) => (
                  <tr key={s.ticker} className={`border-b border-gray-700/50 h-10 ${s.passed === 6 ? 'bg-emerald-900/10' : ''}`}>
                    <td className="py-2 pr-4 font-bold text-emerald-200 whitespace-nowrap">
                      {s.ticker}
                      {s.sector && <span className="ml-1.5 text-[10px] text-gray-500 font-normal">{s.sector}</span>}
                    </td>
                    {COLS.map((c) => <Cell key={c.key} s={s.steps[c.key]} fmt={c.fmt} />)}
                    <td className="py-2 pr-2 text-center">
                      <span className={`font-bold ${s.passed === 6 ? 'text-emerald-300' : s.passed >= 5 ? 'text-emerald-400/80' : 'text-gray-300'}`}>
                        {s.passed}/6
                      </span>
                    </td>
                  </tr>
                ))}
                {shown.length === 0 && (
                  <tr><td colSpan={8} className="py-8 text-center text-gray-500">No stocks at {minScore}+/6 yet. Lower the filter or run the backfill.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-gray-600 mt-3">
            Long-term quality screen — pair it with the technical tabs for timing (a high-quality name on a Breakout = strongest confluence).
            ROE = EPS ÷ NAV; EPS growth = 5-yr annual CAGR; Debt/Equity = bank loans ÷ (paid-up + reserves).
          </p>
        </>
      )}
    </section>
  );
}
