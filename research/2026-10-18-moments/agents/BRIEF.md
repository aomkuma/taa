# Setup OWN research team - shared brief (2026-10-17)

You are one of several research agents working in parallel to make the owner's gold scalping setup (Setup OWN)
profitable. Read this whole brief first. The full history is in `docs/OWN_SETUP.md` (long; skim "Results" and
rounds 1-10) and the owner's goals in `docs/OWNER_GOALS.md`.

## The owner's goals (guidance, not hard rules - "be flexible with real data")

- Gold (XAUUSD) on FBS, MT5. Scalps first; when the picture is clear, hold a short trend (seconds to 2-3 hours).
- Target at least about 5 USD of price per trade (the owner's gold pip = 1.00 USD; 4173.8 -> 4178.8 = 5 pips).
- About 3 trades a day, one in each session (Asia, London, New York).
- The largest timeframe for the setup is H1 (no H4/D1 analysis).
- Pass bar: at least +0.15 R a trade net of costs (tolerance +0.10), most months positive.
- Principles: no single rule decides direction; a full arsenal of tools, pick the right one for the moment; everything
  relative; live in the present; learn from the losing trades (below).

## Markets (owner, 2026-10-17): gold and the major currency pairs

Trade gold (XAUUSD) and the majors (EURUSD, GBPUSD, USDJPY, AUDUSD, USDCHF, USDCAD, NZDUSD; M1 in
`data/history/FBS-Demo/<PAIR>/M1.parquet` from 2023-09). Other markets (indices, crosses) may serve as inputs only.
For a pair, express targets/stops in pips and in that pair's ATR; costs from its own spread column (x the pair's
point) + about 0.2 pip slippage each way.

## Learn like a trader (owner, 2026-10-17)

"Learn like a trader who keeps trying to learn and improve": look at the charts of real trades (losers and
winners), keep a journal of why each was taken and what happened, draw lessons, try the next version, repeat.
The research venv has matplotlib (`data/venv-research/Scripts/python`); you can view a PNG with the Read tool.

## Progress in stages (owner, 2026-10-17)

Cut losses -> break even -> profit -> sustainable profit; a setup need not be profitable from day one. Keep and
report every change that clearly cuts the loss or the drawdown (show the step-by-step table: baseline -> each
change), not only rules that already pass +0.15 R.

## The test window (the owner stresses this)

- **Test only on 2026-03-01 .. 2026-10-14** (the data ends 2026-10-14 08:18 UTC). Report it month by month.
- **Design, fit and choose only on data before 2026-03-01.** Write your exact rule in your notes file
  *before* you compute it on the test window, and run the test once per frozen rule. If you look at the test and
  change the rule, say so plainly and count it as a new rule.

## Data (all local, read-only)

- Gold M1 bars: `import gold; gold.bars("M1")` (from `research/2026-10-18-moments/gold.py`; index = bar open time
  UTC; columns open/high/low/close/tick_volume/spread; spread in points, x 0.01 = USD). 2020-09 .. 2026-10-14.
  M5/M15/H1: resample M1 yourself (the stored M5 covers only 2025-10..).
- Gold ticks (bid/ask, ms, UTC): `data/ticks/XAUUSD/YYYY-MM-DD.parquet`, weekdays 2025-10-01 .. 2026-10-16
  (columns time_utc, bid, ask; about 300-400k ticks a day). Use `pd.to_datetime(...).dt.as_unit("ns")` before
  int64 (pandas 3 keeps ms otherwise).
- FX M1: `data/history/FBS-Demo/<PAIR>/M1.parquet` (EURUSD, USDJPY, GBPUSD, AUDUSD, USDCHF, USDCAD ... 2023-09 ..).
- US release calendar (official, ET times): `gold.releases()` -> columns date, time_et, event (CPI, NFP, PPI, PCE,
  GDP, FOMC), t (UTC). 2021-09 .. 2026-10.
