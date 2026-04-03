"""
Analyzer Module for DSE Sniper System
Implements RVOL calculation, scoring, and signal generation
v3: Projected RVOL for intraday accuracy
v5: Graduated scoring, multi-day accumulation, OBV divergence,
    volume acceleration, close position ratio, institutional flow
v6: Enhanced syndicate detection — price tightening, consecutive green
    buying, smart money divergence, VWAP proximity, improved volume
    projection (U-shaped model), extended accumulation window
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

        # v5: Graduated RVOL thresholds (replaces hard 2.5x cliff)
        self.rvol_tiers = [
            (4.0, 60),   # Extreme volume
            (2.5, 50),   # Strong accumulation
            (2.0, 30),   # Significant interest
            (1.5, 15),   # Elevated interest
        ]
        # Legacy threshold kept for compatibility
        self.rvol_threshold = 1.5  # v5: lowered from 2.5 (graduated scoring handles tiers)
        self.price_change_threshold = 0.02  # 2% price change for quiet accumulation
        
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
        if price_range_pct < 5.0 and cum_rvol > 10.0:
            pts = 20   # Very quiet + very high volume — textbook accumulation
        elif price_range_pct < 8.0 and cum_rvol > 12.0:
            pts = 15   # Moderate range but extremely high volume — likely accumulation
        elif price_range_pct < 5.0 and cum_rvol > 7.0:
            pts = 10   # Quiet with moderate volume
        elif price_range_pct < 10.0 and cum_rvol > 10.0:
            pts = 5    # Somewhat contained range with strong volume

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
        """v5: Bullish OBV divergence — OBV rising while price flat/falling."""
        obv_slope = row.get('obv_slope_20', 0)
        price_slope = row.get('price_slope_20', 0)
        if pd.isna(obv_slope) or pd.isna(price_slope):
            return {'score': 0, 'divergence': False, 'obv_slope': 0, 'price_slope': 0}
        divergence = obv_slope > 0 and price_slope <= 0
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
        squeeze = ratio < 0.6
        tight = ratio < 0.8

        pts = 0
        if squeeze:
            pts = 15  # Strong squeeze — breakout imminent
        elif tight:
            pts = 5   # Moderate tightening

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
        if consec >= 5:
            pts = 20  # Very strong sustained buying
        elif consec >= 3:
            pts = 10  # Confirmed buying pattern

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

        pts = 0
        if sm_score > 0.05:
            pts = 15  # Clear smart money accumulation
        elif sm_score > 0.02:
            pts = 8   # Moderate signal

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

        pts = 0
        if distance_pct > 0:       # Above SMA
            pts = 10
        elif distance_pct >= -3:    # 0-3% below — near crossover
            pts = -5
        elif distance_pct >= -10:   # 3-10% below
            pts = -25
        else:                       # >10% below
            pts = -50

        if crossover:
            pts += 15  # Fresh trend reversal bonus

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

    def calculate_score(self, row: pd.Series, df: pd.DataFrame,
                       paid_up_capital: Optional[float] = None) -> Dict:
        """
        v6 SCORING ENGINE — Enhanced multi-factor syndicate detection.

        Components (max raw = 275, normalized to 0-100%):
        - Graduated RVOL:           0-60 pts
        - Quiet Accumulation (5D):  0-20 pts
        - Multi-Day Accumulation:   0-45 pts  (extended 10-day window)
        - Volume Acceleration:      0-10 pts
        - SMA Position (graduated): -50 to +25 pts
        - OBV Divergence:           0-15 pts
        - Close Position Ratio:     0-10 pts
        - Low Float:                0-20 pts
        - RR Ratio (softened):      -10 to +10 pts
        - Price Tightening (BB):    0-15 pts
        - Consecutive Green+Vol:    0-20 pts
        - Smart Money Divergence:   0-15 pts
        - VWAP Proximity:           0-10 pts
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

        # Dynamic denominator: reduce max when data-unavailable components can't fire
        # v6 base max = 60+20+45+10+25+15+10+20+10 + 15+20+15+10 = 275
        # (Institutional Flow removed — no data source on DSE)
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
    
    def generate_signal(self, score: int) -> str:
        """
        Generate trading signal based on score

        v6 thresholds (score is 0-100, percentage of max 290 raw):
          >= 55: BUY  (multi-factor confirmation with v6 syndicate signals)
          >= 30: WAIT (developing pattern worth watching)
          <  30: IGNORE
        """
        if score >= 55:
            return 'BUY'
        elif score >= 30:
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
            df = self.db.get_stock_data(ticker)
            
            if df.empty:
                return {
                    'ticker': ticker,
                    'status': 'error',
                    'message': 'No data available'
                }
            
            # Calculate indicators
            df = self.calculate_indicators(df)
            
            # Apply survival filters
            filter_result = self.apply_survival_filters(df, ticker)
            
            if not filter_result['passed']:
                return {
                    'ticker': ticker,
                    'status': 'filtered',
                    'message': filter_result['reason']
                }
            
            # Get the row to analyze
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
            
            # *** v5: GRADUATED TREND FILTER ***
            # Only hard-filter stocks >10% below 200 SMA (deep downtrend).
            # Stocks 0-10% below are penalised via graduated scoring but still analysed.
            if pd.notna(row['sma_200']) and row['sma_200'] > 0:
                distance_pct = (row['close'] - row['sma_200']) / row['sma_200'] * 100
                if distance_pct < -10:
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

            # 14. RR Ratio
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
