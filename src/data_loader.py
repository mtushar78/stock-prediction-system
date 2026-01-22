"""
Data Loader for DSE Sniper System
Loads historical CSV data into database
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional
import logging
from db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """Loads stock data from CSV files into database"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize data loader
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
    
    def load_csv_file(self, csv_path: Path, ticker: str) -> bool:
        """
        Load a single CSV file into database
        
        Args:
            csv_path: Path to CSV file
            ticker: Stock ticker symbol
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Read CSV file
            df = pd.read_csv(csv_path)
            
            # Validate required columns
            required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                logger.error(f"Missing columns in {csv_path}: {missing_cols}")
                return False
            
            # Convert date to datetime
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            # Drop rows with invalid dates
            df = df.dropna(subset=['Date'])
            
            # Convert numeric columns
            for col in ['Open', 'High', 'Low', 'Close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce').fillna(0).astype(int)
            
            # Drop rows with all NaN values
            df = df.dropna(subset=['Open', 'High', 'Low', 'Close'], how='all')
            
            # Sort by date
            df = df.sort_values('Date')
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['Date'], keep='last')
            
            if len(df) == 0:
                logger.warning(f"No valid data in {csv_path}")
                return False
            
            # Insert into database
            self.db.insert_stock_data(df, ticker, source="adjusted_data")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading {csv_path}: {e}")
            return False
    
    def load_directory(self, data_dir: str = "data/adjusted_data", 
                      ticker_filter: Optional[List[str]] = None) -> dict:
        """
        Load all CSV files from directory into database
        
        Args:
            data_dir: Directory containing CSV files
            ticker_filter: Optional list of specific tickers to load
            
        Returns:
            Dictionary with loading statistics
        """
        data_path = Path(data_dir)
        
        if not data_path.exists():
            logger.error(f"Directory not found: {data_dir}")
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        # Get all CSV files
        csv_files = list(data_path.glob("*.csv"))
        
        logger.info(f"Found {len(csv_files)} CSV files in {data_dir}")
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for csv_file in csv_files:
            # Extract ticker from filename (remove _data.csv)
            ticker = csv_file.stem.replace('_data', '')
            
            # Apply ticker filter if provided
            if ticker_filter and ticker not in ticker_filter:
                skipped_count += 1
                continue
            
            logger.info(f"Loading {ticker}...")
            
            if self.load_csv_file(csv_file, ticker):
                success_count += 1
            else:
                failed_count += 1
        
        stats = {
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'total': len(csv_files)
        }
        
        logger.info(f"Loading complete: {stats}")
        
        return stats
    
    def reload_ticker(self, ticker: str, data_dir: str = "data/adjusted_data") -> bool:
        """
        Reload data for a specific ticker (clears existing data first)
        
        Args:
            ticker: Stock ticker symbol
            data_dir: Directory containing CSV files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear existing data
            self.db.clear_ticker_data(ticker)
            
            # Find CSV file
            data_path = Path(data_dir)
            csv_file = data_path / f"{ticker}_data.csv"
            
            if not csv_file.exists():
                logger.error(f"File not found: {csv_file}")
                return False
            
            # Load data
            return self.load_csv_file(csv_file, ticker)
            
        except Exception as e:
            logger.error(f"Error reloading {ticker}: {e}")
            return False


def main():
    """Main function for testing data loader"""
    # Initialize database
    db = DatabaseManager()
    
    # Create data loader
    loader = DataLoader(db)
    
    # Load all data from adjusted_data directory
    print("Loading historical data...")
    stats = loader.load_directory("data/adjusted_data")
    
    print("\nLoading Statistics:")
    print(f"  Successful: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Total Files: {stats['total']}")
    
    # Show database statistics
    print("\nDatabase Statistics:")
    db_stats = db.get_stats()
    for key, value in db_stats.items():
        print(f"  {key}: {value}")
    
    # Close database
    db.close()


if __name__ == "__main__":
    main()
