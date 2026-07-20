'use client';

/**
 * /playbook — the graphical "how do I actually trade with this app" guide.
 *
 * A visual, followable version of docs/TRADING_PLAYBOOK.md, extended with the
 * pages shipped since it was written (Momentum, Coils, Rebounds, News). Every
 * number on this page comes from the point-in-time, cost-adjusted backtests
 * (PROFITABILITY_AUDIT, weekly_system_study*, backtest_momentum, backtest_coil).
 *
 * ORDERING (2026-07-20): lead with the strong-tape swing play (Momentum ⚡
 * Stage-2 trigger) because most weeks you are NOT in a reversal cluster, so that
 * is the more-often-live edge. Reversal is kept as the highest-edge premium
 * event. Long-term dividend bucket is the year-round engine underneath both.
 *
 * Sections: live season → your move today → the two swing plays → the always-on
 * engine → weekly routine map → evidence bars → page roles → sizing → exits →
 * hard rules → honest limits.
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
  CalendarDays,
  TrendingDown,
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
    const pos = risk / 0.1; //     against the −10% stop → 10% position
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
          You have <span className="text-emerald-400">two validated swing plays</span> — one for each market season —
          and a <span className="text-violet-400">long-term dividend bucket</span> compounding underneath both.
          Your only job each week: know which play is <span className="text-emerald-400">live</span>, trade{' '}
          <span className="text-emerald-400">only that one</span>, and never force a trade when neither is firing.
        </p>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* §1 — Live season + your move today                          */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={1}>What season is it — and what&apos;s your move today?</SectionTitle>
      <p className="text-sm mb-3">
        The market has two seasons, measured by <b className="text-gray-100">breadth</b> (% of liquid stocks above
        their 50-day average). Breadth decides <b className="text-gray-100">which of your two plays is live</b>. Here
        is today&apos;s reading, straight from the app:
      </p>
      <MarketHealthMeter data={market} />

      {market && (
        <div
          className={`rounded-lg border p-4 -mt-1 ${
            isReversal ? 'border-emerald-600/60 bg-emerald-950/20' : 'border-indigo-600/60 bg-indigo-950/20'
          }`}
        >
          <div className="text-[11px] uppercase tracking-wide font-bold mb-1 text-gray-400">Your live play right now</div>
          {isReversal ? (
            <p className="text-sm text-emerald-100">
              🌱 <b>Reversal season is OPEN</b> — this is the rare, high-edge window. Go to the{' '}
              <b>Dashboard → Reversals list</b>, buy 2–4 Grade A/B panic names, and add to your long-term fortress
              stocks while they&apos;re cheap. This is the play that pays the most; use it while it&apos;s here.
            </p>
          ) : (
            <p className="text-sm text-indigo-100">
              🛡️ <b>Preservation season</b> — no reversal edge today. Your live play is the{' '}
              <b>Momentum ⚡ Stage-2 trigger</b>: open the Momentum page, filter to <b>⚡ Setup</b>. If a row is
              lit, that&apos;s a legitimate buy (+8%/3mo in testing). If none are lit, you buy nothing today and add
              to the long-term bucket instead. <b>Both are correct outcomes.</b>
            </p>
          )}
        </div>
      )}

      {/* ---------------------------------------------------------- */}
      {/* §2 — The two swing plays                                    */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={2}>Your two swing plays (one per season)</SectionTitle>
      <p className="text-sm mb-4">
        These are the only two buy signals that survived honest, cost-adjusted testing on DSE. Play A is live{' '}
        <b className="text-gray-100">most of the time</b> (strong tape is the common state); Play B is{' '}
        <b className="text-gray-100">rarer but pays the most</b>. You never run both at once — the season tells you which.
      </p>

      <div className="grid md:grid-cols-2 gap-4">
        {/* PLAY A — Momentum trigger (leads: more often live) */}
        <div className="rounded-lg border border-indigo-600/60 bg-indigo-950/20 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="flex items-center gap-2 font-bold text-indigo-200">
              <Zap className="w-5 h-5" /> Play A — Momentum ⚡ Trigger
            </span>
            <span className="text-[10px] font-bold text-white bg-indigo-600 px-2 py-0.5 rounded-full">MOST WEEKS</span>
          </div>
          <dl className="text-xs space-y-2">
            <div>
              <dt className="text-gray-400">When it&apos;s live</dt>
              <dd className="text-gray-100">🛡️ Strong tape (breadth ≥ 45%) — the market&apos;s usual state.</dd>
            </div>
            <div>
              <dt className="text-gray-400">What you buy</dt>
              <dd className="text-gray-100">
                Momentum page → <b>⚡ Setup</b> filter: a stock breaking its 20-day high on ≥1.5× volume{' '}
                <b>while inside a monthly Stage-2 advance</b>. Nothing else on that page — a raw trigger without
                Stage-2 barely beats costs.
              </dd>
            </div>
            <div>
              <dt className="text-gray-400">The edge</dt>
              <dd className="text-emerald-300 font-bold">+8.2% over 3 months <span className="text-gray-500 font-normal">(vs +2% baseline; 119 samples)</span></dd>
            </div>
            <div>
              <dt className="text-gray-400">Exit</dt>
              <dd className="text-gray-100">
                Trail the rising 20-day average; hard stop −10%. Don&apos;t chase if already extended ~5%+ above the trigger.
              </dd>
            </div>
            <div>
              <dt className="text-gray-400">Reality</dt>
              <dd className="text-gray-400">
                Intermittent — some weeks show <b>zero</b> ⚡ Setups. No setup = no trade. The trigger window is only
                1–2 days, so glance at the page during your regular market check.
              </dd>
            </div>
          </dl>
        </div>

        {/* PLAY B — Reversal (rarer, highest edge) */}
        <div className="rounded-lg border border-emerald-600/60 bg-emerald-950/20 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="flex items-center gap-2 font-bold text-emerald-200">
              <Sprout className="w-5 h-5" /> Play B — Reversal (buy panic)
            </span>
            <span className="text-[10px] font-bold text-white bg-emerald-700 px-2 py-0.5 rounded-full">RARE · TOP EDGE</span>
          </div>
          <dl className="text-xs space-y-2">
            <div>
              <dt className="text-gray-400">When it&apos;s live</dt>
              <dd className="text-gray-100">🌱 Weak tape (breadth &lt; 45%) — selloff clusters, a few times a year.</dd>
            </div>
            <div>
              <dt className="text-gray-400">What you buy</dt>
              <dd className="text-gray-100">
                Dashboard → <b>Reversals list</b>: 2–4 deeply-oversold Grade A/B names, prefer DEEP VALUE, skip THIN.
              </dd>
            </div>
            <div>
              <dt className="text-gray-400">The edge</dt>
              <dd className="text-emerald-300 font-bold">+7.9% net / trade <span className="text-gray-500 font-normal">(sweet spot breadth 30–45%, 74% win)</span></dd>
            </div>
            <div>
              <dt className="text-gray-400">Exit</dt>
              <dd className="text-gray-100">Fixed: stop −10%, target +25%, time-stop 20 days. Never average down.</dd>
            </div>
            <div>
              <dt className="text-gray-400">Reality</dt>
              <dd className="text-gray-400">
                You can&apos;t summon it — when the banner turns green, act. The app rings the 🔔 season bell so you
                don&apos;t miss the open.
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Momentum badge legend — plain words */}
      <div className="mt-4 border border-gray-800 rounded-lg p-4 bg-gray-900/40">
        <div className="text-sm font-bold text-gray-200 mb-3">The Momentum badges, in plain words</div>
        <div className="space-y-2 text-xs">
          {[
            ['⚡ Trigger', 'bg-green-800 text-green-100 border-green-600', 'Broke its 20-day high today on big volume (1.5×+). This is the buy signal — but only inside Stage 2.'],
            ['🚀 Launchpad', 'bg-fuchsia-900/60 text-fuchsia-200 border-fuchsia-700', 'The 10/20/50-day averages are squeezed into a tight cluster. Loaded, not fired yet. Watch it — often the day before a trigger.'],
            ['↩ Pullback', 'bg-sky-900/50 text-sky-200 border-sky-700', 'Dipped back to its rising 20-day average. A lower-risk second-chance entry in an uptrend.'],
            ['📏 Extended', 'bg-orange-900/50 text-orange-200 border-orange-700', 'Already too far above the breakout. Too late — chasing here is where FOMO loses money. Wait for a pullback.'],
            ['· Waiting', 'bg-gray-800 text-gray-400 border-gray-700', 'Nothing yet. Just on the watchlist.'],
          ].map(([badge, cls, desc]) => (
            <div key={badge as string} className="flex items-start gap-3">
              <span className={`shrink-0 w-28 text-center border rounded px-1.5 py-0.5 font-semibold ${cls}`}>{badge}</span>
              <span className="text-gray-300 pt-0.5">{desc}</span>
            </div>
          ))}
        </div>

        {/* Why only the ⚡ Setup combination is a buy */}
        <div className="mt-4 border-t border-gray-800 pt-3">
          <div className="text-xs font-bold text-gray-200 mb-2">Why &quot;trigger + Stage 2&quot; and nothing else? The backtest:</div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="border border-gray-700 rounded p-2">
              <div className="text-gray-400">Trigger alone</div>
              <div className="font-bold text-gray-300 text-base">+2.6%</div>
              <div className="text-[10px] text-gray-500">3 mo — barely beats costs</div>
            </div>
            <div className="border border-gray-700 rounded p-2">
              <div className="text-gray-400">Stage 2 alone</div>
              <div className="font-bold text-gray-300 text-base">+2.0%</div>
              <div className="text-[10px] text-gray-500">3 mo — same as any stock</div>
            </div>
            <div className="border border-emerald-600 bg-emerald-950/30 rounded p-2">
              <div className="text-emerald-300">Trigger IN Stage 2</div>
              <div className="font-bold text-emerald-300 text-base">+8.2%</div>
              <div className="text-[10px] text-emerald-400/70">3 mo — the ⚡ Setup badge</div>
            </div>
          </div>
          <p className="text-[11px] text-gray-500 mt-2">
            The trigger is the engine, Stage 2 is the road. Either one alone goes nowhere — together they showed the
            edge. That&apos;s the whole logic.
          </p>
        </div>

        {/* Several setups the same day */}
        <div className="mt-3 border-t border-gray-800 pt-3 text-xs text-gray-300">
          <b className="text-gray-100">Several ⚡ Setups on the same day?</b> You may buy more than one — up to your
          2–4 position cap, ~10% each. Prefer the <b className="text-emerald-300">calm ones</b>: small recent run,
          RSI under ~70. A setup that already jumped 25–30% this month can still work, but you&apos;re late to it —
          it&apos;s the riskiest entry of the batch.
        </div>
      </div>

      {/* Honesty callout: reversals aren't actually rare over history */}
      <div className="mt-4 flex items-start gap-3 border border-amber-700/50 bg-amber-950/20 rounded-lg p-3">
        <CalendarDays className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-100/90 leading-relaxed">
          <b className="text-amber-200">Don&apos;t under-weight Play B.</b> It <i>feels</i> rare because 2026 has been an
          unusually strong, one-sided year. But on your own 5½-year database, reversal season was{' '}
          <b>~52% of all trading days</b> — every year gave 2–9 hunting windows (2022: 9 windows / 154 days; 2025: 5
          windows / 124 days). You just can&apos;t schedule them. That&apos;s exactly why Play A exists: it keeps you
          productive in strong tape without forcing you to reach for the higher-edge play before it&apos;s actually live.
        </div>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* §3 — The always-on engine                                   */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={3}>The always-on engine: the Long-Term bucket</SectionTitle>
      <div className="rounded-lg border border-violet-700/50 bg-violet-950/20 p-4 text-sm">
        <p className="mb-2">
          <b className="text-violet-200">This runs in every season</b>, and it&apos;s where most of your capital
          should live. The 🏛️ <b>Long-Term page</b> is a &quot;Dividend Fortress&quot; shortlist — companies with long
          unbroken cash-dividend records. In the point-in-time test the high-yield subset was{' '}
          <b className="text-emerald-300">positive in 6 of 6 years, including both bear markets</b>.
        </p>
        <p className="text-xs text-gray-400">
          Different money, different clock (years, not weeks). Decide your split up front — e.g.{' '}
          <b className="text-gray-200">60% long-term / 30% swing / 10% cash</b> — and never let one bucket raid the
          other. Bonus: <b className="text-gray-200">reversal season is the best time to add</b> to fortress names —
          panic prices, fatter yields. So even a dry swing year isn&apos;t idle: you&apos;re compounding here.
        </p>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* §4 — Weekly routine map                                     */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={4}>Your weekly routine, as a map (15 min, 1–2× a week)</SectionTitle>
      <p className="text-sm mb-4">
        You don&apos;t watch the screen all day. When you sit down, this is the whole decision tree — it always ends in
        exactly one of: take Play A, take Play B, protect, or do nothing (all valid).
      </p>

      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40">
        <div className="mx-auto w-fit px-4 py-2 rounded-full bg-gray-800 border border-gray-700 text-white text-sm font-semibold">
          Open the dashboard
        </div>
        <FlowArrow />
        <div className="mx-auto w-fit px-4 py-2 rounded bg-sky-900/50 border border-sky-700 text-sky-200 text-sm font-bold text-center">
          Look at the SEASON banner — which colour?
        </div>

        <div className="grid md:grid-cols-2 gap-4 mt-4">
          {/* Strong-tape branch (Play A) — listed first */}
          <div className={`rounded-lg border p-3 ${!isReversal && market ? 'border-indigo-500 bg-indigo-950/30 ring-1 ring-indigo-500/40' : 'border-indigo-800/60 bg-indigo-950/10'}`}>
            <div className="flex items-center gap-2 font-bold text-indigo-300 mb-1">
              <ShieldCheck className="w-4 h-4" /> 🛡️ AMBER — strong tape (breadth ≥ 45%)
              {!isReversal && market && <span className="text-[10px] bg-indigo-600 text-white px-1.5 py-0.5 rounded-full">TODAY</span>}
            </div>
            <div className="text-[11px] text-indigo-200/70 mb-2">The common state. Play A is live; Play B is not.</div>
            <ol className="space-y-1.5 text-sm">
              {[
                ['Momentum page → filter ⚡ Setup', 'the only buy in strong tape'],
                ['A row lit? Size ~10%, buy, trail the 20-day SMA', 'stop −10%, don’t chase extended'],
                ['None lit? Add to a long-term fortress name instead', 'the engine never sleeps'],
                ['Check red Alerts for exits on what you hold', 'honour stops/targets'],
                ['Tempted by anything else? Watchlist it, close the app', 'Coils / Rebounds hold it'],
              ].map(([step, note], i) => (
                <li key={i} className="flex gap-2">
                  <span className="w-5 h-5 shrink-0 rounded-full bg-indigo-700 text-white text-[11px] flex items-center justify-center mt-0.5">{i + 1}</span>
                  <span>
                    <span className="text-gray-100">{step}</span>
                    <span className="text-gray-500 text-xs"> — {note}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>

          {/* Weak-tape branch (Play B) */}
          <div className={`rounded-lg border p-3 ${isReversal ? 'border-emerald-500 bg-emerald-950/30 ring-1 ring-emerald-500/40' : 'border-emerald-800/60 bg-emerald-950/10'}`}>
            <div className="flex items-center gap-2 font-bold text-emerald-300 mb-1">
              <Sprout className="w-4 h-4" /> 🌱 GREEN — weak tape (breadth &lt; 45%)
              {isReversal && <span className="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded-full">TODAY</span>}
            </div>
            <div className="text-[11px] text-emerald-200/70 mb-2">The rare, high-edge window. Play B is live — prioritise it.</div>
            <ol className="space-y-1.5 text-sm">
              {[
                ['Open the Reversals list', 'your top-edge buy list'],
                ['Pick 2–4: Grade A/B, prefer DEEP VALUE, skip THIN', 'buy panic, not strength'],
                ['Size ~10% each; set stop −10% / target +25% / 20-day', 'all three, immediately'],
                ['Add to fortress names too — they’re on sale', 'reversal = best time to buy long-term'],
                ['Journal each trade, close the app', 'done hunting'],
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
        </div>

        <div className="mt-4 text-center text-xs text-gray-500">
          Weeks with no buy are <b className="text-gray-300">normal and correct</b> — your test showed forcing a trade
          every week loses 20–36% of capital per year. A quiet screen is the app protecting you.
        </div>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* §5 — Evidence                                               */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={5}>Where the money actually is (your backtests, net of costs)</SectionTitle>
      <p className="text-sm mb-2">
        Why only two plays. Green bars are the validated edges; red bars are what the app deliberately stops you from
        doing. DSE round-trip costs ≈ 1–1.5%, so an edge must clear that.
      </p>
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40">
        <EvidenceBar
          label="⚡ Play A — Momentum daily TRIGGER inside monthly Stage-2"
          sub="+8.2% over 3 months vs +2.1% for the universe. The one validated buy in strong tape. Stage label alone = no edge; raw trigger alone barely beats costs."
          value={8.2}
          unit="% gross / 3 mo"
        />
        <EvidenceBar
          label="🌱 Play B — Reversals in weak tape (breadth 30–45%)"
          sub="THE top edge, 74% win. But it only appears in selloff clusters — a few windows a year (still ~52% of all days historically)."
          value={7.9}
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
          label="Stage-3 / topping stocks (even if they trigger)"
          sub="−7.1% over 6 months. A trigger in a topping stock is a trap — this is why Play A requires Stage-2."
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
      {/* §6 — Page roles                                             */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={6}>Every page has exactly one job</SectionTitle>
      <p className="text-sm mb-3">
        The menu is a funnel: two pages you <b className="text-emerald-300">BUY</b> from (one per play), three you{' '}
        <b className="text-sky-300">WATCH</b>, one you <b className="text-violet-300">INVEST</b> from, and the rest is{' '}
        <b className="text-gray-400">CONTEXT</b>. If you remember nothing else, remember which badge is on which page.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        {[
          {
            icon: Zap, name: 'Momentum → ⚡ Setup filter', badge: 'BUY (Play A)', badgeCls: 'bg-emerald-700',
            note: 'Your strong-tape buy list. Buy ONLY the ⚡ Setup rows (trigger inside Stage-2, +8%/3mo). The stage label alone is context; Stage 3/4 = stay away.',
          },
          {
            icon: TrendingUp, name: 'Dashboard → Reversals list', badge: 'BUY (Play B)', badgeCls: 'bg-emerald-600',
            note: 'Your weak-tape buy list — in 🌱 season only. Sort by grade, prefer DEEP VALUE, skip THIN. 68% win, Grade A ≈ 82%.',
          },
          {
            icon: Sprout, name: 'Coiled Springs', badge: 'WATCH', badgeCls: 'bg-sky-600',
            note: 'Winner-DNA screen: tight quiet bases above the 200-day. The launch trigger is invisible in the chart — a watch-daily list with alerts, never an automatic buy.',
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
            note: 'The always-on Dividend Fortress engine — years, not weeks. Most of your capital. Add every month; add hardest in reversal season.',
          },
          {
            icon: Activity, name: 'Chart Analyst / Manual Analyze', badge: 'CONTEXT ONLY', badgeCls: 'bg-gray-600',
            note: 'For understanding structure, support/resistance and risk tags. Patterns carry NO buy edge on DSE — looking is free, buying off them is not.',
          },
          {
            icon: Calculator, name: 'Time Machine (date bar)', badge: 'TRAINING', badgeCls: 'bg-gray-600',
            note: 'Rewind to a past selloff and watch what the Reversals list looked like. Free practice between windows.',
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
      {/* §7 — Sizing calculator                                      */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={7}>How much to buy (same for both plays)</SectionTitle>
      <p className="text-sm mb-3">
        One rule, whichever play is live: <b className="text-gray-100">never let a single trade lose more than 1% of
        your total money</b>. With a −10% stop, that&apos;s a ~10% position. Type your capital:
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
            <div className="text-[11px] text-gray-400 mb-1">Concurrent swing positions</div>
            <div className="text-lg font-bold text-sky-300">{fmtBDT(sizing.pos * 2)} – {fmtBDT(sizing.pos * 4)}</div>
            <div className="text-[11px] text-gray-500">2–4 max; the rest stays cash / long-term</div>
          </div>
        </div>
        <div className="text-[11px] text-gray-400 mb-1">What full swing deployment looks like (max 4 positions):</div>
        <div className="flex h-8 rounded overflow-hidden border border-gray-700 text-[10px] font-bold text-white">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-emerald-600 border-r border-gray-900 flex items-center justify-center" style={{ width: '10%' }}>
              #{i}
            </div>
          ))}
          <div className="bg-gray-700 flex-1 flex items-center justify-center text-gray-300">CASH / LONG-TERM — 60%</div>
        </div>
        <div className="mt-3 flex items-start gap-2 text-xs text-amber-300/90 bg-amber-950/20 border border-amber-800/50 rounded p-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Liquidity check before every buy: if the app tags a stock <b>THIN</b>, skip it. Keep your order under
            ~10–20% of its average daily volume, or your own buying moves the price against you. And DSE settles{' '}
            <b>T+2</b> — shares you buy can&apos;t be sold for ~3 days, so intraday round-trips are impossible anyway.
          </span>
        </div>
      </div>

      {/* ---------------------------------------------------------- */}
      {/* §8 — Exits (two schemes)                                    */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={8}>Exits: decide them the moment you buy — the scheme depends on the play</SectionTitle>
      <p className="text-sm mb-3">Never improvise an exit. Momentum trades <i>trail a trend</i>; reversals use <i>fixed levels</i>.</p>
      <div className="grid md:grid-cols-2 gap-4">
        {/* Momentum exits */}
        <div className="border border-indigo-700/50 bg-indigo-950/20 rounded-lg p-4">
          <div className="flex items-center gap-2 font-bold text-indigo-200 mb-3">
            <Zap className="w-4 h-4" /> Play A — Momentum trade
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-indigo-400 shrink-0" />
              <span><b className="text-indigo-200">Trail the 20-day average.</b> As it rises with the trade, it becomes your moving stop.</span>
            </div>
            <div className="flex items-center gap-2">
              <OctagonX className="w-4 h-4 text-red-400 shrink-0" />
              <span><b className="text-red-300">Hard stop −10%</b> in case it breaks fast before the SMA catches up.</span>
            </div>
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-gray-400 shrink-0" />
              <span><b className="text-gray-200">No fixed target</b> — ride the trend; exit when it closes below the 20-day SMA. Don&apos;t chase if already ~5%+ extended above the trigger.</span>
            </div>
          </div>
        </div>
        {/* Reversal exits */}
        <div className="border border-emerald-700/50 bg-emerald-950/20 rounded-lg p-4">
          <div className="flex items-center gap-2 font-bold text-emerald-200 mb-3">
            <Sprout className="w-4 h-4" /> Play B — Reversal trade
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="border border-red-700/50 bg-red-950/20 rounded p-2">
              <OctagonX className="w-5 h-5 text-red-400 mx-auto mb-1" />
              <div className="font-bold text-red-300">−10%</div>
              <div className="text-[10px] text-gray-400">Stop</div>
            </div>
            <div className="border border-emerald-700/50 bg-emerald-950/20 rounded p-2">
              <Target className="w-5 h-5 text-emerald-400 mx-auto mb-1" />
              <div className="font-bold text-emerald-300">+25%</div>
              <div className="text-[10px] text-gray-400">Target</div>
            </div>
            <div className="border border-sky-700/50 bg-sky-950/20 rounded p-2">
              <Clock className="w-5 h-5 text-sky-400 mx-auto mb-1" />
              <div className="font-bold text-sky-300">20d</div>
              <div className="text-[10px] text-gray-400">Time stop</div>
            </div>
          </div>
          <div className="text-[11px] text-gray-500 mt-2 text-center">Fixed levels — a reversal is a falling knife, so the stop is wide and the clock is hard.</div>
        </div>
      </div>
      <div className="mt-3 border border-red-800/60 bg-red-950/30 rounded p-3 text-sm text-red-200 font-semibold text-center">
        ☠️ Iron rule for BOTH plays: NEVER average down. The stop takes you out — adding to a loser is how accounts die.
      </div>

      {/* ---------------------------------------------------------- */}
      {/* §9 — Hard rules                                             */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={9}>The 7 hard rules (print these)</SectionTitle>
      <div className="border border-gray-800 rounded-lg divide-y divide-gray-800 bg-gray-900/40">
        {[
          'Check the season first — it tells you which of your two plays is live. Run only that one.',
          'In strong tape, buy ONLY ⚡ Setups (trigger inside Stage-2). In weak tape, buy the Reversals list.',
          'Never risk more than 1% of capital per trade (≈10% position vs a −10% stop).',
          'Set your exits the moment you buy — trail the 20-day for momentum, fixed −10/+25/20d for reversals.',
          'Never average down. Let the stop do its job.',
          'No signal firing = no trade. Add to the long-term bucket instead; never force a swing.',
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
      {/* §10 — Honest limits                                          */}
      {/* ---------------------------------------------------------- */}
      <SectionTitle n={10}>The honest fine print</SectionTitle>
      <div className="border border-gray-800 rounded-lg p-4 bg-gray-900/40 text-sm space-y-2 mb-10">
        <p>
          • Even with two plays, this is <b className="text-gray-100">not</b> a trade every day or week. Signal-gated
          means dry spells; that&apos;s the system working, not failing. Daily round-trip trading loses money on DSE — settled.
        </p>
        <p>
          • Realistically this is <b className="text-gray-100">modest, part-time, seasonal income</b> — not a salary.
          Do not quit your job for it.
        </p>
        <p>
          • The +8% (momentum) and +7.9% (reversal) figures are backtest averages, not promises — any single trade can
          lose, which is what the stop is for. <b className="text-gray-100">Prove it with small real money first</b>:
          log every trade (date, season, play, entry, exits, followed-plan?). After 15–20 trades, if your real net per
          trade is near +3%, the edge is real for you — scale up slowly. If not, stay small and find out why (usually:
          traded the wrong play for the season, chased an extended entry, or ignored a stop).
        </p>
        <p className="text-gray-500 text-xs pt-1">
          Sources: docs/TRADING_PLAYBOOK.md · PROFITABILITY_AUDIT.md · MOMENTUM_STRATEGY.md · WINNER_ANATOMY.md ·
          LONG_TERM_STRATEGY.md · weekly_system_study* — all reproducible via the backtest scripts listed in each.
        </p>
      </div>
    </main>
  );
}
