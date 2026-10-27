# Audit report: 02cbebf and 82d3f1f

**Verdict: the code adds a fail-closed plan gate and an H4 edge gate for the three bots, but the running DEMO engine has not loaded those changes. The edge rule also does not cover the enabled PLAN-1 strategies.** The requested test suite could not start in this read-only environment, so the code is not fully verified.

## 1. Do the commit messages tell the truth?

**02cbebf:** Its code claims check out against the diff: `DayPlan` treats missing, empty, unreadable, or invalid UTF-8 files as unplanned; the mode gate blocks new orders; and the H4 rule rejects unreadable or negative leans for the three bot strategies. The recorded `+0.102 → +0.210 R` and `+0.214 / +0.207` figures match the new rule set’s tables. I did not independently reproduce those figures from the historical data.

The RR scope claim also checks out: the global `risk.min_risk_reward` remains **1.0** in [config.yaml](/C:/Users/korap/taa/config.yaml:253); the **0.8** value is on the `three_bots` lane at [config.yaml](/C:/Users/korap/taa/config.yaml:226). The profile’s lower RR is combined conservatively with the local cage in [limits.py](/C:/Users/korap/taa/app/risk/limits.py:267), then the lane’s own value is applied in [decision_engine.py](/C:/Users/korap/taa/app/engine/decision_engine.py:257). I found no global RR cage reduction or plan1 RR loosening in the diff.

**82d3f1f:** The replay guard exists in `day.py`, and review rounds 2–5 are present. But the statement in `RULES_LOCKED.md` that the earlier mistakes are “now impossible to repeat” overstates the guard: [test_bots.py](/C:/Users/korap/taa/research/2026-10-26-three-bots/test_bots.py:30) explicitly allows deliberate parameter variations. The tests protect against bare defaults and compare the shipped values to app defaults; they cannot prevent a future script from supplying a different, incorrect configuration.

There is also a stale statement in [HANDOFF.md](/C:/Users/korap/taa/docs/HANDOFF.md:425) claiming the final `isfinite` guard is unreachable. The code and a dedicated test show otherwise: a finite ATR of `1e-320` can overflow the division, and the guard refuses it at [edge_side.py](/C:/Users/korap/taa/app/strategy/edge_side.py:81) and [test_strategy_edge_side.py](/C:/Users/korap/taa/tests/unit/test_strategy_edge_side.py:176).

## 2. Standing rules against the finished code

**P26, the morning plan:** The implementation is a real pre-send gate. [orchestrator.py](/C:/Users/korap/taa/app/engine/orchestrator.py:654) reevaluates it before orders, and the DEMO integration tests cover zero `order_send` calls without a plan and orders flowing after a plan is restored. Missing, unreadable, or invalid text fails closed.

There is a completeness gap: [day_plan.py](/C:/Users/korap/taa/app/risk/day_plan.py:51) accepts any non-whitespace UTF-8 text as a plan. It does not check for the day’s condition, levels, trend, edge side, or scenarios. The gate therefore refuses an empty file, but a one-character file opens it.

More urgently, [HANDOFF.md](/C:/Users/korap/taa/docs/HANDOFF.md:408) says the DEMO process was not restarted after the H4 gate was switched on, and lines 423–424 say P26 was still only a note. The running process therefore does not have the new gates, regardless of the current source code.

**Larger-timeframe edge, unreadable means refuse:** `trend_box` and `range_break` refuse when the H4 lean is unavailable or against the trade, when `require_edge_side` is enabled. But that setting is enabled only for the three new bots in [config.yaml](/C:/Users/korap/taa/config.yaml:211). The four enabled PLAN-1 strategies at [config.yaml](/C:/Users/korap/taa/config.yaml:159) do not apply an edge-side gate. Since the standing rule says “every trade,” this is a rule violation: PLAN-1 entries can still trade without a larger-timeframe edge reading. The AI strategy is disabled in this config.

**Stops and kill switch:** I found no diff change that weakens the trade stop or kill switch. `min_stop_atr` is new but defaults to zero and is not enabled in the shipped config. The loss breakers are already deactivated in the baseline, consistent with the owner’s decision. That leaves the documented DEMO exposure—7.5% risk per trade, up to two positions, about 15% combined open risk—with stops and the kill switch as protection. A missing gate can allow an entry the owner’s edge rule would reject; if it loses, the stop can lose up to the trade’s risk budget, and two positions can put roughly 15% of equity at risk before gaps or execution effects. There is no active loss breaker to stop a sequence of such losses.

**Frozen rule set 2:** The diff appends rule set 2 and preserves rule set 1 marked withdrawn. I found no subsequent movement of set 2’s threshold or reported figures in the supplied diff. The H4 threshold is still zero. The document itself acknowledges the figures were selected after seeing both historical halves, so the forward test remains necessary.

## 3. Changes with broader impact than their purpose

The earlier global `min_risk_reward` cage reduction is **not present**. The global value remains 1.0; 0.8 is scoped to the `three_bots` lane, and the profile combination remains conservative for lanes without their own override.

The config does enable all three bot strategies where they were disabled. That is within the stated purpose of running the three-bot system, but it is a consequential change: it adds active strategies on the DEMO account, and the handoff says the running process has not loaded the new edge gate.

I found no unintended change to stop placement or kill-switch behavior. The profile schema now accepts RR values below 1.0, but the effective local cage still prevents that value from lowering the global floor for lanes without an explicit lane RR. Plan1 remains at the 1.0 cage.

## 4. Dead code, reachability, and comments

The handoff’s “unreachable” `isfinite` statement is contradicted by live code and the overflow test described above.

`app/strategy/weighing.py` is an inert helper with no production call site in the diff. It has no live trading effect. The new `edge_side()` convenience function also has no production caller; production strategy checks use `edge_lean()` and `behind()` directly. Neither appears to cause an order-safety defect.

The P26 tests that normally create a plan in their fixtures would not alone prove refusal, but the added dedicated DEMO tests explicitly delete the plan and assert zero broker sends, then restore it and assert orders flow. That contract is covered in source.

## 5. Requested checks

- `.venv\Scripts\python.exe -m pytest -q`: **could not collect or run tests**. Pytest exited before collection because it could not find a writable temporary directory. No suite pass/fail count is available; this was not a green run.
- `ruff check app tests`: **passed** (“All checks passed!”).
- `mypy app`: **did not complete**. Mypy 2.4.0 exited with an internal error; with `--no-incremental --show-traceback`, the cause was `sqlite3.OperationalError: unable to open database file`, consistent with the read-only environment.
- `bandit -q -r app -c pyproject.toml`: **passed**, exit code 0. It emitted warnings about words in comments being interpreted as test names.

## Fix before the next trading day

The most urgent issue is operational: the current DEMO process is trading without the code changes’ P26 and H4 gates. Stop relying on that process until the engine-verified backtest is complete and the updated engine has been restarted with a valid day plan. Before treating the edge rule as satisfied, extend the larger-timeframe edge check to the enabled PLAN-1 strategies too.

**The engine should not keep running overnight as it is.** The report is based on the committed diff and handoff; I made no file changes.