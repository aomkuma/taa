# Review: the day-plan gate (P26), and the H4 gate fixes after your last review

**Not read-only this time.** My last two briefs told you to prove each test bites by breaking a line, and
also forbade changing code - a contradiction, twice. You may edit to plant bugs, and must restore every
one. Still: **no commit, no push, no `.env`, no `config.yaml`, no DEMO/LIVE settings.**

**The engine is running live on the DEMO account** (it imported these modules at start, so edits do not
reach the running process - but restore anything you plant immediately anyway).

Write only `research/2026-10-26-three-bots/REVIEW_FINDINGS_4.md`. Use `.venv\Scripts\python.exe`.

## What is new

**1. `app/risk/day_plan.py` + the `DAY_PLAN` gate condition.** The owner's rule since 2026-10-25 is that
a trading day starts with its plan. It was written down as a principle, a knowledge-base entry and a
memory, and the engine still opened a DEMO session without one. So the plan is now a file whose presence
is the permission, like the kill switch: `data/plans/<Thai trading day>.md`. Missing, empty, or
unreadable means the mode gate fails and no broker order is sent; open positions are still managed.
Tests: `tests/unit/test_risk_day_plan.py` (9 cases).

**2. The fixes from your last review**, which you have not seen:
   - `edge_lean` now rejects a non-finite mean, width and result (`nan < 0` is False, so a NaN opened the
     gate - your finding).
   - a hand-worked resampling test that does NOT call `resample_from_h1`, answering your "partly
     circular" point.
   - `research/2026-10-26-three-bots/plant_bugs_edge.py`: 15 planted bugs, **14 caught**. The one miss is
     the final `isfinite` guard, which no input can reach because the mean and width guards already stop
     everything; it is recorded as a deliberate miss rather than covered by a faked test. **Judge that
     call - say if you would delete the guard, or find an input that reaches it.**

## What to check, hardest first

1. **Is the gate fail-closed in every path?** `evaluate_gate` takes `day_plan_ok: bool = True` so its
   existing callers keep working - **that default is fail-OPEN by construction**. Find every caller and
   say whether each one passes the real value; say plainly whether the default should be removed and the
   argument made required, and what that would cost.
2. **Does it actually stop an order?** Trace from `Orchestrator.gate()` to `order_send`. Is the gate
   consulted before every entry, or only in `_presend`? Can an entry be placed on a path that never asks?
   Does it correctly NOT block managing or closing an open position?
3. **The Thai trading day.** 07:00 Thai to 07:00 Thai, from `datetime.astimezone`. Check the boundary by
   hand at 06:59:59 / 07:00:00 Thai, for a moment given in UTC, and for one given in another zone.
   Thailand has no daylight saving - confirm nothing in the code assumes a fixed +7 anyway.
4. **Do the 9 tests bite?** Break each production line they cover, run that test, confirm it fails,
   restore. Report every one. Two of them I wrote wrong first and the code was right; look for any case
   that asserts the implementation rather than the rule.
5. **Anything else that would hurt on a live account**, including the new `self.clock.now_utc()` call
   inside `gate()` and whether `settings.path(env.DAY_PLAN_DIR)` resolves where I think it does.

## How to answer

A section per item: what you checked, how, the verdict, and for anything wrong the exact line, the proof
and the cost. Say plainly where you found nothing. End with the one change you would most want, and
whether you would leave both gates on overnight.
