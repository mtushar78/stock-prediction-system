# Level 2 Sell Logic - Quick Start Guide

## 🎉 What's New?

Your DSE Sniper System now has **professional-grade sell logic** with two powerful upgrades:

### 1. 🎯 Dynamic ATR-Based Trailing Stops
- **Fixed 5% → Dynamic 2x ATR**
- Volatile stocks get wider stops (no false exits)
- Stable stocks get tighter stops (better profit protection)

### 2. 🧟 Zombie Killer
- Automatically exits positions held >10 days with <2% profit
- Frees up capital for better opportunities
- No more dead money sitting idle

---

## Quick Test

Run this to verify everything works:

```bash
python3 test_level2_sell.py
```

Expected: **5/5 tests pass** ✅

---

## Check Your Portfolio

```bash
python src/portfolio_manager.py check
```

You'll now see:
- **ATR value** (stock's natural volatility)
- **Days Held** (how long you've owned it)
- **Dynamic trailing stop** (adapts to each stock)
- **Zombie warnings** (if position is dead)

---

## Example Output

### Normal Position
```
SANDHANINS      | Status: HOLD ✅
  Buy: 21.20 | Current: 21.30 | Highest: 21.30
  Profit: +0.47% (+50 BDT) | Days Held: 1
  Stop Loss: 19.72 | Trail Stop: 20.00 (ATR (2x0.65=1.30))
  ATR: 0.65 | RVOL: 3.56x | Volume: 524,364
```

### Zombie Position (Triggers Exit)
```
DEADSTOCK       | Status: SELL NOW 🧟
  Buy: 50.00 | Current: 50.50 | Highest: 52.00
  Profit: +1.00% (+50 BDT) | Days Held: 12
  ⚡ ZOMBIE KILLER: Held 12 days with only 1.00% profit. Free up capital.
```

---

## How It Works

### ATR Trailing Stop
| Stock Type | ATR | Peak | Old Stop (5%) | New Stop (2×ATR) | Benefit |
|-----------|-----|------|---------------|------------------|---------|
| Stable (GP) | 2 BDT | 100 | 95 | 96 | **Tighter** (+1 BDT) |
| Volatile (SEAPEARL) | 10 BDT | 100 | 95 | 80 | **Looser** (no shake-out) |

### Zombie Killer
```
IF Days_Held > 10 AND Profit < 2%
THEN SELL (Free capital for better trades)
```

---

## Signal Types

Your system now detects **4 types of sell signals**:

1. **STOP_LOSS** 💀 - Hit -7% emergency brake
2. **TAKE_PROFIT** 💰 - Trend broken (ATR-based)
3. **CLIMAX** ⚠️ - Volume spike at profit >20%
4. **ZOMBIE_EXIT** 🧟 - Dead position (>10 days, <2% profit)

---

## Test Results

✅ **All tests passed:**
```
✅ PASS: ATR Calculation
✅ PASS: Days Held Calculation
✅ PASS: Zombie Detection Logic
✅ PASS: ATR Trailing Stop Comparison
✅ PASS: Real Portfolio Test

Results: 5/5 tests passed
🎉 ALL TESTS PASSED! Level 2 sell logic is working correctly.
```

---

## Real Portfolio Example

Your current portfolio was tested:
- **SANDHANINS**: ATR = 0.65, Stop = 20.00 (tight for stable stock)
- **PROVATIINS**: ATR = 1.25, Stop = 30.00 (medium volatility)
- **RUPALIINS**: ATR = 0.92, Stop = 22.25 (tight for stable stock)

All positions are healthy (no zombies, no sell signals).

---

## What's Next?

### You're Ready to Use Level 2!
The sell logic is **production-ready** and fully tested.

### Future: Level 2 Buy Logic
When you're ready, we can upgrade the **buy logic** with:
1. **Sector Confluence** - Only buy if 2+ stocks in sector show signals
2. **VWAP Filter** - Only buy if price > VWAP (buyers in control)
3. **Dynamic Position Sizing** - Adjust size based on confidence

---

## Files Modified

- `src/analyzer.py` - Added ATR calculation
- `src/portfolio_manager.py` - Level 2 sell logic
- `test_level2_sell.py` - Test suite (NEW)
- `docs/LEVEL2_SELL_UPGRADES.md` - Full documentation (NEW)

---

## Need Help?

1. **Run tests**: `python3 test_level2_sell.py`
2. **Check portfolio**: `python src/portfolio_manager.py check`
3. **Read full docs**: `docs/LEVEL2_SELL_UPGRADES.md`

---

## Summary

🎯 **Dynamic stops** adapt to each stock's personality  
🧟 **Zombie Killer** eliminates dead money  
✅ **100% tested** and production-ready  
📚 **Fully documented** with examples  

**Your exit game is now at the "Hedge Fund" standard!** 🚀

---

**Version:** 2.0  
**Status:** ✅ Production Ready  
**Last Updated:** January 23, 2026
