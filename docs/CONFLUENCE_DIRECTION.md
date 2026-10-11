# Confluence direction — reading the whole chart before choosing a side

Status: **plan, nothing built yet** (owner, 2026-10-11). Ticket: TAA-L812 in `docs/TICKETS_LEARNING.md`.
Related: `docs/AI_ANALYST_DISCUSSION.md` (Phase 16, the AI analyst), `docs/INVERTED_SETUPS.md`,
`docs/SETUP_REVIEW.md` §14-§15. No profitability claims: this is a plan to measure, not a result.

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

- Two-world backtests (normal and inverted, separate accounts, the widest research config), 4 months first
  (2026-06-05 .. 2026-10-05), then the full year on the eight symbols.
- Report per world: trades, win rate, R per trade with a 90 % CI, net, max drawdown in R, how far losers ran
  toward the target before turning and how far winners went against the stop (`two_worlds.py`).
- **Horizons:** how often the chosen side is right after 4 hours, 1 day and 3 days (direction hit rate against
  a coin and against the bot's setups on the same bars), next to the traded result with stop and target.
- **Thresholds:** at most 3 pre-registered settings of (net threshold, *k*); chosen on one half and judged on
  the other half and on hold-out symbols, like every rule in SETUP_REVIEW. A setting that only works
  in-sample is not a finding.
- **Goal and gap stated before and after:** ≥ +0.15 R per trade net, CI lower bound > 0 in both halves,
  ≥ 300 trades a year on the eight symbols, max drawdown ≤ 15 R.

## 4. Path B — the AI reads the same chart (after or beside A; forward only)

The Phase 16 analyst (AI_ANALYST_DISCUSSION §3): the engine sends the AI the same chart pack (M15/H1/H4 numbers,
the evidence and zones of Path A, optionally a chart image) and records its side and thesis **in shadow** for
every Path A candidate and on a schedule.

- **Forward only:** an AI cannot be backtested fairly (it may have seen those prices in training).
- **The comparison that matters:** the AI's side vs Path A's side vs the bot's setups vs a coin, on the same
  bars, in R after costs, over hundreds of cases (weeks). A handful of correct calls cannot be told apart
  from luck at 50/50.
- Needs the owner's Anthropic API key and a daily budget (the default 50 calls / $2 a day is too small for
  every candidate on eight symbols; an estimate comes with the stage-B ticket).

## 5. How an AI may take part in orders (stages, each the owner's decision)

| Stage | The AI may | Gates |
|---|---|---|
| Today | veto or comment (Phase 13) | after every other check; can only block |
| B. shadow | give a side and a thesis, recorded and scored | no orders |
| C. filter | remove bot signals against its side | can only reduce risk |
| D. armed plan | the owner arms a thesis; the engine waits for its trigger and raises an ordinary signal | every risk rule, breaker and the mode gate; DEMO first |
| Never | send orders to MT5 directly or size, widen a stop or bypass a gate | — |

## 6. Steps

1. Finish the two-world backtests of the nine setups (running since 2026-10-11 20:20 Thai time) and write
   SETUP_REVIEW §15.
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
