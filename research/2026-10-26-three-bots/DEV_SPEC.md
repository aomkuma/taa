# DEV SPEC — the three bots as real strategies

**For:** a developer session (Codex / GPT-6-Luna) working in `c:\Users\korap\taa`.
**Written by:** the research session, 27 Oct 2026. Roles: research writes the spec and measures the result;
this session builds it (memory `taa-roles-research-dev-measure`).

Read `CLAUDE.md` and `docs/CODING_STANDARDS.md` first and follow them. Everything below is already measured;
**do not re-tune any number** — if a value looks wrong, say so and stop, do not change it.

---

## 1. What exists today

`research/2026-10-26-three-bots/bots.py` is a standalone research harness: it reads stored Parquet bars,
walks M5 closes, and settles trades on M1 bars. It is **not** wired into the app. It proved three setups on
XAUUSD over 2025-10-20 .. 2026-10-23 (12 months), spread 0.30 USD deducted per trade:

| bot | trades | win % | R / trade | total R | worst drawdown |
|---|---|---|---|---|---|
| DOWN (trend pullback, sell) | 38 | 50 % | +0.280 | +10.7 | −5.3 R |
| RANGE (H4 box break) | 41 | 22 % | +0.488 | +20.0 | −4.2 R |
| UP (trend pullback, buy) | 23 | 26 % | +0.133 | +3.0 | −3.9 R |
| **all three, one account** | **102** | **33 %** | **+0.331** | **+33.7** | **−9.4 R** |

Reproduce with `.venv\Scripts\python research\2026-10-26-three-bots\round6.py`.

Already in the app and reusable: `app/strategy/zigzag.py` (MetaTrader 5's ZigZag 12/5/3, tested in
`tests/unit/test_strategy_zigzag.py`, 45 planted bugs all caught).

## 2. The job

Port the three setups into `app/strategy/` as real strategies that run through the normal engine and backtest
path, with the same decisions as the research harness. **No new behaviour, no new parameters, no tuning.**

### 2.1 Files to add

- `app/strategy/trend_box.py` — `TrendBox` (shared base, not registered), `TrendBoxDown` (`name =
  "trend_box_down"`), `TrendBoxUp` (`name = "trend_box_up"`).
- `app/strategy/range_break.py` — `RangeBreak` (`name = "range_break"`).
- Register all three in `app/strategy/catalog.py` → `STRATEGIES`.
- Add a lane for them in `config.yaml` (entry timeframe **M5**), `enabled: false`.
- Tests: `tests/unit/test_strategy_trend_box.py`, `tests/unit/test_strategy_range_break.py`.
- A parity script: `research/2026-10-26-three-bots/parity.py` (see §4).

### 2.2 Frames each strategy needs

`ctx.frames` must carry M1, M5, H1 and H4. The decision is taken at the close of an **M5** bar. Only bars
closed by `ctx.market.decision_time_utc` may be read — the context builder already enforces this; never widen
a window yourself.

## 3. The rules, exactly

All prices are XAUUSD. "ZigZag" always means `app.strategy.zigzag.zigzag(high, low)` with the module defaults
(depth 12, deviation 0.05, backstep 3) and **only its confirmed swings** (the first element of the returned
tuple; the second, still-forming point must never be used — it repaints).

### 3.1 Shared gates (all three)

1. **Windows.** Decide only inside: Asia 07:00–09:00 Thai, London 13:00–15:00 Thai, New York 08:00–11:30
   New York local (so it follows US daylight saving). Outside them: HOLD.
2. **One position per strategy.** Each strategy holds at most one position of its own; the engine's position
   book enforces this. `trend_box_down` and `trend_box_up` can never both be in a trade (their conditions are
   opposites), so at most two positions are open at once.
3. **No entry into a running push.** Let `risk = |stop − entry|`. Over the **last 60 minutes of closed M1
   bars**, let `run = entry − min(low)` for a SELL and `max(high) − entry` for a BUY. If `run > 1.2 × risk`,
   HOLD. (Reference: `bots.P.run`, `run_minutes` 60.)
