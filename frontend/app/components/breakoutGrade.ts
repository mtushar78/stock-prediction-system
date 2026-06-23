import { BreakoutChecksShape } from './BreakoutCriteria';

export type Grade = 'A' | 'B' | 'C' | 'D';
export interface GradeResult {
  grade: Grade;
  score: number; // 0-100
  factors: { label: string; value: string; good: 'good' | 'ok' | 'weak' }[];
}

/**
 * Per-stock breakout QUALITY grade. Weights come from a 14-year study of what
 * separates winning breakouts from losers (rank-IC vs fwd-10d return):
 *   market regime/breadth (+0.138, strongest) > tighter base (+0.075) >
 *   lower volatility/ATR (+0.064) > non-extreme volume (+0.043).
 * Grade A breakouts historically won ~54% vs ~42% for D.
 */
export function breakoutGrade(checks: BreakoutChecksShape | undefined, breadth: number | null | undefined): GradeResult {
  const c = checks || {};
  let pts = 0, max = 0;
  const factors: GradeResult['factors'] = [];

  if (typeof breadth === 'number') {
    const p = breadth >= 65 ? 40 : breadth >= 45 ? 20 : 0;
    pts += p; max += 40;
    factors.push({ label: 'Market regime', value: `${breadth}% breadth`, good: p >= 40 ? 'good' : p >= 20 ? 'ok' : 'weak' });
  }
  if (typeof c.base_tight_pct === 'number') {
    const bt = c.base_tight_pct;
    const p = bt < 5 ? 25 : bt < 8 ? 15 : bt < 12 ? 5 : 0;
    pts += p; max += 25;
    factors.push({ label: 'Base tightness', value: `${bt}% / 10d`, good: p >= 15 ? 'good' : p >= 5 ? 'ok' : 'weak' });
  }
  if (typeof c.atr_pct === 'number') {
    const a = c.atr_pct;
    const p = a < 4 ? 20 : a < 6 ? 10 : 0;
    pts += p; max += 20;
    factors.push({ label: 'Volatility (ATR)', value: `${a}% of price`, good: p >= 20 ? 'good' : p >= 10 ? 'ok' : 'weak' });
  }
  if (typeof c.rvol === 'number') {
    const r = c.rvol;
    const p = (r >= 1.5 && r <= 3) ? 15 : (r <= 4.5 ? 8 : 0);
    pts += p; max += 15;
    factors.push({ label: 'Volume (not extreme)', value: `${r}×`, good: p >= 15 ? 'good' : p >= 8 ? 'ok' : 'weak' });
  }

  const score = max > 0 ? Math.round((pts / max) * 100) : 0;
  const grade: Grade = score >= 70 ? 'A' : score >= 50 ? 'B' : score >= 30 ? 'C' : 'D';
  return { grade, score, factors };
}

export const gradeColor = (g: Grade) =>
  g === 'A' ? 'bg-emerald-600 text-white'
  : g === 'B' ? 'bg-green-700 text-green-100'
  : g === 'C' ? 'bg-yellow-700 text-yellow-100'
  : 'bg-gray-600 text-gray-200';
