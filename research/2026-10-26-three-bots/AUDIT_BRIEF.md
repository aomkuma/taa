# Audit the day's two commits against the owner's own rules (2026-10-27)

Read-only. Two other sessions are editing files in this repo right now, so change nothing. Write only
`research/2026-10-26-three-bots/AUDIT_FINDINGS.md`. Use `.venv\Scripts\python.exe`.

A long day produced 13 mistakes that were caught one at a time, four review rounds between us, and then
two commits: **02cbebf** and **82d3f1f**. You reviewed pieces of this as it was built. This is the sweep
over the whole of it, with fresh eyes on the finished diff rather than on each change as it arrived.

`git show --stat 02cbebf 82d3f1f`, `git log -2 --format=%B`, and `git diff 659f080..HEAD` are your input.
`docs/HANDOFF.md`'s last section describes the state those commits leave behind.

## What to audit

1. **Does the commit message tell the truth?** Take every factual claim in both messages and check it
   against the diff. A commit that overstates what was done is worse than one that says less.
2. **The owner's standing rules, against the finished code** - name any place the two have come apart:
   - a trading day starts with its plan, and the plan refuses rather than reminds (P26, 07:00 Thai);
   - take only the side with the edge on a frame LARGER than the entry frame; unreadable means refuse;
   - fail-closed everywhere: a missing, unreadable or doubtful input stops trading, never permits it;
   - the loss breakers are deactivated by the owner's decision, so each trade's stop and the kill switch
     are the whole of what protects the account - nothing may weaken either;
   - `research/2026-10-26-three-bots/RULES_LOCKED.md` set 2 is frozen: no number in it may have moved.
3. **What did the diff change that nobody asked for?** The day included one case of exactly this: the
   global `risk.min_risk_reward` cage was lowered to let one lane through, which quietly loosened the
   live plan1 strategies until it was caught. Look for any other change whose blast radius is wider than
   its stated purpose - especially in `config.yaml` and anything under `app/risk/`.
4. **Is anything in the diff dead, unreachable, or contradicted by its own comment?** Several comments
   in this diff make claims about reachability and about what is tested. Check them.
5. **Run the suite yourself** (`.venv\Scripts\python -m pytest -q`) and report the real number, plus
   `ruff check app tests`, `mypy app`, `bandit -q -r app -c pyproject.toml`. If anything fails, that is
   the headline.

## How to answer

A section per item. For anything wrong: the exact file and line, how you proved it, and what it would
cost on the live DEMO account the engine is trading right now. Say plainly where you found nothing - a
clean verdict from you is worth something. End with the single most important thing to fix before the
next trading day, and whether the engine should keep running overnight as it is.
