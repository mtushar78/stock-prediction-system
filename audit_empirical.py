"""
Empirical audit: 50 random point-in-time chart-pattern readings.

Picks random (ticker, as-of-date) pairs, runs the analyzer on history UP TO
that date, then INDEPENDENTLY re-derives the book's identification rules and
measure-rule target from the raw OHLCV — and checks the engine agrees.

This is a second, data-driven audit that complements the code-vs-book review:
it proves the engine's *output geometry* actually satisfies Bulkowski's numeric
definitions on real DSE data, and that the measure-rule targets it reports match
the book formula applied to the real bars (catching mislabels / off-by-ones).

Run: python audit_empirical.py
"""

import random
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

from src.db_manager import DatabaseManager
from src.pattern_analyzer import PatternAnalyzer, clean_history

SEED = 20260701
TARGET_N = 50
TOL = 0.02  # 2% tolerance comparing re-derived target to engine target


def kp_price(pat, label_contains):
    for k in pat["key_points"]:
        if label_contains in (k.get("label") or ""):
            return k["price"]
    return None


def approx(a, b, tol=TOL):
    if a is None or b is None:
        return None
    if b == 0:
        return abs(a) < 1e-6
    return abs(a - b) / abs(b) <= tol


def verify(pat, df):
    """Return list of (check_name, passed(bool|None), detail)."""
    code = pat["code"]
    checks = []
    price_now = float(df.iloc[-1]["close"])
    tgt = pat.get("target")
    bo = pat.get("breakout_price")

    kps = pat["key_points"]
    prices = [k["price"] for k in kps]

    if code.startswith("double_bottom"):
        b1 = prices[0]; peak = prices[1]; b2 = prices[2]
        lo = min(b1, b2)
        checks.append(("bottoms within 5%", abs(b1 - b2) / ((b1 + b2) / 2) <= 0.05,
                       f"{b1:.2f} vs {b2:.2f}"))
        checks.append(("rise >=10%", (peak - lo) / lo >= 0.10, f"{(peak-lo)/lo*100:.1f}%"))
        exp = peak + (peak - lo)  # FULL height added to confirmation
        checks.append(("target = FULL height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code.startswith("double_top"):
        t1 = prices[0]; valley = prices[1]; t2 = prices[2]
        hi = max(t1, t2)
        checks.append(("tops within 5%", abs(t1 - t2) / ((t1 + t2) / 2) <= 0.05, f"{t1:.2f} vs {t2:.2f}"))
        checks.append(("drop >=10%", (hi - valley) / hi >= 0.10, f"{(hi-valley)/hi*100:.1f}%"))
        exp = valley - (hi - valley) / 2.0  # HALF height (book, double tops)
        checks.append(("target = HALF height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code == "triple_bottom":
        e = prices
        checks.append(("3 lows within 3.5%", (max(e) - min(e)) / min(e) <= 0.035, f"{e}"))
        exp = bo + (bo - min(e))  # full height off confirmation
        checks.append(("target = FULL height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code == "triple_top":
        e = prices
        checks.append(("3 highs within 3.5%", (max(e) - min(e)) / max(e) <= 0.035, f"{e}"))
        exp = bo - (max(e) - bo)  # FULL height (book) — the fix
        checks.append(("target = FULL height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code == "hs_bottom":
        ls, head, rs = prices
        checks.append(("head is lowest", head < ls and head < rs, f"head {head:.2f} vs {ls:.2f}/{rs:.2f}"))
        checks.append(("shoulders within 5%", abs(ls - rs) / ((ls + rs) / 2) <= 0.05, f"{ls:.2f} vs {rs:.2f}"))
        checks.append(("target above breakout", tgt is None or tgt > bo, f"{tgt} vs bo {bo}"))
    elif code == "hs_top":
        ls, head, rs = prices
        checks.append(("head is highest", head > ls and head > rs, f"head {head:.2f}"))
        checks.append(("shoulders within 5%", abs(ls - rs) / ((ls + rs) / 2) <= 0.05, f"{ls:.2f} vs {rs:.2f}"))
        checks.append(("target below breakout", tgt is None or tgt < bo, f"{tgt} vs bo {bo}"))
    elif code == "three_rising_valleys":
        checks.append(("valleys strictly rising", prices[0] < prices[1] < prices[2], f"{prices}"))
    elif code == "three_falling_peaks":
        checks.append(("peaks strictly falling", prices[0] > prices[1] > prices[2], f"{prices}"))
    elif code == "pipe_bottom":
        s1, s2 = prices[0], prices[1]
        checks.append(("spikes within 5%", abs(s1 - s2) / ((s1 + s2) / 2) <= 0.05, f"{s1:.2f} vs {s2:.2f}"))
        exp = bo + (bo - min(s1, s2))
        checks.append(("target = FULL height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code == "pipe_top":
        s1, s2 = prices[0], prices[1]
        checks.append(("spikes within 5%", abs(s1 - s2) / ((s1 + s2) / 2) <= 0.05, f"{s1:.2f} vs {s2:.2f}"))
        exp = bo - (max(s1, s2) - bo)
        checks.append(("target = FULL height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code in ("flag", "pennant"):
        pole_base = kp_price(pat, "base"); pole_top = kp_price(pat, "top")
        if pole_base and pole_top:
            gain = (pole_top - pole_base) / pole_base
            checks.append(("flagpole >=20%", gain >= 0.20, f"{gain*100:.0f}%"))
            exp = bo + (pole_top - pole_base)  # full pole projected off breakout
            checks.append(("target = pole height (book)", approx(tgt, exp), f"engine {tgt} vs book {exp:.2f}"))
    elif code == "high_tight_flag":
        pole_base = kp_price(pat, "base"); pole_top = kp_price(pat, "top")
        if pole_base and pole_top:
            gain = (pole_top - pole_base) / pole_base
            checks.append(("doubled (>=90%)", gain >= 0.90, f"{gain*100:.0f}%"))
    elif code == "falling_wedge":
        span_hi = float(df["high"].max())  # over whole slice approximates span extreme
        checks.append(("up-target near a swing high (book: highest high)",
                       tgt is None or tgt <= span_hi * 1.001, f"engine {tgt} vs span_hi {span_hi:.2f}"))
    elif code == "rising_wedge":
        span_lo = float(df["low"].min())
        checks.append(("down-target near a swing low (book: lowest low)",
                       tgt is None or tgt >= span_lo * 0.999, f"engine {tgt} vs span_lo {span_lo:.2f}"))
    elif "triangle" in code or "rectangle" in code:
        checks.append(("target on correct side of breakout",
                       tgt is None or bo is None or (tgt > bo) == (pat["bias"] == "bullish"),
                       f"tgt {tgt} bo {bo} bias {pat['bias']}"))
    elif code == "dead_cat_bounce":
        plunge = kp_price(pat, "plunge")
        checks.append(("event present", plunge is not None, f"plunge low {plunge}"))

    # Universal: confirmed patterns must have a real breakout bar
    if pat["status"] == "confirmed":
        checks.append(("confirmed has breakout_date", pat.get("breakout_date") is not None, ""))
    return checks


def main():
    rng = random.Random(SEED)
    db = DatabaseManager()
    pa = PatternAnalyzer()
    tickers = db.get_all_tickers()
    rng.shuffle(tickers)

    instances = []
    tried = 0
    for t in tickers:
        if len(instances) >= TARGET_N or tried > 1500:
            break
        df_full = clean_history(db.get_stock_data(t))
        if len(df_full) < 120:
            continue
        # a few random as-of dates per ticker
        for _ in range(3):
            tried += 1
            idx = rng.randint(90, len(df_full) - 1)
            sl = df_full.iloc[: idx + 1].reset_index(drop=True)
            try:
                res = pa.analyze(sl)
            except Exception as e:
                instances.append((t, "ERR", {"code": "ENGINE_ERROR"}, str(e), []))
                continue
            for pat in res["chart_patterns"]:
                asof = sl.iloc[-1]["date"]
                checks = verify(pat, sl)
                instances.append((t, str(asof)[:10], pat, "", checks))
                if len(instances) >= TARGET_N:
                    break

    # Report
    total_checks = 0
    failed = []
    per_code = {}
    print(f"=== EMPIRICAL AUDIT: {len(instances)} readings (seed {SEED}) ===\n")
    for (t, asof, pat, err, checks) in instances:
        code = pat.get("code")
        per_code.setdefault(code, [0, 0])
        if err and code == "ENGINE_ERROR":
            print(f"[ENGINE ERROR] {t}: {err}")
            continue
        line_fail = []
        for (name, passed, detail) in checks:
            if passed is None:
                continue
            total_checks += 1
            per_code[code][1] += 1
            if passed:
                per_code[code][0] += 1
            else:
                line_fail.append((name, detail))
        if line_fail:
            failed.append((t, asof, code, pat["status"], line_fail))

    print("Per-pattern pass rate (checks passed / total):")
    for code in sorted(per_code):
        ok, tot = per_code[code]
        print(f"  {code:24s} {ok}/{tot}")
    passed_checks = total_checks - sum(len(f[4]) for f in failed)
    print(f"\nTOTAL: {passed_checks}/{total_checks} checks passed "
          f"({100*passed_checks/max(total_checks,1):.1f}%)")

    if failed:
        print(f"\n=== {len(failed)} readings with >=1 FAILED check ===")
        for (t, asof, code, status, fails) in failed:
            print(f"  {t} @ {asof} [{code}/{status}]")
            for (name, detail) in fails:
                print(f"      FAIL: {name}  ({detail})")
    else:
        print("\nNo failed checks — every reading matches the book's rules & measure-rule targets.")


if __name__ == "__main__":
    main()
