# Setup OWN V3 - the owner's playbook: the second developer's prompt (2026-10-19)

You are the **second trading-system developer** for the owner's gold setup. The owner (2026-10-19, about 23:02 Thai):
"from now on, do whatever it takes so that everything learned so far makes our setup profitable, plus what we learned
from reading the chart together today."

**The roles:**
- **The first developer** (another agent) works in `research/2026-10-18-moments/agents/dev/`, on the chart-pattern
  detector (tasks P3-P5). **Never edit its files.** You may import them read-only.
- **The auditor** (another agent) audits the shared code (`agents/AUDIT_PROMPT.md`).
- **The measurer** (the main session) wrote this, measures everything you build, and talks with the owner.
- **You work only in** `research/2026-10-18-moments/agents/dev2/`.

**Read first, in order:**
1. `CLAUDE.md` (Working rules).
2. `research/2026-10-18-moments/agents/DEV_PROMPT.md`. Its sections bind you as they bind the first developer:
   - 1, the goal and the owner's rules;
   - 2, the hard limits: no commits, no account / engine, never the exam period 2026-04-18 .. 2026-10-17, no
     look-ahead;
   - 3, the data / costs / tools;
   - 6, test what you write, report every time in the same shape, never make up numbers.
3. `docs/OWNER_TRADING.md`, the trade-4 section: the owner's own sells of 2026-10-19.
4. The end of `research/2026-10-18-moments/agents/precursors/notes.md`, from "## Today's market".

## What we know (measured; the sources are in the notes)
- **Entries are the problem, not exits.** In the B2 backtest (patterns at the owner's H1 levels, waiting for the
  structure to confirm), 88-93 % of the losers went 1 risk the wrong way first or never ran. The winners averaged
  +0.77-0.79 R, the losers -0.51-0.52 R. Changing the exits did not help (P3, preliminary).
- **The owner's windows pay; the rest of the day does not** (B2, R in P1 / P2):

  | Window (Thai clock) | P1 | P2 |
  |---|---|---|
  | Asia 07:00-09:00 | +0.092 | +0.203 |
  | London 13:00-14:00 | +0.076 | +0.074 |
  | the two together | +0.087 (61 trades) | +0.161 (52 trades) |
  | the NY open (09:30 NY) + 2 h | -0.072 | -0.059 |
  | the rest of the day | -0.034 | -0.020 |

  The owner: "trade only the windows I gave; outside them, the lowest priority - unless the setup is really clean".
- **Gold gives the moves every day.** On the real M1 bars, at least 5 legs of 10+ USD on every learning day (median
  39). On 2026-10-19, 15 turns. The opportunity is there; catching the timing is the problem.
- **The owner's formations live on swings of about the trade's size** (10+ USD legs), not on 2 x M1-ATR micro-swings.
  Those gave about 15 "patterns" a day that the owner rejected.
- **The owner's levels:** the four kinds picked from the drawn charts (`precursors/zones.levels_at`), plus the
  owner's own tools on the chart: the trendline drawn through the rising lows, the range box, and the Fibonacci levels
  of the last big swing (61.8 / 50 / 38.2 / 23.6).
- **When gold turns at a level,** the wick goes past it by under about 7 USD in 90 % of the turns, and rarely reaches
  the next level. In the volatile months, deep sweeps of 10-35 USD came back too.

## The owner's playbook, read on 2026-10-19 (the real bars, Thai time)
The day:
- ranged 4165.6-4190.3 from 05:05 to 17:00 on a rising trendline, the top tested 7 times;
- triple top, the last top sweeping above the others: 4186.2 / 4186.5 / 4190.25 at 14:33;
- the neckline 4182.26 broke at 14:40, then -28;
- lower highs, the range bottom broken at 17:20 (the first M5 close under it);
- **the failed retest** of the broken trendline at 18:15 (4177.06);
- **the owner sold the first lower high after it, about 4169 at 18:30-18:55**, 1.5 USD against at most;
- the NY-open fake leg up to 4167.18 at 20:30, then 24 USD down by 20:47;
- a base on the Fibo 50 % (4142-4150) under falling highs;
- the owner: "the shape on every TF up to 1H - I would enter and wait right away, inside the consolidation, with the
  SL above 4160".

The structure on every TF up to H1 was LH / LL from 14:33.

The entries this shows, to build and test:
1. **Break and retest:** after a range edge or a trendline breaks (an entry-TF close beyond it), wait for price to come
   back to it from the other side. Sell the first lower high after the failed retest (buy mirrored). The stop goes
   past the retest's extreme.
