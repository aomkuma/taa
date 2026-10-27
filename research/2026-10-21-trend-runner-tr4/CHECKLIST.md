# TR4 checklist

- [x] Create a separate TR4 research directory; leave TR1/TR2/TR3 and the existing shadow journal untouched.
- [x] Freeze the candidate as the single 80/70 MTF percentile pause/resume gate; do not tune from the development result.
- [x] Define causal M15/M30/H1 ATR(14), 120-hour-equivalent percentile windows, composite, and hysteresis semantics.
- [x] Set the forward-only boundary and prohibit using locked/seen outcomes as validation.
- [x] Specify paired evaluation against TR3 on identical forward opportunities; slippage excluded.
- [x] Add an isolated, testable gate implementation with tests for boundary, state, ordering, and causality.
- [ ] Confirm valid forward ATR inputs and TR3 shadow decisions are available after 2026-10-21 00:00 UTC.
- [ ] Collect enough forward rows for the frozen TR3 cold-start requirements; keep TR4 observational.
- [ ] Reach 100 scored opportunities and 60 scored trading days after cold start.
- [ ] Run the one-time paired evaluation and audit integrity, concentration, drawdown, and uncertainty.
- [ ] Decide whether to retain, reject, or request a separately scoped integration review; never auto-promote.
