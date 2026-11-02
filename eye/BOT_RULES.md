# The bot's rules - the current specification

**This file is the specification in force** - the rules the bot uses now, their parameters, the acceptance
cases a build must pass, and the plan for judging it. Where each rule came from, and every rule tried and
dropped, is in `eye/BOT_SPEC.md` (the history); measurements are in `eye/BOT_RESEARCH.md`. A developer builds
from this file alone; where it and the history differ, this file wins.

**A second setup, the owner's run zones, has its own specification - `eye/ZONE_RULES.md` - and code (`eye/zone_bot.py`); nothing in this file applies to it, nor it to this one (2026-11-02).**

Each rule says whose it is: **(owner)** - the owner's rule or words (METHOD 2e); **[Claude]** - a definition
Claude gave where the owner gave none: a named parameter with a default, written into every decision, for the
owner to change. A question or a chart the owner shows, and any number inside one, is never a rule.

> **2026-10-30, the owner: build from the committed code and take H1 out** (*"fix it from here, and remove 1H"*).
> The side comes from **rule 16** - since 2026-10-31 **held on M15 until the opposite break, with the owner's M and W, trend legs only** (`side_rule` m15); H4's clear trend, else fading the latest run (2026-10-30 evening) is kept as `side_rule` h4, a record. **Rules 1 (the lean) and 11 (the H1 / M30 range state)
> are not used and not built** - kept below only as the record; every parameter of theirs (`h1_read`, `state_tf`,
> `fib_range`, `range_min_leg`, `range_tp`, `trend_days`, `range_days`) is withdrawn. Rules 0, 2, 3, 6-10, 12-17 stand.

## Words used

