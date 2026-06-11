import { Signal } from '../types';

interface SignalDetailModalProps {
  signal: Signal;
  onClose: () => void;
}

function scoreColor(score: number) {
  // v7 thresholds: BUY ≥ 50, WAIT ≥ 28
  if (score >= 50) return 'text-green-400';
  if (score >= 28) return 'text-yellow-400';
  return 'text-red-400';
}

function earlyColor(score?: number) {
  if (score == null) return 'text-gray-500';
  if (score >= 60) return 'text-orange-400';
  if (score >= 40) return 'text-amber-300';
  return 'text-gray-500';
}

function pts(n: number) {
  if (n > 0) return `+${n}`;
  return `${n}`;
}

interface V6Component {
  name: string;
  points: number;
  maxPts: string;
  detail: string;
}

function getV6Breakdown(signal: Signal): V6Component[] {
  const d = signal.v5_details;
  if (!d) return [];

  const rvol = d.rvol;
  const qa = d.quiet_accumulation;
  const mda = d.multi_day_accumulation;
  const va = d.volume_acceleration;
  const sma = d.sma;
  const obv = d.obv_divergence;
  const cpr = d.close_position_ratio;
  const lf = d.low_float;
  const pt = d.price_tightening;
  const cg = d.consecutive_green;
  const sm = d.smart_money;
  const vwap = d.vwap_proximity;
  const rr = d.rr;
  const coil = d.pre_breakout_coil;
  const le = d.late_entry;

  return [
    {
      name: 'Graduated RVOL',
      points: rvol?.points ?? 0,
      maxPts: '40',
      detail: `RVOL = ${rvol?.value ?? 0}x (v7 caps: ≥4→40, ≥2.5→32, ≥2→22, ≥1.5→12)`,
    },
    {
      name: 'Quiet Accumulation (5D)',
      points: qa?.score ?? 0,
      maxPts: '20',
      detail: `Range ${qa?.price_range_pct?.toFixed(1) ?? '-'}%, cumRVOL ${qa?.cum_rvol?.toFixed(1) ?? '-'}`,
    },
    {
      name: 'Multi-Day Accumulation (10D)',
      points: mda?.score ?? 0,
      maxPts: '45',
      detail: `${mda?.days_elevated ?? 0}/10 days RVOL>1.5, avg ${mda?.avg_rvol?.toFixed(1) ?? '-'}x`,
    },
    {
      name: 'Volume Acceleration',
      points: va?.score ?? 0,
      maxPts: '10',
      detail: `VAI (3d/10d) = ${va?.vai?.toFixed(1) ?? '-'}x`,
    },
    {
      name: 'SMA 200 Position',
      points: sma?.score ?? 0,
      maxPts: '25',
      detail: `${sma?.distance_pct?.toFixed(1) ?? '-'}% from SMA${sma?.crossover ? ' | CROSSOVER' : ''}`,
    },
    {
      name: 'OBV Divergence',
      points: obv?.score ?? 0,
      maxPts: '15',
      detail: obv?.divergence ? 'Bullish divergence detected' : 'No divergence',
    },
    {
      name: 'Close Position Ratio',
      points: cpr?.score ?? 0,
      maxPts: '10',
      detail: `CPR = ${cpr?.cpr?.toFixed(2) ?? '-'} (>0.7 + RVOL>1.5)`,
    },
    {
      name: 'Low Float',
      points: lf?.points ?? 0,
      maxPts: '20',
      detail: lf?.available === false ? 'Run fundamentals scraper' : (lf?.points ?? 0) > 0 ? 'Low paid-up capital' : 'Not a low-float stock',
    },
    {
      name: 'Price Squeeze (BB)',
      points: pt?.score ?? 0,
      maxPts: '20',
      detail: pt?.ratio != null ? `BB width ${(pt.ratio * 100).toFixed(0)}% of avg${pt.squeeze ? ' — SQUEEZE' : ''}` : 'N/A',
    },
    {
      name: 'Buying Streak',
      points: cg?.score ?? 0,
      maxPts: '10',
      detail: `${cg?.consecutive_days ?? 0} consecutive green candles with above-avg volume (v7 cap: lagging indicator)`,
    },
    {
      name: 'Smart Money',
      points: sm?.score ?? 0,
      maxPts: '10',
      detail: `Divergence = ${sm?.divergence_value?.toFixed(3) ?? '0'} (v7 cap: high-vol-up vs low-vol-down)`,
    },
    {
      name: 'VWAP Proximity',
      points: vwap?.score ?? 0,
      maxPts: '10',
      detail: vwap?.distance_pct != null ? `${vwap.distance_pct.toFixed(1)}% from 5D VWAP${vwap.near_vwap ? ' — NEAR' : ''}` : 'N/A',
    },
    {
      name: 'Pre-Breakout Coil (v7)',
      points: coil?.score ?? 0,
      maxPts: '25',
      detail: coil
        ? `10d range ${coil.range_pct?.toFixed(1) ?? '-'}%, ATR ${coil.atr_contracting ? 'contracting' : 'stable'} — leading indicator`
        : 'N/A',
    },
    {
      name: 'Late-Entry Penalty (v7)',
      points: le?.score ?? 0,
      maxPts: '0',
      detail: le
        ? (le.flags && le.flags.length > 0
            ? `Already extended: ${le.flags.join('; ')}`
            : `5d ret ${le.return_5d_pct ?? '-'}%, SMA dist ${le.sma_distance_pct ?? '-'}% — no penalty`)
        : 'N/A',
    },
    {
      name: 'Reward:Risk Ratio',
      points: rr?.ratio != null ? (rr.ratio >= 2 ? 10 : rr.ratio < 1 ? -10 : 0) : 0,
      maxPts: '10',
      detail: rr?.ratio != null ? `R:R = ${rr.ratio.toFixed(1)}:1` : 'R:R not available',
    },
  ];
}

