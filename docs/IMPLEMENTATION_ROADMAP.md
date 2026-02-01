# 🚀 Implementation Roadmap: Enhanced DSE Sniper Trading System

**Created:** February 1, 2026  
**Target:** Fix bearish portfolio performance with proven technical analysis  
**Approach:** Incremental improvements, battle-tested each step

---

## 🎯 Overview

This roadmap implements the hybrid strategy combining:
- **Your Edge:** Volume-based syndicate detection (RVOL)
- **Missing Pieces:** Entry timing, exit strategy, trend confirmation
- **YouTube Wisdom:** Multi-timeframe, support/resistance, reward:risk ratios

---

## 📅 Phase 1: Critical Fixes (Week 1-2) - IMMEDIATE IMPACT

### 🔴 Priority 1: Enforce Trend Filter (Weekend Task)

**Problem:** Buying stocks below 200 SMA = catching falling knives

**Current Code** (`src/analyzer.py`, line ~350):
```python
# In calculate_score():
if row['close'] > row['sma_200']:
    score += 10
    reasons.append("Above 200 SMA")
else:
    score -= 50
    reasons.append("Below 200 SMA")
```

**Issue:** Even with -50 points, total score can still reach 80+ (BUY signal)

**Fix:**
```python
# In analyze_ticker(), before calculate_score():

# MANDATORY TREND FILTER
if pd.notna(row['sma_200']) and row['close'] < row['sma_200']:
    return {
        'ticker': ticker,
        'status': 'filtered',
        'message': 'Below 200 SMA - Downtrend (Trend Filter)',
        'date': row['date'].strftime('%Y-%m-%d'),
        'close': round(row['close'], 2),
        'sma_200': round(row['sma_200'], 2)
    }
```

**Expected Impact:**
- Eliminate 60-70% of losing trades
- Only trade WITH the trend
- Immediate improvement in win rate

**Testing:**
```bash
# Check current portfolio against this filter
python -c "
from src.analyzer import StockAnalyzer
from src.db_manager import DatabaseManager

db = DatabaseManager()
analyzer = StockAnalyzer(db)

# Test your current holdings
holdings = ['IBNSINA', 'ISLAMIINS', 'PROVATIINS', 'RELIANCINS', 'RUPALIINS', 'SANDHANINS', 'TAKAFULINS']

for ticker in holdings:
    result = analyzer.analyze_ticker(ticker)
    print(f'{ticker}: {result.get(\"message\", result.get(\"signal\", \"N/A\"))}')
"
```

---

### 🔴 Priority 2: Add Support/Resistance Detection

**Purpose:** Know where to place stop-loss and take-profit

**New Function** (add to `src/analyzer.py`):
```python
def find_support_resistance(self, df: pd.DataFrame, current_price: float, 
                            lookback=60, num_levels=3) -> Dict:
    """
    Identify key support and resistance levels
    
    Args:
        df: DataFrame with OHLC data
        current_price: Current closing price
        lookback: Days to look back (default: 60)
        num_levels: Number of levels to identify (default: 3)
        
    Returns:
        Dictionary with nearest support and resistance
    """
    # Get recent price action
    recent_df = df.tail(lookback)
    
    # Find swing highs (resistance candidates)
    swing_highs = []
    for i in range(1, len(recent_df) - 1):
        if (recent_df.iloc[i]['high'] > recent_df.iloc[i-1]['high'] and
            recent_df.iloc[i]['high'] > recent_df.iloc[i+1]['high']):
            swing_highs.append(recent_df.iloc[i]['high'])
    
    # Find swing lows (support candidates)
    swing_lows = []
    for i in range(1, len(recent_df) - 1):
        if (recent_df.iloc[i]['low'] < recent_df.iloc[i-1]['low'] and
            recent_df.iloc[i]['low'] < recent_df.iloc[i+1]['low']):
            swing_lows.append(recent_df.iloc[i]['low'])
    
    # Cluster nearby levels (within 2% of each other)
    def cluster_levels(levels, tolerance=0.02):
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = [[levels[0]]]
        
        for level in levels[1:]:
            if abs(level - clusters[-1][-1]) / clusters[-1][-1] < tolerance:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        
        return [np.mean(cluster) for cluster in clusters]
    
    resistance_levels = cluster_levels(swing_highs)
    support_levels = cluster_levels(swing_lows)
    
    # Find nearest support (below current price)
    nearest_support = None
    if support_levels:
        supports_below = [s for s in support_levels if s < current_price]
        if supports_below:
            nearest_support = max(supports_below)
    
    # Find nearest resistance (above current price)
    nearest_resistance = None
    if resistance_levels:
        resistances_above = [r for r in resistance_levels if r > current_price]
        if resistances_above:
            nearest_resistance = min(resistances_above)
    
    return {
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'all_support_levels': support_levels,
        'all_resistance_levels': resistance_levels
    }
```

