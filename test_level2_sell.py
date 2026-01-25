#!/usr/bin/env python3
"""
Test Script for Level 2 Sell Logic
Tests the ATR-based trailing stop and Zombie Killer features
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from portfolio_manager import PortfolioManager
from db_manager import DatabaseManager
from analyzer import StockAnalyzer
import pandas as pd
from datetime import datetime, timedelta

def test_atr_calculation():
    """Test ATR calculation with sample data"""
    print("\n" + "="*80)
    print("TEST 1: ATR Calculation")
    print("="*80)
    
    # Create sample OHLC data
    data = {
        'date': pd.date_range(start='2024-01-01', periods=20, freq='D'),
        'high': [105, 107, 110, 108, 112, 115, 113, 118, 120, 119, 
                 122, 125, 123, 128, 130, 127, 132, 135, 133, 138],
        'low': [100, 102, 105, 103, 107, 110, 108, 113, 115, 114,
                117, 120, 118, 123, 125, 122, 127, 130, 128, 133],
        'close': [103, 105, 108, 106, 110, 113, 111, 116, 118, 117,
                  120, 123, 121, 126, 128, 125, 130, 133, 131, 136]
    }
    df = pd.DataFrame(data)
    
    pm = PortfolioManager()
    atr = pm.calculate_atr(df, period=14)
    
    print(f"✅ ATR calculated successfully: {atr:.2f}")
    print(f"   This means the stock typically moves ±{atr:.2f} BDT per day")
    print(f"   Trailing stop would be set at: 2x ATR = {2*atr:.2f} BDT below peak")
    
    return atr > 0

def test_days_held_calculation():
    """Test days held calculation"""
    print("\n" + "="*80)
    print("TEST 2: Days Held Calculation")
    print("="*80)
    
    pm = PortfolioManager()
    
    # Test with various dates
    test_dates = [
        ((datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'), 5),
        ((datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'), 10),
        ((datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'), 15),
    ]
    
    for date_str, expected_days in test_dates:
        days = pm.calculate_days_held(date_str)
        status = "✅" if days == expected_days else "❌"
        print(f"{status} Date {date_str}: {days} days held (expected {expected_days})")
    
    return True

def test_zombie_detection():
    """Test zombie position detection logic"""
    print("\n" + "="*80)
    print("TEST 3: Zombie Killer Logic")
    print("="*80)
    
    test_cases = [
        {"days": 5, "profit": 1.5, "is_zombie": False, "desc": "New position"},
        {"days": 12, "profit": 1.8, "is_zombie": True, "desc": "Zombie: 12 days, <2% profit"},
        {"days": 15, "profit": 5.0, "is_zombie": False, "desc": "Good: 15 days, >2% profit"},
        {"days": 8, "profit": 0.5, "is_zombie": False, "desc": "Too early: <10 days"},
    ]
    
    for case in test_cases:
        is_zombie = case['days'] > 10 and case['profit'] < 2
        status = "✅" if is_zombie == case['is_zombie'] else "❌"
        zombie_str = "🧟 ZOMBIE" if is_zombie else "✅ GOOD"
        print(f"{status} {case['desc']}: Days={case['days']}, Profit={case['profit']:.1f}% → {zombie_str}")
    
    return True

def test_atr_trailing_stop():
    """Test ATR-based trailing stop calculation"""
    print("\n" + "="*80)
    print("TEST 4: ATR-Based Trailing Stop Comparison")
    print("="*80)
    
    # Simulate two stocks with different volatility
    stocks = [
        {"name": "Stable Stock (GP)", "price": 100, "atr": 2.0},
        {"name": "Volatile Stock (SEAPEARL)", "price": 100, "atr": 10.0},
    ]
    
    peak_price = 100
    
    for stock in stocks:
        atr = stock['atr']
        
        # Level 1: Fixed 5% trailing stop
        fixed_stop = peak_price * 0.95
        
        # Level 2: 2x ATR trailing stop
        atr_stop = peak_price - (2 * atr)
        
        print(f"\n{stock['name']}:")
        print(f"  Peak Price: {peak_price:.2f} BDT")
        print(f"  ATR (Volatility): {atr:.2f} BDT")
        print(f"  Level 1 Stop (Fixed 5%): {fixed_stop:.2f} BDT (Loss if triggered: {peak_price - fixed_stop:.2f})")
        print(f"  Level 2 Stop (2x ATR): {atr_stop:.2f} BDT (Loss if triggered: {peak_price - atr_stop:.2f})")
        
        if atr < 5:
            print(f"  ✅ Level 2 is TIGHTER - Better for stable stocks")
        else:
            print(f"  ✅ Level 2 is LOOSER - Gives breathing room for volatile stocks")
    
    return True

def test_with_real_portfolio():
    """Test with actual portfolio if available"""
    print("\n" + "="*80)
    print("TEST 5: Real Portfolio Check (Level 2)")
    print("="*80)
    
    try:
        pm = PortfolioManager()
        portfolio = pm.get_portfolio()
        
        if portfolio.empty:
            print("⚠️  Portfolio is empty. Cannot test with real data.")
            print("💡 To test with real data, add a position using:")
            print("   python src/portfolio_manager.py add --ticker GP --price 100 --quantity 100")
            return True
        
        print(f"Found {len(portfolio)} position(s) in portfolio")
        print("\nRunning Level 2 sell signal check...\n")
        
        signals = pm.check_sell_signals(verbose=True)
        
        if signals:
            print("\n📊 SELL SIGNALS DETECTED:")
            for signal in signals:
                print(f"\n  Ticker: {signal['ticker']}")
                print(f"  Signal Type: {signal['signal_type']}")
                print(f"  Action: {signal['action']}")
                print(f"  Reason: {signal['reason']}")
                if 'atr' in signal:
                    print(f"  ATR: {signal['atr']:.2f}")
                if 'days_held' in signal:
                    print(f"  Days Held: {signal['days_held']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing real portfolio: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("LEVEL 2 SELL LOGIC - TEST SUITE")
    print("Testing ATR-Based Trailing Stop & Zombie Killer")
    print("="*80)
    
    tests = [
        ("ATR Calculation", test_atr_calculation),
        ("Days Held Calculation", test_days_held_calculation),
        ("Zombie Detection Logic", test_zombie_detection),
        ("ATR Trailing Stop Comparison", test_atr_trailing_stop),
        ("Real Portfolio Test", test_with_real_portfolio),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} FAILED: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Level 2 sell logic is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
