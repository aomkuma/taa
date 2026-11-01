# M1 profile row-size sensitivity result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md` written before the $0.01 and $0.50 runs.  
**Feed:** FBS-Demo M1 tick_volume profiles; FBS raw bid/ask tick execution.

## Validation results

| Bin width | Rule | Trades | Wins | Net points/oz | Net R |
|---:|---|---:|---:|---:|---:|
| $0.01 | baseline | 23 | 7 | -41.73 | -13.49 |
| $0.01 | min_rr_2 | 4 | 0 | -9.31 | -4.90 |
| $0.10 | baseline | 25 | 7 | -43.18 | -15.98 |
| $0.10 | min_rr_2 | 7 | 0 | -12.46 | -7.98 |
| $0.50 | baseline | 21 | 5 | -41.18 | -14.01 |
| $0.50 | min_rr_2 | 5 | 0 | -12.29 | -5.89 |

The $0.10 rows reproduce `../m1_tick_volume_profile_2026-10-31/REPORT.md`; $0.01 is the FBS symbol tick size, and $0.50 is a coarser sensitivity case. The fixed M1 profile edge strategy lost in validation at all three widths. The 2R version had zero winners in validation at all three widths (7, 4 and 5 trades, respectively). No row size produced a candidate.

Development did not provide consistency either: at $0.01 the baseline had 1/3 positive folds and the 2R rule 2/3, but validation was -4.90R; at $0.50 both variants had 0/3 positive folds. Do not choose a width from these historical results.

## Interpretation

The negative result is not caused only by the chosen $0.10 bin. But none of these FBS profiles is a substitute for the OANDA profile in the screenshot. The specific custom indicator row-size setting is still unknown, and all three variants use FBS M1 OHLC range allocation rather than OANDA M1 bars.

Commission and extra slippage are excluded; adding them cannot improve these already negative validation results. This does not prove every POC method fails; it rejects this frozen edge-rotation + 2R rule across these tested row widths.

Artifacts: `PROTOCOL.md`, `test_bin_width.py`, `bin_0.01/`, `bin_0.50/`, and the existing $0.10 run in `../m1_tick_volume_profile_2026-10-31/`.
