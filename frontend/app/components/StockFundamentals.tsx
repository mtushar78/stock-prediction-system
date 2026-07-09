'use client';

/**
 * StockFundamentals — the "everything about this company" panel for the
 * /analyze page. Pulls two independent sources:
 *   1. /api/fundamentals/{ticker}  → sector, category, EPS, P/E, NAV, ROE,
 *      D/E, sponsor %, market cap … (weekly Saturday fundamentals scrape)
 *   2. /api/long-term/{ticker}/dividends → full per-year cash/bonus dividend
 *      record (same data the Long-Term "Dividend Fortress" list drills into)
 *
 * Deliberately read-only and self-contained: both fetches fail soft, so a
 * ticker with no fundamentals or no dividend record still renders cleanly.
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { Building2, Landmark } from 'lucide-react';

interface Fundamentals {
  ticker: string;
  sector?: string | null;
  market_category?: string | null;
  market_cap?: number | null;
  face_value?: number | null;
  total_shares?: number | null;
  eps?: number | null;
  pe_ratio?: number | null;
  nav?: number | null;
  roe?: number | null;
  debt_to_equity?: number | null;
  eps_growth_pa?: number | null;
  sponsor_pct?: number | null;
  reserves_mn?: number | null;
  paid_up_capital_cr?: number | null;
  last_updated?: string | null;
}

interface DivYear {
  year: number;
  cash_pct: number | null;
  stock_pct: number | null;
}

interface DivHistoryResp {
  ticker: string;
  history: DivYear[];
}

function num(n: number | null | undefined, digits = 2, suffix = '') {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${Number(n).toLocaleString(undefined, { maximumFractionDigits: digits })}${suffix}`;
}

function Fact({ label, value, hint, color }: { label: string; value: string; hint?: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-3" title={hint}>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`font-bold ${color ?? 'text-gray-100'}`}>{value}</div>
    </div>
  );
}

export default function StockFundamentals({
  apiUrl,
  ticker,
  price,
}: {
  apiUrl: string;
  ticker: string;
  price?: number | null;
}) {
  const [fund, setFund] = useState<Fundamentals | null>(null);
  const [fundMissing, setFundMissing] = useState(false);
  const [div, setDiv] = useState<DivYear[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setFund(null);
      setFundMissing(false);
      setDiv([]);

      const fundP = axios
        .get<Fundamentals>(`${apiUrl}/api/fundamentals/${ticker}`)
        .then((r) => {
          if (!cancelled) setFund(r.data);
        })
        .catch(() => {
          if (!cancelled) setFundMissing(true);
        });

      const divP = axios
        .get<DivHistoryResp>(`${apiUrl}/api/long-term/${ticker}/dividends`)
        .then((r) => {
          if (!cancelled) setDiv(r.data?.history ?? []);
        })
        .catch(() => {
          /* no dividend record — non-fatal */
        });

      await Promise.allSettled([fundP, divP]);
      if (!cancelled) setLoading(false);
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, ticker]);

  // Dividend derived stats (cash side — the honesty signal).
  const cashYears = div.filter((d) => (d.cash_pct ?? 0) > 0);
  const latest = cashYears.length ? cashYears[cashYears.length - 1] : null;
  const faceValue = fund?.face_value ?? 10;
  const latestDps = latest && latest.cash_pct != null ? (latest.cash_pct / 100) * faceValue : null;
  const yieldPct = latestDps != null && price ? (latestDps / price) * 100 : null;

  // Consecutive cash-paying streak ending at the most recent year on record.
  let streak = 0;
  if (div.length) {
    const sorted = [...div].sort((a, b) => b.year - a.year);
    for (const d of sorted) {
      if ((d.cash_pct ?? 0) > 0) streak += 1;
      else break;
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ---- Sector & fundamentals ---- */}
      <div className="bg-gray-950 border border-gray-700 rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-teal-300 flex items-center gap-2">
            <Building2 className="w-4 h-4" /> Sector &amp; Fundamentals
          </h3>
          {fund?.sector && (
            <span className="text-xs bg-teal-900/40 border border-teal-700 text-teal-200 rounded px-2 py-0.5">
              {fund.sector}
            </span>
          )}
        </div>

        {loading && <div className="text-sm text-gray-500 py-4">Loading fundamentals…</div>}

        {!loading && fundMissing && (
          <div className="text-sm text-gray-600 py-4">No fundamentals on record for {ticker}.</div>
        )}

        {!loading && fund && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <Fact label="Sector" value={fund.sector || '—'} color="text-teal-200" />
              <Fact label="Category" value={fund.market_category || '—'} hint="DSE market category (A/B/N/Z)" />
              <Fact
                label="Market Cap"
                value={fund.market_cap != null ? `${num(fund.market_cap / 10, 0)} Cr` : '—'}
                hint="Market capitalisation (Cr taka)"
              />
              <Fact label="EPS" value={num(fund.eps)} hint="Earnings per share (latest)" />
              <Fact
                label="P/E"
                value={num(fund.pe_ratio, 1)}
                hint="Price / earnings"
                color={fund.pe_ratio != null && fund.pe_ratio > 0 && fund.pe_ratio < 15 ? 'text-green-300' : 'text-gray-100'}
              />
              <Fact label="NAV" value={num(fund.nav)} hint="Net asset value per share" />
              <Fact
                label="ROE"
                value={num(fund.roe, 1, '%')}
                hint="Return on equity"
                color={fund.roe != null && fund.roe >= 15 ? 'text-green-300' : 'text-gray-100'}
              />
              <Fact
                label="D/E"
                value={num(fund.debt_to_equity, 1, '%')}
                hint="Debt-to-equity"
                color={fund.debt_to_equity != null && fund.debt_to_equity > 100 ? 'text-red-300' : 'text-gray-100'}
              />
              <Fact label="EPS Growth" value={num(fund.eps_growth_pa, 1, '%')} hint="EPS growth p.a." />
              <Fact
                label="Sponsor"
                value={num(fund.sponsor_pct, 1, '%')}
                hint="Sponsor / director holding — skin in the game"
                color={fund.sponsor_pct != null && fund.sponsor_pct >= 30 ? 'text-green-300' : 'text-gray-100'}
              />
              <Fact label="Face Value" value={num(fund.face_value, 0)} hint="Par value per share (taka)" />
              <Fact label="Paid-up Cap" value={fund.paid_up_capital_cr != null ? `${num(fund.paid_up_capital_cr, 0)} Cr` : '—'} />
            </div>
            {fund.last_updated && (
              <div className="text-[11px] text-gray-600 mt-3">
                Fundamentals as of {String(fund.last_updated).slice(0, 10)} · weekly scrape. Check the latest quarterly before acting.
              </div>
            )}
          </>
        )}
      </div>

      {/* ---- Dividend history ---- */}
      <div className="bg-gray-950 border border-gray-700 rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-emerald-300 flex items-center gap-2">
            <Landmark className="w-4 h-4" /> Dividend History
          </h3>
          {cashYears.length > 0 && (
            <span className="text-xs text-gray-500">
              {cashYears.length} paying years{streak > 0 ? ` · ${streak}y streak` : ''}
            </span>
          )}
        </div>

        {loading && <div className="text-sm text-gray-500 py-4">Loading dividends…</div>}

        {!loading && div.length === 0 && (
          <div className="text-sm text-gray-600 py-4">No cash-dividend record on file for {ticker}.</div>
        )}

        {!loading && div.length > 0 && (
          <>
            {/* Headline: latest declared + yield on today's price */}
            <div className="grid grid-cols-3 gap-3 text-sm mb-3">
              <Fact
                label="Latest Cash Div"
                value={latest?.cash_pct != null ? `${num(latest.cash_pct, 0, '%')}` : '—'}
                hint={latest ? `Declared for ${latest.year} (% of ${faceValue} tk face value)` : undefined}
                color="text-emerald-200"
              />
              <Fact
                label="DPS"
                value={latestDps != null ? `${num(latestDps)} tk` : '—'}
                hint="Cash dividend per share (taka)"
              />
              <Fact
                label="Yield"
                value={yieldPct != null ? `${num(yieldPct, 1, '%')}` : '—'}
                hint="DPS ÷ current price. Compare vs ~8–9% bank FDR."
                color={yieldPct != null && yieldPct >= 8 ? 'text-emerald-300' : 'text-gray-100'}
              />
            </div>

            {/* Full per-year grid — cash % (bonus flagged) */}
            <div className="flex flex-wrap gap-1.5 max-h-56 overflow-y-auto">
              {[...div]
                .sort((a, b) => b.year - a.year)
                .map((h) => (
                  <div
                    key={h.year}
                    className={`px-2 py-1 rounded border text-center text-xs ${
                      h.cash_pct ? 'border-emerald-800/60 bg-emerald-950/30' : 'border-gray-700 bg-gray-800/40'
                    }`}
                    title={`${h.year}: cash ${h.cash_pct ?? 0}%${h.stock_pct ? `, stock ${h.stock_pct}%` : ''}`}
                  >
                    <div className="text-gray-500">{h.year}</div>
                    <div className={h.cash_pct ? 'text-emerald-300 font-bold' : 'text-gray-600'}>
                      {h.cash_pct ? `${h.cash_pct}%` : '—'}
                    </div>
                    {h.stock_pct ? <div className="text-sky-400/80">+{h.stock_pct}%B</div> : null}
                  </div>
                ))}
            </div>
            <div className="text-[11px] text-gray-600 mt-3">
              % of face value ({faceValue} tk). B = bonus (stock) dividend. A long unbroken cash record is the
              hardest thing to fake in a manipulated market.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
