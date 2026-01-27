"""
DSE Sniper API - FastAPI Backend
Professional full-stack architecture for stock analysis and portfolio management
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
import sys
from pathlib import Path
import pandas as pd
import logging
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.db_manager import DatabaseManager
from src.analyzer import StockAnalyzer
from src.portfolio_manager import PortfolioManager
from src.stocksurfer_fetcher import StockSurferFetcher
# from src.dse_scraper import run_daily_scraper  # COMMENTED OUT - HAS BUGS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = str(Path(__file__).parent.parent / 'data' / 'dse_history.db')
BANGLADESH_TZ = pytz.timezone('Asia/Dhaka')

# Global scheduler
scheduler = AsyncIOScheduler(timezone=BANGLADESH_TZ)

# Pydantic models
class Trade(BaseModel):
    ticker: str
    buy_price: float
    quantity: int
    date: Optional[str] = None
    notes: Optional[str] = ""

class SystemStatus(BaseModel):
    status: str
    market_status: str
    last_update: Optional[str] = None
    next_update: Optional[str] = None

# Background task to update data (RESTORED - Using StockSurfer)
async def scheduled_data_update(is_final_update: bool = False):
    """
    Run data update during market hours (3 times: opening, middle, closing)
    
    Args:
        is_final_update: True ONLY for 2:45 PM run (market closed, final candle)
    """
    try:
        update_type = "FINAL CANDLE" if is_final_update else "INTRADAY SNAPSHOT"
        logger.info(f"⏰ Starting scheduled data update [{update_type}]...")
        
        db = DatabaseManager(DB_PATH)
        
        # Update stock data from stocksurferbd with is_final flag
        try:
            fetcher = StockSurferFetcher(db)
            stats = fetcher.update_all_tickers(delay=2.0, is_final=is_final_update)
            logger.info(f"✅ Data update completed: {stats['success']} success, {stats['failed']} failed")
        except ImportError:
            logger.warning("stocksurferbd not available, skipping data update")
        except Exception as e:
            logger.error(f"Error updating data: {e}")
        
        # Run analysis and save signals to a temporary table
        try:
            analyzer = StockAnalyzer(db)
            df_results = analyzer.analyze_all_tickers()
            
            if not df_results.empty:
                # Save results to signals_today table
                conn = db.get_connection()
                df_results.to_sql('signals_today', conn, if_exists='replace', index=False)
                conn.close()
                logger.info(f"✅ Analysis completed: {len(df_results)} signals generated")
            else:
                logger.info("No signals generated today")
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
        
        db.close()
        logger.info("✅ Scheduled update completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Scheduled update failed: {e}")

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("🚀 DSE Sniper API starting up...")
    logger.info(f"📊 Database: {DB_PATH}")
    
    # Run initial analysis on startup
    logger.info("📊 Running initial analysis...")
    try:
        db = DatabaseManager(DB_PATH)
        analyzer = StockAnalyzer(db)
        df_results = analyzer.analyze_all_tickers()
        
        if not df_results.empty:
            # Save results to signals_today table
            # Convert reasons list to string for SQL storage
            df_results_copy = df_results.copy()
            df_results_copy['reasons'] = df_results_copy['reasons'].apply(lambda x: str(x) if isinstance(x, list) else x)
            df_results_copy.to_sql('signals_today', db.conn, if_exists='replace', index=False)
            db.conn.commit()
            logger.info(f"✅ Initial analysis completed: {len(df_results)} signals generated")
        else:
            logger.warning("⚠️  No signals generated on startup")
        
        db.close()
    except Exception as e:
        logger.error(f"❌ Initial analysis failed: {e}")
    
    # Schedule 3 updates during market hours (10:00 AM - 2:30 PM) - RESTORED
    # 1. Morning update at 11:00 AM - INTRADAY SNAPSHOT
    scheduler.add_job(
        scheduled_data_update,
        CronTrigger(hour=11, minute=0, timezone=BANGLADESH_TZ),
        args=[False],  # is_final = False
        id='morning_update',
        name='Morning Data Update',
        replace_existing=True
    )
    
    # 2. Afternoon update at 1:00 PM - INTRADAY SNAPSHOT
    scheduler.add_job(
        scheduled_data_update,
        CronTrigger(hour=13, minute=0, timezone=BANGLADESH_TZ),
        args=[False],  # is_final = False
        id='afternoon_update',
        name='Afternoon Data Update',
        replace_existing=True
    )
    
    # 3. Closing update at 2:45 PM (after market closes at 2:30 PM) - FINAL CANDLE
    scheduler.add_job(
        scheduled_data_update,
        CronTrigger(hour=14, minute=45, timezone=BANGLADESH_TZ),
        args=[True],  # is_final = True
        id='closing_update',
        name='Closing Data Update (FINAL)',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("⏰ Scheduler started: 3 updates during market hours")
    logger.info("  - Morning: 11:00 AM")
    logger.info("  - Afternoon: 1:00 PM")
    logger.info("  - Closing: 2:45 PM")
    
    # Get next run times
    for job_id in ['morning_update', 'afternoon_update', 'closing_update']:
        job = scheduler.get_job(job_id)
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            logger.info(f"⏰ Next {job.name}: {next_run}")
    
    yield
    
    # Shutdown
    logger.info("🛑 DSE Sniper API shutting down...")
    scheduler.shutdown()
    logger.info("✅ Scheduler stopped")

# Create FastAPI app
app = FastAPI(
    title="DSE Sniper API",
    description="Algorithmic Volume Analysis System for Dhaka Stock Exchange",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        "http://localhost:12002",  # Frontend service
        "https://dse-sniper.maksudul.com"  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes

@app.get("/")
def health_check() -> SystemStatus:
    """System health check and status"""
    try:
        # Get last update time from database
        db = DatabaseManager(DB_PATH)
        cursor = db.conn.cursor()
        
        # Try to get last update from stock_data
        cursor.execute("SELECT MAX(date) FROM stock_data")
        result = cursor.fetchone()
        last_update = result[0] if result and result[0] else None
        
        db.close()
        
        # Get next scheduled update from all 3 jobs
        next_update = None
        job_ids = ['morning_update', 'afternoon_update', 'closing_update']
        next_times = []
        
        for job_id in job_ids:
            job = scheduler.get_job(job_id)
            if job and job.next_run_time:
                next_times.append(job.next_run_time)
        
        if next_times:
            # Get the soonest next run time
            next_run = min(next_times)
            next_update = next_run.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Determine market status (DSE trading hours: 10:00 AM - 2:30 PM)
        now = datetime.now(BANGLADESH_TZ)
        hour = now.hour
        minute = now.minute
        
        if 10 <= hour < 14 or (hour == 14 and minute <= 30):
            market_status = "OPEN"
        else:
            market_status = "CLOSED"
        
        return SystemStatus(
            status="ONLINE",
            market_status=market_status,
            last_update=last_update,
            next_update=next_update
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return SystemStatus(
            status="ONLINE",
            market_status="UNKNOWN",
            last_update=None,
            next_update=None
        )

@app.get("/api/sniper-signals")
def get_sniper_signals():
    """Get BUY signals from analysis engine"""
    try:
        db = DatabaseManager(DB_PATH)
        
        # Try to fetch pre-calculated signals
        try:
            df = pd.read_sql(
                "SELECT * FROM signals_today WHERE signal IN ('BUY', 'WAIT') ORDER BY score DESC",
                db.conn
            )
            db.close()
            
            if not df.empty:
                # Rename columns for frontend
                df = df.rename(columns={
                    'ticker': 'Ticker',
                    'close': 'Price',
                    'rvol': 'RVOL',
                    'score': 'Score',
                    'signal': 'Signal',
                    'reasons': 'Reason',
                    'volume': 'Volume',
                    'avg_volume_20': 'AvgVolume20',
                    'price_change_pct': 'PriceChange',
                    'sma_200': 'SMA200'
                })
                
                # Format Reason (convert list to string)
                if 'Reason' in df.columns:
                    df['Reason'] = df['Reason'].apply(lambda x: ', '.join(eval(x)) if isinstance(x, str) and x.startswith('[') else x)
                
                return df.to_dict(orient="records")
        except Exception as e:
            logger.warning(f"No pre-calculated signals found, running fresh analysis: {e}")
            
            # Run fresh analysis
            analyzer = StockAnalyzer(db)
            df_results = analyzer.analyze_all_tickers()
            
            conn.close()
            db.close()
            
            if not df_results.empty:
                # Filter for BUY and WAIT signals
                df_filtered = df_results[df_results['signal'].isin(['BUY', 'WAIT'])].copy()
                
                # Rename columns
                df_filtered = df_filtered.rename(columns={
                    'ticker': 'Ticker',
                    'close': 'Price',
                    'rvol': 'RVOL',
                    'score': 'Score',
                    'signal': 'Signal',
                    'reasons': 'Reason'
                })
                
                # Format Reason
                if 'Reason' in df_filtered.columns:
                    df_filtered['Reason'] = df_filtered['Reason'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
                
                return df_filtered.to_dict(orient="records")
            
            return []
    
    except Exception as e:
        logger.error(f"Error getting sniper signals: {e}")
        return []

@app.get("/api/portfolio")
def get_portfolio():
    """Get current portfolio holdings with live P/L and Level 2 sell logic details"""
    try:
        pm = PortfolioManager(DB_PATH)
        portfolio_df = pm.get_portfolio()
        
        if portfolio_df.empty:
            return []
        
        # Get current prices and calculate P/L with Level 2 details
        db = DatabaseManager(DB_PATH)
        
        results = []
        for _, position in portfolio_df.iterrows():
            ticker = position['ticker']
            
            # Get market data for ATR calculation
            cursor = db.conn.cursor()
            cursor.execute(
                "SELECT date, close, high, low, open, volume FROM stock_data WHERE ticker=? ORDER BY date DESC LIMIT 30",
                (ticker,)
            )
            market_data = cursor.fetchall()
            
            if not market_data:
                continue
            
            # Create DataFrame for ATR calculation
            df_market = pd.DataFrame(market_data, columns=['date', 'close', 'high', 'low', 'open', 'volume'])
            
            current_price = df_market.iloc[0]['close']
            current_open = df_market.iloc[0]['open']
            current_volume = df_market.iloc[0]['volume']
            
            # Calculate profit
            profit_pct = ((current_price - position['buy_price']) / position['buy_price']) * 100
            profit_amount = (current_price - position['buy_price']) * position['quantity']
            
            # Calculate ATR (Level 2)
            atr = pm.calculate_atr(df_market, period=14)
            
            # Calculate days held (Level 2)
            days_held = pm.calculate_days_held(position['purchase_date'])
            
            # Calculate RVOL
            if len(df_market) >= 20:
                avg_volume_20 = df_market['volume'].mean()
                rvol = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
            else:
                rvol = 0
            
            # Calculate stop prices
            stop_loss_price = position['buy_price'] * 0.93  # -7% Emergency Brake
            
            # Dynamic ATR-based trailing stop
            if atr > 0:
                atr_stop_distance = 2 * atr
                trailing_stop_price = position['highest_seen'] - atr_stop_distance
                stop_type = f"ATR"
            else:
                trailing_stop_price = position['highest_seen'] * 0.95
                stop_type = "Fixed 5%"
            
            # Determine status and check for zombie
            status = 'HOLD'
            is_zombie = days_held > 10 and profit_pct < 2
            
            # Check sell conditions
            if current_price <= stop_loss_price:
                status = 'STOP_LOSS'
            elif current_price <= trailing_stop_price:
                status = 'TAKE_PROFIT'
            elif is_zombie:
                status = 'ZOMBIE_WARNING'
            
            results.append({
                'ticker': ticker,
                'buy_price': position['buy_price'],
                'quantity': position['quantity'],
                'highest_seen': position['highest_seen'],
                'purchase_date': position['purchase_date'],
                'current_price': round(current_price, 2),
                'profit_pct': round(profit_pct, 2),
                'profit_amount': round(profit_amount, 2),
                'status': status,
                # Level 2 details
                'atr': round(atr, 2),
                'days_held': days_held,
                'rvol': round(rvol, 2),
                'stop_loss_price': round(stop_loss_price, 2),
                'trailing_stop_price': round(trailing_stop_price, 2),
                'stop_type': stop_type,
                'atr_distance': round(2 * atr, 2) if atr > 0 else 0,
                'is_zombie': is_zombie,
                'volume': int(current_volume)
            })
        
        db.close()
        
        return results
    
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return []

@app.post("/api/trade")
def add_trade(trade: Trade):
    """Add a new trade to portfolio"""
    try:
        pm = PortfolioManager(DB_PATH)
        
        success = pm.add_trade(
            ticker=trade.ticker.upper(),
            buy_price=trade.buy_price,
            quantity=trade.quantity,
            date=trade.date,
            notes=trade.notes or ""
        )
        
        if success:
            return {
                "success": True,
                "message": f"Added {trade.ticker.upper()} to portfolio"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"{trade.ticker.upper()} already exists in portfolio"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/trade/{ticker}")
def remove_trade(ticker: str):
    """Remove a position from portfolio"""
    try:
        pm = PortfolioManager(DB_PATH)
        pm.remove_position(ticker.upper())
        
        return {
            "success": True,
            "message": f"Removed {ticker.upper()} from portfolio"
        }
    
    except Exception as e:
        logger.error(f"Error removing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
def get_alerts():
    """Get SELL signals (Stop Loss / Take Profit / Climax)"""
    try:
        pm = PortfolioManager(DB_PATH)
        signals = pm.check_sell_signals(verbose=False)
        
        # Format for frontend
        alerts = []
        for signal in signals:
            alerts.append({
                'ticker': signal['ticker'],
                'type': signal['signal_type'],
                'value': f"{signal['profit_pct']:+.1f}%",
                'action': signal['action'],
                'reason': signal['reason'],
                'urgency': signal['urgency'],
                'current_price': signal['current_price'],
                'buy_price': signal['buy_price'],
                'profit_amount': signal['profit_amount']
            })
        
        return alerts
    
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return []

@app.get("/api/portfolio/summary")
def get_portfolio_summary():
    """Get portfolio summary statistics"""
    try:
        pm = PortfolioManager(DB_PATH)
        stats = pm.get_portfolio_summary()
        return stats
    
    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trigger-update")
async def trigger_manual_update():
    """Manually trigger data update (for testing)"""
    try:
        logger.info("🔄 Manual update triggered...")
        asyncio.create_task(scheduled_data_update())
        
        return {
            "success": True,
            "message": "Update started in background"
        }
    
    except Exception as e:
        logger.error(f"Error triggering update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scheduler/status")
def get_scheduler_status():
    """Get scheduler status and next run time"""
    try:
        job = scheduler.get_job('daily_update')
        
        if job:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z') if job.next_run_time else None
            
            return {
                "scheduler_running": scheduler.running,
                "next_update": next_run,
                "update_time": "14:45 (2:45 PM Bangladesh Time)"
            }
        else:
            return {
                "scheduler_running": scheduler.running,
                "next_update": None,
                "update_time": "14:45 (2:45 PM Bangladesh Time)"
            }
    
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=12001)
