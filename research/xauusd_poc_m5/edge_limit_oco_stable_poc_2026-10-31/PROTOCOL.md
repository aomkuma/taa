# OCO limits in a stationary value cluster

**Status:** corrected exploratory execution-audited filter; earlier premature-activation output is retained under `premature_activation_diagnostic/` and must not be used for inference.
**Date:** 2026-10-31 (Asia/Bangkok)

## Question and rule

Does stability in the two three-hour POCs identify a better VAL/VAH rotation cluster? A cluster only activates at the first M5 open where all conditions hold simultaneously: base six-hour profile qualifies, prior completed M5 close is inside that same profile's [VAL, VAH], six-hour price efficiency <=0.25, and older/recent-half POC centers differ by <=$0.50. Freeze levels at that activation. Only accept edge touches while the prior close remains within frozen VA and current rolling efficiency/POC-shift gates remain valid. One cluster/session, OCO, one fill/session, up to 72 profile bars, cancel after two consecutive closes outside the frozen VA.

Use corrected FBS M1 tick-volume price-row allocation profile, $0.10 bins, 70% value area and executable bid/ask ticks. Stops are 2 x six-hour median spread + $0.10 outside the frozen edge. A stop crossed on the entry quote is exited immediately. R is normalized to the stop distance from the planned limit price. Target is frozen POC. Same 158 sessions; chronological 110 development / 48 validation; three dev folds. Candidate: >=20 dev trades, positive net R in >=2 folds and positive validation net R.

## Audit note

The first implementation activated levels on the first base-profile qualification and then waited for the POC stability gate. The 72-bar expiry could elapse before that gate occurred, yielding only 1 development and 5 validation fills. That was an activation-timing error, not evidence. Those CSVs are preserved for traceability and superseded by this corrected run.

## Limits

FBS-Demo, not OANDA. M1 OHLC allocation approximates TradingView's profile. Validation is not an untouched holdout because related studies inspected it. Commission, queue position, latency, and additional slippage are excluded.
