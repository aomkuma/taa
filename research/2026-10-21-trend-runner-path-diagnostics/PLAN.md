# Trend-runner post-entry path diagnostics

## Purpose

Describe how the already-selected TR3 RUNNER trades behave after entry, and whether the path of profitable trades differs from non-profitable trades at 15, 30, 60 and 120 minutes. This is exploratory research only. It does not change TR1, TR3, TR4, any order path, or the forward-shadow contract.

## Evidence boundary

- Read only `research/2026-10-20-trend-runner-r3/predictions_primary.parquet` and `data/history/FBS-Demo/XAUUSD/M1.parquet`.
- Restrict the population to the frozen TR3 `action == RUNNER` rows (expected 83 rows; all P1/P2 seen development data).
- Define outcome cohorts by the frozen `runner_r > 0` (positive) versus `runner_r <= 0` (non-positive).
- The historical exam remains locked and is not used. No observations after an entry's 120-minute checkpoint are read for path metrics.
- Do not tune entry, exit, score, thresholds, or use the diagnostics to promote a strategy.

## Frozen measurements

At each checkpoint (15, 30, 60, 120 elapsed minutes after actual `entry_time`), use only complete M1 bars whose `open_time` is at or after the next whole-minute boundary after entry and whose `close_time` is no later than the earlier of the checkpoint and the frozen `runner_exit_time`. This excludes the partially formed entry minute, prevents using information unavailable at the checkpoint, and never counts market movement after the position was closed. Record whether the trade was still open at the checkpoint and actual minutes observed; report survivors separately because later checkpoint survivor cohorts are small and selected by holding time.

For side `s` (+1 BUY, -1 SELL), entry `E`, and initial risk `RISK`, measure the path through the earlier of exit/checkpoint:

- close return in R: `s * (last_close - E) / RISK`;
- OHLC MFE in R: maximum directional high/low excursion from E divided by RISK;
- OHLC MAE in R: minimum directional low/high excursion from E divided by RISK;
- +1R/+3R reached: whether any complete bar's directional high/low touched that level by checkpoint;
- giveback in R: MFE less checkpoint close return.

Report count, median and interquartile range by outcome cohort and checkpoint, plus target-touch rates. Distinguish the exploratory, retrospective cohort label from information available at the checkpoint. M1 OHLC cannot establish tick ordering inside a bar; excursion and touch values are bar approximations, not executable fills.

For a compact chart-structure description, aggregate the complete in-position post-entry M1 observations to UTC M5 bars, and count directionally higher highs / higher lows for BUY (lower lows / lower highs for SELL), comparing adjacent completed M5 bars. This is descriptive only, not a pivot signal or filter.

## Reporting

Record cohort counts, missing/short path coverage, checkpoint metrics, caveats, and one restrained conclusion. Include the source files and date range. Treat small subgroup differences as hypotheses, not stable effects. Any candidate rule requires a newly collected forward sample under the existing shadow/evaluation contract.
