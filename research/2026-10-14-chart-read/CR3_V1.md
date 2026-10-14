# CR-3 for harmonic V1: rules chosen on the first half, judged on the rest

Script: `cr3_features.py v1` (docs/CHART_READ.md §8 M1). Trades: `data/backtests/inv/setup_harmonic_prz_v11y`
(181 trades, the year that made V1 pass, SETUP_REVIEW §15.3). Features: the engine's `MapBook` +
`signal_features` at each entry, context H1/H4/D1 (map parameters of `config.yaml`; the old research config
`config_h_v1.yaml` no longer loads).

## Selection rule

The same rule as CR3_F1.md, unchanged (written before the F1 choose run): on the choose set (before
2026-04-09, AUDUSD and XAUUSD left out) a filter keeps ≥ 60 % of the trades, its kept mean beats the baseline
by ≥ +0.05 R and its removed trades average below 0 R; at most three, ranked by kept total R, one per filter
family. Judged once on the second half (no hold-outs) and the hold-outs (year): the kept mean beats the
baseline on both and the second half's kept 90 % lower bound is above 0.

## Choose run (2026-10-14, about 18:45 Thai time)

181 trades; choose set 76, +0.175 R/trade (total +13.30 R). Needs ≥ 46 kept, kept mean ≥ +0.225 R.

| Rule | Kept | Kept R/trade | Kept CI90 | Removed | Qualifies |
|---|---|---|---|---|---|
| baseline | 76 | +0.175 | −0.085 .. +0.453 | - | |
| h4_not_against | 53 | **+0.353** | +0.019 .. +0.686 | −0.234 (23) | yes |
| h4_room_2 | 67 | **+0.243** | −0.040 .. +0.529 | −0.331 (9) | yes |
| h1_room_1.5 | 64 | +0.250 | −0.047 .. +0.555 | −0.224 (12) | yes (room family: h4_room_2 is better) |
| h1_room_2 | 61 | +0.254 | −0.049 .. +0.551 | −0.144 (15) | yes (room family) |
| h1_skip_mixed | 39 | +0.401 | +0.024 .. +0.788 | −0.063 (37) | no: keeps 51 % |
| h1_surest_mixed | 40 | +0.367 | +0.006 .. +0.734 | −0.038 (36) | no: keeps 53 % |
| h4_with | 17 | +0.622 | +0.030 .. +1.222 | +0.046 (59) | no: keeps 22 % |
| h1_not_against | 52 | −0.005 | −0.321 .. +0.315 | +0.564 (24) | no |
| h4_skip_mixed | 40 | +0.130 | | +0.225 (36) | no |
| h1/h4_at_level | 7 | | | | no: 7 trades |

## Chosen rules

**h4_not_against** (`structure_tf: H4`, `structure_gate: not_against`) and **h4_room_2** (`structure_tf: H4`,
`room_min_r: 2`).

## Judge run

Run once with the two rules unchanged (2026-10-14, about 18:50 Thai time):

| Set | Trades | Baseline | h4_not_against (kept) | h4_room_2 (kept) | Both (kept) |
|---|---|---|---|---|---|
| choose: 1st half, no hold-outs | 76 | +0.175 | +0.353 (53) | +0.243 (67) | +0.429 (46) |
| 2nd half, no hold-outs | 44 | +0.054 | **−0.204** (29) | +0.089 (38), CI90 −0.276 .. +0.470 | −0.139 (24) |
| hold-outs AUDUSD + XAUUSD, year | 61 | +0.369 | +0.239 (36) | +0.438 (58) | +0.349 (33) |

**Result: neither rule passes.**
- **h4_not_against flips:** in the second half the trades it removes are winners (+0.554 R, n 15), so it loses
  there; the same flip CHART_READ.md §2 showed for this cell. Rejected.
- **h4_room_2 points the same way on all three sets** (the removed trades average −0.331 R (9), −0.167 R (6),
  −0.966 R (3); 18 of 181 trades), but fails the pre-registered test that the second half's kept 90 % lower
  bound be above 0. That test cannot be met by a filter removing 6 of 44 trades: the second half's baseline
  itself spans −0.280 .. +0.407. Not adopted from this round; whether to put it through the backtest ladder
  is the owner's decision.