export default function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  const breakdown = getV6Breakdown(signal);
  const hasBreakdown = breakdown.length > 0 && signal.v5_details && Object.keys(signal.v5_details).length > 0;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80" onClick={onClose}>
      <div
        className="bg-gray-950 border border-green-500/50 rounded-lg p-6 shadow-2xl w-[90vw] max-w-[520px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4 border-b border-gray-700 pb-3">
          <div>
            <h3 className="text-lg font-bold text-green-400">{signal.Ticker}</h3>
            <div className="text-xs text-gray-500">v7 Scoring Engine</div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-2xl font-bold">
            ×
          </button>
        </div>

        <div className="space-y-4 text-sm">
          {/* Price & Score */}
          <div className="bg-gray-900 p-4 rounded">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <div className="text-gray-500 text-xs">Price</div>
                <div className="text-white font-bold text-lg">৳{signal.Price}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">Score</div>
                <div className={`font-bold text-lg ${scoreColor(signal.Score)}`}>{signal.Score}/100</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs">Raw</div>
                <div className="text-gray-300 font-bold text-lg">{signal.RawScore ?? '-'}</div>
              </div>
            </div>
          </div>

          {/* Trend Status */}
          {signal.TrendStatus && (
            <div className={`p-3 rounded border ${
              signal.TrendStatus === 'UPTREND'
                ? 'bg-green-900/20 border-green-700'
                : signal.TrendStatus === 'NEAR_SMA'
                  ? 'bg-yellow-900/20 border-yellow-700'
                  : 'bg-red-900/20 border-red-700'
            }`}>
              <div className="flex items-center justify-between">
                <div className="text-xs font-bold text-gray-400">📊 Trend</div>
                <div className={`text-sm font-bold ${
                  signal.TrendStatus === 'UPTREND' ? 'text-green-400' :
                  signal.TrendStatus === 'NEAR_SMA' ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {signal.TrendStatus === 'UPTREND' ? '⬆️ UPTREND' :
                   signal.TrendStatus === 'NEAR_SMA' ? '↔️ NEAR SMA' : '⬇️ DOWNTREND'}
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Price ৳{signal.Price} vs SMA 200 ৳{signal.SMA200?.toFixed(2) ?? '-'}
              </div>
            </div>
          )}

          {/* Trading Levels */}
          {(signal.NearestSupport || signal.NearestResistance || signal.RecommendedStopLoss) && (
            <div className="bg-blue-900/20 border border-blue-700 p-4 rounded">
              <div className="text-xs font-bold text-blue-400 mb-3">🎯 Trading Levels</div>
              <div className="space-y-2">
                {signal.NearestSupport != null && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Support</span>
                    <span className="text-green-400 font-bold">৳{signal.NearestSupport.toFixed(2)}</span>
                  </div>
                )}
                {signal.NearestResistance != null && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Resistance</span>
                    <span className="text-red-400 font-bold">৳{signal.NearestResistance.toFixed(2)}</span>
                  </div>
                )}
                {signal.RecommendedStopLoss != null && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400">Stop Loss</span>
                    <span className="text-orange-400 font-bold">৳{signal.RecommendedStopLoss.toFixed(2)}</span>
                  </div>
                )}
                {signal.RewardRiskRatio != null && (
                  <div className="flex justify-between items-center border-t border-gray-700 pt-2">
                    <span className="text-gray-400">R:R Ratio</span>
                    <span className={`font-bold ${signal.RewardRiskRatio >= 2 ? 'text-green-400' : signal.RewardRiskRatio >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {signal.RewardRiskRatio.toFixed(1)}:1
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* v5 Score Breakdown */}
          <div className="bg-purple-900/20 border border-purple-700 p-4 rounded">
            <div className="text-xs font-bold text-purple-400 mb-3">🧮 v7 Score Breakdown ({breakdown.length} Components)</div>
            {hasBreakdown ? (
              <div className="space-y-1 text-xs">
                {breakdown.map((comp, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className={comp.points > 0 ? 'text-green-400' : comp.points < 0 ? 'text-red-400' : 'text-gray-600'}>
                        {comp.points > 0 ? '✅' : comp.points < 0 ? '❌' : '⬜'}
                      </span>
                      <div className="min-w-0">
                        <div className="text-gray-200 truncate">{comp.name}</div>
                        <div className="text-gray-600 truncate">{comp.detail}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 ml-2 shrink-0">
                      <span className={`font-bold ${comp.points > 0 ? 'text-green-400' : comp.points < 0 ? 'text-red-400' : 'text-gray-600'}`}>
                        {pts(comp.points)}
                      </span>
                      <span className="text-gray-700">/{comp.maxPts}</span>
                    </div>
                  </div>
                ))}

                <div className="flex justify-between items-center pt-2 border-t-2 border-gray-600 mt-2">
                  <span className="text-white font-bold">RAW TOTAL</span>
                  <span className="text-gray-300 font-bold">{signal.RawScore ?? '-'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-white font-bold">FINAL SCORE (raw / max × 100)</span>
                  <span className={`text-xl font-bold ${scoreColor(signal.Score)}`}>{signal.Score}/100</span>
                </div>

                <div className="text-gray-500 text-xs italic mt-2">
                  {signal.Score >= 50 && '✅ BUY — Strong multi-factor confirmation'}
                  {signal.Score >= 28 && signal.Score < 50 && '⏳ WAIT — Developing pattern, monitor'}
                  {signal.Score < 28 && '❌ IGNORE — Insufficient evidence'}
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-500 italic">Breakdown data not available — regenerate signals to populate.</div>
            )}
          </div>

          {/* v7: EarlyScore panel — leading pre-breakout detector */}
          {typeof signal.EarlyScore === 'number' && (
            <div className="bg-gray-900 p-4 rounded border border-orange-900/40">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-bold text-orange-300">🔥 EARLY SCORE (Pre-Breakout Detector)</div>
                <span className={`text-xl font-bold ${earlyColor(signal.EarlyScore)}`}>
                  {signal.EarlyScore}/100 — {signal.EarlySignal}
                </span>
              </div>
              <div className="text-xs text-gray-400 mb-2 italic">
                {signal.EarlySignal === 'EARLY' && 'Tight base + first volume tell + not extended. Best entry window.'}
                {signal.EarlySignal === 'WATCH' && 'Setup forming, but missing volume tell or testing high. Watch closely.'}
                {signal.EarlySignal === 'NONE' && 'No pre-breakout setup detected here.'}
              </div>
              {signal.EarlyComponents && (
                <div className="space-y-1 text-xs">
                  {Object.entries(signal.EarlyComponents).map(([k, v]) => {
                    const points = (v as { points?: number })?.points ?? 0;
                    const niceName: Record<string, string> = {
                      tight_base: 'Tight Base',
                      goldilocks_volume: 'Goldilocks Volume',
                      closing_tell: 'Closing Tell',
                      near_resistance: 'Near 10d High',
                      not_extended: 'Not Extended',
                    };
                    const max: Record<string, string> = {
                      tight_base: '25', goldilocks_volume: '25',
                      closing_tell: '20', near_resistance: '15', not_extended: '15',
                    };
                    return (
                      <div key={k} className="flex items-center justify-between border-b border-gray-800 last:border-0 py-1">
                        <span className="text-gray-300">{niceName[k] || k}</span>
                        <span className={`font-bold ${points > 0 ? 'text-green-400' : points < 0 ? 'text-red-400' : 'text-gray-600'}`}>
                          {pts(points)} <span className="text-gray-700">/{max[k] || '-'}</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
              {signal.EarlyReasons && signal.EarlyReasons.length > 0 && (
                <div className="mt-2 text-xs text-gray-400">
                  <span className="text-gray-500">Reasons: </span>{signal.EarlyReasons.join(', ')}
                </div>
              )}
              {(signal.IsFreshEarly || signal.IsFreshBuy) && (
                <div className="mt-2 text-xs text-orange-300 font-bold">
                  ⭐ FRESH — first day this signal fired (yesterday was {signal.PrevEarlySignal || signal.PrevSignal || 'lower'})
                </div>
              )}
            </div>
          )}

          {/* Volume Analysis */}
          <div className="bg-gray-900 p-4 rounded">
            <div className="text-xs font-bold text-gray-400 mb-2">📈 Volume Analysis</div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">RVOL</span>
                <span className={`font-bold ${signal.RVOL >= 2.0 ? 'text-yellow-400' : signal.RVOL >= 1.5 ? 'text-yellow-300' : 'text-gray-400'}`}>
                  {signal.RVOL}x
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Today&apos;s Volume</span>
                <span className="text-white">{(signal.Volume || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">20-Day Avg</span>
                <span className="text-white">{(signal.AvgVolume20 || 0).toLocaleString()}</span>
              </div>
              <div className="text-gray-600 mt-2 italic text-xs">
                {signal.RVOL >= 4.0 ? '🔥 Extreme volume — v7 cap (+40 pts) — often LATE' :
                 signal.RVOL >= 2.5 ? '⚡ Very high volume (+32 pts)' :
                 signal.RVOL >= 2.0 ? '📈 High volume (+22 pts)' :
                 signal.RVOL >= 1.5 ? '📊 Elevated volume (+12 pts)' :
                 '💤 Normal volume (0 pts)'}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 rounded transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
