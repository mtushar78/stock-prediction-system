// Chart-pattern tutorial library.
//
// One lesson per Bulkowski pattern the engine detects: a plain-English story,
// a value/real-world analogy, how to spot it, how WE detect it, the measure
// rule, Bulkowski's real bull-market track record, and how to trade it — plus
// a schematic spec that PatternSchematic renders as an annotated diagram.
//
// Every detected pattern code maps to one of these via tutorialCodeFor().

export type SchematicPoint = { x: number; p: number }; // x,p in 0..1 (p: 1=high price, 0=low)
export type SchematicLine = { p: number; label: string; kind: 'neckline' | 'target' | 'support' | 'resistance' | 'stop' };
export type SchematicDot = { x: number; p: number; label: string };
export interface Schematic {
  points: SchematicPoint[];      // the price path
  lines?: SchematicLine[];       // horizontal reference lines
  dots?: SchematicDot[];         // labelled key points
  breakout?: { x: number; p: number }; // where price breaks out
  bias: 'bullish' | 'bearish' | 'neutral';
}

export interface Tutorial {
  code: string;
  name: string;
  family: string;               // grouping for the sidebar
  bias: 'bullish' | 'bearish' | 'neutral';
  oneLiner: string;
  story: string;
  analogy: string;
  identify: string[];
  howWeDetect: string;
  measureRule: string;
  stats: { avg: number | null; fail: number | null; meet: number | null; rank: number | null };
  trade: string[];
  gotchas: string[];
  schematic: Schematic;
}

