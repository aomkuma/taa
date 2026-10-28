# Why does the sell side lose so distinctly? (owner's question, 2026-10-27)

Read-only investigation, shared with the research session, which is measuring the owner's momentum
hypothesis in parallel. Write only `research/2026-10-26-three-bots/SELLS_REPLY.md`. Change no code.

## The fact to explain

248 trades, 2023-09 .. 2026-10, exits stripped to stop-and-target (`geometry_trades.csv`,
`edge_trades.csv` - the latter has `side`, `regime`, `window`, `mae_r`, `mfe_r`, `fitted`):

| bot | regime | side | trades | R a trade |
|---|---|---|---|---|
| RANGE | bear | BUY | 17 | **+0.329** |
| RANGE | bear | SELL | 5 | -0.817 |
| RANGE | bull | BUY | 13 | -0.310 |
| RANGE | bull | SELL | 25 | **-0.810** |
| DOWN | bear | SELL | 24 | +0.164 |
| DOWN | bull | SELL | 49 | -0.111 |
| UP | bear | BUY | 11 | +0.224 |
| UP | bull | BUY | 76 | -0.118 |

A range break to the downside loses **-0.81 R a trade in both regimes**. That is the sharpest number in
the whole study and it does not depend on the regime, which makes it a property of the sell side itself,
not of the market phase.

## What to find out

**The cause, with numbers.** Candidate explanations, in no order - test the ones you can, say which you
could not and why:

1. **Drift.** Gold went 1,900 → 4,380 over these years. Measure the unconditional drift over the same
   holding horizon the trades had: from a random/every M5 bar, the mean move over N minutes, by regime.
   How much of -0.81 R is simply fighting that drift?
2. **Asymmetric follow-through at a level.** The knowledge base (F-entry at line 668 of
   `app/strategy/kb.yaml`) measured that a swept LOW is more often a fake than a swept HIGH, and sweeps
   deeper. If a downward break of a range is more often a fake than an upward one, that is the cause.
   Measure it on the H4 boxes the range bot used.
3. **Stop placement.** A sell's stop sits above the box, where stop clusters and sweeps live. Compare the
   MAE distribution of sells and buys: do sells get touched at the stop by a thinner margin?
4. **Where the target is.** Compare `mfe_r` for sells and buys: do sells reach less far before turning?
5. **Spread and cost asymmetry.** The spread is taken once, the same for both sides; confirm that is true
   in the harness (`bots.settle`) and quantify it as a share of the risk per side.
6. **Time of day.** Do sells cluster in a window that is bad for any side?

Also test anything you think of that we have not listed.

## How to answer

- One cause per section: the claim, the measurement that supports it, the number, and how much of the
  -0.81 R it accounts for. Add the measurements up and say what is left unexplained.
- Say which explanations you **ruled out** and with what number - a ruled-out cause is as useful here.
- Beware the small cells: RANGE bear SELL is 5 trades. Say where you are reasoning from too little data.
- Finish with: if this is real, what should the system do about the sell side - and what would prove it
  before we change anything.
- Use `.venv\Scripts\python.exe`; the system Python has no pandas.
