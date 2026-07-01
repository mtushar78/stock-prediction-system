'use client';

/**
 * TutorialView — the browsable chart-pattern learning library. A sidebar lists
 * every pattern (grouped by family); the main panel teaches the selected one
 * with a schematic diagram, the story, a value analogy, how to spot it, how we
 * detect it, the measure rule, Bulkowski's real stats, and how to trade it.
 *
 * Used both in the Tutorial tab and inside TutorialModal.
 */

import { useMemo } from 'react';
import { TUTORIALS, TUTORIAL_ORDER, Tutorial } from '../tutorials';
import PatternSchematic from './PatternSchematic';
import { BookOpen, Target, Search, Cpu, Ruler, TrendingUp, AlertTriangle, Quote, Lightbulb, ExternalLink } from 'lucide-react';

const biasColor = (b: string) => (b === 'bullish' ? '#34d399' : b === 'bearish' ? '#f87171' : '#cbd5e1');

const gradeStat = (label: string, value: number | null, suffix = '', good?: boolean) => (
  <div className="bg-gray-900/60 rounded px-2 py-1.5 text-center">
    <div className="text-[10px] text-gray-500 uppercase tracking-wide">{label}</div>
    <div className={`text-sm font-bold ${good === true ? 'text-emerald-400' : good === false ? 'text-red-400' : 'text-gray-200'}`}>
      {value === null || value === undefined ? '—' : `${value}${suffix}`}
    </div>
  </div>
);

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-xs font-bold text-purple-300 uppercase tracking-wide">
        {icon}
        {title}
      </div>
      <div className="text-sm text-gray-300 leading-relaxed">{children}</div>
    </div>
  );
}

export default function TutorialView({
  activeCode,
  onSelect,
}: {
  activeCode: string;
  onSelect: (code: string) => void;
}) {
  const groups = useMemo(() => {
    const g: Record<string, Tutorial[]> = {};
    TUTORIAL_ORDER.forEach((code) => {
      const t = TUTORIALS[code];
      if (!t) return;
      (g[t.family] ??= []).push(t);
    });
    return g;
  }, []);

  const t = TUTORIALS[activeCode] ?? TUTORIALS[TUTORIAL_ORDER[0]];
  const c = biasColor(t.bias);

  return (
    <div className="flex flex-col md:flex-row gap-4">
      {/* Sidebar */}
      <aside className="md:w-60 shrink-0 space-y-3 md:max-h-[70vh] md:overflow-y-auto pr-1">
        {Object.entries(groups).map(([family, items]) => (
          <div key={family}>
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">{family}</div>
            <div className="space-y-0.5">
              {items.map((it) => (
                <button
                  key={it.code}
                  onClick={() => onSelect(it.code)}
                  className={`w-full text-left px-2 py-1.5 rounded text-sm transition flex items-center gap-2 ${
                    it.code === t.code ? 'bg-purple-800/50 text-white' : 'text-gray-300 hover:bg-gray-800'
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: biasColor(it.bias) }} />
                  {it.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </aside>

      {/* Lesson */}
      <div className="flex-1 min-w-0 space-y-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-2xl font-bold" style={{ color: c }}>
              {t.name}
            </h3>
            <p className="text-gray-400 text-sm">{t.oneLiner}</p>
          </div>
          <span className="text-[11px] px-2 py-1 rounded border" style={{ color: c, borderColor: c + '66' }}>
            {t.bias.toUpperCase()}
          </span>
        </div>

        <div className="grid md:grid-cols-2 gap-4 items-start">
          <PatternSchematic schematic={t.schematic} />
          {/* Bulkowski stats */}
          <div>
            <div className="text-xs font-bold text-purple-300 uppercase tracking-wide mb-1.5 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5" /> Bulkowski track record (bull market)
            </div>
            <div className="grid grid-cols-2 gap-2">
              {gradeStat('Avg move', t.stats.avg, '%', true)}
              {gradeStat('Fail rate', t.stats.fail, '%', t.stats.fail != null ? t.stats.fail <= 10 : undefined)}
              {gradeStat('Hit target', t.stats.meet, '%', t.stats.meet != null ? t.stats.meet >= 60 : undefined)}
              {gradeStat('Rank', t.stats.rank, '', undefined)}
            </div>
            <div className="mt-2 text-[11px] text-gray-500">
              Avg move = typical rise/decline after breakout. Fail rate = % that don’t move even 5%. Hit target = % that reach the
              measure-rule objective. Rank = Bulkowski’s overall performance rank (1 = best).
            </div>
          </div>
        </div>

        {/* Value analogy — highlighted */}
        <div className="bg-gradient-to-r from-purple-950/50 to-gray-900 border border-purple-800/40 rounded-lg p-3 flex gap-2">
          <Quote className="w-4 h-4 text-purple-300 shrink-0 mt-0.5" />
          <div className="text-sm text-purple-100/90 italic">{t.analogy}</div>
        </div>

        <Section icon={<BookOpen className="w-3.5 h-3.5" />} title="What’s happening (the story)">
          {t.story}
        </Section>

        <Section icon={<Search className="w-3.5 h-3.5" />} title="How to spot it">
          <ul className="list-disc pl-5 space-y-1">
            {t.identify.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </Section>

        <Section icon={<Lightbulb className="w-3.5 h-3.5" />} title="Worked examples">
          <div className="space-y-2">
            {t.examples.map((x, i) => (
              <div key={i} className="bg-gray-900/60 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
                {x}
              </div>
            ))}
          </div>
        </Section>

        <div className="grid md:grid-cols-2 gap-4">
          <Section icon={<Cpu className="w-3.5 h-3.5" />} title="How dse-sniper detects it">
            {t.howWeDetect}
          </Section>
          <Section icon={<Ruler className="w-3.5 h-3.5" />} title="Price target (measure rule)">
            {t.measureRule}
          </Section>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <Section icon={<Target className="w-3.5 h-3.5" />} title="How to trade it">
            <ul className="list-disc pl-5 space-y-1">
              {t.trade.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </Section>
          <Section icon={<AlertTriangle className="w-3.5 h-3.5" />} title="Gotchas">
            <ul className="list-disc pl-5 space-y-1 text-amber-200/80">
              {t.gotchas.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </Section>
        </div>

        <Section icon={<ExternalLink className="w-3.5 h-3.5" />} title="Further reading">
          <div className="flex flex-wrap gap-2">
            {t.sources.map((s, i) => (
              <a
                key={i}
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs bg-gray-900/60 border border-gray-700 hover:border-indigo-600 hover:text-indigo-200 text-gray-300 rounded px-2 py-1 transition"
              >
                <ExternalLink className="w-3 h-3" /> {s.title}
              </a>
            ))}
          </div>
        </Section>

        <div className="text-[11px] text-gray-600 pt-1">
          Win-rate statistics are bull-market averages from Thomas Bulkowski, <i>Encyclopedia of Chart Patterns</i> (2nd ed.);
          explanations synthesised from the sources above.
        </div>
      </div>
    </div>
  );
}
