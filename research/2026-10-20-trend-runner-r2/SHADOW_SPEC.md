# TR2 forward shadow specification

Status: specification only. It does not place orders, modify configuration or connect to DEMO/LIVE.

## Collection boundary

- Earliest collection time: 2026-10-21 00:00 UTC, after the TR2 rules were frozen and measured.
- Never backfill the locked 2026-04-18 through 2026-10-17 historical exam into this study.
- Continue until both 60 new XAUUSD trading days and 100 new frozen TR1 opportunities are present.
- Evaluation happens once at that boundary. No threshold, feature, target clip, alpha or window adjustment during
  collection. Changes require a named new round and restart the forward clock.

## Input record at entry

Each shadow row must contain a unique trade key, UTC entry/anchor time, session, side, entry, initial stop/risk,
pullback ratio, and these entry-time features:

`h1_flow_6_atr`, `h4_flow_3_atr`, `open_space_atr`, `h1_atr_percentile_120`, `risk_h1_feature`,
`pullback_ratio_feature`, `anchor_entry_minutes`, `side_feature`, `session_asia`, `session_london`, and
`prior_session_runner_edge`.

Also record the model refit month, training start/end, eligible training count, training-input hash, FAST/RUNNER
predictions, action, reason, and code/rule hash. The row becomes immutable at entry.

## Causal operation

- Build H1/H4 only from clock-complete bars with `available_at <= entry_time`.
- Same-session history includes only outcomes fully completed before entry.
- Refit on the first UTC calendar day of a month from the preceding 90 calendar days, requiring 60 completed rows.
- Keep preprocessing and coefficients fixed inside the month.
- Apply the frozen -0.05 skip threshold and +0.05 runner margin.
- Record hypothetical FAST and RUNNER outcomes independently after they complete; do not use them to revise an
  already-recorded decision.

## One-time forward decision

Report the same primary/baseline metrics and readiness gates as `HYPOTHESIS.md`. In addition, require no causal or
hash violation and reconcile risk-normalized R with the intended position-sizing policy. Passing is evidence for a
later integration review, not automatic permission to trade.