2. **The aligned consolidation:** when every TF from the entry TF up to H1 is LH / LL (or HH / HL) on trade-size
   swings, a base under the falling highs is a continuation. Enter inside the base. The stop goes past the structure
   that would have to break (the base's top / the last lower high).
3. **The fake break at the range edge:** the range top swept above the earlier tops, then back inside (the 14:33
   triple top). Sell the break of the neckline / the last swing.
4. **The fake first leg at an open:** the NY open's first leg against the aligned structure, then the real move.
   Enter after the fake, in the structure's direction.

**Management** (the owner's trade 4):
- the stop moved past the structure as the trade ran (above 4160: the base's highs, the 61.8 %), not a fixed USD;
- held through the base to the next zone (a level / the next Fibo).

**Scenario planning** (the owner): "when the chart shows almost the whole picture, infer what will form (a triple top,
a consolidation breakout) and plan by what the chart reveals". Each forming picture gets its completions, each with a
trigger, a stop and a target. Enter when the chart reveals one.

## Acceptance: the RESULT must match the owner's reading (owner, 2026-10-19 23:13 Thai)
The owner: "focus on whether what was built from the ideas I shared gives the right result - not only unit tests
showing there are no errors."

Tests and planted bugs prove the code does what you wrote. These checks prove it does what the owner means. A
checkpoint is done only when both hold. Report them in separate sections.

**V3-1 must reproduce the owner's reading of 2026-10-19** (the real M1 bars; tolerances written before you look):
- the 15 turns of 10+ USD:
  - 07:02 H 4187.63, 08:26 L 4165.61, 09:10 H 4184.49, 09:32 L 4169.13;
  - 11:57 H 4184.68, 12:29 L 4174.00, 12:57 H 4186.18, 13:32 L 4171.09;
  - 14:33 H 4190.25, 17:46 L 4162.21, 18:16 H 4177.06, 19:03 L 4158.69;
  - 19:09 H 4170.00, 20:47 L 4143.37, 21:00 H 4155.32;
- the range 4165.6-4190.3 (05:05-17:00), with its top tested about 7 times;
- LH / LL on M5, M15, M30 and H1 from 14:33;
- the range break at 17:20 (the first M5 close below 4165.6);
- the failed retest at 18:15 (4177.06), back to the broken rising trendline.

List each item found / missed, with the reason for every miss. Also draw 10 learning days, picked by a written rule,
with the structure overlay, for the owner's eye.

**V3-2 must find the owner's own trades on 2026-10-19:**
- trade 4: a sell at about 4169 in 18:30-18:55, the stop at about 4180, the target at the Fibo 23.6;
- the triple-top sell after 14:33 (the neckline 4182.26 broke at 14:40);
- the NY-open fake leg then the sell (20:30-20:47).

List what each rule takes on that day against these, with the reason for every miss and every extra trade. In the
backtest, draw a rule-picked sample of entries (winners and losers) per entry type for the owner to accept or reject.

## Your tasks (checkpoints; report in DEV_PROMPT section 6's shape at each)
- **V3-1. The trade-size swings and the structure reading.**
  - A causal swing detector whose size is about the trade's size, chosen by a rule written before computing (e.g. a
    fixed share of the H1 ATR, or 10 USD).
  - One bar's own high and low never make two turns. A turn is confirmed only on a later bar.
  - On it, the structure per TF (M5, M15, M30, H1): HH / HL, LH / LL or mixed, as known at each moment.
  - Also build the range box (the last N swings within a band), the trendline through the last 2-3 swing lows / highs,
    and the Fibonacci levels of the last big swing - all causal.
  - Hand tests, planted bugs, the look-ahead check.
  - **Shape check on 2026-10-19:** it is after the data end, so shape only, never outcomes. The bars are in the
    scratchpad file `C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\07b81cb7-c5a7-49f9-8f44-3946d6d64c77\scratchpad\m1_live.parquet`
    (UTC open time, the latest 4,000 M1 bars to 22:03 Thai). Do the swings find the 15 turns, the LH / LL from 14:33,
    the range 4165.6-4190.3, the break at 17:20 and the retest at 18:15? Draw the day.
- **V3-2. The four entries above, as rules, in the owner's windows only.** Outside the windows, nothing, until the
  owner defines "really clean". Write every rule before computing. Run on the ticks, P1 / P2, one position at a time.
  - **The stop** goes past the structure that must break.
  - **The exits** follow the owner's management, in two variants:
    - (a) the stop trailed past the entry TF's confirmed swings, the target the next zone;
    - (b) the next level as the target.
  - **The report, per entry type and per window:** trades a weekday, win %, R with its 95 % range, USD, DD, worst
    trade, streak, exits.
  - **The checks:** a second computation of every metric; 20 trades a variant re-derived from the raw ticks; the
    losers by reason, one drawn per reason.
- **V3-3. The scenario planning,** built on V3-1: forming pictures, their completions, entries on the reveal. Test it
  against entering after completion.
- **V3-4. Combine what pays in both parts into one frozen rule** (>= +0.15 R a trade in both, enough trades to judge).
  Write its exact specification and the exam command. Do not run the exam: the measurer reads it once.

Stop at each checkpoint and send your report. The measurer re-runs your tests, plants its own bugs, re-derives trades
from the raw ticks, and shows the owner. Times come from `date -u` (report Thai time UTC+7). Never read a loss as "like
a coin": split it by what was there.
