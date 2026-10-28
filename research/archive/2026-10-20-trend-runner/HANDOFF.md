# TREND-RUNNER (TR1) handoff

Status: round 1 finished and marked **FAIL**. Research is isolated in this directory. Nothing was added to
`app/strategy`, configuration, database state, DEMO or LIVE, and no PLAN-1/Setup OWN source was imported or edited.

## What was built

- A guarded P1/P2 data path with the exam locked.
- Causal UTC M1/M5/M15/H1 bars, MT5 ATR, confirmed fractals and DST-aware session anchors.
- Spread-aware raw-tick entries, gap stops, ordered equal-time quotes and four exit families.
- The selected setup: 0.25 H opening impulse, first causal M1 pullback/continuation, one third at +1R and two thirds
  on a M5 structure trail that graduates to M15 after +3R.
- A common frozen P1/P2 runner with SHA-256 enforcement, independent entry/exit replay, mutation harnesses and chart
  audits.

## Honest result

- P1: 138 trades, +0.265R/trade, +192.92 USD at 0.01 lot.
- P2: 142 trades, +0.088R/trade, +84.20 USD at 0.01 lot.
- Frequency is about 2.15 trades per scheduled weekday in both parts.
- P2 fails the required +0.15R/trade gate. The exam was not opened.
- P1 was concentrated in London and a +16.424R outlier; P2 shifted toward Asia/NY and buys. The fixed trail does not
  identify persistent flow consistently enough.

## Evidence map

- Detailed plan and checklist: `PLAN.md`, `CHECKLIST.md`
- Data foundation: `FOUNDATION.md`
- Entry definitions/results: `OPPORTUNITY_ROUND_1.md`, `OPPORTUNITY_FINDINGS_P1.md`
- Exit definitions/results: `EXIT_DESIGN_P1.md`, `EXIT_FINDINGS_P1.md`
- Frozen rule and hashes: `FROZEN_ROUND_1.md`, `freeze_manifest.json`
- Complete validation: `VALIDATION_ROUND_1.md`
- Visual audit: `CHART_AUDIT_P1.md`, `charts_p1/audit_contact_sheet.svg`
- Frozen artifacts: `frozen_entries_p1.parquet`, `frozen_results_p1.parquet`, `frozen_entries_p2.parquet`,
  `frozen_results_p2.parquet`
- Independent replay reports: `out_verify_opportunities_p1.txt`, `out_verify_exits_p1.txt`,
  `out_verify_frozen_p2.txt`

## Verification status

- 58 unit tests pass and ruff is clean.
- 14/14 foundation, 8/8 opportunity and 9/9 exit mutants were caught.
- Three real-data truncation cuts passed 392,801 bar/ATR, 175,832 pivot and 3,285 entry-cell comparisons.
- Independent P1 replay passed all 364 opportunity rows and 552 exit rows.
- Independent P2 replay passed 2,272 entry-field and 5,680 exit-field checks.
- Post-validation frozen hashes still match. Latest P2 tick opened: 2026-04-17. No exam artifact exists.

## Stop boundary and possible next round

Do not promote TR1 round 1, switch to the best P2 control, tune it on P2, open the exam or integrate it with PLAN-1.

The next permitted hypothesis is that runner activation needs a present-time higher-timeframe-flow and open-space
gate, not merely fixed price progress plus a local pivot. It must be written as a new round before implementation and
must use a genuinely new validation slice; the already-seen P2 can be diagnostic/design evidence but cannot judge
that new rule.

No git commit was created. Existing unrelated working-tree changes were left untouched.
