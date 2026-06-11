'use client';

/**
 * ChartDetailModal — full chart-oriented breakdown for one ticker.
 *
 * - Renders a 60-day candlestick chart with lightweight-charts v5.
 * - Overlays SMA200, support, resistance lines.
 * - Marks every detected pattern on the relevant bar with a colored arrow.
 * - Shows volume histogram beneath the chart.
 * - Below the chart, a plain-English breakdown of each pattern.
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
import { ChartSignal, ChartOhlcvBar, ChartPattern } from '../types';
import { X, AlertCircle, Info } from 'lucide-react';

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

const patternBars = (name: string): number => {
  // How many bars back from the latest bar each pattern occupies
  if (name === 'Morning Star' || name === 'Three White Soldiers') return 3;
  if (
    name === 'Bullish Engulfing' ||
    name === 'Piercing Line' ||
    name === 'Bullish Harami'
  )
    return 2;
  return 1; // Hammer, Inverted Hammer, Bullish Marubozu
};

export default function ChartDetailModal({ apiUrl, ticker, onClose }: ChartDetailModalProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const [signal, setSignal] = useState<ChartSignal | null>(null);
  const [ohlcv, setOhlcv] = useState<ChartOhlcvBar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch signal + OHLCV in parallel
  useEffect(() => {
    let cancelled = false;
    const fetchAll = async () => {
      try {
        setLoading(true);
        setError(null);
        const [sigRes, ohlcvRes] = await Promise.all([
          axios.get<ChartSignal>(`${apiUrl}/api/chart-analysis/${ticker}`),
          axios.get<ChartOhlcvBar[]>(`${apiUrl}/api/chart-analysis/${ticker}/ohlcv?days=90`),
        ]);
        if (cancelled) return;
        setSignal(sigRes.data);
        setOhlcv(Array.isArray(ohlcvRes.data) ? ohlcvRes.data : []);
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

  // Esc to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Build the chart whenever data is ready
  useEffect(() => {
    if (!chartRef.current || !signal || ohlcv.length < 5) return;

    // Tear down any previous instance
    if (chartInstanceRef.current) {
      try {
        chartInstanceRef.current.remove();
      } catch (e) {
        // ignore — chart may already be disposed
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
      timeScale: {
        borderColor: '#374151',
        timeVisible: false,
        secondsVisible: false,
      },
      crosshair: { mode: CrosshairMode.Normal },
    });
    chartInstanceRef.current = chart;

    // Candles
    const candleSeries: ISeriesApi<'Candlestick'> = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    // Filter to bars with full OHLC
    const cleanBars = ohlcv.filter(
      (b) =>
        b.open !== null &&
        b.high !== null &&
        b.low !== null &&
        b.close !== null,
    );

    const candleData = cleanBars.map((b) => ({
      time: b.date as Time,
      open: b.open as number,
      high: b.high as number,
      low: b.low as number,
      close: b.close as number,
    }));
    candleSeries.setData(candleData);

    // Volume histogram on a separate price scale at the bottom
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
        color:
          (b.close ?? 0) >= (b.open ?? 0)
            ? 'rgba(16, 185, 129, 0.5)'
            : 'rgba(239, 68, 68, 0.5)',
      })),
    );

    // SMA200 — overlay if we have enough bars; otherwise just SMA of available
    if (cleanBars.length >= 20) {
      const smaSeries = chart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        title: 'SMA',
      });
      const period = Math.min(50, cleanBars.length);
      const smaData: { time: Time; value: number }[] = [];
      let sum = 0;
      const closes = cleanBars.map((b) => b.close as number);
      for (let i = 0; i < closes.length; i++) {
        sum += closes[i];
        if (i >= period) sum -= closes[i - period];
        if (i >= period - 1) {
          smaData.push({ time: cleanBars[i].date as Time, value: sum / period });
        }
      }
      smaSeries.setData(smaData);
    }

    // Support & Resistance horizontal lines as price lines on the candle series
    if (signal.context?.support) {
      candleSeries.createPriceLine({
        price: signal.context.support,
        color: '#10b981',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'support',
      });
    }
    if (signal.context?.resistance) {
      candleSeries.createPriceLine({
        price: signal.context.resistance,
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'resistance',
      });
    }

    // Pattern markers — pin each detected pattern to its actual bar(s).
    // The pattern fired on the LATEST bar (or spans the last 2-3 bars for
    // multi-candle patterns). Place a labelled arrow on the first bar of
    // each pattern.
    const markers: SeriesMarker<Time>[] = [];
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
        text: `${p.name} (${p.final_strength})`,
      });
    });
    if (markers.length > 0) {
      createSeriesMarkers(candleSeries, markers);
    }

    chart.timeScale().fitContent();

    return () => {
      if (chartInstanceRef.current) {
        try {
          chartInstanceRef.current.remove();
        } catch (e) {
          // ignore
        }
        chartInstanceRef.current = null;
      }
    };
  }, [signal, ohlcv]);

  const trendLabel = signal?.context?.trend ?? '?';
  const trendColor =
    trendLabel === 'uptrend'
      ? 'text-green-400'
      : trendLabel === 'downtrend'
      ? 'text-red-400'
      : 'text-yellow-400';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-2"
      onClick={onClose}
    >
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
            {signal && (
              <>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-bold ${confidenceClass(
                    signal.confidence,
                  )}`}
                >
                  {signal.confidence}
                </span>
                <span className="text-sm text-gray-400">
                  bias{' '}
                  <span
                    className="font-bold"
                    style={{ color: biasColor(signal.overall_bias) }}
                  >
                    {signal.overall_bias.toUpperCase()}
                  </span>
                </span>
                <span className="text-sm text-gray-400">
                  score{' '}
                  <span className="text-purple-300 font-bold">{signal.overall_score}</span>
                  /100
                </span>
                <span className="text-xs text-gray-500">
                  {signal.analysis_date}
                </span>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          {loading && (
            <div className="text-center text-gray-400 py-12">Loading chart…</div>
          )}
          {error && (
            <div className="bg-red-900/40 border border-red-700 text-red-200 rounded p-3 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" /> {error}
            </div>
          )}

          {/* Context strip */}
          {signal && (
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
                <div className="text-yellow-300 font-bold">
                  {signal.context?.rvol?.toFixed?.(2) ?? '-'}×
                </div>
              </div>
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-gray-500">SUPPORT / RESIST</div>
                <div className="text-gray-200">
                  <span className="text-emerald-400">
                    {signal.context?.support?.toFixed?.(2) ?? '-'}
                  </span>{' '}
                  /{' '}
                  <span className="text-red-400">
                    {signal.context?.resistance?.toFixed?.(2) ?? '-'}
                  </span>
                </div>
              </div>
              <div className="bg-gray-800 border border-gray-700 rounded px-3 py-2">
                <div className="text-gray-500">SMA200 DIST</div>
                <div className="text-gray-200">
                  {signal.context?.sma200_distance_pct?.toFixed?.(1) ?? '-'}%{' '}
                  <span className="text-gray-500 text-[10px]">
                    (₹{signal.context?.sma200?.toFixed?.(2) ?? '-'})
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Chart */}
          <div
            ref={chartRef}
            className="w-full bg-[#0b1220] rounded border border-gray-700"
            style={{ minHeight: 420 }}
          />

          {/* Legend */}
          <div className="text-[11px] text-gray-500 flex flex-wrap gap-3">
            <span><span className="text-amber-400">━</span> Moving Average (50d)</span>
            <span><span className="text-emerald-400">- - -</span> Support</span>
            <span><span className="text-red-400">- - -</span> Resistance</span>
            <span><span style={{ color: '#10b981' }}>↑</span> Bullish pattern marker (label = strength /100)</span>
          </div>

          {/* Pattern breakdown */}
          {signal && signal.patterns.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-purple-300 mt-4">
                Pattern breakdown
              </h3>
              {signal.patterns.map((p, i) => (
                <PatternCard key={i} pattern={p} />
              ))}
            </div>
          )}

          {/* Plain-English summary */}
          {signal && (
            <div className="bg-gray-800 border border-gray-700 rounded p-3">
              <div className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                <Info className="w-3 h-3" /> Plain-English summary
              </div>
              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-sans">
                {signal.explanation}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PatternCard({ pattern }: { pattern: ChartPattern }) {
  const c = biasColor(pattern.bias);
  return (
    <div
      className="bg-gray-800/60 border rounded p-3 space-y-2"
      style={{ borderColor: c + '66' }}
    >
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
          <span className="text-gray-500">base</span>
          <span className="text-gray-300">{pattern.base_strength}</span>
          <span className="text-gray-600">→</span>
          <span className="text-gray-500">final</span>
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
