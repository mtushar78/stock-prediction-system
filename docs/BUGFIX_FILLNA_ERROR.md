# Bug Fix: fillna(None) ValueError

**Date**: 2026-02-01  
**Severity**: CRITICAL  
**Impact**: API returned empty results despite valid data in database

## The Problem

The `/api/sniper-signals` endpoint was silently failing and returning `[]` even though the database contained 271 valid signals.

### Root Cause

Invalid pandas `fillna()` usage:

```python
# BROKEN CODE:
for col in numeric_columns:
    if col in df.columns:
        df[col] = df[col].fillna(0 if col != 'sma_200' else None)  # ❌ WRONG!
```

When `col == 'sma_200'`, this became `df[col].fillna(None)`, which raises:

```
ValueError: Must specify a fill 'value' or 'method'.
```

This error was caught by a generic try/except block that returned `[]`, causing **silent failure**.

## The Solution

### 1. Fixed the fillna Logic

```python
# FIXED CODE:
# Fill numeric columns with 0 (except sma_200 which stays None)
numeric_columns = ['projected_vol', 'price_change_pct', 'avg_volume_20', 'rvol', 'score', 'volume', 'close']
for col in numeric_columns:
    if col in df.columns:
        df[col] = df[col].fillna(0)

# sma_200 is excluded from the list, so NaN values stay as None for JSON compatibility
```

### 2. Added Comprehensive Error Logging

**Before**: Errors were silently caught  
**After**: Explicit logging at every step

```python
logger.info(f"✅ Fetched {len(df)} signals from signals_today table")
# ... processing ...
logger.info(f"✅ Processed NaN values successfully")
# ... processing ...
logger.info(f"✅ Returning {len(result)} signals to frontend")
```

**On Error**: Full stack trace is logged

```python
except Exception as e:
    logger.error(f"❌ CRITICAL ERROR processing signals data: {e}")
    import traceback
    logger.error(traceback.format_exc())
    raise HTTPException(status_code=500, detail=f"Error processing signals: {str(e)}")
```

### 3. Removed Silent Failures

Changed from:
```python
except Exception as e:
    logger.error(f"Error: {e}")
    return []  # ❌ Silent failure!
```

To:
```python
except Exception as e:
    logger.error(f"❌ CRITICAL ERROR: {e}")
    logger.error(traceback.format_exc())
    raise HTTPException(status_code=500, detail=str(e))  # ✅ Explicit error!
```

## Prevention Measures

### 1. Comprehensive Logging

Every critical operation now logs:
- ✅ Success messages with counts
- ⚠️  Warning messages for empty results
- ❌ Error messages with full stack traces

### 2. No More Silent Failures

Instead of returning empty arrays on error, the API now:
- Raises `HTTPException` with 500 status
- Returns detailed error message
- Logs full stack trace

### 3. Monitoring

Check logs to detect issues:

```bash
# Check for errors
sudo journalctl -u dse-sniper-backend --since "1 hour ago" | grep "CRITICAL ERROR"

# Check signal counts
sudo journalctl -u dse-sniper-backend --since "1 hour ago" | grep "Returning.*signals"
```

### 4. Testing Script

Created `test_api_logic.py` to test the exact API logic locally before deployment:

```bash
python3 test_api_logic.py
```

This helped identify the exact line where the error occurred.

## How to Ensure This Never Happens Again

### 1. Check Logs Regularly

```bash
# After any deployment, check for errors
sudo journalctl -u dse-sniper-backend -n 100 --no-pager | grep -E "(ERROR|CRITICAL)"
```

### 2. Monitor API Health

The endpoint now returns HTTP 500 on failure instead of silently returning `[]`:

```bash
curl -I https://dse-sniper-backend.maksudul.com/api/sniper-signals
# Should return: HTTP/2 200 OK
# If error: HTTP/2 500 Internal Server Error
```

### 3. Test Before Deploying

Always run the test script after changes:

```bash
python3 test_api_logic.py
```

### 4. Never Use fillna(None)

**ALWAYS validate fillna() arguments:**

```python
# ❌ NEVER DO THIS:
df[col].fillna(None)  # Raises ValueError!

# ✅ ALWAYS DO THIS:
df[col].fillna(0)     # Use a valid value
df[col].fillna('')    # Or valid string
# Or skip the column if you want to keep NaN as None
```

### 5. Avoid Generic try/except

```python
# ❌ BAD - Hides errors:
try:
    # ... code ...
except Exception as e:
    logger.error(f"Error: {e}")
    return []  # Silent failure!

# ✅ GOOD - Explicit errors:
try:
    # ... code ...
except Exception as e:
    logger.error(f"❌ CRITICAL: {e}")
    logger.error(traceback.format_exc())
    raise HTTPException(status_code=500, detail=str(e))
```

## Lessons Learned

1. **Never trust pandas with None** - Use explicit values for fillna()
2. **Always log at critical steps** - Helps debug production issues
3. **Never silently fail** - Return proper HTTP error codes
4. **Test locally first** - Use test scripts before deploying
5. **Monitor logs after deployment** - Catch issues immediately

## Files Modified

- `backend/main.py` - Fixed fillna() logic and added comprehensive error handling
- `test_api_logic.py` - Created diagnostic script
- `check_signals.py` - Created database validation script
- `run_scheduler_manually.py` - Created manual scheduler runner

## Verification

After fix:
- ✅ Local API returns 12 signals
- ✅ Production API returns 16 signals
- ✅ Logs show detailed progress
- ✅ Errors raise HTTP 500 instead of silent []
- ✅ Frontend displays all signals correctly
