# POC-stable balance cluster result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the corrected run.  
**Sample:** 158 covered sessions (110 development, 48 validation).

| Period | Trades | Wins | Net points/oz | Net R |
|---|---:|---:|---:|---:|
| development | 57 | 18 | -100.23 | -23.87 |
| validation | 21 | 7 | +1.82 | -3.43 |
| all | 78 | 25 | -98.41 | -27.30 |

Development folds: fold 1 -2.14R, fold 2 -14.41R, fold 3 -7.32R

The stricter center-stability gate produced 149 cluster starts across 158 sessions (the 10% limit still passed in most sessions). It did not pass selection: validation was -3.43R and all three development folds were negative. It also underperformed the ungated frozen-rotation baseline by development R.

No method is selected. This result says the tested POC/VA profile-stability condition did not isolate a profitable rotation opportunity in this sample.

The same-data validation has been inspected in other experiments. Tick-update activity is broker-specific; bid/ask is included, but commission and extra slippage are excluded.

Artifacts: `PROTOCOL.md`, `test_flat_poc.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, and `trades.csv`.
