# Cross-check the research session's code (2026-10-27, evening)

The owner asked you to review what I wrote today. Be adversarial. Earlier today you caught two real
things (a test that passed with the H4 cutoff moved a bar early, and `should_close` unreachable from an
extra lane), and this afternoon you caught the one that mattered most: my measurement scripts ran
`bots.P()` instead of the shipped parameters, so an afternoon of conclusions described a setup we do not
ship. **Assume there is another one of those in here.**

Read-only. Write only `research/2026-10-26-three-bots/REVIEW_FINDINGS_2.md`. Change no code.
Use `.venv\Scripts\python.exe`.

## Known stale, do not spend time on

`RULES_LOCKED.md` and the knowledge-base entries F22, F23, F24, X44, R10 contain numbers from the wrong
parameter set. I know; I am rewriting them. Review the **code**, not those two documents.

## What to review, in priority order

### 1. The measurement scripts — highest risk

`geometry.py`, `edge_by_condition.py`, `momentum.py`. These now drive which rules we adopt, so a quiet
error here is expensive.

- **Point-in-time correctness.** Every reading must come from a bar CLOSED before the decision. Check
  each resample and each `readable` / `closed_at` offset by hand - H1 frames are close-stamped, so the
  shift back by one hour before resampling is load-bearing. A reading that peeks is the worst bug here.
- **`geometry.path_stats`.** The counterfactual re-settles the same entry and target with a stop k times
  wider, on the real M1 path, and gives it the ORIGINAL deadline (07:00 Bangkok next day), not the
  moment the original exited. The first version used the original's exit time and that was wrong - the
  win rate did not move with the stop width, which is what exposed it. Is the current version right?
  Is `got.r * k` the correct way back into R of the original risk? Work it out yourself.
- **`momentum.momentum`.** Momentum = (close - 50-bar mean) / 14-bar Wilder ATR of that frame. Check the
  ATR is Wilder's and matches MetaTrader 5, that the D1 and H4 resampling is correct, and that `read_at`
  cannot return a bar that had not closed.
- **`edge_by_condition.regimes`.** bull = close over a RISING 50-day mean, bear = close under a FALLING
  one. Check the `closed_at` offset and that a trade on the day a regime flips reads the earlier label.
- **The binning and the split.** `fitted` is `2025-10-20 <= at < 2026-10-24`. Does any table mix the two
  halves in a way that lets the fitted half carry a claim about the unseen one?

### 2. The guard I added after your catch

`bots.py`: `SHIPPED`, `_shipped()`, the `ValueError` in `run()`, `audit.BEST = bots.SHIPPED`, and
`test_bots.py`. Does the guard actually close the hole, or can the same mistake still be made another
way - for example by passing a dict with the wrong contents, or `replace(P())` with no change? Is
`test_the_shipped_set_matches_the_app_strategies` comparing the right fields, and would it really fail
if someone changed a default in `app/strategy/`? Try it.

### 3. The engine fix you found, as I implemented it

`app/engine/backends.py`, `position_manager.py`, `broker_positions.py`, `orchestrator.py` and the three
tests (`test_position_manager.py`, `test_broker_positions.py`, `test_engine_lanes.py`). The main lane
calls both `on_bar` and `on_lane_bar`; I pass `close_check=lane.name != MAIN` so the main lane does not
ask twice. Can a position now be closed twice, or closed by a lane that does not own it? Is the broker
path safe when `self.close` is called inside a loop over `bot_positions(symbol)`?

### 4. The H4 tests I split after your finding

`test_an_unclosed_h4_bar_never_reaches_the_zigzag` and
`test_the_newest_closed_h4_bar_does_reach_the_zigzag`, plus the shared `h4_highs_seen` helper. Does the
pair now cover both directions of the cutoff, and does the helper itself re-implement any production
logic?

## How to answer

One section per item: what you checked, how, and the verdict. For anything wrong: the exact line, how
you proved it, and what it would cost. **Where you found nothing, say so plainly** - a clean verdict
from you is worth something, and padding it is not. Finish with the single thing you would most want
changed.
