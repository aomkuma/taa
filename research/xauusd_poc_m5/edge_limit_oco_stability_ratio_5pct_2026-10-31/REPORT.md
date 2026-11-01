# POC stability normalized to value-area width

## Result

A relative definition of POC stability (older/recent 3h POC distance <=5% of current six-hour VA width) still failed development consistency.

- Development: 44 trades, 3 targets, net **-30.62R**; folds: -11.24R, -12.09R, -7.29R.
- Validation: 18 trades, 3 targets, net **+10.60R**.
- All three development folds were negative; validation sample is below the 20-trade development minimum and was inspected in related work.

This scale-normalized gate is positive only in the later validation block and does not establish a robust method. Protocol: `PROTOCOL.md`.
