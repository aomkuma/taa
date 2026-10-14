# Confluence direction — reading the whole chart before choosing a side

Status: **plan, nothing built yet** (owner, 2026-10-11). Ticket: TAA-L812 in `docs/TICKETS_LEARNING.md`.
Related: `docs/AI_ANALYST_DISCUSSION.md` (Phase 16, the AI analyst), `docs/INVERTED_SETUPS.md`,
`docs/SETUP_REVIEW.md` §14-§15, `docs/CHART_READ.md` (TAA-L813: the deterministic chart read this path
builds on). No profitability claims: this is a plan to measure, not a result.

## 1. The owner's observation (2026-10-11, in Thai, summarized)

- When the owner gives an AI a **live** chart and asks whether price is more likely to go up or down, the answer
  has often come true afterwards. These were forward questions on live charts, not hindsight.
- The AI combines **many parts at once**: support and resistance, key price zones and chart patterns, on
  **M15, H1 and H4**. The bot's setups each fire on **one trigger** (a breakout, a harmonic completion, …) and
  trade at once, whatever the rest of the chart says.
- The owner asked whether an AI agent could take part in sending orders through the engine. Answer given: yes
  in stages, never around the risk and mode gates (§5); first measure whether the whole-chart reading adds value.

## 2. What exists already

| Piece | Where | Today |
|---|---|---|
| Evidence detectors (S/R zones and breakouts, chart patterns, Fibonacci, harmonics, SMC, candles, trend, momentum, volatility, sessions) | `app/evidence/` | run on every closed bar; each item has a direction, quality, tier, invalidation and targets |
| Confluence score (noisy-OR per family, conflicts penalized) | `app/evidence/confluence.py` (TAA-307) | used only as the **setup strength** of a signal a setup already raised, in that setup's direction |
| H4/D1 market map (trend vs range, demand/supply zones, room to the opposing zone) | `app/indicators/market_map.py` (TAA-L809) | recorded as `ctx:h4_*` / `ctx:d1_*` features; no strategy reads it |
| Two-world backtests (original and inverted, separate accounts) | `app.cli backtest`, `research/2026-10-11-pre-run/two_worlds.py` | the yardstick for every idea here |
| AI analyst (theses, shadow, arm) | `docs/AI_ANALYST_DISCUSSION.md`, Phase 16 | designed, not built; AI is veto/advisory only today |

The missing piece is a **direction decided by the whole picture**: today the trigger decides the side, and the
rest of the chart only adds points to it.

## 3. Path A — a deterministic confluence direction (first; backtestable)

A new strategy, `setup_confluence`, that asks the question the owner asks the AI: *on M15, H1 and H4 together,
which side does the evidence favour, and is the agreement strong enough to act?*

1. **Score both sides on every closed M15 bar** with the existing `confluence_score`, over the active evidence
   of M15, H1 and H4 (H4 detectors need the context timeframe in the evidence pass; to check) plus the market
   map (H4/D1 trend, zone with or against the side, room to the opposing zone). Net score = BUY score − SELL
   score.
2. **Act only on clear agreement:** |net| ≥ a threshold, at least *k* evidence families on the chosen side, at
   least one higher timeframe (H1 or H4) agreeing, and no strong opposing zone between the entry and the target.
3. **Levels from the chart, not from a fixed multiple:** stop beyond the invalidation of the strongest
   supporting item or the zone the trade leans on (capped by `max_sl_atr`); target at the next opposing zone or
   the best supporting target, so the R:R comes from the structure.
4. **It is an ordinary strategy:** its signals pass the decision engine, every risk rule, the breakers and the
   mode gate; `inverted()` gives its other world for free.

### Measurement (fixed before any run)

- The two-world backtests of INVERTED_SETUPS §5 (same method and research config), 4 months first
  (2026-06-05 .. 2026-10-05), then the full year; per-world report from `two_worlds.py`.
- Also the **direction hit rate** after 4 hours, 1 day and 3 days, against a coin and against the bot's setups
  on the same bars.
- At most 3 pre-registered settings of (net threshold, *k*), judged walk-forward and on hold-out symbols as in
  SETUP_REVIEW; the goal and the gap are stated before and after (HANDOFF prompt).

### 3.1 Triple screen and the market phase of each setup (owner, 2026-10-11)

Elder's triple screen (*Trading for a Living*) on the owner's timeframes: **H4** the tide (direction),
**H1** the wave (a pullback against the tide), **M15** the ripple (the entry, here the setup's own trigger).
Every timeframe has its own trend: a sideways H4 can hold a trending H1, so the phase is read on all three
screens, not on one.

1. **Measure first:** each backtest trade gets the state of H4, H1 and M15 at the last bar closed before its
   entry (`state_frame`: WITH / AGAINST / RANGE / TRANSITION relative to the side), grouped into a few phases
   with enough trades: `aligned` (H4 and H1 with), `pullback` (H4 with, M15 against or ranging: the triple
   screen entry), `range_h1_with` (H4 range, H1 with), `range_h1_other`, `against_h4`, `other`.
   Tool: `research/2026-10-11-pre-run/three_screens.py`, both worlds side by side.
2. **Assign by data, not by label:** a setup gets a phase (and a side: normal or inverted) only where the phase
   holds in both halves and on the hold-out symbols. Textbook expectations, to be confirmed or rejected:
   pullback setups (fib, elliott, trend pullback) in `pullback`; breakouts at a range turning into a trend;
   reversals (harmonic, candle, neckline, SMC) at range edges or a trend's end.
3. **Then gate:** each setup trades only in its phases (a per-setup rule through the L810 hook H1), confirmed
   by two-world backtests like any rule.
4. Results and the assignment per setup: SETUP_REVIEW §15.

## 4. Path B — the AI reads the same chart (forward only)

Phase 16 as designed in AI_ANALYST_DISCUSSION (§3 chart pack and thesis, §3.4 stages, §4.4 why it can only be
measured forward, §4.5 safety). The only addition here: the AI is also asked on **every Path A candidate**, so
the AI's side, Path A's side, the bot's setups and a coin are compared on the same bars. Needs the owner's API
key and a daily budget.

## 5. How an AI may take part in orders

The stages in AI_ANALYST_DISCUSSION §3.4 (shadow → filter → armed plan, each behind a flag and the owner's
decision). The AI never sends orders to MT5 directly and never bypasses a risk rule, a breaker or the mode gate.

## 6. Steps

1. Harmonic first, alone (owner, 2026-10-11): two-world backtests over a year, its three-screen phase (§3.1)
   and the entry/exit hypotheses on its trades; SETUP_REVIEW §15. The other eight setups wait.
2. Path A: `setup_confluence` (strategy, config, TH/EN texts, tests incl. no look-ahead), then two-world
   backtests, 4 months then a year; SETUP_REVIEW section with the result and the gap.
3. Path B: Phase 16 stage A/B tickets (chart pack, `ThesisV1`, shadow tracker) once the owner provides a key and
   a budget; compare with Path A on the same bars.
4. Only with numbers: stage C/D, the owner's go-ahead each time; LIVE stays off.

## 7. Open questions for the owner

- Q-C1 The holding horizon the owner has in mind when asking an AI (hours, a day, several days)? Measured at
  4 h / 1 d / 3 d meanwhile.
- Q-C2 Which AI and what input the owner used (a chart image, which timeframes), so Path B can copy it.
- Q-C3 Path B budget per day once Path A has a first result.
