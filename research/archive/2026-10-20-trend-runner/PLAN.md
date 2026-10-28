# Setup TREND-RUNNER (TR1) - research plan

Written before implementation or measurement: 2026-10-20 13:48 Thai time (06:48 UTC).

## 1. Mandate

Build a separate setup that looks for a low-risk continuation entry after an opening impulse and, only when the
market proves that the move is persistent, holds a runner beyond the fast exits used by PLAN-1.

This is a new setup, not a PLAN-1 exit variant and not Setup OWN V3. Its working name is **TREND-RUNNER** and its
research id is **TR1**.

The research must answer two different questions:

1. Can a causal, structure-based pullback entry produce positive expectancy after the spread?
2. Given the same entry, can a conditional runner capture more net R than a fast fixed exit without making the
   drawdown or dependence on a few outliers unacceptable?

Past results describe the sample only. They are not a claim of future profitability.

## 2. Isolation contract

All TR1 source, tests, logs, generated tables and charts stay under this directory during research.

TR1 must not:

- edit or import setup-specific code from `agents/dev/`, `agents/dev2/`, `agents/strategist/` or PLAN-1;
- change PLAN-1's frozen rules, outputs, weights or exam state;
- write into `app/strategy/`, `config.yaml` or an engine database during research;
- read data at or after 2026-04-18 until a rule is frozen and the one exam run is authorized;
- use an outcome, a future bar or a later tick to choose an entry, stop, trail or market state;
- tune a rule on P2 after P2 has been opened for that frozen round.

TR1 may reuse only neutral infrastructure:

- the raw Parquet bar and tick stores;
- stable `app/` types and time utilities that do not encode another setup;
- audited formulas as a reference for an independent implementation and cross-check.

If a shared structure reader is wanted later, it must first have a frozen public interface. TR1 will consume it
through a small adapter; it will never reach into another setup's internal files.

## 3. Data boundary and costs

| Purpose | Inclusive dates | Rule |
|---|---|---|
| P1 design | 2025-10-18 .. 2026-01-15 | May be inspected and used to choose the frozen rule |
| P2 validation | 2026-01-16 .. 2026-04-17 | Open only after the round is frozen; no tuning on its result |
| Exam | 2026-04-18 .. 2026-10-17 | One read by the measurer after all acceptance gates pass |

Gold is XAUUSD on FBS-Demo. Bars and ticks are interpreted in UTC internally. User-facing times are Thai time.
New York anchors are DST-aware.

The primary cost is the observed bid/ask spread. Entry slippage is a parameter whose default is 0, following the
owner's current decision. Sensitivity runs may add slippage, but may not replace the spread-only primary result.
R is net P&L after costs divided by the initial price risk. Stops may tighten but never widen after entry.

## 4. What is known before TR1

- PLAN-1 is mainly a fast-exit plan: London is capped around 60 minutes and the NY 08:30 straddle around 30 minutes.
- Blindly holding the NY entry longer is not stable. In the existing developer study, the 08:30 entry improved in P1
  but deteriorated in P2 after 60 minutes. A runner therefore needs an activation test; time alone is insufficient.
- Asia B2 and the London ORB have behaved like range/sideways pieces. The NY straddle has paid mainly in a D1 trend.
- Immediate break-even and small-TF trailing did not rescue the old B2 stream. TR1 may move a stop only after a new
  confirmed structure exists.
- A result depending on one crash trade is not acceptable. Results must be shown without the best one and best three
  trades.

## 5. Setup concept

TR1 has four causal stages.

### 5.1 Opening impulse

Observe one of the owner's moments without entering immediately:

- Asia from 07:00 Thai;
- London from 13:00 Thai;
- New York from 08:30 New York.

The first round studies one common, relative definition of an impulse across the three windows. Its size is expressed
in the H1 ATR available at the anchor, never in a fixed number of dollars. The P1 study may compare at most three
neighbouring impulse thresholds. It reports every threshold tried.

### 5.2 First valid pullback

After an impulse, wait for the first pullback that:

- stays on the impulse side of its origin;
- forms a causal local extreme on M1, M5 or M15;
- has a risk small enough relative to the H1 ATR;
- leaves sufficient open space before the next known larger-TF level.

The entry is the first continuation close or stop trigger beyond the pullback's micro structure. The initial stop is
beyond the pullback extreme plus a spread/volatility buffer. The same fill and stop are used by every exit variant so
the exit comparison is on a fixed entry population.

### 5.3 Runner activation

Every entry begins as a normal trade. It becomes a runner only after observable evidence, chosen on P1 and frozen
before P2. Candidate evidence is limited to:

