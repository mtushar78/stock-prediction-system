'use client';

/**
 * ChartDetailModal — full chart-oriented breakdown for one ticker.
 *
 * Two independent engines are shown together:
 *   1. Candlestick engine (src/chart_analyzer.py) — 1/2/3-bar patterns.
 *   2. Chart-pattern engine (src/pattern_analyzer.py) — Bulkowski multi-week
 *      formations (double bottoms, H&S, triangles, flags, dead-cat bounce…)
 *      with real win-rate statistics + measure-rule price targets.
 *
 * The chart draws the selected chart pattern's geometry directly:
 * necklines / trend lines / support-resistance rails as line segments, and
 * the measure-rule target + stop as labelled price lines.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
  LineStyle,
  ColorType,
  CrosshairMode,
  IChartApi,
  ISeriesApi,
  Time,
  SeriesMarker,
} from 'lightweight-charts';
import {
  ChartSignal,
  ChartOhlcvBar,
  ChartPattern,
  DetectedChartPattern,
} from '../types';
import { tutorialCodeFor } from '../tutorials';
import TutorialModal from './TutorialModal';
import { X, AlertCircle, Info, AlertTriangle, Target, Crosshair, TrendingUp, TrendingDown, GraduationCap } from 'lucide-react';

interface ChartDetailModalProps {
  apiUrl: string;
  ticker: string;
  onClose: () => void;
}

const biasColor = (bias: string) =>
  bias === 'bullish' ? '#10b981' : bias === 'bearish' ? '#ef4444' : '#9ca3af';

const confidenceClass = (c: string) =>
  c === 'HIGH'
    ? 'bg-purple-700 text-white'
    : c === 'MEDIUM'
    ? 'bg-blue-700 text-white'
    : c === 'LOW'
    ? 'bg-gray-600 text-gray-200'
    : 'bg-gray-800 text-gray-500';

const gradeCls = (g?: string) =>
  g === 'A'
    ? 'bg-emerald-500 text-black'
    : g === 'B'
    ? 'bg-lime-500 text-black'
    : g === 'C'
    ? 'bg-yellow-500 text-black'
    : g === 'D'
    ? 'bg-orange-500 text-black'
    : 'bg-red-600 text-white';

const verdictCls = (v?: string) =>
  v === 'BUY SETUP'
    ? 'bg-emerald-600 text-white'
    : v === 'WATCH'
    ? 'bg-blue-600 text-white'
    : v === 'EXIT / AVOID'
    ? 'bg-orange-700 text-white'
    : v === 'DANGER'
    ? 'bg-red-700 text-white'
    : v === 'PLAYED OUT'
    ? 'bg-gray-800 text-gray-500'
    : 'bg-gray-600 text-gray-100';

// ------------------------------------------------------------------ //
// BOTTOM LINE — the one plain-English answer to "should I buy this?"
//
// The user's problem: the list only flags DANGERS, and the header badge
// shows candlestick "confidence" (how clean the shape is) which reads like
// a buy score but is NOT one. So a stock with no warning + a HIGH badge
// looks buyable when the engine never said so. This synthesizes the top
// chart pattern's verdict into one explicit call — positive OR negative —
// so absence-of-warning is never mistaken for a green light.
// ------------------------------------------------------------------ //
type Tone = 'good' | 'watch' | 'bad' | 'neutral';
interface BottomLine {
  action: string;      // short chip, e.g. "WATCH ONLY"
  tone: Tone;
  headline: string;    // one sentence answering buy-or-not
}

const TONE_CLS: Record<Tone, { box: string; chip: string; icon: string }> = {
  good: { box: 'bg-emerald-950/60 border-emerald-600', chip: 'bg-emerald-600 text-white', icon: 'text-emerald-400' },
  watch: { box: 'bg-amber-950/50 border-amber-600/70', chip: 'bg-amber-500 text-black', icon: 'text-amber-400' },
  bad: { box: 'bg-red-950/70 border-red-600', chip: 'bg-red-700 text-white', icon: 'text-red-400' },
  neutral: { box: 'bg-gray-800 border-gray-600', chip: 'bg-gray-600 text-gray-100', icon: 'text-gray-400' },
};

function bottomLineFor(signal: ChartSignal, top: DetectedChartPattern | undefined): BottomLine {
  // No multi-week chart pattern at all — only candlesticks (or nothing).
  if (!top) {
    const hasCandles = (signal.patterns?.length ?? 0) > 0;
    if (hasCandles) {
      return {
        action: 'NOT A BUY',
        tone: 'neutral',
        headline:
          'Only short-term candlestick signals here — no multi-week chart pattern. Candlesticks alone ' +
          'have no proven buy edge on DSE; treat them as context, not a reason to buy.',
      };
    }
    return {
      action: 'NOTHING HERE',
      tone: 'neutral',
      headline: 'No actionable chart pattern right now — nothing to buy or avoid on this chart.',
    };
  }

  const dseBad = top.dse_stats && top.dse_stats.net_20d <= 0;
  switch (top.verdict) {
    case 'BUY SETUP':
      return {
        action: 'BUYABLE',
        tone: 'good',
        headline:
          `Buyable — ${top.name} is a fresh, high-edge breakout and the proven quant engine agrees (🚀 REV). ` +
          'Buy near support and respect the stop.',
      };
    case 'WATCH':
      return {
        action: 'WATCH — NOT A BUY YET',
        tone: 'watch',
        headline:
          `The ${top.name} is real and confirmed, but a bullish chart pattern ALONE has no proven edge on DSE` +
          (dseBad ? ` (this pattern historically returned ${top.dse_stats!.net_20d}% net at +20d here)` : '') +
          '. Do NOT buy on the pattern by itself — it only becomes a buy on a day the quant Reversal signal also fires (🚀 REV badge).',
      };
    case 'EXIT / AVOID':
      return {
        action: 'DO NOT BUY',
        tone: 'bad',
        headline: `Do not buy — ${top.name} is a confirmed topping pattern with downside to target. Exit or reduce if you already hold.`,
      };
    case 'DANGER':
      return {
        action: 'AVOID',
        tone: 'bad',
        headline: `Avoid — ${top.name}: a falling knife that usually breaks lower. Not a buy for ~6 months.`,
      };
    case 'WAIT':
      return {
        action: 'WAIT',
        tone: 'neutral',
        headline: `Wait — the ${top.name} shape is complete but has NOT broken out yet. No action until it closes beyond the line.`,
      };
    case 'PLAYED OUT':
      return {
        action: 'NO EDGE LEFT',
        tone: 'neutral',
        headline: `The move already ran to its target — the easy money is gone. Nothing to buy here.`,
      };
    default:
      return {
        action: 'NO CLEAR EDGE',
        tone: 'neutral',
        headline: `${top.name} detected, but direction isn't resolved into a buy or avoid yet.`,
      };
  }
}

// Colours for the geometry we overlay on the candles.
const LINE_COLORS: Record<string, string> = {
  neckline: '#f59e0b',
  resistance: '#ef4444',
  support: '#10b981',
  trend: '#a78bfa',
  target: '#22d3ee',
  stop: '#f43f5e',
};

const patternBars = (name: string): number => {
  if (name === 'Morning Star' || name === 'Three White Soldiers') return 3;
  if (
    name === 'Bullish Engulfing' ||
    name === 'Piercing Line' ||
    name === 'Bullish Harami'
  )
    return 2;
  return 1;
};

/**
 * Derive a plain target + support from real price structure so EVERY chart
 * shows a target — not only the ones with a Bulkowski pattern. Uses swing
 * pivots over the visible history:
 *   • target  = nearest overhead swing high ≥2% above price (the next supply
 *               zone / first objective); if price is near the window high with
 *               nothing meaningful above, the window peak itself (the recovery
 *               objective a fallen-and-turning stock is climbing back toward).
 *   • support = nearest swing low below price (where to expect a bounce / the
 *               level whose loss breaks the turn).
 */
