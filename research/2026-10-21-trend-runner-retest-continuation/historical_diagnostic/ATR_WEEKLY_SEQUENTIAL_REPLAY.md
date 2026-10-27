# ATR-adaptive strategy — week-by-week historical replay

This is a chronological research journal, not live trading. Each event's ATR state is computed from completed M15/M30/H1 bars available at its decision time. The adaptive decision uses only prior allowed trades whose outcomes had already settled. A blocked trade's counterfactual result is recorded for evaluation but never updates the policy.
The three policy paths are distinct: the trailing learner and source-stop screen below evaluate ATR at the original source stop; the frozen entry-time lock was tested separately on 2021-09..2023-10 and is summarized in `historical_holdout_2021_2023/HOLDOUT_RESULTS.md`.

R values are candidate trade outcomes, not account equity. Weeks are UTC Monday-start; only weeks containing source events are listed. The locked exam period is excluded.

## Weekly replay

### Week of 2023-10-30 UTC

Events: 2; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +0.000R; trailing adaptive +0.000R; source-stop screen +0.000R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-11-01 07:07 | BUY / LONDON | NORMAL_OR_LOW (0.22/0.17/0.25; 0.22) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-11-03 00:28 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.04/0.28; 0.04) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2023-11-06 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +0.000R; trailing adaptive +0.000R; source-stop screen +0.000R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-11-06 06:50 | BUY / LONDON | NORMAL_OR_LOW (0.54/0.49/0.53; 0.53) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-11-07 00:27 | SELL / ASIA | NORMAL_OR_LOW (0.12/0.10/0.15; 0.12) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2023-11-08 06:56 | BUY / LONDON | NORMAL_OR_LOW (0.06/0.14/0.09; 0.09) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2023-11-10 01:29 | BUY / ASIA | NORMAL_OR_LOW (0.13/0.65/0.85; 0.65) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2023-11-13 UTC

Events: 5; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -0.604R; trailing adaptive -0.604R; source-stop ATR-state screen -0.604R (blocked +0.000R). Cumulative: frozen -0.604R; trailing adaptive -0.604R; source-stop screen -0.604R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-11-14 06:39 | BUY / LONDON | NORMAL_OR_LOW (0.07/0.06/0.19; 0.07) | 0; mean — | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2023-11-15 01:14 | BUY / ASIA | NORMAL_OR_LOW (0.04/0.08/0.93; 0.08) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | +0.396R |
| 2023-11-16 01:24 | SELL / ASIA | NORMAL_OR_LOW (0.13/0.17/0.62; 0.17) | 2; mean -0.302R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-11-17 01:16 | BUY / ASIA | NORMAL_OR_LOW (0.11/0.20/0.60; 0.20) | 2; mean -0.302R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-11-17 06:48 | SELL / LONDON | NORMAL_OR_LOW (0.11/0.21/0.26; 0.21) | 2; mean -0.302R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -0.604R.

### Week of 2023-11-20 UTC

Events: 7; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -1.760R; trailing adaptive -1.760R; source-stop ATR-state screen -1.760R (blocked +0.000R). Cumulative: frozen -2.364R; trailing adaptive -2.364R; source-stop screen -2.364R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-11-20 07:07 | SELL / LONDON | NORMAL_OR_LOW (0.64/0.69/0.44; 0.64) | 2; mean -0.302R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2023-11-21 06:28 | SELL / LONDON | NORMAL_OR_LOW (0.53/0.68/0.44; 0.53) | 2; mean -0.302R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-11-22 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.28/0.83; 0.28) | 2; mean -0.302R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2023-11-23 07:42 | BUY / LONDON | NORMAL_OR_LOW (0.38/0.33/0.18; 0.33) | 3; mean -0.535R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2023-11-23 15:31 | BUY / NY0830 | NORMAL_OR_LOW (0.11/0.04/0.08; 0.08) | 3; mean -0.535R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2023-11-24 00:32 | SELL / ASIA | NORMAL_OR_LOW (0.07/0.03/0.01; 0.03) | 3; mean -0.535R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | -0.760R |
| 2023-11-24 06:39 | SELL / LONDON | NORMAL_OR_LOW (0.20/0.10/0.02; 0.10) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -1.760R.

### Week of 2023-11-27 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -2.364R; trailing adaptive -2.364R; source-stop screen -2.364R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-11-27 00:47 | BUY / ASIA | NORMAL_OR_LOW (0.40/0.64/0.29; 0.40) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-11-28 07:18 | BUY / LONDON | NORMAL_OR_LOW (0.14/0.37/0.17; 0.17) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-11-30 01:03 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.22/0.56; 0.22) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-01 00:49 | BUY / ASIA | NORMAL_OR_LOW (0.19/0.40/0.68; 0.40) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-01 14:10 | SELL / NY0830 | NORMAL_OR_LOW (0.79/0.75/0.47; 0.75) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2023-12-04 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -2.364R; trailing adaptive -2.364R; source-stop screen -2.364R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-12-05 01:18 | BUY / ASIA | NORMAL_OR_LOW (0.67/0.65/0.81; 0.67) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-05 06:28 | BUY / LONDON | NORMAL_OR_LOW (0.55/0.60/0.76; 0.60) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-12-06 00:31 | BUY / ASIA | NORMAL_OR_LOW (0.04/0.20/0.65; 0.20) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-07 01:08 | BUY / ASIA | NORMAL_OR_LOW (0.06/0.15/0.40; 0.15) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-12-07 06:34 | BUY / LONDON | NORMAL_OR_LOW (0.12/0.13/0.15; 0.13) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2023-12-11 UTC

Events: 4; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +2.349R; trailing adaptive +2.349R; source-stop ATR-state screen +2.349R (blocked +0.000R). Cumulative: frozen -0.015R; trailing adaptive -0.015R; source-stop screen -0.015R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-12-11 13:57 | SELL / NY0830 | NORMAL_OR_LOW (0.45/0.46/0.23; 0.45) | 4; mean -0.591R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | +2.349R |
| 2023-12-12 08:01 | BUY / LONDON | NORMAL_OR_LOW (0.17/0.01/0.11; 0.11) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2023-12-13 00:19 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.02/0.29; 0.02) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-12-14 01:51 | SELL / ASIA | HIGH (0.88/1.00/1.00; 1.00) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +2.349R.

### Week of 2023-12-18 UTC

Events: 7; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -0.791R; trailing adaptive +0.000R; source-stop ATR-state screen -0.791R (blocked +0.000R). Cumulative: frozen -0.806R; trailing adaptive -0.015R; source-stop screen -0.806R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-12-18 00:52 | BUY / ASIA | NORMAL_OR_LOW (0.39/0.63/0.68; 0.63) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-18 06:16 | SELL / LONDON | NORMAL_OR_LOW (0.08/0.34/0.42; 0.34) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-18 14:31 | SELL / NY0830 | NORMAL_OR_LOW (0.40/0.52/0.23; 0.40) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2023-12-19 07:45 | BUY / LONDON | NORMAL_OR_LOW (0.23/0.16/0.23; 0.23) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.791R (blocked counterfactual) |
| 2023-12-20 00:23 | SELL / ASIA | NORMAL_OR_LOW (0.07/0.22/0.36; 0.22) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-12-21 06:29 | SELL / LONDON | NORMAL_OR_LOW (0.11/0.10/0.17; 0.11) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2023-12-22 01:32 | SELL / ASIA | NORMAL_OR_LOW (0.77/0.65/0.88; 0.77) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.791R.

### Week of 2023-12-25 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -0.806R; trailing adaptive -0.015R; source-stop screen -0.806R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2023-12-26 07:03 | BUY / LONDON | NORMAL_OR_LOW (0.06/0.24/0.37; 0.24) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2023-12-27 00:18 | SELL / ASIA | NORMAL_OR_LOW (0.50/0.37/0.32; 0.37) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2023-12-27 06:38 | BUY / LONDON | NORMAL_OR_LOW (0.08/0.10/0.18; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2023-12-28 06:36 | SELL / LONDON | NORMAL_OR_LOW (0.26/0.47/0.60; 0.47) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2023-12-29 13:41 | SELL / NY0830 | NORMAL_OR_LOW (0.69/0.58/0.19; 0.58) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-01-01 UTC

Events: 2; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -0.806R; trailing adaptive -0.015R; source-stop screen -0.806R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-01-02 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.38/0.53/0.62; 0.53) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-02 14:56 | BUY / NY0830 | NORMAL_OR_LOW (0.97/0.79/0.68; 0.79) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-01-08 UTC

Events: 4; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -0.806R; trailing adaptive -0.015R; source-stop screen -0.806R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-01-08 01:02 | BUY / ASIA | NORMAL_OR_LOW (0.09/0.37/0.93; 0.37) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-01-08 14:30 | SELL / NY0830 | HIGH (0.88/0.80/0.69; 0.80) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2024-01-10 07:03 | SELL / LONDON | NORMAL_OR_LOW (0.42/0.33/0.14; 0.33) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-01-11 06:40 | BUY / LONDON | NORMAL_OR_LOW (0.23/0.14/0.10; 0.14) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-01-15 UTC

Events: 4; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -0.348R; trailing adaptive +0.000R; source-stop ATR-state screen -0.348R (blocked +0.000R). Cumulative: frozen -1.154R; trailing adaptive -0.015R; source-stop screen -1.154R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-01-15 14:28 | BUY / NY0830 | NORMAL_OR_LOW (0.10/0.32/0.09; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-01-17 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.12/0.62/0.76; 0.62) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.348R (blocked counterfactual) |
| 2024-01-18 14:01 | SELL / NY0830 | NORMAL_OR_LOW (0.73/0.62/0.34; 0.62) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-01-19 00:13 | SELL / ASIA | NORMAL_OR_LOW (0.10/0.40/0.36; 0.36) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.348R.

### Week of 2024-01-22 UTC

