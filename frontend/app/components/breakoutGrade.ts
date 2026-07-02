import { BreakoutChecksShape } from './BreakoutCriteria';

export type Grade = 'A' | 'B' | 'C' | 'D';
export interface GradeResult {
  grade: Grade;
  score: number; // 0-100
  factors: { label: string; value: string; good: 'good' | 'ok' | 'weak' }[];
}

/**
 * Per-stock breakout QUALITY grade — recalibrated by the 2026-07 cost audit
 * (docs/PROFITABILITY_AUDIT.md §3.3, breakout_grade_audit.py):
 *   - Market breadth is the ONLY factor with real predictive weight → 60 pts.
 *   - Non-extreme volume keeps a small weight → 15 pts.
 *   - Tight base and low ATR, isolated, were NEGATIVE net of costs — they are
 *     now shown for information but carry no points.
 * Honest expectation: even Grade A nets only ~+0.7%/trade (48% win) after the
 * 0.8% round-trip commission; D ≈ 0%. The grade orders, it does not rescue.
 */
export function breakoutGrade(checks: BreakoutChecksShape | undefined, breadth: number | null | undefined): GradeResult {
  const c = checks || {};
  let pts = 0, max = 0;
  const factors: GradeResult['factors'] = [];

  if (typeof breadth === 'number') {
    const p = breadth >= 65 ? 60 : breadth >= 55 ? 40 : breadth >= 45 ? 20 : 0;
    pts += p; max += 60;
    factors.push({ label: 'Market regime', value: `${breadth}% breadth`, good: p >= 40 ? 'good' : p >= 20 ? 'ok' : 'weak' });
  }
  if (typeof c.rvol === 'number') {
    const r = c.rvol;
    const p = (r >= 1.5 && r <= 3) ? 15 : (r <= 4.5 ? 8 : 0);
    pts += p; max += 15;
    factors.push({ label: 'Volume (not extreme)', value: `${r}×`, good: p >= 15 ? 'good' : p >= 8 ? 'ok' : 'weak' });
  }
  // Informational only (0 pts): measured net-negative as standalone filters.
  if (typeof c.base_tight_pct === 'number') {
    const bt = c.base_tight_pct;
    factors.push({ label: 'Base tightness (info)', value: `${bt}% / 10d`, good: bt < 8 ? 'good' : bt < 12 ? 'ok' : 'weak' });
  }
  if (typeof c.atr_pct === 'number') {
    const a = c.atr_pct;
    factors.push({ label: 'Volatility ATR (info)', value: `${a}% of price`, good: a < 4 ? 'good' : a < 6 ? 'ok' : 'weak' });
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
