# Review findings 5 — P26 and H4 gate re-check

Reviewed the current working tree and the claims in `REVIEW_BRIEF_5.md`. No commit or push was made. I did not edit `.env` or `config.yaml`. The tree already had many unrelated modifications before this review; findings below distinguish the requested gate work from that broader dirty state.

## Part 1 — claims checked

| Claim | Verdict | Evidence |
|---|---|---|
| `day_plan_ok=True` was removed; callers must state it. | **Proven.** | `evaluate_gate()` declares required keyword-only `day_plan_ok: bool` with no default (`app/risk/mode_gates.py`). The production caller passes `self.day_plan.exists(now)` (`app/engine/orchestrator.py`). Gate truth-table tests now explicitly supply a value through their helper. Python will raise `TypeError` for an omitted argument; there is no dedicated test that deliberately omits it. |
| The final `isfinite` guard is reachable; the comment and planting note were corrected and a tiny-ATR test was added. | **Proven.** | `edge_lean()` checks finite positive width, divides by it, then checks whether the result is finite. A tiny positive finite width can overflow that division. The source comment now acknowledges this and `test_a_tiny_atr_overflows_to_infinity_and_is_refused` covers it. Running `plant_bugs_edge.py` produced **15/15 caught**, including removal of the final result guard. |
| The boundary-direction test was missing. | **Proven fixed.** | `test_the_boundary_faces_the_right_way` asserts the date before 07:00, just after 07:00, and at noon. |
| `is_file()`, parent `mkdir()`, and `write()`'s returned path were unasserted. | **Proven fixed.** | The directory-named-like-a-plan test asserts `is_file()` behavior; the nested-directory write case proves the parent is created and asserts the returned path equals the expected plan path and is a file. |
| The `OSError` branch was unverified. | **Proven fixed.** | `test_an_unreadable_path_counts_as_unplanned` replaces `Path.read_text()` with an `OSError` and asserts `exists()` returns false. |
| No non-UTC, non-Bangkok zone was tested. | **Proven fixed.** | `test_a_moment_given_in_a_third_timezone_reads_the_same` tests New York timestamps and expected Thai trading dates. |
| Whitespace-only files counted as plans. | **Proven fixed, with an implementation caveat below.** | `exists()` now requires `p.is_file()` and `bool(p.read_text(encoding="utf-8").strip())`; the whitespace-only test asserts false. |
| DEMO/PAPER fixtures needed isolated plan folders and a plan matching their clock. | **Proven fixed for successful fixtures.** | Both harnesses set `DAY_PLAN_DIR` under `tmp_path`. `demo_settings()` writes a plan for `START` if it does not already exist, so a restart reuses it. The PAPER harness isolates its directory too. |

### `read_text()` behavior and missing-plan integration coverage

The whitespace check is content-correct for ordinary UTF-8 plans, but `read_text()` reads the **entire file into memory**. A very large plan can cause unnecessary memory use; a bounded read would be safer. Permission and other filesystem `OSError`s are caught and treated as unplanned. Invalid UTF-8 raises `UnicodeDecodeError`, which is **not** an `OSError` and is not caught in `DayPlan.exists()`. That exception does not yield permission, and the pre-send callback cannot reach `execution.send()` if it propagates, so the path appears fail-closed for orders; it does not return a normal `DAY_PLAN` refusal, and this case is untested. Treating decode errors as unplanned would make the contract explicit.

There is **no end-to-end DEMO engine test** that removes or omits the plan and proves no broker order is sent. The fixture writes a plan every time, and the current DEMO integration tests exercise success, kill-switch blocking, and flattening—not a missing-plan refusal. Unit tests cover `DayPlan.exists()` and the gate’s truth table, but not the full engine-to-order path for P26. This remains the key test hole.

### Mutation and test results

- `.venv\Scripts\python.exe research/2026-10-26-three-bots/plant_bugs_edge.py`: **15/15 caught**.
- Edge-side, trend-box, and range-break unit tests after the mutation runner: **72 passed**.
- Day-plan, mode-gate, and DEMO engine tests: **550 passed**.
- The mutation runner initially found an abandoned backup from an interrupted run and restored it. After the stable 15/15 run, the related tests passed and the backup artifact was removed. The runner restores each mutation in a `finally` block; final tests confirm the source is back in its passing state.

## Part 2 — drift against the owner's rules

1. **P26 — 07:00 Thai trading-day plan is a gate:** `trading_date()` uses `Asia/Bangkok` and the 07:00 boundary; `evaluate_gate()` requires an explicit plan result; the orchestrator checks it with the current clock both during gate evaluation and through the existing pre-send path. Missing/unreadable `OSError` input refuses. **Gap:** the end-to-end missing-plan refusal is not tested; malformed UTF-8 raises rather than returning a `DAY_PLAN` failure.
2. **H4 rule — larger frame, closed bar, lean on the trade's side at ≥0:** `edge_lean()` rejects entry frames not smaller than H4, uses only bars closed by decision time, and returns `None` when it cannot read a finite lean. The configured trend and range gates refuse `None` or negative own-side lean, so zero is admitted. Current `config.yaml` sets `require_edge_side: true` on the three strategies. Mutation suite: 15/15. No threshold drift found.
3. **Fail-closed inputs:** missing plans, whitespace-only plans, directories, and `OSError`s do not open the plan gate; unreadable H4 data is refused by the strategy gates. **Drift/limitation:** invalid UTF-8 is an uncaught exception, not an explicit `DAY_PLAN` refusal (though it does not grant send permission); large files are read without a bound.
4. **Stops and kill switch after breaker deactivation:** the P26 edits add a gate condition and wire it to the pre-send check; they do not change stop placement/management or kill-switch behavior. The kill switch remains checked in the gate and immediately pre-send. DEMO integration tests still cover no entries under HALT and closing positions under FLATTEN. No weakening attributable to these fixes found.
5. **Frozen `RULES_LOCKED.md` set 2:** the working diff preserves set 2's H4 formula, closed-bar requirement, and zero threshold. It adds set 2 after marking set 1 withdrawn; it does not alter set 2's numeric threshold. No locked-rule number drift found.

## Recommendation

The single change I would prioritize is an end-to-end DEMO test with no plan that asserts `DAY_PLAN` failure and zero `order_send` calls. **Keep both the P26 day-plan gate and H4 edge gate on.**