Events: 6; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -1.154R; trailing adaptive -0.015R; source-stop screen -1.154R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-01-22 07:05 | SELL / LONDON | NORMAL_OR_LOW (0.60/0.55/0.26; 0.55) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-22 13:56 | SELL / NY0830 | NORMAL_OR_LOW (0.69/0.81/0.48; 0.69) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-01-23 07:31 | SELL / LONDON | NORMAL_OR_LOW (0.72/0.58/0.19; 0.58) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-25 01:08 | SELL / ASIA | NORMAL_OR_LOW (0.19/0.42/0.83; 0.42) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-25 07:14 | SELL / LONDON | NORMAL_OR_LOW (0.03/0.00/0.05; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-26 06:18 | SELL / LONDON | NORMAL_OR_LOW (0.04/0.10/0.30; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-01-29 UTC

Events: 7; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -1.154R; trailing adaptive -0.015R; source-stop screen -1.154R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-01-29 00:41 | SELL / ASIA | NORMAL_OR_LOW (0.67/0.46/0.55; 0.55) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-01-30 01:06 | BUY / ASIA | NORMAL_OR_LOW (0.28/0.50/0.92; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-30 06:36 | BUY / LONDON | NORMAL_OR_LOW (0.09/0.12/0.31; 0.12) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-31 00:31 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.04/0.71; 0.04) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-01-31 06:56 | SELL / LONDON | NORMAL_OR_LOW (0.01/0.03/0.34; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-02-01 00:50 | BUY / ASIA | HIGH (0.76/0.95/0.99; 0.95) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2024-02-01 07:18 | SELL / LONDON | NORMAL_OR_LOW (0.17/0.34/0.78; 0.34) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-02-05 UTC

Events: 4; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -0.261R; trailing adaptive +0.000R; source-stop ATR-state screen -0.261R (blocked +0.000R). Cumulative: frozen -1.415R; trailing adaptive -0.015R; source-stop screen -1.415R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-02-08 00:40 | BUY / ASIA | NORMAL_OR_LOW (0.07/0.13/0.27; 0.13) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-02-08 06:22 | SELL / LONDON | NORMAL_OR_LOW (0.23/0.12/0.17; 0.17) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.261R (blocked counterfactual) |
| 2024-02-09 01:01 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.10/0.65; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-02-09 07:13 | BUY / LONDON | NORMAL_OR_LOW (0.12/0.08/0.03; 0.08) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.261R.

### Week of 2024-02-12 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -1.415R; trailing adaptive -0.015R; source-stop screen -1.415R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-02-14 01:04 | BUY / ASIA | NORMAL_OR_LOW (0.20/0.44/0.98; 0.44) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-02-15 06:28 | BUY / LONDON | NORMAL_OR_LOW (0.10/0.07/0.33; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-02-16 06:32 | SELL / LONDON | NORMAL_OR_LOW (0.05/0.08/0.25; 0.08) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_EXIT_HORIZON |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-02-19 UTC

Events: 8; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +0.858R; trailing adaptive +0.000R; source-stop ATR-state screen +0.858R (blocked +0.000R). Cumulative: frozen -0.557R; trailing adaptive -0.015R; source-stop screen -0.557R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-02-19 07:33 | BUY / LONDON | NORMAL_OR_LOW (0.37/0.55/0.64; 0.55) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-02-19 14:24 | SELL / NY0830 | NORMAL_OR_LOW (0.48/0.39/0.36; 0.39) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-02-20 00:30 | SELL / ASIA | NORMAL_OR_LOW (0.11/0.17/0.14; 0.14) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-02-21 00:29 | SELL / ASIA | NORMAL_OR_LOW (0.12/0.23/0.38; 0.23) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-02-21 06:30 | SELL / LONDON | NORMAL_OR_LOW (0.35/0.36/0.23; 0.35) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-02-22 06:41 | BUY / LONDON | NORMAL_OR_LOW (0.20/0.24/0.53; 0.24) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.858R (blocked counterfactual) |
| 2024-02-22 14:22 | SELL / NY0830 | NORMAL_OR_LOW (0.83/0.78/0.49; 0.78) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-02-23 00:36 | BUY / ASIA | NORMAL_OR_LOW (0.11/0.49/0.69; 0.49) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.858R.

### Week of 2024-02-26 UTC

Events: 4; high-ATR: 0; completed candidate trades: 3; allowed: 0; blocked completed: 3.
This week: frozen -0.854R; trailing adaptive +0.000R; source-stop ATR-state screen -0.854R (blocked +0.000R). Cumulative: frozen -1.411R; trailing adaptive -0.015R; source-stop screen -1.411R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-02-27 06:43 | BUY / LONDON | NORMAL_OR_LOW (0.00/0.02/0.02; 0.02) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.613R (blocked counterfactual) |
| 2024-02-28 15:24 | SELL / NY0830 | NORMAL_OR_LOW (0.86/0.68/0.62; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-02-29 00:31 | BUY / ASIA | NORMAL_OR_LOW (0.03/0.05/0.59; 0.05) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.467R (blocked counterfactual) |
| 2024-03-01 00:52 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.23/0.91; 0.23) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 3 trades, -0.854R.

### Week of 2024-03-04 UTC

Events: 2; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -1.411R; trailing adaptive -0.015R; source-stop screen -1.411R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-03-05 06:58 | SELL / LONDON | NORMAL_OR_LOW (0.69/0.62/0.78; 0.69) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-03-07 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.52/0.72/0.93; 0.72) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-03-11 UTC

Events: 7; high-ATR: 0; completed candidate trades: 3; allowed: 0; blocked completed: 3.
This week: frozen -1.536R; trailing adaptive +0.000R; source-stop ATR-state screen -1.536R (blocked +0.000R). Cumulative: frozen -2.947R; trailing adaptive -0.015R; source-stop screen -2.947R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-03-11 02:06 | SELL / ASIA | NORMAL_OR_LOW (0.68/0.54/1.00; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.063R (blocked counterfactual) |
| 2024-03-11 07:34 | BUY / LONDON | NORMAL_OR_LOW (0.29/0.36/0.66; 0.36) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.720R (blocked counterfactual) |
| 2024-03-12 06:58 | SELL / LONDON | NORMAL_OR_LOW (0.20/0.15/0.09; 0.15) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-13 01:28 | BUY / ASIA | NORMAL_OR_LOW (0.42/0.50/0.92; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-03-14 00:46 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.18/0.23; 0.18) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-03-14 06:25 | BUY / LONDON | NORMAL_OR_LOW (0.06/0.02/0.06; 0.06) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-15 06:46 | SELL / LONDON | NORMAL_OR_LOW (0.23/0.17/0.12; 0.17) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.879R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 3 trades, -1.536R.

### Week of 2024-03-18 UTC

Events: 9; high-ATR: 2; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +6.178R; trailing adaptive +0.000R; source-stop ATR-state screen +6.178R (blocked +0.000R). Cumulative: frozen +3.231R; trailing adaptive -0.015R; source-stop screen +3.231R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-03-18 00:20 | SELL / ASIA | NORMAL_OR_LOW (0.27/0.40/0.64; 0.40) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-18 07:02 | BUY / LONDON | NORMAL_OR_LOW (0.18/0.37/0.23; 0.23) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +6.178R (blocked counterfactual) |
| 2024-03-19 01:17 | SELL / ASIA | NORMAL_OR_LOW (0.04/0.03/0.16; 0.04) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-19 06:44 | SELL / LONDON | NORMAL_OR_LOW (0.43/0.21/0.04; 0.21) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-20 00:48 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.03/0.40; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-03-20 07:46 | BUY / LONDON | NORMAL_OR_LOW (0.19/0.15/0.00; 0.15) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-21 00:12 | SELL / ASIA | HIGH (0.99/1.00/1.00; 1.00) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2024-03-21 12:52 | SELL / NY0830 | HIGH (0.75/0.82/0.89; 0.82) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_CONTINUATION |
| 2024-03-22 13:01 | BUY / NY0830 | NORMAL_OR_LOW (0.59/0.76/0.71; 0.71) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +6.178R.

### Week of 2024-03-25 UTC

Events: 8; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.231R; trailing adaptive -0.015R; source-stop screen +3.231R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-03-25 00:36 | SELL / ASIA | NORMAL_OR_LOW (0.39/0.51/0.65; 0.51) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-03-25 13:32 | SELL / NY0830 | NORMAL_OR_LOW (0.50/0.49/0.57; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-26 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.11/0.09/0.20; 0.11) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-03-27 00:47 | SELL / ASIA | NORMAL_OR_LOW (0.14/0.12/0.72; 0.14) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-03-27 06:57 | BUY / LONDON | NORMAL_OR_LOW (0.25/0.31/0.23; 0.25) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-03-27 14:11 | BUY / NY0830 | HIGH (0.85/0.83/0.63; 0.83) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2024-03-28 00:23 | SELL / ASIA | NORMAL_OR_LOW (0.20/0.10/0.53; 0.20) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-03-28 06:22 | SELL / LONDON | NORMAL_OR_LOW (0.26/0.22/0.12; 0.22) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-04-01 UTC

Events: 7; high-ATR: 1; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +1.012R; trailing adaptive +0.000R; source-stop ATR-state screen +1.012R (blocked +0.000R). Cumulative: frozen +4.244R; trailing adaptive -0.015R; source-stop screen +4.244R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-04-01 12:52 | BUY / NY0830 | HIGH (0.82/0.70/0.85; 0.82) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2024-04-02 00:55 | BUY / ASIA | NORMAL_OR_LOW (0.50/0.53/0.85; 0.53) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-02 06:35 | BUY / LONDON | NORMAL_OR_LOW (0.38/0.46/0.48; 0.46) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-04 00:32 | BUY / ASIA | NORMAL_OR_LOW (0.21/0.22/0.45; 0.22) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-04-04 07:05 | BUY / LONDON | NORMAL_OR_LOW (0.03/0.17/0.15; 0.15) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-04 13:15 | BUY / NY0830 | NORMAL_OR_LOW (0.54/0.30/0.13; 0.30) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-05 00:51 | SELL / ASIA | NORMAL_OR_LOW (0.23/0.80/0.68; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +1.012R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +1.012R.

### Week of 2024-04-08 UTC

Events: 4; high-ATR: 1; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -0.013R; trailing adaptive +0.000R; source-stop ATR-state screen -0.013R (blocked +0.000R). Cumulative: frozen +4.231R; trailing adaptive -0.015R; source-stop screen +4.231R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-04-08 00:27 | SELL / ASIA | HIGH (0.82/0.65/1.00; 0.82) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2024-04-08 13:13 | BUY / NY0830 | NORMAL_OR_LOW (0.78/0.59/0.88; 0.78) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-09 00:25 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.03/0.28; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-04-10 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.13/0.64; 0.13) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.013R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.013R.

### Week of 2024-04-15 UTC

Events: 5; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -0.787R; trailing adaptive +0.000R; source-stop ATR-state screen -0.787R (blocked +0.000R). Cumulative: frozen +3.444R; trailing adaptive -0.015R; source-stop screen +3.444R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-04-15 13:28 | SELL / NY0830 | NORMAL_OR_LOW (0.63/0.52/0.53; 0.53) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-16 00:53 | BUY / ASIA | NORMAL_OR_LOW (0.31/0.73/0.84; 0.73) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.787R (blocked counterfactual) |
| 2024-04-17 06:25 | SELL / LONDON | NORMAL_OR_LOW (0.04/0.05/0.30; 0.05) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-04-18 07:09 | BUY / LONDON | NORMAL_OR_LOW (0.03/0.03/0.22; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-19 00:46 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.10/0.17; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.787R.

### Week of 2024-04-22 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.444R; trailing adaptive -0.015R; source-stop screen +3.444R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-04-22 00:19 | SELL / ASIA | NORMAL_OR_LOW (0.20/0.23/0.28; 0.23) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-04-23 06:56 | SELL / LONDON | NORMAL_OR_LOW (0.60/0.93/0.57; 0.60) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-04-25 07:08 | BUY / LONDON | NORMAL_OR_LOW (0.18/0.28/0.07; 0.18) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-04-29 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +0.125R; trailing adaptive +0.000R; source-stop ATR-state screen +0.125R (blocked +0.000R). Cumulative: frozen +3.569R; trailing adaptive -0.015R; source-stop screen +3.569R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-04-29 06:25 | BUY / LONDON | NORMAL_OR_LOW (0.39/0.47/0.19; 0.39) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.125R (blocked counterfactual) |
| 2024-04-29 12:48 | SELL / NY0830 | NORMAL_OR_LOW (0.41/0.30/0.28; 0.30) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-04-30 06:15 | SELL / LONDON | NORMAL_OR_LOW (0.16/0.06/0.07; 0.07) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-05-01 06:37 | BUY / LONDON | NORMAL_OR_LOW (0.16/0.16/0.23; 0.16) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-05-02 06:42 | BUY / LONDON | NORMAL_OR_LOW (0.22/0.18/0.91; 0.22) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-05-03 01:59 | SELL / ASIA | NORMAL_OR_LOW (0.07/0.18/0.53; 0.18) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.125R.

### Week of 2024-05-06 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.569R; trailing adaptive -0.015R; source-stop screen +3.569R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-05-07 01:06 | BUY / ASIA | NORMAL_OR_LOW (0.05/0.10/0.42; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-05-07 06:14 | SELL / LONDON | NORMAL_OR_LOW (0.07/0.18/0.07; 0.07) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-05-08 12:46 | SELL / NY0830 | NORMAL_OR_LOW (0.60/0.50/0.25; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-05-13 UTC

Events: 2; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.569R; trailing adaptive -0.015R; source-stop screen +3.569R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-05-13 13:08 | BUY / NY0830 | NORMAL_OR_LOW (0.79/0.70/0.38; 0.70) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-05-14 01:01 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.00/0.25; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-05-20 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.569R; trailing adaptive -0.015R; source-stop screen +3.569R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-05-20 00:21 | SELL / ASIA | NORMAL_OR_LOW (0.77/0.71/0.89; 0.77) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-05-21 01:08 | BUY / ASIA | NORMAL_OR_LOW (0.40/0.55/0.72; 0.55) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-05-21 14:16 | BUY / NY0830 | NORMAL_OR_LOW (0.74/0.68/0.68; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-05-22 06:38 | SELL / LONDON | NORMAL_OR_LOW (0.42/0.40/0.24; 0.40) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-05-24 00:51 | SELL / ASIA | NORMAL_OR_LOW (0.12/0.20/0.60; 0.20) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-05-27 UTC

Events: 3; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -0.660R; trailing adaptive +0.000R; source-stop ATR-state screen -0.660R (blocked +0.000R). Cumulative: frozen +2.909R; trailing adaptive -0.015R; source-stop screen +2.909R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-05-29 00:49 | SELL / ASIA | NORMAL_OR_LOW (0.05/0.11/0.54; 0.11) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.660R (blocked counterfactual) |
| 2024-05-29 06:10 | SELL / LONDON | NORMAL_OR_LOW (0.26/0.16/0.24; 0.24) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-05-31 01:03 | BUY / ASIA | NORMAL_OR_LOW (0.07/0.01/0.59; 0.07) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.660R.

### Week of 2024-06-03 UTC

Events: 5; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +1.449R; trailing adaptive +0.000R; source-stop ATR-state screen +1.449R (blocked +0.000R). Cumulative: frozen +4.358R; trailing adaptive -0.015R; source-stop screen +4.358R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-06-03 06:43 | SELL / LONDON | NORMAL_OR_LOW (0.77/0.57/0.59; 0.59) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-06-03 13:06 | BUY / NY0830 | NORMAL_OR_LOW (0.63/0.69/0.49; 0.63) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-06-04 06:25 | BUY / LONDON | NORMAL_OR_LOW (0.14/0.10/0.23; 0.14) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-06-07 01:08 | BUY / ASIA | NORMAL_OR_LOW (0.06/0.08/0.38; 0.08) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +1.449R (blocked counterfactual) |
| 2024-06-07 07:54 | SELL / LONDON | NORMAL_OR_LOW (0.81/0.77/0.40; 0.77) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +1.449R.

### Week of 2024-06-10 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +4.358R; trailing adaptive -0.015R; source-stop screen +4.358R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-06-10 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.49/0.69/0.93; 0.69) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-06-12 01:35 | SELL / ASIA | NORMAL_OR_LOW (0.13/0.07/0.18; 0.13) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-06-13 06:13 | BUY / LONDON | NORMAL_OR_LOW (0.42/0.49/0.68; 0.49) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-06-14 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.02/0.00/0.68; 0.02) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-06-17 UTC

Events: 8; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +0.265R; trailing adaptive +0.000R; source-stop ATR-state screen +0.265R (blocked +0.000R). Cumulative: frozen +4.623R; trailing adaptive -0.015R; source-stop screen +4.623R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-06-17 00:10 | SELL / ASIA | NORMAL_OR_LOW (0.08/0.18/0.57; 0.18) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-06-17 07:49 | SELL / LONDON | NORMAL_OR_LOW (0.52/0.29/0.15; 0.29) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-06-17 16:01 | SELL / NY0830 | NORMAL_OR_LOW (0.85/0.73/0.52; 0.73) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-06-18 01:16 | BUY / ASIA | NORMAL_OR_LOW (0.12/0.07/0.39; 0.12) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-06-19 01:08 | BUY / ASIA | NORMAL_OR_LOW (0.04/0.04/0.49; 0.04) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-06-20 00:49 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.15/0.07; 0.07) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-06-21 06:15 | SELL / LONDON | NORMAL_OR_LOW (0.14/0.25/0.22; 0.22) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.265R (blocked counterfactual) |
| 2024-06-21 13:07 | SELL / NY0830 | NORMAL_OR_LOW (0.60/0.68/0.51; 0.60) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.265R.

### Week of 2024-06-24 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +4.623R; trailing adaptive -0.015R; source-stop screen +4.623R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-06-25 00:21 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.04/0.34; 0.04) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-06-27 00:49 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.01/0.59; 0.01) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-06-28 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.04/0.09/0.29; 0.09) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-06-28 06:37 | BUY / LONDON | NORMAL_OR_LOW (0.25/0.33/0.12; 0.25) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-07-01 UTC

Events: 6; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +4.623R; trailing adaptive -0.015R; source-stop screen +4.623R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-07-01 00:23 | SELL / ASIA | NORMAL_OR_LOW (0.19/0.23/0.67; 0.23) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-07-02 00:17 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.07/0.56; 0.07) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-07-03 00:58 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.10/0.57; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-03 06:36 | BUY / LONDON | NORMAL_OR_LOW (0.20/0.18/0.09; 0.18) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-04 00:37 | SELL / ASIA | NORMAL_OR_LOW (0.09/0.31/0.68; 0.31) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-07-05 07:55 | BUY / LONDON | NORMAL_OR_LOW (0.38/0.25/0.00; 0.25) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-07-08 UTC

Events: 6; high-ATR: 0; completed candidate trades: 2; allowed: 0; blocked completed: 2.
This week: frozen -1.287R; trailing adaptive +0.000R; source-stop ATR-state screen -1.287R (blocked +0.000R). Cumulative: frozen +3.336R; trailing adaptive -0.015R; source-stop screen +3.336R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-07-08 12:50 | SELL / NY0830 | NORMAL_OR_LOW (0.65/0.67/0.47; 0.65) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-09 06:59 | SELL / LONDON | NORMAL_OR_LOW (0.33/0.40/0.53; 0.40) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-11 01:20 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.05/0.38; 0.05) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |
| 2024-07-11 06:21 | SELL / LONDON | NORMAL_OR_LOW (0.19/0.05/0.14; 0.14) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-12 00:17 | SELL / ASIA | NORMAL_OR_LOW (0.50/0.60/0.96; 0.60) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.287R (blocked counterfactual) |
| 2024-07-12 06:17 | SELL / LONDON | NORMAL_OR_LOW (0.26/0.53/0.39; 0.39) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -1.287R.

### Week of 2024-07-15 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.336R; trailing adaptive -0.015R; source-stop screen +3.336R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-07-15 13:20 | SELL / NY0830 | NORMAL_OR_LOW (0.79/0.68/0.35; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-07-16 00:51 | SELL / ASIA | NORMAL_OR_LOW (0.06/0.42/0.73; 0.42) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-07-18 00:28 | SELL / ASIA | NORMAL_OR_LOW (0.10/0.43/0.74; 0.43) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-19 06:23 | SELL / LONDON | NORMAL_OR_LOW (0.68/0.83/0.65; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-07-19 12:58 | SELL / NY0830 | NORMAL_OR_LOW (0.60/0.70/0.66; 0.66) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-07-22 UTC

Events: 5; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -1.000R; trailing adaptive -1.000R; source-stop ATR-state screen +0.000R (blocked -1.000R). Cumulative: frozen +2.336R; trailing adaptive -1.015R; source-stop screen +3.336R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-07-23 06:31 | SELL / LONDON | NORMAL_OR_LOW (0.22/0.17/0.08; 0.17) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-07-23 12:56 | BUY / NY0830 | NORMAL_OR_LOW (0.50/0.55/0.23; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-07-24 00:51 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.02/0.03; 0.02) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-25 01:07 | SELL / ASIA | NORMAL_OR_LOW (0.24/0.48/0.78; 0.48) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-25 06:39 | SELL / LONDON | HIGH (0.70/1.00/0.97; 0.97) | 0; mean — | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | -1.000R |

**Weekly market-state read:** HIGH: 1 trades, -1.000R.

### Week of 2024-07-29 UTC

Events: 7; high-ATR: 0; completed candidate trades: 2; allowed: 0; blocked completed: 2.
This week: frozen -1.933R; trailing adaptive +0.000R; source-stop ATR-state screen -1.933R (blocked +0.000R). Cumulative: frozen +0.402R; trailing adaptive -1.015R; source-stop screen +1.402R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-07-29 00:19 | BUY / ASIA | NORMAL_OR_LOW (0.61/0.50/0.52; 0.52) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |
| 2024-07-29 06:35 | BUY / LONDON | NORMAL_OR_LOW (0.18/0.21/0.42; 0.21) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-07-29 12:44 | BUY / NY0830 | NORMAL_OR_LOW (0.41/0.34/0.35; 0.35) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.933R (blocked counterfactual) |
| 2024-07-30 00:58 | BUY / ASIA | NORMAL_OR_LOW (0.05/0.10/0.22; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-07-31 00:23 | SELL / ASIA | NORMAL_OR_LOW (0.06/0.50/0.56; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-08-01 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.02/0.55/0.61; 0.55) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-08-02 06:52 | SELL / LONDON | NORMAL_OR_LOW (0.67/0.93/0.78; 0.78) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -1.933R.

### Week of 2024-08-05 UTC

Events: 4; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +0.633R; trailing adaptive +0.000R; source-stop ATR-state screen +0.633R (blocked +0.000R). Cumulative: frozen +1.036R; trailing adaptive -1.015R; source-stop screen +2.036R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-08-07 01:28 | SELL / ASIA | NORMAL_OR_LOW (0.15/0.03/0.42; 0.15) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-08-07 13:16 | BUY / NY0830 | NORMAL_OR_LOW (0.44/0.26/0.19; 0.26) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-08-08 00:49 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.06/0.08; 0.06) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-08-09 06:29 | BUY / LONDON | NORMAL_OR_LOW (0.09/0.04/0.02; 0.04) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.633R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.633R.

### Week of 2024-08-12 UTC

Events: 3; high-ATR: 0; completed candidate trades: 3; allowed: 0; blocked completed: 3.
This week: frozen -2.160R; trailing adaptive +0.000R; source-stop ATR-state screen -2.160R (blocked +0.000R). Cumulative: frozen -1.125R; trailing adaptive -1.015R; source-stop screen -0.125R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-08-15 00:56 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.03/0.85; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |
| 2024-08-15 06:22 | BUY / LONDON | NORMAL_OR_LOW (0.12/0.04/0.07; 0.07) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |
| 2024-08-16 01:27 | BUY / ASIA | NORMAL_OR_LOW (0.02/0.03/0.92; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.160R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 3 trades, -2.160R.

### Week of 2024-08-19 UTC

Events: 6; high-ATR: 0; completed candidate trades: 2; allowed: 0; blocked completed: 2.
This week: frozen +0.643R; trailing adaptive +0.000R; source-stop ATR-state screen +0.643R (blocked +0.000R). Cumulative: frozen -0.481R; trailing adaptive -1.015R; source-stop screen +0.519R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-08-19 13:09 | SELL / NY0830 | NORMAL_OR_LOW (0.78/0.68/0.59; 0.68) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-08-20 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.02/0.00/0.25; 0.02) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-08-21 00:41 | BUY / ASIA | NORMAL_OR_LOW (0.05/0.28/0.60; 0.28) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-08-21 07:04 | SELL / LONDON | NORMAL_OR_LOW (0.60/0.51/0.22; 0.51) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.380R (blocked counterfactual) |
| 2024-08-21 12:54 | SELL / NY0830 | NORMAL_OR_LOW (0.46/0.55/0.28; 0.46) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.263R (blocked counterfactual) |
| 2024-08-23 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.10/0.60; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, +0.643R.

### Week of 2024-08-26 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -0.481R; trailing adaptive -1.015R; source-stop screen +0.519R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-08-26 01:17 | SELL / ASIA | NORMAL_OR_LOW (0.25/0.11/0.43; 0.25) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-08-27 06:20 | BUY / LONDON | NORMAL_OR_LOW (0.28/0.29/0.15; 0.28) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-08-28 06:33 | BUY / LONDON | NORMAL_OR_LOW (0.49/0.46/0.25; 0.46) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-08-29 06:36 | BUY / LONDON | NORMAL_OR_LOW (0.23/0.30/0.25; 0.25) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-08-30 12:53 | SELL / NY0830 | NORMAL_OR_LOW (0.76/0.81/0.40; 0.76) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-09-02 UTC

Events: 2; high-ATR: 1; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -1.000R; trailing adaptive +0.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen -1.481R; trailing adaptive -1.015R; source-stop screen -0.481R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-09-03 12:47 | BUY / NY0830 | HIGH (0.95/0.86/0.47; 0.86) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2024-09-06 00:39 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.00/0.33; 0.00) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2024-09-09 UTC

Events: 6; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen -1.481R; trailing adaptive -1.015R; source-stop screen -0.481R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-09-09 13:20 | BUY / NY0830 | NORMAL_OR_LOW (0.62/0.70/0.55; 0.62) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-09-10 01:24 | SELL / ASIA | NORMAL_OR_LOW (0.08/0.28/0.43; 0.28) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-09-10 06:26 | BUY / LONDON | NORMAL_OR_LOW (0.15/0.13/0.12; 0.13) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-09-11 01:24 | SELL / ASIA | NORMAL_OR_LOW (0.07/0.10/0.38; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-09-13 01:15 | BUY / ASIA | NORMAL_OR_LOW (0.44/0.45/0.89; 0.45) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-09-13 07:25 | SELL / LONDON | NORMAL_OR_LOW (0.59/0.59/0.42; 0.59) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-09-16 UTC

Events: 4; high-ATR: 0; completed candidate trades: 2; allowed: 0; blocked completed: 2.
This week: frozen +1.645R; trailing adaptive +0.000R; source-stop ATR-state screen +1.645R (blocked +0.000R). Cumulative: frozen +0.164R; trailing adaptive -1.015R; source-stop screen +1.164R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-09-18 00:56 | SELL / ASIA | NORMAL_OR_LOW (0.09/0.30/0.83; 0.30) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-09-18 08:16 | BUY / LONDON | NORMAL_OR_LOW (0.40/0.33/0.21; 0.33) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-09-18 12:40 | SELL / NY0830 | NORMAL_OR_LOW (0.54/0.35/0.24; 0.35) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.412R (blocked counterfactual) |
| 2024-09-19 07:25 | BUY / LONDON | NORMAL_OR_LOW (0.63/0.60/0.97; 0.63) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +2.057R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, +1.645R.

### Week of 2024-09-23 UTC

Events: 4; high-ATR: 0; completed candidate trades: 2; allowed: 0; blocked completed: 2.
This week: frozen +1.838R; trailing adaptive +0.000R; source-stop ATR-state screen +1.838R (blocked +0.000R). Cumulative: frozen +2.002R; trailing adaptive -1.015R; source-stop screen +3.002R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-09-23 06:34 | SELL / LONDON | NORMAL_OR_LOW (0.42/0.38/0.28; 0.38) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +2.022R (blocked counterfactual) |
| 2024-09-24 01:01 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.00/0.08; 0.03) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-09-25 15:00 | SELL / NY0830 | NORMAL_OR_LOW (0.87/0.64/0.58; 0.64) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.185R (blocked counterfactual) |
| 2024-09-27 00:30 | SELL / ASIA | NORMAL_OR_LOW (0.04/0.16/0.93; 0.16) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, +1.838R.

### Week of 2024-09-30 UTC

Events: 3; high-ATR: 0; completed candidate trades: 2; allowed: 0; blocked completed: 2.
This week: frozen -1.601R; trailing adaptive +0.000R; source-stop ATR-state screen -1.601R (blocked +0.000R). Cumulative: frozen +0.401R; trailing adaptive -1.015R; source-stop screen +1.401R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-09-30 12:51 | SELL / NY0830 | NORMAL_OR_LOW (0.79/0.79/0.64; 0.79) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-10-01 08:16 | BUY / LONDON | NORMAL_OR_LOW (0.23/0.17/0.09; 0.17) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.601R (blocked counterfactual) |
| 2024-10-01 12:42 | SELL / NY0830 | NORMAL_OR_LOW (0.37/0.26/0.01; 0.26) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -1.601R.

### Week of 2024-10-07 UTC

Events: 3; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +2.170R; trailing adaptive +0.000R; source-stop ATR-state screen +2.170R (blocked +0.000R). Cumulative: frozen +2.571R; trailing adaptive -1.015R; source-stop screen +3.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-10-07 06:55 | BUY / LONDON | NORMAL_OR_LOW (0.31/0.32/0.47; 0.32) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +2.170R (blocked counterfactual) |
| 2024-10-10 00:22 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.10/0.24; 0.10) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-10-10 06:35 | BUY / LONDON | NORMAL_OR_LOW (0.19/0.17/0.09; 0.17) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +2.170R.

