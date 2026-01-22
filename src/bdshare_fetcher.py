"""
BDShare Fetcher for DSE Sniper System
Fetches historical data from bdshare API for dates not in CSV files
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from db_manager import DatabaseManager
import time

try:
    from bdshare import get_hist_data
    BDSHARE_AVAILABLE = True
except ImportError:
    BDSHARE_AVAILABLE = False
    logging.warning("bdshare not available. Install with: pip install bdshare")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BDShareFetcher:
    """Fetches recent historical data using bdshare library"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize BDShare fetcher
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        
        if not BDSHARE_AVAILABLE:
            raise ImportError("bdshare library not available. Install with: pip install bdshare")
    
    def fetch_ticker_data(self, ticker: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch historical data for a ticker using bdshare
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format (default: today)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"Fetching data for {ticker} from {start_date} to {end_date}...")
            
            # Fetch data using bdshare
            df = get_hist_data(
                ticker,
                start_date,
                end_date
            )
            
            if df is None or df.empty:
                logger.warning(f"No data received for {ticker}")
                return pd.DataFrame()
            
            # Standardize column names to match database schema
            df = df.reset_index()
            
            # Map bdshare columns to our schema
            column_mapping = {
                'date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }
            
            # Rename columns if they exist
            df.columns = df.columns.str.lower()
            df = df.rename(columns={k.lower(): v for k, v in column_mapping.items()})
            
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
            
            # Sort by date
            df = df.sort_values('Date')
            
            logger.info(f"Fetched {len(df)} records for {ticker}")
            
            return df[required_cols]
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()
    
    def update_ticker(self, ticker: str, start_date: str = "2022-11-14", 
                     end_date: Optional[str] = None, delay: float = 1.0) -> bool:
        """
        Fetch and update data for a single ticker
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (default: 2022-11-14)
            end_date: End date (default: today)
            delay: Delay in seconds between requests to avoid rate limiting
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch data
            df = self.fetch_ticker_data(ticker, start_date, end_date)
            
            if df.empty:
                logger.warning(f"No data to update for {ticker}")
                return False
            
            # Insert into database
            self.db.insert_stock_data(df, ticker, source="bdshare")
            
            logger.info(f"Successfully updated {ticker} with {len(df)} records")
            
            # Add delay to avoid overwhelming the API
            time.sleep(delay)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating {ticker}: {e}")
            return False
    
    def update_all_tickers(self, start_date: str = "2022-11-14", 
                          end_date: Optional[str] = None,
                          ticker_list: Optional[List[str]] = None,
                          delay: float = 2.0) -> dict:
        """
        Update data for all tickers or a specified list
        
        Args:
            start_date: Start date (default: 2022-11-14)
            end_date: End date (default: today)
            ticker_list: List of tickers to update (default: all from database)
            delay: Delay in seconds between requests
            
        Returns:
            Dictionary with update statistics
        """
        if ticker_list is None:
            ticker_list = self.db.get_all_tickers()
        
        logger.info(f"Updating {len(ticker_list)} tickers from {start_date} to {end_date or 'today'}...")
        
        success_count = 0
        failed_count = 0
        failed_tickers = []
        
        for i, ticker in enumerate(ticker_list, 1):
            logger.info(f"Processing {i}/{len(ticker_list)}: {ticker}")
            
            if self.update_ticker(ticker, start_date, end_date, delay):
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
    
    def update_missing_data(self, ticker: str, start_date: str = "2022-11-14") -> bool:
        """
        Update only missing dates for a ticker (smart update)
        
        Args:
            ticker: Stock ticker symbol  
            start_date: Start date to check from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get latest date in database for this ticker
            latest_date = self.db.get_latest_date(ticker)
            
            if latest_date:
                latest_dt = datetime.strptime(latest_date, '%Y-%m-%d')
                # Start from day after latest date
                fetch_start = (latest_dt + timedelta(days=1)).strftime('%Y-%m-%d')
                
                logger.info(f"{ticker}: Latest DB date is {latest_date}, fetching from {fetch_start}")
            else:
                # No data in database, start from specified start_date
                fetch_start = start_date
                logger.info(f"{ticker}: No existing data, fetching from {fetch_start}")
            
            # Check if we need to fetch anything
            today = datetime.now().strftime('%Y-%m-%d')
            if fetch_start > today:
                logger.info(f"{ticker}: Already up to date")
                return True
            
            # Fetch and update
            return self.update_ticker(ticker, fetch_start, today)
            
        except Exception as e:
            logger.error(f"Error in smart update for {ticker}: {e}")
            return False


def main():
    """Main function for testing bdshare fetcher"""
    if not BDSHARE_AVAILABLE:
        print("bdshare library not installed. Please install with: pip install bdshare")
        return
    
    # Initialize database
    db = DatabaseManager()
    
    # Create fetcher
    fetcher = BDShareFetcher(db)
    
    # Test with a single ticker
    print("\nTesting with GP ticker...")
    success = fetcher.update_ticker('GP', start_date='2022-11-14')
    
    if success:
        print("\nSuccess! Data fetched and stored.")
        
        # Show some stats
        df = db.get_stock_data('GP', start_date='2022-11-14')
        print(f"\nRecords in database for GP from 2022-11-14: {len(df)}")
        if not df.empty:
            print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    else:
        print("\nFailed to fetch data")
    
    db.close()


if __name__ == "__main__":
    main()