function deriveLevels(
  bars: { high: number; low: number; close: number }[],
  price: number,
): { target: number | null; support: number | null } {
  if (bars.length < 12 || !price) return { target: null, support: null };
  const L = 3, R = 3;
  const highs: number[] = [];
  const lows: number[] = [];
  for (let i = L; i < bars.length - R; i++) {
    const h = bars[i].high, l = bars[i].low;
    let isHigh = true, isLow = true;
    for (let j = i - L; j <= i + R; j++) {
      if (bars[j].high > h) isHigh = false;
      if (bars[j].low < l) isLow = false;
    }
    if (isHigh) highs.push(h);
    if (isLow) lows.push(l);
  }
  const above = highs.filter((h) => h > price * 1.02).sort((a, b) => a - b);
  let target: number | null = above.length ? above[0] : null;
  if (target == null) {
    const maxH = Math.max(...bars.map((b) => b.high));
    if (maxH > price * 1.02) target = maxH; // recovery objective (window peak)
  }
  const below = lows.filter((l) => l < price * 0.99).sort((a, b) => b - a);
  const support: number | null = below.length ? below[0] : null;
  return {
    target: target != null ? Number(target.toFixed(2)) : null,
    support: support != null ? Number(support.toFixed(2)) : null,
  };
}

/**
 * ChartAnalysisBody — the full chart-analysis content (data fetch, chart,
 * pattern cards, bottom-line verdict) with NO modal chrome. Used both by
 * ChartDetailModal (wrapped in an overlay) and embedded directly at the
 * bottom of the /analyze page.
 */
