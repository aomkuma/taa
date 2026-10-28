# Checklist

- [x] Confirm this is isolated research only; preserve TR1/TR3/TR4 and all execution paths.
- [x] Fix eligible data sources, selected cohort and seen-data boundary before measuring.
- [x] Predefine checkpoint calculations and directional OHLC treatment in `PLAN.md`.
- [x] Verify the frozen prediction row count, action counts, outcome labels and entry-date boundary.
- [x] Implement a reproducible diagnostic script in this folder only.
- [x] Assert bars are complete, post-entry, and no later than each checkpoint or actual exit.
- [x] Calculate 15/30/60/120-minute path summaries, target-touch rates, and M5 directional structure counts.
- [x] Check coverage and missing-bar effects; inspect cohort and split counts.
- [x] Write results, caveats, and a non-promotion decision to `RESULTS.md`.
- [x] Run script twice and verify deterministic outputs; Python compile check passes.
- [x] Create the quantitative summary in the workspace Canvas.
- [ ] Verify the host Canvas TypeScript/render diagnostics; this environment exposed no Canvas compiler/check tool.
- [ ] Report the current work status and next valid evidence step clearly.
