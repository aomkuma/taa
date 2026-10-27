# Post-stop recovery and fixed M5 re-entry study

**Decision: the exact immediate M5-reclaim + 1R-stop version failed; this does not reject every re-entry idea.** The 1.5R-stop sensitivity improved substantially but remained negative. Neither version is approved for the strategy or for trading. The wider-stop result is post-hoc exploration on the same data, not confirmation.

## Study definition

Population: 632 frozen walk-forward opportunities stopped before a preceding +1R touch. The locked exam and all post-shadow data were excluded. The implementation follows the written trigger: first completed M5 close back across the original entry in the original direction, then next M1 open. The primary version uses a 1-original-R stop, 2R target, and 120-minute time exit. Entry includes recorded spread; slippage is excluded. Audit found no same-M1 stop/target collisions, so the stop-first ambiguity convention did not cause the negative result. No evident timing/side/spread implementation error was found in the rule as specified; however, M1 OHLC still limits fill-order certainty.

## Re-entry result

- M5 closed back through the original entry in 514 / 632 eligible cases (81.3%); median wait was 33 minutes (IQR 14-80).
- 514 re-entry attempts completed: **-64.32R** total, **-0.125R per attempt**, 29.8% winners, median result -1.00R, median holding time 10 minutes.
- Exits: {'STOP_INTRABAR': 353, 'TARGET_2R': 143, 'TIME_120M': 13, 'STOP_GAP': 4, 'TARGET_GAP': 1}.
- Same-M1 stop/target ambiguous cases: **0**. Thus conservative collision handling did not explain this loss.

| Stop-event year | Attempts | Mean R/attempt | Total R | Win rate |
|---|---:|---:|---:|---:|
| 2023 | 36 | -0.332R | -11.96R | 22.2% |
| 2024 | 199 | -0.162R | -32.30R | 29.1% |
| 2025 | 229 | -0.085R | -19.51R | 30.6% |
| 2026 | 50 | -0.011R | -0.55R | 34.0% |

| Chronological half | Attempts | Mean R/attempt | Total R |
|---|---:|---:|---:|
| earlier | 257 | -0.187R | -48.18R |
| later | 257 | -0.063R | -16.14R |

The 1R-stop candidate is negative in both chronological halves and all calendar-year cuts; the 2026 cut is partial. This establishes failure of this exact rule on this sample, not failure of the entire setup family.

## Stop-width audit: a possible fix, not a pass

Of the 357 baseline stop-outs, **155 (43.4%)** later touched +2R from the re-entry within the remaining observation horizon. Across those later-target paths, median worst adverse excursion was -1.05R; 65.7% stayed within 1.5R adverse and 78.8% within 2R. This suggests stop width may contribute, but is not proof that a wider stop is the right remedy.

An exploratory sensitivity widened only the stop to 1.5 original-R while keeping the target at +2 original-R, the trigger, entry, and time exit unchanged. This changes the payoff ratio to 2R reward / 1.5R risk. It improved mean return from -0.125 to **-0.049 original-risk-R per attempt** (-0.033 per 1.5R actually risked), and win rate from 29.8% to 42.2%, but still lost **-25.39 original-risk-R total**. This is a useful clue, not a profitable or validated variant.

| 1.5R-stop cut | Attempts | Mean original-risk R | Total original-risk R | Win rate |
|---|---:|---:|---:|---:|
| 2023 | 36 | -0.430R | -15.49R | 30.6% |
| 2024 | 199 | +0.031R | +6.20R | 45.2% |
| 2025 | 229 | -0.088R | -20.05R | 40.6% |
| 2026 | 50 | +0.079R | +3.95R | 46.0% |

| Chronological half | Attempts | Mean original-risk R | Total original-risk R |
|---|---:|---:|---:|
| earlier | 257 | -0.071R | -18.32R |
| later | 257 | -0.027R | -7.07R |

The wider-stop sensitivity remains mixed across years and negative in both chronological halves. Because it was selected after seeing the baseline losses, these cuts are diagnostic only and must not be used to claim a robust edge.

## How often did the original direction recover?

These are event-path percentages from the original entry price after the initial stop, not re-entry returns. Touching a level uses M1 OHLC and does not prove a tradable fill.

| Minutes after stop | Events with full horizon | Reclaimed original entry | Touched original +1R | Touched original +2R |
|---:|---:|---:|---:|---:|
| 15 | 632 | 39.6% | 12.5% | 4.3% |
| 30 | 632 | 55.4% | 24.8% | 12.2% |
| 60 | 632 | 69.3% | 43.7% | 28.0% |
| 120 | 632 | 76.4% | 55.7% | 41.9% |
| 240 | 632 | 81.3% | 64.4% | 51.4% |
| 480 | 632 | 88.9% | 75.6% | 65.5% |

By original entry window, the M5-reclaim rate and 60-minute +1R rate were:

| Window | Stop events | M5 reclaim | Original +1R within 60m |
|---|---:|---:|---:|
| ASIA | 254 | 82.3% | 44.5% |
| LONDON | 218 | 83.9% | 38.1% |
| NY0830 | 160 | 76.2% | 50.0% |

## Next development decision

Do not add the tested immediate-reclaim versions to the strategy: 1R stop failed, while 1.5R stop improved but remained negative. Do not conclude that all re-entry or trend-following logic is unusable: later continuation after the stop was common enough to justify one carefully isolated follow-up hypothesis. The next research branch should test whether waiting for a retest/continuation after the M5 reclaim and placing a stop beyond local structure avoids premature stop-outs. Specify and freeze one rule before measuring it; use untouched forward-shadow observations for confirmation. Keep the current strategy frozen and separate; no repeated tuning on this inspected historical sample.

## Limits

M1 OHLC cannot recover exact intra-minute order or executable stop/target fills. The M5 re-entry idea was prompted by already observed trade-journal outcomes, so this replay is not independent validation. Events may overlap; total R is event-level and not a portfolio equity curve. Tick-level price sequence is unavailable across most of the tested period.