### Week of 2024-10-14 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.571R; trailing adaptive -1.015R; source-stop screen +3.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-10-14 01:18 | SELL / ASIA | NORMAL_OR_LOW (0.48/0.16/0.28; 0.28) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-10-14 12:51 | SELL / NY0830 | NORMAL_OR_LOW (0.62/0.50/0.37; 0.50) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-10-17 07:10 | SELL / LONDON | NORMAL_OR_LOW (0.63/0.47/0.03; 0.47) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-10-18 06:17 | SELL / LONDON | NORMAL_OR_LOW (0.35/0.37/0.18; 0.35) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-10-21 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.571R; trailing adaptive -1.015R; source-stop screen +3.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-10-22 06:38 | BUY / LONDON | NORMAL_OR_LOW (0.39/0.30/0.27; 0.30) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-10-23 00:40 | SELL / ASIA | NORMAL_OR_LOW (0.05/0.08/0.47; 0.08) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-10-25 01:09 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.00/0.42; 0.01) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-10-25 06:21 | SELL / LONDON | NORMAL_OR_LOW (0.34/0.14/0.00; 0.14) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-10-28 UTC

Events: 5; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.571R; trailing adaptive -1.015R; source-stop screen +3.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-10-28 00:48 | SELL / ASIA | HIGH (0.85/0.60/0.88; 0.85) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2024-10-28 06:34 | BUY / LONDON | NORMAL_OR_LOW (0.54/0.60/0.56; 0.56) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-10-29 00:45 | BUY / ASIA | NORMAL_OR_LOW (0.08/0.01/0.11; 0.08) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-10-30 07:56 | SELL / LONDON | NORMAL_OR_LOW (0.47/0.43/0.20; 0.43) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-10-31 01:41 | BUY / ASIA | NORMAL_OR_LOW (0.09/0.04/0.45; 0.09) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-11-04 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -1.000R; trailing adaptive +0.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen +1.571R; trailing adaptive -1.015R; source-stop screen +2.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-11-04 06:36 | SELL / LONDON | NORMAL_OR_LOW (0.32/0.32/0.41; 0.32) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R (blocked counterfactual) |
| 2024-11-05 01:20 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.02/0.28; 0.02) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-11-05 06:28 | BUY / LONDON | NORMAL_OR_LOW (0.38/0.30/0.15; 0.30) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-11-05 14:07 | BUY / NY0830 | NORMAL_OR_LOW (0.54/0.59/0.58; 0.58) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-11-08 00:26 | BUY / ASIA | NORMAL_OR_LOW (0.62/0.70/0.78; 0.70) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-11-08 13:41 | SELL / NY0830 | NORMAL_OR_LOW (0.57/0.54/0.29; 0.54) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2024-11-11 UTC