4. **Size of the prize.** `|take_profit − entry| ≥ 5.00 USD` and `|take_profit − entry| ≥ min_r × risk`, with
   `min_r` per strategy below. Otherwise HOLD.
5. **Daily flat.** Every position is closed at 07:00 Thai. Implement as position management, not as an entry
   rule.

### 3.2 `trend_box_down` (SELL) and `trend_box_up` (BUY)

Read the ZigZag on the **last 400 closed H1 bars**.

1. **Stepping.** Let `H[-1], H[-2]` be the last two confirmed swing highs and `L[-1], L[-2]` the last two
   confirmed swing lows. DOWN needs `H[-1] < H[-2]` **and** `L[-1] < L[-2]`; UP needs both higher. Else HOLD.
2. **The leg.** Let `A, B` be the last two confirmed swings in order. DOWN needs `A` a high and `B` a low; UP
   the reverse. `leg = |A.price − B.price|`; if `leg ≤ 0`, HOLD.
3. **The box.** Over the **closed M5 bars before the decision bar**, take the **longest** window of `n` bars
   with `24 ≥ n ≥ 6` whose `top − floor ≤ box × leg` (`top` = max high, `floor` = min low of those `n` bars).
   Search `n` from 24 downwards and use the first that fits. If none fits, HOLD.
   *Two details that are easy to get wrong, both load-bearing:* the window is `past.iloc[-n-1:-1]` in the
   research — the decision bar itself is **excluded** from the box; and once a box of size `n` fits, that box
   is the only one considered — if it then fails the retrace (§3.2.4) or the trigger (§3.2.5) the answer is
   HOLD, the search does **not** continue to shorter boxes.
4. **The retrace.** `mid = (top + floor) / 2`. DOWN: `retr = (mid − B.price) / leg`; UP: `retr = (B.price −
   mid) / leg`. Require `0.382 ≤ retr ≤ 0.786`. Else HOLD.
5. **The trigger.** DOWN: the decision bar's **close** is below `floor`. UP: above `top`. Else HOLD.
6. **The plan.** Entry = that close. DOWN: `stop = top + buffer × (top − floor)`, `take_profit = B.price`
   (must be below the entry). UP: `stop = floor − buffer × (top − floor)`, `take_profit = B.price` (above the
   entry). Then apply gate §3.1.4.

**Parameters (defaults — these are the measured values):**

| | `box` | `retrace` | `buffer` | `min_r` | `min_take_profit` | exit |
|---|---|---|---|---|---|---|
| `trend_box_down` | 0.20 | 0.382 – 0.786 | 0.20 | 1.2 | 5.0 | stop / take-profit only |
| `trend_box_up` | 0.33 | 0.382 – 0.786 | 0.20 | 1.2 | 5.0 | break-even at +0.5 R |

### 3.3 `range_break`

Read the ZigZag on the **last 300 closed H4 bars** (build H4 by resampling H1 with `4h`, `first/max/min/last`,
then drop rows with gaps).

1. **Not trending.** Using the same two-swing test as §3.2.1 on the H4 swings: if it is stepping up or down,
   HOLD. Only a flat H4 qualifies.
2. **The box.** `hh` = the last confirmed H4 swing high, `ll` = the last confirmed H4 swing low. Require
   `hh > ll`.
3. **The trigger.** Let `prev` be the previous M5 close and `price` the decision bar's close.
   BUY when `price > hh ≥ prev`; SELL when `price < ll ≤ prev`. Else HOLD. (Price leaves the box on this bar.)
4. **The plan.** `rng = hh − ll`. BUY: `stop = hh − buffer × rng × 0.25`, `take_profit = price + tp_range ×
   rng`. SELL: `stop = ll + buffer × rng × 0.25`, `take_profit = price − tp_range × rng`. Then gate §3.1.4.

**Parameters:** `buffer = 0.3`, `tp_range = 0.5`, `min_r = 0.8`, `min_take_profit = 5.0`, exit = break-even at
+0.5 R.

### 3.4 The break-even exit (`trend_box_up`, `range_break`)

