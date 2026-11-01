# Low-efficiency rotation gate result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before calculation.  
**Sample:** 158 sessions; 110 development / 48 validation.

| Rule | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz |
|---|---:|---:|---:|---:|---:|
| baseline | 44 | +2.37 | 29 | -2.90 | -26.75 |
| low_eff_025 | 42 | +2.60 | 29 | -2.88 | -25.31 |

The <=0.25 six-hour efficiency gate changed 2 development trades and no validation trades. Validation stayed -2.88R, and the candidate did not pass selection. The condition was not selective in this replay and did not solve regime sensitivity.

Selection is none. Activity counts and P&L use the FBS-Demo feed and exclude commission/extra slippage.