Events: 6; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +1.571R; trailing adaptive -1.015R; source-stop screen +2.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-11-11 00:32 | SELL / ASIA | NORMAL_OR_LOW (0.07/0.08/0.33; 0.08) | 5; mean -0.003R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-11-12 13:59 | SELL / NY0830 | HIGH (0.82/0.86/0.43; 0.82) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2024-11-13 14:17 | BUY / NY0830 | NORMAL_OR_LOW (0.50/0.22/0.11; 0.22) | 3; mean +0.196R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-11-14 00:37 | BUY / ASIA | NORMAL_OR_LOW (0.56/0.65/0.75; 0.65) | 3; mean +0.196R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-11-15 06:29 | SELL / LONDON | NORMAL_OR_LOW (0.12/0.01/0.22; 0.12) | 3; mean +0.196R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-11-15 15:46 | SELL / NY0830 | NORMAL_OR_LOW (0.94/0.70/0.43; 0.70) | 3; mean +0.196R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-11-18 UTC

Events: 2; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +1.571R; trailing adaptive -1.015R; source-stop screen +2.571R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-11-19 00:29 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.00/0.12; 0.00) | 3; mean +0.196R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-11-22 14:54 | BUY / NY0830 | HIGH (0.99/1.00/0.97; 0.99) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: PENDING_EXIT_HORIZON |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-11-25 UTC

Events: 4; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +2.615R; trailing adaptive +2.615R; source-stop ATR-state screen +2.615R (blocked +0.000R). Cumulative: frozen +4.185R; trailing adaptive +1.600R; source-stop screen +5.185R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-11-28 07:47 | BUY / LONDON | NORMAL_OR_LOW (0.29/0.44/0.09; 0.29) | 1; mean +2.349R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | +2.615R |
| 2024-11-29 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.00/0.00; 0.00) | 2; mean +2.482R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-11-29 07:05 | BUY / LONDON | NORMAL_OR_LOW (0.26/0.54/0.22; 0.26) | 2; mean +2.482R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-11-29 13:43 | SELL / NY0830 | NORMAL_OR_LOW (0.41/0.41/0.40; 0.41) | 2; mean +2.482R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +2.615R.

### Week of 2024-12-02 UTC

Events: 3; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -0.879R; trailing adaptive -0.879R; source-stop ATR-state screen -0.879R (blocked +0.000R). Cumulative: frozen +3.307R; trailing adaptive +0.721R; source-stop screen +4.307R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-12-03 01:21 | BUY / ASIA | NORMAL_OR_LOW (0.08/0.13/0.32; 0.13) | 2; mean +2.482R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-12-05 01:11 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.04/0.46; 0.04) | 2; mean +2.482R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | -0.879R |
| 2024-12-06 14:45 | SELL / NY0830 | HIGH (0.94/0.78/0.90; 0.90) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: PENDING_RECLAIM_HORIZON |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.879R.

### Week of 2024-12-09 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.307R; trailing adaptive +0.721R; source-stop screen +4.307R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-12-11 13:40 | BUY / NY0830 | NORMAL_OR_LOW (0.60/0.62/0.97; 0.62) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2024-12-12 13:49 | SELL / NY0830 | NORMAL_OR_LOW (0.70/0.38/0.57; 0.57) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-12-13 06:40 | SELL / LONDON | NORMAL_OR_LOW (0.13/0.23/0.04; 0.13) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-12-13 14:28 | SELL / NY0830 | NORMAL_OR_LOW (0.72/0.70/0.58; 0.70) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2024-12-16 UTC

Events: 7; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +0.076R; trailing adaptive +0.076R; source-stop ATR-state screen +0.000R (blocked +0.076R). Cumulative: frozen +3.383R; trailing adaptive +0.797R; source-stop screen +4.307R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-12-16 00:26 | SELL / ASIA | NORMAL_OR_LOW (0.13/0.12/0.28; 0.13) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-12-16 07:56 | BUY / LONDON | NORMAL_OR_LOW (0.13/0.13/0.03; 0.13) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2024-12-16 13:51 | SELL / NY0830 | NORMAL_OR_LOW (0.42/0.20/0.10; 0.20) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-12-18 01:03 | BUY / ASIA | NORMAL_OR_LOW (0.05/0.05/0.28; 0.05) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-12-18 06:31 | SELL / LONDON | NORMAL_OR_LOW (0.13/0.12/0.02; 0.12) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2024-12-19 14:11 | SELL / NY0830 | HIGH (0.88/0.86/0.91; 0.88) | 1; mean -1.000R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | +0.076R |
| 2024-12-20 01:06 | SELL / ASIA | NORMAL_OR_LOW (0.17/0.30/0.58; 0.30) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** HIGH: 1 trades, +0.076R.

### Week of 2024-12-23 UTC

Events: 5; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -0.796R; trailing adaptive -0.796R; source-stop ATR-state screen -0.796R (blocked +0.000R). Cumulative: frozen +2.587R; trailing adaptive +0.001R; source-stop screen +3.511R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2024-12-23 13:59 | BUY / NY0830 | NORMAL_OR_LOW (0.59/0.35/0.45; 0.45) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2024-12-24 06:29 | SELL / LONDON | NORMAL_OR_LOW (0.06/0.07/0.03; 0.06) | 2; mean +0.868R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | +0.204R |
| 2024-12-24 15:04 | SELL / NY0830 | NORMAL_OR_LOW (0.44/0.30/0.07; 0.30) | 3; mean +0.647R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_RECLAIM_HORIZON |
| 2024-12-26 06:55 | SELL / LONDON | NORMAL_OR_LOW (0.09/0.00/0.18; 0.09) | 3; mean +0.647R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2024-12-27 01:45 | SELL / ASIA | NORMAL_OR_LOW (0.07/0.02/0.30; 0.07) | 4; mean +0.235R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -0.796R.

### Week of 2024-12-30 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.587R; trailing adaptive +0.001R; source-stop screen +3.511R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-01-02 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.10/0.04/0.72; 0.10) | 4; mean +0.235R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-01-02 06:11 | SELL / LONDON | NORMAL_OR_LOW (0.23/0.46/0.58; 0.46) | 4; mean +0.235R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-01-03 01:24 | BUY / ASIA | NORMAL_OR_LOW (0.06/0.24/0.89; 0.24) | 4; mean +0.235R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-01-06 UTC

Events: 3; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +0.506R; trailing adaptive +0.506R; source-stop ATR-state screen +0.506R (blocked +0.000R). Cumulative: frozen +3.094R; trailing adaptive +0.508R; source-stop screen +4.017R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-01-06 00:34 | SELL / ASIA | NORMAL_OR_LOW (0.18/0.11/0.39; 0.18) | 4; mean +0.235R | trailing: ALLOW_WARMUP; fixed: ALLOW_NORMAL_OR_LOW | +0.506R |
| 2025-01-08 06:31 | BUY / LONDON | NORMAL_OR_LOW (0.15/0.08/0.30; 0.15) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-01-09 00:27 | SELL / ASIA | NORMAL_OR_LOW (0.11/0.75/0.78; 0.75) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.506R.

### Week of 2025-01-13 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.094R; trailing adaptive +0.508R; source-stop screen +4.017R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-01-13 00:19 | BUY / ASIA | NORMAL_OR_LOW (0.47/0.65/0.88; 0.65) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-01-13 06:47 | BUY / LONDON | NORMAL_OR_LOW (0.38/0.59/0.69; 0.59) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-01-14 01:17 | BUY / ASIA | NORMAL_OR_LOW (0.24/0.26/0.64; 0.26) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-01-16 06:23 | SELL / LONDON | NORMAL_OR_LOW (0.11/0.28/0.18; 0.18) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-01-17 14:06 | SELL / NY0830 | NORMAL_OR_LOW (0.71/0.54/0.19; 0.54) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-01-20 UTC

Events: 2; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.094R; trailing adaptive +0.508R; source-stop screen +4.017R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-01-20 17:26 | SELL / NY0830 | NORMAL_OR_LOW (0.83/0.71/0.74; 0.74) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-01-24 06:25 | BUY / LONDON | NORMAL_OR_LOW (0.45/0.42/0.42; 0.42) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-01-27 UTC

Events: 7; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -1.164R; trailing adaptive -1.164R; source-stop ATR-state screen -1.164R (blocked +0.000R). Cumulative: frozen +1.930R; trailing adaptive -0.656R; source-stop screen +2.853R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-01-28 00:52 | BUY / ASIA | NORMAL_OR_LOW (0.31/0.37/0.93; 0.37) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-01-28 07:08 | SELL / LONDON | NORMAL_OR_LOW (0.09/0.13/0.07; 0.09) | 5; mean +0.289R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-01-29 13:47 | BUY / NY0830 | NORMAL_OR_LOW (0.40/0.34/0.07; 0.34) | 6; mean +0.074R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-01-30 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.10/0.58/0.60; 0.58) | 6; mean +0.074R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-01-30 14:06 | BUY / NY0830 | NORMAL_OR_LOW (0.34/0.53/0.22; 0.34) | 6; mean +0.074R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.164R |
| 2025-01-31 07:07 | SELL / LONDON | NORMAL_OR_LOW (0.12/0.11/0.31; 0.12) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-01-31 14:48 | BUY / NY0830 | NORMAL_OR_LOW (0.67/0.54/0.35; 0.54) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -1.164R.

### Week of 2025-02-03 UTC

Events: 4; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +1.930R; trailing adaptive -0.656R; source-stop screen +2.853R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-02-03 06:39 | BUY / LONDON | HIGH (0.70/0.88/0.98; 0.88) | 2; mean -0.462R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2025-02-04 14:08 | SELL / NY0830 | NORMAL_OR_LOW (0.78/0.85/0.73; 0.78) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-02-05 00:56 | BUY / ASIA | NORMAL_OR_LOW (0.20/0.13/0.64; 0.20) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-02-07 00:48 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.03/0.44; 0.03) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-02-10 UTC

Events: 4; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -0.688R; trailing adaptive -0.688R; source-stop ATR-state screen +0.000R (blocked -0.688R). Cumulative: frozen +1.242R; trailing adaptive -1.344R; source-stop screen +2.853R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-02-10 14:18 | SELL / NY0830 | NORMAL_OR_LOW (0.80/0.59/0.39; 0.59) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-11 13:51 | BUY / NY0830 | HIGH (0.87/0.86/1.00; 0.87) | 2; mean -0.462R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | -0.688R |
| 2025-02-12 07:35 | BUY / LONDON | NORMAL_OR_LOW (0.56/0.61/0.20; 0.56) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-13 00:54 | BUY / ASIA | NORMAL_OR_LOW (0.12/0.36/0.70; 0.36) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** HIGH: 1 trades, -0.688R.

### Week of 2025-02-17 UTC

Events: 7; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +2.852R; trailing adaptive +2.852R; source-stop ATR-state screen +2.852R (blocked +0.000R). Cumulative: frozen +4.095R; trailing adaptive +1.509R; source-stop screen +5.706R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-02-17 00:29 | BUY / ASIA | NORMAL_OR_LOW (0.79/0.65/0.90; 0.79) | 7; mean +0.040R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +2.852R |
| 2025-02-18 06:29 | BUY / LONDON | NORMAL_OR_LOW (0.31/0.17/0.02; 0.17) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-19 00:30 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.03/0.18; 0.03) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-19 07:21 | BUY / LONDON | NORMAL_OR_LOW (0.13/0.47/0.33; 0.33) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-02-20 06:51 | SELL / LONDON | NORMAL_OR_LOW (0.11/0.16/0.52; 0.16) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-21 00:46 | SELL / ASIA | NORMAL_OR_LOW (0.08/0.14/0.70; 0.14) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-21 13:43 | SELL / NY0830 | NORMAL_OR_LOW (0.51/0.60/0.86; 0.60) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +2.852R.

### Week of 2025-02-24 UTC

Events: 3; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +0.704R; trailing adaptive +0.704R; source-stop ATR-state screen +0.704R (blocked +0.000R). Cumulative: frozen +4.798R; trailing adaptive +2.212R; source-stop screen +6.409R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-02-24 00:27 | SELL / ASIA | NORMAL_OR_LOW (0.32/0.30/0.45; 0.32) | 8; mean +0.392R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.704R |
| 2025-02-24 06:44 | BUY / LONDON | NORMAL_OR_LOW (0.57/0.67/0.61; 0.61) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-02-28 00:45 | BUY / ASIA | NORMAL_OR_LOW (0.13/0.19/0.82; 0.19) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.704R.

### Week of 2025-03-03 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +4.798R; trailing adaptive +2.212R; source-stop screen +6.409R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-03-03 00:39 | SELL / ASIA | NORMAL_OR_LOW (0.78/0.71/0.82; 0.78) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-03-03 14:11 | BUY / NY0830 | NORMAL_OR_LOW (0.38/0.28/0.07; 0.28) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-03-06 06:17 | BUY / LONDON | NORMAL_OR_LOW (0.11/0.05/0.15; 0.11) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-03-07 00:34 | SELL / ASIA | NORMAL_OR_LOW (0.45/0.30/0.49; 0.45) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-03-10 UTC

