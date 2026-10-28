# Review brief: audit the research session's own changes (2026-10-27)

You delivered `app/strategy/trend_box.py`, `app/strategy/range_break.py` and their tests against
`DEV_SPEC.md`. The research session then reviewed your work and changed things. **Your job now is the
mirror image: audit those changes and try to break them.** Be adversarial. Finding nothing is a result,
but finding nothing because you did not look is not.

## What changed after your delivery

```
app/strategy/trend_box.py      min_take_profit default 5.0 -> 0.0 (+ comment)
app/strategy/range_break.py    min_take_profit default 5.0 -> 0.0 (+ comment); warmup_bars() 300 -> 1200
config.yaml                    ai lane min_take_profit 5.0 -> 0.0
research/2026-10-26-three-bots/bots.py   min_tp 5.0 -> 0.0
tests/unit/test_strategy_trend_box.py    + test_a_box_taller_than_the_cap_is_not_a_box
tests/unit/test_strategy_range_break.py  + test_h4_is_built_from_h1_open_times_and_only_from_closed_bars
                                         + test_an_unclosed_h4_bar_never_reaches_the_zigzag
                                         ~ test_sell_break_plan_is_the_mirror_and_reward_floor_is_enforced
research/2026-10-26-three-bots/my_bugs.py  14 planted bugs by the research session (all 14 now caught)
```

Start from `git diff` and `git status` to see them exactly.

## The four questions to answer

1. **Is turning the take-profit floor off actually safe?** The claim is that it rejected 1 of 496 signals
   (`gate_bite.py`). Check every place a take-profit floor still matters: `app/ai/plan.py`,
   `app/ai/trader.py` (`MIN_TAKE_PROFIT`), `app/strategy/ai_lane.py` (`target_trim` uses
   `min_take_profit` in `max(reach * (1 - trim), min(min_take_profit, reach))`). **With the floor at 0.0,
   does any of those expressions now behave differently from what its comment says, divide by zero, or
   let a target collapse onto the entry?** Write the arithmetic out, do not guess.

2. **Are the three new tests honest?** The research session caught one of its own tests re-implementing
   the production filter inside the test body, so a planted bug could not fail it. Check all three new
   tests for the same flaw: does each one fail if the production line it claims to cover is broken?
   Prove it by breaking the line and running the single test.

3. **Plant your own bugs against the NEW tests.** Pick at least 6 mistakes the research session's tests
   should catch and that are different from the 21 in your `plant_bugs.py` and the 14 in `my_bugs.py`.
   Aim at the newly covered ground: the `box * leg` cap, the H4 close-to-open shift, the forming-H4
   filter, the floor parameter. Write them as a script like `plant_bugs.py` with a crash-safe backup,
   run it, and report caught / MISSED.

4. **Anything else wrong.** `warmup_bars()` returning 1200 while `required_timeframes()` returns H1 -
   does the lane actually get 1200 H1 bars? Does the `three_bots` lane in `config.yaml` line up with
   what the strategies read? Is `RangeBreak.should_close` / `TrendBox.should_close` reachable at all
   given the decision timestamps the engine uses?

## Rules

- Do not touch `.env`, `TRADING_MODE`, anything DEMO/LIVE, or any credential.
- Do not run `git commit`, `git push`, or any deploy.
- Leave the working tree exactly as you found it: every planted bug restored.
- Write your findings to `research/2026-10-26-three-bots/REVIEW_FINDINGS.md`: one section per question,
  each finding as *what is wrong / how I proved it / what it would cost*. Say plainly if a question
  came back clean.
