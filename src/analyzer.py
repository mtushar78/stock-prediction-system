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
from db_manager import DatabaseManager

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
    
    def calculate_score(self, row: pd.Series, paid_up_capital: Optional[float] = None) -> Dict:
        """
        Calculate trading score based on DSE Sniper algorithm
        
        Scoring System (0-100):
        - RVOL > 2.5: +50 points
        - Price Change < 2% AND RVOL > 2.5: +20 points (Quiet Accumulation)
        - Paid-Up Capital < 50 Cr: +20 points (Low Float Multiplier)
        - Price > 200-Day SMA: +10 points
        - Below 200 SMA: -50 points
        
        Args:
            row: Series with stock data and indicators for a single day
            paid_up_capital: Paid-up capital in Crores (optional)
            
        Returns:
            Dictionary with score and reasoning
        """
        score = 0
        reasons = []
        
        # Check RVOL
        if pd.notna(row['rvol']) and row['rvol'] > self.rvol_threshold:
            score += 50
            reasons.append(f"High RVOL ({row['rvol']:.1f}x)")
            
            # Check for Quiet Accumulation
            if pd.notna(row['price_change']) and abs(row['price_change']) < self.price_change_threshold:
                score += 20
                reasons.append(f"Quiet Accumulation (RVOL {row['rvol']:.1f}x, Price Change {row['price_change_pct']:.2f}%)")
        
        # Check Paid-Up Capital (Low Float Multiplier)
        if paid_up_capital is not None and paid_up_capital < self.low_cap_threshold:
            score += 20
            reasons.append(f"Low Float ({paid_up_capital:.1f} Cr)")
        
        # Check SMA position
        if pd.notna(row['sma_200']):
            if row['close'] > row['sma_200']:
                score += 10
                reasons.append("Above 200 SMA")
            else:
                score -= 50
                reasons.append("Below 200 SMA")
        
        return {
            'score': score,
            'reasons': reasons
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
            
            # Calculate score
            score_result = self.calculate_score(row, paid_up_capital)
            
            # Generate signal
            signal = self.generate_signal(score_result['score'])
            
            # Prepare result
            result = {
                'ticker': ticker,
                'status': 'success',
                'date': row['date'].strftime('%Y-%m-%d'),
                'close': round(row['close'], 2),
                'volume': int(row['volume']),
                'rvol': round(row['rvol'], 2) if pd.notna(row['rvol']) else 0,
                'avg_volume_20': int(row['avg_volume_20']) if pd.notna(row['avg_volume_20']) else 0,
                'price_change_pct': round(row['price_change_pct'], 2) if pd.notna(row['price_change_pct']) else 0,
                'sma_200': round(row['sma_200'], 2) if pd.notna(row['sma_200']) else None,
                'paid_up_capital': paid_up_capital,
                'score': score_result['score'],
                'signal': signal,
                'reasons': score_result['reasons']
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
