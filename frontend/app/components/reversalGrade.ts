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
}

/**
 * Per-stock REVERSAL quality grade. Weights come from a 7-year study of what
 * separates winning reversals from losers (rank-IC vs fwd-10d return):
 *   deeper oversold / lower RSI (-0.253, strongest) >
 *   further below 50-SMA (-0.249) > sharper recent drop / ret5 (-0.211) >
 *   higher volume / rvol (+0.071).
 * Grade A reversals historically won ~82% vs ~58% for D (+10.5% vs +3.3% avg).
 */
export function reversalGrade(checks: ReversalChecksShape | undefined): GradeResult {
  const c = checks || {};
  let pts = 0, max = 0;
  const factors: GradeResult['factors'] = [];

  // 1. Oversold depth (strongest signal) — lower RSI is better
  if (typeof c.rsi === 'number') {
    const r = c.rsi;
    const p = r < 20 ? 35 : r < 25 ? 22 : r < 30 ? 10 : 0;
    pts += p; max += 35;
    factors.push({ label: 'Oversold depth', value: `RSI ${r}`, good: p >= 22 ? 'good' : p >= 10 ? 'ok' : 'weak' });
  }
  // 2. Distance below 50-SMA — more stretched = more room to mean-revert up
  if (typeof c.dist50 === 'number') {
    const d = c.dist50; // negative
    const p = d <= -25 ? 30 : d <= -15 ? 20 : d <= -8 ? 8 : 0;
    pts += p; max += 30;
    factors.push({ label: 'Below 50-SMA', value: `${d}%`, good: p >= 20 ? 'good' : p >= 8 ? 'ok' : 'weak' });
  }
  // 3. Recent drop severity (capitulation) — sharper 5-day fall bounces harder
  if (typeof c.ret5 === 'number') {
    const x = c.ret5; // negative
    const p = x <= -12 ? 20 : x <= -7 ? 13 : x <= -3 ? 5 : 0;
    pts += p; max += 20;
    factors.push({ label: 'Capitulation (5d)', value: `${x}%`, good: p >= 13 ? 'good' : p >= 5 ? 'ok' : 'weak' });
  }
  // 4. Volume confirmation — higher rvol = stronger turn
  if (typeof c.rvol === 'number') {
    const v = c.rvol;
    const p = v >= 2.5 ? 15 : v >= 1.5 ? 9 : 0;
    pts += p; max += 15;
    factors.push({ label: 'Turn volume', value: `${v}×`, good: p >= 15 ? 'good' : p >= 9 ? 'ok' : 'weak' });
  }

  const score = max > 0 ? Math.round((pts / max) * 100) : 0;
  const grade: Grade = score >= 70 ? 'A' : score >= 50 ? 'B' : score >= 30 ? 'C' : 'D';
  return { grade, score, factors };
}
