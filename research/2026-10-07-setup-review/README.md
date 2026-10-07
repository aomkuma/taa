# Setup review research scripts (2026-10-07)

Prototypes behind [docs/SETUP_REVIEW.md](../../docs/SETUP_REVIEW.md). Not part of the product, not linted, not
tested: TAA-L707 turns them into a supported `app.cli research` harness. Everything is read-only on history and
writes only to `data/research/` (git-ignored). All results are hypothetical, bar-based replays.

| Script | What it does |
|---|---|
| `run_family.sh NAME STRATEGIES DETECTORS [CONFIG]` | one-year `advisory replay` per symbol (4 in parallel) into `data/research/fam_NAME_SYMBOL.db`; needs M15/H1 (or the config's timeframes) and M5 history in `data/history`. Four processes need ~2 GB of commit memory each with the chart detectors: run two at a time unless the page file is larger |
| `analyze_replays.py "fam_light_*"` | per strategy: mean R with a bootstrap CI, half-years, symbols; nearer targets; HTF alignment; how losers lost |
| `diagnose_breakout.py` | re-simulates `setup_breakout` on M5 (market vs retest entries) and splits by context at the signal bar |
| `baseline_breakout.py` | the same signals as traded, faded and in a random direction (information and cost drag) |
| `walkforward_breakout.py` | context × direction, then single-condition rules chosen on Oct-Mar and measured on Apr-Oct |
| `hypotheses.py STRATEGY` | groups A (exits), B (stop size, costs), C (entry location and time), D (retest with a wide stop, re-entry) |

Families used:

```bash
# light (fast): ~2.5 h on this machine for a year of M15
research/2026-10-07-setup-review/run_family.sh light \
  "example_trend_pullback,setup_breakout,setup_elliott_wave,setup_fib_pullback,setup_smc_reversal" \
  "volatility.donchian,sessions.asian_breakout,sessions.open_breakout,elliott.wave,fib.golden_zone,smc.fvg,smc.liquidity_sweep,structure.bos_choch"
# heavy (chart patterns, harmonics): not run yet (ran out of commit memory with four processes)
research/2026-10-07-setup-review/run_family.sh heavy \
  "setup_pattern_breakout,setup_neckline_break,setup_harmonic_prz" \
  "chart.double,chart.triple,chart.head_shoulders,chart.triangle,chart.wedge,chart.rectangle,chart.flag,chart.cup_handle,harmonic.abcd,harmonic.bat,harmonic.butterfly,harmonic.crab,harmonic.cypher,harmonic.gartley,harmonic.shark"
# a timeframe variant: a copy of config.yaml with timeframes.entry H1 and timeframes.higher H4
sed -e 's/^  higher: H1 .*/  higher: H4/' -e 's/^  entry: M15 .*/  entry: H1/' config.yaml > data/research/config_h1.yaml
research/2026-10-07-setup-review/run_family.sh lightH1 "<light strategies>" "<light detectors>" data/research/config_h1.yaml
```

Run the replays at idle priority while the DEMO engine runs (they otherwise slow its loop), and never next to
a full test run (memory).
