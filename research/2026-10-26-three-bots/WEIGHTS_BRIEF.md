# Measure what each reading is worth (2026-10-27, night)

Write ONLY `research/2026-10-26-three-bots/weights.py` and `WEIGHTS.md`. Nothing else: another session
is in `app/` and `docs/` right now. No commit, no push, no `.env`, no `config.yaml`.
Use `.venv\Scripts\python.exe`.

## Why

The three gold bots decide with 6, 6 and 3 pass/fail gates out of ~132 measures the system can compute,
and weigh none of them. The owner's standing rule (2026-10-23): *"no entry on one or a few parameters;
combine every component learned, weighted."* The vessel exists and is unused - read
`app/strategy/weighing.py` (Weight / Scale / score). Your job is the CONTENTS: which readings carry
anything, and how much. Not the wiring.

## The data, already produced - do not regenerate

`research/2026-10-26-three-bots/momentum_trades.csv` - 239 trades of the SHIPPED bots, 2023-09..2026-10-24.
Columns: bot, side, at, r, out, mae_r, mfe_r, risk, fitted, regime, window, mom_H1, mom_H4, mom_D1.
`fitted` True = inside the window the parameters were fitted on (2025-10-20..2026-10-24), False = never seen.

Read first: `RULES_LOCKED.md` (rule set 2 - the frozen rule and the standard of evidence expected), then
`momentum.py` and `geometry.py` to see how readings are taken point-in-time.

## Deliver

1. `weights.py` - for every candidate reading available AT THE DECISION BAR: how well it separates
   winners from losers, AND its effect on mean R, reported separately for the fitted and never-seen
   halves with each half's n.
2. `WEIGHTS.md` - the table and a proposed set of weights.

## The rules this is judged on

- **Point-in-time only.** Every reading from a bar CLOSED before that trade's `at`. The stored history is
  stamped by each bar's OPEN (`app/engine/ai_trader.to_frame`); the app's live frames by the CLOSE.
  Getting this backwards cost a whole afternoon on 2026-10-27 - a one-hour lookahead inverted which
  timeframe appeared to matter. Any reading you add that is not already in the CSV must have its timing
  proven by a hand-worked case in the file.
- Never an aggregate without both halves beside it, each with its n.
- A reading whose sign FLIPS between the halves is not a candidate, however good its average. Say so for
  each one you test.
- Separating winners from losers is NOT predicting net R. Report both; prefer R.
- Say which candidates overlap (correlate) - related readings double-count the same evidence.
- You are choosing among many candidates on data you can see. Estimate what best-of-N selection is worth
  by itself if you can.
- If a number is odd - a count that cannot be right, a rate that does not move - STOP and explain it
  rather than writing a story around it. Three separate failures that day announced themselves that way
  and were talked past.

End with: the weights you propose, what you would NOT take and why, and the one thing to measure next.
