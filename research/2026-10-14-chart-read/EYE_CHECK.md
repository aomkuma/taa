# Eye check: 20 charts the bot picked (TAA-L813 CR-4)

Drawn by `eye_check_sample.py` (seed 20261014): 8 symbols, M15/H1/H4, 7 groups, random bars of the year
within each group, never chosen by result. Each link opens the PWA chart as it was at that bar's close
with the bot's read drawn (`read=1`, `end=`). The check passes when the bot's trend and its two nearest
levels agree with the owner's reading on at least 16 of the 20 (docs/CHART_READ.md §8).

**How to check:** sign in to the DEMO PWA (http://localhost:8001) and open each link: the chart stops at
that bar, with the bot's swings (purple, HH/HL/LH/LL), levels (green support, red resistance, orange
flipped), trendlines and the pink dotted line where the trend's structure ends; the panel above the chart
states the bot's read in words. Read the chart yourself first, then compare. *Trend*: the same structure
(up, down, triangle, megaphone, flat). *Levels*: the bot's nearest support and resistance sit where you
would draw them. Mark ✓ or ✗ with a word in the last two columns; every ✗ becomes a test case.

| # | Symbol | TF | Bar close (Thai time) | Group | Bot's trend | Nearest support | Nearest resistance | Link | Owner: trend | Owner: levels |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | USDCAD | M15 | 2026-02-05 14:45 | UP | UP | 1.36285 (support) | 1.37024 (resistance) | [open](http://localhost:8001/charts?symbol=USDCAD&tf=M15&end=2026-02-05T07:45:00Z&read=1) | | |
| 2 | NZDUSD | H1 | 2026-04-07 18:00 | DOWN | DOWN | 0.56800 (support) | 0.57295 (resistance) | [open](http://localhost:8001/charts?symbol=NZDUSD&tf=H1&end=2026-04-07T11:00:00Z&read=1) | | |
| 3 | USDCHF | H4 | 2026-04-13 08:00 | CONTRACTING | CONTRACTING | 0.78552 (support) | 0.80182 (resistance) | [open](http://localhost:8001/charts?symbol=USDCHF&tf=H4&end=2026-04-13T01:00:00Z&read=1) | | |
| 4 | USDJPY | M15 | 2025-12-22 16:15 | BROADENING | BROADENING | 157.229 (support) | 157.769 (resistance) | [open](http://localhost:8001/charts?symbol=USDJPY&tf=M15&end=2025-12-22T09:15:00Z&read=1) | | |
| 5 | XAUUSD | H1 | 2026-04-30 01:00 | FLIPPED | DOWN | - | 4,554.89 (flipped) | [open](http://localhost:8001/charts?symbol=XAUUSD&tf=H1&end=2026-04-29T18:00:00Z&read=1) | | |
| 6 | GBPUSD | H4 | 2026-04-01 00:00 | SWEEP_RECLAIM | UP | - | 1.32185 (flipped) | [open](http://localhost:8001/charts?symbol=GBPUSD&tf=H4&end=2026-03-31T17:00:00Z&read=1) | | |
| 7 | AUDUSD | M15 | 2025-11-13 17:15 | BREAK_HOLD | UP | 0.65652 (flipped) | - | [open](http://localhost:8001/charts?symbol=AUDUSD&tf=M15&end=2025-11-13T10:15:00Z&read=1) | | |
| 8 | EURUSD | H1 | 2026-07-03 21:00 | UP | UP | 1.13739 (flipped) | 1.14726 (resistance) | [open](http://localhost:8001/charts?symbol=EURUSD&tf=H1&end=2026-07-03T14:00:00Z&read=1) | | |
| 9 | USDCAD | H4 | 2025-10-30 21:00 | DOWN | DOWN | 1.38930 (flipped) | 1.39721 (flipped) | [open](http://localhost:8001/charts?symbol=USDCAD&tf=H4&end=2025-10-30T14:00:00Z&read=1) | | |
| 10 | NZDUSD | M15 | 2026-08-24 06:15 | CONTRACTING | CONTRACTING | 0.59684 (support) | 0.59848 (resistance) | [open](http://localhost:8001/charts?symbol=NZDUSD&tf=M15&end=2026-08-23T23:15:00Z&read=1) | | |
| 11 | USDCHF | H1 | 2026-08-12 03:00 | BROADENING | BROADENING | 0.80601 (support) | 0.81301 (flipped) | [open](http://localhost:8001/charts?symbol=USDCHF&tf=H1&end=2026-08-11T20:00:00Z&read=1) | | |
| 12 | USDJPY | H4 | 2026-05-04 08:00 | FLIPPED | UP | 156.450 (support) | 157.390 (flipped) | [open](http://localhost:8001/charts?symbol=USDJPY&tf=H4&end=2026-05-04T01:00:00Z&read=1) | | |
| 13 | XAUUSD | M15 | 2026-08-12 16:45 | SWEEP_RECLAIM | UP | 4,383.89 (support) | 4,415.88 (resistance) | [open](http://localhost:8001/charts?symbol=XAUUSD&tf=M15&end=2026-08-12T09:45:00Z&read=1) | | |
| 14 | GBPUSD | H1 | 2026-08-14 21:00 | BREAK_HOLD | BROADENING | 1.35302 (flipped) | 1.35451 (resistance) | [open](http://localhost:8001/charts?symbol=GBPUSD&tf=H1&end=2026-08-14T14:00:00Z&read=1) | | |
| 15 | AUDUSD | H4 | 2026-08-26 20:00 | UP | UP | 0.71293 (flipped) | 0.71800 (resistance) | [open](http://localhost:8001/charts?symbol=AUDUSD&tf=H4&end=2026-08-26T13:00:00Z&read=1) | | |
| 16 | EURUSD | M15 | 2026-09-21 16:15 | DOWN | DOWN | 1.14789 (flipped) | 1.14856 (resistance) | [open](http://localhost:8001/charts?symbol=EURUSD&tf=M15&end=2026-09-21T09:15:00Z&read=1) | | |
| 17 | USDCAD | H1 | 2026-03-19 10:00 | CONTRACTING | CONTRACTING | 1.36877 (support) | 1.37414 (resistance) | [open](http://localhost:8001/charts?symbol=USDCAD&tf=H1&end=2026-03-19T03:00:00Z&read=1) | | |
| 18 | NZDUSD | H4 | 2026-06-15 08:00 | BROADENING | BROADENING | 0.57693 (support) | 0.59925 (resistance) | [open](http://localhost:8001/charts?symbol=NZDUSD&tf=H4&end=2026-06-15T01:00:00Z&read=1) | | |
| 19 | USDCHF | M15 | 2026-06-11 02:45 | FLIPPED | BROADENING | 0.79953 (flipped) | - | [open](http://localhost:8001/charts?symbol=USDCHF&tf=M15&end=2026-06-10T19:45:00Z&read=1) | | |
| 20 | USDJPY | H1 | 2026-04-29 19:00 | SWEEP_RECLAIM | DOWN | 158.959 (support) | 159.851 (resistance) | [open](http://localhost:8001/charts?symbol=USDJPY&tf=H1&end=2026-04-29T12:00:00Z&read=1) | | |
