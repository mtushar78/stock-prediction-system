"""
Portfolio Manager - The Harvest Module (Level 2)
Manages portfolio and generates sell signals based on:
1. Emergency Brake (-7% stop loss)
2. The Ratchet (Dynamic 2x ATR trailing stop - adapts to volatility)
3. The Climax (Volume anomaly detection)
4. The Zombie Killer (Time-based exit for dead positions)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

from db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio and sell signals (The Harvest Module)"""

    def __init__(self):
        """Initialize portfolio manager (uses DATABASE_URL from environment)."""
        # Use a single shared DatabaseManager — its engine is pooled, so
        # creating one per request is cheap.
        self._db = DatabaseManager()
        self.init_portfolio_db()

    def get_db_connection(self):
        """Return a fresh pooled raw connection (caller must close it)."""
        return self._db.get_connection()

    def init_portfolio_db(self):
        """Initialize portfolio tables (idempotent — DatabaseManager.init_db
        already creates them, but keep here for safety)."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    buy_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    highest_seen DOUBLE PRECISION NOT NULL,
                    purchase_date TEXT NOT NULL,
                    notes TEXT,
                    total_cost DOUBLE PRECISION DEFAULT 0,
                    commission_paid DOUBLE PRECISION DEFAULT 0,
                    PRIMARY KEY (user_id, ticker)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    buy_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission DOUBLE PRECISION NOT NULL,
                    total_cost DOUBLE PRECISION NOT NULL,
                    purchase_date TEXT NOT NULL,
                    notes TEXT
                )
            """)
            conn.commit()
            logger.info("Portfolio database initialized")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to init portfolio tables: {e}")
            raise
        finally:
            conn.close()
    
    def add_trade(self, user_id: int, ticker: str, buy_price: float, quantity: int,
                  date: Optional[str] = None, notes: str = "", budget: Optional[float] = None) -> Dict:
        """
        Add a new trade to portfolio with commission calculation

        Args:
            user_id: Owner of the position
            ticker: Stock ticker
            buy_price: Purchase price
            quantity: Number of shares
            date: Purchase date (default: today)
            notes: Optional notes
            budget: Optional budget for suggested quantity calculation
            
        Returns:
            Dictionary with trade details including commission
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate commission (0.40% of trade value)
        COMMISSION_RATE = 0.004  # 0.40%
        trade_value = buy_price * quantity
        commission = trade_value * COMMISSION_RATE
        total_cost = trade_value + commission
        
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if position exists
            cursor.execute(
                "SELECT * FROM portfolio WHERE user_id = %s AND ticker = %s",
                (user_id, ticker),
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing position - calculate new average price.
                # Column order matches CREATE TABLE: user_id, ticker, buy_price,
                # quantity, highest_seen, purchase_date, notes, total_cost,
                # commission_paid.
                old_qty = existing[3]
                old_avg_price = existing[2]
                old_total_cost = existing[7] if len(existing) > 7 and existing[7] is not None else (old_qty * old_avg_price)
                old_commission = existing[8] if len(existing) > 8 and existing[8] is not None else 0

                new_qty = old_qty + quantity
                new_total_cost = old_total_cost + total_cost
                new_commission_total = old_commission + commission
                new_avg_price = (old_total_cost + trade_value + commission) / new_qty

                # CRITICAL FIX: Reset purchase_date to today when averaging down
                # This prevents the "Zombie Date Trap" where old purchase dates
                # trigger false zombie warnings after adding more shares
                cursor.execute("""
                    UPDATE portfolio
                    SET quantity = %s, buy_price = %s, total_cost = %s, commission_paid = %s, purchase_date = %s
                    WHERE user_id = %s AND ticker = %s
                """, (new_qty, new_avg_price, new_total_cost, new_commission_total, date, user_id, ticker))

                logger.info(f"✅ Updated {ticker}: Added {quantity} shares @ {buy_price} BDT. New avg: {new_avg_price:.2f}, Total qty: {new_qty}, Purchase date reset to {date}")
            else:
                # Insert new position
                cursor.execute("""
                    INSERT INTO portfolio (user_id, ticker, buy_price, quantity, highest_seen, purchase_date, notes, total_cost, commission_paid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, ticker, buy_price, quantity, buy_price, date, notes, total_cost, commission))

                logger.info(f"✅ Added {ticker}: {quantity} shares @ {buy_price} BDT on {date}")

            # Record in purchase history
            cursor.execute("""
                INSERT INTO purchase_history (user_id, ticker, buy_price, quantity, commission, total_cost, purchase_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, ticker, buy_price, quantity, commission, total_cost, date, notes))

            conn.commit()
            
            return {
                'success': True,
                'ticker': ticker,
                'quantity': quantity,
                'buy_price': buy_price,
                'commission': round(commission, 2),
                'total_cost': round(total_cost, 2),
                'date': date
            }
            
        except Exception as e:
            logger.error(f"❌ Error adding trade: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def calculate_optimal_buy(self, ticker: str, current_price: float, budget: float, 
                             signal_strength: int = 50) -> Dict:
        """
        Calculate optimal number of shares to buy based on budget and signal strength
        
        Args:
            ticker: Stock ticker
            current_price: Current market price
            budget: Available budget
            signal_strength: Signal score (0-100)
            
        Returns:
            Dictionary with buy recommendation
        """
        COMMISSION_RATE = 0.004  # 0.40%
        
        # Adjust budget allocation based on signal strength
        # Strong signals (80+): Use up to 100% of budget
        # Medium signals (45-79): Use up to 70% of budget
        # Weak signals (<45): Use up to 40% of budget
        if signal_strength >= 80:
            budget_allocation = 1.0
        elif signal_strength >= 45:
            budget_allocation = 0.7
        else:
            budget_allocation = 0.4
        
        allocated_budget = budget * budget_allocation
        
        # Calculate max quantity considering commission
        # budget = (price * qty) + (price * qty * commission_rate)
        # budget = price * qty * (1 + commission_rate)
        # qty = budget / (price * (1 + commission_rate))
        max_quantity = int(allocated_budget / (current_price * (1 + COMMISSION_RATE)))
        
        if max_quantity <= 0:
            return {
                'can_buy': False,
                'reason': 'Insufficient budget',
                'min_required': round(current_price * (1 + COMMISSION_RATE), 2)
            }
        
        # Calculate actual costs
        trade_value = current_price * max_quantity
        commission = trade_value * COMMISSION_RATE
        total_cost = trade_value + commission
        avg_price = total_cost / max_quantity
        
        return {
            'can_buy': True,
            'ticker': ticker,
            'suggested_quantity': max_quantity,
            'price_per_share': round(current_price, 2),
            'trade_value': round(trade_value, 2),
            'commission': round(commission, 2),
            'total_cost': round(total_cost, 2),
            'avg_price_per_share': round(avg_price, 2),
            'remaining_budget': round(budget - total_cost, 2),
            'budget_used_pct': round((total_cost / budget) * 100, 2),
            'signal_strength': signal_strength
        }
    
    def get_purchase_history(self, user_id: int, ticker: Optional[str] = None) -> pd.DataFrame:
        """
        Get purchase history for a ticker or all tickers (scoped to a user)

        Args:
            user_id: Owner of the history
            ticker: Optional ticker to filter by

        Returns:
            DataFrame with purchase history
        """
        from sqlalchemy import text
        if ticker:
            df = pd.read_sql_query(
                text("SELECT * FROM purchase_history WHERE user_id = :user_id AND ticker = :ticker ORDER BY purchase_date DESC"),
                self._db.engine,
                params={"user_id": user_id, "ticker": ticker},
            )
        else:
            df = pd.read_sql_query(
                text("SELECT * FROM purchase_history WHERE user_id = :user_id ORDER BY purchase_date DESC"),
                self._db.engine,
                params={"user_id": user_id},
            )
        return df
    
    def update_position(self, user_id: int, ticker: str, quantity: int, avg_price: Optional[float] = None):
        """
        Update an existing position (e.g., adding more shares)

        Args:
            user_id: Owner of the position
            ticker: Stock ticker
            quantity: New total quantity
            avg_price: New average price (optional)
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            if avg_price:
                cursor.execute("""
                    UPDATE portfolio
                    SET quantity = %s, buy_price = %s
                    WHERE user_id = %s AND ticker = %s
                """, (quantity, avg_price, user_id, ticker))
            else:
                cursor.execute("""
                    UPDATE portfolio
                    SET quantity = %s
                    WHERE user_id = %s AND ticker = %s
                """, (quantity, user_id, ticker))

            conn.commit()
            logger.info(f"Updated {ticker}: {quantity} shares")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def remove_position(self, user_id: int, ticker: str,
                        sell_price: Optional[float] = None,
                        notes: str = "") -> Optional[Dict]:
        """
        Remove a position from portfolio (after selling), journaling the sale
        into sale_history with realized P&L so the track record survives.

        Args:
            user_id: Owner of the position
            ticker: Stock ticker to remove
            sell_price: Actual sell price. Falls back to the latest close.
            notes: Optional sell note (e.g. exit reason)

        Returns:
            Dict with realized P&L details, or None if no position existed.
        """
        COMMISSION_RATE = 0.004  # 0.40%, same as the buy side
        conn = self.get_db_connection()
        cursor = conn.cursor()
        result = None
        try:
            cursor.execute(
                "SELECT buy_price, quantity, total_cost, commission_paid, purchase_date "
                "FROM portfolio WHERE user_id = %s AND ticker = %s",
                (user_id, ticker),
            )
            row = cursor.fetchone()
            if row:
                buy_price, quantity = float(row[0]), int(row[1])
                total_cost = float(row[2]) if row[2] else buy_price * quantity * (1 + COMMISSION_RATE)
                purchase_date = row[4]
                if sell_price is None:
                    cursor.execute(
                        "SELECT close FROM stock_data WHERE ticker = %s AND close > 0 "
                        "AND is_final = 1 ORDER BY date DESC LIMIT 1",
                        (ticker,),
                    )
                    px = cursor.fetchone()
                    sell_price = float(px[0]) if px else buy_price
                gross = float(sell_price) * quantity
                commission = gross * COMMISSION_RATE
                proceeds = gross - commission
                realized = proceeds - total_cost
                sale_date = datetime.now().strftime('%Y-%m-%d')
                cursor.execute("""
                    INSERT INTO sale_history (user_id, ticker, sell_price, quantity, commission,
                        proceeds, cost_basis, realized_pnl, buy_price, purchase_date, sale_date, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, ticker, float(sell_price), quantity, round(commission, 2),
                      round(proceeds, 2), round(total_cost, 2), round(realized, 2),
                      buy_price, purchase_date, sale_date, notes))
                result = {
                    'ticker': ticker, 'sell_price': float(sell_price), 'quantity': quantity,
                    'proceeds': round(proceeds, 2), 'cost_basis': round(total_cost, 2),
                    'realized_pnl': round(realized, 2),
                    'realized_pct': round(realized / total_cost * 100, 2) if total_cost else None,
                    'sale_date': sale_date,
                }
            cursor.execute(
                "DELETE FROM portfolio WHERE user_id = %s AND ticker = %s",
                (user_id, ticker),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        logger.info(f"Removed {ticker} from portfolio"
                    + (f" — realized {result['realized_pnl']:+.2f} tk" if result else ""))
        return result
    
    def get_portfolio(self, user_id: int) -> pd.DataFrame:
        """
        Get current portfolio for a user

        Returns:
            DataFrame with portfolio positions
        """
        from sqlalchemy import text
        return pd.read_sql_query(
            text("SELECT * FROM portfolio WHERE user_id = :user_id ORDER BY ticker"),
            self._db.engine,
            params={"user_id": user_id},
        )
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range (ATR) for a stock
        
        ATR measures the stock's volatility to set dynamic stop losses.
        A volatile stock gets a wider stop, a stable stock gets a tighter stop.
        
        Args:
            df: DataFrame with OHLCV data (must have 'high', 'low', 'close')
            period: Lookback period (default: 14 days)
            
        Returns:
            Current ATR value (float)
        """
        if len(df) < 2:
            return 0.0
        
        df = df.copy().sort_values('date')
        
        # Calculate the 3 components of True Range
        high_low = df['high'] - df['low']
        high_prev_close = np.abs(df['high'] - df['close'].shift(1))
        low_prev_close = np.abs(df['low'] - df['close'].shift(1))
        
        # True Range is the maximum of these three
        true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
        
        # Calculate ATR using Exponential Weighted Moving Average
        atr = true_range.ewm(alpha=1/period, adjust=False).mean()
        
        # Return the latest ATR value
        return atr.iloc[-1] if not atr.empty else 0.0
    
    def calculate_days_held(self, purchase_date: str) -> int:
        """
        Calculate number of days a position has been held
        
        Args:
            purchase_date: Purchase date string (YYYY-MM-DD)
            
        Returns:
            Number of days held
        """
        purchase_dt = datetime.strptime(purchase_date, '%Y-%m-%d')
        current_dt = datetime.now()
        days_held = (current_dt - purchase_dt).days
        return days_held
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        v3 UPGRADE: Calculate Relative Strength Index (RSI)
        
        RSI measures momentum (0-100):
        - RSI > 70: Overbought (tighten trailing stop)
        - RSI > 80: Extremely overbought (very tight stop)
        - RSI < 30: Oversold
        
        Args:
            df: DataFrame with 'close' column
            period: Lookback period (default: 14 days)
            
        Returns:
            Latest RSI value (float)
        """
        if len(df) < period + 1:
            return 50.0  # Neutral default if insufficient data
        
        # Calculate price changes
        delta = df['close'].diff()
        
        # Separate gains and losses
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        # Return latest RSI value
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
    
    def check_sell_signals(self, user_id: int, verbose: bool = True) -> List[Dict]:
        """
        Run daily check for sell signals (The Harvest Module core logic)

        Args:
            user_id: Owner whose positions to scan
            verbose: Print detailed output

        Returns:
            List of dictionaries with sell signals
        """
        from sqlalchemy import text
        conn = self.get_db_connection()

        # Load portfolio (scoped to the user)
        portfolio = pd.read_sql_query(
            text("SELECT * FROM portfolio WHERE user_id = :user_id"),
            self._db.engine,
            params={"user_id": user_id},
        )

        if portfolio.empty:
            conn.close()
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
            
            # Get current market data (need more data for ATR calculation)
            market_data = pd.read_sql_query(
                text("""
                    SELECT * FROM stock_data
                    WHERE ticker = :ticker
                    ORDER BY date DESC
                    LIMIT 30
                """),
                self._db.engine,
                params={"ticker": ticker},
            )
            
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
            
            # Calculate ATR (Level 2: Dynamic Volatility Measure)
            current_atr = self.calculate_atr(market_data, period=14)
            
            # v3 UPGRADE: Calculate RSI (Momentum Measure)
            current_rsi = self.calculate_rsi(market_data, period=14)
            
            # Calculate Days Held (Level 2: Zombie Killer)
            days_held = self.calculate_days_held(purchase_date)
            
            # Update highest seen (The Ratchet mechanism)
            new_highest = highest_seen
            if current_price > highest_seen:
                new_highest = current_price
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "UPDATE portfolio SET highest_seen = %s WHERE user_id = %s AND ticker = %s",
                        (new_highest, user_id, ticker)
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                if verbose:
                    print(f"\n📈 {ticker}: NEW HIGH! Ratchet moved: {highest_seen:.2f} → {new_highest:.2f}")
            
            # Calculate trigger prices
            stop_loss_price = buy_price * 0.93  # -7% Emergency Brake
            
            # v3 UPGRADE: RSI-Based Dynamic ATR Multiplier
            # Default: Loose leash (let winners run)
            atr_multiplier = 2.0
            stop_desc = "Standard"
            
            # If RSI > 70 (Overbought): Tighten leash
            if current_rsi > 70:
                atr_multiplier = 1.5
                stop_desc = "Tight (RSI > 70)"
            
            # If RSI > 80 (Extreme Overbought): Very tight leash
            if current_rsi > 80:
                atr_multiplier = 1.0
                stop_desc = "Aggressive (RSI > 80)"
            
            # Calculate ATR-based trailing stop with dynamic multiplier
            if current_atr > 0:
                atr_stop_distance = atr_multiplier * current_atr
                trailing_stop_price = new_highest - atr_stop_distance
                stop_type = f"ATR x{atr_multiplier} ({stop_desc})"
            else:
                # Fallback to fixed 5% if ATR unavailable
                trailing_stop_price = new_highest * 0.95
                stop_type = "Fixed 5%"
            
            # Calculate profit
            profit_pct = ((current_price - buy_price) / buy_price) * 100
            profit_amount = (current_price - buy_price) * quantity
            
            # Determine candle type
            is_red_candle = current_price < current_open
            is_doji = abs(current_price - current_open) / current_open < 0.01 if current_open > 0 else False
            
            # DECISION MATRIX (LEVEL 2)
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
            
            # CONDITION B: The Ratchet (Dynamic ATR-based Trailing Stop)
            elif current_price <= trailing_stop_price:
                # Only a "take profit" if the exit is above entry. If the
                # trailing stop fires while we are below the buy price, this is
                # a trend exit at a LOSS, not profit-taking.
                in_profit = current_price > buy_price
                action = "SELL NOW 💰" if in_profit else "SELL NOW 📉"
                reason = f"TRAILING STOP ({stop_type}): Dropped below {trailing_stop_price:.2f} from peak of {new_highest:.2f}. Trend broken."
                signal_type = "TAKE_PROFIT" if in_profit else "TREND_EXIT"
                urgency = "HIGH"
            
            # CONDITION C: The Climax (Volume anomaly with profit > 20%)
            elif profit_pct > 20 and rvol > 5.0 and (is_red_candle or is_doji):
                action = "SELL HALF ⚠️"
                reason = f"CLIMAX DETECTED: RVOL {rvol:.1f}x with red/doji candle. Possible dump."
                signal_type = "CLIMAX"
                urgency = "HIGH"
            
            # CONDITION D: The Zombie Killer (LEVEL 2 NEW)
            # If held >10 days AND profit <2%, free up capital
            elif days_held > 10 and profit_pct < 2:
                action = "SELL NOW 🧟"
                reason = f"ZOMBIE KILLER: Held {days_held} days with only {profit_pct:.2f}% profit. Free up capital for better opportunities."
                signal_type = "ZOMBIE_EXIT"
                urgency = "MEDIUM"
            
            # Display status
            if verbose:
                zombie_warning = " ⚠️ ZOMBIE" if days_held > 10 and profit_pct < 2 and signal_type != "ZOMBIE_EXIT" else ""
                print(f"\n{ticker.ljust(15)} | Status: {action}{zombie_warning}")
                print(f"  Buy: {buy_price:.2f} | Current: {current_price:.2f} | Highest: {new_highest:.2f}")
                print(f"  Profit: {profit_pct:+.2f}% ({profit_amount:+,.0f} BDT) | Days Held: {days_held}")
                print(f"  Stop Loss: {stop_loss_price:.2f} | Trail Stop: {trailing_stop_price:.2f} ({stop_type})")
                print(f"  ATR: {current_atr:.2f} | RSI: {current_rsi:.1f} | RVOL: {rvol:.2f}x | Volume: {current_volume:,}")
                
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
                    'trailing_stop_price': trailing_stop_price,
                    'atr': current_atr,
                    'days_held': days_held
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
    
    def get_portfolio_summary(self, user_id: int) -> Dict:
        """
        Get portfolio summary statistics for a user

        Returns:
            Dictionary with portfolio stats
        """
        from sqlalchemy import text
        portfolio = pd.read_sql_query(
            text("SELECT * FROM portfolio WHERE user_id = :user_id"),
            self._db.engine,
            params={"user_id": user_id},
        )

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

            # Get current price (parameterized — never f-string into SQL)
            latest = pd.read_sql_query(
                text("SELECT close FROM stock_data WHERE ticker = :ticker ORDER BY date DESC LIMIT 1"),
                self._db.engine,
                params={"ticker": ticker},
            )

            if not latest.empty:
                current_price = latest.iloc[0]['close']
                total_invested += buy_price * quantity
                current_value += current_price * quantity
        
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
    parser.add_argument('--user-id', type=int, default=1, help='Owner user id (default: 1)')

    args = parser.parse_args()

    pm = PortfolioManager()

    if args.action == 'add':
        if not all([args.ticker, args.price, args.quantity]):
            print("Error: --ticker, --price, and --quantity required for 'add'")
            return
        pm.add_trade(args.user_id, args.ticker, args.price, args.quantity, args.date)

    elif args.action == 'check':
        signals = pm.check_sell_signals(args.user_id, verbose=True)
        if signals:
            print("\n🚨 URGENT ACTIONS REQUIRED:")
            for signal in signals:
                print(f"\n{signal['ticker']}: {signal['action']}")
                print(f"  {signal['reason']}")
    
    elif args.action == 'list':
        portfolio = pm.get_portfolio(args.user_id)
        if portfolio.empty:
            print("Portfolio is empty")
        else:
            print("\nCurrent Portfolio:")
            print(portfolio.to_string(index=False))
    
    elif args.action == 'remove':
        if not args.ticker:
            print("Error: --ticker required for 'remove'")
            return
        pm.remove_position(args.user_id, args.ticker)

    elif args.action == 'summary':
        stats = pm.get_portfolio_summary(args.user_id)
        print("\nPortfolio Summary:")
        print(f"  Total Positions: {stats['total_positions']}")
        print(f"  Total Invested: {stats['total_invested']:,.2f} BDT")
        print(f"  Current Value: {stats['current_value']:,.2f} BDT")
        print(f"  Total Profit: {stats['total_profit']:+,.2f} BDT ({stats['profit_pct']:+.2f}%)")


if __name__ == "__main__":
    main()
