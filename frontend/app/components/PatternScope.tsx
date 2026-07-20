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
  const [sectorFilter, setSectorFilter] = useState<string>('ALL');

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

  // Distinct sectors present today (for the category filter), most-common first.
  const sectorList = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) {
      const s = r.sector || 'Unknown';
      counts.set(s, (counts.get(s) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [rows]);

  // Sector filter applies FIRST, so the tab counts reflect the chosen category.
  const sectorRows = useMemo(
    () => (sectorFilter === 'ALL' ? rows : rows.filter((r) => (r.sector || 'Unknown') === sectorFilter)),
    [rows, sectorFilter],
  );

  const setups = useMemo(() => sectorRows.filter(isSetup), [sectorRows]);
  const warnings = useMemo(() => sectorRows.filter(isWarn), [sectorRows]);

  const filtered = useMemo(() => {
    if (tab === 'SETUPS') return setups;
    if (tab === 'WARNINGS') return warnings;
    if (tab === 'CONFIRMED') return sectorRows.filter((r) => r.status === 'confirmed');
    return sectorRows;
  }, [sectorRows, tab, setups, warnings]);

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
          av = a.rebound_room_pct ?? a.room_pct ?? -999;
          bv = b.rebound_room_pct ?? b.room_pct ?? -999;
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
  // Only reversal confluence counts — it's the one with a validated net edge.
  const confluenceCount = sectorRows.filter((r) => r.confluence === 'reversal').length;

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
        <div className="flex gap-1 flex-wrap items-center">
          {/* Category (sector) filter */}
          <select
            value={sectorFilter}
            onChange={(e) => setSectorFilter(e.target.value)}
            title="Filter by sector / category"
            className="bg-gray-700 text-gray-200 text-xs rounded px-2 py-1 border border-gray-600 mr-1 max-w-[170px]"
          >
            <option value="ALL">All sectors ({rows.length})</option>
            {sectorList.map(([s, n]) => (
              <option key={s} value={s}>{s} ({n})</option>
            ))}
          </select>
          <TabBtn id="SETUPS" label="🎯 SETUPS" count={setups.length} cls="bg-emerald-700 text-white" />
          <TabBtn id="WARNINGS" label="⚠ WARNINGS" count={warnings.length} cls="bg-red-800 text-white" />
          <TabBtn id="CONFIRMED" label="CONFIRMED" count={sectorRows.filter((r) => r.status === 'confirmed').length} />
          <TabBtn id="ALL" label="ALL" count={sectorRows.length} />
        </div>
      </div>
      {sectorFilter !== 'ALL' && (
        <div className="mb-2 text-xs text-cyan-300/80">
          Showing <b>{sectorFilter}</b> only ·{' '}
          <button onClick={() => setSectorFilter('ALL')} className="underline hover:text-cyan-200">clear filter</button>
        </div>
      )}

      {/* ---- Takeaway banner: the decision at a glance ---- */}
      {!loading && rows.length > 0 && (
        <div className="mb-3 bg-gradient-to-r from-cyan-950/60 to-gray-900 border border-cyan-800/40 rounded-lg p-3">
          <div className="flex items-center gap-2 text-sm text-cyan-200 mb-2">
            <Trophy className="w-4 h-4 text-yellow-400" />
            <b>Today&apos;s takeaway:</b>
            <span className="text-gray-300">
              {setups.length} actionable setup{setups.length === 1 ? '' : 's'}
              {confluenceCount > 0 && (
                <> · <span className="text-emerald-300">{confluenceCount} with quant REVERSAL confluence 🚀</span></>
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
                {(() => {
                  const room = r.rebound_room_pct ?? r.room_pct;
                  return room != null && room > 0 ? (
                    <span className="text-emerald-400 font-bold">+{room}%</span>
                  ) : null;
                })()}
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
          <div className="border-t border-gray-700 pt-2">
            <b className="text-gray-200">DSE reality</b> — what buying this pattern&apos;s confirmation and holding
            <b> 20 trading days</b> actually returned on DSE (2023–26, net of 0.8% costs).{' '}
            <span className="text-emerald-400 font-bold">+2.2% net · 51% win</span> = the average trade made +2.2%
            after costs and 51% of trades were profitable — a small real edge.{' '}
            <span className="text-red-400 font-bold">−0.8% net · 43% win</span> = the average trade LOST money and
            most trades lost — the pattern looks bullish but doesn&apos;t pay here.{' '}
            <span className="text-amber-400 font-bold">unproven</span> = too few local occurrences to measure; the
            book stats and target are US numbers, not validated on DSE.
          </div>
          <div className="border-t border-gray-700 pt-2">
            <b className="text-gray-200">⚠ risk tags</b> — live-state checks from the decliner study (how tops look
            the day before they fall). These fire on <b>price</b>, not volume:
            <ul className="list-disc pl-5 mt-1 space-y-0.5">
              <li><b className="text-red-300">OVERBOUGHT RSI ≥65</b> — price rose too fast vs its own history. On DSE
                that mean-reverts: buyers are exhausted, not &quot;trending&quot;.</li>
              <li><b className="text-red-300">ALREADY RAN +X%/20d</b> — the move you&apos;d be buying already happened;
                you&apos;d be the exit liquidity.</li>
              <li><b className="text-red-300">STRETCHED above 20-SMA</b> — price far above its average snaps back
                more often than it keeps going.</li>
              <li><b className="text-red-300">CLIMAX VOLUME ≥3×</b> — huge volume AFTER a run is distribution
                (holders selling to latecomers), the opposite of quiet accumulation volume BEFORE a move.</li>
              <li><b className="text-red-300">THIN</b> — too few shares trade per day to enter/exit at fair prices.</li>
              <li><b className="text-red-300">NO QUANT DATA</b> — the quant engine skipped this ticker (too thin or
                broken data), so none of the checks above could even run. Treat as untracked, not as safe.</li>
            </ul>
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
              <th onClick={() => toggleSort('target')} className="pb-3 pr-3 cursor-pointer hover:text-gray-300" title="Upside objective — the next overhead resistance the price must reclaim. This is the SAME target shown on the chart when you open a row (the pattern's own measure-rule projection lives in the pattern card).">TARGET · ROOM{arrow('target')}</th>
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
                  <td className="py-2 pr-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${vm.cls}`}>{r.verdict}</span>
                    {r.verdict_reason && (
                      <div className="text-[10px] text-gray-500 mt-0.5 max-w-[220px] truncate" title={r.verdict_reason}>
                        {r.verdict_reason}
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-3 font-bold text-cyan-300 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5">
                      {r.ticker}
                      {r.confluence === 'reversal' && (
                        <span title="Quant REVERSAL signal also fires here — the one confluence with a validated net edge (+5.1%/trade, 65% win)" className="text-[9px] bg-emerald-600 text-white px-1 py-0.5 rounded font-bold">
                          🚀 REV
                        </span>
                      )}
                      {r.confluence === 'breakout' && (
                        <span title="Quant breakout also fires here — informational only (breakout nets ~+0.3%/trade after costs, no edge boost applied)" className="text-[9px] bg-gray-600 text-gray-200 px-1 py-0.5 rounded font-bold">
                          BRK
                        </span>
                      )}
                      {r.has_dcb && <ShieldAlert className="w-3.5 h-3.5 text-red-400" />}
                    </span>
                    {r.sector && (
                      <div className="text-[10px] text-gray-500 mt-0.5 font-normal">{r.sector}</div>
                    )}
                    {(r.risk_tags?.length ?? 0) > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1 max-w-[240px]"
                        title="Live-state warnings — this is how tops look the day before they fall (see the decliner study). A rising chart + big target does NOT override these.">
                        {r.risk_tags!.map((t) => (
                          <span key={t} className="text-[9px] bg-red-900/50 text-red-300 border border-red-800/60 px-1 py-0.5 rounded font-bold whitespace-nowrap">
                            ⚠ {t}
                          </span>
                        ))}
                      </div>
                    )}
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
                    {(() => {
                      // THE canonical target — the ONE value the chart also
                      // headlines (backend `rebound_target`, identical across
                      // every view; verified equal for all tickers). We do NOT
                      // fall back to the Bulkowski measure-rule target here: that
                      // is a different number and mixing it in is exactly what made
                      // the row disagree with the chart. When there's no canonical
                      // target (thin history) we show "—", never a second guess.
                      // The measure-rule projection still lives in the pattern card.
                      const tgt = r.rebound_target ?? null;
                      const room = r.rebound_room_pct ?? null;
                      if (tgt == null) return <span className="text-gray-600">—</span>;
                      return (
                        <span className="inline-flex items-center gap-1">
                          <Target className="w-3 h-3 text-cyan-400" />
                          <span className="text-gray-300">{tgt}</span>
                          {room != null &&
                            (room <= 0 ? (
                              <span className="text-gray-500 text-xs">· reached</span>
                            ) : (
                              <span className="text-xs font-bold text-emerald-400">
                                · +{room}% room
                              </span>
                            ))}
                        </span>
                      );
                    })()}
                    {r.bias === 'bullish' && (r.dse_stats ? (
                      <div className={`text-[10px] mt-0.5 font-bold ${r.dse_stats.net_20d > 0 ? 'text-emerald-400/80' : 'text-red-400/90'}`}
                        title={`What buying this pattern's confirmation ACTUALLY returned on DSE (point-in-time 2023–26, +20 trading days, net of 0.8% commission, n=${r.dse_stats.n}). The target above is the US book's projection — this is the local reality.`}>
                        DSE reality: {r.dse_stats.net_20d > 0 ? '+' : ''}{r.dse_stats.net_20d}% net · {r.dse_stats.win_pct}% win
                      </div>
                    ) : (
                      <div className="text-[10px] mt-0.5 font-bold text-amber-400/80"
                        title="Too few historical occurrences of this pattern on DSE (2023–26) to measure what buying it actually returns. The US book stats and the target are UNVERIFIED here — don't assume they transfer.">
                        DSE reality: unproven — no local backtest data
                      </div>
                    ))}
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
