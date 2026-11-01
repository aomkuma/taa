# Regime filter comparison

**Run date:** 2026-10-31 (Asia/Bangkok)
**Frozen plan:** `PROTOCOL.md`; compared on the same 158 fully covered sessions as the rolling six-hour baseline.

## Results

| Rule | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz | All points/oz |
|---|---:|---:|---:|---:|---:|---:|
| Rolling 6h baseline | 220 | -72.12 | 96 | -4.38 | +7.52 | -364.17 |
| Fade only if older/recent 3h price ranges overlap | 218 | -64.09 | 96 | -26.01 | -65.89 | -332.13 |
| Trade only in direction of 6h drift (efficiency ?0.35) | 0 | 0 | 0 | 0 | 0 | 0 |
| Cluster fade or trend pullback | 218 | -64.09 | 96 | -26.01 | -65.89 | -332.13 |

No rule passed the preregistered selection rule. The 3h range-overlap condition did not reduce trade count materially because later signals in a session continued to qualify. The drift-aligned entry rule produced no eligible setups. The combined rule therefore behaved like cluster fade and also lost in validation.

## Reading

The tested range overlap is too permissive as a cluster detector, while the drift-strength threshold was too restrictive for edge entries. The baseline results now match the earlier six-hour run after excluding bars that touched both edges simultaneously. Nothing in this comparison supports choosing a winner.

The next hypothesis freezes the cluster levels after stable balance forms and explicitly switches to a breakout retest when two closes accept outside the frozen edge. It is written as a separate, preregistered experiment.

Data limitations: FBS-Demo quote updates are a broker activity proxy, not centralized volume; spread is reflected in bid/ask fills but commission and extra slippage are excluded. Some dates were inspected in prior baseline analyses.