export function ChartAnalysisBody({ apiUrl, ticker }: { apiUrl: string; ticker: string }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const [signal, setSignal] = useState<ChartSignal | null>(null);
  const [ohlcv, setOhlcv] = useState<ChartOhlcvBar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Which chart pattern's geometry is drawn on the candles.
  const [activePattern, setActivePattern] = useState(0);
  // Tutorial overlay for "learn this pattern".
  const [learnCode, setLearnCode] = useState<string | null>(null);

  const chartPatterns: DetectedChartPattern[] = useMemo(
    () => signal?.chart_patterns ?? [],
    [signal],
  );
  const summary = signal?.chart_pattern_summary ?? null;

  // Bars with missing OHLC are dropped before rendering — surface that instead
  // of silently drawing a shorter chart (pattern geometry can look misaligned).
  const droppedBars = useMemo(
    () => ohlcv.filter((b) => b.open === null || b.high === null || b.low === null || b.close === null).length,
    [ohlcv],
  );

  // Structural target + support drawn on EVERY chart (see deriveLevels).
  const autoLevels = useMemo(() => {
    const bars = ohlcv
      .filter((b) => b.high !== null && b.low !== null && b.close !== null)
      .map((b) => ({ high: b.high as number, low: b.low as number, close: b.close as number }));
    if (bars.length < 12) return { target: null, support: null };
    return deriveLevels(bars, bars[bars.length - 1].close);
  }, [ohlcv]);
  const lastClose = useMemo(() => {
    const c = ohlcv.filter((b) => b.close !== null);
    return c.length ? (c[c.length - 1].close as number) : null;
  }, [ohlcv]);

  // Fetch signal + OHLCV in parallel. 300 bars so multi-month patterns fit.
  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        setLoading(true);
        setError(null);
        const [sigRes, ohlcvRes] = await Promise.all([
          axios.get<ChartSignal>(`${apiUrl}/api/chart-analysis/${ticker}`),
          axios.get<ChartOhlcvBar[]>(`${apiUrl}/api/chart-analysis/${ticker}/ohlcv?days=300`),
        ]);
        if (cancelled) return;
        setSignal(sigRes.data);
        setOhlcv(Array.isArray(ohlcvRes.data) ? ohlcvRes.data : []);
        setActivePattern(0);
      } catch (e: unknown) {
        if (cancelled) return;
        const msg =
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          `Failed to load chart for ${ticker}`;
        setError(typeof msg === 'string' ? msg : `Failed to load chart for ${ticker}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAll();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, ticker]);

  // Build the chart whenever data or the selected pattern changes.
  useEffect(() => {
    if (!chartRef.current || !signal || ohlcv.length < 5) return;

    if (chartInstanceRef.current) {
      try {
        chartInstanceRef.current.remove();
      } catch {
        /* already disposed */
      }
      chartInstanceRef.current = null;
    }

    const container = chartRef.current;
    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#0b1220' },
        textColor: '#d1d5db',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      rightPriceScale: {
        borderColor: '#374151',
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: { borderColor: '#374151', timeVisible: false, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    chartInstanceRef.current = chart;

    const candleSeries: ISeriesApi<'Candlestick'> = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    const cleanBars = ohlcv.filter(
      (b) => b.open !== null && b.high !== null && b.low !== null && b.close !== null,
    );
    const barTimes = new Set(cleanBars.map((b) => b.date));

    candleSeries.setData(
      cleanBars.map((b) => ({
        time: b.date as Time,
        open: b.open as number,
        high: b.high as number,
        low: b.low as number,
        close: b.close as number,
      })),
    );

    // Volume histogram
    const volSeries: ISeriesApi<'Histogram'> = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      color: '#3b82f6',
    });
    chart.priceScale('vol').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
      borderVisible: false,
    });
    volSeries.setData(
      cleanBars.map((b) => ({
        time: b.date as Time,
        value: b.volume || 0,
        color: (b.close ?? 0) >= (b.open ?? 0) ? 'rgba(16,185,129,0.5)' : 'rgba(239,68,68,0.5)',
      })),
    );

    // 50-day moving average
    if (cleanBars.length >= 20) {
      const smaSeries = chart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 1,
        lineStyle: LineStyle.Solid,
        title: 'MA',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      const period = Math.min(50, cleanBars.length);
      const smaData: { time: Time; value: number }[] = [];
      let sum = 0;
      const closes = cleanBars.map((b) => b.close as number);
      for (let i = 0; i < closes.length; i++) {
        sum += closes[i];
        if (i >= period) sum -= closes[i - period];
        if (i >= period - 1) smaData.push({ time: cleanBars[i].date as Time, value: sum / period });
      }
      smaSeries.setData(smaData);
    }

    const markers: SeriesMarker<Time>[] = [];

    // ---- Draw the ACTIVE chart pattern's geometry ----
    const cp = chartPatterns[activePattern];
    // A pattern's horizontal target/stop are its MEASURE-RULE projection, which
    // only applies once the pattern CONFIRMS (breaks out). While it is still
    // "forming" that target is conditional — and often bearish / low-confidence
    // — so it must NOT be drawn as THE chart target (that's what made a forming
    // bearish Rising Wedge show "target 99" while the Rebounds list showed the
    // +14% upside objective). Until confirmation we fall back to the structural
    // objective (deriveLevels) — the same "next overhead resistance" Rebounds
    // headlines — so the two views agree.
    const cpConfirmed = cp?.status === 'confirmed';
    if (cp) {
      cp.lines.forEach((ln) => {
        const pts = ln.points
          .filter((p) => barTimes.has(p.date))
          .map((p) => ({ time: p.date as Time, value: p.price }));
        if (ln.kind === 'target' || ln.kind === 'stop') {
          // Labelled horizontal price line — only once the pattern confirms.
          if (cpConfirmed && cp.target != null && ln.kind === 'target') {
            candleSeries.createPriceLine({
              price: cp.target,
              color: LINE_COLORS.target,
              lineWidth: 2,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: `target ${cp.target}`,
            });
          }
          if (cpConfirmed && cp.stop != null && ln.kind === 'stop') {
            candleSeries.createPriceLine({
              price: cp.stop,
              color: LINE_COLORS.stop,
              lineWidth: 1,
              lineStyle: LineStyle.Dotted,
              axisLabelVisible: true,
              title: `stop ${cp.stop}`,
            });
          }
          return;
        }
        if (pts.length >= 2) {
          const seg = chart.addSeries(LineSeries, {
            color: LINE_COLORS[ln.kind] ?? '#9ca3af',
            lineWidth: 2,
            lineStyle: ln.kind === 'neckline' ? LineStyle.Dashed : LineStyle.Solid,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          seg.setData(pts);
        }
      });
      // target/stop when not present as an explicit line entry (confirmed only)
      if (cpConfirmed && cp.target != null && !cp.lines.some((l) => l.kind === 'target')) {
        candleSeries.createPriceLine({
          price: cp.target,
          color: LINE_COLORS.target,
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `target ${cp.target}`,
        });
      }
      // key-point markers
      cp.key_points.forEach((k) => {
        if (!barTimes.has(k.date)) return;
        markers.push({
          time: k.date as Time,
          position: cp.bias === 'bullish' ? 'belowBar' : 'aboveBar',
          color: biasColor(cp.bias),
          shape: 'circle',
          text: k.label ?? '',
        });
      });
    }

    // ---- Structural target + support (drawn when the active pattern doesn't
    //      already provide them) so every chart shows an objective ----
    // Prefer the backend rebound_target (identical to the Rebounds list) over
    // the local swing-high heuristic so the chart line matches the row.
    const structTarget = signal?.rebound_target != null ? signal.rebound_target : autoLevels.target;
    if (!(cpConfirmed && cp && cp.target != null) && structTarget != null) {
      candleSeries.createPriceLine({
        price: structTarget,
        color: LINE_COLORS.target,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `target ${structTarget}`,
      });
    }
    if (!(cpConfirmed && cp && cp.stop != null) && autoLevels.support != null) {
      candleSeries.createPriceLine({
        price: autoLevels.support,
        color: LINE_COLORS.support,
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: `support ${autoLevels.support}`,
      });
    }

    // ---- Candlestick pattern markers (latest bars) ----
    const lastIdx = cleanBars.length - 1;
    signal.patterns.forEach((p) => {
      const span = patternBars(p.name);
      const startIdx = lastIdx - (span - 1);
      if (startIdx < 0 || startIdx > lastIdx) return;
      const bar = cleanBars[startIdx];
      markers.push({
        time: bar.date as Time,
        position: p.bias === 'bullish' ? 'belowBar' : 'aboveBar',
        color: biasColor(p.bias),
        shape: p.bias === 'bullish' ? 'arrowUp' : 'arrowDown',
        text: p.name,
      });
    });

    if (markers.length > 0) createSeriesMarkers(candleSeries, markers);

    chart.timeScale().fitContent();

    return () => {
      if (chartInstanceRef.current) {
        try {
          chartInstanceRef.current.remove();
        } catch {
          /* ignore */
        }
        chartInstanceRef.current = null;
      }
    };
  }, [signal, ohlcv, chartPatterns, activePattern, autoLevels]);

  const trendLabel = signal?.context?.trend ?? '?';
  const trendColor =
    trendLabel === 'uptrend'
      ? 'text-green-400'
      : trendLabel === 'downtrend'
      ? 'text-red-400'
      : 'text-yellow-400';

  // The target/support to headline: a CONFIRMED pattern's own measure-rule
  // target wins; while it's only forming that target is conditional (and often
  // a bearish downside projection), so we headline the structural upside
  // objective instead — keeping the chart in agreement with the Rebounds list.
  const activeCp = chartPatterns[activePattern];
  const activeCpConfirmed = activeCp?.status === 'confirmed';
  // Structural objective = the backend rebound_target (same function + data as
  // the Rebounds list) so the chart headline matches the row; fall back to the
  // local swing-high estimate only if the backend didn't supply one.
  const structTarget = signal?.rebound_target != null ? signal.rebound_target : autoLevels.target;
  const dispTarget = activeCpConfirmed && activeCp.target != null ? activeCp.target : structTarget;
  const dispStop = activeCpConfirmed && activeCp.stop != null ? activeCp.stop : autoLevels.support;
  const targetPct = dispTarget != null && lastClose ? ((dispTarget - lastClose) / lastClose) * 100 : null;
  const stopPct = dispStop != null && lastClose ? ((dispStop - lastClose) / lastClose) * 100 : null;

  return (
    <>
        {/* Body */}
        <div className="p-4 space-y-4">
          {/* Signal-clarity / bias / date strip (was the modal header) */}
          {signal && (
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className={`px-2 py-0.5 rounded text-xs font-bold ${confidenceClass(signal.confidence)}`}
                title="How clearly a candlestick pattern is formed on the latest bars — NOT a buy/sell call. Read the BOTTOM LINE banner below for whether to buy."
              >
                {signal.confidence} <span className="font-normal opacity-70">signal clarity</span>
              </span>
              <span className="text-sm text-gray-400">
                bias{' '}
                <span className="font-bold" style={{ color: biasColor(signal.overall_bias) }}>
                  {signal.overall_bias.toUpperCase()}
                </span>
              </span>
              {signal.analysis_date && (
                <span className="text-xs text-gray-500">{signal.analysis_date}</span>
              )}
            </div>
          )}

          {loading && <div className="text-center text-gray-400 py-12">Loading chart…</div>}
          {error && (
            <div className="bg-red-900/40 border border-red-700 text-red-200 rounded p-3 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" /> {error}
            </div>
          )}

          {/* Stale-analysis guard — a verdict computed on old bars is not a
              verdict on today's price. Surface the age loudly. */}
          {!loading && !error && signal?.analysis_date && (() => {
            const days = Math.floor((Date.now() - Date.parse(signal.analysis_date)) / 86400000);
            if (!(days > 5)) return null;
            return (
              <div className="bg-amber-900/40 border border-amber-600 text-amber-100 rounded p-3 text-sm flex items-start gap-2">
                <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0 text-amber-400" />
                <div>
                  <b>Stale analysis — last bar is {signal.analysis_date} ({days} days old).</b>{' '}
                  Every verdict below was computed on that data, not today&apos;s price. Patterns may have
                  broken out, failed, or expired since. Refresh the price data before acting.
                </div>
              </div>
            );
          })()}

          {/* ---- BOTTOM LINE: the one plain answer — buy or not? ---- */}
          {!loading && !error && signal && (() => {
            const bl = bottomLineFor(signal, chartPatterns[0]);
            const t = TONE_CLS[bl.tone];
            return (
              <div className={`rounded-lg border p-3 flex items-start gap-3 ${t.box}`}>
                {bl.tone === 'good' ? (
                  <TrendingUp className={`w-6 h-6 mt-0.5 shrink-0 ${t.icon}`} />
                ) : bl.tone === 'bad' ? (
                  <AlertTriangle className={`w-6 h-6 mt-0.5 shrink-0 ${t.icon}`} />
                ) : (
                  <Info className={`w-6 h-6 mt-0.5 shrink-0 ${t.icon}`} />
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold">Bottom line</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-black ${t.chip}`}>{bl.action}</span>
                    {signal.confluence === 'reversal' && (
                      <span className="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded font-bold"
                        title="Quant REVERSAL signal also fires here — the one confluence with a validated net edge (+5.1%/trade, 65% win)">
                        🚀 REV confluence
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-100">{bl.headline}</div>
                  {(signal.risk_tags?.length ?? 0) > 0 && bl.tone !== 'bad' && (
                    <div className="flex flex-wrap gap-1 mt-1.5"
                      title="Live-state warnings — this is how tops look the day before they fall. A rising chart + big target does NOT override these.">
                      {signal.risk_tags!.map((tag) => (
                        <span key={tag} className="text-[10px] bg-red-900/50 text-red-300 border border-red-800/60 px-1.5 py-0.5 rounded font-bold whitespace-nowrap">
                          ⚠ {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {!loading && droppedBars > 0 && (
            <div className="bg-amber-900/30 border border-amber-700/50 text-amber-200/90 rounded p-2 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {droppedBars} bar{droppedBars === 1 ? '' : 's'} with missing price data were omitted from this
              chart — pattern lines/targets touching those dates may look incomplete.
            </div>
          )}

          {/* Dead-cat-bounce warning banner */}
          {summary?.has_dead_cat_bounce && (
            <div className="bg-red-950/70 border border-red-600 text-red-100 rounded p-3 flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0 text-red-400" />
              <div className="text-sm">
                <b>Dead-Cat-Bounce warning.</b> A ≥15% one-session plunge fired recently. Bulkowski’s
                data: price breaks below the event low ~67% of the time and falls a further ~18%. Treat
                rallies as exits — and avoid bullish setups here for ~6 months.
              </div>
            </div>
          )}

          {/* Chart-pattern summary headline */}
          {summary && !summary.has_dead_cat_bounce && (
            <div className="bg-gray-800 border border-purple-800/40 rounded p-3 text-sm text-gray-200 flex items-start gap-2">
              <Info className="w-4 h-4 mt-0.5 text-purple-300 shrink-0" />
              <span>{summary.headline}</span>
            </div>
          )}

          {/* Wyckoff structure context — annotation only, never a buy call */}
          {signal?.wyckoff?.in_structure && (
            <div className="bg-gray-800 border border-teal-800/50 rounded p-3 text-xs">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-teal-300 font-bold text-sm">Wyckoff structure</span>
                <span className="text-gray-500">accumulation trading range</span>
                {signal.wyckoff.event && (
                  <span className="text-[10px] bg-teal-800 text-teal-100 px-1.5 py-0.5 rounded font-bold"
                    title="Event detected on the latest bar — context only, not a buy signal">
                    {signal.wyckoff.event.replace('_', ' ')}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-gray-300">
                <div><span className="text-gray-500">Support </span>{signal.wyckoff.checks.support ?? '–'}</div>
                <div><span className="text-gray-500">Resistance (creek) </span>{signal.wyckoff.checks.resistance ?? '–'}</div>
                <div><span className="text-gray-500">Range height </span>{signal.wyckoff.checks.range_height_pct != null ? `${signal.wyckoff.checks.range_height_pct}%` : '–'}</div>
                <div><span className="text-gray-500">Decline into range </span>{signal.wyckoff.checks.decline_into_range_pct != null ? `${signal.wyckoff.checks.decline_into_range_pct}%` : '–'}</div>
                {signal.wyckoff.checks.spring_low != null && (
                  <>
                    <div><span className="text-gray-500">Spring low </span>{signal.wyckoff.checks.spring_low}</div>
                    <div><span className="text-gray-500">Spring volume </span>{signal.wyckoff.checks.spring_rvol != null ? `${signal.wyckoff.checks.spring_rvol}×` : '–'}
                      {signal.wyckoff.checks.spring_type ? ` (type #${signal.wyckoff.checks.spring_type})` : ''}</div>
                  </>
                )}
              </div>
              <div className="text-[10px] text-gray-500 mt-1.5">{signal.wyckoff.note}</div>
            </div>
          )}

          {/* Context strip */}
          {signal && signal.context && Object.keys(signal.context).length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-gray-500">TREND</div>
                <div className={`font-bold ${trendColor}`}>
                  {trendLabel.toUpperCase()}{' '}
                  <span className="text-gray-500 text-[10px]">
                    ({signal.context?.trend_slope_pct?.toFixed?.(1) ?? '0.0'}%)
                  </span>
                </div>
              </div>
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-gray-500">RVOL</div>
                <div className="text-yellow-300 font-bold">{signal.context?.rvol?.toFixed?.(2) ?? '-'}×</div>
              </div>
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-gray-500">SUPPORT / RESIST</div>
                <div className="text-gray-200">
                  <span className="text-emerald-400">{signal.context?.support?.toFixed?.(2) ?? '-'}</span>
                  {' / '}
                  <span className="text-red-400">{signal.context?.resistance?.toFixed?.(2) ?? '-'}</span>
                </div>
              </div>
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-gray-500">SMA200 DIST</div>
                <div className="text-gray-200">{signal.context?.sma200_distance_pct?.toFixed?.(1) ?? '-'}%</div>
              </div>
            </div>
          )}

          {/* Target / support headline — always present so every chart has an objective */}
          {!loading && !error && (dispTarget != null || dispStop != null) && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {dispTarget != null && (
                <span className="inline-flex items-center gap-1 bg-cyan-950/40 border border-cyan-800/50 text-cyan-200 rounded px-2 py-1">
                  <Target className="w-3.5 h-3.5" /> Target <b>{dispTarget}</b>
                  {targetPct != null && (
                    <span className="text-emerald-400 font-bold">
                      ({targetPct > 0 ? '+' : ''}{targetPct.toFixed(1)}%)
                    </span>
                  )}
                </span>
              )}
              {dispStop != null && (
                <span className="inline-flex items-center gap-1 bg-emerald-950/30 border border-emerald-800/40 text-emerald-200/90 rounded px-2 py-1">
                  🛡 Support <b>{dispStop}</b>
                  {stopPct != null && (
                    <span className="text-red-400 font-bold">({stopPct.toFixed(1)}%)</span>
                  )}
                </span>
              )}
              {!activeCp && (
                <span className="text-gray-500">
                  — target = next overhead resistance from recent swing highs; support = nearest swing low.
                </span>
              )}
            </div>
          )}

          {/* Chart */}
          <div
            ref={chartRef}
            className="w-full bg-[#0b1220] rounded border border-gray-700"
            style={{ minHeight: 440 }}
          />

          {/* Legend */}
          <div className="text-[11px] text-gray-500 flex flex-wrap gap-3">
            <span><span className="text-amber-400">━</span> 50-day MA</span>
            <span><span style={{ color: LINE_COLORS.neckline }}>- -</span> Neckline</span>
            <span><span style={{ color: LINE_COLORS.support }}>━</span> Support rail</span>
            <span><span style={{ color: LINE_COLORS.resistance }}>━</span> Resistance rail</span>
            <span><span style={{ color: LINE_COLORS.target }}>- -</span> Target (pattern / next resistance)</span>
            <span><span style={{ color: LINE_COLORS.support }}>┈</span> Support</span>
            <span><span style={{ color: LINE_COLORS.stop }}>┈</span> Stop</span>
          </div>

          {/* ---- Chart patterns (Bulkowski) ---- */}
          {chartPatterns.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-bold text-purple-300 mt-2 flex items-center gap-2">
                <Crosshair className="w-4 h-4" /> Chart patterns
                <span className="text-[11px] text-gray-500 font-normal">
                  (click one to draw it on the chart · stats are Bulkowski bull-market averages)
                </span>
              </h3>
              {chartPatterns.map((p, i) => (
                <ChartPatternCard
                  key={i}
                  pattern={p}
                  active={i === activePattern}
                  onClick={() => setActivePattern(i)}
                  onLearn={() => setLearnCode(tutorialCodeFor(p.code))}
                />
              ))}
            </div>
          )}

          {/* ---- Candlestick patterns ---- */}
          {signal && signal.patterns.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-gray-300 mt-4">Candlestick patterns (last bars)</h3>
              {signal.patterns.map((p, i) => (
                <PatternCard key={i} pattern={p} />
              ))}
            </div>
          )}

          {chartPatterns.length === 0 && signal && signal.patterns.length === 0 && !loading && (
            <div className="text-sm text-gray-500 text-center py-6">
              No active chart or candlestick patterns detected on the current data.
            </div>
          )}

          {/* Plain-English candlestick summary */}
          {signal && signal.explanation && (
            <div className="bg-gray-800 border border-gray-700 rounded p-3">
              <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <Info className="w-3 h-3" /> Candlestick engine summary
              </div>
              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-sans">{signal.explanation}</pre>
            </div>
          )}
        </div>
    {learnCode && <TutorialModal code={learnCode} onClose={() => setLearnCode(null)} />}
    </>
  );
}

/**
 * ChartDetailModal — overlay wrapper around ChartAnalysisBody (used from the
 * dashboard / chart-analysis pages where the chart opens in a modal).
 */
export default function ChartDetailModal({ apiUrl, ticker, onClose }: ChartDetailModalProps) {
  // Esc to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-2" onClick={onClose}>
      <div
        className="bg-gray-900 rounded-lg shadow-2xl border border-purple-800/40 w-full max-w-[1200px] max-h-[95vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-700 flex items-center justify-between sticky top-0 bg-gray-900 z-10">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-2xl font-bold text-purple-300">{ticker}</h2>
            <span className="text-xs text-gray-500 border border-purple-800/60 rounded px-1.5 py-0.5">
              Chart Analyst
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-6 h-6" />
          </button>
        </div>
        <ChartAnalysisBody apiUrl={apiUrl} ticker={ticker} />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ //
// Bulkowski chart-pattern card
// ------------------------------------------------------------------ //

function Stat({ label, value, suffix = '', good }: { label: string; value: number | null; suffix?: string; good?: boolean }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex flex-col">
      <span className="text-[10px] text-gray-500 uppercase tracking-wide">{label}</span>
      <span className={`text-sm font-bold ${good === true ? 'text-emerald-400' : good === false ? 'text-red-400' : 'text-gray-200'}`}>
        {value}
        {suffix}
      </span>
    </div>
  );
}

function ChartPatternCard({
  pattern,
  active,
  onClick,
  onLearn,
}: {
  pattern: DetectedChartPattern;
  active: boolean;
  onClick: () => void;
  onLearn: () => void;
}) {
  const c = biasColor(pattern.bias);
  const s = pattern.stats;
  const confirmed = pattern.status === 'confirmed';
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      className={`w-full text-left rounded-lg p-3 space-y-2 border transition cursor-pointer ${
        active ? 'bg-gray-800 ring-1 ring-purple-500' : 'bg-gray-800/40 hover:bg-gray-800/70'
      }`}
      style={{ borderColor: c + (active ? 'aa' : '44') }}
    >
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {pattern.grade && (
            <span className={`w-6 h-6 rounded flex items-center justify-center font-black text-xs ${gradeCls(pattern.grade)}`} title={`edge ${pattern.edge ?? '-'}/100`}>
              {pattern.grade}
            </span>
          )}
          {pattern.bias === 'bullish' ? (
            <TrendingUp className="w-4 h-4" style={{ color: c }} />
          ) : (
            <TrendingDown className="w-4 h-4" style={{ color: c }} />
          )}
          <span className="text-sm font-bold" style={{ color: c }}>
            {pattern.name}
          </span>
          {pattern.verdict && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${verdictCls(pattern.verdict)}`}>
              {pattern.verdict}
            </span>
          )}
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
              confirmed ? 'bg-emerald-900/70 text-emerald-300' : 'bg-amber-900/60 text-amber-300'
            }`}
          >
            {confirmed ? 'CONFIRMED' : 'FORMING'}
          </span>
          <span className="text-[10px] text-gray-500 uppercase">{pattern.category}</span>
          {s.rank != null && (
            <span className="text-[10px] text-purple-300 border border-purple-800/60 rounded px-1">
              Bulkowski rank #{s.rank}
            </span>
          )}
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              onLearn();
            }}
            className="text-[10px] text-indigo-300 hover:text-indigo-100 inline-flex items-center gap-0.5 cursor-pointer"
            title="Learn this pattern"
          >
            <GraduationCap className="w-3.5 h-3.5" /> Learn
          </span>
        </div>
        {pattern.target != null && (
          <div className="flex items-center gap-1 text-xs" style={{ color: LINE_COLORS.target }}>
            <Target className="w-3.5 h-3.5" />
            <span className="font-bold">{pattern.target}</span>
            {pattern.target_pct != null &&
              (((pattern.bias === 'bullish' && pattern.target_pct <= 0) ||
                (pattern.bias === 'bearish' && pattern.target_pct >= 0)) ? (
                <span className="text-emerald-400">✓ target hit</span>
              ) : (
                <span className="text-gray-400">
                  ({pattern.target_pct > 0 ? '+' : ''}
                  {pattern.target_pct}%)
                </span>
              ))}
          </div>
        )}
      </div>

      <div className="text-xs text-gray-300">{pattern.plain}</div>
      {pattern.verdict_reason && (
        <div className="text-xs text-cyan-200/90 bg-cyan-950/30 border border-cyan-900/40 rounded px-2 py-1">
          <b>Verdict:</b> {pattern.verdict_reason}
        </div>
      )}

      {/* Bulkowski statistics row */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 bg-gray-900/50 rounded px-2 py-1.5">
        <Stat label="Avg move" value={s.avg_move_pct} suffix="%" good />
        <Stat label="Fail rate" value={s.failure_rate_pct} suffix="%" good={s.failure_rate_pct != null ? s.failure_rate_pct <= 10 : undefined} />
        <Stat label="Hit target" value={s.meet_target_pct} suffix="%" good={s.meet_target_pct != null ? s.meet_target_pct >= 60 : undefined} />
        <Stat label="Throwback" value={s.throwback_pct} suffix="%" />
        <div className="flex flex-col">
          <span className="text-[10px] text-gray-500 uppercase tracking-wide">Breakout</span>
          <span className="text-sm font-bold text-gray-200">{pattern.breakout_price ?? '—'}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-gray-500 uppercase tracking-wide">Stop</span>
          <span className="text-sm font-bold text-gray-200">{pattern.stop ?? '—'}</span>
        </div>
      </div>

      {pattern.bias === 'bullish' && (pattern.dse_stats ? (
        <div className={`text-[11px] rounded px-2 py-1 border font-bold ${
          pattern.dse_stats.net_20d > 0
            ? 'text-emerald-300 bg-emerald-950/30 border-emerald-900/40'
            : 'text-red-300 bg-red-950/30 border-red-900/40'}`}>
          DSE reality (not the US book): buying this confirmation returned{' '}
          {pattern.dse_stats.net_20d > 0 ? '+' : ''}{pattern.dse_stats.net_20d}% net at +20 days,{' '}
          {pattern.dse_stats.win_pct}% win rate (n={pattern.dse_stats.n}, 2023–26 point-in-time).
        </div>
      ) : (
        <div className="text-[11px] rounded px-2 py-1 border font-bold text-amber-300 bg-amber-950/30 border-amber-900/40">
          DSE reality: UNPROVEN — this pattern occurred too rarely on DSE (2023–26) to backtest.
          The Bulkowski stats above are US bull-market numbers and the target is a projection;
          neither is validated on this market.
        </div>
      ))}

      {pattern.quality_notes && pattern.quality_notes.length > 0 && (
        <ul className="text-[11px] text-amber-300/80 list-disc pl-4 space-y-0.5">
          {pattern.quality_notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
// Candlestick pattern card (unchanged behaviour)
// ------------------------------------------------------------------ //

function PatternCard({ pattern }: { pattern: ChartPattern }) {
  const c = biasColor(pattern.bias);
  return (
    <div className="bg-gray-800/60 border rounded p-3 space-y-2" style={{ borderColor: c + '66' }}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ color: c }}>
            {pattern.name}
          </span>
          <span className="text-[10px] text-gray-500 uppercase">
            {pattern.type} · {pattern.bias}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500">strength</span>
          <span className="font-bold" style={{ color: c }}>
            {pattern.final_strength}/100
          </span>
        </div>
      </div>
      <div className="text-xs text-gray-300">{pattern.plain}</div>
      {pattern.context_notes && pattern.context_notes.length > 0 && (
        <ul className="text-[11px] text-gray-400 list-disc pl-4 space-y-0.5">
          {pattern.context_notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
