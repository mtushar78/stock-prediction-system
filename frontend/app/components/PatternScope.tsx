'use client';

/**
 * PatternScope — the multi-week CHART-pattern scanner (Bulkowski engine),
 * built as a DECISION tool, not a data dump.
 *
 * Every row carries a single A–F edge grade (Bulkowski reward/risk × how
 * fresh the breakout is × room left to target × throwback risk) and a plain
 * verdict — BUY SETUP / WATCH / EXIT-AVOID / DANGER / PLAYED OUT — plus a
 * confluence flag when the proven quant breakout/reversal engine agrees.
 * A takeaway banner surfaces the day's best opportunities and dangers.
 *
 * Reads /api/chart-analysis/patterns. Clicking a row opens ChartDetailModal.
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ChartPatternScanRow } from '../types';
import { tutorialCodeFor } from '../tutorials';
import { Crosshair, TrendingUp, TrendingDown, Target, Info, Rocket, Trophy, GraduationCap, ShieldAlert } from 'lucide-react';

interface PatternScopeProps {
  apiUrl: string;
  onRowClick: (ticker: string) => void;
  onLearn?: (tutorialCode: string) => void;
}

type Tab = 'SETUPS' | 'WARNINGS' | 'CONFIRMED' | 'ALL';
type SortKey = 'edge' | 'target' | 'ticker' | 'price' | 'pattern';
type SortDir = 'asc' | 'desc';

// Verdict → colour + rank (for default ordering & the banner).
const VERDICT_META: Record<string, { cls: string; rank: number }> = {
  'BUY SETUP': { cls: 'bg-emerald-600 text-white', rank: 5 },
  WATCH: { cls: 'bg-blue-600 text-white', rank: 4 },
  'EXIT / AVOID': { cls: 'bg-orange-700 text-white', rank: 3 },
  DANGER: { cls: 'bg-red-700 text-white', rank: 6 },
  WAIT: { cls: 'bg-gray-600 text-gray-100', rank: 2 },
  'PLAYED OUT': { cls: 'bg-gray-800 text-gray-500', rank: 1 },
};

const gradeCls = (g: string | null) => {
  switch (g) {
    case 'A':
      return 'bg-emerald-500 text-black';
    case 'B':
      return 'bg-lime-500 text-black';
    case 'C':
      return 'bg-yellow-500 text-black';
    case 'D':
      return 'bg-orange-500 text-black';
    default:
      return 'bg-red-600 text-white';
  }
};

const biasBadge = (bias: string) =>
  bias === 'bullish'
    ? 'bg-emerald-700/40 text-emerald-300 border-emerald-700'
    : bias === 'bearish'
    ? 'bg-red-900/40 text-red-300 border-red-800'
    : 'bg-gray-700 text-gray-300 border-gray-600';

const isSetup = (r: ChartPatternScanRow) => r.verdict === 'BUY SETUP' || r.verdict === 'WATCH';
const isWarn = (r: ChartPatternScanRow) => r.has_dcb || r.verdict === 'DANGER' || r.verdict === 'EXIT / AVOID';

export default function PatternScope({ apiUrl, onRowClick, onLearn }: PatternScopeProps) {
  const [rows, setRows] = useState<ChartPatternScanRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('SETUPS');
  const [sortKey, setSortKey] = useState<SortKey>('edge');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await axios.get<ChartPatternScanRow[]>(`${apiUrl}/api/chart-analysis/patterns`);
        if (cancelled) return;
        setRows(Array.isArray(res.data) ? res.data : []);
      } catch {
        if (!cancelled) setError('Could not load chart-pattern scan');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetch();
    const id = setInterval(fetch, 60000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiUrl]);

  const setups = useMemo(() => rows.filter(isSetup), [rows]);
  const warnings = useMemo(() => rows.filter(isWarn), [rows]);

  const filtered = useMemo(() => {
    if (tab === 'SETUPS') return setups;
    if (tab === 'WARNINGS') return warnings;
    if (tab === 'CONFIRMED') return rows.filter((r) => r.status === 'confirmed');
    return rows;
  }, [rows, tab, setups, warnings]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let av: number | string = 0;
      let bv: number | string = 0;
      switch (sortKey) {
        case 'edge':
          av = a.edge;
          bv = b.edge;
          break;
        case 'target':
          av = a.room_pct ?? -999;
          bv = b.room_pct ?? -999;
          break;
        case 'ticker':
          av = a.ticker;
          bv = b.ticker;
          break;
        case 'price':
          av = a.price ?? 0;
          bv = b.price ?? 0;
          break;
        case 'pattern':
          av = a.top_name;
          bv = b.top_name;
          break;
      }
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === 'asc' ? (Number(av) || 0) - (Number(bv) || 0) : (Number(bv) || 0) - (Number(av) || 0);
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    else {
      setSortKey(k);
      setSortDir('desc');
    }
  };
  const arrow = (k: SortKey) => (sortKey === k ? (sortDir === 'desc' ? ' ▼' : ' ▲') : '');

  // The takeaway: best 3 setups + count of dangers.
  const topSetups = useMemo(
    () => [...setups].sort((a, b) => b.edge - a.edge).slice(0, 3),
    [setups],
  );
  const confluenceCount = rows.filter((r) => r.confluence).length;

  const TabBtn = ({ id, label, count, cls }: { id: Tab; label: string; count: number; cls?: string }) => (
    <button
      onClick={() => setTab(id)}
      className={`px-3 py-1 rounded text-xs ${
        tab === id ? cls ?? 'bg-cyan-700 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
      }`}
    >
      {label} ({count})
    </button>
  );

  return (
    <section className="bg-gray-800 rounded-lg p-6 border border-cyan-800/40 mb-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-cyan-300 flex items-center gap-2">
            <Crosshair className="w-5 h-5" /> Chart-Pattern Scanner
          </h2>
          <span className="text-[10px] text-gray-500 border border-cyan-800/60 rounded px-1.5 py-0.5 text-cyan-300/80">
            Bulkowski · graded setups + price targets
          </span>
          <button onClick={() => setShowHelp((x) => !x)} className="text-gray-500 hover:text-gray-200 ml-1" title="What is this?">
            <Info className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-1 flex-wrap">
          <TabBtn id="SETUPS" label="🎯 SETUPS" count={setups.length} cls="bg-emerald-700 text-white" />
          <TabBtn id="WARNINGS" label="⚠ WARNINGS" count={warnings.length} cls="bg-red-800 text-white" />
          <TabBtn id="CONFIRMED" label="CONFIRMED" count={rows.filter((r) => r.status === 'confirmed').length} />
          <TabBtn id="ALL" label="ALL" count={rows.length} />
        </div>
      </div>

      {/* ---- Takeaway banner: the decision at a glance ---- */}
      {!loading && rows.length > 0 && (
        <div className="mb-3 bg-gradient-to-r from-cyan-950/60 to-gray-900 border border-cyan-800/40 rounded-lg p-3">
          <div className="flex items-center gap-2 text-sm text-cyan-200 mb-2">
            <Trophy className="w-4 h-4 text-yellow-400" />
            <b>Today&apos;s takeaway:</b>
            <span className="text-gray-300">
              {setups.length} actionable setup{setups.length === 1 ? '' : 's'}
              {confluenceCount > 0 && (
                <> · <span className="text-sky-300">{confluenceCount} agree with the quant engine 🚀</span></>
              )}
              {warnings.length > 0 && (
                <> · <span className="text-red-300">{warnings.length} to avoid/exit ⚠</span></>
              )}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {topSetups.length === 0 && (
              <span className="text-xs text-gray-500">No high-edge bullish setups right now — the market isn&apos;t offering clean entries.</span>
            )}
            {topSetups.map((r) => (
              <button
                key={r.ticker}
                onClick={() => onRowClick(r.ticker)}
                className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded px-2.5 py-1.5 text-xs transition"
              >
                <span className={`w-5 h-5 rounded flex items-center justify-center font-black text-[11px] ${gradeCls(r.grade)}`}>
                  {r.grade}
                </span>
                <span className="font-bold text-cyan-300">{r.ticker}</span>
                <span className="text-gray-400">{r.top_name}</span>
                {r.room_pct != null && r.room_pct > 0 && (
                  <span className="text-emerald-400 font-bold">+{r.room_pct}%</span>
                )}
                {r.confluence && <Rocket className="w-3 h-3 text-sky-400" />}
              </button>
            ))}
          </div>
        </div>
      )}

      {showHelp && (
        <div className="mb-3 bg-gray-900 border border-cyan-800/40 rounded p-3 text-xs text-gray-300 space-y-2">
          <div>
            Each stock is graded <b className="text-emerald-400">A</b>–<b className="text-red-400">F</b> on
            <b> edge</b> = Bulkowski reward ÷ risk × how <b>fresh</b> the breakout is × <b>room</b> left to the
            price target × throwback risk. The <b>verdict</b> tells you what to do:
          </div>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 pl-1">
            <li><span className="px-1.5 py-0.5 rounded bg-emerald-600 text-white font-bold text-[10px]">BUY SETUP</span> fresh, high-edge bullish breakout with room to run</li>
            <li><span className="px-1.5 py-0.5 rounded bg-blue-600 text-white font-bold text-[10px]">WATCH</span> confirmed but middling edge / getting old</li>
            <li><span className="px-1.5 py-0.5 rounded bg-orange-700 text-white font-bold text-[10px]">EXIT / AVOID</span> confirmed topping pattern — reduce or stay away</li>
            <li><span className="px-1.5 py-0.5 rounded bg-red-700 text-white font-bold text-[10px]">DANGER</span> dead-cat bounce — falling knife, not a buy</li>
            <li><span className="px-1.5 py-0.5 rounded bg-gray-600 text-white font-bold text-[10px]">WAIT</span> shape complete but hasn&apos;t broken out yet</li>
            <li><span className="px-1.5 py-0.5 rounded bg-gray-800 text-gray-500 font-bold text-[10px]">PLAYED OUT</span> already ran to target — no edge left</li>
          </ul>
          <div>
            <span className="text-sky-300 font-bold">🚀 confluence</span> = your proven quant breakout/reversal
            engine ALSO fires here. That&apos;s the strongest agreement — it bumps the grade.
          </div>
        </div>
      )}

      {error && <div className="bg-red-900/40 border border-red-700 text-red-200 rounded p-2 text-xs mb-2">{error}</div>}

      <div className="overflow-x-auto">
        <table className="text-left text-sm min-w-[900px] w-full">
          <thead>
            <tr className="text-gray-500 text-xs border-b border-gray-700">
              <th onClick={() => toggleSort('edge')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300" title="A–F edge grade">GRADE{arrow('edge')}</th>
              <th className="pb-3 pr-3">VERDICT</th>
              <th onClick={() => toggleSort('ticker')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300">TICKER{arrow('ticker')}</th>
              <th onClick={() => toggleSort('price')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300">PRICE{arrow('price')}</th>
              <th onClick={() => toggleSort('pattern')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300">PATTERN{arrow('pattern')}</th>
              <th onClick={() => toggleSort('target')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300" title="Room to the measure-rule target">TARGET · ROOM{arrow('target')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const vm = VERDICT_META[r.verdict ?? 'WATCH'] ?? VERDICT_META.WATCH;
              const dim = r.verdict === 'PLAYED OUT';
              return (
                <tr
                  key={r.ticker}
                  className={`border-b border-gray-700/50 hover:bg-cyan-900/10 transition cursor-pointer h-11 ${dim ? 'opacity-45' : ''}`}
                  onClick={() => onRowClick(r.ticker)}
                  title={r.verdict_reason ?? 'Click for the full chart'}
                >
                  <td className="py-2 pr-3">
                    <span className={`inline-flex w-7 h-7 rounded items-center justify-center font-black ${gradeCls(r.grade)}`} title={`edge ${r.edge}/100`}>
                      {r.grade}
                    </span>
                  </td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${vm.cls}`}>{r.verdict}</span>
                  </td>
                  <td className="py-2 pr-3 font-bold text-cyan-300 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5">
                      {r.ticker}
                      {r.confluence && (
                        <span title={`Quant ${r.confluence} signal also fires here — strongest agreement`} className="text-[9px] bg-sky-600 text-white px-1 py-0.5 rounded font-bold">
                          🚀
                        </span>
                      )}
                      {r.has_dcb && <ShieldAlert className="w-3.5 h-3.5 text-red-400" />}
                    </span>
                  </td>
                  <td className="py-2 pr-3 whitespace-nowrap text-gray-200">{r.price?.toFixed(1) ?? '-'}</td>
                  <td className="py-2 pr-3 whitespace-nowrap text-gray-100">
                    <span className="inline-flex items-center gap-1.5">
                      {r.bias === 'bullish' ? (
                        <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                      ) : r.bias === 'bearish' ? (
                        <TrendingDown className="w-3.5 h-3.5 text-red-400" />
                      ) : null}
                      {r.top_name}
                      {r.pattern_count > 1 && <span className="text-gray-500 text-[10px]">+{r.pattern_count - 1}</span>}
                      {onLearn && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onLearn(tutorialCodeFor(r.top_code));
                          }}
                          title={`Learn about ${r.top_name}`}
                          className="text-indigo-400 hover:text-indigo-200"
                        >
                          <GraduationCap className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </span>
                  </td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {r.target != null ? (
                      <span className="inline-flex items-center gap-1">
                        <Target className="w-3 h-3 text-cyan-400" />
                        <span className="text-gray-300">{r.target}</span>
                        {r.room_pct != null &&
                          (r.room_pct <= 0 ? (
                            <span className="text-gray-500 text-xs">· reached</span>
                          ) : (
                            <span className={`text-xs font-bold ${r.bias === 'bearish' ? 'text-orange-300' : 'text-emerald-400'}`}>
                              · {r.bias === 'bearish' ? '' : '+'}
                              {r.room_pct}% room
                            </span>
                          ))}
                      </span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-600">
                  {loading
                    ? 'Scanning for chart patterns…'
                    : tab === 'SETUPS'
                    ? 'No high-edge bullish setups right now — no clean entries on offer.'
                    : tab === 'WARNINGS'
                    ? 'No dead-cat bounces or topping patterns flagged.'
                    : 'No active chart patterns in the latest session.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
