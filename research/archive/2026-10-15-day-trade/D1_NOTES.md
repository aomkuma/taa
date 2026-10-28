# Day trade D1 (owner, 2026-10-15): M1-M5 entries, 8 symbols, flat within the day

## Step 1: intraday behaviour (intraday_study.py, first half 2025-10 .. 2026-04-08)

- **Cost decides the symbols.** At the M1-M5 stop scale (1.5 × ATR(M5) or 1 × ATR(M15)) the spread alone costs
  0.11-0.30 R a trade on the seven FX pairs (NZDUSD 0.28-0.30, USDCAD 0.23, USDCHF 0.20, AUDUSD 0.19, EURUSD
  0.15, GBPUSD and USDJPY 0.11-0.12) and 0.025 R on XAUUSD. Every trigger and way is negative on the FX pairs
  pooled (−0.05 .. −0.26 R), the same finding as the M1 scalping study (only gold survives costs).
- **Gold, the first half:** following the break pays, fading it does not.

| XAUUSD, first half | Trades | RR 1.0 | RR 1.5 | RR 2.0 |
|---|---|---|---|---|
| ny_or_break follow, stop m15 | 129 | +0.070 | +0.143 | +0.199 |
| ny_or_break follow, stop m5 | 129 | +0.023 | +0.155 | +0.204 |
| pdhl_break follow, stop m15 | 97 | +0.093 | +0.082 | +0.113 |
| pdhl_break follow, stop m5 | 97 | +0.175 | +0.211 | +0.237 |
| asia_break (either way) | 70 | about 0 | | |

## Chosen on the first half (written before the second half was looked at, 2026-10-15 ~00:00 Thai time)

1. **D1-A:** XAUUSD, the NY opening range (13:30-14:00 UTC) broken by an M5 close 14:00-18:00 UTC, traded with
   the break, stop 1.5 × ATR(M5), target 2 R, flat at 20:45 UTC.
2. **D1-B:** XAUUSD, the previous UTC day's high/low broken by an M5 close 07:00-18:00 UTC, traded with the
   break, stop 1.5 × ATR(M5), target 2 R, flat at 20:45 UTC.

The H4 split is not used: its cells are 6-21 trades. Judged on the second half next; survivors go to code and
the backtest ladder.

## Judged on the second half (2026-04-09 .. 2026-09-30): both fail

| XAUUSD, follow, stop m5, RR 2 | 1st half | 2nd half |
|---|---|---|
| D1-A NY opening range | +0.204 (129), CI90 −0.003 .. +0.413 | **−0.082** (122), CI90 −0.284 .. +0.116 |
| D1-B previous day high/low | +0.237 (97), CI90 −0.010 .. +0.485 | **−0.275** (91), CI90 −0.494 .. −0.049 |

No phase explains the flip: by H4 ATR percentile (tertiles) the quiet/mid/high cells change sign between the
halves for both triggers, and the monthly means (about 20 trades a month) swing around zero (D1-A: +0.50 in
October 2025, −0.29 in September 2026; no run of losing months). A plain session break on M5 has no edge that
survives the walk-forward, before any context is added.

## Next (proposal to the owner)

The one intraday edge on gold that has held so far is S1 (M1 fades of counter-trend breaks inside an H1+M15
trend; 8 months +0.27 R/trade at the time of writing). Day trade D1 = that logic on M5 entries (context M30/H1/H4,
stop and target on the M5 scale), flat by 20:45 UTC, then the ladder; the session triggers only as context
(where the break happens), not as the signal.

## D1 = S1's logic on M5 (owner, 2026-10-15: "go on")

`data/research/config_d1a_m5.yaml` (screens H1/M15) and `config_d1b_m5.yaml` (H4/M30): S1's params with
`atr_bars: 12` (one hour of M5), flat within the day.

- **First March run invalid (00:43-00:52 Thai time, kept in `data/backtests/inv/d1_invalid/`):** the day cut
  `session_end_utc: 16:00` together with S1's `skip_window_ny: 08:00-12:00` (12:00-16:00 UTC in March after the
  US DST change) left entries only 07:00-12:00 UTC: 3 signals (S1 on M1 had 24 that month), 3 stop-outs. It
  tested the window mistake, not the idea, and is not counted.
- **Fixed:** `session_end_utc: 18:30` and a 24-bar (2-hour) time stop, so entries run 07:00-12:00 and
  16:00-18:30 UTC and every trade still closes by 20:30 UTC. March rerun for both variants.

## Second mistake found, then the results (2026-10-15, 02:20-03:18 Thai time)

- **The cooldown was not rescaled:** `strategies.cooldown_bars: 60` came from S1 (60 M1 bars = 1 hour) and meant
  5 hours on M5, so most re-entries were blocked (August D1d: 6 signals, 2 trades). Every bar-counted setting was
  then listed against S1; only the cooldown needed scaling (→ 12 bars). The runs with the 5-hour cooldown are kept
  in `data/backtests/inv/d1_invalid/*_cooldown5h` and not counted.

| Variant (XAUUSD M5, cooldown 1 h, flat by 20:30 UTC) | Screens | March | August |
|---|---|---|---|
| D1a | H1 / M15, map state | −0.736 (3 trades) | dropped |
| D1b | H4 / M30, map state | +0.480 (2) | **0 trades** (0 signals) |
| D1c | H1 / M15, swings | −0.596 (7) | dropped |
| D1d | H4 / M30, swings | +0.431 (2) | **−1.016** (3, all stopped) |

**Result: no D1 variant passes two rungs.** Counts stay at 0-7 trades a month: the fade needs a break against both
screens at once, which the M5 bars rarely give (H1 and M15 trend the same way on 6 % of March's M5 bars by the
map state, 17 % by the swings). S1's logic does not carry to M5 with S1's scale-free parameters.

Levers not tried yet: the stop/target scale on M5 (measure the fade's MFE/MAE first), the entry windows, trend
entries with the screens. Proposal to the owner instead: treat S1 (M1, year +0.277 R, 76 trades) as the
day-trade/scalping setup and work on its trade count.