In `manage_position`: once the position has been **+0.5 R ahead at any point since entry** (measured on closed
M1 highs/lows, not on closes), move the stop to the entry price and leave it there. Never move it against the
position. `trend_box_down` does not do this — it measured worse with it (+0.280 → +0.094).

The engine's existing `break_even` management is close but triggers on a different multiple; use the
strategy's own `manage_position` so the 0.5 R and the "ahead at any point" reading are exact, and leave the
lane's `management.break_even` off for these strategies.

*Ordering within a bar (matters for parity):* in the research the stop is tested **before** the break-even
move on the same bar, so the stop that applies during a bar is the one set at the end of the previous bar. A
bar that both reaches +0.5 R and trades back to the original stop is a full stop-out, not a break-even exit.

## 4. Acceptance

A change is done only when all of these hold.

1. **Hand-worked unit tests** for every piece, in the style of `tests/unit/test_strategy_zigzag.py`: small
   frames with numbers worked out in the test's comments, covering for each strategy — the stepping test
   (passes and both ways of failing), the longest-box search (a box that fits, one too tall, the decision bar
   excluded), each retrace boundary (0.382 and 0.786 inclusive, just outside on each side), the trigger (close
   through vs. only the wick through), stop and take-profit arithmetic, each §3.1 gate rejecting, and the
   break-even exit (not yet +0.5 R; reached then price comes back).
2. **Planted bugs.** Add a script in the style of `research/2026-10-24-replay/plant_bugs_29_33.py` with at
   least 15 bugs across the new code (one per rule above, plus the ZigZag "confirmed only" rule and the
   60-minute run window). Every bug must be caught. Commit the output file.
3. **Parity.** `research/2026-10-26-three-bots/parity.py` runs the new strategies through
   `app.cli backtest` (or `app.backtest.engine` directly) on FBS-Demo XAUUSD, 2025-10-20 .. 2026-10-23, and
   compares against `bots.py`'s trades: a table of trade count, R/trade and total R per strategy, plus every
   trade the two disagree on with the reason. **Differences are expected** — the engine enters on the next
   quote and uses real tick spread, the research enters at the M5 close with a flat 0.30 — so the acceptance
   is: entry *decisions* (symbol, side, bar) match at least 90 %, and every unmatched decision is explained in
   the script's output. Do not change the rules to force a match; report the gap.
4. **Green:** `.venv\Scripts\python -m pytest -q`, `ruff format` + `ruff check` on `app tests scripts`,
   `mypy app`, `bandit -q -r app -c pyproject.toml`.
5. **Architecture:** `tests/unit/test_architecture.py` passes unchanged (no new package needed — both files go
   in the existing `app/strategy`).
6. **Tickets:** add a ticket under Phase 18 in `docs/TICKETS.md` for this work and tick its items with
   `.venv\Scripts\python scripts\tickets.py tick <id> <n>` then `sync`, in the same change.

**The research session checks the result independently** before it counts as done: it re-runs `parity.py`,
re-derives a sample of trades from the stored bars by hand against §3, and runs its own planted bugs against
the new code. Report what you could not make match rather than making it match by changing a rule — a silent
rule change found at that check sends the whole ticket back.

## 5. Rules for this work

- **No tuning.** Every threshold above is a measured result. If a test shows a rule cannot be implemented as
  written, stop and report it; do not pick a different number.
- **No new indicators or filters.** If a rule seems to need one, report it.
- **Closed bars only.** Never read the forming bar, never the ZigZag's forming point.
- **Keep it out of live.** The lane is `enabled: false`. Do not touch `.env`, `TRADING_MODE`, DEMO or LIVE.
- **Ask before** `git push`, any Railway deploy, or anything touching the owner's accounts. Committing per
  ticket is fine.
- Code, comments and docstrings in **English**.

## 6. What this does NOT fix (research keeps these)

Known weaknesses, measured, not this session's job — do not try to solve them:

- the result leans on a few trades: dropping the best 5 of 102 leaves +0.092 R/trade;
- the parameters were chosen on the same 12 months they were measured on; first half +0.522 R/trade, second
  half +0.186;
- 8.5 trades a month against the owner's goal of a trade most days;
- worst drawdown −9.4 R (−57 % of the account at 6 % risk a trade).
