"""
DSE Sniper - Main Pipeline
Volume Anomaly Detection System for Dhaka Stock Exchange
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from db_manager import DatabaseManager
from data_loader import DataLoader
from analyzer import StockAnalyzer
from report_generator import ReportGenerator
from stocksurfer_fetcher import StockSurferFetcher
from portfolio_manager import PortfolioManager
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_data_command(args):
    """Load historical data into database"""
    logger.info("Starting data load...")
    
    db = DatabaseManager(args.db_path)
    loader = DataLoader(db)
    
    # Load data
    if args.ticker:
        # Load specific ticker
        logger.info(f"Loading data for {args.ticker}...")
        success = loader.reload_ticker(args.ticker, args.data_dir)
        if success:
            logger.info(f"Successfully loaded {args.ticker}")
        else:
            logger.error(f"Failed to load {args.ticker}")
    else:
        # Load all data
        logger.info(f"Loading all data from {args.data_dir}...")
        stats = loader.load_directory(args.data_dir, args.filter)
        
        logger.info(f"\nLoad Statistics:")
        logger.info(f"  Success: {stats['success']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Skipped: {stats['skipped']}")
        logger.info(f"  Total: {stats['total']}")
    
    # Show database stats
    db_stats = db.get_stats()
    logger.info(f"\nDatabase Statistics:")
    for key, value in db_stats.items():
        logger.info(f"  {key}: {value}")
    
    db.close()


def analyze_command(args):
    """Analyze stocks and generate signals"""
    logger.info("Starting analysis...")
    
    db = DatabaseManager(args.db_path)
    analyzer = StockAnalyzer(db)
    reporter = ReportGenerator(args.output_dir)
    
    # Analyze stocks
    if args.ticker:
        # Analyze single ticker
        logger.info(f"Analyzing {args.ticker}...")
        result = analyzer.analyze_ticker(args.ticker)
        
        if result['status'] == 'success':
            print(f"\n{'-'*80}")
            print(f"Analysis Result for {args.ticker}")
            print(f"{'-'*80}")
            for key, value in result.items():
                if key not in ['status', 'ticker']:
                    print(f"  {key}: {value}")
            print(f"{'-'*80}\n")
        else:
            logger.error(f"Analysis failed: {result.get('message', 'Unknown error')}")
    else:
        # Analyze all tickers
        logger.info("Analyzing all tickers...")
        df_results = analyzer.analyze_all_tickers()
        
        if df_results.empty:
            logger.warning("No stocks passed analysis filters")
        else:
            logger.info(f"Analysis complete: {len(df_results)} stocks analyzed")
            
            # Generate reports
            reports = reporter.generate_all_reports(df_results, print_console=not args.no_console)
            
            if reports:
                logger.info("\nReports generated:")
                for report_type, path in reports.items():
                    logger.info(f"  {report_type.upper()}: {path}")
    
    db.close()


def update_command(args):
    """Update data using stocksurferbd (fetch recent historical data)"""
    logger.info("Starting data update from stocksurferbd...")
    
    db = DatabaseManager(args.db_path)
    
    try:
        fetcher = StockSurferFetcher(db)
    except ImportError:
        logger.error("stocksurferbd library not available. Install with: pip install stocksurferbd")
        db.close()
        return
    
    if args.ticker:
        # Update specific ticker
        logger.info(f"Updating {args.ticker}...")
        success = fetcher.update_ticker(args.ticker, delay=args.delay)
        if success:
            logger.info(f"Successfully updated {args.ticker}")
        else:
            logger.error(f"Failed to update {args.ticker}")
    else:
        # Update all tickers
        ticker_list = args.filter if args.filter else None
        
        if ticker_list:
            logger.info(f"Updating {len(ticker_list)} specified tickers...")
        else:
            logger.info("Updating all tickers in database...")
        
        stats = fetcher.update_all_tickers(
            ticker_list=ticker_list,
            delay=args.delay
        )
        
        logger.info(f"\nUpdate Statistics:")
        logger.info(f"  Success: {stats['success']}")
        logger.info(f"  Failed: {stats['failed']}")
        logger.info(f"  Total: {stats['total']}")
    
    # Show database stats
    db_stats = db.get_stats()
    logger.info(f"\nDatabase Statistics:")
    for key, value in db_stats.items():
        logger.info(f"  {key}: {value}")
    
    db.close()


def stats_command(args):
    """Show database statistics"""
    db = DatabaseManager(args.db_path)
    
    stats = db.get_stats()
    
    print(f"\n{'='*60}")
    print("DATABASE STATISTICS")
    print(f"{'='*60}")
    
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    if args.verbose:
        tickers = db.get_all_tickers()
        print(f"\nTickers in database ({len(tickers)}):")
        for i, ticker in enumerate(tickers[:50], 1):  # Show first 50
            print(f"  {i}. {ticker}")
        
        if len(tickers) > 50:
            print(f"  ... and {len(tickers) - 50} more")
    
    print(f"{'='*60}\n")
    
    db.close()


def portfolio_command(args):
    """Portfolio management (The Harvest Module)"""
    pm = PortfolioManager(args.db_path)
    
    if args.portfolio_action == 'add':
        # Add new position
        if not all([args.ticker, args.price, args.quantity]):
            logger.error("--ticker, --price, and --quantity required for 'add'")
            return
        pm.add_trade(args.ticker, args.price, args.quantity, args.date, args.notes or "")
    
    elif args.portfolio_action == 'list':
        # List all positions
        portfolio = pm.get_portfolio()
        if portfolio.empty:
            print("\nPortfolio is empty")
        else:
            print("\nCurrent Portfolio:")
            print(portfolio.to_string(index=False))
    
    elif args.portfolio_action == 'check':
        # Check for sell signals (The Harvest Module)
        signals = pm.check_sell_signals(verbose=True)
        if signals:
            print("\n" + "="*80)
            print("🚨 URGENT ACTIONS REQUIRED:")
            print("="*80)
            for signal in signals:
                print(f"\n{signal['ticker']}: {signal['action']}")
                print(f"  Urgency: {signal['urgency']}")
                print(f"  Reason: {signal['reason']}")
                print(f"  Current: {signal['current_price']:.2f} | Buy: {signal['buy_price']:.2f}")
                print(f"  Profit: {signal['profit_pct']:+.2f}% ({signal['profit_amount']:+,.0f} BDT)")
    
    elif args.portfolio_action == 'remove':
        # Remove position
        if not args.ticker:
            logger.error("--ticker required for 'remove'")
            return
        pm.remove_position(args.ticker)
    
    elif args.portfolio_action == 'summary':
        # Show portfolio summary
        stats = pm.get_portfolio_summary()
        print("\n" + "="*60)
        print("PORTFOLIO SUMMARY")
        print("="*60)
        print(f"  Total Positions: {stats['total_positions']}")
        print(f"  Total Invested: {stats['total_invested']:,.2f} BDT")
        print(f"  Current Value: {stats['current_value']:,.2f} BDT")
        print(f"  Total Profit: {stats['total_profit']:+,.2f} BDT ({stats['profit_pct']:+.2f}%)")
        print("="*60 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='DSE Sniper - Volume Anomaly Detection System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load all historical data
  python main.py load
  
  # Load specific ticker
  python main.py load --ticker GP
  
  # Analyze all stocks and generate reports
  python main.py analyze
  
  # Analyze specific stock
  python main.py analyze --ticker GP
  
  # Show database statistics
  python main.py stats
        """
    )
    
    parser.add_argument(
        '--db-path',
        default='data/dse_history.db',
        help='Path to SQLite database (default: data/dse_history.db)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Load command
    load_parser = subparsers.add_parser('load', help='Load historical data into database')
    load_parser.add_argument(
        '--data-dir',
        default='data/adjusted_data',
        help='Directory containing CSV files (default: data/adjusted_data)'
    )
    load_parser.add_argument(
        '--ticker',
        help='Load specific ticker only'
    )
    load_parser.add_argument(
        '--filter',
        nargs='+',
        help='Filter by specific tickers'
    )
    load_parser.set_defaults(func=load_data_command)
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze stocks and generate signals')
    analyze_parser.add_argument(
        '--ticker',
        help='Analyze specific ticker only'
    )
    analyze_parser.add_argument(
        '--output-dir',
        default='outputs/signals',
        help='Output directory for reports (default: outputs/signals)'
    )
    analyze_parser.add_argument(
        '--no-console',
        action='store_true',
        help='Skip console output, only generate files'
    )
    analyze_parser.set_defaults(func=analyze_command)
    
    # Update command (bdshare)
    update_parser = subparsers.add_parser('update', help='Update data from bdshare (Nov 14, 2022 onwards)')
    update_parser.add_argument(
        '--ticker',
        help='Update specific ticker only'
    )
    update_parser.add_argument(
        '--start-date',
        default='2022-11-14',
        help='Start date for update (default: 2022-11-14)'
    )
    update_parser.add_argument(
        '--end-date',
        help='End date for update (default: today)'
    )
    update_parser.add_argument(
        '--filter',
        nargs='+',
        help='Filter by specific tickers'
    )
    update_parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Delay in seconds between requests (default: 2.0)'
    )
    update_parser.set_defaults(func=update_command)
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    stats_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed statistics including ticker list'
    )
    stats_parser.set_defaults(func=stats_command)
    
    # Portfolio command (The Harvest Module)
    portfolio_parser = subparsers.add_parser('portfolio', help='Portfolio management (The Harvest Module)')
    portfolio_parser.add_argument(
        'portfolio_action',
        choices=['add', 'list', 'check', 'remove', 'summary'],
        help='Portfolio action to perform'
    )
    portfolio_parser.add_argument(
        '--ticker',
        help='Stock ticker'
    )
    portfolio_parser.add_argument(
        '--price',
        type=float,
        help='Buy price'
    )
    portfolio_parser.add_argument(
        '--quantity',
        type=int,
        help='Number of shares'
    )
    portfolio_parser.add_argument(
        '--date',
        help='Purchase date (YYYY-MM-DD)'
    )
    portfolio_parser.add_argument(
        '--notes',
        help='Optional notes'
    )
    portfolio_parser.set_defaults(func=portfolio_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
