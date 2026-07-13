'use client';

/**
 * /news — DSE News & Rumor Radar.
 *
 * Two views over the same idea ("what is the broker-house crowd reacting to?"):
 *
 *  1. Rumor Radar  — /api/unusual-activity. Stocks moving on abnormal
 *     volume/price today, each cross-referenced against the official news feed.
 *     'Unexplained' moves (big volume, no disclosed news) and exchange-flagged
 *     names (DSE query/halt) are the data-driven proxy for floor chatter.
 *  2. News Feed    — /api/news. The official price-sensitive information feed
 *     (dividends, board meetings, results, credit ratings) plus the exchange's
 *     own query/halt/rumor-clarification notices, filterable by category.
 *
 * Clicking any ticker opens the full manual analysis in a modal.
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Newspaper, RefreshCw, Radar, AlertTriangle, Search, Filter,
} from 'lucide-react';
import FullAnalysisModal from '../components/FullAnalysisModal';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const f1 = (n: number | null | undefined) => (n == null ? '—' : n.toFixed(1));

// ------------------------- types ------------------------- //
interface NewsItem {
  ticker: string;
  news_date: string;
  category: string;
  title: string;
  body: string;
  is_price_sensitive: boolean;
  is_query: boolean;
}
interface NewsResponse {
  count: number;
  category_counts: Record<string, number>;
  news: NewsItem[];
}
interface Unusual {
  ticker: string;
  sector: string | null;
  price: number;
  change_pct: number;
  rvol: number;
  turnover_x: number;
  turnover_today_mn: number;
  day_range_pct: number;
  direction: 'up' | 'down';
  classification: 'exchange_flagged' | 'unexplained' | 'news_driven';
  classification_label: string;
  has_query: boolean;
  latest_news_date: string | null;
  latest_news_category: string | null;
  latest_news_title: string | null;
  score: number;
  reasons: string[];
}
interface UnusualResponse {
  as_of: string | null;
  universe: number;
  count: number;
  counts: { exchange_flagged: number; unexplained: number; news_driven: number };
  stocks: Unusual[];
}

// ------------------------- styling helpers ------------------------- //
const CAT_COLOR: Record<string, string> = {
  'Query Response': 'bg-red-900/50 text-red-300 border-red-700',
  'Dividend': 'bg-emerald-900/50 text-emerald-300 border-emerald-700',
  'Board Meeting': 'bg-blue-900/50 text-blue-300 border-blue-700',
  'AGM/EGM': 'bg-indigo-900/50 text-indigo-300 border-indigo-700',
  'Financial Result': 'bg-purple-900/50 text-purple-300 border-purple-700',
  'Credit Rating': 'bg-amber-900/50 text-amber-300 border-amber-700',
  'Capital / Rights / IPO': 'bg-pink-900/50 text-pink-300 border-pink-700',
  'Record Date / Spot': 'bg-gray-800 text-gray-400 border-gray-600',
  'Corporate Action': 'bg-teal-900/50 text-teal-300 border-teal-700',
  'Fund NAV': 'bg-gray-800 text-gray-500 border-gray-700',
  'Other': 'bg-gray-800 text-gray-400 border-gray-600',
};
const catClass = (c: string) => CAT_COLOR[c] || CAT_COLOR['Other'];

const CLS_STYLE = {
  exchange_flagged: { label: 'EXCHANGE FLAGGED', color: 'bg-red-600 text-white', ring: 'border-red-700' },
  unexplained: { label: 'UNEXPLAINED MOVE', color: 'bg-amber-500 text-black', ring: 'border-amber-700' },
  news_driven: { label: 'NEWS-DRIVEN', color: 'bg-gray-600 text-white', ring: 'border-gray-700' },
} as const;

export default function NewsPage() {
  const [tab, setTab] = useState<'radar' | 'feed'>('radar');
  const [unusual, setUnusual] = useState<UnusualResponse | null>(null);
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);

  // feed filters
  const [category, setCategory] = useState<string>('ALL');
  const [queryOnly, setQueryOnly] = useState(false);
  const [search, setSearch] = useState('');

  const fetchAll = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      axios.get<UnusualResponse>(`${API_URL}/api/unusual-activity`),
      axios.get<NewsResponse>(`${API_URL}/api/news?limit=300`),
    ])
      .then(([u, n]) => { setUnusual(u.data); setNews(n.data); })
      .catch(() => setError('Could not load news / radar data.'))
      .finally(() => setLoading(false));
  };
  useEffect(fetchAll, []);

  // ---- Rumor Radar rows ---- //
  const radarRows = useMemo(() => unusual?.stocks ?? [], [unusual]);

  // ---- News Feed rows (client-side filter over the fetched window) ---- //
  const feedRows = useMemo(() => {
    let rows = news?.news ?? [];
    if (queryOnly) rows = rows.filter((r) => r.is_query);
    if (category !== 'ALL') rows = rows.filter((r) => r.category === category);
    const q = search.trim().toUpperCase();
    if (q) rows = rows.filter((r) => r.ticker.includes(q) || r.title.toUpperCase().includes(q));
    return rows;
  }, [news, category, queryOnly, search]);

  const categories = useMemo(() => {
    const cc = news?.category_counts ?? {};
    return Object.entries(cc).sort((a, b) => b[1] - a[1]);
  }, [news]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 p-6">
      <div className="max-w-6xl mx-auto">
        {/* header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-amber-400 flex items-center gap-2">
              <Radar className="w-7 h-7" /> News &amp; Rumor Radar
            </h1>
            <p className="text-gray-500 text-sm">
              What the market is reacting to — official disclosures + the moves that have no
              explanation yet.
            </p>
          </div>
          <button
            onClick={fetchAll}
            className="px-3 py-1.5 rounded bg-gray-800 border border-gray-700 hover:bg-gray-700 text-sm flex items-center gap-1.5"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>

        {/* tab switch */}
        <div className="flex gap-1 mb-5">
          <button
            onClick={() => setTab('radar')}
            className={`px-4 py-2 rounded-t text-sm font-medium flex items-center gap-1.5 border-b-2 ${
              tab === 'radar' ? 'text-amber-300 border-amber-400' : 'text-gray-400 border-transparent hover:text-gray-200'
            }`}
          >
            <Radar className="w-4 h-4" /> Rumor Radar
            {unusual && (
              <span className="ml-1 text-xs bg-amber-900/60 text-amber-200 px-1.5 rounded">
                {unusual.count}
              </span>
            )}
          </button>
          <button
            onClick={() => setTab('feed')}
            className={`px-4 py-2 rounded-t text-sm font-medium flex items-center gap-1.5 border-b-2 ${
              tab === 'feed' ? 'text-emerald-300 border-emerald-400' : 'text-gray-400 border-transparent hover:text-gray-200'
            }`}
          >
            <Newspaper className="w-4 h-4" /> News Feed
            {news && (
              <span className="ml-1 text-xs bg-emerald-900/60 text-emerald-200 px-1.5 rounded">
                {news.count}
              </span>
            )}
          </button>
        </div>

        {error && (
          <div className="p-4 mb-4 rounded bg-red-950/60 border border-red-800 text-red-300 text-sm">
            {error}
          </div>
        )}
        {loading && <div className="text-gray-500 py-10 text-center">Loading…</div>}

        {/* ===================== RUMOR RADAR ===================== */}
        {!loading && tab === 'radar' && unusual && (
          <>
            <div className="flex flex-wrap gap-3 mb-4 text-sm">
              <span className="text-gray-500">As of <b className="text-gray-300">{unusual.as_of || '—'}</b></span>
              <span className="px-2 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-800">
                {unusual.counts.exchange_flagged} exchange-flagged
              </span>
              <span className="px-2 py-0.5 rounded bg-amber-900/40 text-amber-300 border border-amber-800">
                {unusual.counts.unexplained} unexplained
              </span>
              <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700">
                {unusual.counts.news_driven} news-driven
              </span>
            </div>

            <div className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-3 mb-4 text-xs text-amber-200/80 flex gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>
                A watchlist, not a buy list. An unexplained spike is as often a pump as it is early
                smart money — the point is to see it the same day it starts moving, with the reason
                (or its conspicuous absence) attached.
              </span>
            </div>

            <div className="space-y-2">
              {radarRows.map((s) => {
                const st = CLS_STYLE[s.classification];
                return (
                  <button
                    key={s.ticker}
                    onClick={() => setActive(s.ticker)}
                    className={`w-full text-left rounded-lg border ${st.ring} bg-gray-900/60 hover:bg-gray-900 p-3 transition`}
                  >
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-2.5">
                        <span className="font-bold text-white text-lg">{s.ticker}</span>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${st.color}`}>
                          {st.label}
                        </span>
                        {s.sector && <span className="text-xs text-gray-500">{s.sector}</span>}
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <span className={s.direction === 'up' ? 'text-emerald-400' : 'text-red-400'}>
                          {s.change_pct >= 0 ? '▲' : '▼'} {Math.abs(s.change_pct).toFixed(1)}%
                        </span>
                        <span className="text-gray-400">৳{s.price}</span>
                        <span className="text-amber-300">{f1(s.rvol)}× vol</span>
                        <span className="text-gray-500 tabular-nums">score {s.score}</span>
                      </div>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-400">
                      {s.reasons.map((r, i) => (
                        <span key={i}>• {r}</span>
                      ))}
                    </div>
                    {s.latest_news_title && (
                      <div className="mt-1.5 text-xs text-gray-500">
                        <span className={`inline-block px-1.5 rounded border mr-1.5 ${catClass(s.latest_news_category || 'Other')}`}>
                          {s.latest_news_category}
                        </span>
                        {s.latest_news_date}: {s.latest_news_title}
                      </div>
                    )}
                  </button>
                );
              })}
              {radarRows.length === 0 && (
                <div className="text-gray-500 py-10 text-center">No unusual activity flagged today.</div>
              )}
            </div>
          </>
        )}

        {/* ===================== NEWS FEED ===================== */}
        {!loading && tab === 'feed' && news && (
          <>
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-2 top-2.5 text-gray-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Ticker or headline…"
                  className="pl-8 pr-3 py-1.5 rounded bg-gray-900 border border-gray-700 text-sm w-56 focus:outline-none focus:border-emerald-600"
                />
              </div>
              <button
                onClick={() => setQueryOnly((v) => !v)}
                className={`px-3 py-1.5 rounded text-sm flex items-center gap-1.5 border ${
                  queryOnly ? 'bg-red-900/50 text-red-200 border-red-700' : 'bg-gray-900 text-gray-400 border-gray-700 hover:text-gray-200'
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" /> Query / Halt / Rumor only
              </button>
            </div>

            {/* category chips */}
            <div className="flex flex-wrap gap-1.5 mb-4">
              <button
                onClick={() => setCategory('ALL')}
                className={`px-2.5 py-1 rounded text-xs border ${
                  category === 'ALL' ? 'bg-gray-200 text-black border-gray-200' : 'bg-gray-900 text-gray-400 border-gray-700'
                }`}
              >
                <Filter className="w-3 h-3 inline mr-1" />All
              </button>
              {categories.map(([cat, n]) => (
                <button
                  key={cat}
                  onClick={() => setCategory(cat)}
                  className={`px-2.5 py-1 rounded text-xs border ${
                    category === cat ? catClass(cat).replace('/50', '') + ' font-semibold' : 'bg-gray-900 text-gray-400 border-gray-700 hover:text-gray-200'
                  }`}
                >
                  {cat} <span className="opacity-60">{n}</span>
                </button>
              ))}
            </div>

            <div className="space-y-2">
              {feedRows.map((it, i) => (
                <div
                  key={`${it.ticker}-${it.news_date}-${i}`}
                  className={`rounded-lg border bg-gray-900/50 p-3 ${
                    it.is_query ? 'border-red-800/60' : it.is_price_sensitive ? 'border-gray-700' : 'border-gray-800'
                  }`}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={() => setActive(it.ticker)}
                      className="font-bold text-white hover:text-amber-300"
                    >
                      {it.ticker}
                    </button>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${catClass(it.category)}`}>
                      {it.category}
                    </span>
                    {it.is_query && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-600 text-white font-bold">
                        RUMOR SIGNAL
                      </span>
                    )}
                    <span className="text-xs text-gray-500 ml-auto">{it.news_date}</span>
                  </div>
                  <div className="mt-1 text-sm text-gray-200 font-medium">{it.title}</div>
                  {it.body && <div className="mt-0.5 text-xs text-gray-500 line-clamp-2">{it.body}</div>}
                </div>
              ))}
              {feedRows.length === 0 && (
                <div className="text-gray-500 py-10 text-center">No news matches these filters.</div>
              )}
            </div>
          </>
        )}
      </div>

      {active && (
        <FullAnalysisModal apiUrl={API_URL} ticker={active} onClose={() => setActive(null)} />
      )}
    </div>
  );
}
