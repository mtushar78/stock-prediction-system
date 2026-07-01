'use client';

/**
 * PatternSchematic — renders a tutorial pattern's idealized shape as an
 * annotated SVG: the price path, horizontal reference lines (neckline /
 * target / support / resistance), labelled key points, and a breakout marker.
 * Driven entirely by the Schematic spec in tutorials.ts.
 */

import { Schematic } from '../tutorials';

const W = 340;
const H = 190;
const PAD_X = 12;
const PAD_TOP = 16;
const PAD_BOT = 22;

const LINE_COLOR: Record<string, string> = {
  neckline: '#f59e0b',
  target: '#22d3ee',
  support: '#10b981',
  resistance: '#ef4444',
  stop: '#f43f5e',
};

const sx = (x: number) => PAD_X + x * (W - 2 * PAD_X);
const sy = (p: number) => PAD_TOP + (1 - p) * (H - PAD_TOP - PAD_BOT);

export default function PatternSchematic({ schematic }: { schematic: Schematic }) {
  const path = schematic.points.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${sx(pt.x).toFixed(1)} ${sy(pt.p).toFixed(1)}`).join(' ');
  const priceColor =
    schematic.bias === 'bullish' ? '#34d399' : schematic.bias === 'bearish' ? '#f87171' : '#cbd5e1';

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto rounded bg-[#0b1220] border border-gray-700">
      {/* subtle baseline grid */}
      {[0.25, 0.5, 0.75].map((g) => (
        <line key={g} x1={PAD_X} x2={W - PAD_X} y1={sy(g)} y2={sy(g)} stroke="#1f2937" strokeWidth={1} />
      ))}

      {/* horizontal reference lines */}
      {(schematic.lines ?? []).map((ln, i) => {
        const y = sy(ln.p);
        const c = LINE_COLOR[ln.kind] ?? '#9ca3af';
        return (
          <g key={i}>
            <line x1={PAD_X} x2={W - PAD_X} y1={y} y2={y} stroke={c} strokeWidth={1.4} strokeDasharray="5 4" />
            <text x={W - PAD_X} y={y - 3} textAnchor="end" fontSize={10} fill={c} className="font-semibold">
              {ln.label}
            </text>
          </g>
        );
      })}

      {/* the price path */}
      <path d={path} fill="none" stroke={priceColor} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />

      {/* breakout marker */}
      {schematic.breakout && (
        <g>
          <circle cx={sx(schematic.breakout.x)} cy={sy(schematic.breakout.p)} r={5} fill="none" stroke="#e5e7eb" strokeWidth={1.5} />
          <text x={sx(schematic.breakout.x)} y={sy(schematic.breakout.p) - 8} textAnchor="middle" fontSize={9} fill="#e5e7eb">
            breakout
          </text>
        </g>
      )}

      {/* labelled key points */}
      {(schematic.dots ?? []).map((d, i) => {
        const x = sx(d.x);
        const y = sy(d.p);
        const below = d.p > 0.5; // put label below if the dot is high up, above if low
        return (
          <g key={i}>
            <circle cx={x} cy={y} r={3.5} fill={priceColor} stroke="#0b1220" strokeWidth={1} />
            <text
              x={x}
              y={below ? y + 14 : y - 8}
              textAnchor="middle"
              fontSize={9.5}
              fill="#9ca3af"
            >
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
