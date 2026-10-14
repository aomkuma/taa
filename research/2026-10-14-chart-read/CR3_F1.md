# CR-3 for breakout F1: rules chosen on the first half, judged on the rest

Script: `cr3_features.py` (docs/CHART_READ.md §8 M1). Trades: the F1 backtests of 2025-10 .. 2026-09
(config `data/research/config_bo_f1.yaml`, 8 symbols). Features: the engine's own `MapBook` + `signal_features`
at each entry (H1, H4, D1 chart reads, MT5 ZigZag 12/5/3).

## Selection rule (written 2026-10-14 before the `choose` run)

On the choose set (entries before 2026-04-09, AUDUSD and XAUUSD left out) a candidate filter qualifies when:

1. it keeps at least 60 % of the trades (the portfolio's trade count is not cut without the owner's say);
2. the kept trades' mean beats the baseline mean by at least +0.05 R;
3. the removed trades' mean is below 0 R (the filter removes losers, not just noise).

At most three qualifying rules are taken, ranked by the kept trades' total R; when two rules are the same
filter on two timeframes, only the better one is kept. They are then judged once, unchanged, on the second
half (no hold-outs) and on the hold-out symbols (the whole year). A rule passes the judge when its kept mean
beats the baseline on both and the kept 90 % interval's lower bound is above 0 on the second half. Survivors
go to the backtest ladder (CR-6); nothing changes trading before that.

## Choose run (2026-10-14, about 18:30 Thai time)

99 F1 trades; choose set 38 trades, +0.112 R/trade (total +4.26 R). Rules with at least 23 kept trades:

| Rule | Kept | Kept R/trade | Kept CI90 | Removed |
|---|---|---|---|---|
| baseline | 38 | +0.112 | −0.046 .. +0.262 | - |
| h4_not_against | 23 | **+0.321** | +0.189 .. +0.446 | −0.208 (n 15) |
| h1_room_2 | 31 | **+0.178** | +0.003 .. +0.330 | −0.180 (n 7) |
| h1_room_1 / 1.5 | 32 | +0.142 | −0.029 .. +0.310 | −0.046 (n 6) |
| h1_not_against | 30 | +0.124 | −0.066 .. +0.296 | +0.067 (n 8) |
| h1_with | 25 | +0.058 | −0.158 .. +0.246 | +0.216 (n 13) |
| h1_skip_mixed / h1_surest_mixed | 33 | +0.060 | −0.122 .. +0.228 | +0.454 (n 5) |
| h4_skip_mixed / h4_surest_mixed | 30 | +0.021 | −0.173 .. +0.207 | +0.452 (n 8) |
| h4_room_1.5 / 2 | 34 | +0.106 | −0.065 .. +0.270 | +0.161 (n 4) |

Too few kept (under 23): h4_with 15 (+0.250), h1_at_level 2, h4_at_level 2 (the entry is almost never at a
read level: a fade enters at the break, away from the swings).

Mixed phases are F1's good trades in this half (removing them lowers the mean), so neither `skip` nor `surest`
qualifies.

## Chosen rules

Qualifying by the rule above: **h4_not_against** (`structure_tf: H4`, `structure_gate: not_against`) and
**h1_room_2** (`structure_tf: H1`, `room_min_r: 2`). Only two qualify. Caveat: `structure_gate` on H4 was
named a candidate in CHART_READ.md §2 from a full-year table, so the second half is not wholly unseen for that
one.

## Judge run

Run once with the two rules unchanged (2026-10-14, about 18:35 Thai time):

| Set | Trades | Baseline | h4_not_against (kept) | h1_room_2 (kept) | Both (kept) |
|---|---|---|---|---|---|
| choose: 1st half, no hold-outs | 38 | +0.112 | +0.321 (23) | +0.178 (31) | +0.378 (20) |
| 2nd half, no hold-outs | 32 | +0.074 | +0.133 (29), CI90 −0.056 .. +0.292 | +0.033 (25) | +0.106 (22) |
| hold-outs AUDUSD + XAUUSD, year | 29 | +0.313 | +0.290 (25) | +0.340 (24) | +0.332 (22) |

**Result: neither rule passes.** h4_not_against beats the baseline on the second half (it removes 3 trades
averaging −0.50 R) but not on the hold-outs (it removes 4 winners averaging +0.46 R), and its second-half
interval reaches below 0. h1_room_2 is worse than the baseline on the second half. So no chart-read rule goes
to the F1 ladder (CR-6) from this round, and F1 stays as it is (its year: 99 trades, +0.159 R/trade).

What the round shows about F1 (a fade of a break against both screens):
- its entries are almost never at a swing level (2 of 38), so `level_gate` cannot be used for it;
- its mixed-phase trades are among its better ones (the same as CHART_READ.md §2), so `mixed_rule` should stay
  `any` for F1;
- the H4 swing structure against the fade is the most consistent loser cell in the first half and the second
  half, but not on the hold-outs; with 3-15 trades per cell this stays a candidate, not a rule.

Same pattern as V1's h4_room_2 for F1's h4_not_against on the first two sets only (it fails on the hold-outs),
so it is weaker than V1's room rule.
