# Review findings 4: P26 day-plan gate and H4 gate fixes

## 1. Fail-closed behavior and `evaluate_gate` callers

**What I checked.** Searched Python sources under `app`, `tests`, and the review directory for `evaluate_gate`, then traced the production caller in `Orchestrator.gate()` (`app/engine/orchestrator.py:627-647`). That method takes one `self.clock.now_utc()` reading and passes `self.day_plan.exists(now)` as `day_plan_ok`. Its day-plan detail is diagnostic only. `evaluate_gate()` records `DAY_PLAN` as a failure whenever the value is false (`app/risk/mode_gates.py:112`). The only application caller found is the orchestrator; the remaining callers are tests, several of which omit the new argument.

**Verdict: production call is fail-closed, public function default is fail-open.** `day_plan_ok: bool = True` at `app/risk/mode_gates.py:87` allows every direct caller that forgets the new condition to pass the day-plan condition. The older truth-table tests currently do exactly that, so they do not model the new rule. Remove the default and make `day_plan_ok` required. The cost is small: update the direct test helper/calls to provide an explicit value (normally `True` for gate truth-table tests), and any external callers will get an immediate `TypeError` until they supply it. This is preferable to silently granting permission. The early return for PAPER/BACKTEST remains a failing MODE result and cannot pass orders.

## 2. Whether the gate stops entries and permits position management

**What I checked.** Followed `Orchestrator._decide()` into `DecisionEngine._mode()`, where a missing or failed gate rejects a DEMO/LIVE decision. Then followed accepted decisions through `DemoBackend.place()` into `OrderManager.execute()`. The market-send path (`order_manager.py:459-485`) and limit placement path (`343-370`) both call the required `presend` callback immediately before `execution.send()`. The production `OrderManager` is constructed with `presend=self._presend` (`orchestrator.py:493-504`); `_presend()` calls `self.gate()` and turns any failed conditions into a send refusal. Market retries repeat this check. I also followed direct sends in `BrokerPositionManager`.

**Verdict: new entry sends are checked twice; management and closes are not blocked.** I found no production entry path that skips the decision gate and pre-send gate. The direct `order_send` calls in `BrokerPositionManager` are stop modifications and position closes, and intentionally bypass entry pre-send checks. That is correct for the stated rule: a missing plan should prevent new orders while leaving open positions manageable and closable. Already placed resting limits have passed the gate at placement; this review found no gate-triggered cancellation if the plan file is later removed, so a previously placed pending order could still fill. That is a residual consequence of checking at send time, not a new-order bypass.

## 3. Thai trading day and plan path

**What I checked.** `trading_date()` converts the aware input with `ZoneInfo("Asia/Bangkok")`, then assigns times before `07:00` to the previous date (`day_plan.py:37-38`). I hand-checked 2026-10-27 06:59:59 Thai maps to 2026-10-26 and 07:00:00 Thai maps to 2026-10-27; the equivalent UTC instants, 2026-10-26 23:59:59 UTC and 2026-10-27 00:00:00 UTC, produce the same respective dates. I also checked 2026-10-27 09:00 America/New_York (20:00 Thai), which maps to 2026-10-27. There is no fixed `+7` arithmetic: the implementation uses the IANA `Asia/Bangkok` zone. Thailand does not observe daylight saving, and this implementation does not encode a fixed offset.

`Settings.path()` resolves relative paths against `REPO_ROOT` (`app/config.py:1542-1545`), so the default `DAY_PLAN_DIR="data/plans"` resolves to this repository's `data/plans`, independent of the process working directory. That is consistent with the intended location.

**Verdict: date conversion and path resolution are correct.** Coverage is slightly narrower than the brief asks: the unit test checks UTC input but not a non-UTC, non-Bangkok zone. My manual New York check passed. The `datetime.astimezone()` call also assumes an aware datetime; production `Clock` implementations guarantee one, and `ManualClock` rejects a naive start.

## 4. Do the nine day-plan tests bite?

