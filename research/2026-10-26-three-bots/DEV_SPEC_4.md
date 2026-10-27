# DEV_SPEC 4 — close the two gaps your own audit found (2026-10-27, night)

Your audit of commits 02cbebf and 82d3f1f (`AUDIT_FINDINGS.md`) named two gaps between the code and the
owner's rules. **The engine is STOPPED** — the owner shut it down so these could be fixed properly, so
you are not working under a live account tonight. Still: **no commit, no push, no `.env`.**

Two other sessions are editing `research/2026-10-26-three-bots/weights*` and `docs/`. Stay out of those.

## Gap 1 — the edge rule covers three strategies, the owner said every trade

Your words: *"that setting is enabled only for the three new bots"*. The owner's rule, 2026-10-27:
**"every trade takes only the side with the edge on a timeframe larger than the entry timeframe."**
Four PLAN-1 strategies trade on the same DEMO account with no such check.

Add the same gate to them. `app/strategy/plan1.py` and `app/strategy/plan1_b2.py` hold
`setup_plan1_orb`, `setup_plan1_ny`, `setup_plan1_b2`, `setup_plan1_b2m5`.

- Reuse `app/strategy/edge_side.py` - `edge_lean()` and `behind()`. Do not write a second copy of either.
- Each gets `require_edge_side: bool = False` on its params, **default off**, exactly as the three bots
  have it. Defaults must stay byte-identical: this round changes mechanism, not behaviour.
- The test is the measured one: refuse when `behind(edge_lean(...), own_side)` is `None` or below 0.
  Unreadable is a refusal, never permission.
- Their entry frames differ from M5 - read each strategy's own entry timeframe from the context, and
  remember `edge_lean` raises if the frame read is not larger than the entry frame. If any of these
  strategies enters on a frame at or above H4, say so in your notes and do NOT force it.
- `warmup_bars()` must cover 64 closed H4 bars (about 256 H1) when the gate is on, as the trend bots do.
- Do **not** change `config.yaml`. The owner decides when to switch it on.

## Gap 2 — a one-character file opens the day

Your words: *"the gate refuses an empty file, but a one-character file opens it"*. P26 asks for the day's
condition, its levels, the trend, the side with the edge and the turn/go-on scenarios.

Make `app/risk/day_plan.py` check that a plan is a plan, not that it is long:

- the file must contain, in any order and case-insensitively, a marker for each of: **condition**,
  **levels**, **the side with the edge**, and **scenarios**. Pick the markers from how
  `data/plans/2026-10-27.md` is actually written (read it) and from `app/ai/plan.py`'s own plan fields,
  so a plan this system writes passes without being reshaped.
- a file that is present but incomplete must refuse **and say which part is missing** - the gate's
  detail string already flows into the refusal, so use it. A plan that fails silently is the failure
  mode this whole gate exists to stop.
- keep every existing refusal: missing, empty, whitespace-only, a directory, unreadable, not UTF-8, and
  the bounded read.

## The absolute rules

1. Defaults OFF and byte-identical behaviour; prove it with the full suite and unchanged parity numbers.
2. Never re-implement production logic inside a test; every test calls the real function.
3. Prove each new test bites: break the one line it covers, run that test, confirm it fails, restore.
   Report every one. **You may edit to plant bugs and must restore every one.**
4. At least 8 new planted bugs for this round in `plant_bugs_4.py`, crash-safe, output committed to
   `plant_bugs_4_output.txt`, caught and MISSED both reported honestly.
5. `ruff format`, `ruff check app tests`, `mypy app`, `bandit`, full `pytest` green before you stop.
6. If anything here contradicts anything else, stop and write it in `DEV_NOTES_4.md` rather than guess.

Write `research/2026-10-26-three-bots/DEV_NOTES_4.md`: each gap, the tests x the mutation proving each
bites, the planted-bug table, proof the defaults are unchanged, and what you did not do.
