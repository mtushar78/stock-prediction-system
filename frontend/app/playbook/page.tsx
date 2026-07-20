'use client';

/**
 * /playbook — the graphical "how do I actually trade with this app" guide.
 *
 * A visual, followable version of docs/TRADING_PLAYBOOK.md, extended with the
 * pages shipped since it was written (Momentum, Coils, Rebounds, News). Every
 * number on this page comes from the point-in-time, cost-adjusted backtests
 * (PROFITABILITY_AUDIT, weekly_system_study*, backtest_momentum, backtest_coil).
 *
 * Sections: live season banner → the weekly decision flowchart → where the
 * money actually is (evidence bars) → what each page is for → position-size
 * calculator → exit rules → the 7 hard rules → honest limits.
 */

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  BookOpen,
  Sprout,
  ShieldCheck,
  TrendingUp,
  Zap,
  Rocket,
  Landmark,
  Radar,
  Activity,
  Calculator,
  Target,
  OctagonX,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ArrowDown,
} from 'lucide-react';
import MarketHealthMeter, { MarketHealth } from '../components/MarketHealthMeter';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/* ------------------------------------------------------------------ */
/* Small building blocks                                              */
/* ------------------------------------------------------------------ */

function SectionTitle({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-2.5 text-lg font-bold text-white mt-10 mb-3">
      <span className="w-7 h-7 rounded-full bg-sky-600 text-white text-sm flex items-center justify-center shrink-0">
        {n}
      </span>
      {children}
    </h2>
  );
}

function FlowArrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center py-1 text-gray-500">
      {label && <span className="text-[11px] text-gray-400 mb-0.5">{label}</span>}
      <ArrowDown className="w-4 h-4" />
    </div>
  );
}

