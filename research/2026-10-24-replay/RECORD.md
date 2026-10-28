# The AI trader's whole measured record

Every day the AI trader has ever traded, with the code version it ran on. Nothing here is a forecast; it is
what happened on replayed ticks. Written 2026-10-28 while recovering day 3's reports, which had been lost.

**The goal to beat: at least +0.15 R a trade after the spread.** Nothing below reaches it.

## Day by day

| Thai day | code version | trades | win | R total | R a trade | net USD | 300 USD account |
|---|---|---:|---:|---:|---:|---:|---|
| 2026-07-06 | first build | 3 | - | +0.21 | - | - | 300.00 → 299.65 |
| 2026-07-07 | after day 1's fixes | 4 | - | −2.43 | - | - | 299.65 → 273.66 |
| 2026-07-08 | ISSUES 29-33 (`1_regime`) | 4 | 25 % | −1.82 | −0.455 | −26.02 | 273.66 → 247.64 |
| 2026-07-08 | re-run (`2_rerun`) | 3 | 33 % | −0.91 | −0.303 | −6.60 | 273.66 → 267.06 |
| 2026-07-08 | + confirm on M1 (`3_confirm_m1`) | 3 | 33 % | −1.24 | −0.414 | −10.39 | 273.66 → 263.27 |
| 2026-07-08 | + confirm on M5 (`4_confirm_m5`) | 4 | 50 % | −0.94 | −0.235 | −11.61 | 273.66 → 262.05 |
| 2026-07-09 | never finished | - | - | - | - | - | - |
| 2025-02-25 | the R01 experiment | 0 | - | 0 | - | - | unchanged |
| 2025-02-26 | the R01 experiment | 0 | - | 0 | - | - | unchanged, 59 wakes |

The four day-3 rows are the **same day** under four code versions, not four days. The full reports are in
`day3_variants/`; their numbers come from each run's own backtest header (trades, win rate, net, expectancy)
and its closing line.

## What the record says

- **Three days traded, eleven to twelve trades, never a positive day after day 1.** The best version of the
  best-measured day still loses 0.235 R a trade.
- **The fixes did help, and not enough.** Day 3 went from −0.455 to −0.235 R a trade across four versions -
  a halving, with the win rate rising 25 % → 50 % - while staying the wrong side of zero.
- **No version has been measured on more than one day.** Day 1 and day 2 have never been re-run on the code
  that produced the −0.235 figure, and day 4 has never run at all. Four single-day numbers from four
  different code versions are not a record of one system.

## Why day 3's reports were lost, and what was changed

`day.py <date> --report` prints to stdout. On 2026-10-26/27 the runs were redirected into
`data/replay/ai/*.log`, while four empty files sat in this folder with the names a reader would look for
(`day_2026-07-08.md`, `_before_confirm`, `_confirm_m1`, `_confirm_m5`, all 0 bytes). `data/` is gitignored,
so the only copies of a third of the record were untracked files on one machine, behind names nobody opens.

Changed on 2026-10-28: the four reports are copied here as `day3_variants/*.md`, with LF endings, and the
four empty placeholders are deleted. The mapping to the old `.log` names is in the table above.

**The habit this cost:** a run's report belongs in this folder under the name a reader looks for, in the same
change as the run. An empty file is worse than a missing one - it answers the question wrongly.

## The re-run of 2026-10-28: one code version, one day at a time

Commit `d00c658`, from an empty store and an empty answers cache (the owner: "wipe the result memory, then
start again"). Day by day, each day reported before the next runs. The journal, with the measurer's own
reading of every decision, is `rerun_2026-10-28/JOURNAL.md`; the generated reports are beside it.

| Thai day | wakes | trades | R | 300 USD account | 100 USD account | AI cost |
|---|---:|---:|---:|---|---|---:|
| 2026-07-06 | 27 | **0** | +0.00 | 300.00 -> 300.00 | 100.00 -> 100.00 | 0 USD |
| 2026-07-06 round 2 (`2da4c76`, ISSUES 37-38 fixed) | 36 | **3** | **+0.71** | 300.00 -> 314.22 | 100.00 -> 114.23 | 0 USD |
| 2026-07-07 day 2 (`2da4c76`, the 150 USD account) | 49 | 1 | **-1.08** | - | 164.22 -> 148.10 | 0 USD |

Day 1 took no trade in a 74.47 USD day. Four causes were found and recorded as ISSUES 37-40, three of them
inputs the AI was never given: R10's H4 lean (the real value was +3.515 all morning, behind a BUY, while the
AI used R10 to refuse buys), the London ORB range, and a morning plan that priced nothing. The fourth is
ISSUES 2 and 29 recurring - its own plan's trigger fired on 1.8x volume and the entry was watched past.

## The next measurement that would settle anything

All four days on **one** code version, today's, in order, with day 4 run to the end. Until then there is no
record of the system as it now stands - only of four systems, one day each.
