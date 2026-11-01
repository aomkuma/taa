# OCO side aligned with six-hour drift

## Result

Aligning the edge side with the net six-hour drift lowered trade count but did not improve the result enough.

- Development: 36 trades, 1 target, net **-24.64R**; folds: -9.39R, +1.90R, -17.15R.
- Validation: 19 trades, 2 targets, net **-11.83R**.

The test kept the prior-close-inside-VA and efficiency <=0.25 gates. In a rising 72-bar close path it allowed VAL buys only; in a falling path it allowed VAH sells only. The rule failed the trade-count and fold/validation requirements.
