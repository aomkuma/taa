# POC migration retest continuation

## Hypothesis and rules
The earlier study used POC migration only to choose which VA edge to fade. This test uses migration as the directional signal and waits for price to retest the frozen six-hour POC. Define migration as recent-half three-hour POC minus older-half three-hour POC at the first qualifying six-hour cluster; require at least $0.50 displacement. If positive, wait for price above POC to touch/reach it and an M5 bar to close back above, then buy the first quote after the close; target frozen VAH and stop below the signal-bar low plus the spread pad. If negative, mirror below POC: retest and close below, short next quote to frozen VAL, stop beyond signal-bar high plus pad. Profile levels and migration direction are frozen at activation; only one trade per session. Execution uses FBS bid/ask ticks.

## Results

- 158 covered sessions: 110 development and 48 validation.
- 27 trades: 18 development and 9 validation.
- Development: **-16.09R**, 2/18 wins; folds: -3.26R (3), -9.77R (9), -3.07R (6).
- Validation: **-4.06R**, 3/9 wins.
- No candidate: sample is below the 20-development-trade minimum and all chronological folds/validation are negative.

## Interpretation and limits
A directional POC migration plus close-confirmed retest did not improve the profile approach on the available FBS sample. The very low counts make precise expectancy uncertain, but the consistent fold losses provide no positive evidence. The profile proxy and broker feed differ from the user's OANDA TradingView chart; extra slippage and commissions are excluded, and validation has been reused.

See the test script and generated trades, fold, selection, and profile audit CSVs.
