"""
Portfolio Manager - The Harvest Module
Manages portfolio and generates sell signals based on:
1. Emergency Brake (-7% stop loss)
2. The Ratchet (-5% trailing stop from highest)
3. The Climax (Volume anomaly detection)
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio and sell signals (The Harvest Module)"""
    
    def __init__(self, db_path: str = "data/dse_history.db"):
        """
        Initialize portfolio manager
        
        Args:
            db_path: Path to database
        """
        self.db_path = db_path
        self.init_portfolio_db()
    
    def get_db_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def init_portfolio_db(self):
        """Initialize portfolio table"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Create portfolio table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                ticker TEXT PRIMARY KEY,
                buy_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                highest_seen REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Portfolio database initialized")
    
    def add_trade(self, ticker: str, buy_price: float, quantity: int, 
                  date: Optional[str] = None, notes: str = "") -> bool:
        """
        Add a new trade to portfolio
        
        Args:
            ticker: Stock ticker
            buy_price: Purchase price
            quantity: Number of shares
            date: Purchase date (default: today)
            notes: Optional notes
            
        Returns:
            True if successful, False otherwise
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Initial highest_seen is the buy_price
            cursor.execute('''
                INSERT INTO portfolio (ticker, buy_price, quantity, highest_seen, purchase_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticker, buy_price, quantity, buy_price, date, notes))
            
            conn.commit()
            logger.info(f"✅ Added {ticker}: {quantity} shares @ {buy_price} BDT on {date}")
            return True
            
        except sqlite3.IntegrityError:
            logger.error(f"❌ Error: You already hold {ticker}. Use update_position() instead.")
            return False
        finally:
            conn.close()
    
    def update_position(self, ticker: str, quantity: int, avg_price: Optional[float] = None):
        """
        Update an existing position (e.g., adding more shares)
        
        Args:
            ticker: Stock ticker
            quantity: New total quantity
            avg_price: New average price (optional)
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            if avg_price:
                cursor.execute('''
                    UPDATE portfolio 
                    SET quantity = ?, buy_price = ?
                    WHERE ticker = ?
                ''', (quantity, avg_price, ticker))
            else:
                cursor.execute('''
                    UPDATE portfolio 
                    SET quantity = ?
                    WHERE ticker = ?
                ''', (quantity, ticker))
            
            conn.commit()
            logger.info(f"Updated {ticker}: {quantity} shares")
            
        finally:
            conn.close()
    
    def remove_position(self, ticker: str):
        """
        Remove a position from portfolio (after selling)
        
        Args:
            ticker: Stock ticker to remove
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker,))
        conn.commit()
        conn.close()
        
        logger.info(f"Removed {ticker} from portfolio")
    
    def get_portfolio(self) -> pd.DataFrame:
        """
        Get current portfolio
        
        Returns:
            DataFrame with portfolio positions
        """
        conn = self.get_db_connection()
        df = pd.read_sql("SELECT * FROM portfolio ORDER BY ticker", conn)
        conn.close()
        return df
    
    def check_sell_signals(self, verbose: bool = True) -> List[Dict]:
        """
        Run daily check for sell signals (The Harvest Module core logic)
        
        Args:
            verbose: Print detailed output
            
        Returns:
            List of dictionaries with sell signals
        """
        conn = self.get_db_connection()
        
        # Load portfolio
        portfolio = pd.read_sql("SELECT * FROM portfolio", conn)
        
        if portfolio.empty:
            if verbose:
                print("\n" + "="*80)
                print("PORTFOLIO GUARDIAN: Portfolio is empty")
                print("="*80)
            return []
        
        if verbose:
            print("\n" + "="*80)
            print("PORTFOLIO GUARDIAN - DAILY SCAN")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
        
        sell_signals = []
        
        for index, position in portfolio.iterrows():
            ticker = position['ticker']
            buy_price = position['buy_price']
            quantity = position['quantity']
            highest_seen = position['highest_seen']
            purchase_date = position['purchase_date']
            
            # Get current market data (last 2 days for RVOL check)
            query = f"""
                SELECT * FROM stock_data 
                WHERE ticker='{ticker}' 
                ORDER BY date DESC 
                LIMIT 20
            """
            market_data = pd.read_sql(query, conn)
            
            if market_data.empty:
                logger.warning(f"⚠️  No market data found for {ticker}")
                continue
            
            # Latest data
            latest = market_data.iloc[0]
            current_price = latest['close']
            current_volume = latest['volume']
            current_open = latest['open']
            
            # Calculate RVOL (last 20 days average)
            if len(market_data) >= 20:
                avg_volume_20 = market_data['volume'].mean()
                rvol = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
            else:
                rvol = 0
            
            # Update highest seen (The Ratchet mechanism)
            new_highest = highest_seen
            if current_price > highest_seen:
                new_highest = current_price
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE portfolio SET highest_seen = ? WHERE ticker = ?",
                    (new_highest, ticker)
                )
                conn.commit()
                if verbose:
                    print(f"\n📈 {ticker}: NEW HIGH! Ratchet moved: {highest_seen:.2f} → {new_highest:.2f}")
            
            # Calculate trigger prices
            stop_loss_price = buy_price * 0.93        # -7% Emergency Brake
            trailing_stop_price = new_highest * 0.95  # -5% from Peak (The Ratchet)
            
            # Calculate profit
            profit_pct = ((current_price - buy_price) / buy_price) * 100
            profit_amount = (current_price - buy_price) * quantity
            
            # Determine candle type
            is_red_candle = current_price < current_open
            is_doji = abs(current_price - current_open) / current_open < 0.01 if current_open > 0 else False
            
            # DECISION MATRIX
            action = "HOLD ✅"
            reason = ""
            signal_type = None
            urgency = "LOW"
            
            # CONDITION A: Emergency Brake (Stop Loss -7%)
            if current_price <= stop_loss_price:
                action = "SELL NOW ❌"
                reason = f"EMERGENCY BRAKE: Hit -7% stop loss limit"
                signal_type = "STOP_LOSS"
                urgency = "CRITICAL"
            
            # CONDITION B: The Ratchet (Trailing Stop -5% from peak)
            elif current_price <= trailing_stop_price:
                action = "SELL NOW 💰"
                reason = f"TRAILING STOP: Dropped 5% from peak of {new_highest:.2f}. Trend broken."
                signal_type = "TAKE_PROFIT"
                urgency = "HIGH"
            
            # CONDITION C: The Climax (Volume anomaly with profit > 20%)
            elif profit_pct > 20 and rvol > 5.0 and (is_red_candle or is_doji):
                action = "SELL HALF ⚠️"
                reason = f"CLIMAX DETECTED: RVOL {rvol:.1f}x with red/doji candle. Possible dump."
                signal_type = "CLIMAX"
                urgency = "HIGH"
            
            # Display status
            if verbose:
                print(f"\n{ticker.ljust(15)} | Status: {action}")
                print(f"  Buy: {buy_price:.2f} | Current: {current_price:.2f} | Highest: {new_highest:.2f}")
                print(f"  Profit: {profit_pct:+.2f}% ({profit_amount:+,.0f} BDT)")
                print(f"  Stop Loss: {stop_loss_price:.2f} | Trail Stop: {trailing_stop_price:.2f}")
                print(f"  RVOL: {rvol:.2f}x | Volume: {current_volume:,}")
                
                if signal_type:
                    print(f"  ⚡ {reason}")
            
            # Record signal
            if signal_type:
                sell_signals.append({
                    'ticker': ticker,
                    'action': action,
                    'signal_type': signal_type,
                    'urgency': urgency,
                    'reason': reason,
                    'buy_price': buy_price,
                    'current_price': current_price,
                    'highest_seen': new_highest,
                    'profit_pct': profit_pct,
                    'profit_amount': profit_amount,
                    'quantity': quantity,
                    'rvol': rvol,
                    'stop_loss_price': stop_loss_price,
                    'trailing_stop_price': trailing_stop_price
                })
        
        conn.close()
        
        if verbose:
            print("\n" + "="*80)
            if sell_signals:
                print(f"🚨 {len(sell_signals)} SELL SIGNAL(S) DETECTED!")
            else:
                print("✅ All positions safe. No sell signals.")
            print("="*80 + "\n")
        
        return sell_signals
    
    def get_portfolio_summary(self) -> Dict:
        """
        Get portfolio summary statistics
        
        Returns:
            Dictionary with portfolio stats
        """
        conn = self.get_db_connection()
        portfolio = pd.read_sql("SELECT * FROM portfolio", conn)
        
        if portfolio.empty:
            return {
                'total_positions': 0,
                'total_invested': 0,
                'current_value': 0,
                'total_profit': 0,
                'profit_pct': 0
            }
        
        total_invested = 0
        current_value = 0
        
        for _, position in portfolio.iterrows():
            ticker = position['ticker']
            buy_price = position['buy_price']
            quantity = position['quantity']
            
            # Get current price
            latest = pd.read_sql(
                f"SELECT close FROM stock_data WHERE ticker='{ticker}' ORDER BY date DESC LIMIT 1",
                conn
            )
            
            if not latest.empty:
                current_price = latest.iloc[0]['close']
                total_invested += buy_price * quantity
                current_value += current_price * quantity
        
        conn.close()
        
        total_profit = current_value - total_invested
        profit_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'total_positions': len(portfolio),
            'total_invested': total_invested,
            'current_value': current_value,
            'total_profit': total_profit,
            'profit_pct': profit_pct
        }


def main():
    """Main function for testing and command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Manager - The Harvest Module')
    parser.add_argument('action', choices=['add', 'check', 'list', 'remove', 'summary'],
                       help='Action to perform')
    parser.add_argument('--ticker', help='Stock ticker')
    parser.add_argument('--price', type=float, help='Buy price')
    parser.add_argument('--quantity', type=int, help='Number of shares')
    parser.add_argument('--date', help='Purchase date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    pm = PortfolioManager()
    
    if args.action == 'add':
        if not all([args.ticker, args.price, args.quantity]):
            print("Error: --ticker, --price, and --quantity required for 'add'")
            return
        pm.add_trade(args.ticker, args.price, args.quantity, args.date)
    
    elif args.action == 'check':
        signals = pm.check_sell_signals(verbose=True)
        if signals:
            print("\n🚨 URGENT ACTIONS REQUIRED:")
            for signal in signals:
                print(f"\n{signal['ticker']}: {signal['action']}")
                print(f"  {signal['reason']}")
    
    elif args.action == 'list':
        portfolio = pm.get_portfolio()
        if portfolio.empty:
            print("Portfolio is empty")
        else:
            print("\nCurrent Portfolio:")
            print(portfolio.to_string(index=False))
    
    elif args.action == 'remove':
        if not args.ticker:
            print("Error: --ticker required for 'remove'")
            return
        pm.remove_position(args.ticker)
    
    elif args.action == 'summary':
        stats = pm.get_portfolio_summary()
        print("\nPortfolio Summary:")
        print(f"  Total Positions: {stats['total_positions']}")
        print(f"  Total Invested: {stats['total_invested']:,.2f} BDT")
        print(f"  Current Value: {stats['current_value']:,.2f} BDT")
        print(f"  Total Profit: {stats['total_profit']:+,.2f} BDT ({stats['profit_pct']:+.2f}%)")


if __name__ == "__main__":
    main()
