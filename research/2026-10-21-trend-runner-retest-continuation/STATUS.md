# Trend Runner (TR1 + RETEST-CONTINUATION V1) status

Updated: 2026-10-22 (owner decision of the same day). The previous status page is kept in
`_original_2026-10-22/STATUS.md` for the record only.

## Earlier results are reset

Every earlier Trend Runner result - the historical diagnostic and its weekly reports, the filter and ATR studies, the
2021-2023 holdout, the TR1 P1/P2 rounds and the 3-year walk-forward - is **reset**. Those numbers came from code with
the bugs below (look-ahead in the pullback choice, M1-bar approximations where the rule fills on ticks, a wrong
eligibility test) and must not be quoted or used. The output files stay on disk only as history.

## Bugs found and fixed (details and evidence: `DEBUG_2026-10-22.md`)

| # | Bug | Status |
|---|---|---|
| B1 | TR1 first pullback: a later pullback was substituted when the first valid one did not continue (look-ahead) | fixed in `tr1/opportunity.py`; TR1 re-frozen |
| B2 | V1 dropped M5 bars with a missing M1 minute | fixed |
| B3 | V1 expired the retest / confirmation 8 h after the stop (the rule limits only the reclaim) | fixed |
| B4 | V1 M5 ATR was not MT5's formula | fixed (`foundation.atr`) |
| B5 | V1's historical TR1 source came from the M1-approximation walk-forward (M1 open + M1 spread, stops at the stop price) | V1 now uses TR1's tick path; `walkforward.py` retired |
| B6 | V1 entries, stops, trail and time exit ran on M1 OHLC + M1 spread instead of bid/ask ticks | fixed (tick simulator) |
| B7 | Original entry spread taken from the M1 bar, not the source fill | fixed |
| B8 | Eligibility required a -1R touch on M1 bars (misses trailed stops before +1R) | fixed (tick SPLIT result) |
| B9 | Historical window shorter than the rule's maximum span | fixed (pipeline + coverage guard) |
| B10 | Prospective adapter refused / reordered equal-time ticks | fixed |
| S1 | Shadow TR1 detector: same look-ahead as B1 | fixed |
| S2 | Shadow tick loaders reordered equal-time quotes | fixed |

The M1 replays `historical_diagnostic.py`, `run_historical_holdout.py` and the 3-year `walkforward.py` now refuse to
run. Tests: 62 (this folder) + 61 (TR1) + 33 (shadow) + 3 (walk-forward guard) pass; planted bugs 57 of 57 caught.
Two independent re-derivations from raw ticks give the same 19 TR1 trades.

## Rule choices kept as in the original (decided by the journal, not by code)

A1 SELL signal bars lifted by the M1 spread; E0 is the executable fill. A2 entry = first quote at/after the
confirmation close (within 2 minutes). A3 the M5 bar of the entry minute counts as "after entry" for the trail.
A4 the 6- and 2-bar windows count existing bars across breaks. A5 a trailed stop before +1R is eligible even with
R > 0. A6 slippage on the entry only, default 0. These are rule choices, not bugs: they stay as they were and wait
for the journal.

## How to run (one week at a time)

```powershell
.venv\Scripts\python research\2026-10-21-trend-runner-retest-continuation\pipeline.py 2025-11-03 2025-11-10
```

The reserved exam [2026-04-18, 2026-10-18) is refused before any read. `run_observer.py` remains the forward
(post-2026-10-21) path.

## Next

The weekly Trend Runner journal with the owner, **after the current NY-window Asia B2 journal is finished**. No
learning run before that.