- Prepared datasets in `data/research/`: `own_ml_long.parquet` (every minute of the active windows - Asia
  00:00-02:00 UTC, London 08:00-09:30 London, New York 08:15-11:15 ET - x both sides, 62 features at the previous
  bar's close, directional ones signed by `side`; `e` = M1 bar index in `gold.bars("M1")` sliced from 2023-09-01),
  `own_ml_arsenal_labels.parquet` (labels y/usd/min for target/stop tools), `own_ml_ticks.parquet` (tick features
  per minute, 2025-10+), `own_ml_zz_votes.parquet` (ZigZag structure + 52 indicator votes), `own_ml_cr_levels.parquet`.

## Simulation conventions (keep them - they match the bot's engine)

- Decide at a bar's close; enter at the next bar's open. A BUY fills at the ask (open + spread) + 0.07 USD slippage;
  a SELL at the bid (open) - 0.07. Stops and targets on bar highs/lows; a SELL's on the ask (bid + spread). Both stop
  and target inside one bar = the stop. A stop exit pays 0.07 slippage; a limit target none. A time exit at the
  bar's close (the bid for a buy, the ask for a sell) with slippage.
- `research/2026-10-18-moments/ny_lab.py` has `M1()` (arrays) and `M1.trade(e, side, tp, sl, be, hz)` (one trade
  with an optional break-even, returning exit/usd/mins and the losers' kind). Reuse it.
- Costs are about 0.3-0.4 USD a round trip at 0.01 lot (spread 0.23-0.36 + slippage). USD at 0.01 lot = price move x 1.
- One position at a time.

### Real costs (the auditor, 2026-10-17; `agents/auditor/notes.md`) - use them in every final test

- The M1 `spread` column is the minute's **minimum** spread: add **+0.08 USD** to it for a market entry (or use the
  real ask per minute from `agents/auditor/tick_minutes.parquet`, 2025-10+). Real entry spread: Asia 0.39, London /
  New York 0.29-0.30 (2026-04+), 20-24 UTC 0.37-0.45 USD.
- Stop fills: slippage **0.15 USD** (New York 0.20), not 0.07. Entry slippage 0.07 is conservative; keep it.
- Real round trip at 0.01 lot about 0.43 USD on average. The harness is otherwise sound (no look-ahead; ticks vs M1
  within +-0.01 R).
- Gold needs 7-15 win-rate points over a coin for +0.15 R (3/3: 14.6, 5/4: 11.5, 8/6: 9.6, 10/8: 9.1, 15/10: 7.8,
  20/12: 7.0). Report R a trade next to that cost and the edge over the coin in points.
- FX majors: M1 scalps are not viable at FBS standard costs (spread / median M1 range 0.5-1.2 vs gold's 0.07-0.09):
  targets of 15-20 pips or more (H1 scale). The real FX spread is unknown (no FX ticks); assume the column + 0.2-0.3 pip.
- Older half-years cost about twice as much in R with price-scaled tools (gold's spread stayed ~0.20-0.24 USD at
  half today's price): compare gross R (before costs) across periods.
- Cheapest loss cuts: bigger targets / fewer trades; avoid Asia and 20-24 UTC; never 21-23 UTC; beware release
  minute 0 for stops.

## The learning loop (the owner's): every run's stopped losers in three kinds, always against a coin-flip side

1 wrong way (less than half way to the target before the stop, no run to the target afterwards) -> the direction;
2 right way, fell short (half way or more, then back to the stop) -> the exit; 3 right way, entered too early
(stopped, then the target reached from the original entry within 120 minutes) -> the timing / the stop.
`loser_kinds.py` / `ny_lab.M1.trade` compute them. A kind is a finding only where it differs from a coin-flip side
on the same minutes.

## What has been tried and failed (do not repeat as-is; build beyond it)

Everything below picked the side about as well as a coin once tested on data it was not chosen on:
moments (Asia/London/NY opens, releases) with three playbooks (break-and-hold, sweep-and-reclaim, with the
flow) and context cells; mined pieces (P1 after a 0.1-0.3 U push; London against the flow); the draw to
yesterday's high/low (no more than a placebo); the dollar leading gold; LightGBM on 62 features (AUC 0.53-0.58,
+6 points hit rate, short of break-even); an arsenal of 11 target/stop tools; the triple screen (H1 trend, M15
RSI pullback, tick timing); a deep pullback (RSI < 40); a weighted indicator score (MACD, RSI, Stochastic,
Bollinger, EMA, ADX, CCI, ROC on M1-H1); New York iterations (break-even at 0.6 of the target was the only kept
change; stronger tide, bar turn, own-record filter, ML screen, stop-hunt reclaim, A-B-C, skip the first 30 minutes,
count 3 and re-check: all no); the confluence of H1 tide + support/resistance + price action + two of three M5
indicators (2026-03..10: 425 trades, -0.032 R; the coin -73 USD vs ours -84).

Foundations measured (round 10): gold's minute-scale returns are close to a random walk in every session and
half-year (variance ratios 0.94-1.03); no hour keeps its drift sign. The one thing with a cause that kept its sign
in both periods: after a big first minute on a release, FOMC and PCE continue and CPI reverses (small samples).

## Rules for you

- Work only in your own folder `research/2026-10-18-moments/agents/<your-name>/` (scripts, notes.md, outputs);
  you may import the existing modules. Do not edit other files, `config.yaml`, `app/`, docs; do not commit; do
  not touch MT5, the broker or any account; do not run pytest.
- Windows + Git Bash: run Python as `PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python ...` from `C:\Users\korap\taa`
  (LightGBM / scikit-learn: `data/venv-research/Scripts/python`, which has pandas/numpy/pyarrow but not `app`).
  Call `gold.below_normal_priority()` in heavy scripts; run at most one heavy process at a time (other agents
  share the 8-core machine).
- No look-ahead: features only from bars closed before the decision.
- Be honest: sanity-check numbers (trades vs days, a few trades by hand), report failures plainly, never claim
  profit beyond the measured past.
- Keep `notes.md` in your folder: each rule written before its test, then its results.
- Final answer to the lead: the best candidate(s) with the exact rule, pre-2026-03 results, the one test on
  2026-03-01 .. 10-14 (month by month, trades a day, win %, USD at 0.01 lot, R a trade, the losers' kinds vs the
  coin), and your verdict and the next idea if it fails.
