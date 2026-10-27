# Review: the H4 edge-side gate, now live on a DEMO account (2026-10-27, evening)

You built `edge_side.py` from DEV_SPEC_3 as a **D1 regime label**. That spec was written from measurements
that turned out to be wrong - you found the cause yourself: the research scripts ran `bots.P()` instead of
the shipped parameters, and had a one-hour lookahead. Corrected, the measurement says **H4 is the frame
that carries the edge** (correlation with the trade's R: H4 +0.156, H1 +0.048, D1 +0.030), and the rule is
a **quantity**, not a label.

So I rewrote your module and rewired both strategies. **This is running on the owner's DEMO account right
now**, so a mistake here places real orders on a real (demo) broker. Review it as such.

Read-only. Write only `research/2026-10-26-three-bots/REVIEW_FINDINGS_3.md`. Use `.venv\Scripts\python.exe`.

## What changed

- `app/strategy/edge_side.py` - rewritten: `resample_from_h1`, `edge_lean` (signed, frame-parameterised,
  default H4), `behind`, and `edge_side` kept as a thin shortcut.
- `app/strategy/trend_box.py` and `range_break.py` - the `require_edge_side` gate now tests
  `behind(edge_lean(...), own_side) >= 0` instead of comparing a `Side`.
- `tests/unit/test_strategy_edge_side.py` - rewritten (11 cases). Your trend/range gate tests were
  repointed at `edge_lean`.
- `config.yaml` - `require_edge_side: true` on all three bots of the `three_bots` lane. **Live.**

## What to check, hardest first

1. **The open/close convention.** App frames are stamped at the bar's CLOSE; the research history is
   stamped at the OPEN. `resample_from_h1` shifts back one hour before resampling. Prove it is right in
   the APP's direction - an hour of lookahead here would make every number since meaningless, and that is
   exactly the bug you caught this afternoon in the other direction. Check `(index + hours) <= at` too.
2. **Does the gate ever let a trade through when it should not?** `edge_lean` returns `None` for an
   unreadable frame and both strategies treat that as refusal. Find any path where `None`, `NaN`, a zero
   ATR, a short frame, or a missing H1 frame could end as a trade rather than a hold.
3. **Is the ATR the same ruler the app trades with?** I call `app.indicators.volatility.atr`. Check the
   seeding and that 64 closed H4 bars (50 mean + 14 ATR) is actually enough for a non-NaN answer, and
   that `warmup_bars` supplies them in every lane that can switch this on.
4. **Do my tests bite?** For each of the 11 cases, break the one production line it covers, run that case,
   confirm it fails, restore. Report each. **Look especially for my own worst habit:** a test helper that
   re-implements production logic instead of calling it. `expected_lean` in the test file reuses
   `resample_from_h1` - judge whether that makes the test circular, and say so plainly if it does.
5. **Anything else that would hurt on a live account.** Gate ordering, a strategy that reads the frame
   before checking it is long enough, an exception that could escape into the engine loop.

## How to answer

One section per item: what you checked, how, the verdict. For anything wrong: the exact line, the proof,
and what it would cost on the live account. Say plainly where you found nothing. End with the single
change you would most want made, and whether you would leave the gate switched on tonight.
