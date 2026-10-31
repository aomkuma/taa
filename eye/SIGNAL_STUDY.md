# The signal study - the definitions it uses (one table, to be confirmed by the owner)

> **Parked 2026-10-30** - the owner: *"really, the principle is simple - find the turning point; SL and TP from ZigZag
> and Fibo; draw the levels right"*. The work went back to the bot's Fibonacci path (BOT_RULES rules 2-10) with the side
> from M15 structure (rule 16). Kept as a record; `eye/signal_study.py` (its piece 1) is reused by rule 16.

The study: for every structure-break event, which of the owner's conditions held at that moment, and what it gave in
R (`eye/BOT_RESEARCH.md`, "Which side of the 50 each signal falls on"). **This file is the only reference the study
reads.** Each row names its source and whose each part is: **(owner)** - the owner's words or answer in METHOD 2e /
LESSONS; **[Claude]** - Claude's definition where the owner gave none (a choice, for the owner to change). Nothing here
is a bot rule; `eye/BOT_RULES.md` and its rule 11 (failed) are not used. Revised 2026-10-30 after audits by Codex and
a fresh Sonnet (both: the first draft reduced the owner's entry sequence to one break).

## The event and the owner's sequence (for a BUY; a SELL is the mirror; METHOD 2e "The buy, written out", l.236-249)

| step | the owner's sequence | in the study | whose |
|---|---|---|---|
| S3 | the structure breaks - price takes out **the last swing high** | **the event**: an M15 close above `H` = the latest fixed M15 swing HIGH at that close, the side changing from SELL to BUY (strip B) | step 3 is Claude's generalisation of the owner's example (l.201-205); the M15 close rule [Claude] |
| S3b | the dip after it holds above the bottom - a **higher low** | after the event, the first swing LOW to be fixed, `D`, is above `L*` (the counter-move's lowest low, C2); a close below `L*` first ends the sequence (no S4 / S5) | Claude's generalisation (l.243-244) |
| S4 | **the high breaks** - price goes through the high that dip started from | `H2` = the latest fixed swing HIGH before `D`'s pivot bar (the high the dip started from); S4 = the first close above `H2` after `D` is fixed | Claude's generalisation (l.245) |
| S5 | **buy on the retest** of that broken high, turning up there | the owner's order: a Buy Stop Limit armed once S4 has closed, its limit at `H2`, **filled at the first touch** (a later bar's low at or below `H2`) - as the owner's order fills; the turn cannot be known when a limit fills, so it is recorded after the fill (an M15 close back above `H2` on one of the 2 bars after the fill bar), not required; the order waits until its stop is hit or the next opposite event (open value 6) | the retest: owner (*"break the low, then retest"*, l.219); the order: METHOD l.246-247; touch-fill, the recorded turn, the wait [Claude] |

## The conditions recorded at the event (closed bars only - pivots counted only once fixed)

| # | condition | definition used | source | whose |
|---|---|---|---|---|
| C1 | Settings | MT5 defaults: ZigZag 12 / 5 / 3, MACD 12 / 26 / 9 (`walk.macd_mt5`), RSI 14 | l.150 | owner |
| C2 | The counter-move | the stretch of strip B's previous side (SELL) that the event ends - from the last M15 close at which strip B's side changed to SELL (B as `eye/research/structure_side.py` computes it, one side per close) up to the event; its fixed swing LOWs in time order; `L*` = the lowest of them | l.341-347 | [Claude] |
| C3 | The count | the run of consecutive lower (or equal) fixed swing LOWs of the counter-move ending at `L*`: **3-5**, or **2 making the owner's M** (BUY, coming down into a support; W = SELL into a resistance) | l.147, l.168-176 | owner |
| C4 | The owner's M / W shape | the counter-move's last two fixed swing LOWs, the second within 35 % of the pattern's height of the first - the height = the highest swing HIGH between them minus the higher of the two lows; asymmetry allowed; judged by shape alone (whether it sits on a level is C8, apart) | l.179-181, l.195 | [Claude] |
| C5 | Divergence | at the counter-move's last two swing lows: price lower or equal, MACD **or** RSI higher (SELL: higher-or-equal high, oscillator lower high); which one(s) recorded; hidden divergence not used | l.148, l.251-261 | owner (one is enough); the comparison [Claude's rendering of the textbook] |
| C6 | Divergence required | for the 3-5 count; an M / W needs none | l.209-212 | owner |
| C7 | The structure at the level | fixed pivots only: the last two fixed M15 swing highs and the last two fixed swing lows, read at the event and again at the S5 fill: **HH and HL together** (BUY) / LH and LL (SELL). The owner's "chart pattern together with" it (METHOD 2b l.79-86) is recorded only as C3-C4's M / W; other named patterns are not detected | LESSONS 1 (l.5-8, l.21-24); METHOD 2b l.79-86 | owner; the pattern part partial [Claude] |
| C8 | A level from the left | the counter-move's extreme within **[open: band]** of an earlier fixed **[open: timeframe, H1 proposed]** pivot - recorded, not required (price usually turns before a level, l.153) | l.146, l.153, l.207 | owner (at support / resistance); the band, timeframe and "within" [Claude], open |
| C9 | The higher side | the M30 lean: **[open]** - recorded as the M30 structure side (a close beyond the latest fixed M30 swing, strip A), and separately "not clear" when strip A changed side within **[open]** | l.145 (never against a clear lean; not clear - M5's trend decides) | owner (the rule); the M30 reading **[Claude - not METHOD's lean, not BOT_RULES' state]** |
| C10 | M5 trend at the event | the last two fixed M5 swing highs and lows: up / down / mixed | l.145 (*"the trend that is traded is measured on M5"*) | owner (the rule); the reading [Claude] |
| C11 | Chasing | the price distance from `L*` to the entry, in R - recorded, no threshold (the owner gave none) | l.155 (*"don't let these happen"*: entering late) | owner (the rule); the measure [Claude] |
| C12 | The window | the event inside Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai - recorded, not required | METHOD 2c | owner (the windows); not requiring them [Claude] |

## The trade and its outcome

| # | item | definition used | source | whose |
|---|---|---|---|---|
| T1 | Entries measured | (a) at the event close - the mechanical baseline, **not the owner's entry**; (b) the owner's S5 retest | l.149, l.218-221 | (a) [Claude]; (b) owner |
| T2 | The stop | beyond the lowest low of the counter-move (BUY) / highest high (SELL) + **[open: buffer, the spread proposed]** | l.222-225 (the 2e entry; the Fibonacci entries' stop, l.311, is not this study) | owner; the buffer open |
| T3 | Reward floor | the trade counts only where the target gives **at least 1:2**; below that - *"no trade, for now"*; with T4 open, results are kept apart per target | l.158 | owner |
| T4 | The target | **[open - D1]**: the Fibo extension (161.8 %, else 127 %, else just before a major level) or just before the opposite level on the left | l.154, l.156, l.226-228 | owner, two statements |
| T5 | Held | until the stop or the target; no time limit; still open at the end of the data = `open`, not a result | l.157, l.263-266 | owner |
| T6 | Scored on | the signal and conditions on M15; the fill, stop and target on the finest stored bars - M5 from 2025-10, M15 before; a bar touching both the stop and the target counts as the stop | l.151, l.382-384 | M5 scoring: METHOD; the both-touched rule [Claude, conservative] |
| T7 | Also recorded | MFE in R before the stop, and whether 1 R / 2 R / 3 R came first - beside the target result | - | [Claude] |
| T8 | Costs | the spread stored with each bar (MT5 `spread`, points x point size); no slippage | the owner, 2026-10-20 - in Claude's memory only, not in a live document (to be written into METHOD when the owner confirms); the stored per-bar spread differs from BOT_RULES' fixed 0.30 | owner (spread only); per-bar [Claude] |
| T9 | Periods | discovery 2023-08 .. 2025-09 (M15 only); check 2025-10 .. 2026-10 (M15 + M5); October 2026 marked as already seen in earlier work | - | [Claude], following Codex's advice |

## Where the documents disagree, and what the study does

| # | the disagreement | where (METHOD unless named) | the study |
|---|---|---|---|
| D1 | Two targets: the Fibo extension vs just before the opposite level | l.154, l.156, l.226 | **owner to choose** (T4); both measured until then |
| D2 | Divergence "one is enough" vs the summary "MACD **and** RSI" and "nothing recorded about one alone" | l.148, l.209-213 vs l.161, l.212 | one is enough (the later explicit answer) |
| D3 | The higher timeframe: steps 1 and the buy steps, the summary and "What Claude understands" say H1; the owner moved it to M30 | l.160-162, l.207, l.239, l.341-356 vs l.145, l.314-316 | M30 |
| D4 | The side row names rule 11's state - it failed the market check | l.316 | not used; C9 instead |
| D5 | The Fibonacci count ("legs, both sides; any two-low pullback is one") vs the setup count (3-5, or 2 making an M / W) | l.313 vs l.147 | the setup count (C3) |
| D6 | The counting timeframe: "M5 or M15" is Claude's reading; the entry timeframe is M5 to M15 (owner) | l.151, l.213 | **M15 [Claude] - owner to confirm**; M5 as a variant |
| D7 | "At support / resistance" vs "a setup does not need its bottom / top on a level" | l.146, l.207 vs l.153 | the level recorded, not required (C8) |
| D8 | The stop: beyond the move's extreme (2e) vs beyond 0 % / 23 % (the Fibonacci entries) | l.222 vs l.311 | 2e's (T2) - this study is the 2e entry |
| D10 | "Trades in a range too" (no trade at all when sideways is a fault) | l.155 | **out of scope**: this study measures structure-break events; a range is not read (rule 11's reading failed); recorded later if the owner wants it |
| D9 | "Nothing in the setup is open any more" vs the open values here | l.375-376 | the open values stand until the owner sets them |

## The open values - **set by the owner, 2026-10-30: "use the proposed values"** (the values in brackets below are
## now the study's; wherever a row above says [open], it means the value set here)

1. **D1 / T4** - which target (proposed: measure both).
2. **D6** - count and divergence on M15 or M5 (proposed: M15, M5 as a variant).
3. **C8** - the band around a level from the left, and its timeframe (proposed: H1 pivots, a band of the spread x 10).
4. **C9** - how the M30 lean is read, and when it is "not clear" (proposed: strip A; not clear if it changed side in
   the last 4 M30 bars).
5. **T2** - the stop buffer (proposed: the spread).
6. **S5** - how long the retest order may wait (proposed: until its stop is hit or the next opposite event).
