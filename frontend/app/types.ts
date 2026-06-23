// TypeScript Types for DSE Sniper

export interface Signal {
  Ticker: string;
  Price: number;
  RVOL: number;
  Score: number;
  Signal: string;
  Reason: string;
  Volume?: number;
  AvgVolume20?: number;
  PriceChange?: number;
  SMA200?: number;
  LastClosingVol?: number;
  CurrentVol?: number;
  ProjectedVol?: number;
  IsMarketOpen?: boolean;
  IsIntraday?: boolean;
  // v4 NEW FIELDS: Enhanced Risk Management
  NearestSupport?: number;
  NearestResistance?: number;
  RecommendedStopLoss?: number;
  RewardRiskRatio?: number;
  ATR?: number;
  TrendStatus?: string;  // 'UPTREND', 'NEAR_SMA', or 'DOWNTREND'
  RawScore?: number;  // v5: raw score before scaling
  // v7 NEW FIELDS — EarlyScore (parallel pre-breakout detector)
  EarlyScore?: number;
  EarlySignal?: 'EARLY' | 'WATCH' | 'NONE' | string;
  EarlyReasons?: string[];
  EarlyComponents?: {
    tight_base?: { points: number; range_pct_10d?: number };
    goldilocks_volume?: { points: number; rvol?: number };
    closing_tell?: { points: number; green?: boolean; cpr?: number; above_prev?: boolean };
    near_resistance?: { points: number; high_10d?: number; distance_pct?: number };
    not_extended?: { points: number; return_5d_pct?: number };
  };
  IsFreshBuy?: boolean;
  IsFreshEarly?: boolean;
  PrevSignal?: string | null;
  PrevEarlySignal?: string | null;
  SignalStrength?: number;  // max(Score, EarlyScore) for sorting
  // v9 BREAKOUT SIGNAL (additive, proven positive edge)
  BreakoutSignal?: boolean;
  BreakoutReasons?: string[];
  IsFreshBreakout?: boolean;
  // v8 ENTRY-PRICE GUIDANCE
  PrevClose?: number;
  DayLow?: number;
  DayHigh?: number;
  RangePosition?: number;
  RecommendedEntry?: number;
  EntryQuality?: 'GOOD' | 'FAIR' | 'HIGH' | string;
  EntryWarning?: string | null;
  // v6: per-component score breakdown
  v5_details?: {
    rvol?: { points: number; value: number };
    quiet_accumulation?: { score: number; price_range_pct?: number; cum_rvol?: number };
    multi_day_accumulation?: { score: number; days_elevated?: number; avg_rvol?: number };
    volume_acceleration?: { score: number; vai?: number };
    sma?: { score: number; distance_pct?: number; crossover?: boolean };
    obv_divergence?: { score: number; obv_slope?: number; price_slope?: number; divergence?: boolean };
    close_position_ratio?: { score: number; cpr?: number };
    low_float?: { points: number; available?: boolean };
    // v6 new components
    price_tightening?: { score: number; squeeze?: boolean; bb_width?: number; bb_avg?: number; ratio?: number };
    consecutive_green?: { score: number; consecutive_days?: number };
    smart_money?: { score: number; divergence_value?: number };
    vwap_proximity?: { score: number; distance_pct?: number; near_vwap?: boolean; vwap_5d?: number };
    rr?: { ratio?: number };
    // v7
    pre_breakout_coil?: { score: number; range_pct?: number; atr_contracting?: boolean; atr_now?: number; atr_prior?: number };
    late_entry?: { score: number; return_5d_pct?: number | null; sma_distance_pct?: number | null; flags?: string[] };
  };
}

export interface EntryGuidance {
  ticker?: string;
  date?: string;
  prev_close: number | null;
  current_price: number;
  day_low: number;
  day_high: number;
  range_position: number;
  recommended_entry: number;
  entry_quality: 'GOOD' | 'FAIR' | 'HIGH' | string;
  entry_warning: string | null;
}

export interface PortfolioItem {
  ticker: string;
  buy_price: number;
  quantity: number;
  highest_seen: number;
  current_price: number;
  profit_pct: number;
  profit_amount: number;
  status: string;
  purchase_date: string;
  // Level 2 fields
  atr: number;
  days_held: number;
  rvol: number;
  stop_loss_price: number;
  trailing_stop_price: number;
  stop_type: string;
  atr_distance: number;
  is_zombie: boolean;
  volume: number;
  // v3 field
  rsi?: number;
  // New fields
  total_cost?: number;
  commission_paid?: number;
}

export interface ScoreHistoryRow {
  date: string;
  close: number | null;
  price_change_pct: number | null;
  volume: number;
  rvol: number | null;
  raw_score: number;
  score: number;
  signal: string;
  early_score: number;
  early_signal: string;
  late_entry_pts: number;
  return_5d_pct: number | null;
  is_intraday: boolean;
}

export interface ScoreHistory {
  ticker: string;
  status: 'success' | 'error' | string;
  message?: string;
  days?: number;
  history: ScoreHistoryRow[];
}

export interface PurchaseHistory {
  id: number;
  ticker: string;
  buy_price: number;
  quantity: number;
  commission: number;
  total_cost: number;
  purchase_date: string;
  notes: string;
}

export interface VolumeHistory {
  date: string;
  volume: number;
}

