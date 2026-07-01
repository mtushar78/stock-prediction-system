// Chart-pattern tutorial library.
//
// One lesson per Bulkowski pattern the engine detects: a plain-English story,
// a value/real-world analogy, how to spot it, concrete worked examples, how WE
// detect it, the measure rule, Bulkowski's real bull-market track record, how
// to trade it, common mistakes, and further-reading sources — plus a schematic
// spec that PatternSchematic renders as an annotated diagram.
//
// Content synthesised from strike.money, StockCharts ChartSchool, Thomas
// Bulkowski's thepatternsite.com, Investopedia, TrendSpider and others.
// Every detected pattern code maps to one of these via tutorialCodeFor().

export type SchematicPoint = { x: number; p: number }; // x,p in 0..1 (p: 1=high price, 0=low)
export type SchematicLine = { p: number; label: string; kind: 'neckline' | 'target' | 'support' | 'resistance' | 'stop' };
export type SchematicDot = { x: number; p: number; label: string };
export interface Schematic {
  points: SchematicPoint[];
  lines?: SchematicLine[];
  dots?: SchematicDot[];
  breakout?: { x: number; p: number };
  bias: 'bullish' | 'bearish' | 'neutral';
}

export interface TutorialSource {
  title: string;
  url: string;
}

export interface Tutorial {
  code: string;
  name: string;
  family: string;
  bias: 'bullish' | 'bearish' | 'neutral';
  oneLiner: string;
  story: string;
  analogy: string;
  identify: string[];
  examples: string[];
  howWeDetect: string;
  measureRule: string;
  stats: { avg: number | null; fail: number | null; meet: number | null; rank: number | null };
  trade: string[];
  gotchas: string[];
  sources: TutorialSource[];
  schematic: Schematic;
}

export function tutorialCodeFor(code: string): string {
  if (code.startsWith('double_bottom')) return 'double_bottom';
  if (code.startsWith('double_top')) return 'double_top';
  return code;
}

const W = (pts: [number, number][]): SchematicPoint[] => pts.map(([x, p]) => ({ x, p }));

