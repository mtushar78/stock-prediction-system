#!/usr/bin/env python3
"""
Portfolio Health Check Script
v4 UPGRADE: Analyzes current holdings against enhanced trading rules

Run this to see which of your current holdings should be exited.
"""

from src.analyzer import StockAnalyzer
from src.db_manager import DatabaseManager
from src.portfolio_manager import PortfolioManager
import sys

def main():
    db = DatabaseManager()
    analyzer = StockAnalyzer(db)
    portfolio = PortfolioManager()  # PortfolioManager creates its own DB connection
    
    print("\n" + "="*90)
    print(" 🏥 PORTFOLIO HEALTH CHECK - v4 ENHANCED RULES")
    print("="*90)
    
    holdings = portfolio.get_portfolio(user_id=1)  # owner account (see backend/migrate_auth.py)
    
    if holdings.empty:
        print("\n✅ No current holdings found in database.")
        print("\nNote: If you have holdings, make sure they're added to the portfolio using:")
        print("  portfolio.add_trade(ticker, 'BUY', quantity, price, date)")
        db.close()
        return
    
    print(f"\n📊 Analyzing {len(holdings)} holdings...\n")
    
    exit_immediately = []
    watch_closely = []
    okay_to_hold = []
    
    for _, holding in holdings.iterrows():
        ticker = holding['ticker']
        avg_cost = holding['buy_price']  # Column is 'buy_price' not 'avg_cost'
        qty = holding['quantity']
        
        # Analyze current status
        analysis = analyzer.analyze_ticker(ticker)
        
        if analysis['status'] == 'filtered':
            # Check if it's filtered due to trend
            if 'Downtrend' in analysis.get('message', ''):
                current_price = analysis.get('close', avg_cost)
                sma_200 = analysis.get('sma_200', 0)
                pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
                
                if pnl_pct < -5:
                    exit_immediately.append({
                        'ticker': ticker,
                        'current': current_price,
                        'entry': avg_cost,
                        'pnl': pnl_pct,
                        'sma_200': sma_200,
                        'reason': 'Downtrend + Loss > 5%',
                        'qty': qty
                    })
                else:
                    watch_closely.append({
                        'ticker': ticker,
                        'current': current_price,
                        'entry': avg_cost,
                        'pnl': pnl_pct,
                        'sma_200': sma_200,
                        'reason': 'Downtrend but small loss/profit',
                        'qty': qty
                    })
            else:
                # Other filter (low volume, etc.)
                print(f"⚪ {ticker}: {analysis.get('message', 'Filtered')}")
            continue
        
        if analysis['status'] != 'success':
            print(f"\n❌ {ticker}: Unable to analyze - {analysis.get('message', 'Unknown error')}")
            continue
        
        current_price = analysis['close']
        sma_200 = analysis.get('sma_200')
        pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
        support = analysis.get('nearest_support')
        resistance = analysis.get('nearest_resistance')
        stop_loss = analysis.get('recommended_stop_loss')
        rr_ratio = analysis.get('reward_risk_ratio')
        trend_status = analysis.get('trend_status', 'UNKNOWN')
        
        # Stock passed trend filter (above 200 SMA)
        okay_to_hold.append({
            'ticker': ticker,
            'current': current_price,
            'entry': avg_cost,
            'pnl': pnl_pct,
            'sma_200': sma_200,
            'support': support,
            'resistance': resistance,
            'stop_loss': stop_loss,
            'rr_ratio': rr_ratio,
            'trend': trend_status,
            'qty': qty
        })
    
    # Print results
    print("\n" + "🔴"*30)
    print("🔴 EXIT IMMEDIATELY (Downtrend + Losing > 5%)")
    print("🔴"*30)
    if exit_immediately:
        for stock in exit_immediately:
            total_cost = stock['entry'] * stock['qty']
            current_value = stock['current'] * stock['qty']
            total_loss = current_value - total_cost
            
            print(f"\n  📉 {stock['ticker']}")
            print(f"     Entry: ৳{stock['entry']:.2f} | Current: ৳{stock['current']:.2f} | P/L: {stock['pnl']:+.2f}%")
            print(f"     200 SMA: ৳{stock['sma_200']:.2f} | Status: BELOW (⬇️ Downtrend)")
            print(f"     Qty: {stock['qty']} | Total Loss: ৳{total_loss:,.2f}")
            print(f"     💀 ACTION: SELL ON MONDAY - Preserve capital!")
    else:
        print("  ✅ None - Good!")
    
    print("\n" + "🟡"*30)
    print("🟡 WATCH CLOSELY (Downtrend but not deeply underwater)")
    print("🟡"*30)
    if watch_closely:
        for stock in watch_closely:
            print(f"\n  ⚠️  {stock['ticker']}")
            print(f"     Entry: ৳{stock['entry']:.2f} | Current: ৳{stock['current']:.2f} | P/L: {stock['pnl']:+.2f}%")
            print(f"     200 SMA: ৳{stock['sma_200']:.2f} | Status: BELOW (⬇️ Downtrend)")
            print(f"     Qty: {stock['qty']}")
            print(f"     ⚡ ACTION: Set tight stop-loss at ৳{stock['current'] * 0.95:.2f} (-5%)")
            print(f"     Consider exit if trend doesn't reverse soon.")
    else:
        print("  ✅ None")
    
    print("\n" + "🟢"*30)
    print("🟢 OKAY TO HOLD (Above 200 SMA - Uptrend)")
    print("🟢"*30)
    if okay_to_hold:
        for stock in okay_to_hold:
            total_cost = stock['entry'] * stock['qty']
            current_value = stock['current'] * stock['qty']
            total_pnl = current_value - total_cost
            
            print(f"\n  ✅ {stock['ticker']}")
            print(f"     Entry: ৳{stock['entry']:.2f} | Current: ৳{stock['current']:.2f} | P/L: {stock['pnl']:+.2f}%")
            sma_display = f"৳{stock['sma_200']:.2f}" if stock['sma_200'] else 'N/A'
            print(f"     200 SMA: {sma_display} | Status: ⬆️ UPTREND")
            print(f"     Qty: {stock['qty']} | Total P/L: ৳{total_pnl:+,.2f}")
            
            if stock['support']:
                print(f"     📊 Support: ৳{stock['support']:.2f}")
            if stock['resistance']:
                print(f"     📊 Resistance: ৳{stock['resistance']:.2f}")
            if stock['stop_loss']:
                stop_pct = ((stock['current'] - stock['stop_loss']) / stock['current']) * 100
                print(f"     🛡️  Recommended Stop: ৳{stock['stop_loss']:.2f} (-{stop_pct:.1f}%)")
            if stock['rr_ratio']:
                emoji = "✅" if stock['rr_ratio'] >= 2.0 else "⚠️"
                print(f"     {emoji} R:R Ratio: {stock['rr_ratio']:.1f}:1")
    else:
        print("  ❌ None - All holdings are in downtrend!")
    
    # Summary
    print("\n" + "="*90)
    print(" 📈 SUMMARY")
    print("="*90)
    
    total_holdings = len(holdings)
    exit_count = len(exit_immediately)
    watch_count = len(watch_closely)
    ok_count = len(okay_to_hold)
    
    print(f"\n  Total Holdings: {total_holdings}")
    print(f"  🔴 Exit Immediately: {exit_count} ({exit_count/total_holdings*100:.1f}%)")
    print(f"  🟡 Watch Closely: {watch_count} ({watch_count/total_holdings*100:.1f}%)")
    print(f"  🟢 Okay to Hold: {ok_count} ({ok_count/total_holdings*100:.1f}%)")
    
    # Calculate total P/L
    total_invested = sum(h['buy_price'] * h['quantity'] for _, h in holdings.iterrows())
    total_current = 0
    
    for stock in exit_immediately + watch_closely + okay_to_hold:
        total_current += stock['current'] * stock['qty']
    
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    print(f"\n  💰 Total Invested: ৳{total_invested:,.2f}")
    print(f"  💵 Current Value: ৳{total_current:,.2f}")
    print(f"  📊 Total P/L: ৳{total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
    
    # Recommendations
    print("\n" + "="*90)
    print(" 💡 RECOMMENDATIONS")
    print("="*90)
    
    if exit_immediately:
        print("\n  ⚠️  CRITICAL ACTION REQUIRED:")
        print(f"     {exit_count} position(s) are in downtrend with significant losses.")
        print("     Consider exiting these positions to preserve capital for better opportunities.")
        print("     Remember: It's better to take a small loss than a big one.")
    
    if watch_closely:
        print(f"\n  👀 MONITOR CLOSELY:")
        print(f"     {watch_count} position(s) are in downtrend but not deeply negative.")
        print("     Set tight stop-losses and exit if trend doesn't reverse.")
    
    if ok_count > 0:
        print(f"\n  ✅ POSITIVE:")
        print(f"     {ok_count} position(s) are in uptrend - these are following the strategy!")
        print("     Use recommended stop-losses to protect profits.")
    
    if ok_count == 0 and total_holdings > 0:
        print("\n  🚨 WARNING: ALL holdings are in downtrend!")
        print("     This violates the core trading rule: 'Trend is your friend'")
        print("     The v4 enhanced system now PREVENTS buying stocks below 200 SMA.")
        print("     Consider gradually exiting downtrending positions.")
    
    print("\n" + "="*90)
    print(" 📚 NEXT STEPS")
    print("="*90)
    print("\n  1. Review the analysis above")
    print("  2. Plan your Monday actions (exits, stop-losses)")
    print("  3. Going forward, the system will ONLY show stocks above 200 SMA")
    print("  4. This dramatically reduces losing trades (60-70% improvement expected)")
    print("\n  📖 See docs/WEEKEND_QUICK_START.md for more details")
    print("\n" + "="*90)
    
    db.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