export interface PriceHistory {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface BuyRecommendation {
  can_buy: boolean;
  ticker?: string;
  suggested_quantity?: number;
  price_per_share?: number;
  trade_value?: number;
  commission?: number;
  total_cost?: number;
  avg_price_per_share?: number;
  remaining_budget?: number;
  budget_used_pct?: number;
  signal_strength?: number;
  reason?: string;
  min_required?: number;
}

export interface Alert {
  ticker: string;
  type: string;
  value: string;
  action: string;
  reason: string;
  urgency: string;
  current_price: number;
  buy_price: number;
  profit_amount: number;
}

export interface SystemStatus {
  status: string;
  market_status: string;
  last_update: string | null;
  next_update: string | null;
}

// ----------------------------
// Manual ticker analysis breakdown (debug UI)
// ----------------------------

export interface SurvivalRuleResult {
  passed: boolean;
  details: string;
}

export interface SurvivalFilterBreakdown {
  passed: boolean;
  reason: string;
  rules: {
    ghost_town: SurvivalRuleResult;
    price_stuck: SurvivalRuleResult;
    min_volume: SurvivalRuleResult;
  };
}

export interface ScoreBreakdownItem {
  name: string;
  passed: boolean;
  points: number;
  details: string;
}

export interface RewardRiskResult {
  valid: boolean;
  reason?: string;
  ratio: number;
  risk_amount?: number;
  risk_percent?: number;
  reward_amount?: number;
  reward_percent?: number;
  recommended?: boolean;
}

export interface DetailedTickerAnalysis {
  ticker: string;
  status: 'success' | 'filtered' | 'error';
  message?: string | null;

  meta?: {
    analysis_date: string;
    current_time: string;
    is_market_open: boolean;
    is_intraday: boolean;
  };

  inputs?: {
    paid_up_capital?: number | null;
  };

  filters?: {
    survival: SurvivalFilterBreakdown;
    trend: {
      passed: boolean;
      reason: string;
      close: number | null;
      sma_200: number | null;
    };
  };

  indicators?: {
    close: number | null;
    open: number | null;
    high: number | null;
    low: number | null;
    volume: number;
    last_closing_vol: number;
    current_vol: number;
    projected_vol: number | null;
    avg_volume_20: number;
    rvol: number;
    price_change_pct: number | null;
    sma_200: number | null;
    atr: number | null;
    daily_range_pct: number;
    // v5 indicators
    close_position_ratio?: number;
    obv_slope_20?: number;
    price_slope_20?: number;
    vol_ma_3?: number;
    vol_ma_10?: number;
    // v6 indicators
    bb_width?: number;
    bb_width_avg?: number;
    consec_green_vol?: number;
    vwap_5d?: number;
    smart_money_score?: number;
  };

  support_resistance?: {
    nearest_support: number | null;
    nearest_resistance: number | null;
    all_support_levels: number[];
    all_resistance_levels: number[];
  };

  risk?: {
    stop_from_support: number | null;
    stop_from_atr: number | null;
    recommended_stop_loss: number | null;
    reward_risk: RewardRiskResult | null;
  };

  score?: {
    final_score: number;
    raw_score?: number;
    signal: string;
    breakdown: ScoreBreakdownItem[];
    official_reasons?: string[] | null;
  };

  // v7: parallel EarlyScore breakdown
  early?: {
    score: number;
    raw_points?: number;
    signal: 'EARLY' | 'WATCH' | 'NONE' | string;
    reasons: string[];
    components: {
      tight_base?: { points: number; range_pct_10d?: number | null };
      goldilocks_volume?: { points: number; rvol?: number };
      closing_tell?: { points: number; green?: boolean; cpr?: number; above_prev?: boolean };
      near_resistance?: { points: number; high_10d?: number; distance_pct?: number | null };
      not_extended?: { points: number; return_5d_pct?: number | null };
    };
  };

  official?: {
    signal?: string;
    score?: number;
    reasons?: string[];
    nearest_support?: number | null;
    nearest_resistance?: number | null;
    recommended_stop_loss?: number | null;
    reward_risk_ratio?: number | null;
    trend_status?: string;
  };
}

// ----------------------------
// Chart-pattern analyzer (independent second-opinion engine)
// ----------------------------

export interface ChartPattern {
  name: string;
  type: 'reversal' | 'continuation' | string;
  bias: 'bullish' | 'bearish' | 'neutral' | string;
  base_strength: number;
  final_strength: number;
  plain: string;
  multipliers?: Record<string, number>;
  context_notes?: string[];
  geometry?: Record<string, number | null>;
}

export interface ChartContext {
  trend?: 'uptrend' | 'downtrend' | 'sideways' | 'unknown' | string;
  trend_slope_pct?: number;
  sma200?: number;
  sma200_distance_pct?: number;
  support?: number;
  resistance?: number;
  near_support?: boolean;
  near_resistance?: boolean;
  rvol?: number;
  avg_vol_20d?: number;
  ret_5d_pct?: number;
}

export interface ChartSignal {
  ticker: string;
  analysis_date: string;
  overall_score: number;
  overall_bias: 'bullish' | 'bearish' | 'neutral' | string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE' | string;
  pattern_count: number;
  price?: number | null;
  patterns: ChartPattern[];
  context: ChartContext;
  explanation: string;
  detected_at?: string;
  // v9: confluence — the quant engine ALSO flags a breakout for this ticker
  breakout?: boolean;
}

export interface ChartOhlcvBar {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number;
}
