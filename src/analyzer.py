"""
Analyzer Module for DSE Sniper System
Implements RVOL calculation, scoring, and signal generation
v3: Projected RVOL for intraday accuracy
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
        
        # Configuration parameters from README
        self.rvol_threshold = 2.5  # RVOL > 2.5 for buy signal
        self.rvol_period = 20  # 20-day average volume
        self.sma_period = 200  # 200-day simple moving average
        self.low_cap_threshold = 50  # Paid-up capital < 50 Cr
        self.high_cap_threshold = 500  # Paid-up capital > 500 Cr (Penny trap)
        self.price_change_threshold = 0.02  # 2% price change for quiet accumulation
        
    def calculate_projected_volume(self, current_vol: float, current_time: datetime = None) -> float:
        """
        v3 UPGRADE: Extrapolate current volume to EOD
        DSE Market Hours: 10:00 AM - 2:30 PM (4.5 hours = 270 minutes)
        
        This prevents intraday snapshots from polluting moving averages.
        Example: 10:30 AM with 50k volume projects to ~650k by EOD.
        
        Args:
            current_vol: Current volume seen so far today
            current_time: Current time (defaults to now in Bangladesh timezone)
            
        Returns:
            Projected volume for end of day
        """
        if current_time is None:
            current_time = datetime.now(pytz.timezone('Asia/Dhaka'))
        
        # Market start/end times
        market_start = current_time.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # If before market, return 0
        if current_time < market_start:
            return 0
        
        # Calculate minutes elapsed since market open
        delta = current_time - market_start
        minutes_elapsed = delta.total_seconds() / 60
        
        # Cap at 270 minutes (full trading day: 4.5 hours)
        minutes_elapsed = min(max(minutes_elapsed, 1), 270)
        
        # Linear Projection: (current_vol / minutes_so_far) * 270
        # v4 future: Use U-shaped curve weighting for more accuracy
        projected = (current_vol / minutes_elapsed) * 270
        
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
                if abs(level - clusters[-1][-1]) / clusters[-1][-1] < tolerance:
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
    
    def calculate_score(self, row: pd.Series, df: pd.DataFrame, 
                       paid_up_capital: Optional[float] = None) -> Dict:
        """
        Enhanced scoring with support/resistance and RR ratio
        v4 UPGRADE: Includes support/resistance analysis and reward:risk ratio
        
        Scoring System (0-100):
        - RVOL > 2.5: +50 points
        - Price Change < 2% AND RVOL > 2.5: +20 points (Quiet Accumulation)
        - Paid-Up Capital < 50 Cr: +20 points (Low Float Multiplier)
        - Price > 200-Day SMA: +10 points
        - Good RR Ratio (>= 2:1): +10 points
        - Poor RR Ratio (< 2:1): -30 points
        - Below 200 SMA: -50 points (will be filtered before scoring)
        
        Args:
            row: Series with stock data and indicators for a single day
            df: Full DataFrame for support/resistance calculation
            paid_up_capital: Paid-up capital in Crores (optional)
            
        Returns:
            Dictionary with score, reasoning, and trading levels
        """
        score = 0
        reasons = []
        
        current_price = row['close']
        
        # Check RVOL
        if pd.notna(row['rvol']) and row['rvol'] > self.rvol_threshold:
            score += 50
            reasons.append(f"High RVOL ({row['rvol']:.1f}x)")
            
            # Check for Quiet Accumulation
            if pd.notna(row['price_change']) and abs(row['price_change']) < self.price_change_threshold:
                score += 20
                reasons.append(f"Quiet Accumulation")
        
        # Check Paid-Up Capital (Low Float Multiplier)
        if paid_up_capital is not None and paid_up_capital < self.low_cap_threshold:
            score += 20
            reasons.append(f"Low Float ({paid_up_capital:.1f} Cr)")
        
        # NEW: Support/Resistance Analysis
        sr_levels = self.find_support_resistance(df, current_price)
        
        nearest_support = sr_levels['nearest_support']
        nearest_resistance = sr_levels['nearest_resistance']
        
        # NEW: Calculate ATR-based stop loss
        atr = row['ATR'] if pd.notna(row['ATR']) else None
        recommended_stop = None
        rr_ratio = None
        
        if atr and nearest_support and nearest_resistance:
            # Stop loss: Higher of (Support - 2%) or (Price - 1.5*ATR)
            # We use "higher" because we want the tighter stop
            stop_from_support = nearest_support * 0.98
            stop_from_atr = current_price - (1.5 * atr)
            recommended_stop = max(stop_from_support, stop_from_atr)
            
            # Calculate RR ratio
            rr_analysis = self.calculate_reward_risk_ratio(
                current_price,
                recommended_stop,
                nearest_resistance
            )
            
            if rr_analysis['valid']:
                rr_ratio = rr_analysis['ratio']
                
                if rr_analysis['recommended']:
                    score += 10
                    reasons.append(f"Good RR Ratio ({rr_analysis['ratio']}:1)")
                else:
                    score -= 30
                    reasons.append(f"Poor RR Ratio ({rr_analysis['ratio']}:1)")
        
        # Check SMA position (this will be filtered before, but keep for legacy)
        if pd.notna(row['sma_200']):
            if current_price > row['sma_200']:
                score += 10
                reasons.append("Above 200 SMA")
            else:
                score -= 50
                reasons.append("Below 200 SMA")
        
        return {
            'score': score,
            'reasons': reasons,
            'support': nearest_support,
            'resistance': nearest_resistance,
            'stop_loss': recommended_stop,
            'rr_ratio': rr_ratio
        }
    
    def generate_signal(self, score: int) -> str:
        """
        Generate trading signal based on score
        
        Args:
            score: Trading score (0-100)
            
        Returns:
            Signal: 'BUY', 'WAIT', or 'IGNORE'
        """
        if score >= 80:
            return 'BUY'
        elif score >= 45:
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
            
            # *** CRITICAL: MANDATORY TREND FILTER ***
            # v4 UPGRADE: Enforce 200 SMA filter - NO buying below 200 SMA
            # This single filter eliminates 60-70% of losing trades
            if pd.notna(row['sma_200']) and row['close'] < row['sma_200']:
                return {
                    'ticker': ticker,
                    'status': 'filtered',
                    'message': 'Below 200 SMA - Downtrend (Trend Filter)',
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
            
            # Calculate volume fields based on market status
            current_vol = int(row['volume'])
            
            # Last closing volume is the previous day's volume (or today's if final)
            if len(df) >= 2:
                if is_intraday:
                    # If we're looking at intraday data, last closing is previous day
                    last_closing_vol = int(df.iloc[-2]['volume'])
                else:
                    # If we're looking at final data, last closing is today's volume
                    last_closing_vol = current_vol
            else:
                last_closing_vol = current_vol
            
            # Projected volume (only during market hours and if intraday)
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
                'current_vol': current_vol if is_market_open else last_closing_vol,
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
                'trend_status': 'UPTREND'  # If we reach here, it's above 200 SMA
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return {
                'ticker': ticker,
                'status': 'error',
                'message': str(e)
            }
    
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