---

### 🔴 Priority 3: Calculate Reward:Risk Ratio

**New Function** (add to `src/analyzer.py`):
```python
def calculate_reward_risk_ratio(self, entry_price: float, stop_loss: float, 
                                target: float) -> Dict:
    """
    Calculate reward:risk ratio for trade planning
    
    Minimum acceptable: 2:1 (make $2 for every $1 risked)
    
    Args:
        entry_price: Planned entry price
        stop_loss: Stop loss price
        target: Take profit target
        
    Returns:
        Dictionary with RR ratio and recommendation
    """
    risk = entry_price - stop_loss
    reward = target - entry_price
    
    if risk <= 0:
        return {
            'valid': False,
            'reason': 'Stop loss must be below entry price'
        }
    
    rr_ratio = reward / risk
    
    return {
        'valid': True,
        'ratio': round(rr_ratio, 2),
        'risk_amount': round(risk, 2),
        'risk_percent': round((risk / entry_price) * 100, 2),
        'reward_amount': round(reward, 2),
        'reward_percent': round((reward / entry_price) * 100, 2),
        'recommended': rr_ratio >= 2.0
    }
```

---

### 🔴 Priority 4: Enhanced Scoring with RR Check

**Modify** `calculate_score()` in `src/analyzer.py`:

```python
def calculate_score(self, row: pd.Series, df: pd.DataFrame, 
                   paid_up_capital: Optional[float] = None) -> Dict:
    """
    Enhanced scoring with support/resistance and RR ratio
    """
    score = 0
    reasons = []
    
    current_price = row['close']
    
    # Check RVOL (unchanged)
    if pd.notna(row['rvol']) and row['rvol'] > self.rvol_threshold:
        score += 50
        reasons.append(f"High RVOL ({row['rvol']:.1f}x)")
        
        # Quiet Accumulation (unchanged)
        if pd.notna(row['price_change']) and abs(row['price_change']) < self.price_change_threshold:
            score += 20
            reasons.append(f"Quiet Accumulation")
    
    # Low Float Multiplier (unchanged)
    if paid_up_capital is not None and paid_up_capital < self.low_cap_threshold:
        score += 20
        reasons.append(f"Low Float ({paid_up_capital:.1f} Cr)")
    
    # NEW: Support/Resistance Analysis
    sr_levels = self.find_support_resistance(df, current_price)
    
    nearest_support = sr_levels['nearest_support']
    nearest_resistance = sr_levels['nearest_resistance']
    
    # NEW: Calculate ATR-based stop loss
    atr = row['ATR'] if pd.notna(row['ATR']) else None
    
    if atr and nearest_support and nearest_resistance:
        # Stop loss: Lower of (Support - 2%) or (Price - 1.5*ATR)
        stop_from_support = nearest_support * 0.98
        stop_from_atr = current_price - (1.5 * atr)
        recommended_stop = max(stop_from_support, stop_from_atr)
        
        # Calculate RR ratio
        rr_analysis = self.calculate_reward_risk_ratio(
            current_price,
            recommended_stop,
            nearest_resistance
        )
        
        if rr_analysis['valid'] and rr_analysis['recommended']:
            score += 10
            reasons.append(f"Good RR Ratio ({rr_analysis['ratio']}:1)")
        elif rr_analysis['valid'] and rr_analysis['ratio'] < 2.0:
            score -= 30
            reasons.append(f"Poor RR Ratio ({rr_analysis['ratio']}:1)")
    
    # Above 200 SMA (will be checked earlier as mandatory filter)
    if pd.notna(row['sma_200']) and current_price > row['sma_200']:
        score += 10
        reasons.append("Above 200 SMA")
    
    return {
        'score': score,
        'reasons': reasons,
        'support': nearest_support,
        'resistance': nearest_resistance,
        'stop_loss': recommended_stop if 'recommended_stop' in locals() else None,
        'rr_ratio': rr_analysis['ratio'] if 'rr_analysis' in locals() and rr_analysis['valid'] else None
    }
```

---

### 🔴 Priority 5: Update analyze_ticker() Output

