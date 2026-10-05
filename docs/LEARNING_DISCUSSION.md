# Learning Layer — Discussion Record

Record of the design conversation of 2026-10-06 between the owner and Claude Code. It explains *why*
[PLAN_LEARNING.md](PLAN_LEARNING.md) and [TICKETS_LEARNING.md](TICKETS_LEARNING.md) look the way they do, so the
reasoning is not lost with the chat. The conversation was in Thai. It is summarized here in English (project
docs rule), and the owner's key statements are quoted in Thai with a translation. No profitability claims: every
idea here is about improving the *odds and the process*, not promising results.

---

## 1. Can the AI learn each symbol's character and use ticks?

**Owner's question:** Is there a way for the AI to learn the "habits" of each symbol: how it moves, sharper entry
signals from ticks, where price is likely to go from ticks, buying and selling pressure, and so on?

**Answer: yes, within what the data allows.**

**Data reality (FBS × MT5):**

- For FX/CFD, `tick_volume` counts quote changes. It is not traded volume, and `real_volume` is 0.
- There is no central order book (OTC). FBS advertises DOM in MT5, but for FX it would be the broker's own quote
  ladder, if anything. This needs a probe before relying on it (TAA-L001).
- Tick history depth is whatever the broker keeps. So we must record ticks ourselves.
- Therefore **true buy/sell pressure is not observable**. We only have proxies: uptick/downtick imbalance, tick
  intensity, spread behavior and price velocity. They describe *this broker's feed*.
- Existing pieces: `copy_ticks_range` in the gateway (used by shadow resolution), and the `volume.tick_spike`
  detector.

**Learning the symbol's character** is the most valuable and the safest part. It is statistics rather than deep
learning, and it can be explained:

- volatility and spread by hour of week
- trend vs mean-reversion tendency (autocorrelation, variance ratio, Hurst via DFA, with confidence intervals)
- breakout follow-through vs false-break rates, and MFE/MAE in ATR
- respect for levels, session character, gaps, news sensitivity, correlation clusters and regime

The engine computes this weekly and versions it ("compute once").

**Ticks for entries:** use them as a *filter and timing* tool, not a direction predictor. Two uses fit:

- confirm a closed-bar signal within minutes
- avoid entries during a spread blow-up, a quote stall or a spike

HFT-style prediction is not realistic: home-network + MT5 latency is hundreds of ms, and spread and commission eat
any micro edge.

**Which AI, in order:**

1. Statistical profiles.
2. Meta-labeling with gradient-boosted trees. The model does not find entries; it scores the signals our
   strategies produce. Shadow trades already provide the labels.
3. A regime classifier.
4. Deep learning or RL: not now (data-hungry, overfits, cannot be explained).
5. LLM: narrative only.

**Pitfalls to design against:**

- overfitting (use walk-forward and purged CV, never random splits)
- costs in the labels from day one
- non-stationarity (drift monitoring and automatic demotion)
- the model can only veto or explain, never bypass risk or the mode gates
- shadow evaluation in PAPER first

**Research notes:**

- Order-flow imbalance predicts only seconds to about a minute ahead, and on exchange books with sizes
  (Cont, Kukanov & Stoikov 2014; arXiv:2112.02947).
- Evans & Lyons (2002) explain 40–80% of daily FX moves with *interdealer* signed flow, which retail MT5 cannot
  see.
- LightGBM stores models as text (`model_to_string` / `Booster(model_str=...)`), so no pickle is needed.

## 2. "Right direction, wrong timing"

**Owner's statement:** traders often read the direction correctly but still lose because of *timing*: when the
price will actually move that way. The owner thought the planned work could help.

**Answer: diagnose first, because the losses come from different failure modes:**

| Mode | What happens | Real cause |
|---|---|---|
| Too early | SL hit first, then price goes to TP | Stop inside normal noise; no trigger |
| Too late (chase) | Entered after the move; a normal pullback stops it out | No wait for a pullback; worse effective RR |
| Not yet | Price drifts sideways until time stop, manual close or swap | Quiet session or wrong regime |
| Timeframe mismatch | HTF right, entry TF still against | Direction and timing judged on one TF |

**Measurable now from existing data:**

- the vindicated-stop rate (an SL hit followed by the TP)
- the MAE of winners
- time to target
- comparison with the owner's own manual trades (TAA-1006)

**Nine remedies:**

1. Separate the HTF direction from the LTF trigger.
2. Let price come to us: learned pullback limits on top of the existing `SCALE_IN`.
3. Stops outside the symbol's hourly noise, with smaller lots so the risk % is unchanged.
4. Enter when liquidity arrives (session opens).
5. Volatility compression as a "move is coming" signal; it says nothing about direction.
6. Tick confirmation.
7. A learned time stop.
8. One budget-capped re-entry.
9. A time-to-move model ("similar setups reached target in ~X–Y h").

Every remedy trades one error for another (missed trades, worse price, smaller lots). So each is evaluated as a
**shadow variant** with paired A/B statistics on the same opportunities.