// Map any engine pattern code → the canonical tutorial key.
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
    oneLiner: 'Price tests a floor twice, holds, and breaks out — a “W”.',
    story:
      'After a decline, sellers drive price to a low. Buyers step in and it bounces. It slips back down to about the same low — but this time sellers can’t push it lower. That failed second attempt tells you selling is exhausted. When price finally closes above the peak between the two lows (the “neckline”), the reversal is confirmed and buyers take over.',
    analogy:
      'Think of a stock that keeps bouncing off ₹100 like a ball off a hard floor. Twice the market tried to sell it below ₹100 and failed. That ₹100 floor is where value buyers keep saying “this is too cheap.” The second failed break is your proof the floor is real — like a house that gets two offers at the same price after sitting unsold; the market has found its value.',
    identify: [
      'Two distinct lows at roughly the same price (within ~5%).',
      'A clear rally between them of at least ~10% (the neckline peak).',
      'Comes after a downtrend — it’s a REVERSAL, not a continuation.',
      'Confirmed only when price CLOSES above the middle peak.',
    ],
    howWeDetect:
      'We extract swing pivots with a zigzag, then look for Low–High–Low where the two lows are within 5%, the middle peak is ≥10% above them, they’re 2–14 weeks apart, and the prior trend was down. We mark it CONFIRMED once a close clears the peak. Adam (sharp/V) vs Eve (wide/rounded) bottoms are classified by width — Eve & Eve is the strongest variant.',
    measureRule:
      'Full height: take the neckline peak minus the lower bottom, and add it ABOVE the neckline. That projected level is the target.',
    stats: { avg: 40, fail: 4, meet: 67, rank: 6 },
    trade: [
      'Buy the close above the neckline (or a small pullback to it).',
      'Stop just below the lower of the two bottoms.',
      'Beware overhead resistance — a “throwback” to the neckline hurts performance.',
    ],
    gotchas: [
      'Unconfirmed “W”s fail ~65% of the time — wait for the breakout close.',
      'If price closes back below the bottoms, the pattern is void.',
    ],
    schematic: {
      bias: 'bullish',
      points: W([[0, 0.85], [0.16, 0.12], [0.38, 0.58], [0.6, 0.14], [0.78, 0.62], [0.9, 0.85], [1, 0.96]]),
      lines: [
        { p: 0.58, label: 'neckline', kind: 'neckline' },
        { p: 0.96, label: 'target', kind: 'target' },
      ],
      dots: [
        { x: 0.16, p: 0.12, label: 'bottom 1' },
        { x: 0.6, p: 0.14, label: 'bottom 2' },
      ],
      breakout: { x: 0.78, p: 0.58 },
    },
  },

  double_top: {
    code: 'double_top',
    name: 'Double Top',
    family: 'Bearish reversals',
    bias: 'bearish',
    oneLiner: 'Price hits a ceiling twice, fails, and breaks down — an “M”.',
    story:
      'After a rise, price reaches a high and pulls back. Buyers try again and reach about the same high — but can’t exceed it. That second failure means demand is used up. When price closes below the valley between the two peaks, the top is confirmed and sellers take control.',
    analogy:
      'A stock rallies to ₹200 twice and can’t get through — like an auction where the top bid keeps stalling at the same number. Nobody is willing to pay more. When the “floor bid” (the valley) finally breaks, the whole thing re-prices lower, the way an overpriced flat finally drops once two buyers walk away at the same ceiling.',
    identify: [
      'Two peaks at roughly the same price (within ~5%).',
      'A meaningful dip between them (~10%+).',
      'Comes after an uptrend.',
      'Confirmed when price CLOSES below the middle valley.',
    ],
    howWeDetect:
      'We find High–Low–High swing pivots with the two highs within 5%, a ≥10% valley between, an uptrend into the pattern, and a confirming close below the valley.',
    measureRule:
      'HALF height (Bulkowski’s rule for tops): take the peak minus the valley, halve it, and subtract from the valley. Tops rarely fill the full projection, so half-height is the realistic target.',
    stats: { avg: 18, fail: 11, meet: 73, rank: 2 },
    trade: [
      'Exit / avoid on the close below the valley.',
      'Watch for underlying support that can stall the decline (a pullback).',
    ],
    gotchas: [
      'If price makes a new high above the peaks before confirming, it’s not a double top.',
      'In a strong bull market, tops fail more often — respect the trend.',
    ],
    schematic: {
      bias: 'bearish',
      points: W([[0, 0.15], [0.16, 0.88], [0.38, 0.42], [0.6, 0.86], [0.78, 0.38], [0.9, 0.15], [1, 0.05]]),
      lines: [
        { p: 0.42, label: 'neckline', kind: 'neckline' },
        { p: 0.2, label: 'target', kind: 'target' },
      ],
      dots: [
        { x: 0.16, p: 0.88, label: 'top 1' },
        { x: 0.6, p: 0.86, label: 'top 2' },
      ],
      breakout: { x: 0.78, p: 0.42 },
    },
  },

  triple_bottom: {
    code: 'triple_bottom',
    name: 'Triple Bottom',
    family: 'Bullish reversals',
    bias: 'bullish',
    oneLiner: 'Three tests of the same floor, then a breakout.',
    story:
      'Like a double bottom but with three touches of the same support. Three failed attempts to break lower is even stronger evidence that sellers are done. Confirmation is a close above the highest peak within the pattern.',
    analogy:
      'A dam holds back the water three separate times. Each time the flood (selling) recedes without breaking it. By the third hold, you trust the dam — and you trust the ₹-floor under the stock.',
    identify: [
      'Three distinct lows at nearly the same price (within ~3.5%).',
      'Well separated (the base spans weeks).',
      'Confirmed by a close above the highest interior peak.',
    ],
    howWeDetect:
      'We require three same-level lows (within 3.5%), a base ≥20 bars wide with real depth, the centre not the lowest (that would be a head-and-shoulders), and a confirming close above the highest peak.',
    measureRule: 'Full height: highest peak minus lowest low, added above the breakout.',
    stats: { avg: 37, fail: 4, meet: 64, rank: 7 },
    trade: ['Buy the breakout close; stop below the lowest low.', 'A higher third valley is a bullish tell.'],
    gotchas: ['Three descending lows is NOT a triple bottom — it’s still a downtrend.'],
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
    oneLiner: 'Three tests of the same ceiling, then a breakdown.',
    story:
      'Three failed pushes to the same high. Demand is exhausted; a close below the lowest valley confirms the reversal down.',
    analogy:
      'A high-jumper attempts the same bar three times and knocks it off each time. After the third miss, you stop betting they’ll clear it — you bet they’ll walk away (the price falls).',
    identify: [
      'Three highs at nearly the same price (within ~3.5%).',
      'Confirmed by a close below the lowest interior valley.',
    ],
    howWeDetect:
      'Three same-level highs (within 3.5%), centre not the highest, span ≥20 bars, confirming close below the lowest valley.',
    measureRule:
      'Full height (NOT the double-top half rule): highest high minus lowest valley, subtracted from the breakout. Only ~40% reach it, so treat it as a ceiling on expectations.',
    stats: { avg: 19, fail: 10, meet: 40, rank: 7 },
    trade: ['Exit on the breakdown close; the target fills only ~40% of the time, so bank profits along the way.'],
    gotchas: ['Rising highs = broadening top, not a triple top.'],
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
    oneLiner: 'A deep low (head) flanked by two shallower lows (shoulders).',
    story:
      'Also called an inverse head-and-shoulders. Sellers make a low (left shoulder), a deeper low (the head), then a higher low (right shoulder) — each dip is losing steam. A close above the neckline (joining the two peaks between the dips) confirms buyers have won.',
    analogy:
      'Picture panic selling that gets progressively less panicky: the second dip is the scariest (the head), but by the third the fear is fading and buyers absorb it. Like a stock that flushes to a washout low, then can’t make a new low even on bad news — the value floor is in.',
    identify: [
      'Three lows: the middle (head) is clearly the lowest; the two shoulders are shallower and roughly level.',
      'Roughly symmetric in time around the head.',
      'Neckline joins the two rally peaks; breakout is a close above it.',
    ],
    howWeDetect:
      'We find Low–High–Low–High–Low pivots where the centre low is ≥5% below the shoulders, shoulders are within 5% of each other and roughly time-symmetric, the neckline peaks are reasonably level, and price closes above the (projected) neckline.',
    measureRule: 'Full height: the vertical distance from the head up to the neckline, added above the breakout.',
    stats: { avg: 38, fail: 3, meet: 74, rank: 7 },
    trade: ['Buy the neckline breakout; stop below the right shoulder.', 'One of the most reliable reversals — 74% reach target.'],
    gotchas: ['If the head isn’t clearly the lowest, it’s a triple bottom instead.'],
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
    oneLiner: 'A high peak (head) flanked by two lower peaks (shoulders).',
    story:
      'The classic top. Buyers make a high (left shoulder), a higher high (head), then a lower high (right shoulder) — momentum is fading. A close below the neckline confirms the downtrend.',
    analogy:
      'A rocket that stalls: each successive burst is weaker. By the right shoulder, the engine is out of fuel. Like a hot stock whose rallies keep falling short — the crowd that was paying up has run out.',
    identify: [
      'Three peaks: the middle (head) is the highest; shoulders are lower and roughly level.',
      'Breakout is a close below the neckline joining the two intervening lows.',
    ],
    howWeDetect:
      'High–Low–High–Low–High pivots with the centre high clearly above the shoulders, shoulders within 5% and time-symmetric, a level-ish neckline, and a confirming close below it. It’s Bulkowski’s #1-ranked bearish pattern in a bear market.',
    measureRule: 'Full height: head down to the neckline, subtracted from the breakout.',
    stats: { avg: 22, fail: 4, meet: 55, rank: 1 },
    trade: ['Exit / short on the neckline break; stop above the higher of the two necklines/armpits.'],
    gotchas: ['A pullback to the neckline is common — it hurts performance, so don’t chase.'],
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
    oneLiner: 'Three higher lows — a staircase up.',
    story:
      'Each pullback bottoms higher than the last. Buyers are getting more eager, stepping in earlier each time. A close above the pattern’s high confirms the uptrend.',
    analogy:
      'Bargain hunters raising their limit orders: first they’ll buy at ₹50, then only get filled at ₹55, then ₹60 — rising demand chasing a stock they believe is cheap.',
    identify: ['Three successively higher lows.', 'Each step is a real move (≥3%).', 'Confirmed by a close above the highest high.'],
    howWeDetect: 'Three strictly rising swing lows spanning ≥25 bars, each leg ≥3%, ≥8% end-to-end, with a confirming close above the pattern high.',
    measureRule: 'Full height (highest high − lowest low) added to the breakout.',
    stats: { avg: 41, fail: 5, meet: 58, rank: 4 },
    trade: ['Buy the breakout; momentum names work best bought near new highs.'],
    gotchas: ['Don’t confuse with a rising wedge (which converges and usually breaks down).'],
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
    oneLiner: 'Three lower highs — a staircase down.',
    story: 'Each rally tops lower than the last — sellers press harder each time. A close below the lowest low confirms the downtrend.',
    analogy: 'Sellers cutting their asking price with every attempt: ₹100, then ₹92, then ₹85 — supply overwhelming a fading bid.',
    identify: ['Three successively lower highs.', 'Confirmed by a close below the lowest low.'],
    howWeDetect: 'Three strictly falling swing highs spanning ≥25 bars, each leg ≥3%, with a confirming close below the pattern low. Only ~33% reach target — get in early.',
    measureRule: 'Full height subtracted from the lowest low.',
    stats: { avg: 17, fail: 12, meet: 33, rank: 8 },
    trade: ['Act early — the target fills only a third of the time. Bank profits fast.'],
    gotchas: ['Weak measure-rule reliability; treat the target as optimistic.'],
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
    oneLiner: 'Flat ceiling, rising floor — pressure builds upward.',
    story:
      'Price keeps stalling at the same resistance, but each pullback bottoms higher. Buyers are willing to pay up sooner and sooner while sellers hold one price line. The coil usually resolves UP (~70%) when price closes above the flat top.',
    analogy:
      'A crowd pushing against a door: they keep backing off less and less. The door (resistance) holds… until the rising pressure pops it open. Like eager buyers narrowing the gap to a seller’s fixed asking price.',
    identify: ['Horizontal resistance line across the highs.', 'Up-sloping support line under the rising lows.', 'Breakout is a close above the flat top.'],
    howWeDetect: 'We fit trendlines to recent swing highs/lows; a near-flat top (|slope|<0.1%/bar) with a clearly rising bottom classifies as ascending. Height = flat top − lowest low.',
    measureRule: 'Add the pattern height (top − lowest low) to the breakout price.',
    stats: { avg: 35, fail: 13, meet: 75, rank: 17 },
    trade: ['Buy the close above the flat top on strong volume.', 'Stop below the rising trendline.'],
    gotchas: ['~30% break DOWN — wait for the actual close, don’t front-run the direction.'],
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
    oneLiner: 'Flat floor, falling ceiling — pressure builds downward.',
    story:
      'Price keeps bouncing off the same support, but each rally tops lower. Sellers grow impatient, hitting the bid sooner. It usually resolves DOWN when price closes below the flat floor.',
    analogy: 'Buyers holding one price line while sellers keep undercutting each other — the floor eventually gives way, like a support level cracking under repeated selling.',
    identify: ['Horizontal support across the lows.', 'Down-sloping resistance over the falling highs.', 'Breakout is a close below the flat floor.'],
    howWeDetect: 'A near-flat bottom with a clearly falling top classifies as descending. Note: in a bull market the less-common UP break is actually the stronger trade.',
    measureRule: 'Subtract the pattern height (highest high − flat floor) from the breakout.',
    stats: { avg: 16, fail: 16, meet: 54, rank: 10 },
    trade: ['Exit/short on the close below support; watch for the bullish up-break exception.'],
    gotchas: ['Direction isn’t guaranteed — trade the actual breakout close.'],
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
    oneLiner: 'A coil of lower highs and higher lows — a spring winding up.',
    story:
      'Buyers and sellers squeeze into an ever-tighter range. Energy builds like a compressed spring; the breakout (either way) releases it. Trade the direction it actually breaks.',
    analogy: 'A tug-of-war where both teams tire and the flag narrows toward the centre — until one side suddenly gives and it snaps their way.',
    identify: ['Down-sloping top and up-sloping bottom converging to an apex.', 'At least two touches on each line.', 'Trade the close beyond a rail.'],
    howWeDetect: 'Both trendlines slope toward each other (top down, bottom up). We stay neutral until a rail is broken, then set direction and target from the break.',
    measureRule: 'Add/subtract the pattern height at the breakout rail.',
    stats: { avg: 31, fail: 9, meet: 66, rank: 16 },
    trade: ['Wait for the breakout close; breakouts near the yearly low tend to perform best.'],
    gotchas: ['Don’t guess the direction early — it’s genuinely two-sided.'],
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
    oneLiner: 'A flat trading range after an up-move.',
    story:
      'Price ping-pongs between horizontal support and resistance while the market pauses. An up-break continues the trend; a down-break reverses it.',
    analogy: 'A stock “resting” in a box, like a house price stuck in a tight band while buyers and sellers agree on a fair range — until new information tips it out.',
    identify: ['Two roughly horizontal parallel lines.', 'At least two touches of each.', 'Trade the rail that breaks.'],
    howWeDetect: 'Both trendlines near-flat with an uptrend into the range → rectangle top. Neutral until a rail breaks.',
    measureRule: 'Add/subtract the box height at the breakout.',
    stats: { avg: 39, fail: 9, meet: 80, rank: 12 },
    trade: ['A “partial rise” that fails to reach the top often precedes a down-break; a partial decline often precedes an up-break.'],
    gotchas: ['Whipsaws inside the box are common — wait for the decisive close.'],
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
    oneLiner: 'A flat trading range after a down-move.',
    story: 'A horizontal range following a decline. An up-break is the bullish reversal; a down-break continues the fall.',
    analogy: 'A stock building a base — value buyers and trapped sellers trading in a fixed band until accumulation wins and it breaks up.',
    identify: ['Two horizontal parallel lines after a downtrend.', 'Trade the rail that breaks.'],
    howWeDetect: 'Two near-flat lines with a downtrend into the range → rectangle bottom.',
    measureRule: 'Add/subtract the box height at the breakout. Up-breaks reach target ~85% of the time.',
    stats: { avg: 46, fail: 10, meet: 85, rank: 11 },
    trade: ['Up-break on rising volume is a high-reliability long (85% hit target).'],
    gotchas: ['Wait for the close beyond the rail.'],
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
    oneLiner: 'Two down-sloping lines converging — selling exhausts, price pops up.',
    story:
      'Price drifts lower in a narrowing channel; both the highs and lows fall, but the decline is losing steam. About 68% of the time it breaks UP, recovering to the top of the wedge.',
    analogy: 'A slowly deflating slide that flattens out — the downward momentum peters out and buyers reclaim the ground, like a stock whose selling dries up after a controlled pullback.',
    identify: ['Both trendlines slope down and converge (top steeper).', 'Ideally ~5 touches.', 'Breakout is a close above the upper line.'],
    howWeDetect: 'Both lines negative-sloped with the top steeper (more negative). Up-target is set to the wedge’s highest high (not breakout+height).',
    measureRule: 'Up-target = the highest high inside the wedge (an “easy objective” per Bulkowski).',
    stats: { avg: 32, fail: 11, meet: 70, rank: 20 },
    trade: ['Buy the up-break; reversals of a prior downtrend perform best.'],
    gotchas: ['~27% dip below the lower line first, then reverse up — don’t panic on the false break.'],
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
    oneLiner: 'Two up-sloping lines converging — a tiring rally that usually breaks DOWN.',
    story:
      'Price grinds higher but the highs and lows converge and momentum narrows. It looks bullish but usually resolves DOWN — the rally runs out of buyers. Bulkowski’s worst-performing pattern, so trade it carefully.',
    analogy: 'A car accelerating toward a cliff — still going up, but the road is running out. The higher-but-weaker highs are a warning the fuel is nearly gone.',
    identify: ['Both trendlines slope UP and converge (bottom steeper).', 'Breakout is usually a close below the lower line.'],
    howWeDetect: 'Both lines positive-sloped, converging. Down-target is set to the wedge’s lowest low (not breakout−height).',
    measureRule: 'Down-target = the lowest low inside the wedge.',
    stats: { avg: 14, fail: 24, meet: 46, rank: 20 },
    trade: ['Take profits/exit fast — moves are small and failures high (24% fail to move 5%).'],
    gotchas: ['High failure rate — don’t oversize. Confirmation matters.'],
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
    oneLiner: 'A sharp run (the pole), then a brief tight pause, then more of the same.',
    story:
      'After a steep, fast advance (the “flagpole”), price consolidates in a small tight range for a few days to three weeks — profit-taking and a breather — before resuming the trend.',
    analogy: 'A sprinter catching their breath mid-race: a short pause, not a stop. The strong prior move is the tell that the trend has real momentum behind it.',
    identify: ['A steep prior move (the pole).', 'A short (≤3 week) tight consolidation.', 'Breakout is a close above the consolidation high.'],
    howWeDetect: 'We require a ≥20% pole in ≤28 bars, a tight (≤13% range) consolidation sitting at the top of the pole, and a confirming close above the consolidation high.',
    measureRule: 'Project the pole’s height off the breakout: target = consolidation high + pole height.',
    stats: { avg: 23, fail: 4, meet: 64, rank: null },
    trade: ['Buy the breakout; these move fast, so act promptly (many reach target within 2 weeks).'],
    gotchas: ['No strong prior pole = not a flag. The pole is the whole point.'],
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
    oneLiner: 'Price roughly DOUBLES fast, pauses tightly, then runs again — the book’s #1 pattern.',
    story:
      'The most powerful bullish pattern in the Encyclopedia. Price at least doubles (≈100%) in two months or less, then forms a short tight flag. Bulkowski measured a 0% break-even failure rate and a 69% average further rise.',
    analogy:
      'A rocket already at escape velocity taking a brief coast before the next stage fires. When a stock proves it can double, the same force often carries it further — momentum begets momentum.',
    identify: ['Price ≈ doubles (≥90%) in ≤2 months.', 'A short, tight consolidation follows.', 'Breakout is a close above the flag high.'],
    howWeDetect: 'We flag it when the pole gain ≥90% within ≤44 bars, followed by a tight consolidation and a confirming close.',
    measureRule: 'HALF the doubling move added to the flag low (still hits target ~90% of the time).',
    stats: { avg: 69, fail: 0, meet: 90, rank: 1 },
    trade: ['Enter on the breakout; use a stop below the flag. Position size for a big potential move.'],
    gotchas: ['Rare — most “doublings” don’t form a clean tight flag. Quality over quantity.'],
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
    oneLiner: 'Like a flag, but the pause is a tiny converging triangle.',
    story:
      'A steep pole followed by a small symmetrical-triangle consolidation (converging highs and lows) rather than a parallel channel. The trend resumes on the breakout.',
    analogy: 'A spinning top slowing to a wobble before someone flicks it again — a brief coil after a strong push.',
    identify: ['A steep prior pole.', 'A short converging consolidation (falling highs + rising lows).', 'Breakout is a close above the pennant.'],
    howWeDetect: 'Same flagpole test as a flag, but we fit the consolidation’s highs and lows — if they converge (high slope < 0, low slope > 0), it’s a pennant.',
    measureRule: 'Project the pole height off the breakout.',
    stats: { avg: 25, fail: 2, meet: 60, rank: null },
    trade: ['Buy the breakout; short-term move, so manage it actively.'],
    gotchas: ['Needs the pole — a converging range without a prior sharp run is just a small triangle.'],
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
    oneLiner: 'A rounded “U” base, then a small dip (the handle), then a breakout.',
    story:
      'Price forms a long rounded bottom (the cup) as sentiment slowly turns, returns to the old high, then makes a small pullback (the handle) that shakes out weak hands. A close above the rim confirms.',
    analogy: 'A teacup: the smooth bowl is patient accumulation; the little handle is the last shakeout before the pour. Like a company quietly recovering, then one final dip that scares off doubters before it re-rates.',
    identify: ['A U-shaped (rounded, not V) base.', 'A short handle in the UPPER half of the cup.', 'Breakout is a close above the right rim.'],
    howWeDetect: 'We fit a parabola to the recent base; a positive, well-fit U with a mid-placed bottom, matched rims, and a shallow recent handle (staying in the upper half) → cup with handle.',
    measureRule: 'HALF the cup depth added to the rim (Bulkowski: half-depth hits target ~76% vs 50% for full).',
    stats: { avg: 34, fail: 5, meet: 50, rank: 13 },
    trade: ['Buy the rim breakout; stop below the handle low.'],
    gotchas: ['A V-shaped bottom is NOT a cup — the roundness (patience) is what matters.'],
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
    oneLiner: 'A long, smooth saucer — sentiment slowly turns from down to up.',
    story:
      'A gradual, gently-curving base with no sharp low. Selling fades and buying builds imperceptibly over weeks or months. A close above the right lip confirms the turn.',
    analogy: 'A supertanker turning around — slow, smooth, unstoppable once underway. Like a beaten-down value name where the bad news stops mattering and accumulation quietly builds.',
    identify: ['A smooth, symmetric saucer (best seen on a weekly chart).', 'Breakout is a close above the right lip.'],
    howWeDetect: 'A well-fit upward parabola over a long window with the low near the middle → rounding bottom (a cup without a handle).',
    measureRule: 'Full depth added to the right-lip breakout.',
    stats: { avg: 43, fail: 5, meet: 57, rank: 5 },
    trade: ['Buy the right-lip breakout; patient pattern, patient entry.'],
    gotchas: ['Needs a smooth curve — a jagged base isn’t a rounding bottom.'],
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
    oneLiner: 'Two adjacent tall downward spikes on the weekly chart — a violent V washout.',
    story:
      'On a weekly chart, two side-by-side long downward spikes to about the same low — a capitulation flush followed by an immediate snap-back. Bulkowski ranks it #2 of 23 bullish patterns (best on WEEKLY data). Confirmed by a close above the two-week high.',
    analogy: 'A fire-sale panic where a stock briefly trades below what it’s obviously worth, then buyers pounce — like grabbing a quality item at a two-day clearance before the price resets.',
    identify: ['Two adjacent weekly bars with unusually long downward spikes.', 'Both lows at about the same price.', 'Confirmed by a close above the pattern’s high.'],
    howWeDetect: 'We resample to weekly bars (so Bulkowski’s weekly stats apply), find two adjacent weeks whose range is >1.5× the recent average with matching lows, and confirm on a daily close above the two-week high.',
    measureRule: 'Full height (pattern high − spike low) added to the breakout.',
    stats: { avg: 45, fail: 5, meet: 83, rank: 2 },
    trade: ['Buy the confirmation; stop below the spike low. 83% reach target — high reliability.'],
    gotchas: ['This is a WEEKLY pattern — daily V-spikes alone are much less reliable (which is why we resample).'],
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
    oneLiner: 'Two adjacent tall upward spikes on the weekly chart — a blow-off top.',
    story:
      'The mirror of the pipe bottom: two side-by-side long upward spikes to about the same high, a buying climax that immediately reverses. Confirmed by a close below the two-week low.',
    analogy: 'A mania spike — everyone piles in at the top over two frantic weeks, then reality hits. Like a collectible that briefly spikes on hype and then re-prices down.',
    identify: ['Two adjacent weekly bars with unusually long upward spikes.', 'Both highs at about the same price.', 'Confirmed by a close below the pattern’s low.'],
    howWeDetect: 'Weekly resampling; two adjacent oversized weeks with matching highs; confirm on a close below the two-week low.',
    measureRule: 'Full height subtracted from the breakout.',
    stats: { avg: 20, fail: 11, meet: 70, rank: 4 },
    trade: ['Exit/short on confirmation; stop above the spike high.'],
    gotchas: ['A weekly pattern — treat isolated daily spikes with caution.'],
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
    oneLiner: 'A huge one-day crash, a tempting bounce, then MORE downside. A trap.',
    story:
      'A company shock gaps the stock down 15%+ in a session on huge volume. It then bounces ~28% off the low over about three weeks — which lures bargain hunters. But Bulkowski found price closes BELOW the event low ~67% of the time and falls a further ~18%. The problem rarely fixes in one quarter, so a second leg down is common.',
    analogy:
      '“Even a dead cat bounces if it falls far enough.” The bounce isn’t recovery — it’s the last exit. Buying it is like catching a falling knife: the ₹ looks cheap, but the business just broke, and cheap gets cheaper.',
    identify: ['A single-session decline of ≥15% (usually a gap, huge volume).', 'A partial bounce that then rolls over.', 'A likely close below the event low weeks later.'],
    howWeDetect: 'We flag any recent session where price dropped ≥15% close-to-low. We then SUPPRESS bullish chart patterns on that stock for ~6 months, exactly as Bulkowski advises.',
    measureRule: 'No formal target — expect a further ~18% below the event low; total decline often ~38% from the pre-event close.',
    stats: { avg: 18, fail: null, meet: null, rank: null },
    trade: ['Do NOT buy the bounce. If you hold it, use the bounce to exit.', 'Avoid any bullish setup on the name for ~6 months.'],
    gotchas: ['The bounce is designed to fool you — “it’s so cheap now” is the exact trap.'],
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