- progress in R within a fixed number of entry-TF bars;
- a new higher low/lower high and continuation extreme on M5;
- an M15 close that holds beyond the broken session structure;
- M15-H1 direction not opposing the trade;
- no nearby larger-TF level that removes the remaining reward.

No outcome label or maximum future excursion is available to this gate.

### 5.4 Exit ladder

The initial comparison uses the same entries and initial risk:

1. **FAST:** the control, a fixed target and time exit.
2. **SWING:** no partial; after activation, trail behind confirmed M5 structure, graduating to M15 structure after
   sufficient progress.
3. **SPLIT:** take a predeclared fraction at the fast target and trail the remainder exactly as SWING.
4. **STATE:** use FAST when the runner gate fails and SWING when it passes.

At most these four exit families are tested in round 1. Parameter neighbours are declared before execution. A stop
never moves farther from price, and a trail uses only structure confirmed at that tick.

## 6. Research sequence

### Phase A - foundation

1. Write an exam-proof bar/tick loader that filters in the Parquet reader and refuses exam dates before opening a tick
   file.
2. Record the data manifest: files, row counts, first/last timestamps, timezone and duplicate/gap counts.
3. Build M5/M15/H1 causally from M1 and cross-check against the stored broker bars.
4. Build the bid/ask fill simulator with hand-worked tests for gaps, a tick touching both levels, timeout and spread.
5. Add no-look-ahead truncation tests and planted bugs before any result is measured.

### Phase B - P1 opportunity study

This is descriptive and uses P1 only. For each window, measure:

- the distribution of the first impulse in H1-ATR units;
- whether a first pullback exists and its depth, duration and entry-TF risk;
- future first passage to +1R, +2R, +3R and +5R from the same causal entry;
- maximum adverse excursion before each milestone;
- continuation after the fast target and giveback before the proposed swing exit;
- collisions with the next session and the time spent in market.

The study must publish the full distributions and counts, not select attractive chart examples.

### Phase C - freeze round 1

Using P1 only:

1. Select one impulse threshold and its immediate neighbours.
2. Freeze the pullback, entry-TF choice, entry, initial stop and level-space rules.
3. Freeze one runner gate and the four exit families.
4. Write the exact rules and hashes of the code/config into `FROZEN_ROUND_1.md`.
5. Run an independent implementation on a sample and draw twelve P1 trades for visual acceptance.

Only after this phase may the P2 reader be enabled.

### Phase D - P2 validation

Run the frozen round once on P2. Report every predeclared neighbour, but do not change the rule. A failed P2 is marked
FAIL with its lesson; the next round must be written before another P2-derived change is measured.

### Phase E - robustness and portfolio interaction

- Re-derive every trade from raw ticks with an independent loop.
- Re-run all tests and planted bugs.
- Report results by window, direction, month, week and market state.
- Remove the best one and best three trades and report the result again.
- Compare standalone TR1 with a read-only portfolio simulation beside PLAN-1. Neither setup's trade list is altered.
- Report position collisions and the opportunity cost of one-position-at-a-time.

### Phase F - exam and engine, only after a pass

The exam remains locked until the checklist's pre-exam gate is complete. If the frozen rule passes the learning gates,
the measurer runs the exam once and records the command and hashes. Engine work starts only after that result is
accepted; it will use a separate strategy module and configuration lane.

## 7. Acceptance gates

The fixed project goal remains the primary bar:

- mean net R/trade at least +0.15 in P1 and P2;
- at least 30 executed trades in each part;
- the pooled 95% interval and every setting tried are reported;
- frequency and exposure are reported against the owner's 2-3-trades-a-day portfolio goal;
- no dependence on one exceptional trade: removing the best trade must not reverse both parts below zero;
- no look-ahead fault, exam read, uncaught material mutant or unexplained independent-replay difference;
- maximum drawdown, worst trade, losing streak, hold time and weekly results are reported in R and USD at 0.01 lot;
- the runner must improve a predeclared combination of net R, retained MFE and/or drawdown over FAST on the same
  entries. A higher headline R with materially worse tail risk is not automatically a pass.

A low-frequency result or a result with fewer than 30 trades per part is PARTIAL, never PASS.

## 8. Reporting discipline

Every measurement entry records:

- the question and rules written before the run;
- files and data periods read;
- exact command and timestamp;
- tests and planted bugs;
- counts, net R, USD, confidence range and robustness cuts;
- what failed and the next permitted change.

`CHECKLIST.md` is updated at every checkpoint. Generated outputs are not committed until their producing code and the
reproduction command are known.