Events: 4; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -1.000R; trailing adaptive -1.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen +3.798R; trailing adaptive +1.212R; source-stop screen +5.409R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-03-10 01:32 | SELL / ASIA | NORMAL_OR_LOW (0.19/0.06/0.70; 0.19) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-03-12 01:00 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.03/0.00; 0.02) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-03-12 06:24 | BUY / LONDON | NORMAL_OR_LOW (0.16/0.05/0.00; 0.05) | 9; mean +0.426R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-03-14 12:48 | BUY / NY0830 | NORMAL_OR_LOW (0.82/0.80/0.55; 0.80) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2025-03-17 UTC

Events: 6; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +3.798R; trailing adaptive +1.212R; source-stop screen +5.409R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-03-17 13:39 | SELL / NY0830 | NORMAL_OR_LOW (0.74/0.58/0.26; 0.58) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-03-18 06:58 | BUY / LONDON | NORMAL_OR_LOW (0.74/0.73/0.09; 0.73) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-03-19 12:51 | BUY / NY0830 | NORMAL_OR_LOW (0.44/0.91/0.57; 0.57) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-03-20 00:14 | BUY / ASIA | NORMAL_OR_LOW (0.17/0.66/0.66; 0.66) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-03-20 13:01 | BUY / NY0830 | HIGH (0.81/0.86/0.55; 0.81) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2025-03-21 00:24 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.09/0.41; 0.09) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-03-24 UTC

Events: 4; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -0.908R; trailing adaptive -0.908R; source-stop ATR-state screen -0.908R (blocked +0.000R). Cumulative: frozen +2.890R; trailing adaptive +0.304R; source-stop screen +4.501R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-03-24 12:59 | SELL / NY0830 | NORMAL_OR_LOW (0.43/0.46/0.48; 0.46) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-03-25 06:53 | SELL / LONDON | NORMAL_OR_LOW (0.11/0.20/0.15; 0.15) | 10; mean +0.284R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.908R |
| 2025-03-27 00:35 | BUY / ASIA | NORMAL_OR_LOW (0.13/0.05/0.18; 0.13) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-03-27 06:49 | SELL / LONDON | NORMAL_OR_LOW (0.59/0.50/0.07; 0.50) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.908R.

### Week of 2025-03-31 UTC

Events: 4; high-ATR: 3; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.890R; trailing adaptive +0.304R; source-stop screen +4.501R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-03-31 06:20 | BUY / LONDON | HIGH (0.93/0.92/0.95; 0.93) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-04-01 07:59 | SELL / LONDON | HIGH (0.90/0.82/0.56; 0.82) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-04-02 07:19 | SELL / LONDON | NORMAL_OR_LOW (0.67/0.61/0.49; 0.61) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-02 12:52 | SELL / NY0830 | HIGH (0.81/0.83/0.82; 0.82) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-04-07 UTC

Events: 5; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +0.376R; trailing adaptive +0.376R; source-stop ATR-state screen +0.376R (blocked +0.000R). Cumulative: frozen +3.266R; trailing adaptive +0.680R; source-stop screen +4.877R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-04-09 00:33 | BUY / ASIA | NORMAL_OR_LOW (0.41/0.45/0.41; 0.41) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-09 12:46 | SELL / NY0830 | NORMAL_OR_LOW (0.70/0.66/0.57; 0.66) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-10 13:33 | BUY / NY0830 | NORMAL_OR_LOW (0.46/0.27/0.28; 0.28) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-11 06:34 | BUY / LONDON | NORMAL_OR_LOW (0.54/0.60/0.34; 0.54) | 11; mean +0.175R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.376R |
| 2025-04-11 13:19 | BUY / NY0830 | NORMAL_OR_LOW (0.59/0.63/0.60; 0.60) | 12; mean +0.192R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.376R.

### Week of 2025-04-14 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -0.540R; trailing adaptive -0.540R; source-stop ATR-state screen -0.540R (blocked +0.000R). Cumulative: frozen +2.726R; trailing adaptive +0.140R; source-stop screen +4.337R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-04-14 01:02 | SELL / ASIA | NORMAL_OR_LOW (0.21/0.01/0.27; 0.21) | 12; mean +0.192R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-14 07:01 | SELL / LONDON | NORMAL_OR_LOW (0.04/0.20/0.15; 0.15) | 12; mean +0.192R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.540R |
| 2025-04-15 06:47 | BUY / LONDON | NORMAL_OR_LOW (0.04/0.06/0.00; 0.04) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-04-15 13:47 | SELL / NY0830 | NORMAL_OR_LOW (0.19/0.12/0.05; 0.12) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-16 14:00 | BUY / NY0830 | NORMAL_OR_LOW (0.66/0.67/0.45; 0.66) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-04-17 00:52 | SELL / ASIA | NORMAL_OR_LOW (0.25/0.20/0.30; 0.25) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.540R.

### Week of 2025-04-21 UTC

Events: 4; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.726R; trailing adaptive +0.140R; source-stop screen +4.337R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-04-21 06:30 | BUY / LONDON | NORMAL_OR_LOW (0.28/0.70/0.88; 0.70) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-04-22 00:18 | SELL / ASIA | NORMAL_OR_LOW (0.67/0.32/0.56; 0.56) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-04-22 13:01 | SELL / NY0830 | HIGH (0.93/0.98/1.00; 0.98) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-04-24 12:42 | BUY / NY0830 | NORMAL_OR_LOW (0.29/0.45/0.59; 0.45) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-04-28 UTC

Events: 6; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +2.726R; trailing adaptive +0.140R; source-stop screen +4.337R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-04-28 01:06 | BUY / ASIA | NORMAL_OR_LOW (0.41/0.21/0.28; 0.28) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-04-29 00:39 | SELL / ASIA | NORMAL_OR_LOW (0.06/0.00/0.08; 0.06) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-04-30 07:10 | SELL / LONDON | NORMAL_OR_LOW (0.04/0.09/0.00; 0.04) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-01 13:11 | BUY / NY0830 | NORMAL_OR_LOW (0.72/0.45/0.78; 0.72) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-02 00:34 | BUY / ASIA | NORMAL_OR_LOW (0.18/0.03/0.45; 0.18) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-05-02 13:19 | SELL / NY0830 | NORMAL_OR_LOW (0.47/0.22/0.08; 0.22) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-05-05 UTC

Events: 5; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +10.077R; trailing adaptive +10.077R; source-stop ATR-state screen +10.077R (blocked +0.000R). Cumulative: frozen +12.803R; trailing adaptive +10.217R; source-stop screen +14.414R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-05-05 00:42 | SELL / ASIA | NORMAL_OR_LOW (0.01/0.09/0.38; 0.09) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-05 07:01 | BUY / LONDON | NORMAL_OR_LOW (0.11/0.31/0.14; 0.14) | 13; mean +0.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +10.077R |
| 2025-05-06 00:47 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.03/0.07; 0.03) | 14; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-05-07 07:22 | BUY / LONDON | HIGH (0.43/0.92/0.97; 0.92) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2025-05-09 00:37 | SELL / ASIA | NORMAL_OR_LOW (0.25/0.56/0.68; 0.56) | 14; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +10.077R.

### Week of 2025-05-12 UTC

Events: 8; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -1.000R; trailing adaptive -1.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen +11.803R; trailing adaptive +9.217R; source-stop screen +13.414R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-05-12 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.90/0.66/0.45; 0.66) | 14; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-05-13 01:09 | BUY / ASIA | NORMAL_OR_LOW (0.05/0.00/0.05; 0.05) | 14; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-13 14:46 | BUY / NY0830 | NORMAL_OR_LOW (0.76/0.25/0.22; 0.25) | 14; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-14 00:33 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.01/0.00; 0.01) | 14; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-05-14 07:48 | BUY / LONDON | NORMAL_OR_LOW (0.30/0.28/0.00; 0.28) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-05-15 00:14 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.04/0.35; 0.04) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-16 06:18 | BUY / LONDON | NORMAL_OR_LOW (0.56/0.66/0.33; 0.56) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-05-16 13:15 | BUY / NY0830 | HIGH (0.96/0.94/0.94; 0.94) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2025-05-19 UTC

Events: 9; high-ATR: 1; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen +1.000R; trailing adaptive +1.000R; source-stop ATR-state screen +1.000R (blocked +0.000R). Cumulative: frozen +12.803R; trailing adaptive +10.218R; source-stop screen +14.415R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-05-19 00:40 | BUY / ASIA | HIGH (0.86/0.68/0.94; 0.86) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2025-05-19 07:42 | BUY / LONDON | NORMAL_OR_LOW (0.30/0.61/0.58; 0.58) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-19 13:12 | SELL / NY0830 | NORMAL_OR_LOW (0.27/0.34/0.58; 0.34) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-05-20 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.04/0.01/0.07; 0.04) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-20 07:05 | SELL / LONDON | NORMAL_OR_LOW (0.23/0.35/0.01; 0.23) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-05-21 06:15 | SELL / LONDON | NORMAL_OR_LOW (0.29/0.65/0.29; 0.29) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-05-22 00:21 | BUY / ASIA | NORMAL_OR_LOW (0.13/0.11/0.09; 0.11) | 15; mean +0.723R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +1.478R |
| 2025-05-22 13:02 | SELL / NY0830 | NORMAL_OR_LOW (0.86/0.72/0.57; 0.72) | 16; mean +0.770R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.478R |
| 2025-05-23 00:56 | SELL / ASIA | NORMAL_OR_LOW (0.06/0.05/0.67; 0.06) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, +1.000R.

### Week of 2025-05-26 UTC

Events: 8; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +12.803R; trailing adaptive +10.218R; source-stop screen +14.415R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-05-26 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.65/0.27/0.57; 0.57) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-05-27 00:31 | SELL / ASIA | NORMAL_OR_LOW (0.03/0.00/0.00; 0.00) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-05-27 06:14 | BUY / LONDON | NORMAL_OR_LOW (0.26/0.23/0.08; 0.23) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-05-28 00:53 | BUY / ASIA | NORMAL_OR_LOW (0.09/0.04/0.21; 0.09) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-05-28 06:16 | SELL / LONDON | NORMAL_OR_LOW (0.53/0.62/0.12; 0.53) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-05-29 00:57 | BUY / ASIA | HIGH (0.97/0.88/0.73; 0.88) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: NO_CONTINUATION |
| 2025-05-29 13:05 | BUY / NY0830 | NORMAL_OR_LOW (0.68/0.65/0.89; 0.68) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-05-30 06:39 | SELL / LONDON | NORMAL_OR_LOW (0.64/0.61/0.16; 0.61) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-06-02 UTC

Events: 5; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +13.360R; trailing adaptive +13.360R; source-stop ATR-state screen +13.360R (blocked +0.000R). Cumulative: frozen +26.163R; trailing adaptive +23.577R; source-stop screen +27.774R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-06-02 00:23 | BUY / ASIA | NORMAL_OR_LOW (0.50/0.22/0.68; 0.50) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +13.360R |
| 2025-06-02 06:13 | BUY / LONDON | NORMAL_OR_LOW (0.16/0.26/0.38; 0.26) | 17; mean +0.697R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-06-02 13:13 | SELL / NY0830 | NORMAL_OR_LOW (0.50/0.68/0.53; 0.53) | 18; mean +1.400R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-06-03 13:12 | BUY / NY0830 | NORMAL_OR_LOW (0.30/0.21/0.31; 0.30) | 18; mean +1.400R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-06-06 01:05 | SELL / ASIA | NORMAL_OR_LOW (0.15/0.08/0.85; 0.15) | 18; mean +1.400R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +13.360R.

### Week of 2025-06-09 UTC

Events: 5; high-ATR: 2; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -0.356R; trailing adaptive -0.356R; source-stop ATR-state screen +0.644R (blocked -1.000R). Cumulative: frozen +25.807R; trailing adaptive +23.221R; source-stop screen +28.419R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-06-09 14:23 | BUY / NY0830 | NORMAL_OR_LOW (0.70/0.28/0.33; 0.33) | 18; mean +1.400R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-06-10 00:32 | SELL / ASIA | NORMAL_OR_LOW (0.11/0.04/0.03; 0.04) | 18; mean +1.400R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.644R |
| 2025-06-12 01:45 | BUY / ASIA | HIGH (0.86/0.83/0.94; 0.86) | 3; mean -0.537R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | -1.000R |
| 2025-06-12 13:14 | BUY / NY0830 | HIGH (0.86/0.95/0.95; 0.95) | 4; mean -0.653R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2025-06-13 12:50 | BUY / NY0830 | NORMAL_OR_LOW (0.71/0.74/1.00; 0.74) | 19; mean +1.360R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** HIGH: 1 trades, -1.000R; NORMAL_OR_LOW: 1 trades, +0.644R.

### Week of 2025-06-16 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -1.000R; trailing adaptive -1.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen +24.807R; trailing adaptive +22.221R; source-stop screen +27.419R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-06-16 01:17 | SELL / ASIA | NORMAL_OR_LOW (0.86/0.69/0.62; 0.69) | 19; mean +1.360R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-06-17 01:11 | SELL / ASIA | NORMAL_OR_LOW (0.46/0.16/0.48; 0.46) | 19; mean +1.360R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-06-17 06:32 | SELL / LONDON | NORMAL_OR_LOW (0.38/0.52/0.20; 0.38) | 19; mean +1.360R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-06-18 06:22 | SELL / LONDON | NORMAL_OR_LOW (0.20/0.11/0.06; 0.11) | 19; mean +1.360R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-06-20 00:39 | SELL / ASIA | NORMAL_OR_LOW (0.09/0.21/0.12; 0.12) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-06-20 13:05 | SELL / NY0830 | NORMAL_OR_LOW (0.12/0.10/0.12; 0.12) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_RECLAIM_HORIZON |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2025-06-23 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +24.807R; trailing adaptive +22.221R; source-stop screen +27.419R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-06-23 12:46 | SELL / NY0830 | NORMAL_OR_LOW (0.70/0.60/0.60; 0.60) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-06-24 12:49 | SELL / NY0830 | NORMAL_OR_LOW (0.58/0.67/0.94; 0.67) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-06-26 00:44 | SELL / ASIA | NORMAL_OR_LOW (0.08/0.07/0.12; 0.08) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-06-27 12:52 | SELL / NY0830 | NORMAL_OR_LOW (0.84/0.70/0.70; 0.70) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-06-30 UTC