**What I checked.** Baseline: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/unit/test_risk_day_plan.py` passed **9/9**. I then made one temporary mutation per case, ran only that case, and restored `app/risk/day_plan.py` in a `finally` block after each run. The final source bytes matched the original exactly.

**Results.** I tested one semantic mutation per test plus five additional helper-line mutations (14 total). Eight of the nine case-specific mutations and two of the five additional mutations were caught (10/14):

- `test_the_day_turns_at_seven_in_the_morning_thai`: changing the 07:00 boundary to 06:00 failed.
- `test_it_reads_the_thai_clock_whatever_zone_the_moment_arrives_in`: skipping timezone conversion failed.
- `test_no_file_means_the_day_is_unplanned`: making `exists()` always return true failed.
- `test_a_written_plan_opens_the_day`: writing zero bytes failed.
- `test_an_empty_file_is_not_a_plan`: dropping the nonzero-size check failed.
- `test_a_plan_written_in_the_morning_still_covers_the_new_york_hours`: assigning the next morning to its calendar date failed.
- `test_a_plan_written_before_seven_is_filed_under_the_day_before`: assigning a pre-07:00 plan to the calendar date failed.
- `test_a_day_is_not_replanned_over_the_top_of_itself`: removing the existing-plan guard failed.

**Miss and coverage gaps.** `test_yesterdays_plan_does_not_cover_today` passed when I changed the boundary predicate from `< 07:00` to `> 07:00`. It verifies that one file does not answer both queried days, but does not independently prove which exact trading date either instant belongs to. The boundary and pre-07 tests catch related faults, so this is a weaker redundant test rather than a production defect. Three additional mutations also passed all nine tests: replacing `p.is_file()` with `True` (a nonempty directory named like a plan would then pass), removing the parent-directory creation, and returning `None` instead of the `Path` from `write()`. These lines are exercised or adjacent to exercised behavior, but their specific contract is not asserted. No unit case tests an unreadable path; the code catches `OSError` and returns false (`day_plan.py:58`), but that fail-closed branch is unverified. There is also no non-UTC-zone unit case.

The DEMO integration fixture has a concrete regression: `demo_settings()` does not override `DAY_PLAN_DIR`, so it resolves to shared repository `data/plans`, while its `ManualClock` starts on 2026-10-01. Running `test_demo_sends_a_protected_broker_order` fails its gate assertion because it looks for `data/plans/2026-09-30.md`; the only current plan file is dated 2026-10-27. This fixture must point `DAY_PLAN_DIR` at a `tmp_path` directory and create the fixture plan for its test clock (or explicitly test the denied case). As written, the integration test cannot exercise a successful DEMO order independently of the operator's live plan files.

## 5. Other live-account concerns; H4 gate fixes

**Clock call.** `Orchestrator.gate()` captures `self.clock.now_utc()` once and uses that same instant for both the plan check and diagnostic path. `SystemClock` returns aware UTC and `ManualClock` stores UTC, so this is sound. If the clock itself raises, the pre-send callback does not proceed to `execution.send()`; the cycle/pre-send fails closed.

**Empty plans.** `DayPlan.exists()` checks `st_size > 0`, so a whitespace-only file is accepted as a plan. If "empty" includes whitespace-only content, this should use a content check such as stripped text; otherwise the current rule is specifically nonzero file presence. `DayPlan.write()` can create a zero-byte file, but that file does not open the gate.

**H4 finite-result guard.** Keep `return lean if math.isfinite(lean) else None` in `app/strategy/edge_side.py:84`. The claim in the implementation comment and `plant_bugs_edge.py` that it is unreachable is too strong: finite close/mean values and a finite, positive but extremely small ATR can overflow the division to infinity. I verified this with the test fixture's finite rising closes and a temporary `atr` result of `1e-320`; `edge_lean()` returned `None` through the final guard. Removing the guard would return infinity, and `infinity < 0` is false, so a negative-only strategy veto could admit a trade without a meaningful lean. The present tests do not exercise this output-overflow case, so the known missed mutation is not evidence that the guard is dead code. Add a focused test if changing the tests is in scope.

The added H4 resampling test does hard-code expected bucket timestamps and highs, so its expected answer is independent. Its code and name/docstring nevertheless claim it does not call `resample_from_h1`; it actually calls that production function and checks the result against the hand-worked expectations. The distinction matters for accurate test descriptions, but the hard-coded assertions do catch a wrong shift (the existing planted-bug output records the shift mutations as caught).

## Recommendation

The single change I would prioritize is removing the fail-open `day_plan_ok=True` default and requiring every caller to state the value. Also isolate the DEMO integration fixture's plan directory so its successful-order test can pass a controlled plan rather than depending on a live date. I would leave both the P26 day-plan gate and H4 edge gate enabled overnight: the Thai trading date intentionally carries the 07:00 plan through the New York session, and I found no reason to disable either gate.

The mutation run left `app/risk/day_plan.py` byte-identical to its starting contents. No commit or push was made; `.env` and `config.yaml` were not edited.