**Research notes:**

- Squeeze, NR7 and inside days only say "expansion likely"; they are direction-neutral.
- First-passage theory gives a random-walk baseline: P(TP first) = b/(a+b), E[time] = a·b/σ². This separates
  "noise would hit this stop anyway" from real timing problems, and it motivates a hazard model with censoring.

→ PLAN_LEARNING §L19, Phase L7.

## 3. Closing the human gaps with playbooks

**Owner's statement (Thai):** "ที่ต้องมีระบบนี้เพื่อต้องการปิดจุดอ่อนของ"คน" เพราะคนมีอารมณ์ความรู้สึก
ความถนัดเทรดแบบเทรนด์, แบบ sideway ถนัดบางสินทรัพย์ โดยระบบนี้เน้นเทรดทุกโอกาสแบบ sniper ก็ได้ ถือรันเทรนด์
เมื่อภาพที่ใหญ่กว่าเกิดเทรนด์ได้ เทรดแบบ sideway ได้"

*Translation:* the system exists to close human weaknesses: emotions, and a bias toward trend or sideways
trading or toward certain assets. It should take every opportunity sniper-style, hold and run a trend when the
bigger picture trends, and trade sideways markets too.

**Answer:**

| Human weakness | What the system does instead |
|---|---|
| Emotions (fear, greed, FOMO, revenge) | The same rules every time, chase guard, budget-capped re-entry, breakers, kill switch |
| Can't hold winners | Rule-based trailing |
| One style only | A playbook per market state, not per trader habit |
| Few assets, few screens | Scans every symbol 24/5, with a per-symbol profile |
| Doesn't know why they lose | Shadow measurement and timing diagnostics |

**Playbooks:**

- **Trend runner** (HTF trend): pullback entries with an LTF trigger; part A takes profit at 1.5R; part B runs
  with a structure or chandelier trail; budget-capped adds.
- **Range** (clear HTF range): edge entries after rejection; TP at the middle or the opposite edge; exit when the
  range breaks.
- **Breakout** (compression, then a break).
- **Stand aside** (unclear, volatile, news or spread stress). This is the hardest for humans and the easiest for
  the system.

**Honest notes:**

- The system is not good at every style automatically. Each playbook must show an edge per symbol, or it is not
  used there.
- "Every opportunity" is still bounded by heat and correlation.
- The system's advantage is consistency and measurement, not being right more often.

→ PLAN_LEARNING §L20, Phase L8.

## 4. Guiding principle

**Owner's statement (Thai):** "โอเคว่ากำไรมันคาดการณ์ไม่ได้ แต่เราจะสร้างโอกาสให้การเทรดใกล้เคียงกับกำไรมากที่สุด"

*Translation:* profit cannot be predicted, but we will create the conditions that bring trading as close to
profit as possible.

**Principle:** a single trade's outcome is unpredictable. The *expected value* over many trades is what we
design: **E[R] = p·W − (1−p)·L − c**, plus the number of independent opportunities (n), survival and discipline.
Every component of the track maps to one lever:

| Lever | Components |
|---|---|
| p (better signals) | Signal-quality model, fit matrix, router |
| W (bigger winners) | Runner |
| L (smaller losers) | Timing, confirmation, time stop |
| c (lower costs) | Costly hours, spread filters |
| n (more opportunities) | Scan everything, range playbook |
| Survival | Sizing, breakers, heat, correlation selection |
| Discipline | Behavior report |

Progress is judged on these process metrics with CIs, never on single trades. → PLAN_LEARNING §L20.0.

## 5. A squad of specialist bots

**Owner's statement (Thai):** "มันเหมือนเรามีกองกำลังนักเทรดมือฉมังออกไปรบบนกระดานเทรดที่แต่ละคน (แต่ละ bot)
ความถนัดต่างกัน เห็นโอกาสต่างกันช่วยกันเก็บกำไรคนละเล็กละน้อย ... แบบเดิมก็ยังต้องทำได้เช่นกัน"

*Translation:* it is like a squad of skilled traders on the board. Each one (each bot) has a different specialty
and sees different opportunities, and together they collect small profits. The old single mode must still work
too.

**Answer (checked against the code):**

**What the code does today:**

- one engine, one risk set, one TF pair (H1/M15) for all strategies
- BUY vs SELL on one symbol cancels both
- scanning covers the 549-symbol catalog in the ranking, but strategies run only on the monitored set (cap 60),
  and trading only on `ALLOWED_SYMBOLS` (4)
- **latent issue found:** magic numbers are `MAGIC_NUMBER_BASE + index` of enabled strategies, so
  enabling/disabling/reordering strategies re-maps open positions

**Design:**

- **Bots** with their own playbooks, TFs, scope, sessions, entry/exit style and risk share.
- A **commander** that:
  - resolves cross-bot conflicts (`net_direction` by default; netting accounts never hold opposite positions)
  - deduplicates correlated exposure
  - allocates the budget inside the account cage