- **Fixed pivot** - a pivot returned by `app.indicators.chart_read.zigzag_pivots` (MT5's ZigZag 12 / 5 / 3, owner)
  run on the last **1,500 closed bars present in the data** of the timeframe being read, up to `now` [Claude]; it is **known** from its
  `confirm_pos` bar (the opposite candidate's bar + `backstep`) - "fixed by `now`" means that bar has closed by
  `now`. A pivot's **time** is its pivot bar's open time (UTC in the data; Thai = Asia/Bangkok for reading).
- **The setup look** (the owner, 2026-10-30, METHOD 2e "Two views": the leg - M5, 2 trading days) `setup_days` **2**
  trading days of M5. [Claude, the application:] it bounds the pivots read by rules 2 (the leg: `L0` and `H100` both
  inside it, otherwise no leg), 3 (the M5 trend) and 4 (the count) - a pivot outside it is not read,
  so a run or count is cut at the look's start; rules 6, 9 and 10 read the bars from the leg's own pivots on, which
  lie inside it. With `fib_tf` M15 the leg and the count read 2 trading days of M15; rule 3 (which reads M5
  pivots) reads 2 of M5. (The owner's trend and range looks belonged to rule 11 and are withdrawn with it.)
  **A trading day** [Claude] = **274 M5 bars, 92 M15 bars** (the stored bars of a full server day in 2026: 274 M5 at
  the median of 213 days; M15 two per 30 minutes). A look of `n` days = the last `n` x that many **closed bars present
  in the data** at `now` - a count of bars, not of calendar dates, so a weekend or holiday without bars is skipped.
  **Within a look** [Claude], the fixed pivots read are those of the 1,500-bar frame above whose pivot bar lies in the
  look - the pivots stay MT5's, the look only chooses which are read.
- **Setup timeframe** `fib_tf` [Claude] - M5 or M15, one per run; the leg (rule 2) is read on it.
- **No H1 or M30 is read** (the owner, 2026-10-30: *"remove 1H"*); **H4 is read for rule 16** (the owner: *"only up to
  H4"*).
- **The price** [Claude] - the last closed **M5** close at `now`.
- **The leg** - the move the Fibo is drawn on (rule 2): a trend leg (traded with it) or a fade leg (the latest run,
  traded against it) - rule 16 says which.
- **M and W** (owner) - the owner's M is a **buy**, formed coming down into a support; the W a **sell** at a
  resistance (the textbook's reversed).
- **Exact levels** [Claude]: Fibo 0.236 / 0.382 / 0.618; extensions 1.272 / 1.618.
- **BUY and SELL** - rules 2-10 are written for a BUY; a SELL is their mirror [Claude]: prices negated (a level
  `L0 + x * leg` becomes `top - x * leg`), highs and lows swap, above and below swap, MACD -> -MACD, RSI -> 100 - RSI;
  for a SELL, `L0` is the leg's **start, a HIGH** (0 %) and `H100` its **end, the latest fixed LOW** (100 %) - a level x is
  `L0 - x * leg` (rule 2). The spread stays a positive cost.
  Rule 16 is written for both sides.

## Order of evaluation, at each M5 close (inside a window when `windows` is on)

0 (time, the window when `windows` is on, warm-up, `max_orders`) -> 16 (the side: `side_rule` m15 - the M15 side, trend legs; no event - no order, reason "side: no M15 event"; `side_rule` h4 - H4 trend leg or a fade leg) -> 2 (the latest leg) -> 10 (has it run?) -> 3 (M5 trend, and the side) -> 4 (count, if
on) -> 6 (level, order price, bounce) -> 7 (stop) -> 8 (target, 1:2) -> 6 (played out, which needs 7
and 8) -> 9 (reach) -> write; for a trend leg whose end has just broken, 17 (the break and its retest) writes its
order instead. Rule 13 decides between a BUY and a SELL candidate; rule 12 governs the order's life.

## Parameters

| name | values | default | whose |
|---|---|---|---|
| `mode` | fib, 2e | fib (2e is a record only - not run) | [Claude] |
| `fib_tf` | M5, M15 | M5 | [Claude] |
| `fib_entry` | 0.382, 0.618, 0.236 | 0.382 (the owner's main zone; the real run may pick another - rule 6) | owner's levels and zone |
| `fib_early` | 0, 0.10 (x the leg) | 0 | [Claude], the owner's idea |
| `fib_stop` | line, line_tight (swing withdrawn with rule 2's rewrite) | line (line and swing matter at 0.618 only - at 0.382 / 0.236 the stop is `L0 - stop_buffer`; line_tight is the 0.382 variant with `fib_early`, rule 7) | line: owner (0.618 "beyond 23 %"); swing, line_tight: [Claude] |
| `fib_count` | off | off (fixed until rule 4 is redefined - rule 2) | owner: "try both"; [Claude] |
| `fib_target` | 1.618, 1.272 | 1.618 | the owner's extensions; default [Claude] (rule 8) |
| `max_entry_frac` | 0.15, 0.25, 0.35 | 0.25 | [Claude] |
| `m5_trend` | now, h100, off | now | [Claude] (rule 3: the M5 trend at the decision; h100 = the earlier test, a record; `off` = rule 3 not applied, a research variant - the owner, 2026-10-31, on running it with and without: *"do it"*) |
| `fib_lean` | on, off | on | [Claude], a research switch kept (not withdrawn), **`side_rule` h4 only**: rule 16's side refuses the other side (on), or not (off); ignored with m15 |
| `fade_min` | 1.0, off | 1.0 | [Claude], from the owner's "come down a lot" (rule 16; **`side_rule` h4 only** - no fade legs with m15) |
| `fade_entry` | 0.5, 0.382, 0.618 | 0.5 | the owner's zone "61 - 38 %"; the default [Claude] (rule 2, a fade leg; **`side_rule` h4 only**) |
| `early_leg` | 0.382, 0.618, off | 0.382 | the owner (2026-10-30: "about 38, 61 %"); the exact form [Claude] (rule 2) |
| `setup_days` | 2 | 2 | the owner (2026-10-30): the leg look, M5 trading days; with `fib_tf` M15 also applied to M15 [Claude] |
| `stop_buffer`, `target_buffer` | USD | 0.50, 0.50 | [Claude] |
| `spread` | USD | 0.30 | [Claude] |
| `max_orders` | count | 1 | [Claude] |
| `order_life_bars` | M5 bars | 24 | [Claude] |
| `min_r` | R | 2.0 | owner (1:2) |
| `side_rule` | m15, h4 | m15 | the owner, 2026-10-31 (rule 16); the form and the default [Claude]; `h4` = the rule of 2026-10-30, a record |
| `mw_tol` | 0.20, 0.15 | 0.20 | [Claude] (rule 16: two pivots this close, x the swing between, are an M or a W) |
| `windows` | off, on | off | the owner, 2026-10-31: *"run it all the time"*; the parameter and its default [Claude] (rule 0); `on` = the three windows, a record |

A combination without meaning (`fib_early` > 0 with an entry other than 0.382 or without `line_tight`; `fib_stop`
swing with an entry other than 0.618; `line_tight` without `fib_early`) is refused at start [Claude].

### The parameters come from a database (the owner, 2026-10-31)

The owner: *"I want every config value read from a db"*; *"the web page later - this for now, because some markets
may need some values switched off"*. The form [Claude], agreed by the owner (*"do it"*):

- **The database**: SQLite, `data/bot_config.db` (its own file, apart from the trading system's databases; `data/`
  is not in git, so the history below is the record). Every program that takes it has `--db PATH` (default that
  file); tests use a temporary file. **On a fresh machine** the file does not exist: the first step is
  `eye/bot_config.py seed --market XAUUSD --set default --by <who>`; a run without the file or the set stops with a
  message that names this command, with the `--db` in use when it is not the default.
- **A set** - a full set of every field of `Params` (the table above), named by **market** (`XAUUSD`, ...) and **set
  name** (`default`, `r3_off`, ...); both are path-safe - letters, digits, `_` and `-` only (they name folders),
  checked on every write and read. A market may have several sets; a set of one market says nothing about another.
- **Text form of a value** - one pair of functions in `eye/bot2e.py`, `param_to_text(name, value)` and
  `param_from_text(name, text)`, used by the database, by `Params.text()` and by the drawing tools' `name=value`
  overrides (`bot_read_day.parse_overrides` today types by the default's type, so `early_leg=off` fails - it uses
  these instead): a float as Python's `repr` (the shortest text that reads back to the same float: `0.1`, `0.382`,
  `2.0`), an int as digits, a text field as itself; `early_leg` and `fade_min` - `off`, else a float. Reading back
  must give exactly the value written (`param_from_text(n, param_to_text(n, v)) == v` for every field).
  `Params.text()` keeps its order of fields and switches to this form (`fib_early=0.1` where it wrote `0.1` already;
  `min_r=2.0` where it wrote `2`).
- **Table `config_change`** - append-only, one row per value written: `id` (integer, increasing), `market`, `set_name`,
  `name` (a `Params` field), `value` (text, as `Params.text()` writes it), `changed_at_utc` (ISO, UTC), `changed_by`,
  `note`. Nothing is updated or deleted. A set's **current values** are, per `name`, the row with the highest `id`;
  its **version** is the highest `id` among its rows. A set's values and version are read in one query (one
  snapshot).
- **Reading a set** (`eye/bot_config.py` `load_params(db, market, set_name) -> (Params, version)`; in `eye/bot_config.py`, not `bot2e.py`, so the two do not import each other): every `Params` field must be
  present and no other name may be - otherwise it stops with the missing / unknown names; **no value falls back to
  the code's default**. Each text value is turned into the field's type (float, int, text; for `early_leg` and
  `fade_min` the text `off` stays text, else a float) and the whole set goes through `Params` (its allowed values
  and combinations) - a set `Params` refuses stops the run. A set that does not exist stops the run.
- **Writing** (`eye/bot_config.py`, a command line; every write is one transaction, and the whole set as it would be
  after the write is checked through `Params` first - a write that makes the set invalid writes nothing; every write
  opens with `BEGIN IMMEDIATE`, so two writers are taken one after the other, and the existence check and the
  validation are made inside that transaction; the time `changed_at_utc` is read once in the command's `main`, in
  UTC, and passed down - the write functions take it as an argument, tests give a fixed time):
  - `seed --market M --set S --by WHO` - a new set from the code's defaults (`Params()`), note "seeded from the code
    defaults"; refused if the set exists.
  - `copy --market M --set S --to-market M2 --to-set S2 --by WHO [--note]` - a new set with the values of an existing
    one; refused if the target exists.
  - `set --market M --set S --by WHO --note TEXT name=value [name=value ...]` - one row per value **that changes**;
    a value equal to the current one is not written; an unknown name is refused.
  - `show --market M --set S` - the current values and the version; `list` - every market and set with its version;
    `history --market M --set S [name]` - the rows, oldest first.
- **Who reads it**:
  - `eye/bot2e.py` (a run): `--market` (default `XAUUSD`) and `--set` (default `default`); the parameter flags
    (`--fib-tf`, `--m5-trend` ...) are **removed** - the values come only from the set.
  - `eye/bot_research.py`: a variant is a set - `--sets S1,S2` (default `default`) on `--market` (default `XAUUSD`);
    the variant's folder is `eye/research/<market>/<set name>/` (a later run of the same set replaces it, as a
    variant's folder is replaced now); its `summary.csv` and the printed table carry the market, set and version. The JSON `--variants` and `DEFAULT_VARIANTS` are removed.
  - `eye/research/bot_view.py` and `bot_read_day.py` (drawings, no trading): take `market=` and `set=` (defaults
    `XAUUSD`, `default`) as the base; their `name=value` overrides stay for drawing only, and the drawing's text
    names the set, its version and every override.
  - Tests may still build `Params(...)` directly.
- **Markets**: the bars loaded are XAUUSD's (`eye/walk.py`); the market is checked **before** any bar is loaded - a
  run or drawing on another market stops with "no bars for <market>" until its bars are wired in.
- **Written into every decision** (rule 14): the structure text's parameter part begins `config=<market>/<set>@v<version>`,
  then every value as now (`Params.text()`); a research run's `summary.csv` has the market, set and version.
- The code's defaults (`Params()`) stay as the **seed** of a new set; the table above is the default set's values.
- **What a build must show** (tests, on a temporary database and a fixed time): a seeded set loads back equal to
  `Params()`; the text round trip for every field (and `0.1`, `off`); a set missing a field, or with an unknown name,
  stops with the names; a missing database and a missing set stop with the seed command; an invalid value or
  combination written by `set` writes nothing (the history unchanged); `set` of an unchanged value writes no row; the
  version rises with each write and `history` lists every row; `seed` / `copy` onto an existing set are refused; two
  writes from two connections both land, one after the other; another market stops with "no bars for <market>"
  before loading bars; a decision's structure text begins `config=XAUUSD/default@v<n>`; one research run from a
  seeded temporary database writes `eye/research/XAUUSD/default/` (in a temporary root) with the market, set and
  version in its summary; `bot_view` / `bot_read_day` read the set and their text names it and the overrides.

## 0. Data, time, costs

- **Data:** FBS-Demo XAUUSD bars - **H4 (rule 16), M15 and M5** (`data/history/FBS-Demo/XAUUSD`); MACD 12 / 26 / 9 as MT5 draws it
  (`walk.macd_mt5`, main line), RSI 14 (owner).
- **Closed bars only** (the project's rule, CLAUDE.md): at `now` a bar of timeframe `tf` exists only if
  `open_time + tf <= now`.
- **Warm-up** [Claude]: no decision until H4 and M5 (and M15 when it is the setup timeframe **or `side_rule` is m15** -
  rule 16 reads the M15 ZigZag) each have 1,500 closed bars before `now`.
- **All day** - the owner, 2026-10-31: *"no need [for the three windows] - run it all the time"*. The form [Claude]:
  parameter `windows`, default **off** - an evaluation at **every 5-minute time** `now` of the Thai calendar day,
  **00:00, 00:05 ... 23:55** (288 scheduled times; `now` = an M5 bar's open + 5 min, so 00:00 is the close of the
  previous day's last bar, and it belongs to the day it falls on - for the order ids `B-<day>-<n>`, the log's `date`
  and a rerun's replacement of a day). A time with no bar (the market closed) gives the reason "market closed", as
  before. `windows` **on** (a record - how every run before 2026-10-31 was made): only the owner's windows, Asia
  07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai, start and end included. A written order may fill and
  run at any time.
- **R** [Claude] = (target - entry - spread) / (entry - stop) for a BUY, (entry - target - spread) / (stop - entry)
  for a SELL, `entry` = the order price - the **planned** R. The owner's rule is the 1:2 floor; the net-of-spread form is Claude's. The spread enters only R and the
  floor; fills and touches use the bar prices.
- **This path is the owner's Fibonacci** (METHOD 2e, "The owner's Fibonacci"): its entry (rule 6) and target (rule 8)
  take the place of 2e's break-and-retest entry (2e steps 3-5) and "at a level from the left" (2e steps 1-2), by the
  owner's later words *"price usually turns before a level; when it reaches the level it usually carries on"*
  (METHOD 2e, "Levels and the turn"). The 2e setup stays in the code as `mode = 2e` - a record only; **the default `mode` is `fib`** (this path). METHOD's nine rules
  were written for the walk by hand; on this path [Claude]: no. 4 and no. 9 were replaced by 2e; no. 1-3 (frames,
  levels from the left, wait for a level) and no. 5 (the structure at the level) are replaced by rules 16, 2-3, 6 and the
  owner's "Levels and the turn"; no. 6 ("enter on a timeframe, exit on that timeframe") holds - the stop and target
  are the setup's, M5 bars only time the touches; no. 7 is rule 9; no. 8 is rule 6's played-out test.

## 1. The M30 lean (owner: "H1 is the lean; the trend is measured on M5" - read on M30 since 2026-10-30, `state_tf`)

> **Withdrawn 2026-10-30 - not used, not built** (the owner: *"remove 1H"*; the side is rule 16's). Kept as the record.

[Claude, after the owner's description as Claude restated it and the owner confirmed: price below the latest high
and making lower lows], closed M30 bars, fixed M30 pivots,
recomputed at every decision (not latched):
- **SELL lean:** `Hf` = the latest fixed M30 HIGH, `Lp` = the latest fixed M30 LOW with a time before `Hf`'s. The last
  M30 close is strictly below `Hf`, **and** some M30 bar after `Hf`'s pivot bar has a low strictly below `Lp`. No `Lp` -
  no SELL lean.
- **BUY lean:** the mirror (`Lf`, `Hp`).
- Both hold: the one whose pivot (`Hf` / `Lf`) is later. Neither: **no lean**.
- **(owner)** never against a clear lean; with no lean the M5 trend (rule 3) decides alone - *"if you wait for H1 to
  be clear, the market has run already."*
- **Under test** [Claude, at the owner's word, 2026-10-29]: on **H1** this reading, and three other readings of H1, showed no
  edge at the traded move sizes (the lean on M30 has not been measured), and October with and without it is under 30 fills (`eye/BOT_RESEARCH.md`, the
  sections from "The H1 lean and the major levels - tested"). Until the owner decides, this rule stays as written.
- **`fib_lean` off** [Claude, the owner's word 2026-10-29: run the bot with and without the lean]: the lean is still
  computed and written (rule 14; while M30 is sideways it is not read - rule 11) but refuses nothing (rule 3's refusal by the M30 trend or the lean is skipped); the M30 range's side
  (rule 11) is not affected. `on` is this rule as written. `off` goes against the owner's "never against a
  clear lean" (METHOD 2e) - it is a measurement the owner asked for, never the real-run setting without the owner's word.
- **While M30 is sideways** (rule 11) the M30 range gives the side instead of this rule.
- **With `h1_read` state (the default) this rule gives no side** - rule 11's M30 trend does; the lean is still
  computed and written for the record (rule 14). `h1_read` lean is this rule as the side outside a sideways range.

## 2. The leg - traded with it (the owner's Fibonacci; rewritten 2026-10-30)

**(owner, 2026-10-30)** on the bot's drawing of 07/10, which drew the fall 4184.25 -> 4161.42 for a BUY: *"I draw it
the other way round, to see the target below, if I expect it to go on down - drawn like this you would be buying,
right?"*; asked whether the Fibo is drawn on the leg running the way it is expected to go on, entered on the pullback,
stop beyond the leg's start, target the extension the same way: *"as I said"*. The owner's labels: **0 % at the
leg's start, 100 % at its end**; the entry on the pullback *"to around 38 - 23 %; 61 % if the bulls are really
strong"*; the stop *"beyond 0 %"* (*"beyond 23 %"* for the 61 % entry); the target 127 - 161 %. (Revision 6's leg -
the counter-move, traded against it - was Claude's misreading of *"to play an up move, draw high -> low"*;
withdrawn.)

Written for a BUY (a SELL is the mirror; rules 3-10 use these names) [Claude, the form], on the setup timeframe's
fixed pivots:
- **A SELL, spelled out**: `H100` = the latest fixed LOW (the end), `L0` = the fixed HIGH immediately before it (the
  start); the leg = `L0 - H100`; a level x = `L0 - x * leg`; entry 0.382 = `L0 - 0.382 x leg`; stop beyond 0 % =
  `L0 + stop_buffer`; target = `L0 - fib_target x leg + target_buffer`. The early leg: the latest fixed pivot a HIGH
  `Hf` with a fixed LOW `Lp` before it, no high above `Hf` since, the lowest low since at or below
  `Hf - early_leg x (Hf - Lp)` - `L0` = `Hf`, a provisional `H100` = that lowest low. **Example (07/10/2026 M5, the
  owner's)**: start 4184.25 (02:00), end 4161.42 (05:50), leg 22.83 - entry 0.382 = **4175.53**, stop 4184.75, the
  161.8 % extension 4147.31, target 4147.81.
- **Which leg is traded** - rule 16: with `side_rule` m15 (the default) a trend leg of the M15 side; with h4 (the
  record) a trend leg in H4's direction when H4 trends clearly, else a fade leg against the latest run.
- **`H100`** = the leg's end = **the latest fixed HIGH**; **`L0`** = the leg's start = **the fixed LOW immediately
  before it**. The leg = `H100 - L0` > 0 (else no leg). Levels `L0 + x * (H100 - L0)` - the owner's labels exactly
  (0 % = `L0`, 100 % = `H100`, 127.2 / 161.8 % above `H100`).
- **An early leg** (the owner: *"if price has come a long way, that is enough to draw the line already"*; how far -
  *"about 38, 61 %"*) - `early_leg` **0.382** (default) / 0.618 / off: when the latest fixed pivot is a LOW `Lf` (the
  next HIGH not yet fixed) with a fixed HIGH `Hp` before it, and over the setup-timeframe bars after `Lf`'s pivot bar up
  to the last bar closed by `now` no low is below `Lf`, and the highest high of those bars is at or above
  `Lf + early_leg x (Hp - Lf)`: the leg is drawn at once with `L0` = `Lf` and a **provisional `H100`** = that highest
  high (the earliest bar holding it; it moves with new highs). When the next HIGH fixes, the fixed leg takes over.
  An early leg is the side's latest leg when one stands.
- **While there is no trade, a break moves the Fibo** (the owner: *"if it breaks, you have to move the Fibo - the run
  is not over"*, *"while we have no trade yet"*): a high beyond a **fixed** `H100` (a SELL: a low below it) - the run goes on: the drawing is retired
  (rule 10) and the next leg is drawn once the new end is a fixed HIGH or an early leg stands (a provisional `H100`
  simply moves with new highs - not a break); a low below `L0` after `H100` (a SELL: a high above its `L0`) - the leg's start is broken: **no leg**.
- **The setup look**: `L0` and `H100` (a provisional `H100`'s bar) inside it, otherwise no leg.
- **The count** (rule 4) and rule 7's `swing` stop were written for the old counter-leg: **not used with this leg**
  (`fib_count` fixed off, `fib_stop` swing withdrawn) until they are redefined.
- **One order per leg**: key = side, setup timeframe, `L0` time (an early leg and the fixed leg that follows it share
  `L0`, so they are one leg); the leg is **used** once an order on it **fills** - an order that expires or is withdrawn
  unfilled leaves it free (while there is no trade the Fibo moves) - in this run or an earlier one (the keys of the
  rows already in the ledger are used from the start of a run). Until used, while it is the latest leg, it is a
  candidate at every decision, inside the setup look; refused once it may pass later. Rule 10 ends it for good.

- **Two kinds of leg** (rule 16 says which is traded): **a trend leg** - the leg as written above (traded with it: for
  a BUY, `L0` = the start low, `H100` = the end high, entry on the pullback, target beyond the end); **a fade leg** -
  the latest run traded against it. A fade leg, written for a **SELL after a run up** (a BUY after a run down is the
  mirror) [Claude, from the owner's drawing of 07/10]: the run = the fixed LOW `S` and the latest fixed HIGH `E` after
  it (or an early leg's provisional `E`); the owner's drawing - **0 % at `E` (the top), 100 % at `S`**; a level x is
  `E - x * (E - S)`; **entry** `fade_entry` **0.5** (default; 0.382 and 0.618 variants - the owner's zone *"61 - 38
  %"*) as a sell limit at `E - fade_entry x run`, written once price is below it (rule 6's bounce mirrored: an M5 bar
  after `E`'s bar with a low strictly below the order price, and the price strictly below it); **stop** `E +
  stop_buffer` (beyond 0 %); **target** `E - fib_target x run + target_buffer` (1.618 - the reachable level first, the owner's rule 8: no level from
  the left is in the way on this path); R under `min_r` - **no order** (1:2 is a filter, the target is not pushed
  further to reach it - the owner, 2026-10-29: *"no trade, for now"*); rules 9 and 12 as written; for a fade leg **rule 10 reads** - a high strictly above `E` after `E`'s bar (the run goes on: the leg
  ends, a resting order is withdrawn - rule 12's withdrawal); **played out** (rule 6) - the chosen target touched before
  the fill; the key - side, timeframe, `E`'s time. **A BUY after a run down**: `E` the latest fixed LOW, `S` the fixed
  HIGH before it; a level x = `E + x * (S - E)`; a buy limit at `E + fade_entry x run`, written once price is above it;
  stop `E - stop_buffer`; target `E + fib_target x run - target_buffer`, R under `min_r` - no order; the leg ends on a low strictly below `E`.
  **Example (07/10/2026 M5, with `fib_lean` off - H4 itself read down that morning, so the default trades the SELL
  trend leg; this fade is the latest run only until the 4161.42 low fixes, decided 06:30-06:50)**: the run 4154.21 (06/10 23:55) -> 4184.25 (07/10 02:00), 30.04; SELL limit
  at 0.5 = 4169.23; stop 4184.75; **target 4136.15 (1.618), R 2.11**. At 0.382 (4172.77)
  R would be 3.03, at 0.618 (4165.69 - where price was at 07:00) R 1.53. On the stored bars price rose to 4169.59 after
  07:00 (the 0.5 limit fills) and fell to 4134.84 by 12:00 - *report* the order of the stop and target touches.

**What changes in rules 6-10 with this leg** (their formulas stand): every "after `L0`'s pivot bar" becomes **after
`H100`'s bar** (the pullback starts at the leg's end) - rule 6's bounce and played-out, rule 10's run; rule 6's default
`fib_entry` becomes **0.382** (the owner's main zone, "38 - 23 %"; 0.618 is the owner's "if the bulls are really
strong"); rule 7's stops stand as written (0.382 / 0.236: `L0 - stop_buffer` = beyond 0 %; 0.618: the 23.6 % level
- `stop_buffer` = beyond 23 %); rule 8's target `L0 + fib_target x leg` is the extension beyond the end, as the owner
draws it.

## 3. The trend on M5 (owner: "the trend is measured on M5")

The owner, 2026-10-30, on the October trades: *"a win rate this low means trading against the market on M5 - find
it"*; 20 of 25 fills had been taken with no M5 trend at the decision (`eye/BOT_RESEARCH.md`, "Where the bot reads M5
wrongly"). **The M5 trend is read at the decision** [Claude], `m5_trend` **now** (the default), on **M5** fixed pivots
fixed by `now`, for M5 and M15 legs alike: the latest two fixed M5 HIGHs and the latest two fixed M5 LOWs by time -
**UP** when the later high is strictly above the earlier high **and** the later low strictly above the earlier low;
**DOWN** when both are strictly below; otherwise **no M5 trend** (also with fewer than two of either). **A BUY needs
UP** (a SELL: DOWN); otherwise no order on this leg - **for a trend leg only; a fade leg is not refused by this rule (rule 16)**. *(The latest two highs and lows are taken wherever they fall: before `L0`, around it or all after it - M5 is UP when
price, at the decision, is making higher highs and higher lows, whichever swings those are. Rule 10 still ends the
leg once a high goes above `H100`.)* `m5_trend` **h100** (a record, for comparison): a BUY needs `H100` strictly above
the latest fixed M5 HIGH whose time is strictly before `H100`'s and which is fixed by `now` (none - no order). Then the side (**rule 16**): a BUY candidate is refused when the side is SELL (a SELL candidate when it is BUY);
no side yet: nothing is refused; skipped when `fib_lean` is off - **all of this with `side_rule` h4 only**; with m15
rule 16 has already kept only the side's legs (no event - no order on either side).

## 4. The pullback's count - a filter (owner: "try both, counting and not counting")

> **Not used since rule 2's rewrite (2026-10-30)** - written for the old counter-leg; `fib_count` is fixed off until it
> is redefined on the leg traded with it.

`fib_count`: **off** (default) - any pullback run passes. **On** (owner: "3-5 peaks", counted as **legs, both sides** -
asked whether that means legs with lower lows, the owner said yes; so a leg here = one low of the run [Claude's
rendering]): the run has **3 to 5** lows - 1 low and 6 or more fail [Claude] - **and** divergence at `L0` against the previous low
of the run on at least one oscillator (owner: "one is enough") - [Claude's rendering]: MACD main or RSI at `L0`'s pivot
bar higher than at the previous low's pivot bar, setup timeframe. **Or the owner's M** (owner: two peaks that make an M
count; a clear M is entered without divergence): a run of exactly **2** lows passes without divergence - any two-low run is taken as the M
(the owner, 2026-10-29: *"try it this way first"*). Which oscillator
diverged (MACD / RSI / both / none) is written into every decision (owner: "the record says which").

## 5. The trend run's count - no chasing

> **Withdrawn 2026-10-30 - not used** (the owner: *"cut what makes the decision worse - with the Fibo, cut the trend legs at
> the entry"*). `max_trend_legs` is withdrawn. Kept as the record.

The owner, on the spec: *"two problems: chasing the price, and no trade when it goes sideways - don't let these two
happen."* [Claude - provisional, for the owner to judge] The `H100` price is the anchor (for an M15 leg too). Take the
fixed **M5** HIGHs fixed by `now` with a time strictly before `H100`'s, latest first, while each is strictly lower than
the one counted before it (the first strictly lower than `H100`); the trend's legs = 1 + their number. At
`max_trend_legs` (5; variant 3) or more, no order. [Claude's inference]: the owner's 3-5 count, applied to the trend,
says a fifth leg is the trend ending, and buying its pullback is chasing.

## 6. The entry

- **Level** `fib_entry` - from the owner's *"wait for it to fall back to around 38 - 23 %; if the bulls are really
  strong, maybe from 61 %"*. **The default is the level that works best** (owner, 2026-10-29: *"use the level that works
  best"*): [Claude] the three are run on the same months; best = the highest mean R a filled trade, every trade drawn
  and checked (ties: more trades); the owner confirms; **the choice is made on months that are not clean (rule 15) and
  frozen before the forward test.** Until the real run: **0.382** (the owner's main zone, 2026-10-30, with the leg traded
  with it - rule 2).
- **Order price** = the level + `fib_early x leg` (above the level for a BUY) - `fib_early` [Claude, the owner's idea of
  getting in before the line]: 0 by default; variant 0.10 with `line_tight`, at the 0.382 level only.
- **The bounce** [Claude]: an order is written only once an **M5** bar after `H100`'s bar (opening at or after that
  bar's close) has a high strictly above
  the order price, and only while the price is strictly above it - a **plain buy limit**. A touch of the order price
  after the bounce and before `now` does not stop it (no order was resting then).
- **Played out** [Claude], checked after rules 7 and 8: on the **M5** bars from that first M5 bar above the order price
  up to `now`, a high at or above the order's target (rule 8), or a low at or below the stop on a later M5 bar - no
  order. (On that first bar only the target counts.)

## 7. The stop

The owner's words differ by case: 2e step 6 - *"beyond the highest top / lowest bottom"*; the Fibonacci - *"the SL is
beyond 88 % - 0 %"*, and for the 61 % entry *"beyond 23 %"*. **The owner confirmed (2026-10-29): for the 0.618
entry the stop is beyond 23 %** - the Fibonacci's specific words govern:
- 0.382 / 0.236: `L0 - stop_buffer` (beyond the lowest bottom - both sentences hold).
- 0.618, `fib_stop` **line**: the 23.6 % level - `stop_buffer` ("beyond 23 %"; above `L0`, so not beyond the lowest
  bottom).
- 0.618, `fib_stop` **swing** [Claude, a variant]: one `stop_buffer` below the lower of the 23.6 % level and the **lowest** fixed
  setup-timeframe low formed after `L0` and fixed by `now`. No such low: the line stop.
- `line_tight` [Claude, a variant] (with `fib_early`): the 0.382 level - `stop_buffer`.

## 8. The target - the ladder

The owner: *"the target from the Fibo; the take-profit placed is what can be reached"* - 1.618 if nothing major stands
before it, else 1.272, else just before that level (METHOD 2e). **A level is major only if price turns at it more
often than at a control** - the test in `eye/BOT_RESEARCH.md`, "The H1 lean and the major levels - tested" [Claude, at
the owner's word *"find the answers by testing and proof"*, 2026-10-29]. No tested band - H1 or H4 pivots, one or
several - turned price more than the control with any consistency, so **no level counts as major on this path**
and the take-profit is the extension:

- **TP** = `L0 + fib_target x leg - target_buffer`, `fib_target` 1.618 (variant 1.272) [Claude, the owner's two
  extensions; 1.618 is the owner's first step]. A SELL: the mirror, `L0 - fib_target x leg +
  target_buffer`.
- If R (rule 0) is under `min_r`, or the TP is not beyond the order price (above it for a BUY, below for a SELL), no
  order.
- A level definition that passes the test (consistently above the control, month by month) brings back the steps before a major level (1.272, then just before the
  level); until one does, none is built.

*Example (27/10, BUY, leg 3989.14 -> 4025.45 = 36.31, entry 0.382 = 4003.01, stop 3988.64): the raw 1.618 extension is
4047.89; TP = 4047.89 - 0.50 = 4047.39, R = (4047.39 - 4003.01 - 0.30) / 14.37 = 3.07.*

## 9. The entry must be reachable

METHOD's nine rules, no. 7 - *"the entry must be a price the market can reach from here"* - with the owner's reason,
*"an obvious level may never be reached precisely because it is obvious."* [Claude] abs(the price - the order price) at
most `max_entry_frac` x the leg. The owner's "4 USD" was an example.

## 10. A leg that has run is over

The owner confirmed it (2026-10-29: *"confirm the two you said"* - this rule and rule 9's reach), from the drawn
October trades. [Claude's test], one test for both uses: once any **M5** bar after `H100`'s bar - an M5 bar whose
open is at or after that bar's close - has a high **strictly above** `H100` (a SELL: a low strictly below its `H100`) (the run goes on - the Fibo moves, rule 2) (a touch at `H100` is not enough), no order on the
leg, ever, and a resting order on it is withdrawn (rule 12).

## 11. Sideways - the M30 state gives the side (owner: sideways is read on the trend timeframe - M30 since 2026-10-30 - the trend for the entry on M5)

> **Withdrawn 2026-10-30 - not used, not built** (the side is rule 16's). **Its M30 state FAILED the market check.** Built from
> this text (`eye/state11.py`, stable and tested) and drawn on July-October, it read against the price structure in
> every month (`eye/BOT_RESEARCH.md`, "Rule 11's state drawn on July-October", "The side from price structure
> against rule 11"). The side is being studied from price structure instead (`eye/SIGNAL_STUDY.md`). The text below
> is kept as the record of what was built.

The owner, 2026-10-29: *"sideways means in the 1-hour timeframe, and the trend is found in the 5-minute"* - and on
2026-10-30: *"change it all to M30"*; the range
counts once price has gone back and forth inside it, *"at least one to two times each side"*, and then the trade is in
the fourth and fifth leg - *"if it can be found from the third leg, that is good"*; asked whether, at the top edge
with M5 turning down, the sell is taken on the M5 Fibo pullback as on a leg: *"yes"*. The edges are the owner's
*"around 88 - 127 %"*, the target *"around 100 %"* (METHOD 2e, "The owner's Fibonacci"). `fib_range` on: rule 11 is
read; off: no M30 state is read at all - never sideways, no range side, no edge target, no M30 trend side; with
`h1_read` lean the lean alone (rule 1), with `h1_read` state no M30 side.

- **The M30 state** [Claude, the owner's way of reading it, 2026-10-30: the swings inside a range do not end it; a
  range ends when M30 closes beyond its edge (the break line, below), and the market then trends that way until price goes back and forth
  again - the owner, on the drawn prototype: *"about this; fix the code to do what we think"*]. **Where a range starts**
  (METHOD 2e, the Sideways row - Claude, from outside sources, the owner 2026-10-30: *"yes"*): a range starts when a
  trend stops making new extremes - the trend's last extreme is one edge, the first bounce from it the other; it
  counts once price comes back to test the first edge without a new extreme beyond it; the swings inside are not
  counted; a break is an M30 close beyond the break line (127 % of the range above its low, -27 % below it - the
  owner's edge zone runs to 127 %; using its end as the break line is [Claude]). **A pivot beyond the first edge with
  no close beyond the break line is a test of that edge, not a new extreme** (the owner, 2026-10-30, choosing it: *"once
  it breaks, you have to wait for the retest anyway"*). **One walk** (the owner's choice, 2026-10-30, of Claude's
  proposal; the form [Claude]): at `now` the M30 fixed pivots (fixed by `now`, time order, oldest first) and the closes
  of the **1,500-bar frame** ("Words used") are walked once, as below; the looks then decide what of it counts ("The
  M30 state at `now`"). A look never starts a walk. "The frame" below is that 1,500-bar frame:
  - **A range** is a pair of consecutive pivots `E`, `B` - `E` the extreme it starts from, `B` the next pivot (the first
    bounce): edges `lo` = the lower price, `hi` = the higher, `h = hi - lo`; **legs = 1**; the **last touch** = the
    kind of `B` (HIGH or LOW). **The edges never move** while the range stands. The first range of the frame is its
    first two pivots [Claude - at the frame's start no trend is known; the frame starts about 32 trading days back,
    far before any look],
    and no close before the second of them is tested; after a break, `E` and `B` are as named under "A break". A pair
    with `h` <= 0 is dropped: the two pivots after the pair (the third and fourth counted from its first) start the
    range, and so on until a pair has `h` > 0 - the same wherever the pair arises, the frame's first range or the pair
    named after a break [Claude; equal pivot prices are rare]. **The closes between `E` and `B` are not tested** [Claude] - the range does not exist until `B` is fixed
    (MT5's ZigZag does not keep every close between two pivots: on the stored M30 bars 125 of 6,282 pivot pairs had
    a close outside them, by up to 16.04 USD; such a close is ignored).
  - **Each later pivot `P(i)`** - first the **closes** on the bars after the previous pivot's bar up to and including
    `P(i)`'s bar are tested for a break (below); when there is none, `P(i)` is taken in: a HIGH at or above
    `lo + 0.88 h` **touches the high edge**, a LOW at or below `lo + 0.12 h` **touches the low edge** - a touch beyond
    the edge, however far its pivot price goes, is a touch like any other while no close has broken (only a close
    breaks) and the edge stays where it is (the owner's choice above); a touch of the other
    edge than the last touch adds **1 leg** and becomes the last touch (two touches of the same edge in a row add
    nothing). A pivot between the two is **in the middle and ignored** - the range stands.
  - **A break**: the first M30 close strictly above `hi + 0.27 h` is a break **up**, strictly below `lo - 0.27 h` a
    break **down** (the break line). The range ends and **the M30 trend** becomes up / down. The next range's
    `E` is **the extreme of the breaking move**: of the two pivots that bound the segment the breaking close lies in
    (`P(i-1)` and `P(i)`), the HIGH for a break up, the LOW for a break down - the ZigZag's turning point of that move,
    so `E` may lie after the breaking close (the move went on past the 127 % line and
    turned at `E`); `B` is the pivot after `E`. The walk goes on with the pivot after `B`. While `B` is not yet fixed
    there is no range and the trend stands. Every break is handled alike: a later break of the new range the same way
    is the trend going on, the other way a trend the other way - and in both the same rule names the next `E` and `B`.
    The walk keeps **the last break**: its way and the bar of its breaking close.
  - **After the last pivot**, the closes on the bars after its bar up to the last closed bar at `now` are tested for a
    break the same way; a break there leaves the trend in force with no range at `now` (its `E` and `B` are found at
    a later `now`, once the segment is closed by a pivot).
  - **The walk at `now`** gives: the range in force (`E`, `B`, `lo`, `hi`, legs, last touch; none while a break's `B`
    is not fixed) and the last break (none if the frame holds no break).
  - **The M30 state at `now`** - the first that holds, in this order [the order is Claude's, from the owner's two
    views and choices]:
    1. the range in force has **legs >= 2** and its `E`'s bar lies in **the range look** (4 trading days) - M30 is
       **sideways** with that range (the range traded first);
    2. the last break's breaking close lies in **the trend look** (7 trading days) - M30 is **trending** that break's
       way (a range of legs 1 after it, or its `B` not yet fixed, does not change this; nor does a range of legs >= 2
       whose `E` is older than the range look);
    3. the range in force has **legs >= 2** - M30 is **sideways** with that range (the owner, 2026-10-30: no trend on
       the 7 days means a range, *"so it can be traded as a range"*);
    4. otherwise - **no M30 side** (no break in the 7 days and the range in force not yet tested back - legs 1 - or no
       range: [Claude] a range counts once price has gone back and forth in it, METHOD 2e's Sideways row).
  - **When the state changes** [Claude, a consequence checked in rule 14]: only at an M30 close where a pivot is fixed,
    a close breaks, or a look's start passes the range's `E` or the last break's close - never because the frame's
    start moved.
  - **The M30 trend's side** (`h1_read` state): up - **BUY** only; down - **SELL** only (rule 3).
- **Sideways** is the state above; the range's edges are `lo` / `hi` as they stand at `now`.
- **The leg being traded** = the range's legs + 1 (the move away from the last touch): **3** with two legs. Trades are
  taken in legs `range_min_leg` (default **3**, the owner's *"from the third leg"*; variant 4) to **5** (the owner's
  *"the fourth and fifth"*). A sideways M30 whose leg is under `range_min_leg` (leg 3 with the variant 4): **no order**
  [Claude - the range is not yet ready for that variant, and M30 is not trending].
- **Leg 6 on** - the owner, 2026-10-29: *"at the sixth leg, be ready for it to run through the edge, which can be
  where we make a big profit"*. [Claude's reading, confirmed by the owner the same evening:] from leg 6 the range gives **no side and no edge target**: the
  legs of either side are taken on the M5 trend (rules 2-10; the lean is still not read - M30 is still sideways),
  with rule 8's extension as the target, so a move through the edge is not cut at it.
- **The side**, in legs `range_min_leg` to 5 [Claude, from the owner's legs]: away from the last touch - the last
  touch at the high edge: **SELL**; at the low edge: **BUY**. Only legs of that side are traded (leg 6 on: above); rules 2-10 apply unchanged (the M5 trend is found by
  rules 2-3, the entry by the Fibo, rule 6). The lean (rule 1) is not used while M30 is sideways: an M30 that reads as
  sideways has no clear lean (the owner's "sideways is read on the higher timeframe"; the precedence is [Claude]).
- **The target** (owner, 2026-10-29: *"go by the 5-minute target, and look at the 1-hour price edges alongside, as
  support, resistance and the take-profit"*) - `range_tp`: `edge` (default; the formula [Claude]) - the nearer of rule 8's extension and the opposite edge less `target_buffer` (a BUY:
  min(extension TP, `hi - target_buffer`); a SELL: max(extension TP, `lo + target_buffer`)); `ext` - rule 8 alone. R
  and the 1:2 floor are computed on the target chosen.
- A range order is a leg order in every other way (rule 12: its fill, withdrawal by its `H100`, hold); the decision
  writes the M30 state in its structure: which of the four cases of "The M30 state at `now`" gave it; sideways - the
  edges, `E`'s and `B`'s prices and Thai times, the legs, the leg traded, the last touch; trending - up / down and the
  Thai time of the breaking close.

## 12. Orders and their life [Claude, except the hold]

- **At a time** `max_orders`: pending orders plus open trades. **Event order at each M5 close** [Claude]: first the
  bar just closed updates the orders already written (fills, exits, expiries, withdrawals); then the decision
  counts `max_orders` and evaluates.
- **Fixed when written:** an order's price, stop, target and planned R never change. The scorer reports the
  **realised** R: the actual fill price in the numerator, the planned risk (order price to stop) in the
  denominator (below).
- **Fill**, on **M5** bars from the bar after the decision, within `order_life_bars` (the last included): a buy limit fills on the first bar whose
  low is at or below its price, at min(that bar's open, the price); a sell limit at max(open, price). Not filled after
  the last of them: **expired** (`no fill`); it frees `max_orders`; its leg is free again (rule 2 - a leg is used only once filled).
- **Withdrawn** - by an M5 bar **before** the fill bar only; **the scorer** writes the reason as the row's `why` (the
  bot writes only the markers below; where both a target and an `H100` crossing happen on one bar, the target's
  reason is written): its target touched
  (`no fill (stop or target first)` - a stop cannot be reached first, the limit lies between); a leg's `H100` crossed strictly (`withdraw beyond <H100>` in the decision
  text), judged on M5 bars as rule 10 says. A bar that both fills and withdraws keeps the fill.
- **Held (owner)** until the stop or the target, no time limit, judged on M5 bars from the fill bar on. On the fill bar
  only the stop counts; from the next bar a bar touching both counts as the stop. **Exit price:** the stop or target
  price; a bar that opens beyond the stop exits at its open [Claude]. **Realised R** = (exit - fill - spread) / (order
  price - stop) for a BUY (mirror for a SELL) - `r_net`: the denominator is the planned risk, the same for every fill
  of the order, so a gap fill beyond the stop is still defined [Claude]. A trade still open when the data ends is `open`, not a result. A change
  of rule 16's side does not touch an order already written.

## 13. Which one, when several qualify [Claude]

A BUY and a SELL candidate at one decision (a leg of each side - `side_rule` h4 only: when rule 16's side is none, or with `fib_lean` off; with m15 there is never more than the side's):
the smaller |the price - the order price|; then a BUY before a SELL.

## 14. What the bot writes, and the acceptance cases [Claude]

- **Files:** decisions to `eye/bot_ledger.csv`, the log to `eye/bot_log.csv`; research runs to
  `eye/research/<variant>/`.
- **The decision row** - the columns of `eye/ledger.csv`: id, cutoff_thai, decided_at, reader = `bot2e`, side, entry,
  stop, target; fill, exit, why, r_net, at_decision_r, missed_by left to the scorer; trigger, rules, conflict, setup
  empty; `structure` names the leg (a trend leg: `L0`, `H100`; a fade leg: `S`, `E` and "fade"; prices and Thai times), the levels, the
  order price, stop, target and its extension, planned R, rule 16's side in its written form, the M5 trend comparison, the counts and which
  oscillator diverged, every parameter, and the withdrawal marker.
- **The log** - one row per evaluated bar: the time, rule 16's side, each rule's state and numbers, and the reason no order
  was written; with several candidates, the reason of the one that got furthest in the order of evaluation (the last
  rule it reached; on a tie, the BUY).
- **Acceptance cases** - evaluated with the window test switched off (`windows` off, the default); times are
  Thai, `now` = the time given; `fib_tf` M5, other parameters at their defaults unless named. Each expected outcome
  below is what the rules give; the developer computes every case from the bars and **reports** each one - a case that
  does not come out as written is reported, not bent to fit; where a part is marked *report*, the developer reports
  what the bars give:
  - **Rule 16 and the fade leg** (`side_rule` **h4**, the record) - 07/10/2026 07:00 M5: H4 **down** (highs 4315.65 -> 4228.63, lows 4244.12 -> 4110.78);
  the SELL trend leg 4184.25 -> 4161.42, refused by rule 3 (M5 not DOWN), no order. With `fib_lean` off at 06:35: the
  fade SELL of rule 2's example (limit 4169.23, stop 4184.75, target 4136.15, R 2.11) - on the stored bars it fills on the 07:10 bar and
  reaches the target at 11:55 Thai (Codex) - *report* what the bot writes.
  - **Withdrawn with rules 1 and 11** (2026-10-30): every earlier case that read H1, the M30 state, the lean or the
    range target (they stay in git history and `eye/BOT_SPEC.md`). The 27/10/2026 18:30 case
    used the old counter-leg - withdrawn with rule 2's rewrite. **Rule 2 (the leg traded with it)**: at 07/10/2026 07:00
    and 07:25, M5, the SELL leg is start 4184.25 -> end 4161.42, entry 0.382 = 4175.53, stop 4184.75, target 4147.81
    (rule 2's example); whether an order is written there (rules 3, 6, 9, 16) - *report*.
  - Rule 3 (`m5_trend` now) at the filled October decisions, against `eye/research/m5_structure_check.py` (the same
    reading, written apart): the bot's UP / DOWN / no trend equals the script's at every one - *report* any difference;
    with `m5_trend` now, none of the 20 decisions the script marks MIXED is written.
  - Rule 12 has no stored-bar case yet: the developer tests each branch on constructed bars (unit tests)
    and reports which stored-bar case first exercises it.

## 15. How results are judged

[Claude, from the owner's "no test or research run until the code is confirmed correct"] **Before any trading run**,
every reading a change touches is run without trading on several stored months, drawn over the candles and passed
by the owner's eye (CLAUDE.md, "How the system is developed", step 7 - the owner, 2026-10-30: *"passing is the bot
reading the chart as close to the market as possible"*). No number is believed until each trade behind it is drawn
(`eye/draw_trades.py`) and checked against these rules. **The bar** is the owner's goal:
at least **+0.15 R a trade after costs** (CLAUDE.md); [Claude] not judged on fewer than 30 filled trades. The real run: the defaults, beside these
variants one at a time - `fib_entry` 0.618 and 0.236, `fib_early` 0.10 with
`line_tight` (at 0.382), `fib_tf` M15, `fib_target` 1.272, `max_entry_frac` 0.15 and 0.35, `fib_lean` off,
`m5_trend` h100. October 2026
first, then the stored months before it (M5 from 2025-10), month by month - **not clean**: the research that chose `H100` and the entry
depth used them. **The clean test is forward**, on the months after 2026-10-28 as their bars arrive.

## 16. The side - held on M15 until the opposite break, with the owner's M and W (the owner, 2026-10-31)

The owner, on 2026-08-12 where H4 read "not clear" through a 400 USD rise: *"there is no LL yet"*; *"two things -
buy the pullback, and wait for a clear picture to sell; to sell, the ZigZag should make an LL first"*; *"an LL on
M15 is enough to sell"*; on the drawing *"I see W and M clearly - try applying it"* (the owner's usage: an M a buy, a
W a sell); after the drawings of three weeks, the owner chose to judge it by the trades (*"C"*). Exactly [Claude, the
form - the prototype `m15_mw.py`, `eye/BOT_RESEARCH.md` "The side held on M15 until the opposite break"]:

- **`side_rule` m15** (the default): on M15 fixed pivots (MT5 ZigZag 12 / 5 / 3 on the last 1,500 closed M15 bars,
  fixed by `now`), taken in order; for each pivot `q` with the pivot before it `m` and the one before that `p` (the
  same kind as `q`):
  - `q` a HIGH: `|q - p| <= mw_tol x (max(p, q) - m)` - a **W** -> **SELL**; else `q > p` - an **HH** -> **BUY**;
  - `q` a LOW: `|q - p| <= mw_tol x (m - min(p, q))` - an **M** -> **BUY**; else `q < p` - an **LL** -> **SELL**;
  - otherwise (a lower high, a higher low, outside the tolerance) - no event.
  The side is that of the **latest event**; no event among the pivots - no side, no order (reason "side: no M15
  event"). `mw_tol` **0.20** [Claude; looked at on one week only - a parameter, 0.15 the variant].
- **The side's legs**: side BUY - only BUY **trend legs** (rule 2, "a trend leg": the early leg when `early_leg` is
  on and one stands, else the fixed leg) - the owner's *"buy the pullback"*; side SELL - only SELL trend legs. **Fade
  legs are not used** with `side_rule` m15 (a turn is the side changing: an LL or a W). Rule 17 (the break and its
  retest) applies to these trend legs as written - its order is written only while the M15 side **at that decision**
(`now`) is the leg's side [Claude]; rule 3 to trend legs as written.
- **`side_rule` h4** (a record - the rule of 2026-10-30, every run before 2026-10-31): H4 trends clearly, else fade the
  latest run, as below.
- **Written** (rule 14): `M15 side BUY (HH a -> b, <Thai time of b>)` / `SELL (W a / b, ...)` / `(M ...)` / `(LL ...)`,
  or `M15 side: no event`; the H4 reading is still written (below), for the record only, when `side_rule` is m15.

### 16 (record, `side_rule` h4) - fade the latest run, unless H4 trends clearly (the owner, 2026-10-30)

The owner: *"simply: if price has run up, look for a sell; if price has come down a lot, look for a buy - unless the
big trend, like 1D / 4H, is very clear, then go with the trend on the pullback or the bounce"*; then *"only up to H4
is enough - reading the big timeframe has been tried many times without success, but try it"*. On 07/10/2026 07:00
(the run 4154.21 -> 4184.25): *"buy what? sell!"* (METHOD 2e). Exactly [Claude, the form]:

- **H4 trends clearly** - on H4 fixed pivots (MT5 ZigZag 12 / 5 / 3 on the last 1,500 closed H4 bars, fixed by
  `now`): the latest two fixed HIGHs and the latest two fixed LOWs - **up** when the later high is strictly above the
  earlier **and** the later low strictly above the earlier; **down** when both strictly below; otherwise **not clear**.
  Up: only BUY legs **with** the trend (rule 2, "a trend leg"); down: only SELL trend legs.
- **Not clear - fade the latest run**: the run = the latest fixed pivot `E` of the setup timeframe and the fixed pivot
  `S` immediately before it (no early form for a fade); **a run up or down is faded only when it is long** (the owner: *"if price
  has come down a lot"*) - `fade_min` **1.0** [Claude]: the run at least `fade_min` x the leg before it (from the fixed pivot
  before `S` to `S`), otherwise no fade leg - `E` a HIGH (a run **up**): a **SELL**; `E` a LOW (a run
  **down**): a **BUY** (rule 2, "a fade leg").
- **`fib_lean` off** (a research switch): H4 is not read - always a fade leg.
- **Rule 3 (the M5 trend) applies to trend legs only** [Claude]: a fade is by its nature against the short trend that
  made the run (on 07/10 at 07:00 M5 was UP, and the owner sold); a fade leg is not refused by rule 3. To be judged on
  the drawings and the run.
- **Rule 17 (the break and its retest) applies to trend legs only**; a fade leg ends when its run goes on (below).
- **Written** (rule 14): `H4 up / down / not clear (highs a->b, lows c->d)` and `trade: trend leg BUY` /
  `fade SELL after the run up a -> b`.
- **Data** (rule 0): H4 is read again for this rule (stored H4 bars); M15 is no longer needed for the side. The M15
  strip B (the previous rule 16) is withdrawn; `eye/signal_study.py` stays as research.

## 17. The break and its retest - the second entry on a leg (the owner, 2026-10-30)

The owner, on 07/10/2026 when the pullback to the entry never came: *"once it breaks the low it has to be entered
anyway, whichever way the Fibo is drawn"*; how - *"by the principle, the retest of the old low"* (METHOD 2e step 5);
the stop - option **C** (beyond the bounce); the target - *"261 may be a bit far; 161 - 200 % may be the minimum"*,
then *"try it"*. The owner added: *"I think the edge is when the big trend is down"* (for this sell) - recorded; the
run reports these trades by the side (rule 16) and by H4's reading. Exactly [Claude, the
form], for a BUY on a **fixed** rule 2 leg (`L0` the start low, `H100` the end high); a SELL spelled out below:
- **The break**: the first setup-timeframe close strictly above `H100`, among the bars whose open is at or after the
  close of the bar on which `H100` became fixed (no close before the pivot was known counts), while the leg's
  pullback order (rule 6) has not filled and no low after `H100` has gone below `L0`.
- **The bounce low** `Lb` = the lowest low of the setup-timeframe bars after `H100`'s bar, up to and including the
  bar before the break bar.
- **The order**, written at the break close (rules 0, 3 and 16 apply as to any order; rule 6's bounce and played-out,
  rule 9 and rule 10 do not): a **buy limit at `H100`** (the retest from above); **stop** `Lb - stop_buffer`; **target**: `L0 + 1.618 x leg - target_buffer`, or when that gives R under `min_r`, `L0 + 2.0 x leg - target_buffer`
  (the owner: *"161 - 200 % may be the minimum"*); still under `min_r` - no order (no 261.8 %).
- **Its life**: rule 12 as any order (`order_life_bars`, fills, the hold), except the withdrawal by an `H100` crossing -
  this order exists because of it; it is withdrawn only by its target touched before the fill (a stop cannot be reached first - the limit lies
  between). At the break, the leg's resting pullback order is withdrawn first (rule 12's event order), so
  `max_orders` counts after it.
- **The leg**: the break retires the drawing for pullback orders (rules 2, 10), but this order belongs to the old leg
  (rule 2's key); once it - or the pullback order - fills, the leg is used. The leg drawn from the new end (rule 2)
  is another leg, with its own pullback order; when both qualify at one decision, rule 13 chooses (the smaller distance
  from the price, then a BUY before a SELL).
- **A SELL**: the break - the first close strictly below the fixed `H100` (the end low); no high after `H100` above
  `L0`; `Hb` = the highest high after `H100`'s bar up to the bar before the break; a sell limit at `H100`; stop
  `Hb + stop_buffer`; targets `L0 - 1.618 x leg + target_buffer`, else `L0 - 2.0 x leg + target_buffer`, as for a BUY.
- **Example (07/10/2026 M5, a SELL)**: start 4184.25, end 4161.42 (leg 22.83), `Hb` 4169.89 (06:30); the break - the
  M5 close at 07:30 Thai, 4160.09; sell limit 4161.42, stop 4170.39; 161.8 % gives R 1.48 (under 2), **200 % - target
  4139.09, R 2.46**. On the stored bars it fills on the 07:40 bar (high 4162.67) and reaches 4139.09 on the 10:10 bar (Claude, re-checked on the stored bars; Codex had said 08:50 - wrong), before 4170.39.

## Withdrawn - do not build

None of these is a parameter to implement; they live only in the history (`eye/BOT_SPEC.md`): a side from H1
structure alone (`fib_side` h1 / entry / any - replaced by the lean); revision 5's leg drawn in the trade's direction; the M1 entry; a fixed USD
reach; "the leg's extreme must sit on a level" and 2e's "Where" row on this path (replaced by the owner's "Levels and
the turn"); the bands of H1 / H4 pivots capping the target and their parameters (`major_tf`, `level_bars`,
`level_min_age_h`, `band_frac`, `band_legs` on this path - no band turned price more than a control); **the range read on the setup timeframe (M5 / M15) and faded at its
88 % / 12 % edges** (rule 11 before 2026-10-29 evening - Claude's misreading: the owner's sideways is on H1, the trend
on M5); **the H1 range that needed every pivot at an edge** (rule 11 of 2026-10-29 evening - its middle swings
ended every range; replaced by the H1 state, 2026-10-30); a depth-dependent choice of `H100`; the 2e
path as a live option; the nine rules no. 4 ("trade the fifth leg") and no. 9 (target a full leg away) - replaced by
2e before this path.

## Code status, 2026-10-31 (not a rule)

**Everything above is built** (rule 16's `side_rule` m15 since 2026-10-31 - below) in `eye/bot2e.py` (from the committed code, git HEAD 968f37e, a piece at a time by a
Sonnet developer, each piece checked by Claude's real mutation runs and Codex; tests green - 276 across the bot, its
tools, architecture, signal study and state11; **committed** c09c13e, the full suite green): H1 / the lean / the old range / mode 2e taken out;
H4 read for rule 16 (a trend leg when H4 trends clearly, else a fade leg); rule 2's trend leg (with the early leg) and
fade leg; rule 17; the setup look; rule 3 (`m5_trend` now / h100 / off). Rule 5 and the count removed. The M15 strip
side (built 2026-10-30) is withdrawn. Tools: `eye/research/bot_view.py` (MT5-style, per moment / per new leg),
`bot_read_day.py`; the runner `eye/bot_research.py` (variants into `eye/research/<variant>/`).
**First run** (October 2026, `r3_now` / `r3_off` - `eye/BOT_RESEARCH.md`, "October 2026 with rule 3 on and off"):
-0.23 / +0.11 R a resolved fill on 17 / 32 fills; fades -0.40 R each (10); not yet drawn and judged.
**Built** (2026-10-31, the full suite green): rule 0's `windows` (default off). The build: the parameter in `Params`; `decide`'s window
test follows `p.windows` when its `windowed` argument is not given (`bot_view.py` keeps passing `windowed=False`
and is unchanged); `walk_days` (`eye/bot2e.py`) and `walk_day` (`eye/research/bot_read_day.py`) step through the 288
times 00:00 - 23:55 of the day with `windows` off and through the three windows with it on, and both use the
calendar day of `now` as the day (rule 0). The comment above `WINDOWS` is corrected to `start <= now <= end` (what
`window_of` does). `bot_read_day.py` lists the times outside the three windows under the
name "all day". What a build must show: `decide` at 03:00 Thai on a weekday with the market open gives a reason
other than "outside window" with `windows` off, and "outside window" with `windows` on; one day's walk with
`windows` off has 288 scheduled times (some may be "market closed"), with `windows` on 93 (25 + 25 + 43 - each
window's start and end included); an order written at 00:00 carries that day's date in its id.
`eye/score.py` `start_of` [Claude, found by the developer]: a row's `decided_at` is its last bar's open (`dd/mm HH:MM`),
which for a decision at 00:00 is 23:55 of the **previous** day while `cutoff_thai` holds the new day; the start is
then that previous day at 23:55 + 5 min (= `now`), never a day later - when `decided_at`'s `dd/mm` is the day before
`cutoff_thai`'s date, the date is moved back one day. The same row scored by `walk_days`' live-order check starts at
the same time.
**Built** (2026-10-31, Codex reviewed until it found nothing, the full suite green): "The parameters come from a
database" (under Parameters) - `eye/bot_config.py`; runs before it wrote `eye/research/<variant>/`, runs after it
`eye/research/<market>/<set>/`. A fresh machine seeds first: `eye/bot_config.py seed --market XAUUSD --set default --by <who>`.
**Built** (2026-10-31; Codex reviewed four times until it found nothing, Claude's mutation runs, the full suite green):
rule 16's `side_rule` m15 and `mw_tol` (the side held on M15 with M and W; trend legs only; no event - no leg). What a build must show: on the stored bars `side_rule` m15 gives the side **BUY at 12/08/2026 13:45 Thai**
(Claude's hand count: the low pair 4356.72 / 4360.22 is an M - 3.50 apart, 0.20 x 47.45 = 9.49 - and the latest
event is the HH 4404.17 -> 4415.88 - 11.71 apart, just outside 0.20 x 55.66 = 11.13, so not a W) - the developer
*reports* the events the code finds; the W 4441.12 / 4449.54 (8.42 apart, the swing to 4396.49 53.05 -
15.9 %) - at **2026-08-13 10:30 Thai** (a later cut-off) the latest event is that W -> SELL at `mw_tol` 0.20 and the
HH -> BUY at 0.15 (Codex's read-only recomputation, 2026-10-31: 8.42 against 10.61 at 0.20); unit tests on made-up pivots for each of HH, LL, M, W, a lower
high and a higher low (no event), the tolerance edge (equal = inside), no event -> no side; a fade leg is never
offered with m15; `side_rule` h4 gives exactly today's results (the existing rule 16 tests pass with `side_rule` h4).
**Open**: levels from the left / the owner's price clusters as obstacles to a target - deferred: Claude's forms of
them were measured on 2026-10-31 / 11-01 and did not mark the turns (`eye/BOT_RESEARCH.md`); next come the single
trades drawn with the owner (HANDOFF, 2026-11-01). The
set-aside work is in `eye/wip/`; `eye/state11.py` (rule 11, failed) is kept, unused.
