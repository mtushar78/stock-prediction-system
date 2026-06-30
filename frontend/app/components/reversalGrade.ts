import { Grade, GradeResult, gradeColor } from './breakoutGrade';

export type { Grade, GradeResult };
export { gradeColor };

export interface ReversalChecksShape {
  close?: number; rsi?: number; max_rsi?: number;
  prev_close?: number; green_day?: boolean;
  rvol?: number; min_rvol?: number;
  room_pct?: number; high_120?: number; min_room_pct?: number;
  dist50?: number; ret5?: number;
  avg_vol20?: number; min_avg_vol20?: number; min_price?: number;
  pos_1y?: number; room_life?: number; deep_value?: boolean;
}

/**
 * Per-stock REVERSAL quality grade. Weights come from a 7-year study of what
 * separates winning reversals from losers (rank-IC vs fwd-10d return):
 *   DEEP VALUE — near 1y-low + big lifetime headroom (70% win vs 63%) >
 *   deeper oversold / lower RSI (-0.253) > further below 50-SMA (-0.249) >
 *   sharper recent drop / ret5 (-0.211) > higher volume / rvol (+0.071).
 * Grade A reversals historically won ~82% vs ~58% for D.
 */
export function reversalGrade(checks: ReversalChecksShape | undefined): GradeResult {
  const c = checks || {};
  let pts = 0, max = 0;
  const factors: GradeResult['factors'] = [];

  // 1. DEEP VALUE — near its 1-year low with big room back to its lifetime high.
  //    Validated: deep-value reversals win ~70% vs ~63% for regular ones.
  {
    const dv = c.deep_value === true;
    const p = dv ? 25 : 0;
    pts += p; max += 25;
    const val = dv
      ? `yes${typeof c.room_life === 'number' ? ` · ${Math.round(c.room_life)}% headroom` : ''}`
      : 'no';
    factors.push({ label: 'Deep value', value: val, good: dv ? 'good' : 'weak' });
  }
  // 2. Oversold depth — lower RSI is better
  if (typeof c.rsi === 'number') {
    const r = c.rsi;
    const p = r < 20 ? 28 : r < 25 ? 18 : r < 30 ? 8 : 0;
    pts += p; max += 28;
    factors.push({ label: 'Oversold depth', value: `RSI ${r}`, good: p >= 18 ? 'good' : p >= 8 ? 'ok' : 'weak' });
  }
  // 3. Distance below 50-SMA — more stretched = more room to mean-revert up
  if (typeof c.dist50 === 'number') {
    const d = c.dist50; // negative
    const p = d <= -25 ? 22 : d <= -15 ? 14 : d <= -8 ? 6 : 0;
    pts += p; max += 22;
    factors.push({ label: 'Below 50-SMA', value: `${d}%`, good: p >= 14 ? 'good' : p >= 6 ? 'ok' : 'weak' });
  }
  // 4. Recent drop severity (capitulation) — sharper 5-day fall bounces harder
  if (typeof c.ret5 === 'number') {
    const x = c.ret5; // negative
    const p = x <= -12 ? 15 : x <= -7 ? 10 : x <= -3 ? 4 : 0;
    pts += p; max += 15;
    factors.push({ label: 'Capitulation (5d)', value: `${x}%`, good: p >= 10 ? 'good' : p >= 4 ? 'ok' : 'weak' });
  }
  // 5. Volume confirmation — higher rvol = stronger turn
  if (typeof c.rvol === 'number') {
    const v = c.rvol;
    const p = v >= 2.5 ? 10 : v >= 1.5 ? 6 : 0;
    pts += p; max += 10;
    factors.push({ label: 'Turn volume', value: `${v}×`, good: p >= 10 ? 'good' : p >= 6 ? 'ok' : 'weak' });
  }

  const score = max > 0 ? Math.round((pts / max) * 100) : 0;
  const grade: Grade = score >= 70 ? 'A' : score >= 50 ? 'B' : score >= 30 ? 'C' : 'D';
  return { grade, score, factors };
}
