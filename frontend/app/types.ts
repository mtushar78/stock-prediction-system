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