- **Shared computation**, so CPU does not grow with the number of bots.
- An **evidence-based allocation** that pauses bots without an edge (shadow kept).
- A **stable magic registry**.
- **Legacy mode** = one implicit `default` bot, identical behavior (golden test).

**Starting roster:** `trend_rider`, `range_sniper`, `breakout_hunter`, `pattern_specialist`, `session_opener`,
`crypto_247`.

→ PLAN_LEARNING §L21, Phase L9.

## 6. Decisions log

| Date | Decision | Where recorded |
|---|---|---|
| 2026-10-06 | The learning layer is a separate track (its own plan and tickets) | PLAN_LEARNING, TICKETS_LEARNING |
| 2026-10-06 | Q1: no early start (not even tick capture); Phase 14 + wrap-up first | §L16 |
| 2026-10-06 | Q9: evaluate risk-free adds (shadow, max 2; real adds off until L13) | §L18 |
| 2026-10-06 | Q10: scan everything tradable | §L18, TAA-L806/L906 |
| 2026-10-06 | New work is **built separately from the existing process**: new modules read existing outputs and plug in through defined, default-off hook points; the existing path stays unchanged | §L0.2 |
| 2026-10-06 | Claude orders the work by suitability | §L16, TICKETS_LEARNING "Waves" |
| 2026-10-06 | Session discussions are kept in project `.md` files (this file) | — |
| 2026-10-06 | While the other session finishes Phase 14 / wrap-up, parts of this track that do not collide with it may be picked up (supersedes the strict reading of Q1 for non-conflicting work). Started with the pure parts of TAA-L701 and TAA-L801 in `app/learning/` | TICKETS_LEARNING |

**Open questions:** PLAN_LEARNING §L18 (Q2–Q8, Q11–Q12).

## 7. Re-check of the plan (2026-10-06)

The owner asked for a re-check of everything planned. Both files were read end to end against this record and
the existing system. The fixes (all in PLAN_LEARNING and TICKETS_LEARNING):

**Contradictions with the separation rule (§L0.2):**

- Entry confirmation moved from `app/engine/` to `app/learning/` (hook H2).
- The new timing detectors go into a new `app/evidence/timing.py`; existing detector files are not edited.
- Selection "extends arbitration" became "runs after arbitration through H1".

**Layering:** hook protocols are structural, so `app.learning` (layer 9) never imports `app.engine` (layer 10).
The backtester and replay call the same hooks.

**Clashes with existing engine rules that the plan had not handled:**

- Trading signals expire after 1 entry bar (`signal_expiry_bars`), which would kill pullback and trigger
  entries. Waiting modes now get their own `entry_window_bars` and re-check invalidation while waiting.
- The arbitration cooldown would block re-entries. A re-entry is now part of the same signal/idea.
- `max_positions_per_symbol: 1` would block runner parts and adds. Under the flags, limits count ideas while
  risk sums all parts.
- The engine-wide Friday cut-off and sessions would stop the crypto bot at weekends. Bots may declare their own
  sessions within their scope.

**Safety gap:** evidence-based allocation could raise a bot's risk share automatically. Now only decreases are
automatic, and increases are owner-confirmed proposals ("never auto-apply" anything that adds risk).

**Missing pieces added:**

- TAA-L002 (hook points + golden harness)
- a profile data budget for hundreds of symbols
- schedule rows for reports and allocation
- API routes for timing, expectancy, playbooks, behavior and squad
- acceptance rows for `independent` and evidence allocation
- project test rules (sync sample rows, API samples, full test runs with the stack stopped)

**Risks added:** multiple comparisons across bots × variants × symbols, higher total costs from many small
trades, CFD and crypto specifics, and the single-account view of affordability.

**Clarified:** section numbers (§L8 = fit matrix) vs ticket phases (Phase L8 = playbooks).

## 8. Sources consulted

- FBS review (DOM offered in MT5): https://www.fxempire.com/brokers/fbs
- MT5 Depth of Market help: https://www.metatrader5.com/en/terminal/help/trading/depth_of_market
- MQL5 book, reading tick history from Python: https://www.mql5.com/en/book/advanced/python/python_copyticks
- Order-flow imbalance overview: https://www.emergentmind.com/topics/order-flow-imbalance
- Generalized OFI price impact: https://arxiv.org/pdf/2112.02947
- Evans & Lyons, Order Flow and Exchange Rate Dynamics: https://faculty.georgetown.edu/evansm1/wpapers_files/orderflow.pdf
- LightGBM Booster API: https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.Booster.html
- NR4/NR7 narrow-range bars: https://www.luxalgo.com/library/concept/nr4-nr7-narrow-range-bars/
- Volatility compression → expansion: https://bookmap.com/blog/narrow-range-breakouts-why-volatility-compression-leads-to-expansion
- First-passage time distribution: https://metricgate.com/docs/first-passage-time/
- Redner, A First Look at First-Passage Processes: https://arxiv.org/pdf/2201.10048