export const TUTORIALS: Record<string, Tutorial> = {
  // ------------------------------------------------------------------ //
  double_bottom: {
    code: 'double_bottom',
    name: 'Double Bottom',
    family: 'Bullish reversals',
    bias: 'bullish',
    oneLiner: 'A falling stock tests the same floor twice, holds, and breaks out — the “W”.',
    story:
      'After a long slide, sellers push price to a low and it bounces. Sellers attack that same low a second time — but run out of ammunition (usually on lighter volume) and price holds. That failed second attempt proves the floor is solid, so buyers take control. When price finally closes above the peak between the two lows (the “neckline”), the reversal is confirmed and a new uptrend often begins.',
    analogy:
      'Like a value investor testing a stock’s floor price twice: when it refuses to go cheaper on the second dip, the bargain hunters pile in — the market has found what it thinks the stock is worth.',
    identify: [
      'A clear downtrend comes first.',
      'Two distinct lows at nearly the same price (within ~5%).',
      'A rally of at least ~10% between them — that peak is the neckline.',
      'Volume usually lighter on the second low than the first.',
      'A decisive CLOSE above the neckline confirms (not just a wick).',
    ],
    examples: [
      'Price falls to 100, bounces to 120, falls back to 101, then closes above 120 → the double bottom confirms. Target = 120 + (120 − 100) = 140.',
      'A penny stock bottoms at 8.0 and again at 8.2 with a 9.5 peak between; a close above 9.5 targets 9.5 + (9.5 − 8.0) = 11.0.',
    ],
    howWeDetect:
      'We extract swing pivots with a zigzag, then look for Low–High–Low where the two lows are within 5%, the middle peak is ≥10% above them, they’re 2–14 weeks apart, and the prior trend was down. It’s CONFIRMED once a close clears the peak. Adam (sharp/V) vs Eve (wide/rounded) bottoms are classified by width — Eve & Eve is the strongest variant.',
    measureRule:
      'Full height: neckline peak minus the lower bottom, added ABOVE the neckline. Low 100, neckline 120 → height 20 → target 140.',
    stats: { avg: 40, fail: 4, meet: 67, rank: 6 },
    trade: [
      'Enter on the close above the neckline, or on a pullback that retests it as new support.',
      'Stop just below the second low.',
      'Prefer a breakout on a volume spike.',
    ],
    gotchas: [
      'Unconfirmed “W”s fail most of the time — wait for the breakout close.',
      'A close back below the bottoms voids the pattern.',
      'Needs a real prior downtrend; in sideways chop it means little.',
    ],
    sources: [
      { title: 'Double Bottom Pattern — Strike.money', url: 'https://www.strike.money/technical-analysis/double-bottom-pattern' },
      { title: 'Double Bottoms & Tops — TrendSpider', url: 'https://trendspider.com/learning-center/chart-patterns-double-bottoms-and-tops/' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.85], [0.16, 0.12], [0.38, 0.58], [0.6, 0.14], [0.78, 0.62], [0.9, 0.85], [1, 0.96]]),
      lines: [{ p: 0.58, label: 'neckline', kind: 'neckline' }, { p: 0.96, label: 'target', kind: 'target' }],
      dots: [{ x: 0.16, p: 0.12, label: 'bottom 1' }, { x: 0.6, p: 0.14, label: 'bottom 2' }],
      breakout: { x: 0.78, p: 0.58 },
    },
  },

  double_top: {
    code: 'double_top',
    name: 'Double Top',
    family: 'Bearish reversals',
    bias: 'bearish',
    oneLiner: 'A rising stock hits the same ceiling twice, fails, and breaks down — the “M”.',
    story:
      'After a strong rally, price reaches a high and pulls back. Buyers try again but stall at the exact same high — demand is exhausted. That second rejection tells everyone the ceiling is real. When price closes below the valley between the two peaks (the neckline), trapped buyers bail and short-sellers pile in, accelerating the drop.',
    analogy:
      'Like a house that fails to sell above the same asking price twice — the market has spoken, and the price starts coming down.',
    identify: [
      'A clear uptrend comes first.',
      'Two distinct peaks at nearly the same price (within ~5%).',
      'A meaningful dip between them (~10%+) — that valley is the neckline.',
      'Volume often lighter on the second peak (fading demand).',
      'A decisive CLOSE below the neckline confirms.',
    ],
    examples: [
      'Price rises to 200, dips to 180, rallies back to 199, then closes below 180 → the double top confirms. Target = 180 − (200 − 180)/2 = 170.',
      'A bank stock tops at 45 and 44.5 with a 40 valley; a close below 40 targets 40 − (45 − 40)/2 ≈ 37.5.',
    ],
    howWeDetect:
      'We find High–Low–High swing pivots with the two highs within 5%, a ≥10% valley between, an uptrend into the pattern, and a confirming close below the valley.',
    measureRule:
      'HALF height (Bulkowski’s rule for tops — the full projection rarely fills): (peak − valley)/2, subtracted from the valley. Peak 200, valley 180 → half-height 10 → target 170.',
    stats: { avg: 18, fail: 11, meet: 73, rank: 2 },
    trade: [
      'Exit / avoid on the close below the valley (or a failed retest from below).',
      'Watch for underlying support that can stall the decline (a pullback).',
      'Confirm with rising volume on the breakdown.',
    ],
    gotchas: [
      'A new high above the peaks before confirming means it’s not a double top.',
      'Don’t act on the wick — wait for the neckline close.',
      'Peaks only days apart are less reliable than well-spaced ones.',
    ],
    sources: [
      { title: 'Double Top (M Pattern) — Strike.money', url: 'https://www.strike.money/technical-analysis/double-top-pattern' },
      { title: 'Double Top & Double Bottom — Britannica Money', url: 'https://www.britannica.com/money/double-top-double-bottom-pattern' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.15], [0.16, 0.88], [0.38, 0.42], [0.6, 0.86], [0.78, 0.38], [0.9, 0.15], [1, 0.05]]),
      lines: [{ p: 0.42, label: 'neckline', kind: 'neckline' }, { p: 0.2, label: 'target', kind: 'target' }],
      dots: [{ x: 0.16, p: 0.88, label: 'top 1' }, { x: 0.6, p: 0.86, label: 'top 2' }],
      breakout: { x: 0.78, p: 0.42 },
    },
  },

  triple_bottom: {
    code: 'triple_bottom',
    name: 'Triple Bottom',
    family: 'Bullish reversals',
    bias: 'bullish',
    oneLiner: 'Price tests the same floor three times and holds, then breaks out — a stubborn double bottom.',
    story:
      'Sellers attack the same support three separate times and fail each time. Every failed attempt proves buyers are defending that price, and sellers grow exhausted. By the third bounce, confidence shifts firmly to the bulls. A close above the resistance line joining the in-between peaks (the neckline) confirms buying has overwhelmed selling.',
    analogy:
      'Like a dam holding back the flood through three storms — after the third failed surge, everyone trusts the wall and builds on top of it.',
    identify: [
      'A downtrend or long base comes first.',
      'Three lows at roughly the same level (within ~3.5%).',
      'Two moderate peaks between them define the neckline.',
      'Usually takes weeks to form; volume ideally rises on the breakout.',
      'Confirmed by a close above the neckline (the highest interior peak).',
    ],
    examples: [
      'Lows at 50, 51, 50 with peaks near 60; a close above 60 confirms. Target = 60 + (60 − 50) = 70.',
      'A stock holds 100 three times with a 112 peak; break above 112 targets 112 + (112 − 100) = 124.',
    ],
    howWeDetect:
      'We require three same-level lows (within 3.5%), a base ≥20 bars wide with real depth, the centre NOT the lowest (that would be a head-and-shoulders), and a confirming close above the highest peak.',
    measureRule: 'Full height: highest peak minus lowest low, added above the breakout. Bottom 50, neckline 60 → target 70.',
    stats: { avg: 37, fail: 4, meet: 64, rank: 7 },
    trade: [
      'Buy the breakout close; stop below the lowest low.',
      'A higher third valley is a bullish tell.',
      'Wait for the breakout — it isn’t valid until price clears the neckline.',
    ],
    gotchas: [
      'Three descending lows is NOT a triple bottom — it’s still a downtrend.',
      'Easily confused with double bottoms or H&S — count the touches.',
      'It’s rare; don’t force-fit it.',
    ],
    sources: [
      { title: 'Triple Bottoms & Tops — TrendSpider', url: 'https://trendspider.com/learning-center/chart-patterns-triple-bottoms-and-tops/' },
      { title: 'Triple Bottom Pattern — Strike.money', url: 'https://www.strike.money/technical-analysis/triple-bottom-pattern' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.8], [0.14, 0.14], [0.28, 0.5], [0.42, 0.15], [0.56, 0.5], [0.7, 0.14], [0.84, 0.55], [0.94, 0.85], [1, 0.95]]),
      lines: [{ p: 0.5, label: 'neckline', kind: 'neckline' }, { p: 0.9, label: 'target', kind: 'target' }],
      dots: [{ x: 0.14, p: 0.14, label: '1' }, { x: 0.42, p: 0.15, label: '2' }, { x: 0.7, p: 0.14, label: '3' }],
      breakout: { x: 0.84, p: 0.5 },
    },
  },

  triple_top: {
    code: 'triple_top',
    name: 'Triple Top',
    family: 'Bearish reversals',
    bias: 'bearish',
    oneLiner: 'Price tests the same ceiling three times and fails, then breaks down — a stubborn double top.',
    story:
      'Buyers charge the same resistance three times and get rejected each time. Every failed push proves sellers are defending that price and that demand is drying up. After the third rejection, sentiment flips bearish. When price closes below the support line joining the in-between troughs (the neckline), trapped buyers exit and sellers take over.',
    analogy:
      'Like a high-jumper who knocks the same bar off three times — after the third miss, the crowd stops believing they’ll clear it.',
    identify: [
      'An uptrend comes first.',
      'Three peaks at roughly the same level (within ~3.5%).',
      'Two moderate troughs between them define the neckline.',
      'Usually takes weeks; volume ideally rises on the breakdown.',
      'Confirmed by a close below the neckline (the lowest interior valley).',
    ],
    examples: [
      'Peaks at 300, 299, 300 with troughs near 280; a close below 280 confirms. Target = 280 − (300 − 280) = 260.',
      'A stock is rejected at 50 three times with a 45 valley; break below 45 targets 45 − (50 − 45) = 40.',
    ],
    howWeDetect:
      'Three same-level highs (within 3.5%), centre not the highest, span ≥20 bars, and a confirming close below the lowest valley.',
    measureRule:
      'Full height (NOT the double-top half rule): highest high minus lowest valley, subtracted from the breakout. Only ~40% reach it, so treat the target as a ceiling on expectations.',
    stats: { avg: 19, fail: 10, meet: 40, rank: 7 },
    trade: [
      'Exit / short on the breakdown close; bank profits along the way (target fills only ~40%).',
      'Stop just above the peak level.',
      'Aim for at least 2:1 reward-to-risk.',
    ],
    gotchas: [
      'Rising highs = broadening top, not a triple top.',
      'Middle peak higher than the others = head-and-shoulders, not a triple top.',
      'If price reclaims the peaks, the pattern has failed.',
    ],
    sources: [
      { title: 'Triple Bottoms & Tops — TrendSpider', url: 'https://trendspider.com/learning-center/chart-patterns-triple-bottoms-and-tops/' },
      { title: 'Triple Top & Bottom — TMGM Academy', url: 'https://www.tmgm.com/en/academy/trading-academy/triple-top-and-triple-bottom-chart-pattern' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.2], [0.14, 0.86], [0.28, 0.5], [0.42, 0.85], [0.56, 0.5], [0.7, 0.86], [0.84, 0.45], [0.94, 0.15], [1, 0.05]]),
      lines: [{ p: 0.5, label: 'neckline', kind: 'neckline' }, { p: 0.12, label: 'target', kind: 'target' }],
      dots: [{ x: 0.14, p: 0.86, label: '1' }, { x: 0.42, p: 0.85, label: '2' }, { x: 0.7, p: 0.86, label: '3' }],
      breakout: { x: 0.84, p: 0.5 },
    },
  },

  hs_bottom: {
    code: 'hs_bottom',
    name: 'Head-and-Shoulders Bottom',
    family: 'Bullish reversals',
    bias: 'bullish',
    oneLiner: 'Three dips — a low shoulder, a lower head, a higher shoulder — signalling a downtrend is ending.',
    story:
      'Sellers push to a low (left shoulder), bounce, then drive even lower (the head). But the next dip stops higher (right shoulder) — sellers are running out of ammo. Buyers step in at rising lows, and when price breaks above the “neckline” joining the two bounce-highs, the trend flips from down to up.',
    analogy:
      'Like a ball bouncing in a bowl — each bounce loses downward energy until it finally rolls up and over the rim.',
    identify: [
      'Prior downtrend into the pattern.',
      'Three troughs: left shoulder, deeper head, higher right shoulder.',
      'The two shoulders roughly level in price and time.',
      'Neckline drawn across the two rebound highs (may slope).',
      'Confirmation = a close ABOVE the neckline, ideally on rising volume.',
    ],
    examples: [
      'Falls to 50 (left shoulder), rebounds to 60, drops to 44 (head), rebounds to 60, then dips only to 51 (right shoulder). Close above 60 → breakout. Height = 60 − 44 = 16 → target 76.',
      'A share bottoms 20 / 16 / 21 with a 25 neckline; close above 25 targets 25 + (25 − 16) = 34.',
    ],
    howWeDetect:
      'We find Low–High–Low–High–Low pivots where the centre low is ≥5% below the shoulders, shoulders are within 5% and roughly time-symmetric, the neckline peaks are reasonably level, and price closes above the (projected) neckline.',
    measureRule: 'Full height: neckline minus head low, added above the breakout. Neckline 60, head 44 → height 16 → target 76.',
    stats: { avg: 38, fail: 3, meet: 74, rank: 7 },
    trade: [
      'Enter on a daily close above the neckline (a second close filters fakeouts).',
      'Stop just below the right shoulder.',
      'A pullback to the neckline that holds is a lower-risk entry.',
    ],
    gotchas: [
      'Don’t buy before the neckline actually breaks.',
      'If the head isn’t clearly the lowest, it’s a triple bottom instead.',
      'Chasing after price has already run most of the way to target.',
    ],
    sources: [
      { title: 'Inverse Head & Shoulders — Strike.money', url: 'https://www.strike.money/technical-analysis/inverse-head-and-shoulders' },
      { title: 'Head-and-Shoulders — Bulkowski', url: 'https://www.thepatternsite.com/HSTExplained.html' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.7], [0.12, 0.32], [0.24, 0.55], [0.4, 0.1], [0.56, 0.55], [0.72, 0.34], [0.85, 0.6], [0.95, 0.82], [1, 0.92]]),
      lines: [{ p: 0.55, label: 'neckline', kind: 'neckline' }, { p: 0.88, label: 'target', kind: 'target' }],
      dots: [{ x: 0.12, p: 0.32, label: 'L. shoulder' }, { x: 0.4, p: 0.1, label: 'head' }, { x: 0.72, p: 0.34, label: 'R. shoulder' }],
      breakout: { x: 0.85, p: 0.55 },
    },
  },

  hs_top: {
    code: 'hs_top',
    name: 'Head-and-Shoulders Top',
    family: 'Bearish reversals',
    bias: 'bearish',
    oneLiner: 'Three peaks — a shoulder, a higher head, a lower shoulder — warning an uptrend is topping.',
    story:
      'Buyers push to a high (left shoulder), pull back, then surge to a new high (the head). But the next rally fails lower (right shoulder) — buyers can no longer make new highs. Each pullback finds the “neckline.” When price closes below it, sellers take control and a decline begins.',
    analogy:
      'Like a rocket losing thrust — one big burst, a smaller one, then it stalls and falls back to earth.',
    identify: [
      'Prior uptrend into the pattern.',
      'Three peaks: left shoulder, higher head, lower right shoulder.',
      'The two shoulders roughly level in price.',
      'Neckline across the two pullback lows (the “armpits”).',
      'Confirmation = a close BELOW the neckline.',
    ],
    examples: [
      'Peaks 100 (left), dips 90, spikes 110 (head), dips 90, rallies only to 101 (right). Close below 90 → breakdown. Height = 110 − 90 = 20 → target 70.',
      'A stock tops 30 / 34 / 29 with a 26 neckline; close below 26 targets 26 − (34 − 26) = 18.',
    ],
    howWeDetect:
      'High–Low–High–Low–High pivots with the centre high clearly above the shoulders, shoulders within 5% and time-symmetric, a level-ish neckline, and a confirming close below it. Bulkowski’s #1-ranked bearish pattern.',
    measureRule: 'Full height: head high minus neckline, subtracted from the breakout. Head 110, neckline 90 → height 20 → target 70.',
    stats: { avg: 22, fail: 4, meet: 55, rank: 1 },
    trade: [
      'Exit / short on a close below the neckline.',
      'Stop just above the higher of the two neckline troughs.',
      'A weak pullback to the neckline that fails is a clean short entry.',
    ],
    gotchas: [
      'Don’t act on the shape before the neckline actually breaks.',
      'You need three distinct peaks with the middle highest.',
      'A strong close back above the neckline often signals a failed pattern.',
    ],
    sources: [
      { title: 'Head-and-Shoulders Tops — Bulkowski', url: 'https://www.thepatternsite.com/hst.html' },
      { title: 'The Measure Rule — Bulkowski', url: 'https://thepatternsite.com/measure.html' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.3], [0.12, 0.68], [0.24, 0.45], [0.4, 0.9], [0.56, 0.45], [0.72, 0.66], [0.85, 0.4], [0.95, 0.18], [1, 0.08]]),
      lines: [{ p: 0.45, label: 'neckline', kind: 'neckline' }, { p: 0.12, label: 'target', kind: 'target' }],
      dots: [{ x: 0.12, p: 0.68, label: 'L. shoulder' }, { x: 0.4, p: 0.9, label: 'head' }, { x: 0.72, p: 0.66, label: 'R. shoulder' }],
      breakout: { x: 0.85, p: 0.45 },
    },
  },

  three_rising_valleys: {
    code: 'three_rising_valleys',
    name: 'Three Rising Valleys',
    family: 'Bullish reversals',
    bias: 'bullish',
    oneLiner: 'Three successively higher dips — a staircase up as buyers gain strength.',
    story:
      'Price pulls back three times, but each dip bottoms higher than the last. Buyers are stepping in earlier and more aggressively each time, refusing to let price fall as far. Since every up-move must start with higher lows, this flags a fresh advance once price clears the pattern’s high.',
    analogy:
      'Like bargain hunters raising their limit orders — first they’ll buy at 50, then only get filled at 55, then 60 — rising demand chasing a stock they believe is cheap.',
    identify: [
      'Three distinct valleys, each bottoming above the prior one.',
      'Valleys look similar in size — all narrow or all wide, not mixed.',
      'Usually within a rising or recovering trend.',
      'Confirmation = a close ABOVE the highest peak in the pattern.',
      'Not a triple bottom (those lows are level, not rising).',
    ],
    examples: [
      'Valleys bottom 30, 34, 38; tallest peak 45. Close above 45 confirms. Height = 45 − 30 = 15 → target 60.',
      'A stock dips 12 / 14 / 16 with an 18 peak; break above 18 targets 18 + (18 − 12) = 24.',
    ],
    howWeDetect:
      'Three strictly rising swing lows spanning ≥25 bars, each leg ≥3%, ≥8% end-to-end, with a confirming close above the pattern high.',
    measureRule: 'Full height: highest peak minus lowest valley, added to the breakout. Peak 45, low 30 → target 60.',
    stats: { avg: 41, fail: 5, meet: 58, rank: 4 },
    trade: [
      'Enter on a close above the pattern’s highest peak.',
      'Momentum names work best bought near new highs.',
      'Stop slightly below the most recent valley.',
    ],
    gotchas: [
      'Don’t confuse with a rising wedge (which converges and usually breaks down).',
      'Forcing it when valleys are wildly different sizes.',
      'Entering before the highest peak is cleared.',
    ],
    sources: [
      { title: 'Three Rising Valleys — Bulkowski', url: 'https://www.thepatternsite.com/3rv.html' },
      { title: 'Three Rising Valleys — Fidelity', url: 'https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/three-rising-valleys' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.5], [0.12, 0.2], [0.26, 0.45], [0.4, 0.32], [0.54, 0.6], [0.68, 0.45], [0.8, 0.72], [0.9, 0.85], [1, 0.95]]),
      lines: [{ p: 0.72, label: 'breakout', kind: 'neckline' }, { p: 0.95, label: 'target', kind: 'target' }],
      dots: [{ x: 0.12, p: 0.2, label: '1' }, { x: 0.4, p: 0.32, label: '2' }, { x: 0.68, p: 0.45, label: '3' }],
      breakout: { x: 0.8, p: 0.72 },
    },
  },

  three_falling_peaks: {
    code: 'three_falling_peaks',
    name: 'Three Falling Peaks',
    family: 'Bearish reversals',
    bias: 'bearish',
    oneLiner: 'Three successively lower peaks — a staircase down as sellers take control.',
    story:
      'Price rallies three times, but each peak tops lower than the last. Buyers are getting weaker — each attempt to push higher runs out of steam sooner. This rolling-over often appears at the end of an uptrend. Once price breaks below the lowest dip between the peaks, a decline is expected.',
    analogy:
      'Like sellers cutting their asking price with every attempt: 100, then 92, then 85 — supply overwhelming a fading bid.',
    identify: [
      'Three distinct peaks, each topping below the prior one.',
      'Peaks look similar in size and shape.',
      'Usually after a rise, as the trend stalls.',
      'Confirmation = a close BELOW the lowest valley between the peaks.',
      'Not a triple top (those peaks are level, not falling).',
    ],
    examples: [
      'Peaks 70, 66, 62; lowest valley 55. Close below 55 confirms. Height = 70 − 55 = 15 → target 40.',
      'A stock tops 40 / 37 / 34 with a 30 valley; break below 30 targets 30 − (40 − 30) = 20.',
    ],
    howWeDetect:
      'Three strictly falling swing highs spanning ≥25 bars, each leg ≥3%, with a confirming close below the pattern low. Only ~33% reach target — get in early.',
    measureRule: 'Full height: highest peak minus lowest valley, subtracted from the breakout. Peak 70, valley 55 → target 40.',
    stats: { avg: 17, fail: 12, meet: 33, rank: 8 },
    trade: [
      'Enter short on a close below the lowest valley.',
      'Act early — the target fills only a third of the time; bank profits fast.',
      'Stop slightly above the third peak.',
    ],
    gotchas: [
      'Don’t mistake a descending triangle or H&S top for this.',
      'Pullbacks after the breakdown are common — don’t panic-cover on the first bounce.',
      'Acting before the lowest valley is broken.',
    ],
    sources: [
      { title: 'Three Falling Peaks — Bulkowski', url: 'https://thepatternsite.com/3fp.html' },
      { title: 'Pattern Pairs: 3 Falling Peaks — Bulkowski', url: 'https://thepatternsite.com/pp3FP.html' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.5], [0.12, 0.8], [0.26, 0.55], [0.4, 0.68], [0.54, 0.4], [0.68, 0.55], [0.8, 0.28], [0.9, 0.15], [1, 0.05]]),
      lines: [{ p: 0.28, label: 'breakout', kind: 'neckline' }, { p: 0.05, label: 'target', kind: 'target' }],
      dots: [{ x: 0.12, p: 0.8, label: '1' }, { x: 0.4, p: 0.68, label: '2' }, { x: 0.68, p: 0.55, label: '3' }],
      breakout: { x: 0.8, p: 0.28 },
    },
  },

  ascending_triangle: {
    code: 'ascending_triangle',
    name: 'Ascending Triangle',
    family: 'Continuation / bilateral',
    bias: 'bullish',
    oneLiner: 'Flat ceiling of equal highs with a rising floor of higher lows — usually breaks up.',
    story:
      'Buyers step in earlier and earlier, lifting the lows, while a wall of sellers dumps shares every time price hits the same ceiling. Each bounce is met by more eager buyers, so the lows climb and the range squeezes shut. Eventually the sellers run out of stock and price pops through the ceiling.',
    analogy:
      'Like water rising in a tank against a lid — the lid holds until the pressure finally blows it off.',
    identify: [
      'Flat horizontal top (resistance) touched 2+ times at the same price.',
      'Rising bottom line connecting higher lows.',
      'The two lines converge to the right.',
      'Volume usually shrinks as the range tightens.',
      'Breakout = a candle that CLOSES above the flat top.',
    ],
    examples: [
      'Stock stalls at 100 three times; lows rise 92 → 95 → 98. Close above 100 on heavy volume → target 100 + (100 − 92) = 108. Stop near 97.',
      'A share caps at 25 with lows 22 → 23 → 24; break above 25 targets 25 + (25 − 22) = 28.',
    ],
    howWeDetect:
      'We fit trendlines to recent swing highs/lows; a near-flat top (|slope|<0.1%/bar) with a clearly rising bottom classifies as ascending. Height = flat top − lowest low.',
    measureRule: 'Add the height (top − lowest low) to the breakout. Top 100, low 92 → height 8 → target 108.',
    stats: { avg: 35, fail: 13, meet: 75, rank: 17 },
    trade: [
      'Wait for a CLOSE above the ceiling, not just a poke.',
      'Look for volume to jump on the breakout.',
      'Stop just below the rising support line; a pullback to the old ceiling is a second entry.',
    ],
    gotchas: [
      '~30% break DOWN — wait for the actual close.',
      'False breakout: price pops above, then falls back inside.',
      'Too few touches (only 1 per line) isn’t a real pattern yet.',
    ],
    sources: [
      { title: 'Ascending Triangle — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/ascending-triangle' },
      { title: 'Ascending Triangle — Bulkowski', url: 'https://thepatternsite.com/at.html' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.3], [0.14, 0.72], [0.28, 0.4], [0.42, 0.74], [0.56, 0.52], [0.7, 0.73], [0.84, 0.9], [1, 0.98]]),
      lines: [{ p: 0.74, label: 'resistance', kind: 'resistance' }, { p: 0.98, label: 'target', kind: 'target' }],
      breakout: { x: 0.84, p: 0.74 },
    },
  },

  descending_triangle: {
    code: 'descending_triangle',
    name: 'Descending Triangle',
    family: 'Continuation / bilateral',
    bias: 'bearish',
    oneLiner: 'Flat floor of equal lows with a falling ceiling of lower highs — often breaks down.',
    story:
      'Sellers grow impatient, capping each rally lower, while a stubborn floor of buyers defends the same price again and again. The rallies get weaker and the range tightens against the floor. Each retest chips away at the buyers’ ammunition. When they give up, price drops through the floor.',
    analogy:
      'Like a heavy hammer tapping a crack repeatedly — the surface holds, holds, then suddenly splits.',
    identify: [
      'Flat horizontal bottom (support) touched 2+ times.',
      'Falling top line connecting lower highs.',
      'The two lines converge to the right.',
      'Volume typically fades during the squeeze.',
      'Breakdown = a candle that CLOSES below the flat floor.',
    ],
    examples: [
      'Floor holds at 70 three times; highs drop 80 → 77 → 73. Close below 70 on rising volume → target 70 − (80 − 70) = 60. Stop near 73.',
      'A stock defends 15 while highs fall 18 → 17 → 16; break below 15 targets 15 − (18 − 15) = 12.',
    ],
    howWeDetect:
      'A near-flat bottom with a clearly falling top classifies as descending. Note: in a bull market the less-common UP break is actually the stronger trade.',
    measureRule: 'Subtract the height (highest high − flat floor) from the breakdown. High 80, floor 70 → height 10 → target 60.',
    stats: { avg: 16, fail: 16, meet: 54, rank: 10 },
    trade: [
      'Wait for a CLOSE below the floor before shorting or exiting.',
      'Confirm with a pickup in volume; stop just above the falling line.',
      'Respect the close — this pattern can bust and rocket upward.',
    ],
    gotchas: [
      'Direction isn’t guaranteed — a firm floor sometimes breaks up.',
      'An intraday wick below the floor that closes back above it isn’t a break.',
      'Works best confirming an existing downtrend.',
    ],
    sources: [
      { title: 'Descending Triangle — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/descending-triangle' },
      { title: 'Descending Triangle — Bulkowski', url: 'https://thepatternsite.com/dt.html' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.7], [0.14, 0.28], [0.28, 0.6], [0.42, 0.26], [0.56, 0.48], [0.7, 0.27], [0.84, 0.1], [1, 0.03]]),
      lines: [{ p: 0.27, label: 'support', kind: 'support' }, { p: 0.04, label: 'target', kind: 'target' }],
      breakout: { x: 0.84, p: 0.27 },
    },
  },

  symmetrical_triangle: {
    code: 'symmetrical_triangle',
    name: 'Symmetrical Triangle',
    family: 'Continuation / bilateral',
    bias: 'neutral',
    oneLiner: 'Lower highs and higher lows coil to a point, then break either way — usually with the prior trend.',
    story:
      'Buyers and sellers reach a standoff. Sellers cap each rally a little lower while buyers lift each dip a little higher, so the range coils tighter toward a tip (the “apex”). Trading goes quiet as everyone waits. The coil stores energy like a compressed spring; when one side wins, price bursts out — most often continuing the trend that came before.',
    analogy:
      'A coiling spring or a pressure cooker — the tighter it winds, the more forceful the eventual release.',
    identify: [
      'Upper line slopes down (lower highs); lower line slopes up (higher lows).',
      'Both lines lean toward each other, meeting at the apex.',
      'At least 2 touches on each line (4+ total).',
      'Volume steadily dries up into the apex.',
      'Breakout = a close beyond either line, best 50–75% of the way to the apex.',
    ],
    examples: [
      'Price coils between falling highs (108 → 104) and rising lows (92 → 96). Widest height = 108 − 92 = 16. Close above 105 → target 105 + 16 = 121. Stop near 96.',
      'A stock narrows between 52/48; break below 48 targets 48 − 4 = 44.',
    ],
    howWeDetect:
      'Both trendlines slope toward each other (top down, bottom up). We stay neutral until a rail is broken, then set direction and target from the break.',
    measureRule: 'Add/subtract the widest height at the breakout rail. Widest 16, up-break at 105 → target 121.',
    stats: { avg: 31, fail: 9, meet: 66, rank: 16 },
    trade: [
      'Don’t guess direction early — wait for the close outside a line.',
      'Volume expansion on the break adds confidence; stop on the opposite rail.',
      'Breakouts too close to the apex often fizzle.',
    ],
    gotchas: [
      'Premature entry inside the coil — either line can give way.',
      'Chasing a low-volume breakout that quickly reverses (a fakeout).',
      'Drawing sloppy lines to force a triangle that isn’t there.',
    ],
    sources: [
      { title: 'Symmetrical Triangle — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/symmetrical-triangle' },
      { title: 'Symmetrical Triangle — TradingSim', url: 'https://www.tradingsim.com/blog/symmetrical-triangle' },
    ],
    schematic: {
      bias: 'neutral',
      points: W([[0, 0.2], [0.14, 0.82], [0.3, 0.32], [0.46, 0.72], [0.62, 0.42], [0.78, 0.62], [0.9, 0.85], [1, 0.95]]),
      lines: [{ p: 0.62, label: 'upper rail', kind: 'resistance' }, { p: 0.42, label: 'lower rail', kind: 'support' }],
      breakout: { x: 0.78, p: 0.62 },
    },
  },

  rectangle_top: {
    code: 'rectangle_top',
    name: 'Rectangle Top',
    family: 'Continuation / bilateral',
    bias: 'neutral',
    oneLiner: 'A flat sideways box after a rise — usually breaks up to continue the uptrend.',
    story:
      'After climbing, price pauses and bounces between a flat ceiling and a flat floor, buyers and sellers evenly matched. It’s often just the uptrend catching its breath. Because the earlier trend was up, the box most often breaks out the top — though a break below the floor can flip it bearish.',
    analogy:
      'A ball bouncing between the floor and ceiling of a room until someone opens the roof.',
    identify: [
      'Flat, roughly parallel resistance (top) and support (bottom).',
      'Price touches each line at least twice (ideally 3 on one).',
      'Highs and lows alternate, filling the box.',
      'Forms after an up-move (that’s what makes it a “top” rectangle).',
      'Breakout = a CLOSE beyond either rail.',
    ],
    examples: [
      'Price oscillates 45–50 for weeks. Height = 5. Close above 50 on rising volume → target 55. Stop near 48.',
      'A stock ranges 100–110; break above 110 targets 110 + 10 = 120.',
    ],
    howWeDetect:
      'Both trendlines near-flat with an uptrend into the range → rectangle top. Neutral until a rail breaks.',
    measureRule: 'Add/subtract the box height at the breakout. Box 45–50 → height 5 → up-target 55.',
    stats: { avg: 39, fail: 9, meet: 80, rank: 12 },
    trade: [
      'Wait for a decisive CLOSE outside the box, not just a wick.',
      'Confirm with a volume jump; taller boxes give bigger moves.',
      'A “partial rise” that stalls below the top often precedes a down-break; a partial decline often precedes an up-break.',
    ],
    gotchas: [
      'Trading every bounce and getting whipsawed inside the range.',
      'Treating a wick past the ceiling as a breakout before it closes there.',
      'Assuming up is guaranteed — it can break down.',
    ],
    sources: [
      { title: 'Rectangle Tops — Bulkowski', url: 'https://thepatternsite.com/recttops.html' },
      { title: 'Rectangle — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/rectangle' },
    ],
    schematic: {
      bias: 'neutral',
      points: W([[0, 0.2], [0.12, 0.75], [0.26, 0.3], [0.4, 0.74], [0.54, 0.3], [0.68, 0.74], [0.82, 0.32], [0.9, 0.78], [1, 0.92]]),
      lines: [{ p: 0.75, label: 'resistance', kind: 'resistance' }, { p: 0.3, label: 'support', kind: 'support' }],
      breakout: { x: 0.9, p: 0.75 },
    },
  },

  rectangle_bottom: {
    code: 'rectangle_bottom',
    name: 'Rectangle Bottom',
    family: 'Continuation / bilateral',
    bias: 'neutral',
    oneLiner: 'A flat sideways box after a decline — often breaks down, but can mark a base.',
    story:
      'After falling, price stalls and trades flat between a ceiling and a floor, buyers and sellers deadlocked. It’s the mirror of the rectangle top: the same box, but it appears after a drop, so the resting trend is down. Sellers usually regain control — but a rectangle bottom can also be where buyers quietly take over, so an up-break is a real possibility.',
    analogy:
      'A pause on a downhill staircase — a flat landing before the next step down (or sometimes the bottom of the stairs).',
    identify: [
      'Flat, roughly parallel support (bottom) and resistance (top).',
      'Each line touched at least twice (ideally 3 on one).',
      'Highs and lows alternate across the box.',
      'Forms after a down-move (that’s what makes it a “bottom” rectangle).',
      'Breakout = a CLOSE beyond either rail.',
    ],
    examples: [
      'Price ranges 25–30 for weeks. Height = 5. Close below 25 on heavy volume → target 20. Stop near 27.',
      'An up-break instead: close above 30 targets 30 + 5 = 35 (the reversal case, ~85% hit target).',
    ],
    howWeDetect:
      'Two near-flat lines with a downtrend into the range → rectangle bottom.',
    measureRule: 'Add/subtract the box height at the breakout. Box 25–30 → height 5 → down-target 20.',
    stats: { avg: 46, fail: 10, meet: 85, rank: 11 },
    trade: [
      'Wait for a CLOSE beyond a rail; up-break on rising volume is a high-reliability long.',
      'Confirm with volume; stop just inside the opposite rail.',
      'Stay alert for an upside bust that flips the box bullish.',
    ],
    gotchas: [
      'Assuming it must fall — an upside breakout can be strong.',
      'Reacting to an intraday poke that closes back inside.',
      'Over-trading the choppy bounces within the range.',
    ],
    sources: [
      { title: 'Rectangle — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/rectangle' },
      { title: 'Rectangle Pattern — Strike.money', url: 'https://www.strike.money/technical-analysis/rectangle-pattern' },
    ],
    schematic: {
      bias: 'neutral',
      points: W([[0, 0.8], [0.12, 0.28], [0.26, 0.72], [0.4, 0.28], [0.54, 0.7], [0.68, 0.28], [0.82, 0.72], [0.9, 0.85], [1, 0.95]]),
      lines: [{ p: 0.72, label: 'resistance', kind: 'resistance' }, { p: 0.28, label: 'support', kind: 'support' }],
      breakout: { x: 0.9, p: 0.72 },
    },
  },

  falling_wedge: {
    code: 'falling_wedge',
    name: 'Falling Wedge',
    family: 'Continuation / bilateral',
    bias: 'bullish',
    oneLiner: 'Price drifts lower between two down-sloping lines that squeeze together — usually breaks UP.',
    story:
      'Sellers keep marking price down, but each drop is shallower and the range narrows — lower highs and lower lows converging. That shrinking range shows selling pressure fading even as price still slips. Sellers are getting tired, so the falling wedge most often breaks up through the upper line, recovering toward the top of the wedge.',
    analogy:
      'A ball bouncing lower and lower with less energy each time — the bounces are dying out, and the next real push is back up.',
    identify: [
      'Two lines both slope down and converge (top usually steeper).',
      'Several touches on each line (aim for ~5 total).',
      'Each new low is only slightly lower — selling weakening.',
      'Volume contracts through the pattern, then swells on the up-break.',
      'Confirm with a close ABOVE the upper line.',
    ],
    examples: [
      'A stock falls 60 → 45. Highs drop 58 → 54 → 51; lows drop 47 → 46 → 45.5. Close above 52 → up-target ≈ the wedge’s highest high (58).',
      'A share coils down from 30 to 25; close above the upper rail targets the pre-wedge high near 30.',
    ],
    howWeDetect:
      'Both lines negative-sloped with the top steeper (more negative). Up-target is set to the wedge’s highest high (not breakout+height) — Bulkowski’s “easy objective.”',
    measureRule: 'Up-target = the highest high inside the wedge.',
    stats: { avg: 32, fail: 11, meet: 70, rank: 20 },
    trade: [
      'Buy on a confirmed close above the upper line, ideally with a volume jump.',
      'Stop just below the last low.',
      'Reversals of a prior downtrend perform best.',
    ],
    gotchas: [
      'It looks bearish (price falling) but usually resolves UP — the mirror trap of the rising wedge.',
      '~27% dip below the lower line first, then reverse up — don’t panic on the false break.',
      'A weak, low-volume break can fail — require conviction.',
    ],
    sources: [
      { title: 'Wedge Patterns — The Trading Bible', url: 'https://thetradingbible.com/wedge-patterns-in-technical-analysis' },
      { title: 'Falling Wedge — Bulkowski', url: 'https://thepatternsite.com/fallwedge.html' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.9], [0.14, 0.55], [0.3, 0.72], [0.46, 0.42], [0.62, 0.58], [0.74, 0.35], [0.86, 0.75], [1, 0.92]]),
      lines: [{ p: 0.9, label: 'target = highest high', kind: 'target' }],
      breakout: { x: 0.86, p: 0.55 },
    },
  },

  rising_wedge: {
    code: 'rising_wedge',
    name: 'Rising Wedge',
    family: 'Continuation / bilateral',
    bias: 'bearish',
    oneLiner: 'Price grinds higher between two up-sloping lines that squeeze together — usually breaks DOWN.',
    story:
      'Buyers keep pushing price to new highs, but each push is weaker and the gains get smaller — highs and lows both rise, yet converge. That narrowing means momentum is draining even as price ticks up. It’s a rally running out of gas, so the wedge most often breaks down through the lower line.',
    analogy:
      'A car still rolling uphill but with the engine sputtering — forward motion continues right up until it stalls and rolls back.',
    identify: [
      'Two lines both slope up and get closer together (converging).',
      'Price touches each line several times (~5 total).',
      'Each new high is only slightly higher — weakening momentum.',
      'Volume usually shrinks as the wedge forms.',
      'Confirm with a decisive close BELOW the lower line.',
    ],
    examples: [
      'A stock climbs 100 → 130. Highs rise 128 → 131 → 133 (barely); lows rise 120 → 125 → 128, lines pinch near 132. Close below 127 → down-target ≈ the wedge’s lowest low (120).',
      'A share wedges up 20 → 24; a close below the lower rail targets the pre-wedge low near 20.',
    ],
    howWeDetect:
      'Both lines positive-sloped, converging (bottom steeper). Down-target is set to the wedge’s lowest low (not breakout−height). Bulkowski’s worst-performing pattern — trade carefully.',
    measureRule: 'Down-target = the lowest low inside the wedge.',
    stats: { avg: 14, fail: 24, meet: 46, rank: 20 },
    trade: [
      'Wait for a confirmed close below the lower line — don’t pre-guess.',
      'Enter short / exit longs on the breakdown; stop just above the last high.',
      'Take profits fast — moves are small and failures high (24% fail to move 5%).',
    ],
    gotchas: [
      'It looks bullish (price rising) but usually resolves DOWN — the classic trap.',
      'Needs enough touches; two random lines aren’t a wedge.',
      'A break UP on strong volume invalidates it — respect the actual break.',
    ],
    sources: [
      { title: 'Rising Wedges — Bulkowski', url: 'https://thepatternsite.com/risewedge.html' },
      { title: 'Guide to Trading Wedge Patterns — Trading Blitz', url: 'https://tradingblitz.com/learn/chart-patterns/guide-to-trading-wedge-chart-patterns-rising-falling/' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.1], [0.14, 0.42], [0.3, 0.28], [0.46, 0.6], [0.62, 0.45], [0.74, 0.68], [0.86, 0.3], [1, 0.12]]),
      lines: [{ p: 0.1, label: 'target = lowest low', kind: 'target' }],
      breakout: { x: 0.86, p: 0.45 },
    },
  },

  flag: {
    code: 'flag',
    name: 'Flag',
    family: 'Continuation',
    bias: 'bullish',
    oneLiner: 'A sharp surge, a short slanted pause in a tidy channel, then more of the same.',
    story:
      'A strong move (the “flagpole”) runs fast on heavy volume. Then traders take a breather: price drifts sideways or gently against the trend inside two parallel lines — a small rectangle tilted opposite the surge. Volume dries up because it’s just profit-taking, not a reversal. The flag usually breaks in the direction of the flagpole. It’s a pause, not a turn.',
    analogy:
      'A sprinter who bursts ahead, then jogs briefly to catch their breath before sprinting again.',
    identify: [
      'A steep, fast move first — the flagpole — on high volume.',
      'A short consolidation between two parallel lines, sloping gently against the trend.',
      'Volume shrinks during the flag.',
      'Duration short — about 1–3 weeks.',
      'Breakout in the flagpole’s direction, on rising volume.',
    ],
    examples: [
      'A stock rockets 30 → 40 (a 10-point pole), then drifts down between 39 and 37 for a week. Close above 40 → target 40 + 10 = 50.',
      'A share jumps 100 → 130, rests 128–124, then breaks above 130 → target 130 + 30 = 160.',
    ],
    howWeDetect:
      'We require a ≥20% pole in ≤28 bars, a tight (≤13% range) consolidation sitting at the top of the pole, and a confirming close above the consolidation high.',
    measureRule: 'Project the pole height off the breakout: target = consolidation high + pole height. Pole 30→40 = 10 → target 50.',
    stats: { avg: 23, fail: 4, meet: 64, rank: null },
    trade: [
      'Enter on the close beyond the flag’s edge, in the pole’s direction.',
      'Stop on the far side of the flag.',
      'These move fast — act on confirmation.',
    ],
    gotchas: [
      'No real flagpole = not a flag.',
      'A flag lasting many weeks becomes a rectangle — reliability fades.',
      'Don’t trade the pause before the breakout confirms.',
    ],
    sources: [
      { title: 'Flag & Pennant — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/flag-pennant' },
      { title: 'Flag Patterns — TrendSpider', url: 'https://trendspider.com/learning-center/chart-patterns-flags/' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.1], [0.1, 0.3], [0.2, 0.55], [0.3, 0.78], [0.42, 0.72], [0.52, 0.64], [0.62, 0.7], [0.72, 0.62], [0.82, 0.82], [0.92, 0.92], [1, 0.98]]),
      lines: [{ p: 0.72, label: 'flag top', kind: 'resistance' }, { p: 0.98, label: 'target', kind: 'target' }],
      dots: [{ x: 0.0, p: 0.1, label: 'pole base' }, { x: 0.3, p: 0.78, label: 'pole top' }],
      breakout: { x: 0.82, p: 0.72 },
    },
  },

  high_tight_flag: {
    code: 'high_tight_flag',
    name: 'High-and-Tight Flag',
    family: 'Continuation',
    bias: 'bullish',
    oneLiner: 'Price roughly DOUBLES fast, pauses tightly, then often launches again — the book’s #1 pattern.',
    story:
      'This starts with an explosive run — price climbs at least ~90% (ideally doubles) in two months or less. Such power means big, motivated buyers. Instead of crashing back, price just pauses in a small, tight, orderly consolidation. Because demand is so strong, it frequently breaks out and continues higher. Bulkowski measured a 0% break-even failure rate.',
    analogy:
      'A rocket already at escape velocity taking a brief coast before the next stage fires — momentum begets momentum.',
    identify: [
      'Price rose ~90%+ (aim for a double) in 2 months or less — the pole.',
      'A tight consolidation: bars overlap, price moves mostly sideways.',
      'Keep the flag short (under ~5 weeks) and orderly, not loose or jagged.',
      'Volume recedes during the rest.',
      'Entry = a close ABOVE the pattern high (not a mere trendline break).',
    ],
    examples: [
      'A stock jumps 10 → 20 in six weeks (a double), then chops tightly 18–20 for two weeks. Close above 20.5 → target = 18 + (20 − 10)/2 = 23.',
      'A share runs 5 → 10, rests 9–10, breaks above 10 → target = 9 + (10 − 5)/2 = 11.5.',
    ],
    howWeDetect:
      'We flag it when the pole gain ≥90% within ≤44 bars, followed by a tight consolidation and a confirming close.',
    measureRule: 'HALF the doubling move added to the flag low (still hits target ~90%). Rise 10→20 = 10 → half 5 → flag low 18 → target 23.',
    stats: { avg: 69, fail: 0, meet: 90, rank: 1 },
    trade: [
      'Buy only on the close above the pattern high — false trendline breaks are common.',
      'Stop below the flag low; size for a big potential move.',
      'Rare — quality over quantity.',
    ],
    gotchas: [
      'No ~90%+ two-month surge = it isn’t a high-and-tight flag, just a normal flag.',
      'A loose, sloppy, or over-long flag weakens it — demand tightness.',
      'Don’t buy the trendline break; wait for the close above the peak.',
    ],
    sources: [
      { title: 'High and Tight Flags — Bulkowski', url: 'https://thepatternsite.com/htf.html' },
      { title: 'Study of High & Tight Flags — Bulkowski', url: 'https://thepatternsite.com/HTFStudy.html' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.08], [0.12, 0.4], [0.24, 0.72], [0.34, 0.9], [0.46, 0.82], [0.56, 0.76], [0.66, 0.82], [0.78, 0.9], [0.9, 0.96], [1, 1.0]]),
      lines: [{ p: 0.86, label: 'flag top', kind: 'resistance' }, { p: 1.0, label: 'target', kind: 'target' }],
      dots: [{ x: 0.0, p: 0.08, label: 'base' }, { x: 0.34, p: 0.9, label: 'doubled' }],
      breakout: { x: 0.78, p: 0.86 },
    },
  },

  pennant: {
    code: 'pennant',
    name: 'Pennant',
    family: 'Continuation',
    bias: 'bullish',
    oneLiner: 'A sharp surge, then a tiny converging-triangle pause, before price resumes the surge.',
    story:
      'Like a flag, a pennant starts with a fast, high-volume move — the flagpole. Then price consolidates, but instead of a parallel channel it coils into a small triangle: highs come down, lows come up, converging to a point. Volume fades during this brief standoff. Because the prior trend is intact, the pennant usually breaks in the flagpole’s direction.',
    analogy:
      'A drawn bowstring pulling tight — energy compressing to a point before releasing the arrow.',
    identify: [
      'A steep flagpole first, on strong volume.',
      'A small CONVERGING triangle (lower highs + higher lows) — not parallel like a flag.',
      'Short duration: roughly 1–3 weeks.',
      'Volume contracts inside, then expands on the break.',
      'Breakout in the direction of the pole.',
    ],
    examples: [
      'A stock jumps 50 → 60 (a 10-point pole), coils between falling highs (59 → 57) and rising lows (55 → 57). Close above 60 → target 60 + 10 = 70.',
      'A share runs 20 → 26, coils to a point near 24, breaks above 26 → target 26 + 6 = 32.',
    ],
    howWeDetect:
      'Same flagpole test as a flag, but we fit the consolidation’s highs and lows — if they converge (highs falling, lows rising), it’s a pennant.',
    measureRule: 'Project the pole height off the breakout. Pole 50→60 = 10 → target 70.',
    stats: { avg: 25, fail: 2, meet: 60, rank: null },
    trade: [
      'Enter on the close beyond the pennant’s edge, in the pole’s direction.',
      'Stop on the opposite side of the coil.',
      'Pennants resolve quickly — be ready when it breaks.',
    ],
    gotchas: [
      'No sharp pole = it’s just a small symmetrical triangle, not a pennant.',
      'If it drags past ~12 weeks it becomes a full symmetrical triangle — less reliable.',
      'Converging lines (pennant) vs parallel lines (flag) — don’t confuse the two.',
    ],
    sources: [
      { title: 'Pennants — Bulkowski', url: 'https://thepatternsite.com/pennants.html' },
      { title: 'Flag & Pennant — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/flag-pennant' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.12], [0.12, 0.4], [0.24, 0.62], [0.32, 0.8], [0.44, 0.55], [0.54, 0.72], [0.64, 0.6], [0.72, 0.68], [0.82, 0.84], [0.92, 0.93], [1, 0.98]]),
      lines: [{ p: 0.98, label: 'target', kind: 'target' }],
      dots: [{ x: 0.0, p: 0.12, label: 'pole base' }, { x: 0.32, p: 0.8, label: 'pole top' }],
      breakout: { x: 0.82, p: 0.7 },
    },
  },

  cup_with_handle: {
    code: 'cup_with_handle',
    name: 'Cup with Handle',
    family: 'Continuation',
    bias: 'bullish',
    oneLiner: 'A rounded “U” base, then a small dip (the handle), then a breakout higher.',
    story:
      'A stock sells off, drifts along a bottom, then slowly climbs back to its old high — carving a smooth U, the “cup.” At the old high, early buyers take profits and price drifts down a little: the “handle,” a brief shakeout that flushes out weak holders. When price pushes above the handle on strong volume, the sellers are gone and the stock runs.',
    analogy:
      'Like a coffee cup seen side-on — a deep round bowl, then a small handle on the right lip before the drink is served. The handle is the last shakeout before the pour.',
    identify: [
      'Rounded U-shaped bottom, not a sharp V.',
      'Both sides of the cup reach roughly the same height (the “rim”).',
      'Handle is a small downward/sideways drift near the rim, in the upper half of the cup.',
      'Volume dries up in the cup and the handle.',
      'Volume surges on the breakout above the handle.',
    ],
    examples: [
      'Falls 100 → 70, rounds along, recovers to 100 (rim), eases to 95 (handle), then breaks above 100 on volume. Target = 100 + (100 − 70)/2 = 115.',
      'Cup rim 50, base 40; handle dips to 47; break above 50 targets 50 + (50 − 40)/2 = 55.',
    ],
    howWeDetect:
      'We fit a parabola to the recent base; a positive, well-fit U with a mid-placed bottom, matched rims, and a shallow recent handle (staying in the upper half) → cup with handle.',
    measureRule: 'HALF the cup depth added to the rim (half-depth hits target ~76% vs 50% for the full depth). Rim 100, base 70 → depth 30 → target 115.',
    stats: { avg: 34, fail: 5, meet: 50, rank: 13 },
    trade: [
      'Enter on a close above the handle high (the rim) with rising volume.',
      'Stop just below the handle low, not the deep cup low.',
      'No volume on the breakout = higher chance it fails; wait for it.',
    ],
    gotchas: [
      'A sharp V-recovery is NOT a cup — the slow rounding is the point.',
      'A deep handle (below the cup’s midpoint) weakens the pattern.',
      'Chasing before the breakout; let price clear the rim first.',
    ],
    sources: [
      { title: 'Cup & Handle: 3 Strategies — TradingSim', url: 'https://www.tradingsim.com/blog/how-to-trade-the-cup-and-handle-pattern' },
      { title: 'Cup and Handle — TrendSpider', url: 'https://trendspider.com/learning-center/chart-patterns-cup-and-handle/' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.82], [0.1, 0.6], [0.2, 0.35], [0.32, 0.2], [0.44, 0.2], [0.56, 0.32], [0.68, 0.58], [0.78, 0.8], [0.85, 0.66], [0.9, 0.7], [0.96, 0.88], [1, 0.96]]),
      lines: [{ p: 0.8, label: 'rim', kind: 'resistance' }, { p: 0.96, label: 'target', kind: 'target' }],
      dots: [{ x: 0.38, p: 0.2, label: 'cup base' }, { x: 0.85, p: 0.66, label: 'handle' }],
      breakout: { x: 0.96, p: 0.8 },
    },
  },

  rounding_bottom: {
    code: 'rounding_bottom',
    name: 'Rounding Bottom',
    family: 'Continuation',
    bias: 'bullish',
    oneLiner: 'A slow, saucer-shaped U where a downtrend gradually curves into an uptrend.',
    story:
      'After a long decline, selling pressure quietly fades. Price stops making meaningful new lows and flattens into a wide, gentle bowl. Mid-way, both buyers and sellers lose interest and volume dries up. Then buyers slowly reappear, absorbing shares, and price curves back up — a mood shift from fear and apathy to quiet optimism, usually with no dramatic news.',
    analogy:
      'Like a supertanker turning around — slow, smooth, unstoppable once underway. Or a beaten-down value name where the bad news simply stops mattering.',
    identify: [
      'Long, gradual U shape (weeks to months), not a quick dip.',
      'Lows get shallower over time, flatten, then turn up.',
      'Roughly symmetrical: the rise mirrors the earlier fall.',
      'Volume high at the start, lowest at the bottom, rising into the advance.',
      'Confirmation = a break above the pattern’s left-side high (the right lip).',
    ],
    examples: [
      'Slides 60 → 40 over two months, grinds near 40, then lifts back to 60. Break above 60 on volume → target 60 + (60 − 40) = 80.',
      'A share rounds 20 → 15 → 20; a close above 20 targets 20 + (20 − 15) = 25.',
    ],
    howWeDetect:
      'A well-fit upward parabola over a long window with the low near the middle → rounding bottom (a cup without a handle).',
    measureRule: 'Full depth added to the right-lip breakout. High 60, bottom 40 → depth 20 → target 80.',
    stats: { avg: 43, fail: 5, meet: 57, rank: 5 },
    trade: [
      'Wait for the close above the left-side high before buying.',
      'Rising volume into the breakout adds confidence.',
      'Stop below the recent higher-low on the right side of the bowl.',
    ],
    gotchas: [
      'Impatience — this is a slow pattern; a jagged, fast bottom isn’t a rounding bottom.',
      'Buying mid-bowl before the trend has actually turned up.',
    ],
    sources: [
      { title: 'Rounding Bottom — StockCharts ChartSchool', url: 'https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/rounding-bottom' },
      { title: 'Rounding Bottom (Saucer) — ChartGuys', url: 'https://www.chartguys.com/chart-patterns/rounding-bottom-saucer' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.8], [0.12, 0.58], [0.26, 0.36], [0.4, 0.22], [0.54, 0.22], [0.68, 0.36], [0.82, 0.6], [0.92, 0.8], [1, 0.94]]),
      lines: [{ p: 0.8, label: 'lip', kind: 'resistance' }, { p: 0.98, label: 'target', kind: 'target' }],
      dots: [{ x: 0.47, p: 0.22, label: 'base' }],
      breakout: { x: 0.92, p: 0.8 },
    },
  },

  pipe_bottom: {
    code: 'pipe_bottom',
    name: 'Pipe Bottom',
    family: 'Bullish reversals',
    bias: 'bullish',
    oneLiner: 'Two side-by-side deep downward spikes on the weekly chart — a violent V washout.',
    story:
      'In a downtrend, sellers panic and hammer price to a sharp low for one week. The next week price stabs down to nearly the same low — but buyers rush in both times, snapping price back up and leaving two long “tails.” This twin-spike bottom shows sellers have exhausted themselves in a violent flush. Best seen on weekly charts; it predicts a quick reversal up once price closes above the spikes.',
    analogy:
      'A fire-sale panic where a stock briefly trades below what it’s obviously worth, then buyers pounce — like grabbing a quality item at a two-day clearance before the price resets.',
    identify: [
      'Two adjacent bars (best on a WEEKLY chart) with long lower shadows.',
      'Both spikes plunge to nearly the same low, with large overlap.',
      'The spikes are noticeably longer than typical spikes of the past year.',
      'Surrounding bars sit well above the two pipe lows.',
      'Confirms when price closes above the higher of the two spike tops.',
    ],
    examples: [
      'Price drops toward 50, spikes to 45 one week then 46 the next, both closing near 52. A later close above 53 confirms. Height = 53 − 45 = 8 → target 61.',
      'Twin weekly dips to 18 and 18.5 with a 21 top; close above 21 targets 21 + (21 − 18) = 24.',
    ],
    howWeDetect:
      'We resample to weekly bars (so Bulkowski’s weekly stats apply), find two adjacent weeks whose range is >1.5× the recent average with matching lows, and confirm on a daily close above the two-week high.',
    measureRule: 'Full height (pattern high − spike low) added to the breakout. Low 45, top 53 → height 8 → target 61.',
    stats: { avg: 45, fail: 5, meet: 83, rank: 2 },
    trade: [
      'Buy on the confirmation close above the spikes.',
      'Stop just below the spike low. 83% reach target — high reliability.',
      'Look for a volume surge on the confirming breakout.',
    ],
    gotchas: [
      'This is a WEEKLY pattern — isolated daily V-spikes are far less reliable (which is why we resample).',
      'No confirming close above the spikes means it isn’t a pipe yet — don’t pre-empt.',
      'Short, ordinary spikes don’t count; they must be unusually long.',
    ],
    sources: [
      { title: 'Pipe Top & Bottom Patterns — Strike.money', url: 'https://www.strike.money/technical-analysis/pipe-top-and-bottom-patterns' },
      { title: 'Pipe Bottoms — Bulkowski', url: 'https://thepatternsite.com/pipeb.html' },
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.6], [0.2, 0.55], [0.36, 0.1], [0.52, 0.12], [0.68, 0.58], [0.84, 0.78], [1, 0.92]]),
      lines: [{ p: 0.6, label: 'neckline', kind: 'neckline' }, { p: 0.95, label: 'target', kind: 'target' }],
      dots: [{ x: 0.36, p: 0.1, label: 'spike 1' }, { x: 0.52, p: 0.12, label: 'spike 2' }],
      breakout: { x: 0.68, p: 0.6 },
    },
  },

  pipe_top: {
    code: 'pipe_top',
    name: 'Pipe Top',
    family: 'Bearish reversals',
    bias: 'bearish',
    oneLiner: 'Two side-by-side deep upward spikes on the weekly chart — a blow-off top.',
    story:
      'After an uptrend, buyers make one last euphoric push to a sharp high — then sellers slam it back down. The next week buyers try again to nearly the same high and fail again, leaving two long upper “tails.” This twin-spike top shows buying is exhausted and sellers have taken control. On weekly charts it warns of a fast reversal down once price closes below the spikes.',
    analogy:
      'A mania spike — everyone piles in at the top over two frantic weeks, then reality hits, like a collectible that spikes on hype and re-prices down.',
    identify: [
      'Two adjacent bars (best WEEKLY) with long upper shadows.',
      'Both spikes reach nearly the same high, with large overlap.',
      'Spikes much longer than typical spikes of the prior year.',
      'Surrounding bars sit well below the two pipe highs.',
      'Confirms when price closes below the lower of the two spike bottoms.',
    ],
    examples: [
      'Climbs toward 100, spikes to 105 one week then 104 the next, both closing near 96. A later close below 94 confirms. Height = 105 − 94 = 11 → target 83.',
      'Twin weekly peaks at 30 and 30.5 with a 27 base; close below 27 targets 27 − (30 − 27) = 24.',
    ],
    howWeDetect:
      'Weekly resampling; two adjacent oversized weeks with matching highs; confirm on a daily close below the two-week low.',
    measureRule: 'Full height (peak − pattern low) subtracted from the breakout. Peak 105, base 94 → height 11 → target 83.',
    stats: { avg: 20, fail: 11, meet: 70, rank: 4 },
    trade: [
      'Sell / short on the close below the spikes; treat it as an exit for longs.',
      'Stop just above the spike high.',
      'A volume surge on the breakdown adds confidence.',
    ],
    gotchas: [
      'A weekly pattern — treat isolated daily spikes with caution.',
      'Without a close below the spikes it isn’t confirmed — avoid front-running.',
      'Two small everyday spikes are not a pipe; they must be abnormally tall.',
    ],
    sources: [
      { title: 'Pipe Top & Bottom Patterns — Strike.money', url: 'https://www.strike.money/technical-analysis/pipe-top-and-bottom-patterns' },
      { title: 'Pipe Tops — Bulkowski', url: 'https://thepatternsite.com/pipet.html' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.4], [0.2, 0.45], [0.36, 0.9], [0.52, 0.88], [0.68, 0.42], [0.84, 0.22], [1, 0.08]]),
      lines: [{ p: 0.4, label: 'neckline', kind: 'neckline' }, { p: 0.05, label: 'target', kind: 'target' }],
      dots: [{ x: 0.36, p: 0.9, label: 'spike 1' }, { x: 0.52, p: 0.88, label: 'spike 2' }],
      breakout: { x: 0.68, p: 0.4 },
    },
  },

  dead_cat_bounce: {
    code: 'dead_cat_bounce',
    name: 'Dead-Cat Bounce',
    family: 'Event — danger',
    bias: 'bearish',
    oneLiner: 'A brief, tempting recovery after a sharp crash that then rolls over to new lows. A trap.',
    story:
      'A stock crashes hard on bad news. After the plunge, bargain-hunters and short-sellers taking profits push price up for a few days — it looks like the bottom is in. But the rebound is weak, on light volume, and stalls below broken support. Sellers return and drive price to fresh new lows, trapping everyone who “bought the dip.” The bounce is not a recovery; it’s a pause inside an ongoing collapse.',
    analogy:
      '“Even a dead cat bounces if it’s dropped from high enough.” The bounce is just physics, not life — the cat is still dead, and the trend is still down. Cheap gets cheaper.',
    identify: [
      'Starts with a steep, fast decline (often a shock or bad news) — ~15%+ in a session.',
      'A short rebound that recovers less than half the drop.',
      'Rebound volume light compared to the crash.',
      'The bounce stalls below prior support / a key moving average.',
      'Weak momentum — no real buying strength.',
    ],
    examples: [
      'Crashes 100 → 60, bounces to 72 over three days on thin volume, then rolls over to 55 — below the crash low.',
      'Drops 40 → 30, weak bounce to 34, then new low at 28. Everyone who bought the “cheap” bounce is now underwater.',
    ],
    howWeDetect:
      'We flag any recent session where price dropped ≥15% close-to-low. We then SUPPRESS bullish chart patterns on that stock for ~6 months, exactly as Bulkowski advises.',
    measureRule:
      'No upside target — expect price to fall BELOW the crash low. Bulkowski: a further ~18% below the event low, ~38% total from the pre-crash close.',
    stats: { avg: 18, fail: null, meet: null, rank: null },
    trade: [
      'Do NOT buy the bounce — it usually makes new lows.',
      'If you hold the stock, use the bounce to exit at a better price.',
      'Avoid any bullish setup on the name for ~6 months.',
    ],
    gotchas: [
      '“It’s so cheap now” is the trap — cheap gets cheaper in a downtrend.',
      'A real bottom reclaims broken support on strong volume; a dead-cat bounce doesn’t.',
      'The company’s problem rarely fixes in one quarter — a second leg down is common.',
    ],
    sources: [
      { title: 'Dead Cat Bounce — Investopedia', url: 'https://www.investopedia.com/terms/d/deadcatbounce.asp' },
      { title: 'Dead-Cat Bounce — Britannica Money', url: 'https://www.britannica.com/money/dead-cat-bounce' },
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.85], [0.12, 0.82], [0.2, 0.8], [0.22, 0.28], [0.34, 0.45], [0.46, 0.5], [0.58, 0.42], [0.7, 0.3], [0.82, 0.18], [1, 0.08]]),
      lines: [{ p: 0.28, label: 'event low', kind: 'support' }],
      dots: [{ x: 0.22, p: 0.28, label: 'crash' }, { x: 0.46, p: 0.5, label: 'bounce (trap)' }],
      breakout: { x: 0.7, p: 0.28 },
    },
  },
};

export const TUTORIAL_ORDER: string[] = [
  'double_bottom', 'hs_bottom', 'triple_bottom', 'three_rising_valleys', 'pipe_bottom',
  'rounding_bottom', 'cup_with_handle',
  'ascending_triangle', 'descending_triangle', 'symmetrical_triangle',
  'rectangle_bottom', 'rectangle_top', 'falling_wedge', 'rising_wedge',
  'flag', 'high_tight_flag', 'pennant',
  'double_top', 'hs_top', 'triple_top', 'three_falling_peaks', 'pipe_top',
  'dead_cat_bounce',
];
