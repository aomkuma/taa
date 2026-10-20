# The team - roles, ownership and how we talk (2026-10-19)

Owner (2026-10-19, about 23:08 Thai): "divide the duties and talk to each other well." The goal is fixed: at least
+0.15 R a trade after costs in both learning parts, about 2-3 trades a day, in the owner's windows, then one exam read.

## Who does what

| Role | Folder (the only place it writes) | Owns | Does not |
|---|---|---|---|
| **The measurer / coordinator** (the main session) | `precursors/` notes and checks, the briefs (`*_PROMPT.md`, this file), `docs/OWNER_TRADING.md` | talking with the owner (in Thai); assigning and relaying work; measuring every deliverable (re-running tests, its own planted bugs, re-deriving trades from the raw ticks, checking on the real candles); commits; the single exam read of a frozen rule | build the trade rules itself |
| **The first developer** | `dev/` | the chart-pattern detector at the owner's levels: P3 the exits, P4 B2 in the owner's windows, P5 the owner's pattern set on trade-size swings | build its own swings: it imports dev2's |
| **The second developer** | `dev2/` | the owner's playbook, Setup OWN V3: **the shared trade-size swings and the structure per TF**; the range box / trendline / Fibonacci; the four entries (break and retest, the aligned consolidation, the fake break at a range edge, the fake first leg at an open); the stops past the structure and the trailing; scenario planning; the frozen rule | edit `dev/` |
| **The auditor** | `audit2/` (+ fixes in research files outside `dev/` / `dev2/`, + the one app fix) | the nine shared building blocks: data, larger-TF bars, indicators, swings, simulators, costs, parts / windows / DST, metrics, untested code | edit `dev/` or `dev2/`: a bug there goes to the measurer as a failing test |
| **The strategist** | `strategist/` | the review: why it does not pay yet, quick measurements, outside research, ranked testable proposals, what to stop doing | build the system; edit other folders |

## How we talk
1. **Through the measurer.** Every report goes to the measurer, who relays what another role needs, with the context.
   Nobody edits another role's folder.
2. **Shared code has one owner.** The trade-size swings and the structure belong to the second developer. Others import
   them read-only and ask for changes through the measurer.
3. **A bug in someone else's code** goes to the measurer as a failing test (file, test, numbers). The owner of the code
   fixes it and reports the fix with the test passing.
4. **The strategist's proposals:** the measurer ranks them with the owner and assigns each to a developer, written into
   that developer's brief.
5. **Every report has the same shape** (`DEV_PROMPT.md` section 6): what was done, each test (what / how / the pass
   line), the planted bugs (CAUGHT / MISSED), the look-ahead check, the results per part, and questions.
   - Nothing "should pass".
   - No made-up numbers.
   - No coin / "50-50" verdicts.
6. **Checkpoints:** each role stops at its checkpoint and reports. The measurer measures, shows the owner, and
   answers. Then the work goes on.
7. **Times** come from `date -u`. Reports give Thai time (UTC+7). The exam period 2026-04-18 .. 2026-10-17 is read
   by no one but the measurer, once per frozen rule.
8. **When unsure, ask in the report.** Do not guess. The owner's meaning comes first: when code and the owner's words
   differ, the code is wrong.

## The current checkpoints (2026-10-20 12:40 Thai)

All four agents stopped on the weekly API limit at about 12:35 Thai (reset 2026-10-21 15:00 Thai). A new session
starts each one again from its brief and its own log.

| Role | Next task | Next checkpoint |
|---|---|---|
| The first developer | CHECKLIST row 38: `dev/plan1.py`, the PLAN-1 runner (costs the spread only; slippage a parameter defaulting to 0; with 0.07 it reproduces `precursors/out_combo.txt` / `out_regime.txt`; an exam switch for the measurer only) | the runner report; then P5 on dev2's swings + the structure cross-check |
| The second developer | finish V3-1: the swings, the structure per TF (D1 / H4 / H1), the side / trend columns, the 2026-10-19 acceptance, written definitions | the V3-1 report; then V3-2 (the "V3 design" in `DEV2_PROMPT.md`) |
| The auditor | item 1 (wf.weekly win = pnl > 0), item 4 (`plib.load_learning()`); item 3 is in the app files, waiting for the measurer's review | `audit2/AUDIT.md`; then dev2's `swings.py` |
| The strategist | CHECKLIST row 39: the transformations of the FAIL rows (the opposite side, the stop x 1.5 / x 2, a nearer target), the state weights per piece (chosen on P1, checked on P2 and the older years); spread only | `strategist/PROPOSALS.md` |
