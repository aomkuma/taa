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

## The current checkpoints
| Role | Working on | Next checkpoint |
|---|---|---|
| The first developer | **paused** (owner, 23:11 Thai: no more tests on the old structure) | resumes on dev2's V3-1: P5 on the new swings + an independent cross-check of the structure reader |
| The second developer | V3-1 (the swings, structure, box / trendline / Fibonacci) | the V3-1 report with the 2026-10-19 shape check |
| The auditor | the data pipeline first (the download that missed Monday), then the other blocks | `audit2/AUDIT.md` |
| The strategist | the review and the ranked proposals | `strategist/PROPOSALS.md` |
