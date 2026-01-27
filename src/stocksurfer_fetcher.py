"""
StockSurfer BD Fetcher for DSE Sniper System
Fetches recent historical data using stocksurferbd library
"""

import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging
from db_manager import DatabaseManager
import time
import os

try:
    from stocksurferbd import PriceData
    STOCKSURFER_AVAILABLE = True
except ImportError:
    STOCKSURFER_AVAILABLE = False
    logging.warning("stocksurferbd not available. Install with: pip install stocksurferbd")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StockSurferFetcher:
    """Fetches recent historical data using stocksurferbd library"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize StockSurfer fetcher
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        
        if not STOCKSURFER_AVAILABLE:
            raise ImportError("stocksurferbd library not available. Install with: pip install stocksurferbd")
        
        self.price_data = PriceData()
    
    def fetch_ticker_data(self, ticker: str) -> pd.DataFrame:
        """
        Fetch all available historical data for a ticker using stocksurferbd
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            logger.info(f"Fetching data for {ticker}...")
            
            # Create temp file
            temp_file = f"temp_{ticker}.xlsx"
            
            # Fetch data using stocksurferbd
            self.price_data.save_history_data(ticker, file_name=temp_file, market='DSE')
            
            if not os.path.exists(temp_file):
                logger.warning(f"No file created for {ticker}")
                return pd.DataFrame()
            
            # Read the Excel file
            df = pd.read_excel(temp_file)
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except:
                pass
            
            if df.empty:
                logger.warning(f"No data received for {ticker}")
                return pd.DataFrame()
            
            # Standardize column names to match database schema
            # stocksurferbd columns: DATE, TRADING_CODE, LTP, HIGH, LOW, OPENP, CLOSEP, YCP, TRADE, VALUE_MN, VOLUME
            column_mapping = {
                'DATE': 'Date',
                'OPENP': 'Open',
                'HIGH': 'High', 
                'LOW': 'Low',
                'CLOSEP': 'Close',  # Use CLOSEP (closing price) instead of LTP
                'VOLUME': 'Volume'
            }
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            
            # Ensure required columns exist
            required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_cols:
                if col not in df.columns:
                    logger.error(f"Missing column {col} in data for {ticker}")
                    return pd.DataFrame()
            
            # Convert data types
            df['Date'] = pd.to_datetime(df['Date'])
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).astype(int)
            
            for col in ['Open', 'High', 'Low', 'Close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove rows with NaN prices
            df = df.dropna(subset=['Open', 'High', 'Low', 'Close'], how='all')
            
            # Sort by date (stocksurferbd returns newest first, we want oldest first)
            df = df.sort_values('Date')
            
            logger.info(f"Fetched {len(df)} records for {ticker}")
            if not df.empty:
                logger.info(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
            
            return df[required_cols]
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()
    
    def update_ticker(self, ticker: str, delay: float = 2.0, is_final: bool = True) -> bool:
        """
        Fetch and update data for a single ticker
        
        Args:
            ticker: Stock ticker symbol
            delay: Delay in seconds after request
            is_final: True for EOD closed candle (2:45 PM), False for intraday snapshot
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch data
            df = self.fetch_ticker_data(ticker)
            
            if df.empty:
                logger.warning(f"No data to update for {ticker}")
                return False
            
            # Insert into database with is_final flag
            self.db.insert_stock_data(df, ticker, source="stocksurferbd", is_final=is_final)
            
            logger.info(f"Successfully updated {ticker} with {len(df)} records")
            
            # Add delay to avoid overwhelming the server
            time.sleep(delay)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating {ticker}: {e}")
            return False
    
    def update_all_tickers(self, ticker_list: Optional[List[str]] = None,
                          delay: float = 2.0, is_final: bool = True) -> dict:
        """
        Update data for all tickers or a specified list
        
        Args:
            ticker_list: List of tickers to update (default: all from database)
            delay: Delay in seconds between requests
            is_final: True for EOD closed candle (2:45 PM), False for intraday snapshot
            
        Returns:
            Dictionary with update statistics
        """
        if ticker_list is None:
            ticker_list = self.db.get_all_tickers()
        
        logger.info(f"Updating {len(ticker_list)} tickers using stocksurferbd... [is_final={is_final}]")
        
        success_count = 0
        failed_count = 0
        failed_tickers = []
        
        for i, ticker in enumerate(ticker_list, 1):
            logger.info(f"Processing {i}/{len(ticker_list)}: {ticker}")
            
            if self.update_ticker(ticker, delay, is_final=is_final):
                success_count += 1
            else:
                failed_count += 1
                failed_tickers.append(ticker)
        
        stats = {
            'success': success_count,
            'failed': failed_count,
            'total': len(ticker_list),
            'failed_tickers': failed_tickers
        }
        
        logger.info(f"\nUpdate complete:")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info(f"  Total: {len(ticker_list)}")
        
        if failed_tickers:
            logger.warning(f"  Failed tickers: {', '.join(failed_tickers[:10])}" + 
                          (f" ... and {len(failed_tickers)-10} more" if len(failed_tickers) > 10 else ""))
        
        return stats


def main():
    """Main function for testing stocksurfer fetcher"""
    if not STOCKSURFER_AVAILABLE:
        print("stocksurferbd library not installed. Please install with: pip install stocksurferbd")
        return
    
    # Initialize database
    db = DatabaseManager()
    
    # Create fetcher
    fetcher = StockSurferFetcher(db)
    
    # Test with a single ticker
    print("\nTesting with GP ticker...")
    success = fetcher.update_ticker('GP')
    
    if success:
        print("\nSuccess! Data fetched and stored.")
        
        # Show some stats
        df = db.get_stock_data('GP')
        print(f"\nTotal records in database for GP: {len(df)}")
        if not df.empty:
            print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    else:
        print("\nFailed to fetch data")
    
    db.close()


if __name__ == "__main__":
    main()
