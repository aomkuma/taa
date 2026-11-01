# Directional-regime breakout filter result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before calculation.  
**Sample:** 158 covered sessions; 110 development / 48 validation.

| Variant | Dev trades | Dev net R | Validation trades | Validation net R |
|---|---:|---:|---:|---:|
| rotation_plus_breakout | 95 | -11.82 | 52 | -5.76 |
| breakout_directional_gate | 46 | +5.31 | 29 | -2.90 |

The regime-gated variant had only 2 breakout trades in development and zero breakout trades in validation; its 29 validation trades were unchanged rotation fades, totaling -2.90R. Of the two gated development breakouts, one won. The filter therefore did not produce enough breakout observations to validate the hypothesis and did not pass the frozen rule.

The ungated breakout strategy remained negative (-5.76R validation). The gated breakout addition is not selected. The zero gated breakout count in validation is explained by the combined two-close acceptance, retest-within-six-bars, six-hour efficiency >=0.35, and direction-alignment conditions; it is too restrictive on this sample.

FBS quote-update volume is broker-specific; bid/ask included, commission/extra slippage excluded. Validation was previously inspected.

Artifacts: `PROTOCOL.md`, `test_breakout_gate.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`.
