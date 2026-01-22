"""
Database Manager for DSE Sniper System
Handles SQLite database operations for stock data storage
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for stock data"""
    
    def __init__(self, db_path: str = "data/dse_history.db"):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize database and create tables if they don't exist"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # Create main stock_data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_data (
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    PRIMARY KEY (date, ticker)
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ticker_date 
                ON stock_data(ticker, date)
            ''')
            
            # Create metadata table for tracking data sources
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    ticker TEXT PRIMARY KEY,
                    last_updated TEXT,
                    data_source TEXT,
                    record_count INTEGER
                )
            ''')
            
            self.conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def insert_stock_data(self, df: pd.DataFrame, ticker: str, source: str = "adjusted_data"):
        """
        Insert stock data into database
        
        Args:
            df: DataFrame with columns: Date, Open, High, Low, Close, Volume
            ticker: Stock ticker symbol
            source: Data source identifier
        """
        try:
            # Prepare data
            df = df.copy()
            df['ticker'] = ticker
            df.columns = [col.lower() for col in df.columns]
            
            # Ensure date is in proper format
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # Select required columns
            columns = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
            df = df[columns]
            
            # Insert data using INSERT OR REPLACE to handle duplicates
            cursor = self.conn.cursor()
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_data (date, ticker, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', tuple(row))
            
            # Update metadata
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO metadata (ticker, last_updated, data_source, record_count)
                VALUES (?, datetime('now'), ?, ?)
            ''', (ticker, source, len(df)))
            
            self.conn.commit()
            logger.info(f"Inserted {len(df)} records for {ticker}")
            
        except Exception as e:
            logger.error(f"Error inserting data for {ticker}: {e}")
            self.conn.rollback()
            raise
    
    def get_stock_data(self, ticker: str, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve stock data from database
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with stock data
        """
        try:
            query = f"SELECT * FROM stock_data WHERE ticker = ?"
            params = [ticker]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date ASC"
            
            df = pd.read_sql_query(query, self.conn, params=params)
            df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error retrieving data for {ticker}: {e}")
            return pd.DataFrame()
    
    def get_all_tickers(self) -> List[str]:
        """
        Get list of all tickers in database
        
        Returns:
            List of ticker symbols
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM stock_data ORDER BY ticker")
            tickers = [row[0] for row in cursor.fetchall()]
            return tickers
            
        except Exception as e:
            logger.error(f"Error getting tickers: {e}")
            return []
    
    def get_latest_date(self, ticker: str) -> Optional[str]:
        """
        Get the latest date for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Latest date as string (YYYY-MM-DD) or None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT MAX(date) FROM stock_data WHERE ticker = ?",
                (ticker,)
            )
            result = cursor.fetchone()
            return result[0] if result[0] else None
            
        except Exception as e:
            logger.error(f"Error getting latest date for {ticker}: {e}")
            return None
    
    def clear_ticker_data(self, ticker: str):
        """
        Clear all data for a specific ticker
        
        Args:
            ticker: Stock ticker symbol
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM stock_data WHERE ticker = ?", (ticker,))
            cursor.execute("DELETE FROM metadata WHERE ticker = ?", (ticker,))
            self.conn.commit()
            logger.info(f"Cleared data for {ticker}")
            
        except Exception as e:
            logger.error(f"Error clearing data for {ticker}: {e}")
            self.conn.rollback()
    
    def get_stats(self) -> dict:
        """
        Get database statistics
        
        Returns:
            Dictionary with stats
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM stock_data")
            ticker_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM stock_data")
            record_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(date), MAX(date) FROM stock_data")
            date_range = cursor.fetchone()
            
            return {
                'total_tickers': ticker_count,
                'total_records': record_count,
                'date_range': f"{date_range[0]} to {date_range[1]}" if date_range[0] else "No data"
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


if __name__ == "__main__":
    # Test the database manager
    db = DatabaseManager()
    print("Database Stats:", db.get_stats())
    db.close()
