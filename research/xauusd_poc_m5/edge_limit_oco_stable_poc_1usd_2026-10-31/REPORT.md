# Stationary-cluster OCO with $1.00 POC drift

## Result

- Development: 51 trades, 5 targets, net **-20.88R**; folds: -6.98R, -14.01R, +0.10R.
- Validation: 28 trades, 3 targets, net **-1.13R**; PF-R 0.95.

Relaxing the half-session POC drift allowance from $0.50 to $1.00 materially increased the sample and brought validation near breakeven, but development remained negative in two folds and overall. The method is not selected. Protocol: `PROTOCOL.md`.
