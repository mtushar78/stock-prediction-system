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
