# Stable-cluster target sensitivity

**Status:** preregistered before target counterfactual run
**Date:** 2026-10-31 (Asia/Bangkok)

## Question

The frozen-cluster rotation strategy was nearly flat in raw points but negative in validation risk units. Test only whether profit-taking at frozen POC or at the opposite frozen value-area edge changes the result.

## Fixed rules

- Same stable-cluster formation, frozen levels, VAL-long / VAH-short entries, wick-based stop, one-position rule, and tick replay as `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Compare only two target modes for rotation trades: (A) frozen POC, (B) opposite frozen VA edge (VAH for VAL long; VAL for VAH short).
- No breakout trades, no other parameter changes.
- Same 158 sessions, chronological 70/30 split, 3 development folds.
- A candidate must have at least 20 development trades, positive net R in at least 2/3 development folds, and positive validation net R; otherwise select none.

## Expectation before reveal

The opposite-edge target gives winners more room but should lower the win rate. I do not expect either target to solve the entry problem by itself.

## Limits

Same data-proxy and execution-cost limits as the underlying stable-cluster study. The validation period is historical and partially inspected in prior research.