Events: 7; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +24.807R; trailing adaptive +22.221R; source-stop screen +27.419R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-06-30 00:36 | BUY / ASIA | NORMAL_OR_LOW (0.77/0.70/0.71; 0.71) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-06-30 12:52 | BUY / NY0830 | NORMAL_OR_LOW (0.55/0.43/0.53; 0.53) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-02 13:27 | SELL / NY0830 | NORMAL_OR_LOW (0.61/0.57/0.49; 0.57) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-07-03 01:16 | SELL / ASIA | NORMAL_OR_LOW (0.43/0.12/0.33; 0.33) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-04 01:09 | SELL / ASIA | NORMAL_OR_LOW (0.08/0.00/0.75; 0.08) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-04 06:35 | BUY / LONDON | NORMAL_OR_LOW (0.13/0.10/0.00; 0.10) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-07-04 14:27 | SELL / NY0830 | NORMAL_OR_LOW (0.23/0.17/0.07; 0.17) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-07-07 UTC

Events: 6; high-ATR: 1; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -0.450R; trailing adaptive -0.450R; source-stop ATR-state screen -1.000R (blocked +0.550R). Cumulative: frozen +24.358R; trailing adaptive +21.772R; source-stop screen +26.419R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-07-07 06:42 | SELL / LONDON | NORMAL_OR_LOW (0.72/0.88/0.47; 0.72) | 20; mean +1.242R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-07-07 13:02 | BUY / NY0830 | HIGH (0.91/0.88/0.91; 0.91) | 4; mean -0.653R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | +0.550R |
| 2025-07-08 07:45 | SELL / LONDON | NORMAL_OR_LOW (0.39/0.26/0.13; 0.26) | 21; mean +1.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-09 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.29/0.33/0.68; 0.33) | 21; mean +1.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-09 06:33 | SELL / LONDON | NORMAL_OR_LOW (0.63/0.73/0.54; 0.63) | 21; mean +1.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-07-10 00:52 | BUY / ASIA | NORMAL_OR_LOW (0.08/0.08/0.47; 0.08) | 21; mean +1.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** HIGH: 1 trades, +0.550R; NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2025-07-14 UTC

Events: 7; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -0.021R; trailing adaptive -0.021R; source-stop ATR-state screen -0.021R (blocked +0.000R). Cumulative: frozen +24.337R; trailing adaptive +21.751R; source-stop screen +26.397R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-07-14 00:48 | BUY / ASIA | NORMAL_OR_LOW (0.72/0.41/0.62; 0.62) | 21; mean +1.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-07-14 06:25 | BUY / LONDON | NORMAL_OR_LOW (0.25/0.38/0.33; 0.33) | 21; mean +1.136R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.979R |
| 2025-07-14 12:55 | SELL / NY0830 | NORMAL_OR_LOW (0.66/0.53/0.50; 0.53) | 22; mean +1.128R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-15 00:40 | BUY / ASIA | NORMAL_OR_LOW (0.02/0.00/0.28; 0.02) | 22; mean +1.128R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-07-15 06:09 | SELL / LONDON | NORMAL_OR_LOW (0.13/0.07/0.00; 0.07) | 23; mean +1.036R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-07-16 06:31 | BUY / LONDON | NORMAL_OR_LOW (0.18/0.15/0.21; 0.18) | 23; mean +1.036R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-07-18 01:09 | SELL / ASIA | NORMAL_OR_LOW (0.10/0.00/0.20; 0.10) | 23; mean +1.036R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -0.021R.

### Week of 2025-07-21 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -0.414R; trailing adaptive -0.414R; source-stop ATR-state screen -0.414R (blocked +0.000R). Cumulative: frozen +23.923R; trailing adaptive +21.337R; source-stop screen +25.983R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-07-23 06:29 | BUY / LONDON | NORMAL_OR_LOW (0.60/0.74/0.31; 0.60) | 23; mean +1.036R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.414R |
| 2025-07-24 01:07 | BUY / ASIA | NORMAL_OR_LOW (0.22/0.26/0.83; 0.26) | 24; mean +0.976R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-07-24 06:18 | SELL / LONDON | NORMAL_OR_LOW (0.74/0.73/0.75; 0.74) | 24; mean +0.976R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-07-25 00:41 | BUY / ASIA | NORMAL_OR_LOW (0.11/0.08/0.52; 0.11) | 24; mean +0.976R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-07-25 06:40 | SELL / LONDON | NORMAL_OR_LOW (0.43/0.31/0.05; 0.31) | 24; mean +0.976R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-07-25 12:45 | SELL / NY0830 | NORMAL_OR_LOW (0.45/0.58/0.33; 0.45) | 24; mean +0.976R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_EXIT_HORIZON |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.414R.

### Week of 2025-07-28 UTC

Events: 7; high-ATR: 1; completed candidate trades: 5; allowed: 5; blocked completed: 0.
This week: frozen -1.919R; trailing adaptive -1.919R; source-stop ATR-state screen -0.919R (blocked -1.000R). Cumulative: frozen +22.004R; trailing adaptive +19.418R; source-stop screen +25.064R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-07-28 12:56 | SELL / NY0830 | NORMAL_OR_LOW (0.44/0.42/0.38; 0.42) | 24; mean +0.976R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.197R |
| 2025-07-30 00:22 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.01/0.34; 0.01) | 25; mean +0.944R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-07-31 00:59 | BUY / ASIA | HIGH (0.46/0.82/1.00; 0.82) | 4; mean -0.265R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | -1.000R |
| 2025-07-31 06:41 | BUY / LONDON | NORMAL_OR_LOW (0.38/0.52/0.84; 0.52) | 26; mean +0.870R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.226R |
| 2025-07-31 13:00 | BUY / NY0830 | NORMAL_OR_LOW (0.71/0.88/0.68; 0.71) | 27; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-08-01 01:07 | BUY / ASIA | NORMAL_OR_LOW (0.25/0.10/0.45; 0.25) | 27; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-08-01 06:22 | SELL / LONDON | NORMAL_OR_LOW (0.37/0.55/0.17; 0.37) | 27; mean +0.846R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.342R |

**Weekly market-state read:** HIGH: 1 trades, -1.000R; NORMAL_OR_LOW: 4 trades, -0.919R.

### Week of 2025-08-04 UTC

Events: 4; high-ATR: 2; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -0.689R; trailing adaptive -0.689R; source-stop ATR-state screen -0.689R (blocked +0.000R). Cumulative: frozen +21.315R; trailing adaptive +18.729R; source-stop screen +24.375R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-08-06 06:51 | BUY / LONDON | NORMAL_OR_LOW (0.12/0.17/0.03; 0.12) | 28; mean +0.803R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-08-08 00:50 | SELL / ASIA | HIGH (0.98/0.91/0.84; 0.91) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-08-08 07:22 | BUY / LONDON | NORMAL_OR_LOW (0.73/0.70/0.76; 0.73) | 28; mean +0.803R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.689R |
| 2025-08-08 12:47 | BUY / NY0830 | HIGH (0.85/0.84/0.79; 0.84) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -0.689R.

### Week of 2025-08-11 UTC

Events: 3; high-ATR: 1; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen +1.851R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +1.851R). Cumulative: frozen +23.166R; trailing adaptive +18.729R; source-stop screen +24.375R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-08-11 00:21 | SELL / ASIA | HIGH (0.62/0.90/0.97; 0.90) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | +1.851R (blocked counterfactual) |
| 2025-08-13 13:30 | SELL / NY0830 | NORMAL_OR_LOW (0.42/0.29/0.17; 0.29) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-08-15 06:38 | SELL / LONDON | NORMAL_OR_LOW (0.15/0.09/0.01; 0.09) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** HIGH: 1 trades, +1.851R.

### Week of 2025-08-18 UTC

Events: 6; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +23.166R; trailing adaptive +18.729R; source-stop screen +24.375R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-08-19 06:23 | BUY / LONDON | NORMAL_OR_LOW (0.32/0.53/0.02; 0.32) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-08-19 12:50 | SELL / NY0830 | NORMAL_OR_LOW (0.26/0.17/0.16; 0.17) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-08-20 06:23 | BUY / LONDON | NORMAL_OR_LOW (0.20/0.18/0.02; 0.18) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-08-21 06:36 | SELL / LONDON | NORMAL_OR_LOW (0.15/0.17/0.05; 0.15) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-08-22 02:12 | SELL / ASIA | NORMAL_OR_LOW (0.21/0.03/0.48; 0.21) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-08-22 06:55 | SELL / LONDON | NORMAL_OR_LOW (0.17/0.17/0.04; 0.17) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-08-25 UTC

Events: 3; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +23.166R; trailing adaptive +18.729R; source-stop screen +24.375R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-08-26 06:31 | SELL / LONDON | HIGH (0.66/0.95/0.86; 0.86) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_CONTINUATION |
| 2025-08-29 00:20 | BUY / ASIA | NORMAL_OR_LOW (0.04/0.05/0.57; 0.05) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-08-29 06:32 | BUY / LONDON | NORMAL_OR_LOW (0.13/0.09/0.08; 0.09) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-09-01 UTC

Events: 5; high-ATR: 2; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +23.166R; trailing adaptive +18.729R; source-stop screen +24.375R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-09-01 00:29 | SELL / ASIA | HIGH (0.84/0.74/0.86; 0.84) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-09-01 13:21 | BUY / NY0830 | HIGH (0.80/0.85/0.92; 0.85) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-09-02 00:42 | BUY / ASIA | NORMAL_OR_LOW (0.39/0.40/0.46; 0.40) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-09-03 00:56 | BUY / ASIA | NORMAL_OR_LOW (0.71/0.70/0.81; 0.71) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-09-03 06:21 | BUY / LONDON | NORMAL_OR_LOW (0.61/0.80/0.72; 0.72) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-09-08 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +0.849R; trailing adaptive +0.849R; source-stop ATR-state screen +0.849R (blocked +0.000R). Cumulative: frozen +24.015R; trailing adaptive +19.578R; source-stop screen +25.225R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-09-08 01:14 | SELL / ASIA | NORMAL_OR_LOW (0.53/0.17/0.82; 0.53) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-09-09 01:10 | BUY / ASIA | NORMAL_OR_LOW (0.11/0.05/0.20; 0.11) | 29; mean +0.752R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.849R |
| 2025-09-10 06:27 | BUY / LONDON | NORMAL_OR_LOW (0.09/0.33/0.19; 0.19) | 30; mean +0.755R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-09-10 14:42 | BUY / NY0830 | NORMAL_OR_LOW (0.75/0.38/0.23; 0.38) | 30; mean +0.755R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-09-11 02:09 | SELL / ASIA | NORMAL_OR_LOW (0.14/0.05/0.18; 0.14) | 30; mean +0.755R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-09-12 06:35 | SELL / LONDON | NORMAL_OR_LOW (0.05/0.07/0.00; 0.05) | 30; mean +0.755R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.849R.

### Week of 2025-09-15 UTC

Events: 1; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +24.015R; trailing adaptive +19.578R; source-stop screen +25.225R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-09-19 07:01 | SELL / LONDON | NORMAL_OR_LOW (0.53/0.79/0.42; 0.53) | 30; mean +0.755R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-09-22 UTC

Events: 9; high-ATR: 0; completed candidate trades: 3; allowed: 3; blocked completed: 0.
This week: frozen +8.438R; trailing adaptive +8.438R; source-stop ATR-state screen +8.438R (blocked +0.000R). Cumulative: frozen +32.453R; trailing adaptive +28.016R; source-stop screen +33.663R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-09-22 00:35 | BUY / ASIA | NORMAL_OR_LOW (0.35/0.16/0.44; 0.35) | 30; mean +0.755R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.406R |
| 2025-09-22 13:01 | BUY / NY0830 | NORMAL_OR_LOW (0.68/0.79/0.68; 0.68) | 31; mean +0.718R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-09-23 07:39 | BUY / LONDON | NORMAL_OR_LOW (0.58/0.80/0.40; 0.58) | 31; mean +0.718R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +9.619R |
| 2025-09-23 13:10 | BUY / NY0830 | NORMAL_OR_LOW (0.78/0.87/0.78; 0.78) | 32; mean +0.996R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-09-24 00:22 | SELL / ASIA | NORMAL_OR_LOW (0.27/0.85/0.80; 0.80) | 32; mean +0.996R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-09-24 07:02 | SELL / LONDON | NORMAL_OR_LOW (0.26/0.42/0.65; 0.42) | 32; mean +0.996R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.775R |
| 2025-09-24 13:37 | SELL / NY0830 | NORMAL_OR_LOW (0.49/0.29/0.44; 0.44) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-09-26 01:11 | BUY / ASIA | NORMAL_OR_LOW (0.44/0.72/0.93; 0.72) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-09-26 13:38 | BUY / NY0830 | NORMAL_OR_LOW (0.74/0.56/0.34; 0.56) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_EXIT_HORIZON |

**Weekly market-state read:** NORMAL_OR_LOW: 3 trades, +8.438R.

### Week of 2025-09-29 UTC

Events: 4; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +32.453R; trailing adaptive +28.016R; source-stop screen +33.663R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-09-29 13:11 | SELL / NY0830 | NORMAL_OR_LOW (0.69/0.73/1.00; 0.73) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-09-30 13:03 | BUY / NY0830 | HIGH (0.84/1.00/1.00; 1.00) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-10-02 00:25 | SELL / ASIA | NORMAL_OR_LOW (0.23/0.18/0.53; 0.23) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-10-02 13:17 | BUY / NY0830 | NORMAL_OR_LOW (0.38/0.43/0.07; 0.38) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-10-06 UTC

