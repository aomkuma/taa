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
  about 70-100 USD a day now, so intraday trends on small timeframes exist every day. **The setups are revised
  every 3-6 months, so backtests cover the latest six months only** (owner, 2026-10-17); older years are
  background, not the judge.
- **Use the machine's edge in time.** The system recomputes every timeframe on every bar, decides without
  hesitation at the bar's close, holds its if-then plans before scheduled releases, and lets the AI analyst
  propose new candidate causes from the runs it could not explain - the data, judged out of sample, decides.
- **A full arsenal, the right tool for the moment** (owner, 2026-10-17): "you need every weapon - a pistol, a
  rifle, an M16, an AK, a fruit knife; it is about which one to pick at that moment." The owner's numbers (5 USD,
  hold times, counts) are guidance, not rules: follow what the real data says. Count goal: about 3 trades a day,
  one in each market session (Asia, London, New York).
- **Learn from the losing trades** (owner, 2026-10-17): "learning from losers is the heart of developing a
  trade; catch the timing and the signals." The real losing trades teach more than one human's opinion; the
  owner's own habits are hypotheses for the data to test.
- **Gold runs in zones of about 70-90 USD (owner, repeated; written here 2026-10-23).** After a strong move the
  zone size is carried along in equal steps from the base the move left; a new strong move shifts (re-anchors) the
  grid; inside a zone the usual run is about half a zone. A zone line is a band, not a sharp line (price stops short
  or overshoots). **The zone is the plan** (where price sits, the next line as the target, how much room a trade
  has); **the edge is the entry and its timing**; reaching a line is not by itself a reason to trade. Example
  (owner's H4 chart, 2026-09-16 .. 10-23): every leg ran line to line 4,369 / 4,293 / 4,217 / 4,141 / 4,066 / 3,990
  (76 USD steps); a 3-week range spanned two zones with lower highs; after the break of 4,141 three weaker re-tests
  of it from below (to 4,155.5, 4,141.9, 4,142.2) gave the sell, the stop above the already-swept 4,155.5, the
  target the next line - the 2026-10-22 NY break of 4,066 ran one zone to 3,990. Details, the grid's code and the
  measurements: `research/2026-10-22-zones/NOTES.md`. Open point: the code sets the step to the D1 ATR(20), which
  sat in 70-90 most of the time but rose to 220-240 after the February 2026 crash - to be measured against the
  owner's 70-90 on the old years.
- **The entry decides (owner, repeated many times; written down 2026-10-23).** Three conditions for every entry,
  checked before any exit or filter is tuned:
  1. **A precise entry, and a stop that is not in a liquidation zone.** Enter at the level where the turn or the
     run starts, not after the move has happened; the stop sits beyond the structure that would prove the trade
     wrong, never where the obvious stops of everyone else sit (just past the swing, the round number, the
     pool) - those get swept.
  2. **Enter when the price structure shows a clear enough picture.** The pattern / structure must be readable on
     the entry timeframe (and agree with the next one up); no entry on a half-formed or noisy picture.
  3. **Trend and momentum.** Know the trend of the larger frames and the momentum at the level (how price arrived,
     how hard, how many touches) before taking the trade; a turn against a strong run needs the run to be spent.

  **Why this is written down:** the NY-B2 journal (26 learning weeks) tuned exits and filters around an entry
  that broke rule 1 - the bot's B2 entered a median 1.7-1.8 pattern heights past the pattern's extreme (the classic
  measured move ends at 2) with a stop 1.8 heights away, so after the entry the median best move was 0.4-0.6 R. It
  looked break-even while learning and lost in both exams (research journal, PLAN1_JOURNAL.md, "late entry";
  `ny_b2/late_entry.py`). **How to apply:** for every piece, measure the entry geometry on every trade first - how
  far price had already moved from the level when we entered, the stop in units of that move and against the
  nearby pools, and the median best / worst after the entry; a piece whose median best is under about 1 R gets a
  new entry, not more rules.
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
