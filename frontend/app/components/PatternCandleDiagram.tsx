'use client';

/**
 * PatternCandleDiagram — renders a tutorial pattern's idealized shape as a clean
 * CANDLESTICK chart (not a line), the way a real chart shows the formation:
 * green/red bodies with wicks tracing the pattern's price path, plus the
 * annotated reference lines (neckline / target / support / resistance / stop),
 * labelled key points and a breakout marker.
 *
 * Candles are synthesised deterministically from the same Schematic spec in
 * tutorials.ts that drove the old line diagram, so every pattern is covered with
 * no extra per-pattern data — we just draw it as candles instead of a stroke.
 */

import { Schematic } from '../tutorials';

const W = 360;
const H = 214;
const PAD_X = 10;
const PAD_TOP = 16;
const PAD_BOT = 26;

const LINE_COLOR: Record<string, string> = {
  neckline: '#f59e0b',
  target: '#22d3ee',
  support: '#10b981',
  resistance: '#ef4444',
  stop: '#f43f5e',
};

const UP = '#34d399';
const DOWN = '#f87171';

// Deterministic 0..1 pseudo-random (no Math.random → stable render, no SSR drift).
const rnd = (i: number, salt: number) => {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
};

// Sample the piecewise-linear price path (points give x,p in 0..1) into n closes.
function samplePath(points: { x: number; p: number }[], n: number): number[] {
  const pts = [...points].sort((a, b) => a.x - b.x);
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const x = n === 1 ? 0 : i / (n - 1);
    let j = 0;
    while (j < pts.length - 2 && pts[j + 1].x < x) j++;
    const a = pts[j];
    const b = pts[Math.min(j + 1, pts.length - 1)];
    const t = b.x === a.x ? 0 : (x - a.x) / (b.x - a.x);
    out.push(a.p + (b.p - a.p) * Math.max(0, Math.min(1, t)));
  }
  return out;
}

interface Candle { open: number; close: number; hi: number; lo: number; up: boolean }

export default function PatternCandleDiagram({ schematic }: { schematic: Schematic }) {
  const N = 32;
  const closes = samplePath(schematic.points, N);

  const candles: Candle[] = closes.map((close, i) => {
    const base = i === 0 ? closes[0] - 0.03 : closes[i - 1];
    const open = base + (rnd(i, 1) - 0.5) * 0.02;
    const bodyH = Math.abs(close - open);
    const hi = Math.max(open, close) + 0.01 + rnd(i, 2) * 0.018 + bodyH * 0.35;
    const lo = Math.min(open, close) - 0.01 - rnd(i, 3) * 0.018 - bodyH * 0.35;
    return { open, close, hi, lo, up: close >= open };
  });

  // Shared vertical domain across candles + reference lines so everything lines up.
  let mn = Infinity;
  let mx = -Infinity;
  candles.forEach((c) => {
    mn = Math.min(mn, c.lo);
    mx = Math.max(mx, c.hi);
  });
  (schematic.lines ?? []).forEach((l) => {
    mn = Math.min(mn, l.p);
    mx = Math.max(mx, l.p);
  });
  if (schematic.breakout) {
    mn = Math.min(mn, schematic.breakout.p);
    mx = Math.max(mx, schematic.breakout.p);
  }
  const pad = (mx - mn) * 0.08 || 0.1;
  mn -= pad;
  mx += pad;

  const plotW = W - 2 * PAD_X;
  const sx = (xf: number) => PAD_X + xf * plotW;
  const sy = (p: number) => PAD_TOP + (1 - (p - mn) / (mx - mn)) * (H - PAD_TOP - PAD_BOT);
  const cw = Math.max(3.2, (plotW / N) * 0.62);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto rounded bg-[#0b1220] border border-gray-700">
      {/* baseline grid */}
      {[0.25, 0.5, 0.75].map((g) => (
        <line key={g} x1={PAD_X} x2={W - PAD_X} y1={PAD_TOP + g * (H - PAD_TOP - PAD_BOT)} y2={PAD_TOP + g * (H - PAD_TOP - PAD_BOT)} stroke="#141c2b" strokeWidth={1} />
      ))}

      {/* reference lines (neckline / target / support / resistance) */}
      {(schematic.lines ?? []).map((ln, i) => {
        const y = sy(ln.p);
        const c = LINE_COLOR[ln.kind] ?? '#9ca3af';
        return (
          <g key={i}>
            <line x1={PAD_X} x2={W - PAD_X} y1={y} y2={y} stroke={c} strokeWidth={1.3} strokeDasharray="5 4" />
            <text x={W - PAD_X} y={y - 3} textAnchor="end" fontSize={10} fill={c} className="font-semibold">
              {ln.label}
            </text>
          </g>
        );
      })}

      {/* candlesticks */}
      {candles.map((c, i) => {
        const x = sx(i / (N - 1));
        const color = c.up ? UP : DOWN;
        const bodyTop = sy(Math.max(c.open, c.close));
        const bodyBot = sy(Math.min(c.open, c.close));
        const bodyH = Math.max(1.4, bodyBot - bodyTop);
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={sy(c.hi)} y2={sy(c.lo)} stroke={color} strokeWidth={1} />
            <rect x={x - cw / 2} y={bodyTop} width={cw} height={bodyH} fill={color} rx={0.5} />
          </g>
        );
      })}

      {/* breakout marker */}
      {schematic.breakout && (
        <g>
          <circle cx={sx(schematic.breakout.x)} cy={sy(schematic.breakout.p)} r={5} fill="none" stroke="#e5e7eb" strokeWidth={1.4} />
          <text x={sx(schematic.breakout.x)} y={sy(schematic.breakout.p) - 8} textAnchor="middle" fontSize={9} fill="#e5e7eb">
            breakout
          </text>
        </g>
      )}

      {/* labelled key points */}
      {(schematic.dots ?? []).map((d, i) => {
        const x = sx(d.x);
        const y = sy(d.p);
        const below = d.p > 0.5;
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={3.4} fill="#facc15" stroke="#0b1220" strokeWidth={1} />
            <text x={x} y={below ? y + 14 : y - 8} textAnchor="middle" fontSize={9.5} fill="#cbd5e1">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
