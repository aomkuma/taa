# TR3 pre-forward profit robustness audit

Verdict: **FRAGILE_POSITIVE**.

This is diagnostic safe-design evidence only. The historical exam was not opened and the Champion was not changed.

## Observed path

- 83 executed trades from 210 scored opportunities.
- +17.702R total and +0.213R/trade.
- Maximum drawdown 13.327R; longest underwater span 42 executed trades.
- Profit factor 1.416; payoff ratio 3.103; win rate 31.3%.
## Fragility

- Removing the best three trades leaves -16.893R.
- Top three trades equal 195.4% of observed net profit.
- Rolling 20-trade expectancy: minimum -0.627R, median +0.238R; 70.3% of windows were positive.
- Profitable months: 3/5; directions: 1/2; sessions: 3/3.

## Resampling uncertainty

- IID 95% mean interval: [-0.267, +0.818]R; positive-total probability 76.1%.
- Moving-block 95% mean interval: [-0.279, +0.779]R; positive-total probability 77.6%.
- Moving-block simulated drawdown median/95th/99th: 14.412/28.045/35.581R.

## Interpretation

Observed expectancy is positive, but robustness still depends on the resampled lower bound, best-trade removal, and rolling-window stability. Hypothetical slippage stress was excluded by user direction. Forward shadow collection is justified; promotion or capital deployment is not.

## Group cuts

### month

  month  trades   total_r    mean_r
2025-12      25 12.428978  0.497159
2026-01      20  9.043131  0.452157
2026-02       6 -3.291190 -0.548532
2026-03      19 -3.412750 -0.179618
2026-04      13  2.933414  0.225647

### direction

direction  trades   total_r    mean_r
      BUY      53 20.775697  0.391994
     SELL      30 -3.074114 -0.102470

### session

session  trades  total_r   mean_r
   ASIA      26 8.566238 0.329471
 LONDON      27 5.975607 0.221319
 NY0830      30 3.159737 0.105325