**Modify** the return statement in `analyze_ticker()`:

```python
# Prepare result (add new fields)
result = {
    'ticker': ticker,
    'status': 'success',
    'date': row['date'].strftime('%Y-%m-%d'),
    'close': round(row['close'], 2),
    'volume': int(row['volume']),
    # ... existing fields ...
    'score': score_result['score'],
    'signal': signal,
    'reasons': score_result['reasons'],
    
    # NEW FIELDS
    'nearest_support': round(score_result['support'], 2) if score_result['support'] else None,
    'nearest_resistance': round(score_result['resistance'], 2) if score_result['resistance'] else None,
    'recommended_stop_loss': round(score_result['stop_loss'], 2) if score_result['stop_loss'] else None,
    'reward_risk_ratio': score_result['rr_ratio'],
    'atr': round(row['ATR'], 2) if pd.notna(row['ATR']) else None
}
```

---

## 📅 Phase 2: Portfolio Analysis Tools (Week 3)

### Create Portfolio Analyzer Script

**New File:** `src/portfolio_analyzer.py`

```python
"""
Portfolio Health Check
Analyzes current holdings against new enhanced rules
"""

from src.analyzer import StockAnalyzer
from src.db_manager import DatabaseManager
from src.portfolio_manager import PortfolioManager
import pandas as pd

class PortfolioHealthCheck:
    """Check portfolio against enhanced trading rules"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.analyzer = StockAnalyzer(self.db)
        self.portfolio = PortfolioManager(self.db)
    
    def analyze_current_holdings(self):
        """Analyze all current holdings"""
        
        holdings = self.portfolio.get_all_holdings()
        
        if holdings.empty:
            print("No current holdings")
            return
        
        print("\n" + "="*80)
        print("PORTFOLIO HEALTH CHECK")
        print("="*80)
        
        results = []
        
        for _, holding in holdings.iterrows():
            ticker = holding['ticker']
            avg_cost = holding['avg_cost']
            current_qty = holding['quantity']
            
            # Get current analysis
            analysis = self.analyzer.analyze_ticker(ticker)
            
            if analysis['status'] != 'success':
                continue
            
            current_price = analysis['close']
            profit_loss = ((current_price - avg_cost) / avg_cost) * 100
            
            # Check against new rules
            warnings = []
            
            # Rule 1: Below 200 SMA?
            if analysis.get('sma_200') and current_price < analysis['sma_200']:
                warnings.append("⚠️ BELOW 200 SMA (Downtrend)")
            
            # Rule 2: No clear support?
            if not analysis.get('nearest_support'):
                warnings.append("⚠️ No clear support level")
            
            # Rule 3: Stop loss recommendation
            stop_loss_price = analysis.get('recommended_stop_loss')
            if stop_loss_price:
                stop_loss_pct = ((current_price - stop_loss_price) / current_price) * 100
            else:
                stop_loss_pct = 7.0  # Default 7%
                stop_loss_price = current_price * 0.93
            
            # Rule 4: Check if stop already hit
            if current_price < stop_loss_price:
                warnings.append(f"🔴 STOP LOSS HIT! Exit at {stop_loss_price:.2f}")
            
            results.append({
                'ticker': ticker,
                'avg_cost': avg_cost,
                'current_price': current_price,
                'profit_loss_pct': profit_loss,
                'quantity': current_qty,
                'sma_200': analysis.get('sma_200'),
                'nearest_support': analysis.get('nearest_support'),
                'recommended_stop': stop_loss_price,
                'warnings': warnings,
                'rr_ratio': analysis.get('reward_risk_ratio')
            })
        
        # Print summary
        df_results = pd.DataFrame(results)
        
        for _, row in df_results.iterrows():
            print(f"\n{row['ticker']}")
            print(f"  Entry: {row['avg_cost']:.2f} | Current: {row['current_price']:.2f} | P/L: {row['profit_loss_pct']:+.2f}%")
            print(f"  200 SMA: {row['sma_200']:.2f if row['sma_200'] else 'N/A'}")
            print(f"  Support: {row['nearest_support']:.2f if row['nearest_support'] else 'N/A'}")
            print(f"  Recommended Stop: {row['recommended_stop']:.2f}")
            
            if row['warnings']:
                for warning in row['warnings']:
                    print(f"  {warning}")
        
        # Summary stats
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        total_positions = len(df_results)
        below_sma = len([r for r in results if r['sma_200'] and r['current_price'] < r['sma_200']])
        stop_hit = len([r for r in results if r['current_price'] < r['recommended_stop']])
        
        print(f"Total Positions: {total_positions}")
        print(f"Below 200 SMA: {below_sma} ({below_sma/total_positions*100:.1f}%)")
        print(f"Stop Loss Hit: {stop_hit} ({stop_hit/total_positions*100:.1f}%)")
        print(f"Avg P/L: {df_results['profit_loss_pct'].mean():.2f}%")
        
        return df_results

if __name__ == "__main__":
    checker = PortfolioHealthCheck()
    checker.analyze_current_holdings()
```

