# AI Analyst + Bot Executor — Discussion Record and Feasibility

Record of the design conversation of 2026-10-06 between the owner and Claude Code (in Thai, summarized here in
English). **Status: proposal; nothing decided or built yet.** No profitability claims: everything here is about
process and measurement, not results.

---

## 1. The owner's question

**Owner (Thai):** "ตัว bot trade มีความสามารถในการ execution เข้าตามสัญญาณ แต่ AI Agents มีความสามารถในการ
วิเคราะห์ประมวลผลเหมือนเวลาเราโยนรูปภาพของกราฟไปให้ช่วยวางเทรด trade setup ให้หน่อย ซึ่ง bot trade บางทีก็รู้สึกว่า
มันไม่ได้มองภาพกว้างเท่าที่เราต้องการคือไม่ยืดหยุ่นเท่า"

*Translation:* the bot executes on signals, but an AI agent can analyze like when you give it a chart image and
ask for a trade setup. The bot sometimes does not see the big picture and is not as flexible. How can the two be
combined, and is it feasible?

## 2. What the system does today (checked against the code)

**The bot (deterministic):**

- Sees **two timeframes**: `timeframes.higher: H1` (bias, regime) and `entry: M15` (setups). D1/H4 are streamed
  for the charts only (`chart_timeframes`), never seen by a strategy. `Timeframe` has no W1.
- 8 strategies, each a **fixed checklist around one trigger family** (`example_trend_pullback`, the 7
  `setup_*` in `app/strategy/setups.py`). Confluence enrichment adds the other evidence as a score, but it never
  changes the plan (entry, stop, target).
- Entries are market orders on the signal bar; a signal expires after 1 bar (`signal_expiry_bars: 1`). There is
  no "wait for price to come to this zone" today (planned in learning L19.3 / hook H2).

**The AI (`app/ai/`, built, off until a key is set):**

