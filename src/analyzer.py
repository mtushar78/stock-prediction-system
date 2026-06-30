"""
Analyzer Module for DSE Sniper System
Implements RVOL calculation, scoring, and signal generation
v3: Projected RVOL for intraday accuracy
v5: Graduated scoring, multi-day accumulation, OBV divergence,
    volume acceleration, close position ratio, institutional flow
v6: Enhanced syndicate detection — price tightening, consecutive green
    buying, smart money divergence, VWAP proximity, improved volume
    projection (U-shaped model), extended accumulation window
v7: Early-detection overhaul
    - NEW: EarlyScore (parallel 5-component score for pre-breakout entries)
    - NEW: Late-entry penalty (penalises stocks already extended)
    - NEW: Pre-Breakout Coil component (tight range + ATR contraction)
    - Capped RVOL ceiling (prevents breakout-day dominance)
    - Softened SMA penalty band, added over-extension penalty
    - Demoted lagging confirmation components (consec_green, smart_money)
    - Loosened thresholds on leading indicators (BB squeeze, OBV, quiet accum)
    - BUY threshold lowered to 50 (with new rebalanced weights)
    - is_fresh_buy / is_fresh_early flags to distinguish day-1 signals
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import pytz
import logging
from src.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def compute_entry_guidance(current_price, day_low, day_high, prev_close,
                           vwap=None, support=None):
    """Advisory intraday buy-price guidance (v8).

    The system never blocks a trade — it WARNS when the price you'd pay isn't
    near the day's low, since chasing the high of a move tends to hand you a
    short-term loss. Returns the previous close, the current price, a
    recommended limit, a quality label and a human-readable warning.

    Quality is driven by where the price sits in today's range:
        range_position = (price - low) / (high - low)   # 0 = at low, 1 = at high
        <= 0.33  -> GOOD   (near the day's low)
        <= 0.55  -> FAIR   (mid-range)
        >  0.55  -> HIGH   (chasing — warn)

    The recommended limit aims for the lower of 5-day VWAP / prior close, but
    never below today's low (unfillable) nor above the current price (no edge).
    """
    cp = float(current_price)
    lo = float(day_low) if day_low not in (None,) else cp
    hi = float(day_high) if day_high not in (None,) else cp
    rng = hi - lo
    pos = (cp - lo) / rng if rng > 0 else 0.0

    anchors = [float(a) for a in (vwap, prev_close) if a and float(a) > 0]
    target = min(anchors) if anchors else cp
    rec = round(max(lo, min(target, cp)), 2)

    if rng <= 0:
        quality = 'FAIR'
    elif pos <= 0.33:
        quality = 'GOOD'
    elif pos <= 0.55:
        quality = 'FAIR'
    else:
        quality = 'HIGH'

    pct = round(pos * 100)
    warning = None
    if quality == 'HIGH':
        warning = (
            f"Price ৳{cp:.2f} is ~{pct}% up today's range "
            f"(low ৳{lo:.2f} / high ৳{hi:.2f}) — not near the day's low. "
            f"Buying here risks a short-term pullback; consider a limit near ৳{rec:.2f}."
        )
    elif quality == 'FAIR' and rng > 0:
        warning = (
            f"Price ৳{cp:.2f} is mid-range (~{pct}% up today's range). "
            f"A dip toward ৳{rec:.2f} would be a safer entry."
        )

    return {
        'prev_close': round(float(prev_close), 2) if prev_close else None,
        'current_price': round(cp, 2),
        'day_low': round(lo, 2),
        'day_high': round(hi, 2),
        'range_position': round(pos, 2),
        'recommended_entry': rec,
        'entry_quality': quality,
        'entry_warning': warning,
    }


class StockAnalyzer:
    """Analyzes stock data and generates trading signals"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize analyzer
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        
        # Configuration parameters
        self.rvol_period = 20  # 20-day average volume
        self.sma_period = 200  # 200-day simple moving average
        self.low_cap_threshold = 50  # Paid-up capital < 50 Cr
        self.high_cap_threshold = 500  # Paid-up capital > 500 Cr (Penny trap)

        # v7: Capped RVOL tiers — extreme volume usually means the move
        # has ALREADY happened. We want to detect setups, not chase spikes.
        # The late-entry penalty + EarlyScore handle the timing edge.
        self.rvol_tiers = [
            (4.0, 40),   # Extreme — capped (was 60)
            (2.5, 32),   # Strong accumulation (was 50)
            (2.0, 22),   # Significant interest (was 30)
            (1.5, 12),   # Elevated interest (was 15)
        ]
        # Legacy threshold kept for compatibility
        self.rvol_threshold = 1.5  # v5: lowered from 2.5 (graduated scoring handles tiers)
        self.price_change_threshold = 0.02  # 2% price change for quiet accumulation

        # ── v9: BREAKOUT ENTRY SIGNAL ───────────────────────────────────────
        # A 14-year walk-forward study (backtest_signals.py / exit_study.py)
        # found the legacy BUY/EARLY signals have NEGATIVE edge: higher score ->
        # worse forward return, because the engine rewards "near the 10-day high
        # + tight base + volume pop" — which on DSE selects local tops that
        # revert (realised -1.2%/trade, win 20%). The ONLY entry rule that beat
        # the universe in EVERY year 2019-2026 was a genuine 20-day-high
        # breakout that is NOT yet extended, in a confirmed uptrend, liquid
        # (realised +1.1%/trade, win 42%, positive every year — same exits).
        # This is exposed ADDITIVELY as `breakout_signal`; the legacy
        # BUY/EARLY signals are left unchanged.
        self.breakout_high_lookback = 20       # must break the N-day high
        self.breakout_high_tol_pct = 1.0       # within this % of (or above) it
        self.breakout_max_ext_20d = 12.0       # reject if 20-day return >= this %
        self.breakout_min_rvol = 1.5           # needs real volume confirmation
        self.breakout_min_avg_vol20 = 50000    # sustained liquidity floor
        self.breakout_min_price = 5.0          # exclude sub-5 penny / MF units

        # v10 REVERSAL signal — buy a confirmed bottom (the mean-reversion edge,
        # opposite of breakout). 7-yr backtest: 68% win / +6.2% avg at +10d, vs
        # 42% universe baseline; Grade A wins ~82%. Fires when a deeply oversold
        # stock with real volume prints its FIRST green day, well below its
        # 120-day high (room to run), and is liquid. See measure_reversal study.
        self.reversal_max_rsi = 30.0           # deeply oversold (Wilder RSI<30)
        self.reversal_min_rvol = 1.5           # capitulation/turn volume
        self.reversal_min_room_pct = 15.0      # >= this % below the 120d high
        self.reversal_min_avg_vol20 = 50000    # same liquidity floor as breakout
        self.reversal_min_price = 5.0          # exclude sub-5 penny / MF units

    def calculate_projected_volume(self, current_vol: float, current_time: datetime = None) -> float:
        """
        v6 UPGRADE: U-shaped volume projection for DSE intraday accuracy.

        DSE volume follows a U-shaped pattern: heavy at open (10:00-10:30),
        quiet in the middle (11:00-13:00), heavy at close (14:00-14:30).
        Linear projection overestimates when sampled during opening rush and
        underestimates when sampled during the quiet midday.

        The cumulative fraction curve approximates how much of EOD volume
        has typically traded by a given minute, derived from DSE intraday
        volume profiles.
        """
        if current_time is None:
            current_time = datetime.now(pytz.timezone('Asia/Dhaka'))

        market_start = current_time.replace(hour=10, minute=0, second=0, microsecond=0)

        if current_time < market_start:
            return 0

        minutes_elapsed = (current_time - market_start).total_seconds() / 60
        minutes_elapsed = min(max(minutes_elapsed, 1), 270)

        # U-shaped cumulative volume fraction model.
        # t is normalised time [0, 1] across 270 min trading day.
        # f(t) approximates cumulative % of EOD volume traded by time t.
        # Derived from: heavy first 30 min (~25%), slow middle, heavy last 30 min (~25%).
        t = minutes_elapsed / 270.0
        cum_frac = 0.25 * min(t / 0.111, 1.0)            # first 30 min → 25%
        if t > 0.111:
            mid_t = min((t - 0.111) / 0.741, 1.0)         # 30 min to 230 min → 50%
            cum_frac += 0.50 * mid_t
        if t > 0.852:
            close_t = min((t - 0.852) / 0.148, 1.0)       # last 40 min → 25%
            cum_frac += 0.25 * close_t

        cum_frac = max(cum_frac, 0.01)  # avoid division by zero
        projected = current_vol / cum_frac

        return projected
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR) - The "Breathing Room" indicator
        
        ATR measures volatility by calculating the "True Range" which captures:
        1. Normal daily range (High - Low)
        2. Gap up scenarios (High - Previous Close)
        3. Gap down scenarios (Previous Close - Low)
        
        This helps set dynamic stop losses that adapt to each stock's natural movement.
        
        Args:
            df: DataFrame with OHLCV data
            period: Lookback period for ATR (default: 14 days)
            
        Returns:
            DataFrame with ATR column added
        """
        df = df.copy()
        
        # Calculate the 3 components of True Range
        high_low = df['high'] - df['low']
        high_prev_close = np.abs(df['high'] - df['close'].shift(1))
        low_prev_close = np.abs(df['low'] - df['close'].shift(1))
        
        # True Range is the maximum of these three
        df['TR'] = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
        
        # Calculate ATR using Exponential Weighted Moving Average (Wilder's Smoothing)
        # This approximates Wilder's smoothing method: ((Prior ATR * 13) + Current TR) / 14
        df['ATR'] = df['TR'].ewm(alpha=1/period, adjust=False).mean()
        
        return df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators for stock data
        v3 UPGRADE: Uses projected RVOL for intraday snapshots
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added indicator columns
        """
        if len(df) < self.sma_period:
            logger.warning(f"Insufficient data for full analysis (need {self.sma_period} days)")
        
        df = df.copy()
        df = df.sort_values('date').reset_index(drop=True)
        
        # Calculate Simple Moving Average (SMA)
        df['sma_200'] = df['close'].rolling(window=self.sma_period, min_periods=1).mean()
        
        # v3 UPGRADE: Calculate Average Volume on COMPLETED days only
        # Shift by 1 so we don't include today's partial data in the average
        df['avg_volume_20'] = df['volume'].shift(1).rolling(window=self.rvol_period, min_periods=1).mean()
        
        # v3 UPGRADE: Projected Volume Logic
        # Check if we're running during market hours AND last row is today
        current_time = datetime.now(pytz.timezone('Asia/Dhaka'))
        is_market_open = 10 <= current_time.hour < 14 or (current_time.hour == 14 and current_time.minute <= 30)
        
        # Create projected_vol column (defaults to actual volume)
        df['projected_vol'] = df['volume']
        
        # Check if last row is marked as intraday snapshot (is_final=0)
        if len(df) > 0 and 'is_final' in df.columns:
            last_idx = df.index[-1]
            is_intraday_snapshot = df.at[last_idx, 'is_final'] == 0
            
            if is_intraday_snapshot and is_market_open:
                # Apply projection to last row only
                current_vol = df.at[last_idx, 'volume']
                proj_vol = self.calculate_projected_volume(current_vol, current_time)
                df.at[last_idx, 'projected_vol'] = proj_vol
                logger.info(f"v3: Projected volume {current_vol:,} → {proj_vol:,.0f}")
        
        # Calculate RVOL using PROJECTED volume
        df['rvol'] = df['projected_vol'] / df['avg_volume_20'].replace(0, np.nan)
        df['rvol'] = df['rvol'].fillna(0)
        
        # Calculate Price Change (%)
        df['price_change'] = df['close'].pct_change()
        df['price_change_pct'] = df['price_change'] * 100
        
        # Calculate Daily Range
        df['daily_range'] = ((df['high'] - df['low']) / df['low'] * 100)
        
        # Calculate ATR (Average True Range) - Level 2 Volatility Indicator
        df = self.calculate_atr(df, period=14)

        # ===== v10 REVERSAL INDICATORS =====
        # 50-day SMA (mean-reversion reference) and 120-day high (upside "room").
        df['sma_50'] = df['close'].rolling(window=50, min_periods=1).mean()
        df['high_120'] = df['high'].rolling(window=120, min_periods=60).max()

        # Wilder's RSI(14) — oversold/exhaustion gauge for the reversal signal.
        _delta = df['close'].diff()
        _up = _delta.clip(lower=0.0)
        _down = (-_delta).clip(lower=0.0)
        _roll_up = _up.ewm(alpha=1/14, adjust=False).mean()
        _roll_down = _down.ewm(alpha=1/14, adjust=False).mean()
        _rs = _roll_up / _roll_down.replace(0, np.nan)
        df['rsi'] = (100 - 100 / (1 + _rs)).fillna(50.0)

        # ===== v5 NEW INDICATORS =====

        # Close Position Ratio: where close falls within the day's range
        # Values near 1.0 = closed at high (buying pressure), near 0.0 = closed at low
        daily_range_abs = df['high'] - df['low']
        df['close_position_ratio'] = ((df['close'] - df['low']) / daily_range_abs.replace(0, np.nan)).fillna(0.5)

        # On-Balance Volume (OBV)
        obv_direction = np.where(df['close'] > df['close'].shift(1), df['volume'],
                                 np.where(df['close'] < df['close'].shift(1), -df['volume'], 0))
        df['obv'] = np.cumsum(obv_direction)

        # OBV slope and price slope — only compute for last row (performance optimization)
        df['obv_slope_20'] = 0.0
        df['price_slope_20'] = 0.0
        if len(df) >= 10:
            n = min(20, len(df))
            x = np.arange(n)
            recent_obv = df['obv'].iloc[-n:].values.astype(float)
            recent_close = df['close'].iloc[-n:].values.astype(float)
            if not np.any(np.isnan(recent_obv)):
                df.iloc[-1, df.columns.get_loc('obv_slope_20')] = np.polyfit(x, recent_obv, 1)[0]
            if not np.any(np.isnan(recent_close)):
                df.iloc[-1, df.columns.get_loc('price_slope_20')] = np.polyfit(x, recent_close, 1)[0]

        # Volume moving averages for acceleration detection
        df['vol_ma_3'] = df['volume'].rolling(3, min_periods=1).mean()
        df['vol_ma_10'] = df['volume'].rolling(10, min_periods=3).mean()

        # ===== v6 NEW INDICATORS =====

        # Bollinger Band Width (20-day) — measures price tightening / squeeze
        bb_sma = df['close'].rolling(20, min_periods=5).mean()
        bb_std = df['close'].rolling(20, min_periods=5).std()
        df['bb_width'] = ((2 * bb_std) / bb_sma.replace(0, np.nan)).fillna(0)
        # 20-day average BB width for relative comparison
        df['bb_width_avg'] = df['bb_width'].rolling(20, min_periods=5).mean()

        # Consecutive green candles (close > open) with above-average volume
        is_green = (df['close'] > df['open']).astype(int)
        above_avg_vol = (df['volume'] > df['avg_volume_20']).astype(int)
        green_vol = is_green * above_avg_vol
        # Count consecutive green+volume days ending at each row
        consec = green_vol.copy()
        for i in range(1, len(consec)):
            if consec.iloc[i] == 1:
                consec.iloc[i] = consec.iloc[i - 1] + 1
            else:
                consec.iloc[i] = 0
        df['consec_green_vol'] = consec

        # VWAP proxy: cumulative (close * volume) / cumulative volume over 5 days
        rolling_vwap_num = (df['close'] * df['volume']).rolling(5, min_periods=1).sum()
        rolling_vwap_den = df['volume'].rolling(5, min_periods=1).sum()
        df['vwap_5d'] = (rolling_vwap_num / rolling_vwap_den.replace(0, np.nan)).fillna(df['close'])

        # Smart Money Divergence: on high-volume days price goes up, on low-volume days price goes down
        # Measured over last 10 days
        df['smart_money_score'] = 0.0
        if len(df) >= 10:
            recent_10 = df.tail(10).copy()
            median_vol = recent_10['volume'].median()
            high_vol_mask = recent_10['volume'] >= median_vol
            low_vol_mask = recent_10['volume'] < median_vol
            price_chg = recent_10['close'].pct_change()
            high_vol_return = price_chg[high_vol_mask].sum() if high_vol_mask.any() else 0
            low_vol_return = price_chg[low_vol_mask].sum() if low_vol_mask.any() else 0
            # Positive = smart money buying (big vol up, small vol down)
            sm_score = float(high_vol_return - low_vol_return) if not (pd.isna(high_vol_return) or pd.isna(low_vol_return)) else 0.0
            df.iloc[-1, df.columns.get_loc('smart_money_score')] = sm_score

        return df
    
    def apply_survival_filters(self, df: pd.DataFrame, ticker: str) -> Dict:
        """
        Apply survival filters to determine if stock should be analyzed
        
        Args:
            df: DataFrame with stock data and indicators
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with filter results
        """
        if len(df) == 0:
            return {'passed': False, 'reason': 'No data'}
        
        # Get recent data (last 5 days)
        recent_df = df.tail(5)
        
        # Filter 1: Ghost Town Rule - Volume == 0 for 3 consecutive days
        if len(recent_df) >= 3:
            last_3_volumes = recent_df['volume'].tail(3).values
            if np.all(last_3_volumes == 0):
                return {'passed': False, 'reason': 'Ghost Town - Zero volume for 3 days'}
        
        # Filter 2: Check if price is stuck (no movement for 5 days)
        if len(recent_df) >= 5:
            price_std = recent_df['close'].std()
            if price_std < 0.01:  # Virtually no price movement
                return {'passed': False, 'reason': 'Price stuck at floor/ceiling'}
        
        # Filter 3: Minimum volume threshold (50,000 as per README)
        latest_volume = df['volume'].iloc[-1]
        if latest_volume < 50000:
            return {'passed': False, 'reason': f'Low volume: {latest_volume}'}
        
        return {'passed': True, 'reason': 'All filters passed'}
    
    def find_support_resistance(self, df: pd.DataFrame, current_price: float, 
                                lookback: int = 60, num_levels: int = 3) -> Dict:
        """
        Identify key support and resistance levels
        
        Args:
            df: DataFrame with OHLC data
            current_price: Current closing price
            lookback: Days to look back (default: 60)
            num_levels: Number of levels to identify (default: 3)
            
        Returns:
            Dictionary with nearest support and resistance
        """
        # Get recent price action
        recent_df = df.tail(lookback)
        
        if len(recent_df) < 3:
            return {
                'nearest_support': None,
                'nearest_resistance': None,
                'all_support_levels': [],
                'all_resistance_levels': []
            }
        
        # Find swing highs (resistance candidates)
        swing_highs = []
        for i in range(1, len(recent_df) - 1):
            if (recent_df.iloc[i]['high'] > recent_df.iloc[i-1]['high'] and
                recent_df.iloc[i]['high'] > recent_df.iloc[i+1]['high']):
                swing_highs.append(recent_df.iloc[i]['high'])
        
        # Find swing lows (support candidates)
        swing_lows = []
        for i in range(1, len(recent_df) - 1):
            if (recent_df.iloc[i]['low'] < recent_df.iloc[i-1]['low'] and
                recent_df.iloc[i]['low'] < recent_df.iloc[i+1]['low']):
                swing_lows.append(recent_df.iloc[i]['low'])
        
        # Cluster nearby levels (within 2% of each other)
        def cluster_levels(levels, tolerance=0.02):
            if not levels:
                return []

            levels = sorted(levels)
            clusters = [[levels[0]]]

            for level in levels[1:]:
                ref = clusters[-1][-1]
                if ref != 0 and abs(level - ref) / abs(ref) < tolerance:
                    clusters[-1].append(level)
                else:
                    clusters.append([level])
            
            return [np.mean(cluster) for cluster in clusters]
        
        resistance_levels = cluster_levels(swing_highs)
        support_levels = cluster_levels(swing_lows)
        
        # Find nearest support (below current price)
        nearest_support = None
        if support_levels:
            supports_below = [s for s in support_levels if s < current_price]
            if supports_below:
                nearest_support = max(supports_below)
        
        # Find nearest resistance (above current price)
        nearest_resistance = None
        if resistance_levels:
            resistances_above = [r for r in resistance_levels if r > current_price]
            if resistances_above:
                nearest_resistance = min(resistances_above)
        
        return {
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'all_support_levels': support_levels,
            'all_resistance_levels': resistance_levels
        }
    
    def calculate_reward_risk_ratio(self, entry_price: float, stop_loss: float, 
                                    target: float) -> Dict:
        """
        Calculate reward:risk ratio for trade planning
        
        Minimum acceptable: 2:1 (make $2 for every $1 risked)
        
        Args:
            entry_price: Planned entry price
            stop_loss: Stop loss price
            target: Take profit target
            
        Returns:
            Dictionary with RR ratio and recommendation
        """
        risk = entry_price - stop_loss
        reward = target - entry_price
        
        if risk <= 0:
            return {
                'valid': False,
                'reason': 'Stop loss must be below entry price',
                'ratio': 0
            }
        
        if reward <= 0:
            return {
                'valid': False,
                'reason': 'Target must be above entry price',
                'ratio': 0
            }
        
        rr_ratio = reward / risk
        
        return {
            'valid': True,
            'ratio': round(rr_ratio, 2),
            'risk_amount': round(risk, 2),
            'risk_percent': round((risk / entry_price) * 100, 2),
            'reward_amount': round(reward, 2),
            'reward_percent': round((reward / entry_price) * 100, 2),
            'recommended': rr_ratio >= 2.0
        }
    
    def _graduated_rvol_score(self, rvol: float) -> int:
        """v5: Return graduated RVOL points instead of binary 2.5x cliff."""
        if pd.isna(rvol) or rvol <= 0:
            return 0
        for threshold, points in self.rvol_tiers:
            if rvol >= threshold:
                return points
        return 0

    def _multi_day_accumulation(self, df: pd.DataFrame, lookback: int = 10) -> Dict:
        """v6: Detect sustained elevated volume over multiple days.

        Extended from 5-day to 10-day window to catch slower syndicate
        accumulation patterns that build positions over 1-2 weeks.
        """
        if len(df) < 6:
            return {'score': 0, 'days_elevated': 0, 'avg_rvol': 0}

        recent = df.tail(lookback)
        days_above = int((recent['rvol'] > 1.5).sum())
        avg_rvol = float(recent['rvol'].mean()) if len(recent) > 0 else 0

        pts = 0
        if days_above >= 7:
            pts = 35  # Strong sustained accumulation over 10 days
        elif days_above >= 5:
            pts = 25
        elif days_above >= 3:
            pts = 15

        # Bonus if average RVOL across those days is > 2.0
        if pts > 0 and avg_rvol > 2.0:
            pts += 10

        return {'score': pts, 'days_elevated': days_above, 'avg_rvol': round(avg_rvol, 2)}

    def _volume_acceleration(self, row: pd.Series) -> Dict:
        """v5: Detect short-term volume ramp (3-day avg / 10-day avg)."""
        vol_ma_3 = row.get('vol_ma_3', 0)
        vol_ma_10 = row.get('vol_ma_10', 0)
        if pd.isna(vol_ma_3) or pd.isna(vol_ma_10) or vol_ma_10 == 0:
            return {'score': 0, 'vai': 0}
        vai = float(vol_ma_3 / vol_ma_10)
        if vai > 2.0:
            return {'score': 10, 'vai': round(vai, 2)}
        elif vai > 1.5:
            return {'score': 5, 'vai': round(vai, 2)}
        return {'score': 0, 'vai': round(vai, 2)}

    def _quiet_accumulation_v5(self, df: pd.DataFrame, lookback: int = 5) -> Dict:
        """v5: Multi-day quiet accumulation using 5-day price range and cumulative RVOL.
        
        Detects stealth buying: high volume with contained price movement.
        Tiered thresholds accommodate DSE small/mid-cap volatility.
        """
        if len(df) < lookback:
            return {'score': 0, 'price_range_pct': None, 'cum_rvol': 0}

        recent = df.tail(lookback)
        avg_close = recent['close'].mean()
        if avg_close == 0:
            return {'score': 0, 'price_range_pct': None, 'cum_rvol': 0}

        price_range_pct = float((recent['close'].max() - recent['close'].min()) / avg_close * 100)
        cum_rvol = float(recent['rvol'].sum())

        pts = 0
        # v7: Loosened — true stealth accumulation has RVOL ≈ 0.8–1.4, not 2.0+.
        # New tiers reward TIGHT price with AT-LEAST-AVERAGE volume.
        if price_range_pct < 4.0 and cum_rvol > 4.0:
            pts = 20   # Very tight + at-least-average volume (stealth)
        elif price_range_pct < 5.0 and cum_rvol > 10.0:
            pts = 20   # Original: very quiet + very high volume
        elif price_range_pct < 5.0 and cum_rvol > 4.0:
            pts = 15   # NEW: tight + average volume
        elif price_range_pct < 6.0 and cum_rvol > 5.0:
            pts = 12   # NEW: somewhat tight + above-avg volume
        elif price_range_pct < 8.0 and cum_rvol > 8.0:
            pts = 10   # Moderate range + decent volume
        elif price_range_pct < 10.0 and cum_rvol > 10.0:
            pts = 5    # Loose range + strong volume

        return {'score': pts, 'price_range_pct': round(price_range_pct, 2), 'cum_rvol': round(cum_rvol, 2)}

    def _close_position_ratio_score(self, row: pd.Series) -> Dict:
        """v5: Reward high-volume days where close is near the high (buying pressure)."""
        cpr = row.get('close_position_ratio', 0.5)
        rvol = row.get('rvol', 0)
        if pd.isna(cpr):
            cpr = 0.5
        if pd.isna(rvol):
            rvol = 0
        passed = cpr > 0.7 and rvol > 1.5
        return {'score': 10 if passed else 0, 'cpr': round(float(cpr), 2), 'passed': passed}

    def _obv_divergence(self, row: pd.Series) -> Dict:
        """v5/v7: Bullish OBV divergence — OBV rising while price flat/falling.

        v7: Allow a tiny positive price slope to count as "flat" so accumulation
        with subtle upward drift (very common on DSE) still fires.
        """
        obv_slope = row.get('obv_slope_20', 0)
        price_slope = row.get('price_slope_20', 0)
        if pd.isna(obv_slope) or pd.isna(price_slope):
            return {'score': 0, 'divergence': False, 'obv_slope': 0, 'price_slope': 0}
        # v7: price_slope <= 0.05 treated as flat-ish
        divergence = obv_slope > 0 and price_slope <= 0.05
        return {
            'score': 15 if divergence else 0,
            'divergence': divergence,
            'obv_slope': round(float(obv_slope), 2),
            'price_slope': round(float(price_slope), 4),
        }

    # ===== v6 NEW SCORING COMPONENTS =====

    def _price_tightening_score(self, row: pd.Series) -> Dict:
        """v6: Detect Bollinger Band squeeze — price compression before breakout.

        When BB width drops below 60% of its 20-day average, it signals
        that volatility is contracting. Syndicates accumulate during tight
        ranges, then trigger a breakout once loaded.
        """
        bb_width = row.get('bb_width', 0)
        bb_avg = row.get('bb_width_avg', 0)
        if pd.isna(bb_width) or pd.isna(bb_avg) or bb_avg == 0:
            return {'score': 0, 'squeeze': False, 'bb_width': 0, 'bb_avg': 0}

        ratio = float(bb_width / bb_avg)
        # v7: Loosened thresholds. Real coils on DSE rarely compress below 0.6.
        squeeze = ratio < 0.75
        tight = ratio < 0.90

        pts = 0
        if squeeze:
            pts = 20  # Strong squeeze — breakout imminent (was 15)
        elif tight:
            pts = 8   # Moderate tightening (was 5)

        return {
            'score': pts,
            'squeeze': squeeze,
            'bb_width': round(float(bb_width), 4),
            'bb_avg': round(float(bb_avg), 4),
            'ratio': round(ratio, 2),
        }

    def _consecutive_green_score(self, row: pd.Series) -> Dict:
        """v6: Reward consecutive green candles with above-average volume.

        3+ consecutive green+volume days = controlled buying (syndicate fingerprint).
        Random retail buying rarely produces this pattern.
        """
        consec = int(row.get('consec_green_vol', 0))
        if pd.isna(consec):
            consec = 0

        pts = 0
        # v7: Capped — this is a LAGGING confirmation indicator. By the time
        # we have 5+ consecutive green volume days, the move is well underway.
        if consec >= 5:
            pts = 10  # was 20
        elif consec >= 3:
            pts = 6   # was 10

        return {'score': pts, 'consecutive_days': consec}

    def _smart_money_divergence_score(self, row: pd.Series) -> Dict:
        """v6: Smart money divergence over last 10 days.

        Positive score = on high-volume days price moved up, on low-volume
        days price moved down. This pattern suggests informed buyers are
        accumulating while retail is selling on low-volume days.
        """
        sm_score = float(row.get('smart_money_score', 0))
        if pd.isna(sm_score):
            sm_score = 0

        # v7: Capped — this indicator mechanically reads "buying" after any
        # multi-day breakout because the up-days ARE the high-vol days.
        # Lagging confirmation; smaller weight.
        pts = 0
        if sm_score > 0.05:
            pts = 10  # was 15
        elif sm_score > 0.02:
            pts = 5   # was 8

        return {'score': pts, 'divergence_value': round(sm_score, 4)}

    def _vwap_proximity_score(self, row: pd.Series) -> Dict:
        """v6: Price staying near 5-day VWAP = institutional controlled buying.

        When price is within 1% of VWAP despite elevated volume, it signals
        institutional algorithms are controlling the price to fill large orders.
        """
        close = row.get('close', 0)
        vwap = row.get('vwap_5d', 0)
        rvol = row.get('rvol', 0)
        if pd.isna(close) or pd.isna(vwap) or vwap == 0 or pd.isna(rvol):
            return {'score': 0, 'distance_pct': None, 'near_vwap': False}

        distance_pct = abs(float(close) - float(vwap)) / float(vwap) * 100
        near_vwap = distance_pct < 1.0 and float(rvol) > 1.5

        pts = 10 if near_vwap else 0

        return {
            'score': pts,
            'distance_pct': round(distance_pct, 2),
            'near_vwap': near_vwap,
            'vwap_5d': round(float(vwap), 2),
        }

    def _sma_graduated_score(self, close: float, sma_200: float, df: pd.DataFrame) -> Dict:
        """v5: Graduated SMA scoring + crossover detection."""
        if pd.isna(sma_200) or sma_200 == 0:
            return {'score': 0, 'crossover': False, 'distance_pct': None}

        distance_pct = (close - sma_200) / sma_200 * 100

        # Crossover detection: was below SMA within last 3 days, now above
        crossover = False
        if len(df) >= 4:
            recent = df.tail(4)
            if (close > sma_200 and
                    any(recent.iloc[i]['close'] < recent.iloc[i]['sma_200']
                        for i in range(len(recent) - 1)
                        if pd.notna(recent.iloc[i].get('sma_200')))):
                crossover = True

        # v7: Softened the penalty band (real accumulation often happens just
        # below SMA) and added an over-extension band (the SMA bonus shouldn't
        # be the same for +5% above and +50% above).
        pts = 0
        if distance_pct > 35:        # Wildly over-extended — late entry
            pts = -10
        elif distance_pct > 25:      # Over-extended
            pts = -5
        elif distance_pct > 15:      # Mildly extended — no bonus, no penalty
            pts = 0
        elif distance_pct > 0:       # Healthy above SMA
            pts = 10
        elif distance_pct >= -3:     # Reclaim setup — slight BONUS (was -5)
            pts = 5
        elif distance_pct >= -10:    # 3-10% below — softer penalty (was -25)
            pts = -10
        else:                        # >10% below — unchanged hard penalty
            pts = -50

        if crossover:
            pts += 20  # Fresh trend reversal bonus (was 15)

        return {'score': pts, 'crossover': crossover, 'distance_pct': round(distance_pct, 2)}

    def _institutional_flow_score(self, row: pd.Series) -> Dict:
        """v5: Compare public_volume vs total volume to detect institutional presence."""
        total_vol = row.get('volume', 0)
        public_vol = row.get('public_volume', None)
        if pd.isna(public_vol) or public_vol is None or pd.isna(total_vol) or total_vol == 0:
            return {'score': 0, 'ratio': None, 'available': False}

        institutional_ratio = 1.0 - (float(public_vol) / float(total_vol))
        institutional_ratio = max(0.0, min(1.0, institutional_ratio))

        pts = 0
        if institutional_ratio > 0.40:
            pts = 15
        elif institutional_ratio > 0.20:
            pts = 10

        return {'score': pts, 'ratio': round(institutional_ratio * 100, 1), 'available': True}

    # ===== v7 NEW SCORING COMPONENTS =====

    def _late_entry_penalty(self, row: pd.Series, df: pd.DataFrame) -> Dict:
        """v7: Penalise stocks that have already extended.

        The single biggest gap in v6 was no penalty for late entries —
        a stock that had rallied 35% in a week scored the same as one
        that was just emerging from a base.
        """
        pts = 0
        flags = []

        # 5-day return penalty
        ret_5d = None
        if len(df) >= 6:
            close_5d_ago = df.iloc[-6]['close']
            if pd.notna(close_5d_ago) and close_5d_ago > 0:
                ret_5d = float((row['close'] - close_5d_ago) / close_5d_ago * 100)
                if ret_5d > 25:
                    pts -= 25; flags.append(f"+{ret_5d:.0f}% in 5d (extreme)")
                elif ret_5d > 15:
                    pts -= 15; flags.append(f"+{ret_5d:.0f}% in 5d")
                elif ret_5d > 10:
                    pts -= 8;  flags.append(f"+{ret_5d:.0f}% in 5d (mild)")

        # SMA over-extension penalty (separate from SMA bonus tier)
        sma = row.get('sma_200')
        dist_sma = None
        if pd.notna(sma) and sma > 0:
            dist_sma = float((row['close'] - sma) / sma * 100)
            if dist_sma > 40:
                pts -= 15; flags.append(f"{dist_sma:.0f}% above SMA (extreme)")
            elif dist_sma > 30:
                pts -= 8;  flags.append(f"{dist_sma:.0f}% above SMA")

        # Runaway candle: today's range > 2.5x ATR-14 AND today closed up >5%
        atr = row.get('ATR')
        if pd.notna(atr) and atr > 0:
            today_range = float(row['high'] - row['low'])
            pc = row.get('price_change_pct')
            if pd.notna(pc) and pc > 5 and today_range > 2.5 * atr:
                pts -= 8; flags.append("Runaway candle (range > 2.5x ATR)")

        return {
            'score': pts,
            'return_5d_pct': round(ret_5d, 2) if ret_5d is not None else None,
            'sma_distance_pct': round(dist_sma, 2) if dist_sma is not None else None,
            'flags': flags,
        }

    def _pre_breakout_coil(self, row: pd.Series, df: pd.DataFrame) -> Dict:
        """v7: Tight 10-day base + ATR contraction = setup ready to break.

        This is the *leading* indicator the old engine lacked. Fires during
        the coil — before the volume spike — so the BUY signal arrives BEFORE
        the move, not after.
        """
        if len(df) < 20:
            return {'score': 0, 'range_pct': None, 'atr_contracting': False}

        recent_10 = df.tail(10)
        avg_close = float(recent_10['close'].mean())
        if avg_close == 0:
            return {'score': 0, 'range_pct': None, 'atr_contracting': False}

        range_pct = float((recent_10['close'].max() - recent_10['close'].min()) / avg_close * 100)

        atr_now = row.get('ATR')
        atr_prior = df.iloc[-20].get('ATR') if 'ATR' in df.columns else None
        atr_contracting = (pd.notna(atr_now) and pd.notna(atr_prior)
                          and atr_prior > 0 and atr_now < 0.8 * atr_prior)

        pts = 0
        if range_pct < 5 and atr_contracting:
            pts = 25  # Strong coil
        elif range_pct < 6 and atr_contracting:
            pts = 20
        elif range_pct < 8 and atr_contracting:
            pts = 15
        elif range_pct < 6:
            pts = 12  # Tight without explicit contraction
        elif range_pct < 8:
            pts = 8

        return {
            'score': pts,
            'range_pct': round(range_pct, 2),
            'atr_contracting': bool(atr_contracting),
            'atr_now': round(float(atr_now), 3) if pd.notna(atr_now) else None,
            'atr_prior': round(float(atr_prior), 3) if pd.notna(atr_prior) else None,
        }

    # ===== v7 EARLY SCORE — parallel pre-breakout detector =====

    def calculate_early_score(self, row: pd.Series, df: pd.DataFrame) -> Dict:
        """v7: 5-factor pre-breakout score (0-100).

        Designed for one job: identify stocks about to break out of a tight
        base on the FIRST tell day, BEFORE the explosive move. Independent of
        the main score (which is a confirmation engine).

        Components (max 100):
          Tight Base       0-25  — 10d close range as % of price
          Goldilocks Vol   0-25  — RVOL 1.8–3.0x sweet spot (NOT 5x+)
          Closing Tell     0-20  — Green close + upper-70% CPR + > prev close
          Near Resistance  0-15  — Within 2% of 10-day high
          Not Extended    -10–15 — 5-day return < 8% rewarded, > 25% penalised

        Signal tiers:
          score >= 60 → EARLY  (act now)
          score >= 40 → WATCH  (setting up, don't buy yet)
          else        → NONE
        """
        if len(df) < 11:
            return {'score': 0, 'raw_points': 0, 'signal': 'NONE',
                    'reasons': [], 'components': {}}

        components = {}
        reasons = []
        pts = 0

        recent_10 = df.tail(10)
        avg_close = float(recent_10['close'].mean()) if len(recent_10) > 0 else 0

        # 1. Tight Base
        tight_pts = 0
        range_pct_10d = None
        if avg_close > 0:
            range_pct_10d = float(
                (recent_10['close'].max() - recent_10['close'].min()) / avg_close * 100
            )
            if range_pct_10d < 4:
                tight_pts = 25
            elif range_pct_10d < 6:
                tight_pts = 18
            elif range_pct_10d < 8:
                tight_pts = 10
        pts += tight_pts
        if tight_pts > 0:
            reasons.append(f"Tight Base ({range_pct_10d:.1f}%/10d)")
        components['tight_base'] = {
            'points': tight_pts,
            'range_pct_10d': round(range_pct_10d, 2) if range_pct_10d is not None else None,
        }

        # 2. Goldilocks Volume — sweet spot RVOL, NOT extreme
        rvol = float(row.get('rvol', 0)) if pd.notna(row.get('rvol', 0)) else 0
        if 1.8 <= rvol <= 3.0:
            vol_pts = 25
        elif 1.5 <= rvol < 1.8:
            vol_pts = 18
        elif 3.0 < rvol <= 4.0:
            vol_pts = 12  # Borderline-late
        elif 1.2 <= rvol < 1.5:
            vol_pts = 8   # Mild interest
        else:
            vol_pts = 0   # Dead, or already exploded
        pts += vol_pts
        if vol_pts > 0:
            reasons.append(f"Goldilocks Vol ({rvol:.1f}x)")
        components['goldilocks_volume'] = {'points': vol_pts, 'rvol': round(rvol, 2)}

        # 3. Closing Tell
        close = float(row['close'])
        open_p = float(row.get('open', close))
        high = float(row.get('high', close))
        low = float(row.get('low', close))
        prev_close = float(df.iloc[-2]['close']) if len(df) >= 2 else close

        is_green = close > open_p
        day_range = high - low
        cpr = (close - low) / day_range if day_range > 0 else 0.5
        above_prev = close > prev_close

        if is_green and cpr > 0.6 and above_prev:
            tell_pts = 20
        elif is_green and above_prev:
            tell_pts = 10
        elif above_prev:
            tell_pts = 5
        else:
            tell_pts = 0
        pts += tell_pts
        if tell_pts >= 10:
            reasons.append("Strong Close")
        components['closing_tell'] = {
            'points': tell_pts, 'green': bool(is_green),
            'cpr': round(float(cpr), 2), 'above_prev': bool(above_prev),
        }

        # 4. Near Resistance (testing the lid of the base)
        high_10d = float(recent_10['high'].max()) if len(recent_10) > 0 else 0
        res_pts = 0
        dist_to_high = None
        if high_10d > 0:
            dist_to_high = float((high_10d - close) / high_10d * 100)
            if dist_to_high <= 2:
                res_pts = 15
            elif dist_to_high <= 4:
                res_pts = 8
        pts += res_pts
        if res_pts > 0:
            reasons.append("Testing 10d High")
        components['near_resistance'] = {
            'points': res_pts,
            'high_10d': round(high_10d, 2),
            'distance_pct': round(dist_to_high, 2) if dist_to_high is not None else None,
        }

        # 5. Not Extended (negative if already up big)
        ret_5d = None
        if len(df) >= 6:
            close_5d_ago = float(df.iloc[-6]['close'])
            if close_5d_ago > 0:
                ret_5d = (close - close_5d_ago) / close_5d_ago * 100

        if ret_5d is None:
            ext_pts = 0
        elif ret_5d < 8:
            ext_pts = 15
        elif ret_5d < 15:
            ext_pts = 8
        elif ret_5d < 25:
            ext_pts = 0
        else:
            ext_pts = -10
        pts += ext_pts
        if ext_pts > 0:
            reasons.append("Not Extended")
        elif ext_pts < 0:
            reasons.append(f"Already +{ret_5d:.0f}% in 5d")
        components['not_extended'] = {
            'points': ext_pts,
            'return_5d_pct': round(ret_5d, 2) if ret_5d is not None else None,
        }

        # Score & signal tier
        final_score = max(0, min(100, pts))
        # v7: EARLY tier requires an actual volume tell (vol_pts >= 12, i.e.
        # RVOL >= 1.5x). Without a volume signal, a tight base is just a
        # quiet stock — it can still WATCH, but it shouldn't say "buy now".
        if final_score >= 60 and vol_pts >= 12:
            signal = 'EARLY'
        elif final_score >= 40:
            signal = 'WATCH'
        else:
            signal = 'NONE'

        return {
            'score': final_score,
            'raw_points': pts,
            'signal': signal,
            'reasons': reasons,
            'components': components,
        }

    def calculate_score(self, row: pd.Series, df: pd.DataFrame,
                       paid_up_capital: Optional[float] = None) -> Dict:
        """
        v7 SCORING ENGINE — Re-weighted multi-factor with late-entry penalty.

        Positive components (max raw = 280 with low-float, 260 without):
        - Graduated RVOL:           0-40 pts   (capped from 60)
        - Quiet Accumulation (5D):  0-20 pts
        - Multi-Day Accumulation:   0-45 pts
        - Volume Acceleration:      0-10 pts
        - SMA Position:             -50 to +30 pts  (softened band, +20 crossover)
        - OBV Divergence:           0-15 pts
        - Close Position Ratio:     0-10 pts
        - Low Float:                0-20 pts
        - RR Ratio:                 -10 to +10 pts
        - Price Tightening (BB):    0-20 pts   (was 15)
        - Consecutive Green+Vol:    0-10 pts   (capped, lagging)
        - Smart Money Divergence:   0-10 pts   (capped, lagging)
        - VWAP Proximity:           0-10 pts
        - Pre-Breakout Coil (v7):   0-25 pts   (NEW — leading)
        - Late-Entry Penalty (v7): -48 to 0    (NEW — applied to raw_score, not max)
        """
        raw_score = 0
        reasons = []
        details = {}  # v5: per-component breakdown for detailed view

        current_price = row['close']
        rvol = row['rvol'] if pd.notna(row['rvol']) else 0

        # 1. Graduated RVOL
        rvol_pts = self._graduated_rvol_score(rvol)
        raw_score += rvol_pts
        if rvol_pts > 0:
            reasons.append(f"High RVOL ({rvol:.1f}x)")
        details['rvol'] = {'points': rvol_pts, 'value': round(float(rvol), 2)}

        # 2. Quiet Accumulation (v5 multi-day)
        qa = self._quiet_accumulation_v5(df)
        raw_score += qa['score']
        if qa['score'] > 0:
            reasons.append("Quiet Accumulation")
        details['quiet_accumulation'] = qa

        # 3. Multi-Day Accumulation
        mda = self._multi_day_accumulation(df)
        raw_score += mda['score']
        if mda['score'] > 0:
            reasons.append(f"Sustained Accumulation ({mda['days_elevated']}d)")
        details['multi_day_accumulation'] = mda

        # 4. Volume Acceleration
        va = self._volume_acceleration(row)
        raw_score += va['score']
        if va['score'] > 0:
            reasons.append(f"Vol Accelerating ({va['vai']:.1f}x)")
        details['volume_acceleration'] = va

        # 5. Graduated SMA + Crossover
        sma_200 = row['sma_200'] if pd.notna(row.get('sma_200')) else None
        sma_result = self._sma_graduated_score(current_price, sma_200, df) if sma_200 else {'score': 0, 'crossover': False, 'distance_pct': None}
        raw_score += sma_result['score']
        if sma_result['crossover']:
            reasons.append("Fresh SMA Crossover")
        elif sma_result['score'] >= 10:
            reasons.append("Above 200 SMA")
        elif sma_result['score'] < 0:
            reasons.append("Below 200 SMA")
        details['sma'] = sma_result

        # 6. OBV Divergence
        obv = self._obv_divergence(row)
        raw_score += obv['score']
        if obv['score'] > 0:
            reasons.append("Bullish OBV Divergence")
        details['obv_divergence'] = obv

        # 7. Close Position Ratio
        cpr = self._close_position_ratio_score(row)
        raw_score += cpr['score']
        if cpr['score'] > 0:
            reasons.append("Strong Close (near high)")
        details['close_position_ratio'] = cpr

        # 8. (Institutional Flow — removed, no data source exists on DSE)

        # 9. Low Float
        low_float_available = paid_up_capital is not None
        if low_float_available and paid_up_capital < self.low_cap_threshold:
            raw_score += 20
            reasons.append(f"Low Float ({paid_up_capital:.1f} Cr)")
        details['low_float'] = {
            'points': 20 if (low_float_available and paid_up_capital < self.low_cap_threshold) else 0,
            'available': low_float_available,
        }

        # ===== v6 NEW COMPONENTS =====

        # 10. Price Tightening (Bollinger Band Squeeze)
        pt = self._price_tightening_score(row)
        raw_score += pt['score']
        if pt['score'] > 0:
            reasons.append(f"Price Squeeze ({pt['ratio']:.0%} of avg)")
        details['price_tightening'] = pt

        # 11. Consecutive Green Candles with Volume
        cg = self._consecutive_green_score(row)
        raw_score += cg['score']
        if cg['score'] > 0:
            reasons.append(f"Buying Streak ({cg['consecutive_days']}d green+vol)")
        details['consecutive_green'] = cg

        # 12. Smart Money Divergence
        smd = self._smart_money_divergence_score(row)
        raw_score += smd['score']
        if smd['score'] > 0:
            reasons.append("Smart Money Buying")
        details['smart_money'] = smd

        # 13. VWAP Proximity
        vwap = self._vwap_proximity_score(row)
        raw_score += vwap['score']
        if vwap['score'] > 0:
            reasons.append("Near VWAP (controlled buying)")
        details['vwap_proximity'] = vwap

        # ===== END v6 =====

        # ===== v7 NEW COMPONENTS =====

        # 14. Pre-Breakout Coil (LEADING indicator)
        coil = self._pre_breakout_coil(row, df)
        raw_score += coil['score']
        if coil['score'] > 0:
            reasons.append(f"Pre-Breakout Coil ({coil['range_pct']}%/10d)")
        details['pre_breakout_coil'] = coil

        # 15. Late-Entry Penalty (suppress already-extended chases)
        le = self._late_entry_penalty(row, df)
        raw_score += le['score']  # negative or zero
        if le['score'] < 0:
            reasons.append(f"Late entry ({le['score']} pts: {', '.join(le['flags'])})")
        details['late_entry'] = le

        # ===== END v7 =====

        # 14. Support / Resistance / RR (softened penalty)
        sr_levels = self.find_support_resistance(df, current_price)
        nearest_support = sr_levels['nearest_support']
        nearest_resistance = sr_levels['nearest_resistance']

        atr = row['ATR'] if pd.notna(row['ATR']) else None
        recommended_stop = None
        rr_ratio = None

        if atr and nearest_support and nearest_resistance:
            stop_from_support = nearest_support * 0.98
            stop_from_atr = current_price - (1.5 * atr)
            recommended_stop = max(stop_from_support, stop_from_atr)

            rr_analysis = self.calculate_reward_risk_ratio(
                current_price, recommended_stop, nearest_resistance
            )
            if rr_analysis['valid']:
                rr_ratio = rr_analysis['ratio']
                if rr_analysis['recommended']:  # >= 2:1
                    raw_score += 10
                    reasons.append(f"Good RR Ratio ({rr_ratio}:1)")
                elif rr_ratio >= 1.0:  # 1:1 to 2:1 — neutral
                    pass  # no penalty, no bonus
                else:  # < 1:1 — mild warning
                    raw_score -= 10
                    reasons.append(f"Poor RR Ratio ({rr_ratio}:1)")

        details['rr'] = {'ratio': rr_ratio}

        # v7 denominator. Positive-only components:
        #   40 (rvol cap) + 20 (quiet) + 45 (mda) + 10 (vol_accel) + 30 (sma+xover)
        # + 15 (obv) + 10 (cpr) + 20 (low_float) + 10 (rr)
        # + 20 (bb cap) + 10 (consec_green cap) + 10 (smart_money cap) + 10 (vwap)
        # + 25 (pre_breakout_coil)
        # = 275 with low_float, 255 without
        # Late-entry penalty is negative-only and subtracts from raw_score
        # without inflating the denominator.
        max_possible = 275
        if not low_float_available:
            max_possible -= 20   # Paid-up capital data not provided

        final_score = max(0, min(100, round(raw_score / max_possible * 100)))

        return {
            'score': final_score,
            'raw_score': raw_score,
            'reasons': reasons,
            'support': nearest_support,
            'resistance': nearest_resistance,
            'stop_loss': recommended_stop,
            'rr_ratio': rr_ratio,
            'v5_details': details,
        }
    
    def calculate_breakout_signal(self, row: pd.Series, df: pd.DataFrame) -> Dict:
        """v9: regime-robust BREAKOUT entry (the only rule with positive edge in
        every year 2019-2026 — see module/__init__ notes).

        Fires when price breaks to a new ~20-day high WITH volume, while still
        EARLY in the move (20-day return under the cap), in a confirmed uptrend,
        and liquid. Returns {'is_breakout', 'reasons' (why it failed/passed),
        'checks'}. Purely structural — independent of the legacy score so it can
        be surfaced additively without touching BUY/EARLY behaviour.
        """
        fails, checks = [], {}
        close = float(row['close']) if pd.notna(row.get('close')) else 0.0

        # 1. Breakout — at / above the N-day high (within tolerance)
        hi = None
        if len(df) >= self.breakout_high_lookback:
            hi = float(df['high'].tail(self.breakout_high_lookback).max())
        dist_hi = ((close / hi - 1) * 100) if hi else None
        breakout_ok = dist_hi is not None and dist_hi > -self.breakout_high_tol_pct
        checks['dist_to_high_pct'] = round(dist_hi, 2) if dist_hi is not None else None
        if not breakout_ok:
            fails.append(f'Not breaking {self.breakout_high_lookback}d high'
                         if dist_hi is not None else 'Insufficient history')

        # 2. Uptrend — above the 200-day SMA
        sma200 = row.get('sma_200')
        uptrend_ok = bool(pd.notna(sma200) and sma200 > 0 and close > sma200)
        checks['uptrend'] = uptrend_ok
        if not uptrend_ok:
            fails.append('Below 200-SMA (not an uptrend)')

        # 3. Not extended — 20-day return under the cap
        ret_20d = None
        if len(df) >= 21:
            c20 = float(df.iloc[-21]['close'])
            if c20 > 0:
                ret_20d = (close - c20) / c20 * 100
        ext_ok = ret_20d is not None and ret_20d < self.breakout_max_ext_20d
        checks['ret_20d'] = round(ret_20d, 2) if ret_20d is not None else None
        if not ext_ok:
            fails.append(f'Already extended ({ret_20d:.0f}%/20d)'
                         if ret_20d is not None else 'Insufficient history')

        # 4. Volume confirmation
        rvol = float(row['rvol']) if pd.notna(row.get('rvol')) else 0.0
        rvol_ok = rvol >= self.breakout_min_rvol
        checks['rvol'] = round(rvol, 2)
        if not rvol_ok:
            fails.append(f'Weak volume ({rvol:.1f}x < {self.breakout_min_rvol}x)')

        # 5. Liquidity / price floor
        avg_vol20 = row.get('avg_volume_20')
        liquid_ok = bool(pd.notna(avg_vol20) and avg_vol20 >= self.breakout_min_avg_vol20)
        price_ok = close >= self.breakout_min_price
        checks['avg_vol20'] = int(avg_vol20) if pd.notna(avg_vol20) else None
        if not liquid_ok:
            fails.append('Thin (20d avg vol < %d)' % self.breakout_min_avg_vol20)
        if not price_ok:
            fails.append('Price < %g (penny/MF unit)' % self.breakout_min_price)

        # Extra context + the rule thresholds, so the UI's "why it fired" modal
        # can show exact values vs the rule for every criterion.
        checks['close'] = round(close, 2)
        checks['high_20d'] = round(hi, 2) if hi else None
        checks['sma200'] = round(float(sma200), 2) if pd.notna(sma200) and sma200 else None
        checks['lookback'] = self.breakout_high_lookback
        checks['tol_pct'] = self.breakout_high_tol_pct
        checks['max_ext_20d'] = self.breakout_max_ext_20d
        checks['min_rvol'] = self.breakout_min_rvol
        checks['min_avg_vol20'] = self.breakout_min_avg_vol20
        checks['min_price'] = self.breakout_min_price

        # Per-stock QUALITY factors (used by the UI quality grade). The study
        # found tighter bases and lower volatility separate winning breakouts
        # from losers (alongside market regime, which the UI adds).
        try:
            r10 = df['close'].tail(10)
            base_tight = float((r10.max() - r10.min()) / r10.mean() * 100) if len(r10) and r10.mean() else None
        except Exception:
            base_tight = None
        atr_val = row.get('ATR')
        atr_pct = (float(atr_val) / close * 100) if (pd.notna(atr_val) and close > 0) else None
        checks['base_tight_pct'] = round(base_tight, 2) if base_tight is not None else None
        checks['atr_pct'] = round(atr_pct, 2) if atr_pct is not None else None

        return {'is_breakout': len(fails) == 0, 'reasons': fails, 'checks': checks}

    def calculate_reversal_signal(self, row: pd.Series, df: pd.DataFrame) -> Dict:
        """v10: REVERSAL entry — buy a confirmed bottom (the mean-reversion edge).

        DSE is a mean-reverting market: deeply oversold stocks that print their
        FIRST green day on volume bounce hard. Backtest 2019-2026 (511 firings):
        WIN 68.5% / +6.15% avg at +10d (median +5.22%), payoff 1.74, knife>15%
        only 3.3% — vs a 41.5% / -0.94%-median universe. Fires when:
          1. Deeply oversold      (RSI < reversal_max_rsi)
          2. First green day       (close > prior close — the turn is starting)
          3. Volume confirmation   (rvol >= reversal_min_rvol — capitulation/turn)
          4. Room to run           (>= reversal_min_room_pct below the 120d high)
          5. Liquid / not a penny  (avg_vol20 + price floor)
        Purely structural and additive — independent of breakout & legacy score.
        Returns {'is_reversal', 'reasons' (why it failed/passed), 'checks'}.
        """
        fails, checks = [], {}
        close = float(row['close']) if pd.notna(row.get('close')) else 0.0

        # 1. Oversold — Wilder RSI below the threshold
        rsi = float(row['rsi']) if pd.notna(row.get('rsi')) else 50.0
        oversold_ok = rsi < self.reversal_max_rsi
        checks['rsi'] = round(rsi, 1)
        if not oversold_ok:
            fails.append(f'Not oversold (RSI {rsi:.0f} >= {self.reversal_max_rsi:.0f})')

        # 2. First green day — today closes above the prior close (the turn)
        prev_close = float(df.iloc[-2]['close']) if len(df) >= 2 else close
        green_ok = close > prev_close > 0
        checks['prev_close'] = round(prev_close, 2)
        checks['green_day'] = green_ok
        if not green_ok:
            fails.append('No green reversal day (close <= prior close)')

        # 3. Volume confirmation
        rvol = float(row['rvol']) if pd.notna(row.get('rvol')) else 0.0
        rvol_ok = rvol >= self.reversal_min_rvol
        checks['rvol'] = round(rvol, 2)
        if not rvol_ok:
            fails.append(f'Weak volume ({rvol:.1f}x < {self.reversal_min_rvol}x)')

        # 4. Room to run — sufficiently below the 120-day high
        hi120 = row.get('high_120')
        room_pct = ((close / float(hi120) - 1) * 100) if (pd.notna(hi120) and hi120 and hi120 > 0) else None
        room_ok = room_pct is not None and room_pct <= -self.reversal_min_room_pct
        checks['room_pct'] = round(room_pct, 2) if room_pct is not None else None
        checks['high_120'] = round(float(hi120), 2) if (pd.notna(hi120) and hi120) else None
        if not room_ok:
            fails.append(f'Little room ({room_pct:.0f}% below 120d high)'
                         if room_pct is not None else 'Insufficient history for 120d high')

        # 5. Liquidity / price floor
        avg_vol20 = row.get('avg_volume_20')
        liquid_ok = bool(pd.notna(avg_vol20) and avg_vol20 >= self.reversal_min_avg_vol20)
        price_ok = close >= self.reversal_min_price
        checks['avg_vol20'] = int(avg_vol20) if pd.notna(avg_vol20) else None
        if not liquid_ok:
            fails.append('Thin (20d avg vol < %d)' % self.reversal_min_avg_vol20)
        if not price_ok:
            fails.append('Price < %g (penny/MF unit)' % self.reversal_min_price)

        # Quality factors (drive the UI grade — from the study's rank-IC vs +10d:
        # lower RSI, further below the 50-SMA, sharper recent drop, higher rvol).
        sma50 = row.get('sma_50')
        dist50 = ((close / float(sma50) - 1) * 100) if (pd.notna(sma50) and sma50 and sma50 > 0) else None
        ret5 = None
        if len(df) >= 6:
            c5 = float(df.iloc[-6]['close'])
            if c5 > 0:
                ret5 = (close - c5) / c5 * 100
        checks['dist50'] = round(dist50, 2) if dist50 is not None else None
        checks['ret5'] = round(ret5, 2) if ret5 is not None else None

        # Thresholds, so the UI "why it fired" modal can show value-vs-rule.
        checks['close'] = round(close, 2)
        checks['max_rsi'] = self.reversal_max_rsi
        checks['min_rvol'] = self.reversal_min_rvol
        checks['min_room_pct'] = self.reversal_min_room_pct
        checks['min_avg_vol20'] = self.reversal_min_avg_vol20
        checks['min_price'] = self.reversal_min_price

        return {'is_reversal': len(fails) == 0, 'reasons': fails, 'checks': checks}

    def generate_signal(self, score: int) -> str:
        """
        Generate trading signal based on score (v7 thresholds).

        v7 re-tuning: pre-breakout coil now contributes, RVOL is capped,
        and the late-entry penalty actively suppresses already-extended
        stocks. The BUY threshold drops slightly so legitimate early-stage
        setups (which v6 buried at WAIT) surface as BUY.

          >= 50: BUY     (was 55)
          >= 28: WAIT    (was 30)
          <  28: IGNORE
        """
        if score >= 50:
            return 'BUY'
        elif score >= 28:
            return 'WAIT'
        else:
            return 'IGNORE'
    
    def analyze_ticker(self, ticker: str, paid_up_capital: Optional[float] = None,
                       analysis_date: Optional[str] = None) -> Dict:
        """
        Analyze a single ticker and generate trading signal
        
        Args:
            ticker: Stock ticker symbol
            paid_up_capital: Paid-up capital in Crores
            analysis_date: Specific date to analyze (YYYY-MM-DD), uses latest if None
            
        Returns:
            Dictionary with analysis results
        """
        try:
            # Get stock data
            raw_df = self.db.get_stock_data(ticker)

            if raw_df.empty:
                return {
                    'ticker': ticker,
                    'status': 'error',
                    'message': 'No data available'
                }

            # Calculate indicators (keep raw_df around for yesterday recompute)
            df = self.calculate_indicators(raw_df)

            # Get the row to analyze FIRST — needed before the survival/trend
            # gates so the reversal signal can exempt deep-dip candidates.
            if analysis_date:
                mask = df['date'] == pd.to_datetime(analysis_date)
                if not mask.any():
                    return {
                        'ticker': ticker,
                        'status': 'error',
                        'message': f'No data for date {analysis_date}'
                    }
                row = df[mask].iloc[-1]
            else:
                row = df.iloc[-1]  # Latest data

            # v10: REVERSAL signal (mean-reversion edge — buy the bottom).
            # Computed up-front: reversal candidates are deeply oversold and
            # below their moving averages, so the downtrend/survival gates below
            # would otherwise drop the very stocks this signal exists to surface.
            reversal = self.calculate_reversal_signal(row, df)

            # Apply survival filters — reversal candidates are EXEMPT (they are
            # liquid & active by construction: rvol>=1.5 and avg_vol20>=50k are
            # already enforced, so they can't be ghost-town / stuck / thin).
            filter_result = self.apply_survival_filters(df, ticker)
            if not filter_result['passed'] and not reversal['is_reversal']:
                return {
                    'ticker': ticker,
                    'status': 'filtered',
                    'message': filter_result['reason']
                }
            
            # *** v5: GRADUATED TREND FILTER ***
            # Only hard-filter stocks >10% below 200 SMA (deep downtrend).
            # Stocks 0-10% below are penalised via graduated scoring but still analysed.
            if pd.notna(row['sma_200']) and row['sma_200'] > 0:
                distance_pct = (row['close'] - row['sma_200']) / row['sma_200'] * 100
                # Reversal candidates are EXEMPT — being below the 200-SMA is the
                # whole point of a mean-reversion / buy-the-bottom entry.
                if distance_pct < -10 and not reversal['is_reversal']:
                    return {
                        'ticker': ticker,
                        'status': 'filtered',
                        'message': f'Deep Downtrend ({distance_pct:.1f}% below 200 SMA)',
                        'date': row['date'].strftime('%Y-%m-%d'),
                        'close': round(row['close'], 2),
                        'sma_200': round(row['sma_200'], 2),
                        'price_change_pct': round(row['price_change_pct'], 2) if pd.notna(row['price_change_pct']) else 0,
                        'trend_status': 'DOWNTREND'
                    }
            
            # Calculate score (pass df for support/resistance calculation)
            score_result = self.calculate_score(row, df, paid_up_capital)

            # Generate signal
            signal = self.generate_signal(score_result['score'])

            # v7: Parallel EarlyScore (leading pre-breakout detector)
            early_result = self.calculate_early_score(row, df)

            # v9: additive BREAKOUT signal (proven positive edge). Computed
            # alongside — does NOT alter the legacy BUY/EARLY signals.
            breakout = self.calculate_breakout_signal(row, df)
            # (v10 reversal already computed up-front, before the trend gates.)

            # v7: Yesterday's perspective for fresh-signal detection.
            # Recompute indicators on history excluding today so the OBV/BB
            # slopes are calculated as of yesterday.
            prev_signal = None
            prev_early_signal = None
            prev_breakout = None
            prev_reversal = None
            if not analysis_date and len(raw_df) >= 21:
                try:
                    df_y = self.calculate_indicators(raw_df.iloc[:-1])
                    if len(df_y) > 0:
                        prev_row_y = df_y.iloc[-1]
                        prev_score = self.calculate_score(prev_row_y, df_y, paid_up_capital)
                        prev_signal = self.generate_signal(prev_score['score'])
                        prev_early = self.calculate_early_score(prev_row_y, df_y)
                        prev_early_signal = prev_early['signal']
                        prev_breakout = self.calculate_breakout_signal(prev_row_y, df_y)['is_breakout']
                        prev_reversal = self.calculate_reversal_signal(prev_row_y, df_y)['is_reversal']
                except Exception as e:
                    logger.debug(f"Fresh-signal recompute failed for {ticker}: {e}")

            is_fresh_buy = bool(signal == 'BUY' and prev_signal != 'BUY')
            is_fresh_early = bool(early_result['signal'] == 'EARLY' and prev_early_signal != 'EARLY')
            is_fresh_breakout = bool(breakout['is_breakout'] and not prev_breakout)
            is_fresh_reversal = bool(reversal['is_reversal'] and not prev_reversal)

            # v8: intraday entry-price guidance (advisory — warn, don't block).
            prev_close_val = (float(df.iloc[-2]['close']) if len(df) >= 2
                              else float(row.get('open', row['close'])))
            entry_guidance = compute_entry_guidance(
                current_price=float(row['close']),
                day_low=float(row['low']) if pd.notna(row.get('low')) else None,
                day_high=float(row['high']) if pd.notna(row.get('high')) else None,
                prev_close=prev_close_val,
                vwap=float(row['vwap_5d']) if pd.notna(row.get('vwap_5d')) else None,
                support=score_result.get('support'),
            )
            
            # Determine market status
            current_time = datetime.now(pytz.timezone('Asia/Dhaka'))
            is_market_open = 10 <= current_time.hour < 14 or (current_time.hour == 14 and current_time.minute <= 30)
            is_intraday = 'is_final' in row and row['is_final'] == 0
            
            # Calculate volume fields
            # CURRENT VOL: Always today's actual volume from database
            current_vol = int(row['volume'])
            
            # LAST CLOSING VOL: Previous day's final volume
            if len(df) >= 2:
                if is_intraday:
                    # If today is intraday, last closing is yesterday's final
                    last_closing_vol = int(df.iloc[-2]['volume'])
                else:
                    # If today is final, last closing is also today (for EOD display)
                    last_closing_vol = current_vol
            else:
                last_closing_vol = current_vol
            
            # PROJECTED VOL: Extrapolated EOD volume (only if market open AND intraday)
            projected_vol = None
            if is_market_open and is_intraday:
                projected_vol = int(row['projected_vol']) if pd.notna(row['projected_vol']) else None
            
            # Prepare result with enhanced fields
            result = {
                'ticker': ticker,
                'status': 'success',
                'date': row['date'].strftime('%Y-%m-%d'),
                'close': round(row['close'], 2),
                'volume': int(row['volume']),
                'last_closing_vol': last_closing_vol,
                'current_vol': current_vol,  # ALWAYS show today's actual volume
                'projected_vol': projected_vol,
                'is_market_open': is_market_open,
                'is_intraday': is_intraday,
                'rvol': round(row['rvol'], 2) if pd.notna(row['rvol']) else 0,
                'avg_volume_20': int(row['avg_volume_20']) if pd.notna(row['avg_volume_20']) else 0,
                'price_change_pct': round(row['price_change_pct'], 2) if pd.notna(row['price_change_pct']) else 0,
                'sma_200': round(row['sma_200'], 2) if pd.notna(row['sma_200']) else None,
                'paid_up_capital': paid_up_capital,
                'score': score_result['score'],
                'signal': signal,
                'reasons': score_result['reasons'],
                
                # v4 NEW FIELDS: Support/Resistance and Risk Management
                'nearest_support': round(score_result['support'], 2) if score_result['support'] else None,
                'nearest_resistance': round(score_result['resistance'], 2) if score_result['resistance'] else None,
                'recommended_stop_loss': round(score_result['stop_loss'], 2) if score_result['stop_loss'] else None,
                'reward_risk_ratio': score_result['rr_ratio'],
                'atr': round(row['ATR'], 2) if pd.notna(row['ATR']) else None,
                'trend_status': 'UPTREND' if (pd.notna(row['sma_200']) and row['close'] > row['sma_200']) else 'NEAR_SMA',
                'raw_score': score_result.get('raw_score', 0),
                'v5_details': self._sanitize_for_json(score_result.get('v5_details', {})),

                # ===== v7 NEW FIELDS =====
                'early_score': early_result['score'],
                'early_signal': early_result['signal'],
                'early_reasons': early_result['reasons'],
                'early_components': self._sanitize_for_json(early_result.get('components', {})),
                'is_fresh_buy': is_fresh_buy,
                'is_fresh_early': is_fresh_early,
                'prev_signal': prev_signal,
                'prev_early_signal': prev_early_signal,
                # Combined "best" score for sorting on the front-end
                'signal_strength': max(score_result['score'], early_result['score']),

                # ===== v9 BREAKOUT SIGNAL (additive, proven edge) =====
                'breakout_signal': breakout['is_breakout'],
                'breakout_reasons': breakout['reasons'],
                'breakout_checks': self._sanitize_for_json(breakout['checks']),
                'is_fresh_breakout': is_fresh_breakout,

                # ===== v10 REVERSAL SIGNAL (additive, mean-reversion edge) =====
                'reversal_signal': reversal['is_reversal'],
                'reversal_reasons': reversal['reasons'],
                'reversal_checks': self._sanitize_for_json(reversal['checks']),
                'is_fresh_reversal': is_fresh_reversal,

                # ===== v8 ENTRY-PRICE GUIDANCE =====
                'prev_close': entry_guidance['prev_close'],
                'day_low': entry_guidance['day_low'],
                'day_high': entry_guidance['day_high'],
                'range_position': entry_guidance['range_position'],
                'recommended_entry': entry_guidance['recommended_entry'],
                'entry_quality': entry_guidance['entry_quality'],
                'entry_warning': entry_guidance['entry_warning'],
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return {
                'ticker': ticker,
                'status': 'error',
                'message': str(e)
            }

    # ----------------------------
    # Detailed analysis (for UI debugging)
    # ----------------------------
    def _safe_float(self, v):
        """Convert numpy/pandas scalars to JSON-serializable python floats."""
        try:
            if v is None:
                return None
            if pd.isna(v):
                return None
            return float(v)
        except Exception:
            return None

    def evaluate_survival_filters_detailed(self, df: pd.DataFrame) -> Dict:
        """Same logic as apply_survival_filters(), but returns per-rule breakdown."""
        if df is None or len(df) == 0:
            return {
                'passed': False,
                'reason': 'No data',
                'rules': {
                    'ghost_town': {'passed': False, 'details': 'No data'},
                    'price_stuck': {'passed': False, 'details': 'No data'},
                    'min_volume': {'passed': False, 'details': 'No data'},
                }
            }

        recent_df_5 = df.tail(5)
        recent_df_3 = df.tail(3)
        latest_volume = self._safe_float(df['volume'].iloc[-1])

        # Rule 1: Ghost Town
        ghost_passed = True
        ghost_details = 'Not enough rows'
        if len(recent_df_3) >= 3:
            last_3_vols = [int(x) for x in recent_df_3['volume'].values.tolist()]
            ghost_passed = not np.all(np.array(last_3_vols) == 0)
            ghost_details = f"Last 3 volumes = {last_3_vols}"

        # Rule 2: Price stuck
        price_stuck_passed = True
        price_stuck_details = 'Not enough rows'
        if len(recent_df_5) >= 5:
            price_std = self._safe_float(recent_df_5['close'].std())
            price_stuck_passed = (price_std is None) or (price_std >= 0.01)
            price_stuck_details = f"5D close std = {price_std:.5f}" if price_std is not None else '5D close std = N/A'

        # Rule 3: Min volume
        min_volume_passed = (latest_volume is not None) and (latest_volume >= 50000)
        min_volume_details = f"Latest volume = {int(latest_volume) if latest_volume is not None else 'N/A'} (min 50,000)"

        passed = ghost_passed and price_stuck_passed and min_volume_passed
        if not passed:
            # Keep reason consistent with apply_survival_filters
            if not ghost_passed:
                reason = 'Ghost Town - Zero volume for 3 days'
            elif not price_stuck_passed:
                reason = 'Price stuck at floor/ceiling'
            else:
                reason = f'Low volume: {int(latest_volume) if latest_volume is not None else 0}'
        else:
            reason = 'All filters passed'

        return {
            'passed': passed,
            'reason': reason,
            'rules': {
                'ghost_town': {'passed': ghost_passed, 'details': ghost_details},
                'price_stuck': {'passed': price_stuck_passed, 'details': price_stuck_details},
                'min_volume': {'passed': min_volume_passed, 'details': min_volume_details},
            }
        }

    def _sanitize_for_json(self, obj):
        """Recursively convert numpy types to native Python for JSON serialization."""
        import numpy as np
        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._sanitize_for_json(v) for v in obj]
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    def score_history(
        self,
        ticker: str,
        days: int = 20,
        paid_up_capital: Optional[float] = None,
    ) -> Dict:
        """Replay the analyzer day-by-day over the last `days` trading days.

        For each day we slice the raw history to that date and recompute
        indicators, so per-row indicators (OBV slope, smart-money, etc.,
        which calculate_indicators only fills for the LAST row) are correct
        AS-OF that day — exactly how the engine would have scored it on the
        settled bar. This is the diagnostic that shows how a stock's MAIN
        score and EarlyScore evolved into (or out of) a BUY.

        Returns rows oldest-first. The latest row reflects today's live state
        (projected volume during market hours); earlier rows are settled.
        """
        try:
            ticker = (ticker or '').upper().strip()
            if not ticker:
                return {'ticker': ticker, 'status': 'error',
                        'message': 'Ticker is required', 'history': []}

            raw_df = self.db.get_stock_data(ticker)
            if raw_df.empty:
                return {'ticker': ticker, 'status': 'error',
                        'message': 'No data available', 'history': []}

            raw_df = raw_df.sort_values('date').reset_index(drop=True)
            days = max(1, min(int(days or 20), 60))
            target_dates = list(raw_df['date'].tail(days))

            history = []
            for d in target_dates:
                sub = raw_df[raw_df['date'] <= d].copy()
                if len(sub) < 2:
                    continue
                ind = self.calculate_indicators(sub)
                last = ind.iloc[-1]
                try:
                    score_res = self.calculate_score(last, ind, paid_up_capital)
                    signal = self.generate_signal(int(score_res.get('score', 0)))
                except Exception as e:
                    logger.debug(f"score_history score failed {ticker} {d}: {e}")
                    score_res = {'score': 0, 'raw_score': 0, 'v5_details': {}}
                    signal = 'ERR'
                try:
                    early = self.calculate_early_score(last, ind)
                except Exception as e:
                    logger.debug(f"score_history early failed {ticker} {d}: {e}")
                    early = {'score': 0, 'signal': 'NONE'}

                le = (score_res.get('v5_details') or {}).get('late_entry') or {}
                is_intraday = bool('is_final' in last and last.get('is_final', 1) == 0)
                history.append({
                    'date': last['date'].strftime('%Y-%m-%d'),
                    'close': self._safe_float(last.get('close')),
                    'price_change_pct': self._safe_float(last.get('price_change_pct')),
                    'volume': int(last['volume']) if pd.notna(last.get('volume')) else 0,
                    'rvol': self._safe_float(last.get('rvol')),
                    'raw_score': int(score_res.get('raw_score', 0)),
                    'score': int(score_res.get('score', 0)),
                    'signal': signal,
                    'early_score': int(early.get('score', 0)),
                    'early_signal': early.get('signal', 'NONE'),
                    'late_entry_pts': int(le.get('score', 0)) if le else 0,
                    'return_5d_pct': self._safe_float(le.get('return_5d_pct')) if le else None,
                    'is_intraday': is_intraday,
                })

            return {'ticker': ticker, 'status': 'success',
                    'days': len(history), 'history': history}
        except Exception as e:
            logger.error(f"score_history failed for {ticker}: {e}")
            return {'ticker': ticker, 'status': 'error',
                    'message': str(e), 'history': []}

    def analyze_ticker_detailed(
        self,
        ticker: str,
        paid_up_capital: Optional[float] = None,
        analysis_date: Optional[str] = None,
    ) -> Dict:
        """Return a detailed breakdown of every calculation step for a ticker.

        This is used by the manual-check UI to validate current position of a stock.
        """
        try:
            ticker = ticker.upper().strip()
            if not ticker:
                return {'ticker': ticker, 'status': 'error', 'message': 'Ticker is required'}

            raw_df = self.db.get_stock_data(ticker)
            if raw_df.empty:
                return {'ticker': ticker, 'status': 'error', 'message': 'No data available'}

            df = self.calculate_indicators(raw_df)

            # Select row
            if analysis_date:
                mask = df['date'] == pd.to_datetime(analysis_date)
                if not mask.any():
                    return {'ticker': ticker, 'status': 'error', 'message': f'No data for date {analysis_date}'}
                row = df[mask].iloc[-1]
            else:
                row = df.iloc[-1]

            current_time = datetime.now(pytz.timezone('Asia/Dhaka'))
            is_market_open = 10 <= current_time.hour < 14 or (current_time.hour == 14 and current_time.minute <= 30)
            is_intraday = bool('is_final' in row and row.get('is_final', 1) == 0)

            # Volume fields
            current_vol = int(row['volume']) if pd.notna(row.get('volume')) else 0
            if len(df) >= 2:
                if is_intraday:
                    last_closing_vol = int(df.iloc[-2]['volume']) if pd.notna(df.iloc[-2].get('volume')) else current_vol
                else:
                    last_closing_vol = current_vol
            else:
                last_closing_vol = current_vol

            projected_vol = None
            if is_market_open and is_intraday:
                pv = row.get('projected_vol')
                projected_vol = int(pv) if pd.notna(pv) else None

            # Filters breakdown
            survival = self.evaluate_survival_filters_detailed(df)
            trend_close = self._safe_float(row.get('close'))
            trend_sma_200 = self._safe_float(row.get('sma_200'))
            # v5: Updated trend filter — graduated, matches analyze_ticker()
            trend_passed = True
            trend_reason = 'Above 200 SMA'
            if trend_sma_200 is not None and trend_close is not None:
                sma_distance_pct = (trend_close - trend_sma_200) / trend_sma_200 * 100 if trend_sma_200 > 0 else 0
                if sma_distance_pct < -10:
                    trend_passed = False
                    trend_reason = f'Deep Downtrend ({sma_distance_pct:.1f}% below 200 SMA)'
                elif trend_close < trend_sma_200:
                    trend_reason = f'Near 200 SMA ({sma_distance_pct:.1f}% below)'

            # Support / resistance and risk
            sr = self.find_support_resistance(df, trend_close if trend_close is not None else 0.0)
            nearest_support = self._safe_float(sr.get('nearest_support'))
            nearest_resistance = self._safe_float(sr.get('nearest_resistance'))
            all_support_levels = [self._safe_float(x) for x in (sr.get('all_support_levels') or [])]
            all_resistance_levels = [self._safe_float(x) for x in (sr.get('all_resistance_levels') or [])]

            atr = self._safe_float(row.get('ATR'))
            stop_from_support = None
            stop_from_atr = None
            recommended_stop = None
            rr = None

            if atr and nearest_support and trend_close:
                stop_from_support = nearest_support * 0.98
                stop_from_atr = trend_close - (1.5 * atr)
                recommended_stop = max(stop_from_support, stop_from_atr)

            if recommended_stop and nearest_resistance and trend_close:
                rr = self.calculate_reward_risk_ratio(trend_close, recommended_stop, nearest_resistance)

            # v5: Use calculate_score() directly — single source of truth
            score_result = self.calculate_score(row, df, paid_up_capital)
            v5d = score_result.get('v5_details', {})

            # Build breakdown list from v5 details for UI
            breakdown = []
            rvol = self._safe_float(row.get('rvol')) or 0.0
            price_change_pct = self._safe_float(row.get('price_change_pct'))

            # 1. Graduated RVOL
            rvol_d = v5d.get('rvol', {})
            breakdown.append({
                'name': 'Graduated RVOL',
                'passed': rvol_d.get('points', 0) > 0,
                'points': rvol_d.get('points', 0),
                'details': f"RVOL={rvol:.2f}x → +{rvol_d.get('points', 0)} pts (tiers: ≥4.0→60, ≥2.5→50, ≥2.0→30, ≥1.5→15)",
            })

            # 2. Quiet Accumulation (5D)
            qa_d = v5d.get('quiet_accumulation', {})
            breakdown.append({
                'name': 'Quiet Accumulation (5D)',
                'passed': qa_d.get('score', 0) > 0,
                'points': qa_d.get('score', 0),
                'details': f"5D range={qa_d.get('price_range_pct', 'N/A')}% (< 5%), cumRVOL={qa_d.get('cum_rvol', 0)} (> 10)",
            })

            # 3. Multi-Day Accumulation
            mda_d = v5d.get('multi_day_accumulation', {})
            breakdown.append({
                'name': 'Multi-Day Accumulation',
                'passed': mda_d.get('score', 0) > 0,
                'points': mda_d.get('score', 0),
                'details': f"{mda_d.get('days_elevated', 0)}/5 days RVOL>1.5, avg={mda_d.get('avg_rvol', 0)}x",
            })

            # 4. Volume Acceleration
            va_d = v5d.get('volume_acceleration', {})
            breakdown.append({
                'name': 'Volume Acceleration',
                'passed': va_d.get('score', 0) > 0,
                'points': va_d.get('score', 0),
                'details': f"VAI (3d/10d)={va_d.get('vai', 0)}x (>2.0→+10, >1.5→+5)",
            })

            # 5. SMA Position
            sma_d = v5d.get('sma', {})
            sma_pts = sma_d.get('score', 0)
            breakdown.append({
                'name': 'SMA 200 Position',
                'passed': sma_pts > 0,
                'points': sma_pts,
                'details': f"Distance={sma_d.get('distance_pct', 'N/A')}%, crossover={'YES' if sma_d.get('crossover') else 'no'}",
            })

            # 6. OBV Divergence
            obv_d = v5d.get('obv_divergence', {})
            breakdown.append({
                'name': 'OBV Divergence',
                'passed': obv_d.get('score', 0) > 0,
                'points': obv_d.get('score', 0),
                'details': f"OBV slope={obv_d.get('obv_slope', 0)}, price slope={obv_d.get('price_slope', 0)}, divergence={'YES' if obv_d.get('divergence') else 'no'}",
            })

            # 7. Close Position Ratio
            cpr_d = v5d.get('close_position_ratio', {})
            breakdown.append({
                'name': 'Close Position Ratio',
                'passed': cpr_d.get('score', 0) > 0,
                'points': cpr_d.get('score', 0),
                'details': f"CPR={cpr_d.get('cpr', 'N/A')} (>0.7 + RVOL>1.5)",
            })

            # 8. (Institutional Flow — removed, no data source on DSE)

            # 9. Low Float
            lf_d = v5d.get('low_float', {})
            breakdown.append({
                'name': 'Low Float',
                'passed': lf_d.get('points', 0) > 0,
                'points': lf_d.get('points', 0),
                'details': f"paid_up_capital={paid_up_capital}" if paid_up_capital else 'Not provided',
            })

            # 10. Price Tightening (v6)
            pt_d = v5d.get('price_tightening', {})
            breakdown.append({
                'name': 'Price Squeeze (BB)',
                'passed': pt_d.get('score', 0) > 0,
                'points': pt_d.get('score', 0),
                'details': f"BB width={pt_d.get('bb_width', 'N/A')}, ratio={pt_d.get('ratio', 'N/A')}x of avg (squeeze < 0.6)",
            })

            # 11. Consecutive Green+Vol (v6)
            cg_d = v5d.get('consecutive_green', {})
            breakdown.append({
                'name': 'Buying Streak',
                'passed': cg_d.get('score', 0) > 0,
                'points': cg_d.get('score', 0),
                'details': f"{cg_d.get('consecutive_days', 0)} consecutive green candles with above-avg volume",
            })

            # 12. Smart Money Divergence (v6)
            smd_d = v5d.get('smart_money', {})
            breakdown.append({
                'name': 'Smart Money',
                'passed': smd_d.get('score', 0) > 0,
                'points': smd_d.get('score', 0),
                'details': f"Divergence={smd_d.get('divergence_value', 0)} (big vol=up, small vol=down)",
            })

            # 13. VWAP Proximity (v6)
            vwap_d = v5d.get('vwap_proximity', {})
            breakdown.append({
                'name': 'VWAP Proximity',
                'passed': vwap_d.get('score', 0) > 0,
                'points': vwap_d.get('score', 0),
                'details': f"Distance={vwap_d.get('distance_pct', 'N/A')}% from 5D VWAP (< 1% + RVOL > 1.5)",
            })

            # 14. Pre-Breakout Coil (v7) — LEADING indicator
            coil_d = v5d.get('pre_breakout_coil', {})
            breakdown.append({
                'name': 'Pre-Breakout Coil',
                'passed': coil_d.get('score', 0) > 0,
                'points': coil_d.get('score', 0),
                'details': (
                    f"10d range={coil_d.get('range_pct', 'N/A')}%, ATR contracting="
                    f"{'YES' if coil_d.get('atr_contracting') else 'no'} "
                    f"(strong coil: range<5% + ATR shrinking → +25)"
                ),
            })

            # 15. Late-Entry Penalty (v7) — penalises already-extended stocks
            le_d = v5d.get('late_entry', {})
            le_pts = le_d.get('score', 0)
            le_flags = le_d.get('flags', [])
            breakdown.append({
                'name': 'Late-Entry Penalty',
                'passed': le_pts == 0,  # 0 means no penalty = good
                'points': le_pts,
                'details': (
                    f"5d return={le_d.get('return_5d_pct', 'N/A')}%, "
                    f"SMA dist={le_d.get('sma_distance_pct', 'N/A')}%"
                    f"{' — ' + '; '.join(le_flags) if le_flags else ' — no penalty'}"
                ),
            })

            # 16. RR Ratio
            rr_d = v5d.get('rr', {})
            rr_ratio_val = rr_d.get('ratio')
            rr_pts = 0
            if rr and rr.get('valid'):
                if rr.get('recommended'):
                    rr_pts = 10
                elif rr_ratio_val is not None and rr_ratio_val < 1.0:
                    rr_pts = -10
            breakdown.append({
                'name': 'Reward:Risk Ratio',
                'passed': rr_pts > 0,
                'points': rr_pts,
                'details': f"RR={rr_ratio_val}:1" if rr_ratio_val else 'RR not available',
            })

            # Use official score from calculate_score
            final_score = score_result['score']
            raw_score_val = score_result.get('raw_score', 0)
            signal = self.generate_signal(final_score)

            # Also call analyze_ticker for official result consistency
            official = None
            if survival['passed'] and trend_passed:
                official = self.analyze_ticker(ticker, paid_up_capital=paid_up_capital, analysis_date=analysis_date)

            response = {
                'ticker': ticker,
                'status': 'success' if (survival['passed'] and trend_passed) else 'filtered',
                'message': None if (survival['passed'] and trend_passed) else (survival['reason'] if not survival['passed'] else trend_reason),

                'meta': {
                    'analysis_date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row.get('date')),
                    'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    'is_market_open': bool(is_market_open),
                    'is_intraday': bool(is_intraday),
                },

                'inputs': {
                    'paid_up_capital': paid_up_capital,
                },

                'filters': {
                    'survival': survival,
                    'trend': {
                        'passed': trend_passed,
                        'reason': trend_reason,
                        'close': self._safe_float(row.get('close')),
                        'sma_200': self._safe_float(row.get('sma_200')),
                    },
                },

                'indicators': {
                    'close': self._safe_float(row.get('close')),
                    'open': self._safe_float(row.get('open')),
                    'high': self._safe_float(row.get('high')),
                    'low': self._safe_float(row.get('low')),
                    'volume': int(row.get('volume')) if pd.notna(row.get('volume')) else 0,
                    'last_closing_vol': int(last_closing_vol),
                    'current_vol': int(current_vol),
                    'projected_vol': projected_vol,
                    'avg_volume_20': int(row.get('avg_volume_20')) if pd.notna(row.get('avg_volume_20')) else 0,
                    'rvol': round(rvol, 4),
                    'price_change_pct': round(price_change_pct, 4) if price_change_pct is not None else None,
                    'sma_200': round(trend_sma_200, 4) if trend_sma_200 is not None else None,
                    'atr': round(atr, 4) if atr is not None else None,
                    'daily_range_pct': round(self._safe_float(row.get('daily_range')) or 0.0, 4),
                    # v5 indicators
                    'close_position_ratio': round(self._safe_float(row.get('close_position_ratio')) or 0.0, 4),
                    'obv_slope_20': round(self._safe_float(row.get('obv_slope_20')) or 0.0, 2),
                    'price_slope_20': round(self._safe_float(row.get('price_slope_20')) or 0.0, 4),
                    'vol_ma_3': int(self._safe_float(row.get('vol_ma_3')) or 0),
                    'vol_ma_10': int(self._safe_float(row.get('vol_ma_10')) or 0),
                    # v6 indicators
                    'bb_width': round(self._safe_float(row.get('bb_width')) or 0.0, 4),
                    'bb_width_avg': round(self._safe_float(row.get('bb_width_avg')) or 0.0, 4),
                    'consec_green_vol': int(self._safe_float(row.get('consec_green_vol')) or 0),
                    'vwap_5d': round(self._safe_float(row.get('vwap_5d')) or 0.0, 2),
                    'smart_money_score': round(self._safe_float(row.get('smart_money_score')) or 0.0, 4),
                },

                'support_resistance': {
                    'nearest_support': round(nearest_support, 4) if nearest_support is not None else None,
                    'nearest_resistance': round(nearest_resistance, 4) if nearest_resistance is not None else None,
                    'all_support_levels': [round(x, 4) for x in all_support_levels if x is not None],
                    'all_resistance_levels': [round(x, 4) for x in all_resistance_levels if x is not None],
                },

                'risk': {
                    'stop_from_support': round(stop_from_support, 4) if stop_from_support is not None else None,
                    'stop_from_atr': round(stop_from_atr, 4) if stop_from_atr is not None else None,
                    'recommended_stop_loss': round(recommended_stop, 4) if recommended_stop is not None else None,
                    'reward_risk': rr,
                },

                'score': {
                    'final_score': final_score,
                    'raw_score': raw_score_val,
                    'signal': signal,
                    'breakdown': breakdown,
                    'official_reasons': official.get('reasons') if isinstance(official, dict) else None,
                },

                # v7: parallel EarlyScore breakdown
                'early': self._sanitize_for_json(self.calculate_early_score(row, df)),

                # v9: breakout verdict + the exact 5-rule checks (the signal to trade)
                'breakout': self._sanitize_for_json(self.calculate_breakout_signal(row, df)),
                # v10: reversal verdict + the exact 5-rule checks (buy-the-bottom)
                'reversal': self._sanitize_for_json(self.calculate_reversal_signal(row, df)),
            }

            # If official analysis exists, include official computed trading levels for easy comparison
            if isinstance(official, dict) and official.get('status') == 'success':
                response['official'] = {
                    'signal': official.get('signal'),
                    'score': official.get('score'),
                    'reasons': official.get('reasons'),
                    'nearest_support': official.get('nearest_support'),
                    'nearest_resistance': official.get('nearest_resistance'),
                    'recommended_stop_loss': official.get('recommended_stop_loss'),
                    'reward_risk_ratio': official.get('reward_risk_ratio'),
                    'trend_status': official.get('trend_status'),
                }

            return response

        except Exception as e:
            logger.error(f"Error analyzing {ticker} (detailed): {e}")
            return {'ticker': ticker, 'status': 'error', 'message': str(e)}
    
    def analyze_all_tickers(self, paid_up_data: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        Analyze all tickers in database
        
        Args:
            paid_up_data: Dictionary mapping ticker to paid-up capital (in Crores)
            
        Returns:
            DataFrame with analysis results sorted by score
        """
        tickers = self.db.get_all_tickers()
        
        logger.info(f"Analyzing {len(tickers)} tickers...")
        
        results = []
        
        for ticker in tickers:
            paid_up_capital = paid_up_data.get(ticker) if paid_up_data else None
            result = self.analyze_ticker(ticker, paid_up_capital)
            
            if result['status'] == 'success':
                results.append(result)
        
        # Convert to DataFrame
        if results:
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values('score', ascending=False).reset_index(drop=True)
            return df_results
        else:
            return pd.DataFrame()


if __name__ == "__main__":
    # Test the analyzer
    db = DatabaseManager()
    analyzer = StockAnalyzer(db)
    
    # Test with a single ticker (GP)
    result = analyzer.analyze_ticker('GP')
    
    print("\nAnalysis Result for GP:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    db.close()