Events: 7; high-ATR: 1; completed candidate trades: 2; allowed: 1; blocked completed: 1.
This week: frozen -0.082R; trailing adaptive +0.559R; source-stop ATR-state screen +0.559R (blocked -0.641R). Cumulative: frozen +32.371R; trailing adaptive +28.575R; source-stop screen +34.222R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-10-06 06:30 | SELL / LONDON | NORMAL_OR_LOW (0.72/0.52/0.46; 0.52) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-07 00:29 | BUY / ASIA | NORMAL_OR_LOW (0.62/0.47/0.54; 0.54) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-08 00:31 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.07/0.42; 0.07) | 33; mean +0.942R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.559R |
| 2025-10-08 07:05 | BUY / LONDON | NORMAL_OR_LOW (0.41/0.49/0.19; 0.41) | 34; mean +0.931R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-10-09 13:35 | BUY / NY0830 | NORMAL_OR_LOW (0.51/0.32/0.81; 0.51) | 34; mean +0.931R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-10 06:21 | SELL / LONDON | HIGH (0.79/0.85/0.93; 0.85) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | -0.641R (blocked counterfactual) |
| 2025-10-10 12:56 | SELL / NY0830 | NORMAL_OR_LOW (0.64/0.76/0.82; 0.76) | 34; mean +0.931R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** HIGH: 1 trades, -0.641R; NORMAL_OR_LOW: 1 trades, +0.559R.

### Week of 2025-10-13 UTC

Events: 7; high-ATR: 2; completed candidate trades: 3; allowed: 2; blocked completed: 1.
This week: frozen -0.515R; trailing adaptive -0.472R; source-stop ATR-state screen -0.472R (blocked -0.043R). Cumulative: frozen +31.856R; trailing adaptive +28.103R; source-stop screen +33.750R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-10-13 13:01 | SELL / NY0830 | NORMAL_OR_LOW (0.30/0.28/0.53; 0.30) | 34; mean +0.931R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-14 00:27 | SELL / ASIA | NORMAL_OR_LOW (0.22/0.37/0.33; 0.33) | 34; mean +0.931R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.543R |
| 2025-10-15 00:25 | BUY / ASIA | NORMAL_OR_LOW (0.38/0.45/0.59; 0.45) | 35; mean +0.889R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-10-15 13:01 | BUY / NY0830 | NORMAL_OR_LOW (0.63/0.70/0.57; 0.63) | 35; mean +0.889R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-10-16 00:42 | BUY / ASIA | NORMAL_OR_LOW (0.16/0.12/0.40; 0.16) | 35; mean +0.889R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.071R |
| 2025-10-17 00:39 | SELL / ASIA | HIGH (0.98/0.96/0.93; 0.96) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | -0.043R (blocked counterfactual) |
| 2025-10-17 13:01 | BUY / NY0830 | HIGH (0.92/0.95/0.99; 0.95) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |

**Weekly market-state read:** HIGH: 1 trades, -0.043R; NORMAL_OR_LOW: 2 trades, -0.472R.

### Week of 2025-10-20 UTC

Events: 7; high-ATR: 2; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +31.856R; trailing adaptive +28.103R; source-stop screen +33.750R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-10-20 00:20 | SELL / ASIA | NORMAL_OR_LOW (0.68/0.79/0.89; 0.79) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-10-21 00:50 | BUY / ASIA | NORMAL_OR_LOW (0.44/0.37/0.64; 0.44) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-22 00:35 | SELL / ASIA | HIGH (0.89/0.82/0.86; 0.86) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2025-10-22 15:09 | SELL / NY0830 | HIGH (0.88/1.00/0.96; 0.96) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2025-10-23 02:05 | SELL / ASIA | NORMAL_OR_LOW (0.51/0.38/0.54; 0.51) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-23 06:22 | BUY / LONDON | NORMAL_OR_LOW (0.22/0.28/0.36; 0.28) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-10-24 00:35 | BUY / ASIA | NORMAL_OR_LOW (0.10/0.03/0.00; 0.03) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-10-27 UTC

Events: 6; high-ATR: 2; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen +0.012R; trailing adaptive +0.012R; source-stop ATR-state screen +0.012R (blocked +0.000R). Cumulative: frozen +31.867R; trailing adaptive +28.115R; source-stop screen +33.762R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-10-27 13:06 | BUY / NY0830 | NORMAL_OR_LOW (0.49/0.45/0.23; 0.45) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-10-29 01:06 | BUY / ASIA | NORMAL_OR_LOW (0.75/0.27/0.31; 0.31) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-10-30 00:26 | BUY / ASIA | HIGH (0.88/0.94/0.68; 0.88) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-10-30 07:08 | BUY / LONDON | HIGH (0.90/0.94/0.97; 0.94) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-10-31 07:04 | BUY / LONDON | NORMAL_OR_LOW (0.07/0.19/0.07; 0.07) | 36; mean +0.866R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.012R |
| 2025-10-31 12:52 | BUY / NY0830 | NORMAL_OR_LOW (0.05/0.05/0.06; 0.05) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, +0.012R.

### Week of 2025-11-03 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +31.867R; trailing adaptive +28.115R; source-stop screen +33.762R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-11-05 01:17 | BUY / ASIA | NORMAL_OR_LOW (0.08/0.05/0.25; 0.08) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-11-05 06:54 | BUY / LONDON | NORMAL_OR_LOW (0.08/0.17/0.14; 0.14) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-11-05 15:06 | SELL / NY0830 | NORMAL_OR_LOW (0.25/0.32/0.07; 0.25) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-11-10 UTC

Events: 5; high-ATR: 3; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +31.867R; trailing adaptive +28.115R; source-stop screen +33.762R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-11-10 00:36 | BUY / ASIA | NORMAL_OR_LOW (0.21/0.35/0.49; 0.35) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-11-11 07:08 | SELL / LONDON | NORMAL_OR_LOW (0.48/0.39/0.12; 0.39) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-11-13 06:21 | SELL / LONDON | HIGH (0.82/0.97/0.99; 0.97) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2025-11-14 01:27 | SELL / ASIA | HIGH (0.70/0.93/0.98; 0.93) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2025-11-14 06:36 | SELL / LONDON | HIGH (0.65/0.84/0.89; 0.84) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-11-17 UTC

Events: 6; high-ATR: 2; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +31.867R; trailing adaptive +28.115R; source-stop screen +33.762R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-11-17 00:21 | SELL / ASIA | HIGH (0.81/0.82/0.97; 0.82) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-11-17 14:12 | SELL / NY0830 | NORMAL_OR_LOW (0.81/0.75/0.76; 0.76) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-11-18 06:35 | SELL / LONDON | NORMAL_OR_LOW (0.56/0.73/0.73; 0.73) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-11-19 07:23 | SELL / LONDON | NORMAL_OR_LOW (0.17/0.18/0.12; 0.17) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-11-20 07:16 | BUY / LONDON | NORMAL_OR_LOW (0.37/0.62/0.65; 0.62) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-11-20 16:07 | SELL / NY0830 | HIGH (0.95/0.86/0.85; 0.86) | 5; mean -0.412R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-11-24 UTC

Events: 5; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -1.309R; trailing adaptive -1.309R; source-stop ATR-state screen -1.309R (blocked +0.000R). Cumulative: frozen +30.559R; trailing adaptive +26.806R; source-stop screen +32.453R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-11-24 07:01 | BUY / LONDON | NORMAL_OR_LOW (0.17/0.10/0.21; 0.17) | 37; mean +0.843R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.309R |
| 2025-11-24 15:02 | BUY / NY0830 | NORMAL_OR_LOW (0.21/0.08/0.03; 0.08) | 38; mean +0.813R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-11-26 00:48 | BUY / ASIA | NORMAL_OR_LOW (0.00/0.02/0.30; 0.02) | 38; mean +0.813R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-11-27 13:52 | BUY / NY0830 | NORMAL_OR_LOW (0.03/0.02/0.05; 0.03) | 37; mean +0.764R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-11-28 07:24 | BUY / LONDON | NORMAL_OR_LOW (0.70/0.45/0.18; 0.45) | 38; mean +0.718R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, -1.309R.

### Week of 2025-12-01 UTC

Events: 5; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +30.559R; trailing adaptive +26.806R; source-stop screen +32.453R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-12-01 01:05 | BUY / ASIA | NORMAL_OR_LOW (0.56/0.66/0.74; 0.66) | 38; mean +0.718R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-03 00:35 | SELL / ASIA | NORMAL_OR_LOW (0.26/0.23/0.90; 0.26) | 38; mean +0.718R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-05 00:19 | BUY / ASIA | NORMAL_OR_LOW (0.01/0.07/0.17; 0.07) | 37; mean +0.761R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-05 06:31 | BUY / LONDON | NORMAL_OR_LOW (0.09/0.12/0.07; 0.09) | 37; mean +0.761R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-05 14:17 | BUY / NY0830 | NORMAL_OR_LOW (0.34/0.08/0.06; 0.08) | 37; mean +0.761R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2025-12-08 UTC

Events: 6; high-ATR: 0; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -1.000R; trailing adaptive -1.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen +29.559R; trailing adaptive +25.806R; source-stop screen +31.453R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-12-08 01:01 | BUY / ASIA | NORMAL_OR_LOW (0.28/0.30/0.47; 0.30) | 37; mean +0.761R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-08 14:34 | BUY / NY0830 | NORMAL_OR_LOW (0.52/0.43/0.23; 0.43) | 37; mean +0.761R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2025-12-10 00:50 | SELL / ASIA | NORMAL_OR_LOW (0.00/0.10/0.42; 0.10) | 37; mean +0.761R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-12-10 06:50 | SELL / LONDON | NORMAL_OR_LOW (0.13/0.17/0.14; 0.14) | 38; mean +0.714R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-12-10 14:21 | BUY / NY0830 | NORMAL_OR_LOW (0.29/0.12/0.10; 0.12) | 38; mean +0.714R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-12 01:13 | SELL / ASIA | NORMAL_OR_LOW (0.44/0.64/1.00; 0.64) | 38; mean +0.714R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2025-12-15 UTC

Events: 4; high-ATR: 1; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen -0.086R; trailing adaptive -0.086R; source-stop ATR-state screen +0.503R (blocked -0.588R). Cumulative: frozen +29.473R; trailing adaptive +25.721R; source-stop screen +31.956R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-12-16 00:58 | BUY / ASIA | NORMAL_OR_LOW (0.31/0.51/0.58; 0.51) | 38; mean +0.714R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-12-17 00:32 | BUY / ASIA | NORMAL_OR_LOW (0.04/0.46/0.67; 0.46) | 38; mean +0.714R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +0.503R |
| 2025-12-17 06:46 | SELL / LONDON | NORMAL_OR_LOW (0.54/0.42/0.55; 0.54) | 39; mean +0.709R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2025-12-19 00:22 | SELL / ASIA | HIGH (0.19/0.86/0.87; 0.86) | 4; mean -0.534R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | -0.588R |

**Weekly market-state read:** HIGH: 1 trades, -0.588R; NORMAL_OR_LOW: 1 trades, +0.503R.

### Week of 2025-12-22 UTC

Events: 5; high-ATR: 1; completed candidate trades: 1; allowed: 1; blocked completed: 0.
This week: frozen -1.000R; trailing adaptive -1.000R; source-stop ATR-state screen -1.000R (blocked +0.000R). Cumulative: frozen +28.473R; trailing adaptive +24.721R; source-stop screen +30.956R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-12-22 06:20 | BUY / LONDON | NORMAL_OR_LOW (0.52/0.60/0.34; 0.52) | 39; mean +0.709R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-22 13:55 | BUY / NY0830 | NORMAL_OR_LOW (0.46/0.28/0.39; 0.39) | 39; mean +0.709R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2025-12-24 00:14 | BUY / ASIA | NORMAL_OR_LOW (0.59/0.77/0.93; 0.77) | 39; mean +0.678R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2025-12-24 07:01 | BUY / LONDON | HIGH (0.65/0.88/0.93; 0.88) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2025-12-24 14:16 | BUY / NY0830 | NORMAL_OR_LOW (0.51/0.63/0.87; 0.63) | 39; mean +0.678R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** NORMAL_OR_LOW: 1 trades, -1.000R.

### Week of 2025-12-29 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +28.473R; trailing adaptive +24.721R; source-stop screen +30.956R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2025-12-30 13:54 | SELL / NY0830 | NORMAL_OR_LOW (0.52/0.53/0.72; 0.53) | 38; mean +0.722R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2025-12-31 14:06 | BUY / NY0830 | NORMAL_OR_LOW (0.55/0.63/0.93; 0.63) | 38; mean +0.722R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_EXIT_HORIZON |
| 2026-01-02 06:20 | SELL / LONDON | NORMAL_OR_LOW (0.04/0.12/0.13; 0.12) | 38; mean +0.722R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-01-05 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +28.473R; trailing adaptive +24.721R; source-stop screen +30.956R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-01-06 00:46 | SELL / ASIA | NORMAL_OR_LOW (0.11/0.08/0.19; 0.11) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-01-06 14:21 | BUY / NY0830 | NORMAL_OR_LOW (0.16/0.16/0.14; 0.16) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-01-07 14:22 | BUY / NY0830 | NORMAL_OR_LOW (0.67/0.36/0.57; 0.57) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-01-08 13:43 | SELL / NY0830 | NORMAL_OR_LOW (0.59/0.33/0.10; 0.33) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-01-12 UTC

Events: 1; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +28.473R; trailing adaptive +24.721R; source-stop screen +30.956R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-01-15 06:28 | BUY / LONDON | NORMAL_OR_LOW (0.80/0.92/0.77; 0.80) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-01-19 UTC