/** One horizontal evidence bar. Scale: ±10% net per trade fills the track. */
function EvidenceBar({
  label,
  sub,
  value,
  unit = '% net / trade',
}: {
  label: string;
  sub: string;
  value: number;
  unit?: string;
}) {
  const pct = Math.min(Math.abs(value) / 10, 1) * 50; // half-track each side of 0
  const pos = value >= 0;
  return (
    <div className="py-1.5">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-200 font-semibold">{label}</span>
        <span className={`font-bold ${pos ? (value > 1 ? 'text-emerald-400' : 'text-gray-400') : 'text-red-400'}`}>
          {value > 0 ? '+' : ''}
          {value}
          {unit && <span className="font-normal text-gray-500 ml-1">{unit}</span>}
        </span>
      </div>
      <div className="relative h-3 bg-gray-800 rounded overflow-hidden">
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-600" />
        <div
          className={`absolute top-0 bottom-0 ${pos ? 'bg-emerald-500' : 'bg-red-500'}`}
          style={pos ? { left: '50%', width: `${pct}%` } : { right: '50%', width: `${pct}%` }}
        />
      </div>
      <div className="text-[11px] text-gray-500 mt-0.5">{sub}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                               */
/* ------------------------------------------------------------------ */

const fmtBDT = (n: number) => `৳${Math.round(n).toLocaleString('en-US')}`;

export default function PlaybookPage() {
  const [market, setMarket] = useState<MarketHealth | null>(null);
  const [capital, setCapital] = useState(500000);

  useEffect(() => {
    axios.get(`${API_URL}/api/market-health`).then((r) => setMarket(r.data)).catch(() => {});
  }, []);

  const isReversal = market?.season === 'REVERSAL' || (market?.breadth_pct != null && market.breadth_pct < 45);

  const sizing = useMemo(() => {
    const risk = capital * 0.01; // never lose more than 1% per trade
    const pos = risk / 0.1; //     against the −10% reversal stop → 10% position
    return { risk, pos };
  }, [capital]);

  return (
    <main className="max-w-4xl mx-auto px-4 py-6 text-gray-300">
      {/* ---------------------------------------------------------- */}
      {/* Hero                                                        */}
      {/* ---------------------------------------------------------- */}
      <div className="flex items-center gap-2 mb-1">
        <BookOpen className="w-6 h-6 text-sky-400" />
        <h1 className="text-2xl font-bold text-white">The Playbook</h1>
      </div>
      <p className="text-sm text-gray-400 mb-4">
        How to actually make money with this app — one picture at a time. Every number below is from
        your own 14-year, cost-adjusted DSE backtests, not theory.
      </p>

      <div className="border border-sky-700/50 bg-sky-950/30 rounded p-4 mb-5">
        <div className="text-sky-300 text-xs font-bold uppercase tracking-wide mb-1">The whole game in one sentence</div>
        <p className="text-white font-semibold leading-relaxed">
          You are a part-time <span className="text-emerald-400">seasonal</span> swing trader. You make money a few
          times a year by <span className="text-emerald-400">buying panic</span>, and you protect money the rest of
          the time by <span className="text-amber-400">doing almost nothing</span>.
        </p>
      </div>

      {/* Live season — step 0, answered for today */}
      <SectionTitle n={1}>What season is it — right now?</SectionTitle>
      <p className="text-sm mb-3">
        The market has two seasons, measured by <b className="text-gray-100">breadth</b> (% of liquid stocks above
        their 50-day average). This is the <b className="text-gray-100">master switch</b> — check it before anything
        else. Here is today&apos;s reading, live:
      </p>
      <MarketHealthMeter data={market} />
      {market && (
        <p className="text-xs text-gray-500 -mt-2 mb-2">
          {isReversal
            ? 'Hunting season is OPEN — follow the green branch below.'
            : 'Hunting season is CLOSED — follow the amber branch below. Doing nothing is the correct move.'}
        </p>
      )}

      {/* ---------------------------------------------------------- */}
      {/* The flowchart                                               */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={2}>Your whole routine, as a map (15 min, 1–2× a week)</SectionTitle>
      <p className="text-sm mb-4">
        You do <b className="text-gray-100">not</b> watch the screen daily — the app rings the 🔔 season bell when
        hunting opens. When you do sit down, this is the entire decision tree:
      </p>

      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40">
        {/* Start */}
        <div className="mx-auto w-fit px-4 py-2 rounded-full bg-gray-800 border border-gray-700 text-white text-sm font-semibold">
          Open the dashboard
        </div>
        <FlowArrow />
        <div className="mx-auto w-fit px-4 py-2 rounded bg-sky-900/50 border border-sky-700 text-sky-200 text-sm font-bold text-center">
          Look at the SEASON banner — what colour is it?
        </div>

        {/* Two branches */}
        <div className="grid md:grid-cols-2 gap-4 mt-4">
          {/* Reversal branch */}
          <div className={`rounded-lg border p-3 ${isReversal ? 'border-emerald-500 bg-emerald-950/30 ring-1 ring-emerald-500/40' : 'border-emerald-800/60 bg-emerald-950/10'}`}>
            <div className="flex items-center gap-2 font-bold text-emerald-300 mb-1">
              <Sprout className="w-4 h-4" /> 🌱 GREEN — Reversal season (breadth &lt; 45%)
              {isReversal && <span className="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded-full">TODAY</span>}
            </div>
            <div className="text-[11px] text-emerald-200/70 mb-2">
              Fear is high, stocks are oversold. This is when the money is made: +2.5% to +7.9% net per trade
              (sweet spot: breadth 30–45% → <b>+7.9% net, 74% win</b>).
            </div>
            <ol className="space-y-1.5 text-sm">
              {[
                ['Open the Reversals list', 'the only list you buy from'],
                ['Pick 2–4 names: Grade A/B, prefer DEEP VALUE', 'skip anything tagged THIN'],
                ['Size each at ~10% of capital', 'calculator in §5 below'],
                ['Place the buys, then set stop −10% / target +25% / 20-day time stop', 'all three, immediately'],
                ['Write each trade in your journal, close the app', 'done hunting'],
              ].map(([step, note], i) => (
                <li key={i} className="flex gap-2">
                  <span className="w-5 h-5 shrink-0 rounded-full bg-emerald-700 text-white text-[11px] flex items-center justify-center mt-0.5">{i + 1}</span>
                  <span>
                    <span className="text-gray-100">{step}</span>
                    <span className="text-gray-500 text-xs"> — {note}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>

          {/* Preservation branch */}
          <div className={`rounded-lg border p-3 ${!isReversal && market ? 'border-amber-500 bg-amber-950/30 ring-1 ring-amber-500/40' : 'border-amber-800/60 bg-amber-950/10'}`}>
            <div className="flex items-center gap-2 font-bold text-amber-300 mb-1">
              <ShieldCheck className="w-4 h-4" /> 🛡️ AMBER — Preservation season (breadth ≥ 45%)
              {!isReversal && market && <span className="text-[10px] bg-amber-600 text-white px-1.5 py-0.5 rounded-full">TODAY</span>}
            </div>
            <div className="text-[11px] text-amber-200/70 mb-2">
              The market is strong and everything looks buyable — that&apos;s the trap. The same reversal buys net
              <b> ≈ 0%</b> here. Your job is protecting capital, not finding trades.
            </div>
            <ol className="space-y-1.5 text-sm">
              {[
                ['Check the red Alerts box', 'a stop or target hit = act today'],
                ['Glance at open positions vs their stops/targets', 'trail winners, honour exits'],
                ['Optional: Momentum page — ⚡ TRIGGER in Stage-2 only', 'the one buy that works in strong tape (§4)'],
                ['Tempted by anything else? Add it to the watchlist instead', 'Coils / Rebounds hold it for next season'],
                ['Close the app', 'cash is a position — sitting out IS the strategy'],
              ].map(([step, note], i) => (
                <li key={i} className="flex gap-2">
                  <span className="w-5 h-5 shrink-0 rounded-full bg-amber-700 text-white text-[11px] flex items-center justify-center mt-0.5">{i + 1}</span>
                  <span>
                    <span className="text-gray-100">{step}</span>
                    <span className="text-gray-500 text-xs"> — {note}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="mt-4 text-center text-xs text-gray-500">
          That&apos;s the entire loop. Dry spells of weeks with zero buys are <b className="text-gray-300">normal and correct</b> —
          your test showed forcing a trade every week loses 20–36% of capital per year.
        </div>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Evidence                                                    */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={3}>Where the money actually is (your backtests, net of costs)</SectionTitle>
      <p className="text-sm mb-2">
        Why the map above looks the way it does. Green bars are real edges; red bars are what the app
        deliberately stops you from doing. DSE round-trip costs ≈ 1–1.5%, so an edge must clear that.
      </p>
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40">
        <EvidenceBar
          label="🌱 Reversals in weak tape (breadth 30–45%)"
          sub="THE edge. 74% win rate; 68% win overall in season, Grade A ≈ 82%. Happens in clusters a few times a year."
          value={7.9}
        />
        <EvidenceBar
          label="⚡ Momentum: daily TRIGGER inside monthly Stage-2"
          sub="+8.2% over 3 months vs +2.1% for the universe. The ONLY validated buy in strong tape. Stage label alone = no edge."
          value={8.2}
          unit="% gross / 3 mo"
        />
        <EvidenceBar
          label="Breakouts list"
          sub="≈ breakeven after costs. That is why it's a watchlist, not a buy list."
          value={0.3}
        />
        <EvidenceBar
          label="Confirmed chart patterns (Chart Analyst)"
          sub="24,781 point-in-time tests: same as buying a random stock. Read charts for context — never buy off them."
          value={-1.0}
        />
        <EvidenceBar
          label="Stage-3 / topping stocks"
          sub="−7.1% over 6 months. The stage labels exist to keep you OUT of these."
          value={-7.1}
          unit="% / 6 mo"
        />
        <EvidenceBar
          label="Forcing a trade every week (any method)"
          sub="Commission grinds you down while the average stock goes nowhere. Overtrading is the most expensive mistake available."
          value={-28}
          unit="% of capital / year"
        />
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Page roles                                                  */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={4}>Every page has exactly one job</SectionTitle>
      <p className="text-sm mb-3">
        The menu is a funnel: two pages you <b className="text-emerald-300">BUY</b> from, three you{' '}
        <b className="text-sky-300">WATCH</b>, one you <b className="text-violet-300">INVEST</b> from, and the rest
        is <b className="text-gray-400">CONTEXT</b>. If you remember nothing else, remember which badge is on which page.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        {[
          {
            icon: TrendingUp, name: 'Dashboard → Reversals list', badge: 'BUY', badgeCls: 'bg-emerald-600',
            note: 'Your primary buy list — in 🌱 season only. Sort by grade, prefer DEEP VALUE, skip THIN. 68% win, Grade A ≈ 82%.',
          },
          {
            icon: Zap, name: 'Momentum', badge: 'BUY (trigger only)', badgeCls: 'bg-emerald-700',
            note: 'Monthly-locked Stage-2 watchlist. Buy ONLY the ⚡ TRIGGER-in-Stage-2 rows (+8%/3mo). The stage label alone is context; Stage 3/4 = stay away.',
          },
          {
            icon: Sprout, name: 'Coiled Springs', badge: 'WATCH', badgeCls: 'bg-sky-600',
            note: 'Winner-DNA screen: tight quiet bases above the 200-day. The launch trigger is invisible in the chart — so it’s a watch-daily list with alerts, never an automatic buy.',
          },
          {
            icon: Rocket, name: 'Rebounds', badge: 'WATCH', badgeCls: 'bg-sky-600',
            note: 'Beaten-down stocks just turning up. Candidates for the next reversal cluster — a feeder list, not a signal.',
          },
          {
            icon: Radar, name: 'News & Rumors', badge: 'WATCH', badgeCls: 'bg-sky-600',
            note: 'DSE query/halt notices + unusual-activity radar. Explains why something on your watchlist is suddenly moving.',
          },
          {
            icon: Landmark, name: 'Long-Term', badge: 'INVEST', badgeCls: 'bg-violet-600',
            note: 'Dividend Fortress — different money, different clock (years). Decide your split (e.g. 60% long-term / 30% swing / 10% cash) and never let one bucket raid the other. Best time to add: reversal season, when yields are fat.',
          },
          {
            icon: Activity, name: 'Chart Analyst / Manual Analyze', badge: 'CONTEXT ONLY', badgeCls: 'bg-gray-600',
            note: 'For understanding structure, support/resistance and risk tags. Patterns carry NO buy edge on DSE — looking is free, buying off them is not.',
          },
          {
            icon: Calculator, name: 'Time Machine (date bar)', badge: 'TRAINING', badgeCls: 'bg-gray-600',
            note: 'Rewind to a past selloff and watch what the Reversals list looked like. Free practice between seasons.',
          },
        ].map((p) => (
          <div key={p.name} className="border border-gray-800 rounded-lg p-3 bg-gray-900/40">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="flex items-center gap-2 font-semibold text-gray-100 text-sm">
                <p.icon className="w-4 h-4 text-gray-400 shrink-0" /> {p.name}
              </span>
              <span className={`text-[10px] font-bold text-white px-1.5 py-0.5 rounded ${p.badgeCls} shrink-0`}>{p.badge}</span>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">{p.note}</p>
          </div>
        ))}
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Sizing calculator                                           */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={5}>How much to buy (use this every time)</SectionTitle>
      <p className="text-sm mb-3">
        One rule: <b className="text-gray-100">never let a single trade lose more than 1% of your total money</b>.
        With the −10% reversal stop, that works out to a ~10% position. Type your capital:
      </p>
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40">
        <label className="text-xs text-gray-400 block mb-1">Your total trading capital (৳)</label>
        <input
          type="number"
          value={capital}
          min={0}
          step={10000}
          onChange={(e) => setCapital(Math.max(0, Number(e.target.value)))}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white w-48 mb-4"
        />
        <div className="grid sm:grid-cols-3 gap-3 mb-4">
          <div className="border border-red-800/60 bg-red-950/20 rounded p-3 text-center">
            <div className="text-[11px] text-gray-400 mb-1">Max loss per trade (1%)</div>
            <div className="text-lg font-bold text-red-300">{fmtBDT(sizing.risk)}</div>
            <div className="text-[11px] text-gray-500">what the −10% stop costs you</div>
          </div>
          <div className="border border-emerald-800/60 bg-emerald-950/20 rounded p-3 text-center">
            <div className="text-[11px] text-gray-400 mb-1">Position size per stock</div>
            <div className="text-lg font-bold text-emerald-300">{fmtBDT(sizing.pos)}</div>
            <div className="text-[11px] text-gray-500">= 1% risk ÷ 10% stop = 10% of capital</div>
          </div>
          <div className="border border-sky-800/60 bg-sky-950/20 rounded p-3 text-center">
            <div className="text-[11px] text-gray-400 mb-1">A full reversal cluster (2–4 buys)</div>
            <div className="text-lg font-bold text-sky-300">{fmtBDT(sizing.pos * 2)} – {fmtBDT(sizing.pos * 4)}</div>
            <div className="text-[11px] text-gray-500">deployed; the rest stays cash</div>
          </div>
        </div>
        {/* Allocation bar */}
        <div className="text-[11px] text-gray-400 mb-1">What full deployment looks like (max 4 positions):</div>
        <div className="flex h-8 rounded overflow-hidden border border-gray-700 text-[10px] font-bold text-white">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-emerald-600 border-r border-gray-900 flex items-center justify-center" style={{ width: '10%' }}>
              #{i}
            </div>
          ))}
          <div className="bg-gray-700 flex-1 flex items-center justify-center text-gray-300">CASH — 60% (yes, really)</div>
        </div>
        <div className="mt-3 flex items-start gap-2 text-xs text-amber-300/90 bg-amber-950/20 border border-amber-800/50 rounded p-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Liquidity check before every buy: if the app tags a stock <b>THIN</b>, skip it. On any stock, keep your
            order under ~10–20% of its average daily volume, or your own buying moves the price against you. And
            remember DSE settles <b>T+2</b> — shares you buy can&apos;t be sold for ~3 days.
          </span>
        </div>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Exits                                                       */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={6}>Exits: decide all three the moment you buy</SectionTitle>
      <p className="text-sm mb-3">Never improvise an exit. Every reversal buy gets all three, written down, on day one:</p>
      <div className="grid sm:grid-cols-3 gap-3">
        <div className="border border-red-700/60 bg-red-950/20 rounded-lg p-4 text-center">
          <OctagonX className="w-6 h-6 text-red-400 mx-auto mb-1" />
          <div className="font-bold text-red-300 text-xl">−10%</div>
          <div className="text-xs text-gray-300 font-semibold mb-1">Stop loss</div>
          <div className="text-[11px] text-gray-500">Wide on purpose — a reversal is a falling knife by design.</div>
        </div>
        <div className="border border-emerald-700/60 bg-emerald-950/20 rounded-lg p-4 text-center">
          <Target className="w-6 h-6 text-emerald-400 mx-auto mb-1" />
          <div className="font-bold text-emerald-300 text-xl">+25%</div>
          <div className="text-xs text-gray-300 font-semibold mb-1">Target</div>
          <div className="text-[11px] text-gray-500">Where reversals historically run to.</div>
        </div>
        <div className="border border-sky-700/60 bg-sky-950/20 rounded-lg p-4 text-center">
          <Clock className="w-6 h-6 text-sky-400 mx-auto mb-1" />
          <div className="font-bold text-sky-300 text-xl">20 days</div>
          <div className="text-xs text-gray-300 font-semibold mb-1">Time stop</div>
          <div className="text-[11px] text-gray-500">Not working in ~4 weeks? Thesis is stale — free the capital.</div>
        </div>
      </div>
      <div className="mt-3 border border-red-800/60 bg-red-950/30 rounded p-3 text-sm text-red-200 font-semibold text-center">
        ☠️ Iron rule: NEVER average down. Oversold can always get more oversold — the stop takes you out, period.
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Hard rules                                                  */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={7}>The 7 hard rules (print these)</SectionTitle>
      <div className="border border-gray-800 rounded-lg divide-y divide-gray-800 bg-gray-900/40">
        {[
          'Check the season first. Green = hunt, amber = protect. Nothing matters more.',
          'Buy panic, not strength. Never chase what is already up.',
          'Never risk more than 1% of capital per trade (≈10% position vs a −10% stop).',
          'Set stop, target and time-stop the moment you buy. Never improvise an exit.',
          'Never average down. Let the stop do its job.',
          'Charts are for looking; the Reversals list (and ⚡ Stage-2 triggers) are for buying.',
          'Doing nothing is a valid — often the correct — move. Cash is a position.',
        ].map((r, i) => (
          <div key={i} className="flex items-center gap-3 p-3 text-sm">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="text-gray-200">
              <b className="text-gray-500 mr-1.5">{i + 1}.</b>
              {r}
            </span>
          </div>
        ))}
      </div>

      {/* ---------------------------------------------------------- */}
      {/* Honest limits                                                */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={8}>The honest fine print</SectionTitle>
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40 text-sm space-y-2 mb-10">
        <p>
          • This will <b className="text-gray-100">not</b> give you a trade every day or week. Weeks-long dry spells
          are the system working, not failing.
        </p>
        <p>
          • Realistically this is <b className="text-gray-100">modest, part-time, seasonal income</b> — not a salary.
          Do not quit your job for it.
        </p>
        <p>
          • The +3–8% per trade figures are backtests. <b className="text-gray-100">Prove it with small real money
          first</b>: log every trade (date, season, entry, exits, grade, followed-plan?). After 15–20 trades, if your
          real net per trade is near +3%, the edge is real for you — scale up slowly. If not, stay small and find out
          why (usually: traded out of season, or ignored a stop).
        </p>
        <p className="text-gray-500 text-xs pt-1">
          Sources: docs/TRADING_PLAYBOOK.md · PROFITABILITY_AUDIT.md · MOMENTUM_STRATEGY.md · WINNER_ANATOMY.md ·
          LONG_TERM_STRATEGY.md — all reproducible via the backtest scripts listed in each.
        </p>
      </div>
    </main>
  );
}