**Usage:**
```bash
python src/portfolio_analyzer.py
```

---

## 📅 Phase 3: Backend API Updates (Week 4)

### Update API Endpoints

**File:** `backend/main.py`

Add new endpoint for enhanced analysis:

```python
@app.get("/api/analysis/enhanced/{ticker}")
def get_enhanced_analysis(ticker: str):
    """
    Get enhanced analysis with support/resistance and RR ratio
    """
    try:
        analysis = analyzer.analyze_ticker(ticker.upper())
        
        if analysis['status'] != 'success':
            raise HTTPException(status_code=404, detail=analysis.get('message', 'Analysis failed'))
        
        return {
            'success': True,
            'data': analysis
        }
    except Exception as e:
        logger.error(f"Enhanced analysis error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/health-check")
def portfolio_health_check():
    """
    Analyze portfolio against enhanced rules
    """
    try:
        from src.portfolio_analyzer import PortfolioHealthCheck
        
        checker = PortfolioHealthCheck()
        results = checker.analyze_current_holdings()
        
        return {
            'success': True,
            'holdings': results.to_dict('records') if not results.empty else []
        }
    except Exception as e:
        logger.error(f"Portfolio health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 📅 Phase 4: Frontend Updates (Week 5)

### Enhanced Stock Card Display

**File:** `frontend/app/page.tsx`

Update the stock card to show support/resistance:

```typescript
{/* Enhanced Trading Levels */}
{stock.nearest_support && stock.nearest_resistance && (
  <div className="mt-2 text-xs space-y-1">
    <div className="flex justify-between">
      <span className="text-gray-400">Resistance:</span>
      <span className="text-red-400">৳{stock.nearest_resistance.toFixed(2)}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-gray-400">Support:</span>
      <span className="text-green-400">৳{stock.nearest_support.toFixed(2)}</span>
    </div>
    {stock.recommended_stop_loss && (
      <div className="flex justify-between">
        <span className="text-gray-400">Stop Loss:</span>
        <span className="text-orange-400">৳{stock.recommended_stop_loss.toFixed(2)}</span>
      </div>
    )}
    {stock.reward_risk_ratio && (
      <div className="flex justify-between">
        <span className="text-gray-400">R:R Ratio:</span>
        <span className={stock.reward_risk_ratio >= 2 ? "text-green-400" : "text-red-400"}>
          {stock.reward_risk_ratio.toFixed(1)}:1
        </span>
      </div>
    )}
  </div>
)}
```

---

## 📅 Phase 5: Testing & Validation (Week 6)

### Backtesting Script

**New File:** `tests/backtest_enhanced_strategy.py`

```python
"""
Backtest enhanced strategy vs old strategy
Compare win rates and profit factors
"""

from src.analyzer import StockAnalyzer
from src.db_manager import DatabaseManager
import pandas as pd
from datetime import datetime, timedelta

