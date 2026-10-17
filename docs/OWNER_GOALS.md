# The owner's goals and principles

What the owner wants from the system, in their words where possible (2026-10-17, restated after both Claude
sessions found that S1 and TS pay only in gold's 2024-26 rally). Read this before any setup or research work; it
outranks earlier targets where they differ. Results never promise profit; they describe the past.

## Goals

1. **Consistent profit.** Positive expectancy over many trades, steady month to month; trading income matters
   to the owner, so the equity curve's steadiness counts as much as its slope.
2. **A trade every day.** About two trades a day per setup (about 500 a year); at least one trade a day overall.
   Daily money goal as stated: at least +15 USD a day on the owner's small account (quoted as 100 USD at 1:2000 on
   2026-10-17; the real account was 150 USD at 1:2000 on 2026-10-15).
3. **Enter only when price is about to run** the expected way, and **take the profit quickly**: the target is a
   share of the moment's usual run, so it follows the market's current pace.
4. **The moments when price runs** (the owner's experience): the Asia, London and New York opens; important
   news and economic releases; ATR falling to its low; a Bollinger squeeze - **all at important support or
   resistance**.

## Principles

- **No single rule decides direction.** Everyone gets the same information and reads the same books (so does
  the market maker). The system keeps several playbooks - break-and-hold (follow the run), sweep-and-reclaim
  (fade the false break), with the higher timeframes' flow - and decides per situation which one to use, or
  to stand aside.
- **Find the core that moves price.** Every run, on M1, M15, H1 or H4, has reasons. Look for them in the price's
  own behaviour: where the liquidity sits (the pools everyone sees), when it arrives (opens, releases, after a
  contraction), which way the bigger flow pushes, how price reacts at the pool.
- **Everything relative and dynamic.** Each timeframe has its own trend and its own range (the triple screen, in
  our own form); ATR moves; thresholds are percentiles of the recent window or multiples of the current scale,
  never fixed numbers.
- **Theory is a guide, not a rule** (about 30-40 %; the rest is each symbol's measured behaviour).
- **Live in the present, without bias.** A setup that works only in some periods is normal; the system's job is
  to see which period we are in now and act on it. That is why the owner builds a system: to remove the human
  psychological weakness. Every decision is logged with its reasons.
- **Strategies are living.** No setup is written once and used forever: setups, market state, volatility and
  trend are reviewed on a schedule and the strategies re-tuned to the present. Example (2026-10-17): gold runs
  about 70-100 USD a day now, so intraday trends on small timeframes exist every day.
- **Use the machine's edge in time.** The system recomputes every timeframe on every bar, decides without
  hesitation at the bar's close, holds its if-then plans before scheduled releases, and lets the AI analyst
  propose new candidate causes from the runs it could not explain - the data, judged out of sample, decides.
- **Try hard, judge honestly.** A test that finds no edge for one factor alone is not the end: test it jointly
  with location, timing and the flow above (an effect can be zero on average and strong in a context). Rules are
  written down before the data that judges them, and the held-out years stay untouched until then.

## Facts behind the current plan (2026-10-17, gold, FBS-Demo history)

| Year | E 2021-22 | D 2022-23 | C 2023-24 | A 2024-25 | B 2025-26 | since 2026-09 |
|---|---|---|---|---|---|---|
| Daily range, median (USD) | 22.9 | 22.1 | 28.1 | 40.2 | 92.9 | 92.9 |

- Spread 0.20-0.27 USD in every year. The New York open (13-15 UTC) has the day's largest 30-minute range in
  every year (about 5 USD in 2021-23, about 20 spreads), then London (06-08 UTC) and Asia (01 UTC).
- S1 by gold's 20-day average daily range at the entry: under 35 USD -0.193 R a trade (185 trades), 35 and above
  +0.179 (182) - a present-tense measure of when a setup is in season.
- Breaks fail less at the New York open (65 % back inside the range, about 74 % at other times); fading false
  breaks paid in London (S1); every fixed rule chosen on one half-year broke on the other (SETUP_REVIEW §14, §23).

## The plan built on this: Setup OWN, the owner's own trade

The owner (2026-10-17): this becomes **the owner's own setup** (Setup OWN; docs/OWNER_TRADING.md). A five-year
moments dataset for gold (opens, releases; relative features for the four drivers; labels in units of the usual
run), hypotheses fixed before testing, a playbook selector re-fitted monthly and judged walk-forward, then the
engine and a weekly / monthly review loop. Method, hypotheses and results: `docs/OWN_SETUP.md`.
