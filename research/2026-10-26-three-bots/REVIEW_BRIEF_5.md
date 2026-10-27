# Re-check: what I changed in answer to REVIEW_FINDINGS_4, and whether any of it drifted

You may plant bugs and must restore every one. **No commit, no push, no `.env`, no `config.yaml`, no
DEMO/LIVE settings.** The engine is running live on the DEMO account.

Write only `research/2026-10-26-three-bots/REVIEW_FINDINGS_5.md`. Use `.venv\Scripts\python.exe`.

## Part 1 — did each fix actually do what I claim?

Take each claim and prove or disprove it. A claim I cannot back is worse than the original fault.

| your finding | what I claim I did |
|---|---|
| `day_plan_ok=True` is fail-open | removed the default; every caller must state it, a forgotten one is a `TypeError` |
| the final `isfinite` guard is reachable (tiny ATR overflows), my "unreachable" claim was wrong | agreed and verified it myself; corrected the comment in `edge_side.py`, corrected the note in `plant_bugs_edge.py`, added `test_a_tiny_atr_overflows_to_infinity_and_is_refused`; `plant_bugs_edge.py` now reports 15/15 |
| the boundary-direction test does not bite | added `test_the_boundary_faces_the_right_way` |
| `is_file()`, the `mkdir`, and `write()`'s return value are unasserted | added three cases |
| the `OSError` branch is unverified | added `test_an_unreadable_path_counts_as_unplanned` |
| no non-UTC, non-Bangkok zone case | added a New York case |
| a whitespace-only file counts as a plan | `exists()` now uses `read_text().strip()`; added a case |
| isolate the DEMO fixture's plan directory | both demo and paper harnesses take `DAY_PLAN_DIR` under `tmp_path`, and the demo harness writes a plan for its own clock (`START`), reusing it on a restart |

Check in particular:
- **Does `plant_bugs_edge.py` really reach 15/15, or did I make the bug easier instead of the test
  stronger?** Run it yourself.
- **The whitespace change replaced a `stat()` with a `read_text()`.** Is that right on a large file, a
  file without read permission, or a file that is not valid UTF-8? Does it still fail closed?
- **The demo fixture now writes a plan.** Does any test still prove the gate REFUSES when the plan is
  missing, end to end through the engine - or did I make every integration test pass by always providing
  one? If no end-to-end refusal case exists, say so: that is the hole the whole gate exists to close.

## Part 2 — has anything drifted from what the owner laid down?

The owner, this evening: *"do not let it drift from what we defined."* Check my changes against these,
and name any place where the code and the rule have come apart:

1. **P26** — a trading day starts with its plan; the day runs 07:00 Thai to 07:00 Thai. The plan is now a
   gate, not a reminder. Nothing may quietly grant permission when the plan is missing.
2. **The H4 rule** (`RULES_LOCKED.md`, set 2) — take the trade only when the H4 lean is at least 0 on the
   trade's own side; the frame read must be LARGER than the entry frame; an unreadable frame is a refusal,
   never permission.
3. **Fail-closed everywhere** — the owner's standing design: a missing, unreadable or doubtful input stops
   trading. Check that none of my edits turned a refusal into an allowance.
4. **The breakers are deactivated by the owner's decision** (2026-10-27), so each trade's stop and the
   kill switch are what is left. Confirm nothing I changed weakens either of those two.
5. **The locked rules are frozen** — `RULES_LOCKED.md` set 2 was dated before any forward day was run.
   Confirm no change of mine alters a number or a threshold in it.

## How to answer

Part 1: one row per claim - proven, disproven, or "could not check", with the evidence. Part 2: one line
per rule, plus any drift found. End with the single thing you would most want changed, and whether both
gates should stay on.