def backtest_comparison(start_date='2025-01-01', end_date='2026-01-31'):
    """
    Compare old vs new strategy
    """
    db = DatabaseManager()
    analyzer = StockAnalyzer(db)
    
    # Get all tickers
    tickers = db.get_all_tickers()
    
    results_old = []
    results_new = []
    
    # Simulate trades
    for ticker in tickers[:50]:  # Test on 50 stocks
        df = db.get_stock_data(ticker)
        
        if df.empty or len(df) < 200:
            continue
        
        df = analyzer.calculate_indicators(df)
        
        for i in range(200, len(df) - 20):  # Need 20 days for exit
            row = df.iloc[i]
            
            # OLD STRATEGY
            if row['rvol'] > 2.5:
                entry_price = row['close']
                stop_old = entry_price * 0.93  # Fixed 7%
                
                # Check next 20 days
                future = df.iloc[i+1:i+21]
                
                # Did we hit stop?
                if future['low'].min() < stop_old:
                    results_old.append({
                        'ticker': ticker,
                        'entry_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': stop_old,
                        'pnl_pct': -7,
                        'outcome': 'LOSS'
                    })
                else:
                    # Take profit at +10% or end of period
                    exit_price = min(entry_price * 1.10, future['close'].iloc[-1])
                    pnl = ((exit_price - entry_price) / entry_price) * 100
                    
                    results_old.append({
                        'ticker': ticker,
                        'entry_date': row['date'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': pnl,
                        'outcome': 'WIN' if pnl > 0 else 'LOSS'
                    })
            
            # NEW STRATEGY (with filters)
            if (row['rvol'] > 2.5 and 
                pd.notna(row['sma_200']) and 
                row['close'] > row['sma_200']):  # MANDATORY FILTER
                
                # Similar backtest logic for new strategy
                # TODO: Implement full new strategy backtest
                pass
    
    # Calculate metrics
    df_old = pd.DataFrame(results_old)
    
    if not df_old.empty:
        print("\n=== OLD STRATEGY ===")
        print(f"Total Trades: {len(df_old)}")
        print(f"Win Rate: {(df_old['outcome'] == 'WIN').sum() / len(df_old) * 100:.1f}%")
        print(f"Avg Win: {df_old[df_old['outcome'] == 'WIN']['pnl_pct'].mean():.2f}%")
        print(f"Avg Loss: {df_old[df_old['outcome'] == 'LOSS']['pnl_pct'].mean():.2f}%")
        print(f"Total PnL: {df_old['pnl_pct'].sum():.2f}%")

if __name__ == "__main__":
    backtest_comparison()
```

---

## 🎯 Implementation Checklist

### Weekend (Feb 1-2, 2026)
- [ ] Add trend filter (no buying below 200 SMA)
- [ ] Run portfolio health check
- [ ] Identify positions that should be exited

### Week 1 (Feb 3-9)
- [ ] Implement support/resistance detection
- [ ] Add reward:risk ratio calculation
- [ ] Update scoring function
- [ ] Test on historical data

### Week 2 (Feb 10-16)
- [ ] Create portfolio analyzer script
- [ ] Update all current holdings with new stop losses
- [ ] Document results

### Week 3 (Feb 17-23)
- [ ] Update backend API endpoints
- [ ] Test API responses
- [ ] Update API documentation

### Week 4 (Feb 24-Mar 2)
- [ ] Update frontend UI components
- [ ] Add support/resistance visualization
- [ ] Add RR ratio display

### Week 5 (Mar 3-9)
- [ ] Write backtesting script
- [ ] Compare old vs new strategy
- [ ] Measure improvement

### Week 6 (Mar 10-16)
- [ ] Paper trading with new rules
- [ ] Monitor performance
- [ ] Fine-tune parameters

---

## 📊 Success Metrics

Track these weekly:

| Metric | Current (Est.) | Target |
|--------|---------------|--------|
| Win Rate | 30-40% | 55-65% |
| Avg Win | Unknown | 8-12% |
| Avg Loss | -7%+ | -3-5% |
| Profit Factor | <1.0 | >1.5 |
| Trades/Week | High | Lower (better quality) |

---

## ⚠️ Risk Management Rules (Non-Negotiable)

1. **Never buy below 200 SMA** (downtrend protection)
2. **Always calculate RR ratio** (minimum 2:1)
3. **Use ATR for stop loss** (volatility-adjusted)
4. **Set stops on entry** (no emotional decisions)
5. **Honor stop losses** (no hoping, no averaging down)

---

## 🔄 Iterative Approach

Don't implement everything at once:

1. **Week 1:** Add filters, test
2. **Week 2:** If improved, continue. If not, revert and analyze
3. **Week 3:** Add next feature
4. **Repeat**

---

## 📚 Additional Resources

- **YouTube Reference:** Multi-timeframe analysis, entry timing
- **Your Edge:** Volume-based syndicate detection (keep this!)
- **Books:** "Trade Your Way to Financial Freedom" (Van Tharp)

---

## 🎓 Key Takeaways

**What's Working:**
- Volume analysis (RVOL detection)
- Projected volume calculation
- Low float identification

**What's Missing:**
- Entry timing
- Exit strategy
- Trend alignment

**What to Add:**
- Support/resistance levels
- Reward:risk ratios
- Mandatory trend filters

---

**Remember:** The goal isn't to make every trade a winner. The goal is to make winning trades bigger than losing trades, and cut losses quickly.

**Your system finds the RIGHT stocks. Now make it find the RIGHT time and the RIGHT price.**
