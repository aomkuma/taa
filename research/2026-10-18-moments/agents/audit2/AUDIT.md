# The system audit, second agent (2026-10-19 15:41 UTC = 22:41 Thai .. 2026-10-20 05:12 UTC = 12:12 Thai)

Round 2: 2026-10-20 05:47 .. 06:11 UTC = 12:47 .. 13:11 Thai - items 1 and 4, dev2's swings (sections 10-12).
Round 3: 2026-10-20 10:05 .. 10:33 UTC = 17:05 .. 17:33 Thai - group b on `load_learning()`, the PLAN-1 runner, dev2's two
test gaps (sections 13-15).

Brief: `../AUDIT_PROMPT.md`. Every number below comes from a script and output named next to it. Nothing here reads
the exam period (2026-04-18 .. 2026-10-17): stores are read with pyarrow row filters that keep only the learning
parts / older history, or only the post-exam days (2026-10-17 on) for alignment checks, so no computation sees an
exam row.

## The table

| # | Component | What was checked | How | Evidence | Verdict | Fix / relay |
|---|---|---|---|---|---|---|
| 1a | `app/market_data/history_download.py` (+ `scripts/download_history.py`, `gateway.rates_range`) | the download reaches the newest bar the terminal holds | the real log of the two 2026-10-19 runs; a FakeMT5 subclass that serves stale local history (`LazySyncFake`); 14 hand-worked tests; 14 planted bugs; one read-only run on the real terminal | before: 7 failed / 7 passed (HEAD module); after: 14 passed; planted 14 of 14 CAUGHT; targeted suites 80 passed; ruff / mypy / bandit clean | **FAIL -> fixed** | see section 1a |
| 1b | `gold.bars` (the OLD / NEW M1 merge) | the cut at the first NEW bar, no duplicates, no gap at the joint, NEW wins | 4 hand-worked tests on synthetic stores; 5 planted bugs; the real stores (pre-exam) against a set-union second source | 30,022 shared minutes equal (OHLC, volume, spread); 0 OLD-only minutes lost by the cut; joint gap 1 min; 1,628,641 bars = the union; 5 of 5 CAUGHT | **PASS** | - |
| 1c | `plib.load` | START inclusive, END exclusive, duplicates (keep last), columns | 1 hand-worked test with bars at START-1, START, a duplicate, END-1, END; 5 planted bugs; the real pre-exam stores | first bar 2023-08-01 00:00; 674,443 bars before START dropped; unique, sorted, float64; 5 of 5 CAUGHT | **PASS** (one note) | note: END = 2026-10-17, so `plib.load()` returns the exam rows; only the callers keep them out -> **item 4: `plib.load_learning()` added** (section 11) |
| 1d | UTC alignment through the DST changes | the M1 store against the raw ticks on the 9 change weeks; the release minutes (an outside clock) in every regime; the daily break | `check_dst.py`: ticks re-aggregated from the raw files; every release before the exam: where the largest M1 range sits within +-90 min; the raw `time_server`; 1 hand-worked test of `gold.releases()` across both changes + 3 planted bugs | OHLC equal on 100 % of 59,363 minutes (9 weeks, out_check_dst.txt); US-on / EU-off weeks: CPI / NFP / PPI / FOMC peak at 0 in 15 of 21, at +-1 in 1, at +-60 in 0; 08:30 New York: 12:30 UTC 151 of 274 at 0 / 1 at +60, 13:30 UTC 81 of 159 at 0 / 5 at +60; 3 of 3 CAUGHT | **PASS** | - |
| 2a | `precursors/indicators.py::bars` against MT5's own H1 / H4 / D1 | OHLC, counts, the server-day boundaries through DST | matched to `data/history/.../{H1,H4,D1}.parquet` through MT5's raw `time_server` (not the code under test); 5 hand-worked tests (winter day, both DST nights, a quiet last minute, clock bars) + the 6 earlier ones; 11 planted bugs | H1 16,032 = 16,032, H4 4,706 = 4,706, D1 1,192 = 1,192, OHLC equal on all, max diff 0.00000, 0 bars on one side only; post-exam days H1 15/15, H4 3/3; 11 of 11 CAUGHT | **PASS** | - |
| 2b | `avail` = the last M1 minute + 1 | how often it is before the bar's end, and why | every bar of the learning parts and of 2021-09 .. 2026-04: is the next M1 bar 30+ min after the last one (market closed) or not (quiet last minutes) | learning parts: M15 / H1 / H4 / D1 0 quiet-minute bars (all 127 early ones are closes); M5 5 bars, 9 minutes in all. 2021-09 .. 2026-04: H1 4 (5 min), M15 14 (38 min), M5 56 (90 min), H4 1 | **PASS** (one note) | note: on those bars the prices at `avail` equal the forming bar's, only the "complete" flag is 1-4 min early |
| 3 | `precursors/foundation.py` ATR / RSI / MACD / EMA | MT5's formulas | the earlier literal MQL5 ports (13 tests, re-run); 4 new hand-worked tests (a gap bar's TR = previous close - low, RSI with a loss in its seed, MACD in fractions, the EMA seed); 11 planted bugs | 17 passed; 11 of 11 CAUGHT | **PASS** | - |
| 4 | the swings: `precursors/fingerprint.py::zigzag`, `dev/patterns.py::zigzag` (read only), `precursors/zones.py` | one bar is never two turns; every pivot confirmed by a later bar; no look-ahead; zones known only when confirmed | 10 hand-worked tests + 20 random series; HEAD vs fixed on every real series the callers build (M1 / M5 / M15 / H1, ATR x 2 / x 3, 10 USD, from 2023-08-01 and 2025-09-01); the future replaced by its mirror at 100 decisions per TF (both ZigZags) and 100 moments for `levels_at`; 15 planted bugs | **the start-up phase made one bar two turns** (a peak confirmed by its own bar, then a trough at the same bar): before 22 failed / 5 passed, after 27 passed; on the real series it happened once (H1 from 2023-08-01, x 2; only the first pivot pair changes, the last at 2023-08-01 14:59), 0 differences in the learning parts; look-ahead 100 / 100 equal on M1 / M5 / H1 for both, with power 100 / 100; zones: 1,004 of 1,004 swings known at the 2nd bar's avail, levels 100 / 100 equal, power 100 / 100; 15 of 15 CAUGHT | **FAIL -> fixed** (fingerprint); **relay** (dev) | fix: `precursors/fingerprint.py` (3 lines); relay: `audit2/test_relay_dev_zigzag.py` (2 failing on `dev/patterns.py`; the developer applied the fix at 12:08 Thai on 2026-10-20, now 2 passed; it changes 0 of its pivots) |
| 5 | the simulators: `surrender.trade` / `run`, `tick_straddle.trade` / `run`, `sr_break.take`, `touches.outcome` / `approach`; the developer's `p2_trades.simulate` (read only) | fills, stops on the bid / ask with the gap, the target as a limit, ties on one tick, the daily break, midnight, R over the fill's risk | 10 hand-worked tests + the earlier 26 (`test_surrender`, `test_tick_straddle`, `test_sr_break`, `test_touches`); 6 hand cases on the developer's `simulate`; 19 planted bugs; the callers' learning-part entry hours from their own input frames | **a trade open at midnight UTC was cut at 23:59:59** (`surrender.run`, `tick_straddle.run` read one UTC day's tick file): before 3 failed / 6 passed (HEAD), after 52 passed with the earlier suites; every current caller enters 11:20 .. 16:00 UTC in P1 / P2, so 0 earlier results change; the developer's `simulate` 6 of 6; 19 of 19 CAUGHT | **FAIL -> fixed** (latent) | fix: `precursors/tick_straddle.py` (`span_ticks`: the next day joined, never an exam day), `precursors/surrender.py` (uses it) |
| 6 | the costs: M1 spread x 0.01 + 0.08, entry slip 0.07, M1 stop slip 0.15 / 0.20 NY | the formula against the raw ticks of the learning parts; the slippage by the earlier audit | `check_costs.py`: 171,127 minutes re-aggregated from the raw tick files: the first tick's spread (what an entry pays) against the formula, overall and in the owner's windows; the earlier audit re-used for the slippage (no code changed since) | overall formula - first-tick spread: mean -0.005, median -0.020 USD; Asia 07-09 Thai +0.013; London 13-14 Thai +0.001; NY open 09:30-11:30 NY -0.036 (median -0.06); M1 column = the minute's min spread 99.9-100 % | **PASS** (one note) | note: in the NY open the formula is 0.036 USD a trade optimistic (about 0.004 R at a 10-USD stop), M1 simulations only |
| 7 | parts, the owner's windows, event times | the same part dates everywhere; Asia 07-09 / London 13-14 Thai, NY 09:30 NY + 2 h; NY / London events DST-aware | every module's constants read; 23 hand-worked tests across both DST changes (the developer's `window_of` read only, `event_minutes`, `pullback15.active`, `plib.ny_mask`, `part_of`); 12 planted bugs; the measurer's B2 window split re-derived from `dev/p2_trades.parquet` | dates equal in `plib`, `m15_trades`, `dev/p2_trades`, `dev/sweep_detector`, `dev/verify_p2`, `dev2/compare_ref`, `strategist/slib`; 23 passed; 12 of 12 CAUGHT; the notes' B2 numbers reproduced exactly (Asia +0.092 / +0.203, London +0.076 / +0.074, NY -0.072 / -0.059, Asia + London +0.087 / +0.161, USD -2.2 / +306.9) | **PASS** (one note) | note: the windows are keyed by the entry time; keyed by the decision time, Asia P1 is +0.004 (not +0.092) |
| 8 | the metrics: `wf.weekly` / `longest_run`, the summaries' max DD, win %, a weekday | the drawdown from 0, break-even trades, the streak in time order, weekday counts, the Thai week | 9 hand-worked tests + 1 question (xfail); 8 planted bugs; a scan of all summaries; the measured effect on the developer's 8 cells and on 40 printed learning-part summaries | **max DD ignored the starting balance** in 20 precursors summaries (`(eq.cummax() - eq).max()`): -5, -5, +1 gave 5, not 10; before 4 failed / 5 passed, after 9 passed + 1 xfail; 130 earlier tests of those modules pass; effect: 1 of 40 printed summaries (+0.4 USD), 1 of 8 developer cells (+1.6 USD, out_dd_impact.txt); 8 of 8 CAUGHT | **FAIL -> fixed**; the question answered (item 1) | fix: the 20 files, `(eq.cummax().clip(lower=0) - eq).max()`; item 1: "win" = pnl > 0 after costs in `wf.weekly`, `wf.walk_forward` and the win shares of 23 more precursors files (section 10) |
| 9 | anything else shared and untested | which shared modules the developers and the strategist import, and their tests | an import scan of `dev/`, `dev2/`, `strategist/` | `fingerprint.py` had no test file (its ZigZag is now in `audit2/test_swings.py`); `dev2/swings.py` + `zigzag_ref.py` are new (dev2's V3-1, in progress) | listed | see section 9; dev2's `swings.py` audited in section 12 |
| 10 | item 1: "win" = pnl > 0 after costs | `wf.weekly`, `wf.walk_forward`'s month row and every precursors win share | 3 new hand-worked tests + a scan test; 14 planted bugs; every stored trade file re-counted on the learning rows, old against new | before 6 failed / 9 passed, after 15 passed; 14 of 14 CAUGHT; 240 learning-part cells: 205 rise, 35 equal, 0 fall (+0.000 .. +0.500, median +0.073); 0 target exits not in profit | **changed** (the measurer's answer) | 24 precursors files; section 10 |
| 11 | item 4: `plib.load_learning()` | a loader that stops before 2026-04-18 00:00 UTC and never returns an exam row | 14 hand-worked tests + 1 on the real stores; 13 planted bugs; a caller list | before 14 failed / 1 passed, after 15 passed; 13 of 13 CAUGHT; real stores 954,198 bars .. 2026-04-17 20:54 (= out_check_merge.txt) | **added** | `gold.py` (`bars(before=)`), `plib.py`; 54 callers listed (section 11) |
| 12 | dev2's `swings.py` (read only; sha256 9ebfe2dd5de473b7.., file time 12:26:40 Thai) | the ZigZag rule 2, `tf_bars`, look-ahead of the whole `analyze`, the pivots against their legs, `running()` | 32 hand-worked tests + 2 questions (xfail); 10 planted bugs (in memory); the real learning bars: `tf_bars` against `indicators.bars`, truncation at 3 server-day ends x 7 TFs, two property counts | 32 passed + 2 xfailed; 10 of 10 CAUGHT; `tf_bars` equal on every TF; truncation 21 of 21 equal (with power); pivots not the extreme of their leg 0.1 % (M1) .. 1.0 % (H1); `running()` != the structure's extreme on 0.0-0.2 % of bars | **PASS** (two questions) | questions 6-7; no bug to relay |
| 13 | round 3, item 1: the group-b callers on `plib.load_learning()` | `framework`, `framework2`, `level_power`, `regime`, `verify_p2` read no exam row and give the same results | one line each (`load()` + the cut -> `load_learning(start=...)`); an AST test of every `plib` call in the five files; each script re-run and diffed against its stored output (parquets compared frame by frame) | the test: HEAD 5 failed / 0 passed -> 5 passed; `out_framework`, `out_level_power` identical; `out_framework2` identical apart from a stderr warning captured in the stored file; `out_regime` every stored line identical (3 new lines from a later print = CHECKLIST row 37's +0.301 / +0.130); `framework2.parquet`, `level_power.parquet` byte-identical; `verify_p2` 6 of 6 cells = `dev/p2_metrics.csv`, 0 overlaps, 60 of 60, 1244 of 1244 (= notes.md) | **switched, identical** | section 13 |
| 14 | the first developer's PLAN-1 runner `dev/plan1.py` + `test_plan1.py` (read only; sha256 dec3a0a5.. / 71779f40..) | the one-position stream, the D1-state weights from closed D1 bars, the cost (the tick spread; slippage a parameter, default 0), the exam switch's guard | 6 new tests + 1 question (xfail) with stubs (no data read); 18 planted bugs against its tests alone and with mine; the learning trades rebuilt in memory and checked on the raw ticks, MT5's own D1 bars and the measurer's `check_plan1.py` | rebuilt = stored (298 / 298 rows); D1 state 298 of 298 (MT5 D1, my loop) and 298 of 298 (the measurer's regime path); the fills = the tick's ask / bid exactly on 298 of 298, faults 0; London 119 / 119, NY 100 / 100, dR 0.0000; stream: 0 dropped, the next fill 4.0 min after an exit at the closest; weights equal; the 6 printed plan lines recomputed equal; planted: its tests 3 of 18, with mine 18 of 18 | **PASS** (no bug; 15 test gaps closed; one question) | section 14; relay the 6 tests (test gaps) |
| 15 | round 3, item 3: dev2's two test gaps (`dev2/swings.py`, now sha256 ff1eff81.., file time 17:08:49 Thai) | `known_at` with a pivot confirmed exactly at d + 1; `running()` when the pivot bar's own extreme lies beyond every later bar | 2 hand-worked tests (the second both ways up) in `test_dev2_swings.py`; the measurer's two mutants | 35 passed + 2 xfailed on the current code; the 2 mutants: 2 of 2 caught (by the two tests alone and by the whole file); round 2's 10 mutants on the new version: 10 of 10 | **tests added** | section 15 |

## 1a. The history download stored nothing after Friday (FAIL, fixed)

**What happened (real evidence, `logs/download.log`):**
- 15:02:06 UTC: `downloaded XAUUSD M1 2026-10-12..2026-10-19: 5832 bars`; then M5 (1,370 bars, the call took 15 s:
  15:02:06 -> 15:02:21), M15 460, H1 115, H4 30, D1 5. The stored M5 / M15 / H1 / H4 / D1 reach Monday 15:00 UTC
  (H4 13:00, D1 Monday), so the terminal had Monday's history for them; only M1 ended at Friday 20:54 UTC.
- 15:40:24 UTC (after the measurer's `copy_rates_from_pos` call): `downloaded XAUUSD M1 2026-10-16..2026-10-19: 1370
  bars`; the store's M1 now ends 2026-10-19 15:40 UTC.
- The cause: `copy_rates_range` returns what the terminal holds locally. The M1 call (the first of the run, under one
  second) got the stale local M1. Nothing checked that the download reached the newest bar.

**The fix (`app/market_data/history_download.py`):**
- After the chunked download, `expected_last_open` asks the terminal for the newest bar inside the window from two
  other sources: the newest bars (`copy_rates_from_pos(0, 3)`) and the bar holding the latest tick (floored in
  server wall-clock time, so D1 opens at server midnight). Only bars inside [start, end) count. A window that ended
  before the newest bar is not checked against newer bars.
- If the download ends before that bar, it waits (1, 2, 4, 8 s) and re-reads only the tail (from its last bar). A
  re-read bar replaces its first copy (`keep="last"`).
- Still short after 4 waits: `HistoryIncompleteError` (a `DataQualityError`) with the symbol, timeframe, the last bar
  and the expected bar. Nothing is returned, so the script stores nothing for it.
- The wait is `time.sleep` resolved at call time (or an injected `sleep`).

**Tests (`tests/unit/test_history_download.py`, 14):**

| Test | What it checks, by hand |
|---|---|
| `test_fixture_reproduces_the_symptom` | the fake itself: the raw range call ends Friday 20:59 UTC, `copy_rates_from_pos` shows Monday 10:00 |
| `test_stale_range_is_completed_after_the_sync[M1]`, `[H1]` | stale range + sync on `copy_rates_from_pos`: the frame ends Monday 10:00, equals a fresh terminal's frame, unique and sorted, one wait, 0 `order_send` / `order_check` |
| `test_never_synchronised_fails_loudly` | the range never syncs: `DataQualityError` naming `XAUUSD M1`, waits exactly [1, 2, 4, 8] |
| `test_tick_shows_the_gap_when_newest_bars_are_stale_too` | the newest bars stale too: the tick (Monday 10:00:30) shows the gap, the error names 2026-10-05 10:00 |
| `test_newest_bars_show_the_gap_without_a_tick` | the tick call fails: the newest bars alone show the gap |
| `test_a_bar_read_again_replaces_its_first_copy` | the stale copy of Friday 20:59 has its close 1.0 off: the result equals the fresh frame |
| `test_re_read_covers_only_the_tail` | 15 days of M1 = two 13-day chunks + one re-read call = 3 range calls |
| `test_fresh_terminal_is_unchanged_and_never_waits` | a synced terminal: no wait, one range call, ends Monday 10:00 |
| `test_window_on_a_minute_boundary` | end = 10:00:00: the 10:00 bar is outside the window; ends 09:59, no wait |
| `test_market_closed_saturday` | Saturday: ends Friday 20:59, no wait |
| `test_past_window_is_not_checked_against_newer_bars` | a stale terminal and a window ending Wednesday 12:00: ends 11:59, no wait |
| `test_d1_bar_from_the_tick_uses_the_server_midnight` | D1 ends at 2026-10-04 21:00 UTC (Monday 00:00 EEST), no false alarm |
| `test_window_before_the_newest_bar_with_no_bars` | a weekend-only window: empty, no wait (Friday's bar is before the window) |

**Before / after (`audit2/plant_bugs_1a.py`, output `audit2/out_plant_bugs_1a.txt`):**
```
BEFORE (git HEAD module): 7 failed, 7 passed in 3.48s
          test_stale_range_is_completed_after_the_sync[M1]
          test_stale_range_is_completed_after_the_sync[H1]
          test_never_synchronised_fails_loudly
          test_tick_shows_the_gap_when_newest_bars_are_stale_too
          test_newest_bars_show_the_gap_without_a_tick
          test_a_bar_read_again_replaces_its_first_copy
          test_re_read_covers_only_the_tail
...
14 of 14 caught
AFTER (the fixed module): 14 passed in 4.95s
```
The first "before" run (`audit2/out_1a_before.txt`, the first 10 tests) shows the symptom itself:
`assert Timestamp('2026-10-02 20:59:00+0000') == Timestamp('2026-10-05 10:00:00+0000')` (M1) and
`Timestamp('2026-10-02 20:00:00+0000') == ...10:00` (H1), and `Failed: DID NOT RAISE DataQualityError`.

**Planted bugs (14, all CAUGHT):** no tail check; no tick source; no newest-bars source; the window end not enforced;
the window start not enforced; a strict comparison (false alarm); the tail not re-read; no wait; the wait not
doubled; one retry only; returning the stale frame instead of raising; the tick floored in UTC instead of server
time; `keep="first"` on the re-read; the re-read from the window start. The first run of the planted bugs missed 4
(no newest-bars source, the window start, `keep="first"`, the re-read from the start); the four tests
`test_newest_bars_show_the_gap_without_a_tick`, `test_window_before_the_newest_bar_with_no_bars`,
`test_a_bar_read_again_replaces_its_first_copy` and `test_re_read_covers_only_the_tail` were added for them.

**Gates on the changed files:**
- `ruff format --check` and `ruff check` on `app/market_data/history_download.py` and
  `tests/unit/test_history_download.py`: `All checks passed!`
- `mypy app/market_data/history_download.py`: `Success: no issues found in 1 source file`
- `bandit -q -c pyproject.toml app/market_data/history_download.py`: exit 0, no findings
- The targeted suites (every test that calls `download_history`, plus the architecture rules):
  `pytest tests/unit/test_history_download.py tests/unit/test_market_data.py tests/unit/test_candle_sync.py
  tests/unit/test_architecture.py` -> `80 passed in 24.05s`

**The real terminal, read only** (15:55:10 UTC = 22:55 Thai, `scripts/download_history.py --symbols XAUUSD
--timeframes M1,H1,D1 --days 2 --out <scratchpad>/hist_check`, `build_read_only`, `allow_trading=False`):
M1 1,071 bars 2026-10-18 22:05 .. 2026-10-19 15:55 UTC, H1 18 bars .. 15:00, D1 1 bar (Monday). No wait and no
warning in `logs/download.log`: the check passes on a synced terminal. The stored `data/history` was not touched.

**What it can change:** nothing in the learning parts. The stale run affected only the days after the exam window.
The fix guards every later download (the developer's and measurer's "today's market" looks).

**Not fixed, for the measurer (questions at the end):**
- **The forming bar is stored.** `download_history` keeps every bar with an open before `end` = now, so the last bar
  of each download is still forming: e.g. the real-terminal check's last M1 bar (15:55) had 47 ticks, and the store's
  H1 15:00 bar (saved 15:02 UTC) has `tick_volume` 657 against 16,870 for 14:00. The store's merge keeps the newer
  copy, so the next overlapping download repairs it. It matters only for a look at the newest bars. The script's
  docstring says "closed history".
- **A window that ends in the past is not checked against newer bars.** If a terminal is stale inside a past window,
  the check cannot see it. All research downloads so far ended at the download time.

## 1b / 1c. `gold.bars` and `plib.load` (PASS)

**Hand-worked tests (`audit2/test_pipeline.py`):**

| Test | What it checks |
|---|---|
| `test_cut_at_the_first_new_bar_new_wins` | OLD 23:55-00:04 (open 1-10, ms units), NEW 00:00-00:07 (open 100-107, us units): 13 bars, opens 1-5 then 100-107, UTC, 00:00 stays 00:00 |
| `test_old_bar_inside_a_new_gap_after_the_cut_is_dropped` | the rule as written: OLD never fills a NEW gap after the cut (real data: 0 such minutes) |
| `test_no_old_store` / `test_unsorted_new_comes_out_sorted` | NEW alone; unsorted rows come out sorted |
| `test_start_inclusive_end_exclusive_duplicates_keep_last` | bars at START-1, START, START+1 twice, END-1, END: kept START, START+1 (the LAST copy, open 33), END-1; 6 float64 columns |
| `test_the_constants` | LEARN_START 2025-10-18, EXAM 2026-04-18 .. 2026-10-17, START 2023-08-01, END 2026-10-17 |

`pytest research/2026-10-18-moments/agents/audit2/test_pipeline.py` -> `7 passed` (with 1d's release test).
Planted bugs (`plant.py mutants_pipeline`, `out_plant_pipeline.txt`): `ALL: 13 of 13 caught; unmutated: 7 passed`.

**The real stores** (`audit2/check_merge.py`, `out_check_merge.txt`; NEW read with open_time < 2026-04-18):
- OLD: 736,076 bars 2021-09-01 .. 2023-10-02 23:59; NEW: 922,587 bars 2023-09-01 00:00 .. 2026-04-17 20:54.
- `gold.bars`: 1,628,641 bars; index UTC, unique, sorted. Before the first NEW bar: 706,054 = every OLD bar before
  it. From it: 922,587 = every NEW bar, equal value by value.
- The joint: the last OLD bar 2023-08-31 23:59, the first NEW bar 2023-09-01 00:00, gap 1 minute.
- The second source (a set union, NEW winning): the overlap 2023-09-01 .. 2023-10-02 has 30,022 shared minutes,
  OHLC equal on 30,022 (max |diff| 0.00000), tick_volume and spread equal on 30,022. OLD-only minutes after the cut: 0.
  NEW-only: 0. `gold.bars` = the union, 1,628,641 bars.
- `plib.load`: 954,198 bars 2023-08-01 .. 2026-04-17 20:54 (the copy ends before the exam).
- The learning parts (2025-10-18 .. 2026-04-17): 173,030 bars; gaps over 10 minutes: 126 = 25 weekends + 96 daily
  breaks + 5 US holidays (2025-11-27 4 h 50, 2025-12-24 1 d 4 h 35, 2025-12-31 1 d 1 h 11, 2026-01-19 3 h 50,
  2026-02-16 3 h 50).

**Note (not a fault):** `plib.END` is 2026-10-17, so `plib.load()` hands every caller the exam rows. The rule "never
read the exam" is kept only by each caller's own filter (the developer's `locate` keeps to the learning parts).

## 1d. UTC alignment through the DST changes (PASS)

`audit2/check_dst.py`, output `out_check_dst.txt`. The ticks and the M1 bars both pass through the same `ServerClock`
(Europe/Athens), so equality between them proves consistency only. The outside clock is the release minutes.

**A. The M1 store against the raw ticks** (re-aggregated here from `data/ticks/XAUUSD/*.parquet`, not from the earlier
audit's `tick_minutes.parquet`):

| Week of | Regime | Days | Minutes | open / high / low / close equal | spread equal | M1-only / tick-only |
|---|---|---|---|---|---|---|
| 2025-10-20 | both summer | 5 | 6,735 | 6,735 each | 6,733 | 0 / 0 |
| 2025-10-27 | US on, EU off | 5 | 6,735 | 6,735 each | 6,732 | 0 / 0 |
| 2025-11-03 | both winter | 5 | 6,795 | 6,795 each | 6,788 | 0 / 0 |
| 2026-03-02 | both winter | 5 | 6,795 | 6,795 each | 6,795 | 0 / 0 |
| 2026-03-09 | US on, EU off | 5 | 6,734 | 6,734 each | 6,732 | 0 / 0 |
| 2026-03-16 | US on, EU off | 5 | 6,734 | 6,734 each | 6,733 | 0 / 0 |
| 2026-03-23 | US on, EU off | 5 | 6,735 | 6,735 each | 6,734 | 0 / 0 |
| 2026-03-30 | both summer | 4 | 5,365 | 5,365 each | 5,364 | 0 / 0 |
| 2026-04-06 | both summer | 5 | 6,735 | 6,735 each | 6,734 | 0 / 0 |

The 18 spread differences: on 2025-11-04 both are minutes whose lowest-spread tick is the first tick of the minute
(00:58:00.051, spread 0.23; MT5's column 0.25). The bid OHLC is equal there too.

**B. The release minutes (every US release before the exam, 2021-11 .. 2026-04, 599 with data):** where the largest M1
range sits within +-90 minutes of the stated New York minute.

| Regime | Events | Peak at 0 | at +-1 | at +60 | at -60 | median range / window median at 0, +60, -60 |
|---|---|---|---|---|---|---|
| US on, EU off (mid-March, late October) | 54 | 19 | 2 | 0 | 0 | 3.41, 1.71, 0.78 |
| both summer | 328 | 172 | 10 | 2 | 0 | 4.51, 1.61, 0.74 |
| both winter | 217 | 100 | 7 | 5 | 1 | 3.99, 1.66, 0.72 |

- CPI / NFP / PPI / FOMC only: US on, EU off 15 of 21 at 0 (1 at +-1, 0 at +-60); both summer 79 of 103 (0 at
  +-60); both winter 52 of 72 (0 at +-60).
- The 08:30 New York releases: 12:30 UTC (US summer) 151 of 274 peak at 0, 1 at +60; 13:30 UTC (US winter) 81 of
  159 at 0, 5 at +60. The +60 minute is the NY open (09:30) in both, hence its 1.7 ratio in every regime.
- The rest peak elsewhere: the weak releases (jobless claims, JOLTS, the press conference) are not the largest move
  of their 3 hours. If the clock were 1 h off in the US-on / EU-off weeks, the strong releases there would peak at
  +60. None does.

**C. The daily break (Mon-Thu, 2023-09 .. 2026-04):** the last bar before it is 16:54 New York in every regime
(UTC 20:54 in US summer, 21:54 in US winter). The raw `time_server` of that bar is 23:54 except in the US-on /
EU-off weeks, where it is 22:54 (47 of 47). The broker's server clock follows the EU dates (Europe/Athens) and its
session follows New York. So the Athens conversion is right in all three regimes, and the session times in New York
time are right too.

**`gold.releases()` hand test** (`test_new_york_time_to_utc_across_both_dst_changes`): 2026-03-06 08:30 -> 13:30
UTC, 2026-03-09 -> 12:30, 2026-03-30 -> 12:30, 2025-10-27 -> 12:30, 2025-11-03 -> 13:30, FOMC 2025-10-29 14:00 ->
18:00. Planted: read as UTC, a fixed -5 h, the Athens clock: 3 of 3 CAUGHT.

## 2. The larger-TF bars, `indicators.bars` (PASS)

`audit2/check_bars.py`, output `out_check_bars.txt`.

**(a) Against MT5's own bars** (the match key: the UTC open for H1, MT5's raw `time_server` for H4 / D1, so the
bucketing code under test is not used to find its own partner):

| TF | Span (whole bars in both) | Ours | MT5 | Both | OHLC equal | max diff | one side only |
|---|---|---|---|---|---|---|---|
| H1 | 2023-08-01 00:00 .. 2026-04-17 19:00 UTC | 16,032 | 16,032 | 16,032 | 16,032 | 0.00000 | 0 / 0 |
| H4 | 2023-04-03 00:00 .. 2026-04-17 16:00 server | 4,706 | 4,706 | 4,706 | 4,706 | 0.00000 | 0 / 0 |
| D1 | 2021-09-02 .. 2026-04-16 server | 1,192 | 1,192 | 1,192 | 1,192 | 0.00000 | 0 / 0 |
| H1, post-exam days | 2026-10-18 23:00 .. 2026-10-19 13:00 UTC | 15 | 15 | 15 | 15 | 0.00000 | 0 / 0 |
| H4, post-exam days | 2026-10-19 04:00 .. 12:00 server | 3 | 3 | 3 | 3 | 0.00000 | 0 / 0 |

The D1 boundaries around the changes (MT5's open_time in UTC; our first M1 bar of that server day): Fri 2025-10-24
21:00 / 22:05; Mon 2025-10-27 22:00 / 22:05; Fri 2025-10-31 22:00 / 22:05; Mon 2025-11-03 22:00 / 23:05; Fri
2026-03-06 22:00 / 23:05; Mon 2026-03-09 22:00 / 22:05; Fri 2026-03-27 22:00 / 22:05; Mon 2026-03-30 21:00 / 22:05;
OHLC equal on all eight.

**Hand-worked (`audit2/test_bars.py`, 5) and the earlier `precursors/test_indicators.py` (6):** `11 passed`.
- the winter server day starts 22:00 UTC;
- the spring-forward night 2026-03-29: the server day is 23 h and its first H4 bar 3 h (22:00 .. 00:59 UTC);
- the fall-back night 2025-10-26: the first H4 bar is 5 h (21:00 .. 01:59 UTC), the server day 25 h;
- a quiet last minute: the M5 bar with no 06:03 / 06:04 is available at 06:03 (the rule as written);
- 15-minute clock bars' OHLC and `avail`.

Planted (`plant.py mutants_bars`, `out_plant_bars.txt`): D1 on the UTC day, H4 on the UTC clock, the server day in
London, at a fixed UTC+2, `avail` = last / last + 2, open = last open, high from the closes, low = max, close = first,
last = first minute: `ALL: 11 of 11 caught; unmutated: 11 passed`.

**(b) `avail` before the bar's end.** It happens on every bar the market closes inside (the daily break, Fridays,
holidays). Those bars cannot change after their last minute, so `avail` is right there. The other case, quiet last
minutes in an open market:

| | M5 | M15 | H1 | H4 | D1 |
|---|---|---|---|---|---|
| learning parts, bars | 34,613 | 11,624 | 2,908 | 762 | 127 |
| early, market closed inside | 5 | 127 | 127 | 127 | 127 |
| early, quiet last minutes | 5 (9 min in all, max 4) | 0 | 0 | 0 | 0 |
| 2021-09 .. 2026-04, quiet last minutes | 56 (90 min) | 14 (38 min) | 4 (5 min) | 1 (1 min) | 0 |

- Whether a decision used one before its end: in the learning parts no H1 / H4 / D1 bar is affected, so no level
  from `zones.py` (H1 swings, the previous day) and no H1 / H4 / D1 reading was early.
- The 5 M5 bars (2025-11-10 06:05, 2025-11-28 08:10, 2025-12-07 23:20, 2026-02-09 15:40, 2026-03-13 00:20 bar
  ends) feed only `indicators.features` (M5 readings). The developer's M5 patterns use its own `tf_bars`
  (`avail` = open + 5 min), not this rule.
- On those bars the prices at `avail` equal the forming bar's (no minute came after), so no future price is used.
  Only the "complete" flag is early, by 1-4 minutes.
- Not changed; noted.

## 3. The indicators, `foundation.py` (PASS)

- The earlier `precursors/test_foundation.py` (13 tests: literal ports of ATR.mq5, RSI.mq5, MACD.mq5, Stochastic.mq5,
  ADX.mq5, Custom Moving Average.mq5 on random bars, plus hand values for TR / ATR(3) / RSI(2)) is re-used.
- Added (`audit2/test_foundation_hand.py`, 4):
  - a gap-down bar (high 15, low 14 after a close of 20) has TR 6 and a gap-up bar TR 6.5, ATR(2) = 6.25. This is
    the term the earlier audit found missing in `ml_dataset.atr14`; `foundation` has it;
  - RSI(2) on 10, 12, 11, 14, 13 = 66.667, 88.889, 61.538 (a loss in the seed);
  - MACD(2, 3, 2) on 10, 12, 11, 13: line 0, 1/3, 1/9, 10/27; signal -, 1/6, 2/9, 13/54;
  - the EMA seeded with the first price.
- `pytest test_foundation_hand.py precursors/test_foundation.py` -> `17 passed`.
- Planted (`plant.py mutants_foundation`, `out_plant_foundation.txt`): TR without either previous-close term, ATR as
  Wilder's smoothing, ATR over n - 1, RSI smoothing by n, RSI seed over n + 1, RSI 100 when flat, MACD signal as an
  EMA, the MACD line reversed, EMA adjust=True, EMA factor 1/n: `ALL: 11 of 11 caught; unmutated: 17 passed`.

## 4. The swings (FAIL in the start-up -> fixed in `fingerprint.py`; relay for `dev/patterns.py`)

**The fault.** Both ZigZags (`fingerprint.zigzag` and the developer's `patterns.zigzag`, the same algorithm) have a
start-up phase before the first pivot. If one bar holds both the highest high and the lowest low and its range reaches
the threshold, the code calls its high a peak confirmed by that same bar. A later bar can then confirm a trough at the
same bar's low: one bar, two turns. That breaks the owner's rule. In the trend phases it cannot happen: a bar that
makes a new extreme only extends it (the `if` comes before the `elif`).

Hand case (ATR 5, k 2, threshold 10): highs 10, 30, 25, 26 and lows 9, 0, 20, 25. HEAD gives a peak at bar 1 (30)
confirmed by bar 1 and a trough at bar 1 (0) confirmed by bar 2.

**The fix** (`precursors/fingerprint.py`, the start-up condition): `if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr:`.
While one bar holds both extremes, the first pivot waits for a later bar that takes one of them out. Then the earlier
extreme is the first pivot, confirmed by that later bar.

**Tests (`audit2/test_swings.py`, 27):**

| Test | What it checks, by hand |
|---|---|
| `test_one_wide_bar_at_the_start_is_never_two_turns` | the case above: no pivot while bars 2-3 stay inside bar 1 |
| `test_after_a_wide_bar_the_first_turn_waits_for_a_bar_that_takes_an_extreme_out` | bar 4 makes 31: the trough at bar 1 (0) confirmed by 4, then the peak at 4 (31) confirmed by 5 (low 20) |
| `test_an_outside_bar_in_an_up_leg_extends_it_and_is_one_turn` / `..._down_leg_is_mirrored` | a bar with a new high and a low 11 below the old peak extends the peak; the next bar confirms it |
| `test_an_equal_high_moves_the_peak_later_and_exactly_the_threshold_confirms` / `test_an_equal_low_moves_the_trough_later` | ties move the pivot later; exactly 10 confirms |
| `test_just_under_the_threshold_confirms_nothing` | 9.99 confirms nothing |
| `test_every_pivot_is_confirmed_by_a_later_bar_and_no_bar_turns_twice[0-19]` | 20 random series with 5 % wide bars and a wide first bar: confirm > bar, unique bars, kinds alternate |

- Before (`out_4_before.txt`, the HEAD module): `22 failed, 5 passed`. All 20 random series fail on their first two
  pivots only (bar 14 a peak confirmed by itself, then a trough at bar 14); none fails after them.
- After: `27 passed`.
- The other precursor tests that use `fingerprint.zigzag` (`test_explore`, `test_loc`, `test_lvl`, `test_lvl2`,
  `test_mw`, `test_parts`, `test_touch`, `test_zones`), run from the repo root: `114 passed in 36.65s`.
- The developer's own ZigZag tests, run read only (`-k zigzag`), including its comparison with `fingerprint.zigzag` on
  real bars: `5 passed`.

**What the fix changes on the real bars** (`audit2/check_swings.py` part A, `out_check_swings.txt`): HEAD against the
fixed code on every series the callers build. Only 1 of 18 series changes: H1 from 2023-08-01 with ATR x 2. HEAD had
1 pivot confirmed by its own bar; 2 pivots differ, the last on 2023-08-01 14:59, and the count is the same (1,885).
The other 17 (M1 110,890 / 53,141 / 12,545 pivots, M5, M15, H1 x 3, and all from 2025-09-01) are identical. **No
earlier result in the learning parts changes.** The fault only bites at a series' first pivot, and every caller runs
the ZigZag over a whole series starting 2023-08-01 or 2025-09-01.

**Look-ahead (part B):** at 100 random decision bars in the learning parts per TF, every later bar is replaced by its
mirror around the decision close and the ATR recomputed. The ATR up to the decision is unchanged (asserted). The
pivots confirmed by the decision bar are the same in 100 of 100 for M1, M5 and H1, for both `fingerprint.zigzag` and
the developer's `patterns.zigzag`. The replaced future changed the full pivot list in 100 of 100, so the check has
power.

**Zones (part C, the real H1 from 2025-09-01 to the exam):** 1,004 swings, each known at the avail of the 2nd bar
after it (1,004 of 1,004). `levels_at` at 100 random moments of the learning parts: the same levels with every M1 bar
after the moment mirrored (100 of 100); three days later the levels differ in 100 of 100 (power).

**Planted (`plant.py mutants_swings`, `out_plant_swings.txt`): `ALL: 15 of 15 caught; unmutated: 35 passed`.**
- ZigZag, 8: the fix removed; the start-up takes the later extreme; an equal high / low does not move the pivot;
  `if` instead of `elif`; strictly above the threshold; the trough tracked from the peak bar; the confirming bar
  recorded as the pivot bar.
- Zones (against the earlier `test_zones.py`), 7: known 1 bar early; known at its own bar; fractals of 3 bars; zones
  from unknown swings; the tolerance from the next bar's ATR; the 5-day high with the forming bar; 2 swings as strong.
- The first run missed 2. "An equal low": my test gap, `test_an_equal_low_moves_the_trough_later` was added.
  "A swing without k bars after it kept": an equivalent mutant (`F.fractals`' centred window is NaN for the last k
  bars, so the filter it removes never drops anything); replaced by "fractals of 3 bars".

**RELAY to the first developer (through the measurer):** `audit2/test_relay_dev_zigzag.py` fails on `dev/patterns.py`:
```
FAILED research/2026-10-18-moments/agents/audit2/test_relay_dev_zigzag.py::test_one_wide_bar_at_the_start_is_never_two_turns
FAILED research/2026-10-18-moments/agents/audit2/test_relay_dev_zigzag.py::test_every_pivot_is_confirmed_by_a_later_bar
```
- `assert ([1, 1] == []`: two pivots at bar 1.
- The fix is the same one-line condition. On the developer's series (from 2025-09-01) part A finds no difference, so
  its P1 / P2 results do not move.
- A second point for the developer: `test_zigzag_equals_the_precursors_zigzag_on_real_bars` compares two copies of
  the same algorithm, so a fault shared by both cannot show there. The hand cases above are the independent check.
- The shared trade-size swings now belong to the second developer (`TEAM.md`). When V3-1 is delivered, its swings
  should pass the same hand cases (`test_swings.py`). I will audit them then if asked.

## 5. The simulators (FAIL, latent: the midnight cut -> fixed; everything else PASS)

**Read and hand-tested:**
- **`surrender.trade`:** enters at the first tick at / after the decision (a buy at ask + 0.07, a sell at bid - 0.07).
  A buy is read on the bid and a sell on the ask. The stop fills at the first tick at / beyond it, its gap included.
  The target is a limit (it pays exactly 10, never more). On one tick the stop beats the target, which beats the
  surrender. A time exit is the last tick before the hold ends. R = pnl / 10 = over the fill's risk, since the stop
  sits 10 from the fill.
- **`tick_straddle.trade`:** a buy stop triggered by the ask, a sell stop by the bid, the stop with its gap, the
  target a limit, R = pnl / s over the fill's risk.
  - One tie note: a single tick meeting both triggers (a spread of at least 2b = 6 USD) would sell. The real
    spread's maximum is about 0.45 (the earlier audit), so this cannot happen.
- **`sr_break.take`:** no entry in the UTC day's last 30 minutes and a 30-minute hold, so its trades end before
  midnight. Its tests are re-run.
- **`touches`:** `scan` reads the levels at the touch bar's open and the approach from earlier closes, so it is
  causal. `outcome` is a label over the next 60 bars by design.
  - Note: 60 bars, not minutes, so a touch just before the daily break counts bars after the reopen.
- **The developer's `p2_trades.simulate` (read only):**
  - R = pnl / (side x (fill - stop)), over the fill's risk;
  - the stop filled at the first tick past it; the target a limit;
  - the tie order stop, target, structure, time, break;
  - a tick gap over 30 minutes exits at the last tick before it;
  - no trade when the fill is already past the stop;
  - its `Ticks` joins each UTC day to the next and refuses exam days.

  `audit2/test_dev_simulate.py`: `6 passed`. The measurer's `verify_p2.py` re-derived 60 / 60 of its trades from the
  raw ticks earlier.

**The fault:** `surrender.run` / `surrender.main` and `tick_straddle.run` load one UTC day's tick file
(`day_ticks(day)`). A trade still open at 24:00 UTC ended as a "time" exit at 23:59:59. A stop or target after
midnight was never seen, and a straddle whose trigger came after midnight was no trade at all.

**The fix:**
- `tick_straddle.span_ticks(day)`: the day's ticks joined to the next day's. A learning day is never joined to an
  exam day (2026-04-17 is never joined to 2026-04-18).
- `tick_straddle.run` and both day loops in `surrender.py` use it.
- `sr_break.run` is left as it is (its own 30-minute guard).

**Tests (`audit2/test_simulators.py`, 9):**

| Test | What it checks, by hand |
|---|---|
| `test_a_buy_stop_is_read_on_the_bid_and_fills_through_its_gap` | fill 100.37, bid 92 holds, bid 85 stops: -15.37, R -1.537 |
| `test_the_target_is_a_limit_never_better` | a sell, the ask 19.63 our way: +10.0 exactly |
| `test_the_entry_is_the_first_tick_at_or_after_the_decision` | decision at 3 s: the 5 s tick's ask 101.3 + 0.07 |
| `test_a_stop_and_the_surrender_on_one_tick_is_the_stop` | the surrender tick is past the stop: 'stop', -10.37 |
| `test_the_daily_break_inside_the_hold_exits_at_the_last_tick_before_it` | a buy at 20:50 UTC, ticks stop 20:54:59, resume 22:05: out at 20:54:59, +0.63 |
| `test_surrender_run_follows_a_trade_past_midnight` | a buy at 23:30, stop at 00:10 next day at 85: 'stop', -15.37 (HEAD: 'time' at 23:59:59) |
| `test_tick_straddle_run_follows_a_trade_past_midnight` | the sell trigger at 00:05 next day, the target at 00:20, R 2.0 (HEAD: no trade) |
| `test_a_learning_day_is_never_joined_to_an_exam_day` | `span_ticks(2026-04-17)` never asks for 2026-04-18 |
| `test_touches_outcome_needs_the_full_x_back` | 9.5 back is 'neither', 10.0 is 'reversed' at bar 2 |

- Before (`out_5_before.txt`, the HEAD `surrender.py` + `tick_straddle.py`): `3 failed, 6 passed`, with
  `assert (['time'] == ['stop']`, `KeyError: 'side'` (an empty result: no trade), and `AttributeError: ... no
  attribute 'span_ticks'`.
- After, with the earlier suites (`test_simulators`, `test_dev_simulate`, `test_surrender`, `test_tick_straddle`,
  `test_sr_break`, `test_touches`, `test_phase_switch`, `test_news_sweep`): `52 passed in 2.45s`.

**Planted (`plant.py mutants_sims`, `out_plant_sims.txt`): `ALL: 19 of 19 caught; unmutated: 27 passed`.**
- surrender, 8: a buy filled at the bid; a sell read on the bid; the stop without its gap; the target paying the
  tick; the surrender before the stop on one tick; the entry at the tick before the decision; the time exit after
  the hold; `run` cut at the UTC day again.
- straddle, 5: no next day; the exam guard removed; the buy stop triggered by the bid; the stop without its gap; R
  over b.
- touches, 6: the touch bar's back side counted; a bar reaching both called a reversal; reversed at x - 1; the
  approach from the earliest bar away; a touch in between ignored; the next level on the wrong side.
- The first runs missed "R over b" and "reversed at x - 1" (no test checked them). The R assertion and
  `test_touches_outcome_needs_the_full_x_back` were added.

**What it changes in earlier results: nothing measured.** The callers' own learning-part inputs enter only in the
active hours:
- `surrender.main` / `phase_switch` (`why_frame.parquet`, P1 / P2, the `active` rule): 3,809 rows, 11:20 .. 16:00
  UTC; with the 60-minute hold every exit is by 17:00 UTC.
- `tick_straddle.main` (`burst_frame.parquet`, P1 / P2, active): 1,263 rows, 11:30 .. 16:00 UTC; with the 60-minute
  wait and the 60-minute hold, by 18:00 UTC.

The cut was a trap for future work late in the UTC day. The owner's Asia window opens at 07:00 Thai = 00:00 UTC: a
widened window, or a trade held past midnight, would have hit it.

## 6. The costs (PASS, one note)

`audit2/check_costs.py`, output `out_check_costs.txt`. Learning parts 2025-10-18 .. 2026-04-17: 171,127 minutes with
both ticks and an M1 bar, re-aggregated here from the raw tick files.

| Window | Minutes | First-tick spread median / mean | Formula median / mean | Formula - first: median / mean / p10 / p90 | Formula >= first | M1 column = min spread |
|---|---|---|---|---|---|---|
| all | 171,127 | 0.390 / 0.365 | 0.310 / 0.359 | -0.020 / -0.005 / -0.080 / +0.080 | 46.7 % | 100.0 % |
| Asia 07-09 Thai | 15,239 | 0.390 / 0.386 | 0.410 / 0.399 | +0.040 / +0.013 / -0.080 / +0.080 | 58.9 % | 100.0 % |
| London 13-14 Thai | 7,618 | 0.390 / 0.378 | 0.360 / 0.379 | +0.000 / +0.001 / -0.080 / +0.080 | 52.4 % | 99.9 % |
| NY open 09:30-11:30 NY | 15,239 | 0.390 / 0.353 | 0.310 / 0.317 | -0.060 / -0.036 / -0.080 / +0.060 | 25.8 % | 100.0 % |

- **The spread formula is unbiased overall** (mean -0.005 USD) and in the Asia and London windows.
- **In the NY open window it is 0.036 USD a trade optimistic** on average (median 0.06). At a 10-USD stop that is
  about 0.004 R. It applies only where an M1 simulation stands in for ticks; the tick simulators use the real
  spread. Not changed (about 20 modules copy the formula inline); noted.
- **The slippage:** no code changed since the earlier audit (`../auditor/notes.md` section 2, `tick_sim.log`), so its
  results are re-used, not repeated:
  - entry: the price drift to +250 ms / +1 s is +0.00 on average, so the fixed 0.07 is conservative;
  - stops on ticks: median 0.07, mean 0.15, NY mean 0.20, which is what `lvl.py` / `lvl2.py` charge on M1 (0.15 /
    0.20 NY);
  - net, realistic against the harness: within about +-0.01 R.

## 7. Parts, windows, event times (PASS, one note)

- **The parts:** the same dates everywhere they are written. P1 2025-10-18 .. 2026-01-16, P2 2026-01-16 ..
  2026-04-18, the exam 2026-04-18 .. 2026-10-17, in `plib`, `m15_trades.PARTS`, `dev/p2_trades.PARTS`,
  `dev/sweep_detector`, `dev/verify_p2`, `dev2/compare_ref`, `strategist/slib`. The developer's other modules import
  `m15_trades.part_of`. Every reader of the stores filters the exam at read time (`dev/patterns.load_m1`,
  `dev/sweep_detector.learning_ticks`, `strategist/slib.m1` / `ticks`, the developer's `Ticks`); `plib.load` does not
  (section 1c).
- **The owner's windows** (`dev/p4_trades.window_of`, read only):
  - Asia 07:00-09:00 Thai and London 13:00-14:00 Thai, on the Thai clock;
  - NY 09:30-11:30 New York time, through `tz_convert`;
  - the start included, the end excluded.

  This matches the owner's words: the London hour is the owner's Thai-clock hour, not London's.
- **The event times** (`footprints.event_minutes` for `m1_features` / `why_frame`, `pullback15.active`): each event
  in its own zone, through `tz_convert`. NY open 09:30 NY, US data 08:30 NY, COMEX 08:20 NY, the PM fix 15:00 London.

**Tests (`audit2/test_windows.py`, 23 passed):**
- 18 cases of `window_of`, among them:
  - 2025-10-31 13:30 UTC = 09:30 EDT while Europe is already on winter time -> NY;
  - 2026-03-10 13:30 UTC = 09:30 EDT while Europe is still on winter time -> NY;
  - 2026-03-06 13:30 UTC = 08:30 EST -> none;
  - London 13:00 Thai = 06:00 UTC in both London summer and winter.
- The London pad.
- The event minutes in all three regimes.
- `pullback15.active` on 2026-03-10 (NY open 13:30 UTC, fix 15:00 UTC), 2026-03-06 (14:30 / 15:00) and 2026-03-30
  (13:30 / 14:00).
- `plib.ny_mask` at 07:55 NY in summer and winter.
- `part_of` at every boundary.
- My first version of the `active` test had a wrong hand value (I took 2026-03-10 14:31 UTC as outside; it is 29
  minutes before the 15:00 GMT fix, so inside). The code was right; the test was corrected.

Planted (`plant.py mutants_windows`, `out_plant_windows.txt`; the developer's file mutated in memory only):
`ALL: 12 of 12 caught; unmutated: 23 passed`.
- Asia's end included; Thai time as UTC+9; London 06:00-07:00 on London's clock; NY at a fixed UTC-5; NY's window 1 h;
- the event clock in UTC;
- the fix on GMT all year; the NY open on EST all year; the active edge exclusive;
- plib's windows on the UTC clock;
- a part's end included; P2 a day late.

**The measurer's B2 window split, re-derived** (`out_window_split.txt`; the script was not in the repo; from
`dev/p2_trades.parquet` with `window_of`): with the window at the entry time and news cost 0, every number in
`precursors/notes.md` is reproduced.

| B2 | P1 | P2 |
|---|---|---|
| Asia | +0.092 (40, 0.45) | +0.203 (35, 0.43) |
| London 13-14 Thai | +0.076 (21) | +0.074 (17) |
| NY open + 2 h | -0.072 (41) | -0.059 (47) |
| Asia + London | +0.087 (61, 0.410), -2.2 USD | +0.161 (52, 0.462), +306.9 USD |

- News costs of 0.5 / 1 / 2 change only the NY rows (-0.074 .. -0.080 / -0.060 .. -0.065).
- **Note (a sensitivity, not a fault):** keyed by the decision time (`t_dec`) instead of the entry, Asia is +0.004
  (39) / +0.178 (36), London +0.144 (20) / +0.188 (14), Asia + London +0.052 (59) / +0.181 (50). The P1 lead in Asia
  rests on trades decided before 07:00 Thai and entered inside the window. The rule should say which time counts.

## 8. The metrics (FAIL: the drawdown -> fixed; one question)

**The fault:** 20 precursors summaries print the max drawdown as `(eq.cummax() - eq).max()`, with
`eq = <trades>.pnl.cumsum()`. The running peak leaves out the starting balance, so a trade list whose first trades
lose has its drawdown understated. Hand case -5, -5, +1: the balance goes 0, -5, -10, -9, so the drawdown is 10; the
formula gives 5.

The files: `big_trades`, `cut`, `lvl`, `lvl2`, `lvl3`, `model_cost`, `model_trades`, `present_wf`, `pullback`,
`pullback15`, `rule_bt`, `sr_break`, `surrender`, `tick_straddle`, `v2`, `v2b`, `v2c`, `v2e`, `v2s`, `wf`.

**The fix (all 20):** `(eq.cummax().clip(lower=0) - eq).max()`. The running peak with the start = max(0, cummax).
The developer's `p2_trades.stats` and the measurer's `verify_p2` already start at 0 (`np.r_[0.0, eq]`) and are
unchanged.

**Tests (`audit2/test_metrics.py`):**

| Test | What it checks, by hand |
|---|---|
| `test_the_drawdown_counts_from_the_starting_balance[sr_break / surrender / tick_straddle]` | -5, -5, +1 -> max DD 10 in each summary string |
| `test_no_summary_measures_the_drawdown_without_the_start` | no precursors file keeps the 0-less formula |
| `test_the_drawdown_after_a_first_win_is_unchanged` | +3, -5, -5, +20 -> 10 |
| `test_the_longest_losing_streak_in_time_order_and_a_break_even_trade` | -1, -2, 0, -1, -1, -1, +5, -1 -> 3 (a 0.0 trade ends a run); empty -> 0 |
| `test_the_weekday_counts[P1 / P2]` | 64 / 66 weekdays (counted by hand); `np.busday_count` = the developer's `bdate_range` |
| `test_the_weekly_table_on_the_thai_week` | Fri 23:30 UTC = Sat 06:30 Thai stays in its week; Sun 22:10 UTC = Mon 05:10 Thai starts the next; trades, USD, running USD, worst, R |
| `test_the_weekly_win_share_with_the_developers_exit_names` | **xfail, a question** (below) |

- Before (`out_8_before.txt`): `4 failed, 5 passed, 1 xfailed`. Each summary `Obtained: 5.0` for 10.0; `Left contains
  20 more items, first extra item: 'big_trades.py'`.
- After: `9 passed, 1 xfailed`.
- The earlier tests of the 17 edited modules that have test files (`test_big_trades` .. `test_v2s`, `test_wf`), from
  the repo root: `130 passed in 39.75s`.

Planted (`plant.py mutants_metrics`, `out_plant_metrics.txt`): `ALL: 8 of 8 caught; unmutated: 9 passed, 1 xfailed`.
- the streak never resets; the last run instead of the longest;
- the week on the UTC clock; the running USD not cumulative; the worst trade = the best; the week's R as a mean;
- the drawdown without the start again; the drawdown as the lowest running total.

**What the fix changes in earlier results:**
- An identity: the drawdown from 0 = max(the old max DD, -the lowest running total). So wherever a summary printed
  both numbers, the corrected value can be read off.
- Of the 40 printed learning-part summary lines in `precursors/out_*.txt` with both numbers, 1 changes:
  `out_straddle.txt` 384.3 -> 384.7 USD (`out_dd_printed.txt`).
- On the developer's P2 trades (`out_dd_impact.txt`, 8 cells: A / B1 / B2 x P1 / P2 and B2 Asia + London), 1
  changes: B2 Asia + London P1, 83.0 -> 84.5 USD (printed difference 1.6 from unrounded values). That curve never
  rose above 0 before its trough.
- No R or win % changes. The drawdown matters most for short lists that start with losses (a window, a week), and
  for the small account.

**Question (xfail test):**
- `wf.weekly` counts a win as `exit == "win"` (the target hit). The developer's exits are named `target` /
  `structure` / `time` / `break`, so `weekly` would show 0 % wins for its trades. Its own `stats` counts `pnl > 0`.
- The precursors summaries' "win" is also the target-hit rate, so a surrender exit with a profit is not a win there.
- Which does the owner mean by "win"? I did not change it.

## 9. Shared and untested (listed)

- **`precursors/fingerprint.py`** had no test file, though the developer's tests compare against it. Its ZigZag is now
  tested in `audit2/test_swings.py`. Its other functions (the 20-code fingerprint) are untested; their callers are
  the library work, not the current setups.
- **`dev2/swings.py`, `dev2/zigzag_ref.py`** (the second developer's V3-1, the shared trade-size swings from now on)
  are new and in progress. I did not audit them. They should pass the same hand cases (`audit2/test_swings.py`: one
  bar never two turns, confirm after the pivot bar, equal extremes, exactly the threshold) and the look-ahead
  mirror check (`check_swings.py` part B). I can run both on them when the measurer asks.
- **The forming bar in the history store** (section 1a) and **`plib.load` handing out the exam rows** (section 1c):
  both noted, not changed.
- **`footprints.event_minutes`** subtracts minutes of the local day without wrapping at midnight. That is right for
  today's events (08:20 .. 15:00 local) and would be wrong for an event near midnight.
- **Readers guarded by `assert`** (`strategist/slib.m1` / `ticks`): an assert vanishes under `python -O`. They are
  research scripts, so this is noted only.

## The relayed ZigZag fix: what it would change for the first developer (measured)

`audit2/check_relay_impact.py`, output `out_relay_impact.txt`. The developer's own inputs (`P.load_m1()`, 220,704 M1
bars 2025-09-01 .. 2026-04-17 20:54), its current `patterns.zigzag` against a fixed copy held in memory (the file is
never touched):

| Input | Current pivots (self-confirmed / a bar twice) | Fixed | Differing |
|---|---|---|---|
| `TF` M1, ATR x 2 | 25,436 (0 / 0) | 25,436 | 0 |
| `TF` M5, ATR x 2 | 4,884 (0 / 0) | 4,884 | 0 |
| `TF` M15, ATR x 2 | 1,762 (0 / 0) | 1,762 | 0 |
| P5 `Chart`, M1, H1 ATR x 0.3 (`K_IN`) | 17,610 (0 / 0) | 17,610 | 0 |
| P5, M1, H1 ATR x 0.6 (`K_MAIN`) | 4,907 (0 / 0) | 4,907 | 0 |

**No pivot of the developer's changes, so none of its P2 / P3 / P4 / P5 learning-part results changes.** The fix
makes the rule hold for a series whose first bar after the warm-up is wide, such as a shorter window or a new start
date.

**Status of the relay (2026-10-20 05:11 UTC = 12:11 Thai):** the first developer applied the same one-line fix to
`dev/patterns.py` (file time 12:08:46 Thai, the line marked "(auditor)"). `audit2/test_relay_dev_zigzag.py` now gives
`2 passed`. The impact table above was measured on the code before that edit: `check_relay_impact.py` refuses to run
unless it finds the old line, and it found it. That edit left `dev/patterns.py` with CRLF line endings (git warns;
`.gitattributes` normalizes them on commit).

## 10. Item 1: "win" = pnl > 0 after costs (changed)

The measurer's answer (notes.md, 2026-10-20 12:21 Thai): a win is a trade with pnl > 0 after costs, whatever its exit
is called. Before, `wf.weekly`, `wf.walk_forward`'s month row and the precursors summaries counted `exit == "win"` (the
target hit), so a profitable time / surrender / structure exit was not a win, and the developer's exit names
(`target`, `structure`, ...) gave 0 %.

**The change:** `(x == "win").mean()` / `(T.exit == "win").mean()` -> `(pnl > 0).mean()` (or `R > 0` where a frame has no
pnl: `place_after_costs`, `trade_labels`) in 24 precursors files: `wf` (weekly, walk_forward's month row, the main
summary), `audit_harness`, `base_after_costs`, `big_trades`, `cut`, `lvl2`, `lvl3`, `lvl_losers`, `model_cost`,
`model_trades`, `paper`, `place_after_costs`, `present_wf`, `pullback`, `pullback15`, `rule_bt`, `sr_break`,
`surrender`, `tick_straddle`, `trade_labels`, `v2b`, `v2c`, `v2e`, `v2s`. A break-even trade (pnl 0.0) is not a win
(and, as before, not a loss in `longest_run`). The exit name still selects trades where a script asks for target
trades (`lvl_losers`, `v2_losers`, `audit.py`), and the labels' own outcome columns (`fp1`, `out`) are not trades.
The developer's `dev/d_report.weekly` and `p2_trades.stats` already count `pnl > 0`.

**Tests (`audit2/test_metrics.py`, now 15):**

| Test | What it checks, by hand |
|---|---|
| `test_the_weekly_win_share_is_the_trades_that_made_money` | exits `target` +10, `structure` +3, `time` 0.0, `time` -2 in one Thai week: win 0.5 (the break-even is not a win) |
| `test_the_walk_forward_months_win_share_is_the_trades_that_made_money` | one cell, two December trades as its past; January's 4 trades +10 (win), +0.5 (time), 0.0, -10 (stop): 4 taken, month win 0.5 |
| `test_a_profitable_time_exit_is_a_win[sr_break / surrender / tick_straddle]` | +10, +0.5, -10, 0.0 -> the printed "win 0.500" |
| `test_no_summary_counts_a_win_by_the_exit_name` | no precursors file computes a share as `exit == "win"` (the three spellings used) |

- Before (`out_win_before.txt`, the HEAD eeca5a9 precursors files in a scratch copy, the same test file):
  `6 failed, 9 passed` - `assert [0.0] == [0.5]` (weekly), `assert [0.25] == [0.5]` (the month), `assert 0.25 == 0.5`
  (each summary), `Left contains 33 more items, first extra item: 'audit_harness.py:54'`.
- After: `15 passed in 1.83s`.
- The earlier tests of the 16 changed modules that have test files (`test_big_trades` .. `test_wf`, from the repo
  root): `93 passed in 43.25s`; the 8 without test files compile (`py_compile`).
- Planted (`plant.py mutants_metrics`, `out_plant_metrics.txt`): `ALL: 14 of 14 caught; unmutated: 15 passed`. New: the
  week's win by the exit name again; the week's break-even counted a win; the month's win by the exit name again; the
  month's break-even counted a win; the summary's win by the exit name again (sr_break); the summary's break-even counted
  a win (surrender).

**What it moves** (`audit2/check_win.py`, output `out_win_impact.txt`: every stored precursors trade file with t / pnl /
exit, 136 files, read with a pyarrow filter t < 2026-04-18; `wf` at eeca5a9 against the working copy):
- No R, USD, drawdown, streak or trade count moves: only the win share. It can only rise: 0 target exits are not in
  profit, so every old win is a new win. 10 learning trades are exactly 0.0 (neither).
- **A. Per file and part:** 240 learning-part cells (P1 / P2): 205 rise, 35 equal, 0 fall; the rise min +0.000,
  median +0.073, max +0.500 (8-trade placebo cell). The largest on real cells: `pullback_trades` P1 0.042 -> 0.384
  (1,871 trades), P2 0.081 -> 0.403; `pullback15_trades` P1 0.062 -> 0.380; `sr_break_trades` P1 0.133 -> 0.327. Older
  rows (before 2025-10-18): 94 cells, +0.010 .. +0.222, median +0.098.
- **B. `wf.weekly`, week by week:** 129 files, 11,218 week rows before the exam, 4,692 rise, 0 fall; every other
  column (cell, trades, R_trade, R, usd, usd_total, worst) equal in all. The LV3 walk-forward (`lvl3_wf_trades`, the
  latest 12 months): 10 weeks, 3 move: 2026-02-16 0.000 -> 0.200, 2026-03-16 0.357 -> 0.571, 2026-04-13 0.111 ->
  0.222. `lvl3_wf_3y_trades`: 119 weeks, 42 move. All rows are in the output.
- **C. `walk_forward`'s month rows** (re-derived from the stored taken trades): 253, 149 rise. LV3: 2026-02 0.190 ->
  0.238 (21), 2026-03 0.226 -> 0.323 (31), 2026-04 to 04-17 0.071 -> 0.143 (14).
- **D. The printed "(learning)" lines** (each file over every row before the exam): 136 files, 132 move. Those printed
  in `out_*.txt`, old = the printed value in every case: `out_wf.txt` 66 trades 0.182 -> 0.258; `out_wf_3y.txt` 500
  trades 0.196 -> 0.312; `out_v2s.txt` 445 trades 0.380 -> 0.427; `out_v2b.txt` 221 trades 0.371 -> 0.412;
  `out_present_wf.txt` 736 trades 0.359 -> 0.424.
- The printed `out_*.txt` files were not re-run; they keep the old numbers until their scripts run again.

## 11. Item 4: `plib.load_learning()` (added)

**The change:**
- `gold.bars(tf, before=None)`: with `before` (UTC-aware), both stores are read with the pyarrow row filter
  `open_time < before`, so no later bar is returned. When every NEW bar is at / after `before`, the OLD cut is
  `before` itself (all OLD rows read are before it). Without `before`, nothing changes. A naive `before` raises
  `TypeError` (tz-naive).
- `plib.load_learning(start=START)`: `load()`'s rules (START inclusive, duplicates keep the last, the six float
  columns), ending before `EXAM_START` (2026-04-18 00:00 UTC), through `gold.bars(before=EXAM_START)`. `plib.load()` is
  unchanged (to END = 2026-10-17) for the measurer's one exam read.

**Tests (`audit2/test_learning_loader.py`, 15):**

| Test | What it checks, by hand |
|---|---|
| `test_it_ends_before_the_exam_and_keeps_load_s_rules` | OLD 23:58, 23:59 (before START), START; NEW START+1 twice, 2026-04-17 23:59, 2026-04-18 00:00, 00:01, 2026-05-04: index START, START+1, 04-17 23:59; opens 3, 11 (the last copy), 12; six float64 columns, UTC |
| `test_it_equals_load_cut_at_the_exam` | `load()` still holds 2026-04-18 00:00; `load_learning()` = `load()[< EXAM_START]` frame-equal |
| `test_a_later_start` | `start=START+1` -> START+1, 04-17 23:59 |
| `test_no_store_read_returns_an_exam_row` | a spy on `pd.read_parquet`: both store reads (NEW and OLD, which holds a 2026-04-20 row) return only rows before the exam |
| `test_equals_the_full_merge_cut_at_before[7 cuts]` | `gold.bars(before=b)` = `gold.bars()[< b]` for b before START, at START, inside the duplicates, at / after the exam, after everything |
| `test_before_the_first_new_bar_keeps_the_old_bars_before_it` | NEW starts after `before`: the OLD bars before it (2 of 4) |
| `test_without_before_nothing_changes` / `test_a_naive_before_is_refused` | 9 bars to 2026-05-04; `TypeError` "tz-naive" |
| `test_the_real_stores_end_before_the_exam` | the real stores through the filter: 954,198 bars, 2023-08-01 00:00 .. 2026-04-17 20:54, unique, sorted (= `out_check_merge.txt`, made from a filtered scratch copy) |

- Before (`out_4_loader_before.txt`, HEAD `gold.py` / `plib.py`): `14 failed, 1 passed` (`TypeError: bars() got an
  unexpected keyword argument 'before'`, `AttributeError: module 'plib' has no attribute 'load_learning'`; the real-store
  test failed on the missing function, before any read).
- After: `15 passed in 3.39s`; with `test_pipeline.py` (load and the merge unchanged): `22 passed`.
- Planted (`plant.py mutants_loader`, `out_plant_loader.txt`; the real-store test left out of the mutant runs, since a
  mutant without the filter would load exam rows): `ALL: 13 of 13 caught; unmutated: 14 passed, 1 deselected`. gold
  (5): the filter `<=`; NEW / OLD read without the filter; no fallback when NEW is empty; a naive `before` taken as UTC.
  plib (8): the stores read to the end and cut after; the learning to EXAM_END; `start` ignored; START exclusive;
  duplicates keep the first; no duplicate removal; the spread dropped; not float.
- `mutants_pipeline.py`'s "spread dropped" pattern was made unique (the new function has the same column list):
  `ALL: 13 of 13 caught; unmutated: 7 passed`.

**The callers** (54 files in `precursors/` call `plib.load()`; found by an AST scan, sorted by reading the lines that
mention the exam; nothing was edited):

| Group | Files | Proposal |
|---|---|---|
| a. read the exam on purpose (an exam switch, an exam part / half, or moments to EXAM_END) - 16 | `base_after_costs`, `big_trades`, `burst_scan`, `by_eye`, `combine`, `loser_audit`, `m1_features`, `m15_trades`, `model_trades`, `moments`, `mw`, `present`, `pullback15`, `range_trades`, `v2b_pictures`, `wf` | keep `load()` only in the exam branch (the measurer's read); the learning branch `load_learning()`. `wf.main` also hands `load()` to `evidence_patterns` for every trade, the exam's included |
| b. cut the bars before the exam right after `load()` - 5 | `framework`, `framework2`, `level_power`, `regime`, `verify_p2` | switch now: the same bars, no exam row in memory (`load_learning(start=...)` for their start dates) - **done in round 3 (section 13)** |
| c. load everything, then pick learning moments only - 5 | `library_present`, `picture_pairs`, `reading_audit`, `snaps`, `zoom_audit` | switch; the result is the same unless a picked moment's drawn / labelled window runs past 2026-04-18 00:00 (the last days of P2) - check on the switch |
| d. no exam filter in sight; mostly the older studies (made before the exam rule of 2026-10-18 on data to 2026-10-17) and library builders - 28 | `audit`, `bot_eye`, `build`, `cont`, `explore`, `eye_check`, `fingerprint`, `footprints`, `gallery`, `gallery_sets`, `indicators`, `library`, `library_match`, `loc`, `loser_charts`, `losers_b`, `lvl_losers`, `no_sl`, `paper`, `phase`, `pullback`, `select_sets`, `straddle`, `touches`, `v2`, `v2_losers`, `wf_library_compare`, `zones` | switch at the next re-run; a re-run then stops at the exam, so its stored outputs (some span to 2026-10-17) no longer reproduce; the measurer decides per file |

- Outside `precursors/`: `dev/` (`patterns.load_m1`, `verify_d`, `verify_p3`), `dev2/` (`swings.load_learning`) and
  `strategist/slib` have their own filtered readers - nothing to change (a proposal only, they are not mine). The
  older folders (`runs/`, `news/`, `trend/`, `reversion/`, `cross/`, `journal/`, `fx/`, `weapon4/`) read `gold.bars` or
  the stores directly without a filter; `shadow/`, `ai_charts/` and `portfolio/` use `portfolio/plib.py` (another
  module). Not active in Setup OWN; listed only.

## 12. dev2's `swings.py` (read only; PASS, two questions)

**The version audited:** `dev2/swings.py`, sha256 `9ebfe2dd5de473b7f702afcfa54aecdf323c2acfd9ab9b0c92b7de2a5f6191c7`,
file time 2026-10-20 12:26:40 Thai (05:26:40 UTC), 545 lines; a snapshot copy in my scratchpad. The hash was the same at
the end of the audit (06:08 UTC = 13:08 Thai). `zigzag_ref.py` (sha256 11ad7e67..) was not audited: `swings.py` does not
import it.

**What was checked and how:**
- **The ZigZag (rule 2)** - `audit2/test_dev2_swings.py`: the hand cases of `audit2/test_swings.py` in dev2's interface
  (a threshold per bar) and under its written rule 2 (a tie keeps the first bar; fingerprint moves it later):
  - one wide bar at the start is never two turns; the first turn waits for a bar that takes an extreme out;
  - an outside bar extends the leg and is one turn (both sides);
  - a tie keeps the first bar, exactly the threshold confirms, 0.01 under confirms nothing;
  - the threshold is read at the confirming bar (both ways: a pivot bar with 10 and a confirming bar with 20 confirms
    nothing; 20 and 10 confirms);
  - 20 random series with wide bars and a threshold that changes every bar: every pivot confirmed by a later bar, no
    bar twice, kinds alternate;
  - no look-ahead: on 5 random series the pivots confirmed by bar d equal those of the series cut at d (17 cuts each).
  - My first version of the "read at the confirming bar" test had a wrong hand value (I let the trough confirm at a
    bar whose threshold was 20). The code was right; the test was corrected.
- **`tf_bars` against `precursors/indicators.bars` on the real learning bars** (249,474 M1 bars 2025-08-01 ..
  2026-04-17 20:54 from `swings.load_learning()`, whose reader filters the exam out): M5 49,903, M15 16,758, M30 8,380,
  H1 4,192, H4 1,098, D1 183 bars; open / high / low / close / last / avail equal on every bar of every TF.
- **Look-ahead of the whole `analyze`** (pivots, structure, bias, box, lines, events, the inner swings): the span
  2025-11-03 .. 2026-01-30 against the same span cut at three server-day ends (2025-11-17, 2025-12-22, 2026-01-14 21:54
  UTC); for each of M1 .. D1 every reading known at the cut (the struct rows, the pivots confirmed by then, the events,
  the boxes and lines born by then) is equal: 21 of 21. Power: in all 21 the full run has more pivots or events after
  the cut. (My first run reported D1 "different": two empty frames with different dtypes; the comparison was fixed to
  compare values.)
- **dev2's own tests, run read only:** `26 passed in 2.34s`.
- Read against the written rules 1-8 / 13: the S at a moment (the last H1 bar complete by it, `side="right"`), the TF
  threshold at the bar's close, the structure pairs, the box walk after the last accepted break, the line anchor with
  the largest / smallest slope (the hull edge), the mirrored `Edge.step` (each comparison checked in the up view) - as
  written.

**Planted (`plant.py mutants_dev2_swings`, `out_plant_dev2_swings.txt`, the file mutated in memory only):
`ALL: 10 of 10 caught; unmutated: 32 passed, 2 xfailed`.** The start-up fix removed; the start-up takes the later
extreme; a tie moves the peak / the trough later; `if` instead of `elif`; strictly above the threshold; the threshold
read at the pivot bar; the confirming bar recorded as the pivot; the trough tracked from the peak bar; the next bar's
threshold (look-ahead).

**Two questions (rule-level, not code bugs; xfail tests in `test_dev2_swings.py`, `out_check_dev2_swings.txt`):**
1. **A pivot is not always the extreme of its leg.** Rule 2 tracks the next extreme from the confirming bar and never
   revises a confirmed pivot. When the threshold changes between bars (it is max(S, the TF's ATR), so it does), price
   can (a) undercut a confirmed trough while the peak is tracked and the larger threshold is not reached, or (b) make
   a lower low before the previous pivot's confirmation. Then the recorded trough is not the lowest low between its two
   peaks. Hand case `test_a_trough_is_the_lowest_low_between_its_two_peaks`: the trough stays 95 @3 though bar 5 went to
   90. On the real learning bars (pivots from 2025-10-18, strictly between the neighbouring pivots):

   | TF | pivots | not the leg's extreme | depth USD median / max |
   |---|---|---|---|
   | M1 | 3,388 | 3 (0.1 %) | 1.42 / 1.94 |
   | M5 | 3,134 | 8 (0.3 %) | 3.20 / 20.47 |
   | M15 | 2,452 | 13 (0.5 %) | 2.76 / 20.12 |
   | M30 | 1,736 | 15 (0.9 %) | 3.66 / 14.80 |
   | H1 | 954 | 10 (1.0 %) | 4.02 / 16.72 |
   | H4 | 256 | 1 (0.4 %) | 6.04 / 6.04 |

   Example (H1): the trough 2025-10-27 20:00 UTC (10-28 03:00 Thai) at 3979.25, while the leg's low is 3973.11 at
   2025-10-28 00:00 UTC (07:00 Thai). A chart reader would put the swing low there. Is the non-revising rule the
   owner's meaning, or should a lower low before the next peak's confirmation move the trough (known from that bar on)?
2. **`running()` and the structure disagree** on rule 4's "running extreme of the leg after the last pivot":
   `running()` takes the lowest low since the pivot, the structure (`analyze`) the ZigZag's tracked extreme from the
   confirming bar. They differ on 104 of 173,030 M1 bars, 32 of 34,613 M5, 15 of 11,624 M15, 10 of 5,813 M30, 2 of
   2,908 H1, 0 of 762 H4 (test `test_running_equals_the_extreme_the_structure_tracks`). Which one is meant, and should
   the public `running()` match it?

## 13. Round 3, item 1: the group-b callers on `plib.load_learning()` (switched, identical)

**The change** (one line each; the cut right after `load()` is now the loader's): `framework.py`, `framework2.py`
`plib.load_learning(start=2025-06-01)`; `level_power.py` `load_learning(start=START - 10 days)`; `regime.py`
`load_learning(start=2025-01-01)`; `verify_p2.py` (`structure_check`) `load_learning(start=2025-09-01)`. Each ends before
2026-04-18 00:00 UTC, as their own cuts did, and no exam row is read into memory any more.

**Test** (`audit2/test_learning_loader.py::test_group_b_reads_only_the_learning_bars`, 5 cases): an AST scan of every
`plib.load(...)` / `plib.load_learning(...)` call in each file; each must hold exactly one call, `load_learning`, with its
own start date (the source text of `start=`).
- Before (the HEAD copies, `out_r3_groupb_before.txt`): `HEAD: 5 failed, 0 passed` (each `[('load', '')]`).
- After: `test_learning_loader.py` `20 passed in 2.58s`; the callers' own tests (`test_framework`, `test_level_power`,
  `test_verify_p2`) `12 passed in 1.82s`.

**The re-runs against the stored outputs** (`out_r3_groupb_diff.txt`; CR stripped). Two scripts run in parallel failed
on the machine's memory (`ArrowMemoryError` / "the paging file is too small"; 879 MB of commit left at the time), not on
the code; each was then run alone.

| Script | Stored output | Result |
|---|---|---|
| `framework.py` | `out_framework.txt` (12:10 Thai) | identical |
| `framework2.py` | `out_framework2.txt` (12:13) + `framework2.parquet` | identical apart from the stored file's first 2 lines, a numpy RuntimeWarning (stderr) captured with stdout, whose line number moved 65 -> 64 since one line went; the parquet byte-identical (sha256 2537fbf5..) |
| `level_power.py` | `out_level_power.txt` (2026-10-18 23:50) + `level_power.parquet` | identical; the parquet byte-identical (f0abdfec..) |
| `regime.py combo_trades.parquet` | `out_regime.txt` (12:28) | all 27 stored lines identical; 4 added lines come from prints added to `regime.py` after that output (the "trades:" line and the by-mechanism weights: P1 +0.301 / USD +263.5, P2 +0.130 / +475.3 = CHECKLIST row 37's "with +1 USD release slippage, by mechanism +0.301 / +0.130"). `combo_trades.parquet` and the default `combo_trades_slip1.parquet` are byte-identical (ced8e2c4..) |
| `verify_p2.py` | no stored file; notes.md 2026-10-19 | the 6 metric lines equal `dev/p2_metrics.csv` (group all, news cost 0) to every printed digit; one position 0; raw ticks 60 of 60; structure exits 1244 of 1244 - as in the notes |

## 14. The PLAN-1 runner `dev/plan1.py` (read only; PASS, no bug; 15 test gaps closed; one question)

**The version audited:** `dev/plan1.py` sha256 `dec3a0a50677bc548e5f17f9b143cc271c9966e69a1b2f78ff7f9956f752d4ae`, file
time 2026-10-20 13:14:26 Thai; `dev/test_plan1.py` `71779f404db67b05e1822c391539f59df3460bf86ea4944d43189a849946cd7b`,
13:09:11 Thai. Snapshot copies in my scratchpad (10:12 UTC = 17:12 Thai); the hashes were the same at 10:31 UTC. Its
stored learning run (`plan1_every_learn_s0_x0.parquet`, `plan1_trades_learn_s0_x0.parquet`, `out_plan1_learn_s0_x0.txt`,
13:17 Thai) was written after the last edit. Its exam switch was never run and no exam data was read: every store read
in my checks has a row filter ending before 2026-04-18, and every tick day read is asserted to be before it.

**Read against the brief:**
- **The exam switch:** `--exam` (`store_true`, default False) is the only way into the exam. `period(False)` = the
  learning parts; `check_period` refuses a learning period past 2026-04-18 and an exam period other than 2026-04-18 ..
  2026-10-18; `load_m1` refuses an end past 2026-04-18 without the switch before reading, reads with a pyarrow row
  filter and re-checks the rows; `PlanTicks` never opens a tick day at / after the period's end (also when B2 joins
  the next day); `build` refuses a trade outside the period; `--repro` reads only the learning M1 and refuses `--exam`.
  No imported module reads data at import (checked: `p3_trades`, `d1_orb`, `p2_trades`, `p4_trades`, `patterns`,
  `sweep_detector`, `news_follow`, `regime`, `indicators`, `phase`). B2's own period guards read module globals at
  call time, so `located_in` moves them for the period and restores them.
- **The cost:** fills at the tick's ask (buy) / bid (sell) + the slippage; market exits at the bid / ask; targets as
  limits. The slippage is `--slippage` (default 0) on every piece: London and NY take it as an argument, B2 through
  `entry_slippage` (B2's simulator reads `p2_trades.SLIP` at each fill, checked in `p3_trades.simulate3`); the NY
  release slippage is `--extra` (default 0). No other cost term (no spread formula, no stop slippage) is used.
- **The one-position stream:** all three pieces' trades in fill order; a fill strictly before the kept trade's exit is
  dropped; a fill at the exit is taken (the convention of `combo.stream` and `verify_p2`).
- **The D1 state:** `indicators.bars(m, "1D")` (server-day bars, `avail` = the last M1 minute + 1; equal to MT5's D1
  in round 1, 2a), `regime.state_at` at the fill: the last bar with `avail <= t`, the 20-day efficiency, P1's terciles
  0.116 / 0.264. The M1 starts 2025-09-01, so the first learning trade has more than 20 closed D1 bars (NaN used: 0).

**Tests (`audit2/test_plan1_audit.py`, 6 + 1 question; stubs record the arguments, nothing reads market data):**

| Test | What it checks, by hand |
|---|---|
| `test_main_without_the_switch_never_builds_the_exam` | `main([])` -> `build(False, 0.0, 0.0)`; `--slippage 0.07 --extra 1` -> `(False, 0.07, 1.0)`; only `--exam` -> `(True, ...)` (the stub stops the run); `main` never reads M1 itself |
| `test_repro_reads_only_the_learning_m1` | `main(["--repro"])` -> `load_m1(2026-04-18, False)` once, then `repro` |
| `test_build_hands_every_piece_the_period_the_tick_end_and_the_slippage` | learning: Asia (2025-10-18, 2026-04-18, ticks end 2026-04-18, slip 0); London 2025-10-20 .. 2026-04-17, 130 days, ticks end 2026-04-18, slip 0; NY the same, slip 0, extra 0; 0.07 / 1.0 reach every piece; the exam (only when asked): Asia / ticks end 2026-10-18, London 2026-04-20 .. 2026-10-16; the state reads server-day D1 bars (30 days of 00:00-09:50 UTC bars -> 30 bars, each complete at 09:51) |
| `test_a_trade_outside_the_period_stops_build` | a stub Asia trade filled at 2026-04-18 00:00 in a learning run -> `ExamPeriodError` |
| `test_asia_b2_runs_b2_with_this_runs_slippage_and_bounds_and_keeps_entries_in_the_period` | `locate` runs inside (2025-10-18, 2026-04-18); the scan starts at the first bar complete at / after the start (bar 1); B2's simulator sees `SLIP` 0.0 (and 0.07 when asked), mode "structure", news cost 0; of 3 candidates (Asia 04-17 01:00 UTC, Asia 04-18 01:00, London 04-17 06:30) the stream gets the two Asia ones and the row kept is 04-17's, `t_dec` = the decision, `t_in` = the fill; the globals restored |
| `test_one_position_at_a_time_by_its_definition` | 200 random sets (1-39 trades, three pieces, shuffled input): kept fills in order, never before the open trade's exit, every dropped trade fills inside a kept trade that filled no later; by hand: a fill at the exit is taken, 1 ns before it is not |
| `test_the_exam_switch_takes_no_abbreviation` (xfail, question 10) | `parse(["--exa"])` turns the exam on (argparse abbreviations) |

- Run: `test_plan1_audit.py` + the developer's `test_plan1.py`: `25 passed, 1 xfailed in 4.73s`.
- **Planted (`plant.py mutants_plan1`, `out_plant_plan1.txt`; in memory only): the developer's tests alone 3 of 18
  caught; with mine 18 of 18 caught.** The 15 its tests miss: `main` builds the exam by default; `main` ignores
  `--slippage`; `main` ignores `--extra`; `--repro` reads M1 to the exam's end; the ticks read to the exam's end; the
  trade-period guard removed; Asia from the learning start in the exam; London at 0.07; NY without the extra; the state
  from H4 bars; B2 at 0.07; `locate` bounded to the exam's end; B2 entries past the period kept; B2's fill time = the
  decision; the scan from the first bar. Its own 40 planted bugs (`dev/out_plant_bugs_plan1.txt`) are all caught: they
  mutate the pieces it tests by hand. None of the 15 is in the code; they are gaps a later edit could slip through -
  **relay: the developer may adopt these tests** (question 11).

**The learning trades on the real data (`check_plan1_audit.py --rebuild`, `out_check_plan1_audit.txt`, 10:23-10:26 UTC):**
0. `plan1.build(False, 0.0, 0.0)` rebuilt in memory = the stored files: every 298 rows, trades 298 rows, frame-equal.
1. **The D1 state from a second source:** MT5's own D1 bars (from 2025-01-01), the last bar whose `close_time <=` the
   fill, the efficiency by my own loop: **298 of 298** labels equal; NaN used 0; the bar read closed 0.08 .. 3.65 days
   before the fill (none after). The measurer's path (`load_learning(2025-01-01)` -> `bars` -> `regime.state_at`, 8
   months more history): 298 of 298, |er difference| 0. Trades per part x state: P1 mixed 29 / sideways 37 / trend 75,
   P2 56 / 48 / 53.
2. **The stream:** 298 trades, 298 kept, **0 dropped** (the three pieces never overlapped in the learning parts at
   slippage 0; the closest next fill came 4.0 min after an exit), so only the unit tests exercise the stream (question
   12). `w_mech` equals the written table; the P1 rule recomputed on these trades = {Asia B2 trend 0.5, NY straddle
   sideways 0.5} = `W_P1`; `w_p1` equal.
3. **The cost on the raw ticks:** 298 of 298 fills = the tick's ask / bid exactly (no slippage), exits at the tick or
   the target, risk / R consistent, no tick beyond the stop before a non-stop exit, London targets at 2 R: faults 0.
   My first version flagged 1 NY fill (2025-11-07 13:30:56.816 UTC): two ticks share that millisecond (bid 3995.11,
   then 3995.02 <= the trigger 3995.04) and the runner filled on the second, correctly; the check now accepts any tick
   of the millisecond (1 such fill). The measurer's independent `check_plan1.london(0.0)` / `ny(0.0)`: **London
   119 / 119, NY 100 / 100, |dR| max 0.0000.**
4. **The printed plan lines** (`out_plan1_learn_s0_x0.txt`), recomputed by separate code (n, win, R, USD, max DD from
   0): **6 of 6 equal** - unweighted P1 141 / 0.532 / +0.249 / +256.18 / 55.82, P2 157 / 0.484 / +0.137 / +507.55 /
   116.69; by mechanism P1 +0.337 / +293.24 / 34.61, P2 +0.188 / +534.37 / 74.88; from P1: P1 +0.288 / +292.02 / 38.71,
   P2 +0.147 / +523.41 / 99.61.

## 15. Round 3, item 3: dev2's two test gaps (tests added)

The measurer's planted bugs in `dev2/swings.py` that no unit test caught (`precursors/plant_dev2_v31.py`): `known_at`
one bar ahead (`searchsorted(piv[3], d + 1, ...)`) and `running()` including the pivot bar (`slice(pb[-1], d + 1)`).
The file changed since round 2: now sha256 `ff1eff818185fa4b38437b6be49bd6edc6fb91e390da1959fefc9807d32e4245`, file time
2026-10-20 17:08:49 Thai; the two functions' lines are the ones the mutants name.

| Test (`audit2/test_dev2_swings.py`) | What it checks, by hand |
|---|---|
| `test_known_at_leaves_out_a_pivot_confirmed_on_the_next_bar` | h 10, 19, 15, 12 / lo 9, 15, 12, 9, threshold 10: trough 9 @0 confirmed by bar 1, peak 19 @1 confirmed by bar 3; pivots known at d = 0..3: 0, 1, 1, 2 (a pivot confirmed at d + 1 is not known at d) |
| `test_running_starts_after_the_pivot_bar[False / True]` | h 10, 30, 25, 22, 24 / lo 9, 12, 21, 19.5, 18: trough 9 @0 (by bar 1), peak 30 @1 (by bar 3: 30 - 19.5 = 10.5); the peak bar's own low 12 is below every later low; `running` at bar 3 = (3, 19.5, trough), at bar 4 = (4, 18, trough), at bar 2 (the peak not yet confirmed) = (1, 30, peak); the same upside down |

- My first hand value was wrong (a bar-2 low of 20 already confirms the peak at bar 2: 30 - 20 = 10); the code was
  right; the series was changed to 21.
- On the current code: `test_dev2_swings.py` `35 passed, 2 xfailed in 2.56s`.
- **Planted (`plant.py mutants_dev2_swings_r3`, `out_plant_dev2_swings_r3.txt`): the two tests alone 2 of 2 caught; the
  whole file 2 of 2 caught.** Round 2's 10 mutants on the new version: `10 of 10 caught; unmutated: 35 passed, 2
  xfailed`.

## The files changed by the audit

| File | Change | Its test (fails before, passes after) |
|---|---|---|
| `app/market_data/history_download.py` | the tail check against the newest bar / latest tick, re-read after a wait, `HistoryIncompleteError` | `tests/unit/test_history_download.py` (new, 14): HEAD 7 failed / 7 passed -> 14 passed |
| `research/.../precursors/fingerprint.py` | the ZigZag start-up: one bar holding both extremes is not a turn | `audit2/test_swings.py`: HEAD 22 failed / 5 passed -> 27 passed |
| `research/.../precursors/tick_straddle.py` | `span_ticks` (the next UTC day joined, never an exam day); `run` uses it; the drawdown from 0 | `audit2/test_simulators.py`: HEAD 3 failed / 6 passed -> 9 passed (with the touches test); `audit2/test_metrics.py` |
| `research/.../precursors/surrender.py` | `run` and `main` use `span_ticks`; the drawdown from 0 | the same |
| 18 more precursors files (`big_trades`, `cut`, `lvl`, `lvl2`, `lvl3`, `model_cost`, `model_trades`, `present_wf`, `pullback`, `pullback15`, `rule_bt`, `sr_break`, `v2`, `v2b`, `v2c`, `v2e`, `v2s`, `wf`) | the drawdown from 0 (one expression each) | `audit2/test_metrics.py`: 4 failed / 5 passed -> 9 passed + 1 xfail |

Round 2 (2026-10-20, not committed):

| File | Change | Its test (fails before, passes after) |
|---|---|---|
| 24 precursors files (section 10: `wf`, `audit_harness`, `base_after_costs`, `big_trades`, `cut`, `lvl2`, `lvl3`, `lvl_losers`, `model_cost`, `model_trades`, `paper`, `place_after_costs`, `present_wf`, `pullback`, `pullback15`, `rule_bt`, `sr_break`, `surrender`, `tick_straddle`, `trade_labels`, `v2b`, `v2c`, `v2e`, `v2s`) | item 1: a win = pnl > 0 (R > 0 where no pnl) | `audit2/test_metrics.py`: 6 failed / 9 passed -> 15 passed |
| `research/2026-10-18-moments/gold.py` | item 4: `bars(tf, before=None)`, the row filter while reading | `audit2/test_learning_loader.py`: 14 failed / 1 passed -> 15 passed |
| `research/.../precursors/plib.py` | item 4: `load_learning(start=START)` | the same |
| `audit2/plant_bugs_1a.py`, `out_plant_bugs_1a.txt` | item 3 (the app fix is in eeca5a9): 4 closed-bar mutants added, 18 of 18 caught | - |
| `audit2/`: `check_win.py`, `check_dev2_swings.py`, `test_learning_loader.py`, `test_dev2_swings.py`, `mutants_loader.py`, `mutants_dev2_swings.py` (new); `test_metrics.py`, `mutants_metrics.py`, `mutants_pipeline.py` (changed); outputs `out_win_before.txt`, `out_win_impact.txt`, `out_4_loader_before.txt`, `out_check_dev2_swings.txt`, `out_plant_metrics.txt`, `out_plant_loader.txt`, `out_plant_pipeline.txt`, `out_plant_dev2_swings.txt` | the audit's own files | - |

Nothing in `dev/` or `dev2/` was edited by the audit (dev2's `swings.py` was mutated in memory only). Nothing was
committed.

Round 3 (2026-10-20, not committed):

| File | Change | Its test (fails before, passes after) |
|---|---|---|
| `research/.../precursors/framework.py`, `framework2.py`, `level_power.py`, `regime.py`, `verify_p2.py` | `plib.load()` + the cut -> `plib.load_learning(start=...)` (one line each) | `audit2/test_learning_loader.py::test_group_b_reads_only_the_learning_bars`: HEAD 5 failed / 0 passed -> 5 passed; the outputs identical (section 13) |
| `audit2/`: `test_plan1_audit.py`, `check_plan1_audit.py`, `mutants_plan1.py`, `mutants_dev2_swings_r3.py` (new); `test_learning_loader.py`, `test_dev2_swings.py` (tests added); outputs `out_r3_groupb_before.txt`, `out_r3_groupb_diff.txt`, `out_check_plan1_audit.txt`, `out_plant_plan1.txt`, `out_plant_dev2_swings_r3.txt` | the audit's own files | - |

Nothing in `dev/` or `dev2/` was edited (`plan1.py` and `swings.py` were mutated in memory only; the plan1 check calls
`build` in memory and writes nothing there). Re-running `framework2.py` / `level_power.py` rewrote their parquet files
in `precursors/` with byte-identical content. Nothing was committed.

## The commands to re-run every check (from the repo root, `.venv`)

```
# 1a (app code)
.venv/Scripts/python -m pytest tests/unit/test_history_download.py tests/unit/test_market_data.py tests/unit/test_candle_sync.py tests/unit/test_architecture.py -q
.venv/Scripts/ruff format --check app/market_data/history_download.py tests/unit/test_history_download.py
.venv/Scripts/ruff check app/market_data/history_download.py tests/unit/test_history_download.py
.venv/Scripts/mypy app/market_data/history_download.py
.venv/Scripts/bandit -q -c pyproject.toml app/market_data/history_download.py
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant_bugs_1a.py          # HEAD before + 14 planted bugs
# every audit test (the relay separately)
.venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_pipeline.py research/2026-10-18-moments/agents/audit2/test_bars.py research/2026-10-18-moments/agents/audit2/test_foundation_hand.py research/2026-10-18-moments/agents/audit2/test_swings.py research/2026-10-18-moments/agents/audit2/test_simulators.py research/2026-10-18-moments/agents/audit2/test_dev_simulate.py research/2026-10-18-moments/agents/audit2/test_windows.py research/2026-10-18-moments/agents/audit2/test_metrics.py -q
.venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_relay_dev_zigzag.py -q
# planted bugs (each prints CAUGHT / MISSED and the unmutated run)
for s in mutants_pipeline mutants_bars mutants_foundation mutants_swings mutants_sims mutants_windows mutants_metrics mutants_loader mutants_dev2_swings; do .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py $s; done
# the real-data checks (learning parts / older history; post-exam days only for alignment)
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_merge.py      # 1b / 1c
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_dst.py        # 1d
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_bars.py       # 2a / 2b
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_swings.py     # 4 (a few minutes)
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_costs.py      # 6
# round 2 (2026-10-20)
.venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_metrics.py research/2026-10-18-moments/agents/audit2/test_learning_loader.py research/2026-10-18-moments/agents/audit2/test_dev2_swings.py -q
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_win.py         # 10: every win share moved, learning rows only
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_dev2_swings.py # 12: tf_bars, truncation, the two properties
# round 3 (2026-10-20)
.venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_learning_loader.py research/2026-10-18-moments/agents/audit2/test_dev2_swings.py research/2026-10-18-moments/agents/audit2/test_plan1_audit.py research/2026-10-18-moments/agents/dev/test_plan1.py -q
for s in mutants_plan1 mutants_dev2_swings_r3; do .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py $s; done
.venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_plan1_audit.py --rebuild   # about 3 min; learning parts only
for f in framework framework2 level_power; do .venv/Scripts/python research/2026-10-18-moments/agents/precursors/$f.py; done   # one at a time
.venv/Scripts/python research/2026-10-18-moments/agents/precursors/regime.py combo_trades.parquet
.venv/Scripts/python research/2026-10-18-moments/agents/precursors/verify_p2.py
```
The one-off measurements whose code is in this file's history, not in a script: the window split
(`out_window_split.txt`), the drawdown impact (`out_dd_impact.txt`, `out_dd_printed.txt`), the callers' entry hours
(section 5), and the HEAD "before" runs of sections 4 and 5 (`out_4_before.txt`, `out_5_before.txt`: the HEAD file
loaded in place of the module, then the test file run). `check_relay_impact.py` refuses to run now that the developer
has applied the fix (it needs the old line).

## Questions for the measurer

Round 3's:

10. **The exam switch takes abbreviations:** argparse accepts `--exa` for `--exam` (`--ex` is refused as ambiguous with
    `--extra`). Not reachable by default (a person must type it), but `ArgumentParser(..., allow_abbrev=False)` in
    `dev/plan1.py` would make only the full `--exam` work. The xfail test `test_the_exam_switch_takes_no_abbreviation`
    waits for the decision.
11. **The PLAN-1 test gaps:** 15 of my 18 planted bugs in `plan1.py` pass the developer's tests (all are caught by
    `audit2/test_plan1_audit.py`; none is in the code). Shall the developer adopt these tests into `dev/test_plan1.py`?
12. **The stream is not exercised by the learning data:** at slippage 0 the three pieces never overlapped (0 dropped of
    298; the closest fill 4.0 min after an exit). Only the unit tests cover it - noted, since the exam may overlap.

Round 2's questions were answered: 6-7 go to the owner / dev2 (the xfail tests stay); 8 -> all 24 files stay; 9 -> the
measurer fixes `trade_labels.py`'s wording.

Round 1's questions 1-5 were answered on 2026-10-20 (notes.md): 1 -> section 10, 2 -> the entry time, 3 -> eeca5a9,
4 -> section 11, 5 -> section 12. Round 2's:

6. **dev2's pivots and the leg's extreme** (section 12, question 1): a confirmed pivot is never revised, so 0.1-1.0 %
   of pivots are not the extreme of their leg (by up to 20 USD on M5 / M15). Is that the owner's meaning?
7. **dev2's `running()` against the structure's running extreme** (section 12, question 2): which one does rule 4
   mean?
8. **Item 1's scope:** the brief named `wf.weekly`; I changed the win share in every precursors summary (24 files) so
   that "win" means one thing everywhere. If only `wf.py` should change now, the other 23 files can be committed
   later or reverted; `test_no_summary_counts_a_win_by_the_exit_name` covers all of them.
9. **`trade_labels.py` still prints "a coin's side"** (the mean of the buy and sell R), a phrase the owner removed
   from the system on 2026-10-19. Not mine to change; noted for its owner.

Round 1:

1. **"Win" in `wf.weekly` and the precursors summaries** is the target-hit rate (`exit == "win"`). The developer's
   exits are named `target` / ..., so its weekly table would show 0 % wins, and its own stats use `pnl > 0`. Which
   does the owner mean? The xfail test `test_the_weekly_win_share_with_the_developers_exit_names` waits for the
   answer.
2. **The window by entry or decision time:** the B2 Asia lead in P1 is +0.092 by entry time and +0.004 by decision
   time. Which time does the owner's "trade only in the windows" mean? The developer's P4 uses the entry.
3. **The forming bar** is stored by `download_history` (the last bar of each download, repaired by the next
   overlapping one). Should the download keep closed bars only, as its docstring says? It would be a second app
   change.
4. **`plib.END` = 2026-10-17** hands the exam rows to every `plib.load()` caller. Keep it, since the measurer reads
   the exam through it, or add a learning-only loader for the others?
5. **dev2's swings** (`dev2/swings.py`, `zigzag_ref.py`): shall I run the same hand cases and mirror check on them
   when V3-1 is delivered?