Events: 6; high-ATR: 2; completed candidate trades: 1; allowed: 0; blocked completed: 1.
This week: frozen -1.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked -1.000R). Cumulative: frozen +27.473R; trailing adaptive +24.721R; source-stop screen +30.956R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-01-19 00:22 | SELL / ASIA | HIGH (0.97/0.97/1.00; 0.97) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_CONTINUATION |
| 2026-01-19 07:11 | BUY / LONDON | NORMAL_OR_LOW (0.07/0.35/0.89; 0.35) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-01-19 14:19 | SELL / NY0830 | NORMAL_OR_LOW (0.06/0.03/0.03; 0.03) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-01-20 06:45 | SELL / LONDON | NORMAL_OR_LOW (0.51/0.37/0.08; 0.37) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-01-21 14:00 | BUY / NY0830 | NORMAL_OR_LOW (0.63/0.70/0.93; 0.70) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-01-22 00:24 | BUY / ASIA | HIGH (0.94/0.97/1.00; 0.97) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | -1.000R (blocked counterfactual) |

**Weekly market-state read:** HIGH: 1 trades, -1.000R.

### Week of 2026-01-26 UTC

Events: 7; high-ATR: 5; completed candidate trades: 2; allowed: 1; blocked completed: 1.
This week: frozen -1.212R; trailing adaptive -0.212R; source-stop ATR-state screen -0.212R (blocked -1.000R). Cumulative: frozen +26.261R; trailing adaptive +24.509R; source-stop screen +30.744R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-01-26 14:05 | SELL / NY0830 | NORMAL_OR_LOW (0.51/0.44/0.74; 0.51) | 37; mean +0.728R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.212R |
| 2026-01-27 00:24 | BUY / ASIA | HIGH (0.96/0.98/0.94; 0.96) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2026-01-28 00:20 | SELL / ASIA | NORMAL_OR_LOW (0.89/0.78/0.74; 0.78) | 37; mean +0.749R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-01-29 00:27 | SELL / ASIA | HIGH (1.00/1.00/1.00; 1.00) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |
| 2026-01-29 06:47 | BUY / LONDON | HIGH (0.83/0.96/1.00; 0.96) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RECLAIM |
| 2026-01-30 06:50 | SELL / LONDON | HIGH (0.85/0.93/0.99; 0.93) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | -1.000R (blocked counterfactual) |
| 2026-01-30 15:08 | SELL / NY0830 | HIGH (0.90/0.95/0.97; 0.95) | 5; mean -0.545R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_CONTINUATION |

**Weekly market-state read:** HIGH: 1 trades, -1.000R; NORMAL_OR_LOW: 1 trades, -0.212R.

### Week of 2026-02-02 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +26.261R; trailing adaptive +24.509R; source-stop screen +30.744R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-02-02 15:36 | SELL / NY0830 | NORMAL_OR_LOW (0.80/0.64/0.86; 0.80) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-02-04 06:19 | SELL / LONDON | NORMAL_OR_LOW (0.09/0.24/0.23; 0.23) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2026-02-05 14:07 | SELL / NY0830 | NORMAL_OR_LOW (0.41/0.31/0.41; 0.41) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2026-02-06 14:08 | BUY / NY0830 | NORMAL_OR_LOW (0.09/0.06/0.31; 0.09) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_EXIT_HORIZON |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-02-09 UTC

Events: 7; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen +3.455R; trailing adaptive +3.455R; source-stop ATR-state screen +3.455R (blocked +0.000R). Cumulative: frozen +29.716R; trailing adaptive +27.964R; source-stop screen +34.199R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-02-09 01:01 | SELL / ASIA | NORMAL_OR_LOW (0.12/0.01/0.02; 0.02) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2026-02-09 06:37 | SELL / LONDON | NORMAL_OR_LOW (0.03/0.10/0.02; 0.03) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-02-10 07:33 | SELL / LONDON | NORMAL_OR_LOW (0.04/0.06/0.02; 0.04) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-02-11 07:15 | BUY / LONDON | NORMAL_OR_LOW (0.01/0.00/0.00; 0.00) | 36; mean +0.775R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +4.328R |
| 2026-02-12 01:17 | SELL / ASIA | NORMAL_OR_LOW (0.31/0.15/0.54; 0.31) | 37; mean +0.871R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-02-12 06:16 | SELL / LONDON | NORMAL_OR_LOW (0.08/0.10/0.06; 0.08) | 37; mean +0.871R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.873R |
| 2026-02-13 06:41 | BUY / LONDON | NORMAL_OR_LOW (0.36/0.55/0.85; 0.55) | 38; mean +0.825R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, +3.455R.

### Week of 2026-02-16 UTC

Events: 4; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +29.716R; trailing adaptive +27.964R; source-stop screen +34.199R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-02-16 06:55 | BUY / LONDON | NORMAL_OR_LOW (0.09/0.22/0.25; 0.22) | 37; mean +0.770R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-02-18 06:23 | SELL / LONDON | NORMAL_OR_LOW (0.05/0.15/0.28; 0.15) | 37; mean +0.770R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2026-02-19 01:06 | SELL / ASIA | NORMAL_OR_LOW (0.23/0.15/0.23; 0.23) | 37; mean +0.770R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-02-20 00:22 | BUY / ASIA | NORMAL_OR_LOW (0.20/0.26/0.41; 0.26) | 37; mean +0.770R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-02-23 UTC

Events: 1; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +29.716R; trailing adaptive +27.964R; source-stop screen +34.199R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-02-26 13:56 | SELL / NY0830 | NORMAL_OR_LOW (0.55/0.21/0.15; 0.21) | 36; mean +0.772R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-03-02 UTC

Events: 4; high-ATR: 2; completed candidate trades: 2; allowed: 1; blocked completed: 1.
This week: frozen +0.265R; trailing adaptive +0.292R; source-stop ATR-state screen +0.000R (blocked +0.265R). Cumulative: frozen +29.981R; trailing adaptive +28.256R; source-stop screen +34.199R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-03-02 00:13 | SELL / ASIA | HIGH (0.96/0.99/0.93; 0.96) | 4; mean -0.509R | trailing: ALLOW_WARMUP; fixed: BLOCK_HIGH_ATR | +0.292R |
| 2026-03-03 00:37 | BUY / ASIA | NORMAL_OR_LOW (0.60/0.68/0.85; 0.68) | 36; mean +0.772R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-03-03 14:02 | SELL / NY0830 | HIGH (1.00/1.00/1.00; 1.00) | 5; mean -0.349R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | -0.027R (blocked counterfactual) |
| 2026-03-04 06:13 | SELL / LONDON | NORMAL_OR_LOW (0.66/0.70/0.86; 0.70) | 36; mean +0.772R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** HIGH: 2 trades, +0.265R.

### Week of 2026-03-09 UTC

Events: 2; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +29.981R; trailing adaptive +28.256R; source-stop screen +34.199R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-03-09 13:31 | SELL / NY0830 | NORMAL_OR_LOW (0.15/0.35/0.75; 0.35) | 36; mean +0.772R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-03-12 13:16 | BUY / NY0830 | NORMAL_OR_LOW (0.05/0.03/0.04; 0.04) | 35; mean +0.823R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-03-16 UTC

Events: 8; high-ATR: 4; completed candidate trades: 2; allowed: 1; blocked completed: 1.
This week: frozen +0.903R; trailing adaptive -0.598R; source-stop ATR-state screen -0.598R (blocked +1.501R). Cumulative: frozen +30.883R; trailing adaptive +27.657R; source-stop screen +33.600R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-03-16 00:52 | BUY / ASIA | HIGH (0.91/0.84/0.83; 0.84) | 5; mean -0.349R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2026-03-17 06:32 | SELL / LONDON | NORMAL_OR_LOW (0.22/0.15/0.08; 0.15) | 35; mean +0.823R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -0.598R |
| 2026-03-17 13:55 | SELL / NY0830 | NORMAL_OR_LOW (0.44/0.18/0.06; 0.18) | 36; mean +0.783R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2026-03-18 01:27 | BUY / ASIA | NORMAL_OR_LOW (0.06/0.00/0.00; 0.00) | 36; mean +0.783R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-03-18 07:18 | BUY / LONDON | NORMAL_OR_LOW (0.10/0.15/0.00; 0.10) | 36; mean +0.783R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-03-19 00:33 | BUY / ASIA | HIGH (0.80/0.82/0.99; 0.82) | 5; mean -0.349R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2026-03-20 00:23 | BUY / ASIA | HIGH (0.68/0.83/0.94; 0.83) | 5; mean -0.349R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | +1.501R (blocked counterfactual) |
| 2026-03-20 13:21 | SELL / NY0830 | HIGH (0.83/0.87/0.83; 0.83) | 5; mean -0.349R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: STRUCTURE_INVALIDATED |

**Weekly market-state read:** HIGH: 1 trades, +1.501R; NORMAL_OR_LOW: 1 trades, -0.598R.

### Week of 2026-03-23 UTC

Events: 4; high-ATR: 1; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +30.883R; trailing adaptive +27.657R; source-stop screen +33.600R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-03-23 06:16 | SELL / LONDON | HIGH (0.82/0.98/0.98; 0.98) | 5; mean -0.349R | trailing: BLOCK_NONPOSITIVE_TRAILING; fixed: BLOCK_HIGH_ATR | no entry: NO_RETEST |
| 2026-03-24 12:53 | SELL / NY0830 | NORMAL_OR_LOW (0.66/0.60/0.63; 0.63) | 35; mean +0.831R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_CONTINUATION |
| 2026-03-25 06:19 | SELL / LONDON | NORMAL_OR_LOW (0.13/0.16/0.36; 0.16) | 35; mean +0.831R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-03-27 06:21 | BUY / LONDON | NORMAL_OR_LOW (0.05/0.05/0.33; 0.05) | 35; mean +0.831R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

### Week of 2026-03-30 UTC

Events: 8; high-ATR: 0; completed candidate trades: 2; allowed: 2; blocked completed: 0.
This week: frozen +0.363R; trailing adaptive +0.363R; source-stop ATR-state screen +0.363R (blocked +0.000R). Cumulative: frozen +31.246R; trailing adaptive +28.020R; source-stop screen +33.963R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-03-30 00:20 | SELL / ASIA | NORMAL_OR_LOW (0.46/0.22/0.33; 0.33) | 35; mean +0.831R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-03-30 06:31 | BUY / LONDON | NORMAL_OR_LOW (0.12/0.33/0.38; 0.33) | 35; mean +0.831R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2026-03-31 06:23 | SELL / LONDON | NORMAL_OR_LOW (0.29/0.61/0.28; 0.29) | 36; mean +0.781R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2026-03-31 13:51 | BUY / NY0830 | NORMAL_OR_LOW (0.61/0.20/0.46; 0.46) | 36; mean +0.781R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-04-01 00:35 | BUY / ASIA | NORMAL_OR_LOW (0.40/0.29/0.28; 0.29) | 36; mean +0.781R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2026-04-01 12:38 | BUY / NY0830 | NORMAL_OR_LOW (0.18/0.41/0.15; 0.18) | 36; mean +0.781R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | +1.363R |
| 2026-04-02 00:44 | BUY / ASIA | NORMAL_OR_LOW (0.12/0.12/0.03; 0.12) | 37; mean +0.796R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |
| 2026-04-02 13:28 | SELL / NY0830 | NORMAL_OR_LOW (0.70/0.68/1.00; 0.70) | 37; mean +0.796R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: PENDING_RECLAIM_HORIZON |

**Weekly market-state read:** NORMAL_OR_LOW: 2 trades, +0.363R.

### Week of 2026-04-06 UTC

Events: 5; high-ATR: 0; completed candidate trades: 3; allowed: 3; blocked completed: 0.
This week: frozen -3.000R; trailing adaptive -3.000R; source-stop ATR-state screen -3.000R (blocked +0.000R). Cumulative: frozen +28.246R; trailing adaptive +25.020R; source-stop screen +30.963R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-04-06 00:18 | BUY / ASIA | NORMAL_OR_LOW (0.73/0.51/0.69; 0.69) | 37; mean +0.796R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2026-04-06 07:06 | BUY / LONDON | NORMAL_OR_LOW (0.12/0.45/0.23; 0.23) | 38; mean +0.749R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-04-07 07:14 | BUY / LONDON | NORMAL_OR_LOW (0.13/0.29/0.03; 0.13) | 38; mean +0.749R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-04-07 13:05 | SELL / NY0830 | NORMAL_OR_LOW (0.71/0.47/0.23; 0.47) | 38; mean +0.749R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |
| 2026-04-10 00:21 | SELL / ASIA | NORMAL_OR_LOW (0.02/0.01/0.07; 0.02) | 39; mean +0.704R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | -1.000R |

**Weekly market-state read:** NORMAL_OR_LOW: 3 trades, -3.000R.

### Week of 2026-04-13 UTC

Events: 3; high-ATR: 0; completed candidate trades: 0; allowed: 0; blocked completed: 0.
This week: frozen +0.000R; trailing adaptive +0.000R; source-stop ATR-state screen +0.000R (blocked +0.000R). Cumulative: frozen +28.246R; trailing adaptive +25.020R; source-stop screen +30.963R.

| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |
|---|---|---|---:|---|---|
| 2026-04-14 06:20 | BUY / LONDON | NORMAL_OR_LOW (0.01/0.01/0.04; 0.01) | 38; mean +0.701R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RETEST |
| 2026-04-15 06:34 | SELL / LONDON | NORMAL_OR_LOW (0.07/0.32/0.16; 0.16) | 38; mean +0.701R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: STRUCTURE_INVALIDATED |
| 2026-04-16 13:42 | BUY / NY0830 | NORMAL_OR_LOW (0.14/0.03/0.00; 0.03) | 38; mean +0.701R | trailing: ALLOW_POSITIVE_TRAILING; fixed: ALLOW_NORMAL_OR_LOW | no entry: NO_RECLAIM |

**Weekly market-state read:** no completed trades in either state.

## What the sequence says

The trailing-mean ATR policy selected 64 attempts for +25.020R and blocked 44 trades worth +3.226R, so it is not adopted. The simpler fixed high-ATR lock selected 93 attempts for +30.963R; its 15 blocked high-ATR attempts summed to -2.717R (first/second chronological halves -1.611R / -1.106R). This is a promising research lead, not validation: only 15 high-ATR attempts and the cutoff came from previously inspected data. The per-trade table exposes decisions and weekly cumulative paths. Do not retune against these same weeks; independent proof needs an untouched sample.
