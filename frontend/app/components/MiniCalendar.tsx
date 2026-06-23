'use client';

import { useState, useEffect, useRef } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  value: string;                 // YYYY-MM-DD (selected/pending)
  min?: string;
  max?: string;
  tradingDays: Set<string>;      // selectable days
  analyzedDays: Set<string>;     // already-cached days (marked green)
  disabled?: boolean;
  onChange: (d: string) => void;
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];
const WD = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const pad = (n: number) => String(n).padStart(2, '0');
const ymd = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`;

/** Themed, dependency-free month calendar. Analyzed days show a green dot/tint;
 *  non-trading days are dimmed and unclickable. Picking a day only sets the
 *  value — running the analysis stays on the Analyze button. */
export default function MiniCalendar({ value, min, max, tradingDays, analyzedDays, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const base = valid ? value : (max || '');

  const [vy, setVy] = useState<number>(base ? +base.slice(0, 4) : 2026);
  const [vm, setVm] = useState<number>(base ? +base.slice(5, 7) : 1); // 1-12

  // Re-center on the selected month when value changes (e.g. Prev/Next).
  useEffect(() => {
    if (base) { setVy(+base.slice(0, 4)); setVm(+base.slice(5, 7)); }
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);

  const firstWd = new Date(vy, vm - 1, 1).getDay();
  const dim = new Date(vy, vm, 0).getDate();
  const cells: (number | null)[] = [...Array(firstWd).fill(null), ...Array.from({ length: dim }, (_, i) => i + 1)];
  const ymPrefix = `${vy}-${pad(vm)}`;
  const canPrev = !min || ymPrefix > min.slice(0, 7);
  const canNext = !max || ymPrefix < max.slice(0, 7);
  const stepMonth = (dir: number) => {
    let m = vm + dir, y = vy;
    if (m < 1) { m = 12; y--; } if (m > 12) { m = 1; y++; }
    setVy(y); setVm(m);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="bg-gray-900 border border-gray-600 rounded px-2.5 py-1 text-gray-100 flex items-center gap-2 hover:border-gray-500 disabled:opacity-40"
      >
        <CalendarDays className="w-4 h-4 text-gray-400" />
        <span className="tabular-nums">{value || 'pick a date'}</span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl p-3">
          <div className="flex items-center justify-between mb-2">
            <button disabled={!canPrev} onClick={() => stepMonth(-1)}
              className="p-1 rounded hover:bg-gray-700 disabled:opacity-30"><ChevronLeft className="w-4 h-4" /></button>
            <span className="text-sm font-bold text-gray-200">{MONTHS[vm - 1]} {vy}</span>
            <button disabled={!canNext} onClick={() => stepMonth(1)}
              className="p-1 rounded hover:bg-gray-700 disabled:opacity-30"><ChevronRight className="w-4 h-4" /></button>
          </div>

          <div className="grid grid-cols-7 gap-1 text-[10px] text-gray-500 mb-1">
            {WD.map((w) => <div key={w} className="text-center">{w}</div>)}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {cells.map((d, i) => {
              if (d === null) return <div key={i} />;
              const ds = ymd(vy, vm, d);
              const inRange = (!min || ds >= min) && (!max || ds <= max);
              const trading = tradingDays.has(ds);
              const analyzed = analyzedDays.has(ds);
              const selected = ds === value;
              const clickable = trading && inRange && !disabled;
              let cls = 'h-8 rounded text-xs flex items-center justify-center relative transition-colors ';
              if (selected) cls += 'bg-amber-600 text-white font-bold';
              else if (analyzed && clickable) cls += 'bg-emerald-800/50 text-emerald-200 hover:bg-emerald-700';
              else if (clickable) cls += 'text-gray-200 hover:bg-gray-700';
              else cls += 'text-gray-700 cursor-not-allowed';
              return (
                <button
                  key={i}
                  disabled={!clickable}
                  onClick={() => { onChange(ds); setOpen(false); }}
                  className={cls}
                  title={trading ? (analyzed ? `${ds} — analyzed (instant)` : `${ds} — trading day`) : `${ds} — no trading`}
                >
                  {d}
                  {analyzed && !selected && <span className="absolute bottom-1 w-1 h-1 rounded-full bg-emerald-400" />}
                </button>
              );
            })}
          </div>

          <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-500 border-t border-gray-700 pt-2">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> analyzed · instant</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-amber-600 inline-block" /> selected</span>
          </div>
        </div>
      )}
    </div>
  );
}
