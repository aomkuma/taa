# POC retest continuation test

## Hypothesis and rules
A stable six-hour profile POC may act as an intraday pivot. In a negative six-hour M5 close drift, after price is below the frozen POC, wait for an M5 bar to touch/reach above POC and close back below, then short at the first quote after the bar closes. Target frozen VAL; stop beyond the signal bar high plus the six-hour spread-based pad. Mirror for longs in a positive drift: price above POC, M5 low reaches POC and closes back above, enter next quote, target frozen VAH, stop below signal low plus pad. Use the same first qualifying six-hour profile per session, >=50% older/recent half-VA overlap and M5 coverage constraints; levels are frozen at cluster activation. Invalidate after two consecutive M5 closes outside the frozen value area or after 72 profile bars. One trade per session. FBS bid/ask ticks determine fills and exits.

## Results

- 158 covered sessions: 110 development and 48 validation.
- 32 trades: 19 development and 13 validation.
- Development: **-14.65R**, 3/19 wins; chronological folds: -3.15R (3 trades), -9.74R (9), -1.76R (7). No positive folds.
- Validation: **-3.07R**, 5/13 wins.
- No candidate. Development count is below 20 and both chronological blocks are negative.

## Interpretation and limits
Using POC as a trend-aligned retest pivot instead of fading the VA edges did not help under this entry, stop and target combination. The low trade count makes the exact loss estimate noisy, but all development folds are negative. This is a separate FBS feed study; it cannot reproduce the OANDA profile from the chart. Commission and slippage beyond quoted spread are omitted, and prior validation has been viewed repeatedly.

Artifacts: `test_poc_retest.py`, `trades.csv`, `summary.csv`, `development_folds.csv`, `selection.csv`, and profile/session audits.