- **Entry review** (`gate.py`): a second opinion on a signal the bot already made. Input: one closed bar's numbers
  (H1/M15 indicator state, 5 S/R levels, the signal's geometry). It can only **block** (veto mode) or record
  (advisory mode). It never proposes a trade.
- **Advisory notes** (`advisory.py`): an opinion and a TH/EN narrative per opportunity, ranking and analytics
  narratives. Descriptive only.
- No price history, no higher timeframes, no images go to the model today.

**Why the bot "does not see the big picture":** partly the AI's absence, but mostly the bot's own design:
two timeframes, one trigger per setup, no playbook by regime, no symbol profile. Several of these are already
planned deterministically in the learning track (L20.1 playbook router, L5 symbol profile, L19 timing).

**Documented rules this idea touches:**

- PLAN R21 / §A20: the AI layer is **veto-only**; "nothing is ever executed from its text".
- PLAN_LEARNING §L12: the LLM is used only for narrative.

Letting the AI *propose* plans is therefore a design change (a PLAN revision), not a ticket within the current
rules. It needs the owner's explicit decision.

## 3. Proposal: analyst, executor, referee

Split by what each side is good at:

| Role | Who | Speed | Does |
|---|---|---|---|
| **Analyst** | LLM (Claude) | slow (10–60 s), on an HTF bar or on demand | Reads the whole multi-timeframe picture and writes a **thesis**: bias, playbook, zones, invalidation, targets, the trigger to wait for, an expiry |
| **Executor** | the existing engine | fast, every closed LTF bar | Watches the zones, waits for a deterministic trigger, sizes by the owner's profile, passes every risk/mode gate, manages the position |
| **Referee** | shadow tracking | continuous | Records every thesis and its outcome in R, compares AI theses with the bot's own signals, and decides with numbers whether the AI earns a role |

The AI decides **where and in which direction** to look; the bot decides **when and how much**, and the gates
decide **whether at all**. The AI's slowness does not matter, because it never times an entry.

### 3.1 The chart pack (input)

Built by the engine from data it already has. Engine-made only, so no prompt-injection path:

- OHLC per timeframe, compressed: D1 ~120 bars, H4 ~120, H1 ~100, M15 ~60 (W1 resampled from D1 if needed).
- Regime, trend, ATR/ADX/RSI per timeframe (`TimeframeState`).
- Active evidence with its prices: chart patterns, Fibonacci, harmonics, SMC, S/R zones and their strength,
  each detector's invalidation and targets (`app/evidence/`).
- Session, spread, news blackout state (codes, never news text); later the L5 symbol profile.
- **Optional chart images** (engine-rendered PNG of D1/H4/H1 with the engine's levels drawn). Vision is good at
  overall shape but imprecise at exact prices, so prices always come from the numeric data. Whether the image
  adds anything is measured (numeric-only vs numeric+image in shadow), because it costs more.

### 3.2 The thesis (output, strict schema)

`ThesisV1` (`extra="forbid"`, echoes the symbol and bar like the existing schemas):

- `bias`: BULLISH / BEARISH / NEUTRAL, with a confidence 0–100
- `playbook`: TREND_RUNNER / RANGE / BREAKOUT / STAND_ASIDE (the same names as L20.1)
- up to 2 `scenarios` (primary and alternative), each with:
  - `side`, `entry_zone` [low, high], `invalidation` price, `targets` (≤ 3)
  - `trigger`: one value from a **closed enum** of triggers the engine already detects (reversal candle in the
    zone, LTF change of character, closed-bar break, Fibonacci golden-zone touch, …), never free text
- `key_levels` with roles, up to 5 short reasons citing the input, a TH/EN narrative
- `valid_for_bars` (capped)

### 3.3 Deterministic validation (the engine, before anything is stored as usable)

- Zone within N ATR of the current price; invalidation on the correct side of the zone.
- Stop distance ≤ `max_sl_atr`; RR from the zone to target 1 ≥ `min_rr` after spread; spread ≤ 15 % of the stop
  (the rules in `app/strategy/rules.py`).
- Trigger from the enum; expiry within the cap; a claim of profit or certainty is refused (`CLAIMS`).
- A failed check makes the thesis INVALID: recorded and shown, never usable.

### 3.4 Stages (each behind its own flag, default off)

| Stage | What the AI may do | Risk added | Needs |
|---|---|---|---|
| **A. Ask AI (on demand)** | PWA button on a symbol/chart: thesis shown with zones drawn on the chart. Same as giving a chart to an AI today, but with the engine's exact data | none | provider + key (exists) |
| **B. Shadow theses** | Theses on watchlist symbols at each H4 close; each tracked: zone reached? trigger fired? outcome in R? expired? | none (API cost only) | thesis tracker |
| **C. Filter** | An active thesis may **only remove** bot signals against its bias or outside its zones (or rank those inside higher) | none: it can only reduce | learning hook H1 (`CandidateFilter`) |
| **D. Armed watch plan** | The owner taps "Arm" (step-up) on a thesis; the engine waits for the zone and the trigger on a closed bar, then raises an ordinary `Signal` (strategy `ai_thesis`) that passes every gate. PAPER first, then DEMO | normal per-signal budget | hook H2 waiting entries (L19.3), PLAN revision |
| **E. Automatic arming** | Only if B and D show a credible edge with CIs, per symbol; always within the cage | normal | owner decision; never before Phase 14 sign-off for LIVE |

Stage D keeps the rule "never auto-apply anything that adds risk": the owner arms each plan, as they choose a
setup from an AI chat today, and the bot supplies the discipline (the trigger, the stop, the size, the gates).

## 4. Feasibility

### 4.1 Technical: high

Already in place:

- `AIProvider.ask` (any system prompt and schema), structured outputs, refusal/timeout handling, per-day budgets,
  per-key caching (`app/ai/`).
- Candles for D1/H4/H1/M15 (`chart_timeframes`), ~all evidence detectors with invalidation and targets.
- Opportunities, shadow tracking, calibration and the AI accuracy page (TAA-1305 measures opinion accuracy
  against shadow outcomes); entry plans (`SAME_PRICE`/`SCALE_IN`); the risk gates, sizer and mode gates.
- The planned learning hooks H1 (filter) and H2 (waiting entries) are exactly the insertion points for C and D.

New work: the chart pack, `ThesisV1` + validation + prompt, a theses table (migration, sync sample), the
thesis tracker, PWA pieces (Ask AI, zones on the chart, thesis list and accuracy, TH/EN keys), and for D the
armed-plan state machine.

### 4.2 Cost (estimate, Claude Opus 5.5 at $4 / $20 per MTok)

- One thesis: ~12k input tokens (chart pack) + ~1.5–3k output → **about $0.06–0.11**; +~$0.02 with three chart
  images. Sonnet 5.5 ($2 / $10) roughly halves it.
- Stage A on demand: cents per question.
- Stage B, 4 symbols × 6 H4 closes = 24 theses a day → **~$2–3 a day (~$60–80 a month)**; 10 symbols ≈ 2.5×.
- An LLM over all 549 symbols is not sensible; the AI reads only the tier-1 shortlist (L20.5) or the watchlist.

### 4.3 Latency

10–60 s per thesis is fine for an H4 thesis valid for hours; the M15/M5 trigger stays deterministic and instant.

### 4.4 The real unknown: does it add value?

- An LLM's chart reading **sounds** convincing; that is not evidence of an edge. Its confidence must be
  calibrated against outcomes like everything else (the existing AI accuracy page does this for opinions).
- **It can only be evaluated forward.** A backtest on history is contaminated: the model may have seen those
  prices in its training data. So stage B must run live for weeks before stage D makes sense. At 24 theses a
  day, a first read after ~3–4 weeks; per-symbol conclusions take longer (theses on the same day correlate).
- **Non-determinism and model changes:** the same chart can give a different thesis, and a new model version
  changes behavior. Record the model id and prompt version with every thesis; re-evaluate after a change.
- The comparison that matters: AI-thesis trades vs the bot's own signals vs a naive baseline, on the same
  symbols and period, in R after costs (the L20.0 expectancy split).

### 4.5 Safety (unchanged invariants)

- The AI never sizes, never widens a stop, never touches an open position, never bypasses risk, the mode gates,
  breakers or the kill switch. Its thesis expires.
- An AI outage means no new theses; the bot keeps working exactly as today.
- Inputs remain engine-made numbers, codes and engine-rendered images; no account data, no external text.

## 5. Recommendation

1. **Cheap deterministic win first, independent of the AI:** give the strategies an H4/D1 context (a third
   timeframe in the context builder) and build the L20.1 playbook router. Much of "the bot doesn't see the big
   picture" is fixed here, with no API cost and full testability.
2. **Then stages A + B together:** Ask AI in the PWA (immediate personal use, replaces copying charts into a
   chat) plus shadow theses on the watchlist, so value is measured from day one.
3. **C and D only after B has data**, and after the learning hooks (L002 H1, L19 H2) exist.
4. Decide the open questions below before any of it starts.

## 6. Decisions (owner, 2026-10-06/07)

| Question | Decision |
|---|---|
| Q-A1 AI may propose theses (PLAN revision 7) | **Accepted**: PLAN §A35 |
| Q-A2 first stage, model, budget | HTF context for the bot first, then Ask AI + shadow theses; Opus 5.5, hybrid: on demand plus a capped schedule |
| Q-A3 chart images | Numbers first; images later as a shadow A/B. AI-side plotting (code execution) adds nothing the numbers lack and is less reproducible: a later experiment at most (TAA-1610) |
| Q-A4 order | Phase 16 in docs/TICKETS.md; after the setup review (docs/SETUP_REVIEW.md) the timing and stop work (TAA-L702) comes first, because the review found the losses there |

## 7. Open questions (as first asked)

- Q-A1: Accept the change from "AI veto-only" to "AI may propose theses; the engine decides" (PLAN revision 7)?
- Q-A2: Which stage first, and with which model (Opus 5.5 vs Sonnet 5.5) and monthly budget?
- Q-A3: Chart images too (cost, A/B), or numeric data only at first?
- Q-A4: Where in the order: before, inside or after the learning track waves?
