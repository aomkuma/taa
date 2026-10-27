# DEV_SPEC 2 — two levers on the trend bots, both off by default (2026-10-27)

Written by the research session for the developer session. The previous round's spec contradicted itself
in two places and cost seven broken tests; this one is deliberately narrower. **If any sentence here
conflicts with another, stop and say so in `DEV_NOTES_2.md` instead of guessing.**

## Why

Journal week 1 (`JOURNAL.md`, 19–27 Oct 2026, real ticks): 6 trades, +5.73 R. The three losers were all
sells from `trend_box_down` while gold rose 4,004 → 4,026 — the bot kept selling through the turn because
its only trend read is the H1 ZigZag. Separately, the two winners went **0.81 R and 0.38 R against the
entry** before they ran, which is why a break-even stop was tested and rejected: the stop sits inside the
noise this entry normally lives in.

Two levers follow from that. **You implement them; you do not tune them and you do not judge them.** No
sweeps, no parameter search, no "which value is best" — the research session measures that.

## The absolute rules

1. **Both levers default to OFF, and OFF must be byte-identical to today's behaviour.** Proof required:
   the whole existing test suite passes unchanged, and `parity.py` still reports its current match rate.
2. **Never re-implement production logic inside a test.** A test that computes the expected value with a
   copy of the formula it is testing is worth nothing — the research session shipped exactly that mistake
   last week and the developer session caught it. Every test calls the production function or
   `evaluate()`.
3. **Every new test must be proven to bite.** For each one, break the single production line it covers,
   run that one test, confirm it fails, restore. Report each mutation and its result in `DEV_NOTES_2.md`.
4. Planted bugs: at least 8 new ones aimed at this change only, in a crash-safe script
   (`plant_bugs_2.py`, byte-for-byte backups, restore in `finally`, recover leftovers on the next run).
   Commit its output as `plant_bugs_2_output.txt`. Report caught / MISSED honestly — a MISSED you report
   is useful, a MISSED you hide is the whole problem.
5. Do not touch `.env`, `TRADING_MODE`, anything DEMO or LIVE, or any credential. Do not `git commit`,
   `git push`, or deploy. Leave the working tree with no planted bug in it.
6. `ruff format`, `ruff check`, `mypy app`, `bandit` and the full `pytest` must all pass before you stop.
7. Do not change any default, any existing parameter value, or `config.yaml`.

## Lever A — the big picture must not disagree (`require_big_tf: bool = False`)

New field on `TrendBoxParams` (so both directions inherit it), default `False`.

When `True`, after the H1 stepping check passes and before the box search:

- Build H4 from the lane's H1 frame **by calling `RangeBreak._h4_from_h1`** — import it, do not write a
  second copy of that resampling. (If the import direction is wrong, move the function to a place both
  can import from and say so in the notes; do not duplicate it.)
- Keep only closed H4 bars with the same rule `range_break` uses: `(h4.index + 4h) <= at`, then `.iloc[-300:]`.
- Fewer than 300 bars → `self.hold(ctx, ReasonCode.INSUFFICIENT_DATA)`.
- Run `zigzag()` on those H4 highs and lows, take the **confirmed** swings only, and read them with the
  existing `stepped()` helper.
- `trend_box_down` holds with reason `"H4_AGAINST"` when `stepped(...) == "UP"`.
- `trend_box_up` holds with reason `"H4_AGAINST"` when `stepped(...) == "DOWN"`.
- `"FLAT"` never blocks either direction.

When `False`, no H4 frame is built and no work is done.

## Lever B — a floor under the stop distance (`min_stop_atr: float = 0.0`)

New field on `TrendBoxParams`, default `0.0`, `ge=0`.

When greater than zero, after the stop is computed from the box edge and before the R check:

- Let `atr` be the H1 ATR over the last 14 **closed** H1 bars of the lane's H1 frame, using Wilder's
  smoothing exactly as `foundation.py` computes it (MetaTrader 5's own formula). If that module cannot be
  imported from `app/`, write the 14-period Wilder ATR in `app/strategy/trend_box.py` and give it its own
  hand-worked test against values you compute by hand in the test, not with the same code.
- `floor = min_stop_atr * atr`.
- If `abs(stop - price) < floor`, move the stop to `price + floor` for a sell, `price - floor` for a buy.
- The R check (`min_r`, `min_take_profit`) then runs against the **widened** stop, so a trade whose reward
  no longer covers it is refused as it is today.
- The `Condition` list gains `Condition("stop_floor", True, detail=f"{floor:.2f}")` only when the stop was
  actually widened.

When `0.0`, nothing is computed and nothing changes.

## Tests to add (hand-worked, in the existing test files)

- Lever A off: an H4 frame that would block changes nothing.
- Lever A on, `trend_box_down`, H4 stepping UP → HOLD `"H4_AGAINST"`; the same bars with H4 FLAT → the
  entry it gives today; the same with H4 DOWN → the entry it gives today.
- Lever A on, `trend_box_up`, mirrored.
- Lever A on with 299 H4 bars → `INSUFFICIENT_DATA`.
- Lever A on must not read a forming H4 bar — same shape as
  `test_an_unclosed_h4_bar_never_reaches_the_zigzag`, through `evaluate()`.
- Lever B off: a tiny box changes nothing.
- Lever B on: a stop nearer than the floor is widened to exactly `price ± floor`, with the number worked
  out by hand in the test.
- Lever B on: a stop already wider than the floor is untouched.
- Lever B on: widening the stop pushes R under `min_r`, so the signal is refused.
- The ATR helper (if you write one): at least one case worked out by hand.

## What to write when you are done

`research/2026-10-26-three-bots/DEV_NOTES_2.md`:

- each lever, what you implemented, and anything in this spec you found unclear or contradictory;
- the table of new tests × the mutation that proves each one bites;
- the planted-bug table, caught and MISSED;
- the proof that defaults are unchanged (test counts before/after, the parity number);
- **what you did not do, and why.**
