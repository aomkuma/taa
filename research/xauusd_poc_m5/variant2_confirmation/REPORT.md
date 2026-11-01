# Variant 2 comparison on a new five-session sample

**Run date:** 2026-10-31 (Asia/Bangkok)
**Window:** active-session UTC dates 2026-09-24 through 2026-10-06; Bangkok dates 2026-09-25, 2026-09-30, 2026-10-01, 2026-10-02 and 2026-10-07 passed the quote-coverage rule. Four other candidate sessions in that window failed coverage and were excluded.

## Rules compared

Both runs use the same previous-session POC/VAL/VAH from midpoint quote-update counts in $0.10 bins. Only VAL long and VAH short are traded; target is POC. Both use the original wick-based stop and the same one-position / one-entry-per-edge constraints.

- **Baseline:** edge touch followed by one M5 close back inside value; enter at the next quote.
- **Variant 2:** require the immediately following M5 bar to also close inside value; additionally, two consecutive M5 closes beyond an edge disable fading that edge for the rest of the session. Enter after the confirmation close.

## Results on identical covered sessions

| Version | Trades | Wins | Stops | Net points per 1 oz | Profit factor |
|---|---:|---:|---:|---:|---:|
| Baseline | 6 | 1 | 5 | +3.35 | 1.21 |
| Variant 2 | 2 | 0 | 2 | -2.50 | 0.00 |

Variant 2 cut trades from 6 to 2 but did not improve this sample. It filtered out four baseline trades: three losers totaling -12.26 points and one winner of +19.41 points. The skipped winner was a VAL long on Bangkok 2026-10-02. Price had already closed below VAL twice, so the all-session acceptance ban blocked the later reclaim; its immediate next M5 close also fell back below VAL. This is direct evidence that the combined filter can suppress a successful recovery as well as failed fades.

The two trades retained by Variant 2 were both stopped: a VAH short on Bangkok 2026-10-02 (-0.82 points; baseline version of that signal lost -0.58) and a VAL long on 2026-10-07 (-1.68; baseline lost -3.22). Later entry reduced the latter loss but did not turn either into a winner.

## Reading

This first test does **not** show that the proposed combined adjustment helps. It does show fewer trades and smaller losses on two retained entries, while missing the sample's only large winner. Because confirmation and the acceptance ban were combined, their separate effects cannot be identified from this comparison. Do not treat this small result as a performance conclusion.

The next clean test should compare the two filters separately on additional untouched sessions. In particular, replace the permanent all-session ban only if a separate preregistered test supports a temporary suspension followed by a fresh reclaim/retest; do not tune this rule to recover the 2026-10-02 winner.

Profile activity is a broker-specific quote-update proxy, not centralized executed XAUUSD volume. P&L includes the bid/ask spread, but excludes commission and extra slippage.

## Artifacts

- `PROTOCOL.md`: rules and expectation written before calculating results
- `run_edge_v2.py`: Variant 2 simulation
- `baseline_same_window/`: unchanged edge-only baseline
- `daily_levels.csv`, `trades.csv`, `summary.csv`: Variant 2 outputs
- `baseline_signal_filter_audit.csv`: how the new filters treated each baseline trade signal
- `session_coverage.csv`: coverage for the nine candidate sessions
