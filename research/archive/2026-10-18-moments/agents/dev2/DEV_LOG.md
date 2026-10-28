# Setup OWN V3 - the second developer's log (`research/2026-10-18-moments/agents/dev2/`)

Times are UTC from `date -u` (reports to the owner in Thai time, UTC+7). The exam period 2026-04-18 .. 2026-10-17 is
never read: the learning bars are read with a filter `2025-08-01 <= open_time < 2026-04-18` (August .. mid-October
2025 is warm-up only), the live file with a filter `open_time >= 2026-10-18 00:00 UTC`.

## V3-1 - the trade-size swings, the structure per TF, the range box / trendline / Fibonacci

### Written before computing (V3-1): the rules (16:13 UTC, `date -u`)

Nothing below was run before it was written. The only facts used are the owner's words, the brief and the numbers
quoted from other logs (named).

1. **The swing size S (USD), at every M1 bar d, known at d's close (open + 1 minute):**
   `S_d = max(10, 0.6 x ATR14 of the last H1 bar complete by d's close)`.
   - 10 USD: the owner's trade size ("a 10-USD move is small"; the brief: the formations live on 10+ USD legs; the
     measurer's count of 2026-10-19 used a fixed 10).
   - 0.6: the first developer's P5 log gives P1's median H1 ATR as 16.3 USD; 0.6 x 16.3 = 9.8, so in the calm P1 the
     two terms meet near 10. In volatile phases (P2's median 28.1 -> about 17) the swing grows with H1, so a leg
     smaller than about half an H1 bar is not read as structure. I re-measure both medians after writing this; the
     measurement does not change the rule.
   - Warm-up (only on the shape day, which has no allowed history before it): while ATR14 of H1 is undefined, the ATR
     is the mean true range of the complete H1 bars so far (the first bar's true range = its high - low); before the
     first complete H1 bar, S = 10.
2. **The swing detector** (a causal ZigZag on any TF's closed bars, threshold thr[i] per bar):
   - Before the first pivot: the highest high and the lowest low so far (the first bar keeps a tie). When they sit on
     different bars and are at least thr[i] apart, the earlier one is the first pivot, confirmed at bar i, and the
     later one is tracked.
   - Tracking a peak at bar e: a bar whose high is above high[e] moves the peak there (the first bar keeps a tie).
     Otherwise, when high[e] - low[i] >= thr[i], the peak is confirmed at bar i and the trough is tracked from bar i.
     Troughs mirrored.
   - So the bar that makes an extreme never confirms it, one bar's high and low never make two turns, and a pivot is
     confirmed on a later bar and known at that bar's close.
   - Output: (pivot bar, price, kind +1 peak / -1 trough, confirming bar), the shape of `dev/patterns.py::zigzag`.
3. **Per TF** (M1, M5, M15, M30, H1; H4 only for the Fibonacci's second definition): the bars of
   `precursors/indicators.bars` (clock bars; H4 on the server day). The threshold at TF bar j = max(S at that bar's
   close, 1.0 x ATR14 of that TF at bar j): a swing must be the trade's size and at least one typical bar of its TF,
   so H1 does not turn on every bar. (On M1 the ATR is far below 10, so the M1 threshold is S.) The TF ATR's warm-up as
   in rule 1.
4. **The structure per TF, at every TF bar j (known at its close); at a moment t, the last TF bar complete by t:**
   - the confirmed peaks and troughs (confirming bar <= j) and the running extreme of the leg after the last pivot;
   - the latest two highs: when the running leg is up and its high is above the last confirmed peak, (that peak, the
     running high); otherwise the last two confirmed peaks. The latest two lows mirrored;
   - highs HH / LH / EQ (newer above / below / equal to older), lows HL / LL / EQ; fewer than two = unknown;
   - the label: up = HH + HL, down = LH + LL, mixed otherwise, unknown when either is unknown;
   - the last break: the latest TF close above the last confirmed peak (+1) or below the last confirmed trough (-1),
     each pivot broken once, with its bar.
5. **The range box (per TF; reported on M1 and M5):**
   - Members are that TF's confirmed pivots, taken only after the last accepted break (below).
   - Born when the newest pivots, walked back from the newest, number at least 4 (they alternate, so two peaks and two
     troughs) while the band they span is at most 3 x S (S at the bar) and every member peak lies in the band's upper
     half and every member trough in its lower half. The walk stops at the first pivot that breaks a condition.
   - A newly confirmed pivot joins a live box when both conditions still hold; otherwise the box ends (outgrown) and
     a new box is sought as above.
   - Breaks, at each TF close: a close above the top (below the bottom) is a break; two consecutive closes beyond is
     an **accepted** break, and the box freezes (no new members). A break followed by a close back inside is a
     **sweep** (a fake break); the box stays live and the sweep's pivot may join it.
   - The last box (live or frozen) stays the reference until a new box is born; breaks of either edge keep being
     recorded on it.
6. **The trendlines (per TF):**
   - A support line is born at each trough's confirmation: through that trough T and the earlier trough, among the 5
     confirmed troughs before it, with the largest slope to T (the lower hull's edge: every trough between lies on or
     above the line). It is born only when that slope is above 0 (rising lows) and no close of the TF between the two
     anchors is below the line. Touches = 2 + the troughs between within 0.2 x S of the line.
   - Resistance mirrored (falling highs; the most negative slope).
   - The newest born line of each kind is the reference until the next one is born.
   - The line's value at a TF bar = the line at that bar's open time; anchors at the pivots' bar open times.
   - Breaks as for the box (a close beyond = break, two consecutive = accepted).
7. **The retest** (box edges and lines, after an accepted break; down-break shown, up mirrored):
   - price must first move away: a low at least RT = 0.25 x S below the broken level after the break;
   - the retest = the first later bar whose high comes to within RT of the level (or above it);
   - the retest **fails** at the first later close below level - RT; the retest's extreme is the highest high from the
     retest bar to that close; the retest **reclaims** the level at two consecutive closes above it.
8. **The Fibonacci of the last big swing (written before computing, as the measurer asked at 16:0x UTC):**
   - the last big swing = the last completed leg of the **H1** swings (rule 3): from the second-last to the last
     confirmed H1 pivot, as known at t;
   - the levels: end - f x (end - start), f = 0.236 / 0.382 / 0.5 / 0.618 (MetaTrader's tool drawn from the leg's
     start to its end: 0 % at the end, 100 % at the start). For a down leg the levels sit above its low, for an up leg
     below its high;
   - a second definition, reported beside it and never chosen by a result: the same on the **H4** swings.
9. **The shape check on 2026-10-19** (after the data end: shape only, no outcome is computed, nothing is fitted on it):
   - the M1 pivots against the measurer's 15 turns: found = a pivot of the same kind within 10 minutes of the listed
     time; the missed and the extra listed;
   - the per-TF label every 5 minutes from 13:00 to 22:00 Thai, and when each TF first read down after 14:33;
   - the M5 box (edges, span) against 4165.6-4190.3 (05:05-17:00) and its down-break against 17:20;
   - the retests (box bottom, support lines) against 18:15 (4177.06);
   - drawn: M1 with the pivots, the box, the lines, the Fibonacci levels, and a strip of the per-TF labels;
   - also drawn, shape only: the weekday nearest the middle of P1 and of P2 (rule: the middle date of the part, the
     nearest Monday-Friday, the earlier on a tie).
10. **The checks:**
    - hand-worked unit tests on small synthetic bars for every rule above;
    - planted bugs (a list run against the tests; every one must be CAUGHT);
    - an independent second swing detector (written differently: per leg, by cumulative minima / maxima) compared
      pivot for pivot on all of P1 + P2, every TF;
    - the look-ahead check: at decision times spread over P1 and P2, every M1 bar after the decision replaced by
      another path; every reading at the decision (S, the pivots known, the structure per TF, the box, the lines,
      their breaks / retests, the Fibonacci) must be unchanged; with power: a planted look-ahead must fail it.

### Added before computing (16:32 UTC, `date -u`; after the measurer's "Acceptance" section and its relays; still nothing run on any bars)

11. **The retest, repeated:** rule 7 records every retest of a broken level, not only the first. After a retest fails
    (a close below level - RT), price is away again, so the next approach to within RT is a new retest.
12. **The tests of a box edge** (the owner's "top tested about 7 times"): the peaks of the **inner swings** (the same
    detector with 0.3 x S, the first developer's inner share) inside the box's top quarter (price >= top - 0.25 x
    height), from the box's first member to its end; the bottom mirrored. Counted against the box as known at the
    moment of counting (at its end, for the report).
13. **The bias per TF** (a second reading beside the label of rule 4, never replacing it): the direction of the last
    structure break (rule 4: the latest close beyond the last confirmed peak / trough). A trader reads a close below
    the last higher low after a higher high as "the up structure is broken" before the next lower high exists.
14. **The interface for the first developer** (`dev2/swings.py`, read-only import; changed only through the
    measurer): the swing size per M1 bar, the M1 pivots in `patterns.zigzag`'s shape (pivot bar, price, kind,
    confirming bar), the pivots known at bar d, and the per-TF pivots / structure / box / lines / Fibonacci. Listed
    with the exact signatures in the V3-1 report.

### The acceptance tolerances (written before looking at 2026-10-19; the owner's reading from `../DEV2_PROMPT.md`)

- **The 15 turns:** found = an M1 pivot of the same kind within 10 minutes of the listed Thai time and within 1.00 USD
  of the listed price. Every miss and every extra pivot is listed with its reason.
- **The range 4165.6-4190.3 (05:05-17:00):** found = an M5 box (rule 5) whose bottom is within 1.00 of 4165.6 and top
  within 1.00 of 4190.3, live from no later than 10:00 Thai (four pivots must exist first) to the break. The top's
  tests (rule 12) are reported against "about 7"; found when 5..9.
- **LH / LL on M5, M15, M30, H1 from 14:33:** a lower high can only be known once the next high has failed, so
  "from 14:33" cannot be read causally at 14:33. Found per TF = the label (rule 4) reads down at the owner's trade-4
  entry window (by 18:55 Thai) and stays down to 22:00; or, failing that, the bias (rule 13) reads down by 18:55 and the
  label reads down by 20:47 (the base) and stays to 22:00. The first time each TF reads down after 14:33 is reported
  against 14:33.
- **The range break at 17:20:** found = the M5 box's first close below its bottom at the 17:20 M5 bar (17:20-17:25
  Thai), and the break accepted (rule 5) by 17:30.
- **The failed retest at 18:15 (4177.06) on the broken rising trendline:** found = a support line (rule 6, M1 or M5),
  broken before 18:15, with a retest (rule 7 / 11) whose bar is within 18:05-18:25 and whose extreme is within 1.00 of
  4177.06, and that retest failing (rule 7) by 18:55.
- **The 10 learning days:** 5 in P1 and 5 in P2, the weekday nearest each of the dates at 1/6, 2/6, 3/6, 4/6 and
  5/6 of the part (the earlier on a tie); each drawn on M1 with the pivots, the M5 box, the lines, the Fibonacci and
  the per-TF labels, shape only. These replace rule 9's two days.

### Added before computing (2026-10-20 05:08 UTC, `date -u`): the owner's TF roles (owner, about 12:05 Thai)

The owner: D1 tells which side has the edge; M15-H1 gives the trend; M1-M5 gives the entry, the exit and the stop.
On a real trend day gold mostly runs one way, with pullbacks inside a small-TF stop. The opens run in their first
30-60 minutes; NY can run up to 4 hours after its open, often choppy in its first 1-2 hours.

15. **The D1 reading:** the same reader (rules 2-4, 13) on D1 bars. The bars are the server day (Europe/Athens), as
    `indicators.bars(m, "1D")` builds them; a D1 bar is known at its last minute + 1. The threshold = max(S, 1.0 x
    ATR14 of D1). Exposed: the D1 label (up / down / mixed) and the D1 bias (the direction of the last D1 close beyond
    the last confirmed D1 swing).
    - Which of the two is "the side with the edge" is the owner's call. Both are reported; V3-2 will say which one it
      uses before it computes.
    - A day with no complete D1 bar before it reads unknown. On 2026-10-19 that is every minute, because the bars
      before 2026-10-18 are the exam's.
16. **The readout** `readings_at(R, t_ns)`: one row per moment, columns `D1_label`, `D1_bias`, `M15_label`,
    `M15_bias`, `M30_label`, `M30_bias`, `H1_label`, `H1_bias` (and the same for any other TF analysed). Each column
    is read from that TF's last bar complete by the moment, so the D1 bias and the M15 / M30 / H1 trend are separate
    columns, each as known then.

### Added before computing (2026-10-20 05:15 UTC, `date -u`): the side and the trend (the measurer's "V3 design", 12:14 Thai)

17. **The side and the trend columns** (in `readings_at`, from the labels of rule 4 and the biases of rule 13, each
    TF read at its last complete bar):
    - **`side`** (the design's rule): +1 (buy side) when the D1 label and the H4 label are both up and the H1 label
      is up or mixed. -1 (sell side) mirrored. 0 (no side) otherwise. NaN when the D1, H4 or H1 label is unknown,
      so that "no data" is kept apart from "no side".
    - **`side_bias`**, a second reading beside it, never chosen by a result: the same with the three biases in place of
      the labels. A bias has no mixed state, so: D1 and H4 biases agree, and the H1 bias is not the opposite.
      - Why: the label is slow. On 2026-10-19 every TF up to M30 read mixed from 14:52 to 18:56, while the bias read
        down from 16:00.
      - V3-2 says which of the two it uses before it computes.
    - **`trend`**: +1 when the M15, M30 and H1 labels all read up, -1 when all three read down, 0 otherwise. NaN when
      any of them is unknown.
    - **`trend_bias`** the same with the three biases.
    - Every column is also given per TF (`D1_label`, `D1_bias`, `H4_...`, `H1_...`, `M30_...`, `M15_...`), so V3-2
      can combine them differently. Any new combination is written before it is computed.

**Noted for V3-2** (the measurer's relays, kept here so V3-2 starts from them):
- The owner, 12:30 Thai: the costs are the tick bid / ask spread only. The slippage is a parameter that defaults to 0.
- The strategist's base rates and pass bars for entry 1 and entry 3, and the judging rules: the pooled mean with its
  95 % range, the neighbouring settings, the number of settings tried, and no lead from a cell under 40 trades.
- The owner's trade 4: first stop 4180 (3 USD over the retest high), target the Fibonacci 23.6 of the owner's swing.
- The V3 design: side -> trend -> entry TF by volatility -> the pullback turn at a level -> the stop past the turn ->
  the exits. The windows are Asia / London + 30-60 min and NY + 4 h, with NY reported per 30-minute bucket.

### V3-1 - the report (2026-10-20, 05:3x UTC = 12:3x Thai, `date -u`)

**A disclosure first.** At about 16:04 UTC on 2026-10-19, while checking the live file's columns before any filter
existed, I printed its first 3 rows: 2026-10-14 16:54-16:56 UTC, open 4081.31-4081.55. Those rows lie in the exam
period. Nothing was computed, fitted or inferred from them. Every later read goes through `load_live()`, which filters
`>= 2026-10-18 00:00 UTC` in the reader.

#### 1. What I did (files in `dev2/`)
- `swings.py`: the shared module, rules 1-17:
  - the swing size and the ZigZag;
  - per TF (M1 .. H4, D1): the pivots, the structure label and bias, the range box, the lines, the breaks / sweeps /
    retests, the Fibonacci, the edge tests;
  - the readout (`readings_at`) with the side and trend columns;
  - the loaders.
- `test_swings.py`: 26 hand-worked tests.
- `plant_bugs_v31.py` -> `out_plant_bugs_v31.txt`: 46 planted bugs. An error is never counted as a catch: it is
  retried, then reported as ERROR.
- `zigzag_ref.py`: a second ZigZag, written differently (leg by leg with prefix maxima / minima).
- `compare_ref.py` -> `out_compare_ref.txt`, `v31_learning.pkl`: the second ZigZag and a brute-force structure,
  checked against the module on P1 + P2, every TF; plus the scale facts.
- `lookahead_v31.py` -> `out_lookahead_v31.txt`: the no-look-ahead check, with power.
- `shape_v31.py` -> `out_shape_v31.txt`, `v31_shape.pkl`: the 2026-10-19 shape check and the side / trend readout.
- `draw_v31.py` -> `charts/index_v31.html` + 12 PNGs: 2026-10-19 (the whole day and the afternoon) and the 10
  learning days picked by the rule.
- `h1_on_m1.py` -> `out_h1_on_m1.txt`: a post-hoc sensitivity for the H1 miss. It is not a rule.
- `tf_agreement.py` -> `out_tf_agreement.txt`: how often each TF agrees with M1, and the shares of the D1, side and
  trend readings per part. A description only, no outcome.

#### 2. The tests (26; each hand-worked, the working in the test comments)

**The swing detector:**
- `test_zigzag_by_hand`: 13 bars at threshold 10. The pivots are (0, 99, trough, confirmed 2), (3, 115, peak, 5),
  (6, 101, trough, 7), (8, 125, peak, 10) and (11, 112, trough, 12). Bar 8 is wide (125 / 99): its own low is never a
  trough, and the next trough is tracked from bar 10.
- `test_zigzag_threshold_read_at_the_confirming_bar`: with thr[5] = 12, bar 5's 11-USD drop does not confirm; bar 6
  does.
- `test_zigzag_tie_keeps_the_first_bar_and_wide_first_bar`: equal highs keep the first bar. A wide first bar makes no
  pivot until another bar holds an extreme. One bar alone never makes a pivot.
- `test_main_path_pivots`: a 104-bar path through 100 / 120 / 102 / 121 / 101 / 115 / 99 / 118 / 90 / 98 / 88 / 110 /
  99. The pivot bars are 0, 9, 18, 28, 38, 45, 53, 63, 86, 97, confirmed at 4, 14, 23, 33, 43, 50, 58, 68, 91, 102.
- `test_known_at_and_running`: the pivots known by bar 37; after the 121 peak the running low is 103, at bar 37.
- `test_inner_swings`: a 4-USD dip is an inner pivot (thr 3), not a trade-size one.

**The structure and the bias:**
- `test_structure_by_hand`:
  - bar 33 up (HH 120 -> 121, HL 100 -> 102);
  - bar 38 mixed (the running low 101 < 102 is an LL);
  - bar 50 down (LH 121 -> 115, LL);
  - bar 63 mixed (the running high 118 > 115 is an HH);
  - unknown before two troughs.
- `test_bias_by_hand`: breaks at bars 28 (+), 38 (-), 53 (-), 62 (+) and 73 (-). The close AT 115 on bar 61 does not
  break.
- `test_cmp_equal`: equal reads 0.
- `test_readings_at`: bar 61 reads down / bias -1, bar 62 mixed / +1; nothing before the first complete bar.
- `test_side_and_trend_by_hand`: 9 rows of D1 / H4 / H1 / M30 / M15 cover:
  - buy and sell;
  - H1 mixed, which is not against;
  - H1 against;
  - D1 / H4 disagreeing;
  - D1 mixed;
  - unknown D1, which gives NaN;
  - unknown M30, which gives a NaN trend;
  - the bias columns differing.

**The edges, the box and the lines:**
- `test_edge_by_hand`, on one level:
  - break, then accepted, but price is not away yet, so no retest while it sits at the level;
  - away, then a retest at bar 6, failing at bar 7 at the retest's high of 98.9;
  - a new retest at bar 8, then a reclaim at bar 9;
  - mirrored for a top;
  - then break / sweep / break / accepted.
- `test_box_by_hand`:
  - born at bar 33 as [100, 121]; it grows to 8 members, and the sweep trough 99 extends the bottom;
  - accepted down at bar 74, then frozen;
  - the events: break 53, sweep 54, break 73, accepted 74, retest 81, fail 82 at 98, retest 91, reclaim 93;
  - no new box from the members before the accepted break.
- `test_box_outgrown_by_the_halves_rule`: the trough 111 lies above the middle 110.5, so box 0 is outgrown at bar 38.
  Box 1 is pivots 1..4, accepted up at bar 40.
- `test_box_tests_of_the_edges`: the top quarter holds 120 / 121 / 118 (115 is below 115.5). The bottom quarter holds
  100 / 102 / 101 / 99.
- `test_lines_by_hand`:
  - the support anchors (the largest slope), with 3 touches (102 lies within 1.53 of the line);
  - the resistance anchors (the steepest fall);
  - the line ids in their birth order;
  - support 0: break 37, accepted 38, retest 39, reclaim 41;
  - resistance 2: break 59, accepted 60;
  - the value at bar 50 = 100 + 50/38.
- `test_no_line_when_a_close_between_is_below_it`: a close under the line between the anchors means no line. An empty
  box / line table keeps its columns.

**The Fibonacci:**
- `test_fib_by_hand`: the leg 115 -> 99 gives 102.776 / 105.112 / 107 / 108.888; the leg 99 -> 118 gives 118 - 19 f;
  there are no levels before two pivots.

**The size and the bars:**
- `test_swing_size_by_hand`: true ranges of 30 / 10 / 34. S = 10 at 00:58, 18 at 00:59 (the H1 bar complete at the
  close counts), 12 at 01:59, 14.8 at 02:59.
- `test_swing_size_floor`: a true range of 10 gives 6, so S = 10.
- `test_swing_size_full_atr14`: the warm-up gives 13.2857; MetaTrader's ATR14 = 20 gives S = 12.
- `test_tf_threshold_takes_the_tf_atr_when_larger`: a true range of 20 gives a threshold of 20.
- `test_tf_bars_match_indicators_bars`: for M5 / M15 / M30 / H1 / H4 / D1, OHLC, last and avail equal
  `indicators.bars`.
- `test_at_reads_the_bar_complete_at_the_moment`: the M5 bar complete at 00:05 is read at 00:05, not 1 ns before.

**The mirror and the loaders:**
- `test_mirror`: negated prices give the same pivot bars, with flipped kinds, labels and events.
- `test_loaders_never_hold_the_exam`: live >= 2026-10-18; learning >= 2025-08-01 and < 2026-04-18.

#### The report, continued after the restart (2026-10-20 05:47-06:05 UTC = 12:47-13:05 Thai, `date -u`)

The first session stopped on the API limit at about 05:35 UTC, after sections 1-2 above. A new session finished the
report. **Nothing in `swings.py`, the tests or the rules was changed after the restart.**

`swings.py` was last saved at 12:26:40 Thai, after the planted-bug output (12:25:56 Thai). `shape_v31.py` was also
saved after its output. So I re-ran:
- the tests: **`26 passed in 2.17s`** (`.venv/Scripts/python -m pytest -q research/2026-10-18-moments/agents/dev2/test_swings.py`);
- the planted bugs: the same 46 / 46 CAUGHT (only the control's run time differs);
- the shape check: identical, except one fixed label (the first bar's date now reads 2026-10-19 Thai);
- the H1 sensitivity: identical.

The look-ahead run (started 12:26:55 Thai) and `compare_ref.py` (12:28 Thai) already ran on the final `swings.py`.

**Lint.** `ruff check` on `dev2/*.py` reports style findings only: line length 237, an assert in the tests 83, print
52, and smaller counts. I read the two that could hide a bug:
- `B023` in `shape_v31.py:174`: a lambda used in the same loop turn, so it is harmless;
- `RUF034` in `test_swings.py:168`: the mirrored level is 100 in both branches, as intended.

#### 3. The planted bugs (`plant_bugs_v31.py` -> `out_plant_bugs_v31.txt`)
**46 of 46 CAUGHT, 0 MISSED, 0 ERROR.** Each bug is planted in a temporary copy and run against the 26 tests. The
loaders are never mutated, so a mutant cannot read the exam. By area:
- the ZigZag: #01-06;
- the size, the warm-up and the threshold: #07-11;
- the structure and the bias: #12-17;
- the box: #18-21;
- the edges, retests and reclaims: #22-26;
- the lines: #27-31;
- the Fibonacci: #32-33;
- the edge tests and the inner swings: #34-35;
- the bars, the readout and `at`: #36-39, #46;
- the side and the trend: #40-45.

The full list, with the test that caught each bug, is in the output file.

#### 4. The look-ahead check (`lookahead_v31.py` -> `out_lookahead_v31.txt`, 514 s)
- **The decisions:** 86, spread over P1 (42) and P2 (44), from 2025-10-20 14:45 UTC to 2026-04-16 15:10 UTC. The
  rule was written in the script before running: every 1999th M1 bar of P1 and P2, from the 1000th.
- **The window:** each decision is analysed on the 20 calendar days before it and the 2 days after.
- **The replacement:** every M1 bar after the decision bar d is replaced, in turn:
  - by the mirror of the real path about d's close;
  - by a flat line at d's close.
- **What is compared at d's close:**
  - S;
  - per TF (M1 .. D1): the last complete bar and its OHLC, the pivots known, the inner pivots, every per-bar structure
    column up to that bar (the label, the pairs, the bias, the box state, the line ids and values), the events, the
    lines born, and the Fibonacci;
  - the readout of rules 16-17, including the side and the trend.
- **The result: 8428 of 8428 readings equal; PASSED.**
- **The power:** two planted look-aheads must fail, and both did:
  - S taken from the H1 bar still forming: 1445 / 1470 equal (differences in S 17, the M1 inner pivots 4, the M5 and
    M15 events 2 each);
  - the TF bar after the last complete one: 1085 / 1470 equal, with differences on every TF.
- **A limit of the check:** the TF bars follow `indicators.bars`, so a bar counts as complete at its last M1 + 1
  minute.
  - When a bar's last minutes have no M1 bar (no ticks), the bar is treated as complete before its clock end. The
    OHLC is right, but "nothing more will come" is known a few minutes early.
  - The check keeps the timestamps, so it cannot see this.
  - It is the shared convention (the auditor's building block "larger-TF bars"), so I did not change it. See question 6.

#### 5. The second computation (`zigzag_ref.py`, `compare_ref.py` -> `out_compare_ref.txt`, 74 s)
The data: 2025-08-01 .. 2026-04-17 20:54 UTC, 249,474 M1 bars (August .. mid-October is warm-up).

**The swings.** A second ZigZag, written leg by leg with prefix maxima / minima, against the module. Identical on every
TF:

| TF | Pivots |
|---|---|
| M1 | 4087 |
| M1 inner | 34054 |
| M5 | 3807 |
| M5 inner | 17128 |
| M15 | 3035 |
| M30 | 2205 |
| H1 | 1277 |
| H4 | 352 |
| D1 | 55 |

**The structure.** Re-derived by brute force at every TF bar (for M1, a sample of 42,632 bars) from the pivot list and
the running extreme computed directly: 0 differences on every TF.

**The scale facts behind rule 1.** Measured after the rule was written; the rule was not changed:
- P1: median H1 ATR 16.33 USD; S median 10.00, 90 % 14.48; the 10-USD floor rules 52.6 % of the minutes;
- P2: median H1 ATR 28.09 USD; S median 16.86, 10 % 10.59, 90 % 35.28; the floor rules 6.7 % of the minutes.

#### 6. The acceptance: 2026-10-19 against the owner's reading (`shape_v31.py` -> `out_shape_v31.txt`; charts `charts/v31_2026-10-19.png`, `charts/v31_2026-10-19_pm.png`)
Each item is judged by the tolerances written in this log **before** the day was looked at ("The acceptance
tolerances"). The data: 1019 M1 bars, 05:05-22:03 Thai. S was 10.00 all day, and the H1 ATR behind it was 11.95-13.49.

| Item (the owner's reading) | Tolerance (written before) | What the module gives | Verdict |
|---|---|---|---|
| The 15 turns of 10+ USD | same kind, within 10 min and 1.00 USD | all 15 at the exact minute and price; 1 extra pivot | **FOUND 15 / 15** |
| The range 4165.6-4190.3, 05:05-17:00 | an M5 box, bottom within 1.00 of 4165.6, top within 1.00 of 4190.3, live by 10:00 | M5 box 4165.61-4190.25, first member 05:05, born 09:25 | **FOUND** |
| The top tested about 7 times | 5..9 tests (rule 12) | 11 | **MISSED** (too many) |
| LH / LL on M5 / M15 / M30 from 14:33 | label down by 18:55 and to 22:00; or bias down by 18:55 and label down by 20:47 and to 22:00 | bias down 16:00, label down 19:00, stays to 22:00 | **FOUND** on M5, M15, M30 (by the second clause); also on M1 |
| LH / LL on H1 from 14:33 | as above | label mixed all evening; bias down from 19:00 | **MISSED** |
| The range break at 17:20 | the M5 box's first close below at the 17:20 bar, accepted by 17:30 | first close below at the 17:20 bar (4165.59); the 17:25 close back inside (a sweep); accepted at the 17:45 bar | **Half:** the break FOUND, the acceptance by 17:30 MISSED |
| The failed retest at 18:15 (4177.06) of the broken rising trendline | a support line (M1 or M5) broken before 18:15; a retest bar in 18:05-18:25 with its extreme within 1.00 of 4177.06; failing by 18:55 | M5 support line (08:25 4165.61 -> 13:30 4171.09, +1.08 USD / h): broken 15:35, accepted 15:40; retest at the 18:10 bar, extreme 4177.06; failed at the 18:25 bar (known 18:30) | **FOUND** (M5; M15 the same) |

**The details, and the reason for every miss:**

1. **The 15 turns.**
   - Each is found at its exact minute and price.
   - The time each became known (confirmed, M1): 07:25, 08:36, 09:25, 10:08, 12:29, 12:40, 13:15, 13:55, 14:52,
     18:02, **18:56** (the 18:16 lower high), 19:10, 19:58, 20:54, 21:13.
   - The extra pivot is 05:05 L 4166.07, the day's first bar. It is the range's first low; the owner's list starts at
     07:02.
   - **A fact for V3-2:**
     - The 18:16 lower high (4177.06) became known as a trade-size pivot only at 18:56, after price fell 10 USD.
     - The owner sold at about 4169 between 18:30 and 18:55, before that, so the owner's entry cannot wait for the
       trade-size pivot.
     - The M5 line's retest_fail (known at 18:30) comes at the start of the owner's entry window.
2. **The top's tests: 11 against "about 7".**
   - The 11 inner-swing peaks in the top quarter (M5): 06:30, 06:45, 07:00, 09:10, 11:55, 12:10, 12:55, 13:05,
     14:00, 14:20, 14:30.
   - The reason: rule 12's inner swings (0.3 x S = 3 USD) count separate wiggles of one visit. For example, 06:30 /
     06:45 / 07:00 and 14:00 / 14:20 / 14:30 are each one approach.
   - I do not know what the owner counts as one test, so I did not change the rule. See question 1.
   - The M1 box (rule 5 on M1) is narrower, 4165.61-4187.63. It ended at the 14:33 sweep (accepted up at 14:33,
     reclaimed at 14:36).
   - The M5 box took the sweep's peak 4190.25 as a member. That is why its top is 4190.25; until then it was 4187.63.
3. **H1 missed.** The H1 trade-size swings (threshold 12.2-13.2 USD, set by the H1 ATR term) cannot see the lower high.
   - The real H1 bars (Thai time):

     | H1 bar | High | Low |
     |---|---|---|
     | 17:00 | 4172.41 | 4162.21 |
     | **18:00** | **4177.06** | **4161.29** |
     | 19:00 | 4170.00 | 4158.69 |
     | 20:00 | 4167.18 | 4143.37 |

   - The 18:16 retest high and a new low (4161.29, at about 18:55) sit inside the **same H1 bar**. One bar's high and
     low never make two turns (the brief's rule), so on H1 the leg from 14:33 is one down leg with no lower high.
   - The 19:09 bounce (4158.69 -> 4170.00 = 11.31) is below the H1 threshold (12.37).
   - So the H1 highs stay 4187.63 -> 4190.25 (an HH) and the lows are LL: the label is mixed.
   - The H1 bias reads down from 19:00: the 18:00 bar closed at 4161.37, under the 08:00 trough 4165.61. That is 5
     minutes after the tolerance's 18:55.
   - **What the owner reads.** `OWNER_TRADING.md` trade 4 lists the H1 highs "4190, 4180, 4173, 4172, 4177 the
     retest, 4170, 4167, 4155, 4150". These are the **H1 candle highs one by one**, not trade-size swings. The real
     bars: 14:00 4190.25, 15:00 4179.53, 16:00 4172.84, 17:00 4172.41, 18:00 4177.06, 19:00 4170.00, 20:00 4167.18,
     21:00 4155.32, 22:00 4147.64. See question 2.
   - A post-hoc sensitivity, not a rule (`h1_on_m1.py`): the H1 threshold applied on the M1 path reads H1 down from
     18:58.
4. **The break at 17:20.**
   - The first M5 close under 4165.61 is the 17:20 bar (close 4165.59, 0.02 below), as the owner said.
   - The 17:25 bar closed back inside (4166.82): by rule 5, a sweep.
   - The break was accepted at the 17:45 bar (known at 17:50).
   - The 17:50 and 17:55 bars then closed above the bottom (4169.93 / 4169.61). Rule 7 calls that a **reclaim**, and a
     reclaimed edge records nothing more.
   - The owner reads the range as broken at 17:20, with the 18:15 retest failing. My rules read the box bottom as
     reclaimed at 17:55, before that retest. See question 3.
5. **The failed retest.**
   - Found on the M5 support line through 08:25 4165.61 and 13:30 4171.09. The line's value is 4176.12 at the 18:10
     bar and 4176.39 at the 18:25 bar.
   - The retest's extreme is 4177.06 (the 18:16 M1 high), 0.67-0.94 over the line.
   - The retest failed at the 18:25 bar's close (4172.11, more than 2.5 under the line), known at 18:30.
   - The M15 line (the same anchors) gives a retest at the 18:00 bar and a fail at the 18:15 bar, also known at 18:30.
   - On M1 the same line was reclaimed at 15:41 (two M1 closes back above), so M1 records nothing after that. The
     tolerance allows M1 or M5, so the item is FOUND, on M5.
   - The line is drawn on the day's own lows, which is not the owner's line: the owner's trendline is "drawn from 15
     Oct", and its anchors lie in the exam period, which I cannot read. See question 4.
6. **Beyond the list** (no tolerance was written for these, so they are not judged):
   - **The Fibonacci.**
     - Rule 8's H1 Fibonacci at 18:30-22:00 is on the leg 08:00 4165.61 -> 14:00 4190.25: 23.6 % 4184.43, 38.2 %
       4180.84, 50 % 4177.93, 61.8 % 4175.02. H4 gives the same leg after 20:00.
     - The owner's "base on the Fibo 50 % at 4142-4150" and target "23.6 below the 50 % (about 4141)" come from a larger
       swing that the owner has not given. Its anchors may lie before 2026-10-18. See question 5.
   - **The side and the trend on the day.**
     - The side is unknown (NaN) all day: in the allowed data no D1 bar is complete before 2026-10-19 22:04 Thai, and
       H4 is unknown until 20:00.
     - The trend by labels reads 0 (H1 is mixed). The trend by biases reads -1 (down) from 19:00. See question 7.

**The 10 learning days** (drawn in `charts/index_v31.html`; shape only, no outcome).
- The rule: in each part, the weekday nearest 1/6 .. 5/6 of the part, the earlier on a tie.
- The days picked:
  - P1: 2025-11-03, 11-17, 12-02, 12-17, 12-31;
  - P2: 2026-01-30, 02-16, 03-03, 03-18, 04-02.
- **A disclosure:** `draw_v31.py` also skips a day with fewer than 600 M1 bars in Thai 05:00-24:00. That skip is not in
  the rule as written in this log. It changed two picks, both days with **0** bars (markets closed):
  - 2026-01-01 -> 2025-12-31 (1075 bars), the earlier of the two days one day away;
  - 2026-04-03 (Good Friday) -> 2026-04-02 (1135 bars).
- The charts are for the owner's eye. Each shows the pivots, the M5 box and lines, the H1 Fibonacci, and per-TF strips
  of the label, the bias, the side and the trend.

#### 7. The results on the learning bars (descriptions only, no outcome; `tf_agreement.py` -> `out_tf_agreement.txt`, `out_compare_ref.txt`)

| Reading, share of M1 closes | P1 | P2 |
|---|---|---|
| D1 label up / down / mixed | 0.382 / 0.227 / 0.390 | 0.632 / 0.046 / 0.322 |
| D1 bias up / down | 0.805 / 0.195 | 0.830 / 0.170 |
| side (labels) +1 / -1 / 0 | 0.115 / 0.054 / 0.831 | 0.205 / 0.009 / 0.785 |
| side_bias +1 / -1 / 0 | 0.264 / 0.026 / 0.710 | 0.342 / 0.076 / 0.582 |
| trend (labels) +1 / -1 / 0 | 0.200 / 0.115 / 0.685 | 0.198 / 0.134 / 0.667 |
| trend_bias +1 / -1 / 0 | 0.401 / 0.253 / 0.345 | 0.379 / 0.222 / 0.399 |
| every TF M1..H1 label down / up | 0.089 / 0.174 | 0.086 / 0.169 |
| the TF's label equals M1's: M5 / M15 / M30 / H1 / H4 | 0.948 / 0.803 / 0.639 / 0.448 / 0.381 | 0.942 / 0.770 / 0.572 / 0.428 / 0.307 |
| the TF's own ATR rules its threshold: M5 / M15 / M30 / H1 | 0.006 / 0.117 / 0.579 / 0.951 | 0.018 / 0.201 / 0.748 / 0.996 |

**What this means for V3-2's trade count** (a description, not a verdict):
- The side by labels is non-zero in about 17 % (P1) / 21 % (P2) of the minutes. The sell side by labels is rare: 5.4 %
  / 0.9 %.
- If V3-2 requires the side by labels, most days have no trade.
- The side by biases is non-zero in 29 % (P1) / 42 % (P2) of the minutes.
- In both parts the D1 bias reads up about 80 % of the time: gold rose through the learning period.

#### 8. The definitions, for the first developer's independent re-implementation (exactly as coded in `swings.py`)

**D0. The bars and the time.**
- M1 bars are indexed by their UTC open time. An M1 bar is known at its open + 1 minute.
- The M5 / M15 / M30 / H1 bars group the M1 bars by the UTC open time, floored to the TF.
- The H4 / D1 bars group by the open time converted to the Europe/Athens wall clock (naive), floored to 4 h / 1 day.
- Each bar takes the first open, the highest high, the lowest low and the last close. Its open time t is the group key
  (M5 .. H1) or the first M1 inside it (H4 / D1).
- A bar is **complete at `avail` = its last M1's open + 1 minute**, as in `precursors/indicators.bars`.
- A reading at a moment t uses the last bar with `avail <= t`.

**D1. The ATR.**
- True range = max(high, previous close) - min(low, previous close).
- ATR14 = the simple mean of the last 14 true ranges, first defined at bar 14 (`foundation.atr`, MetaTrader's formula).
- Warm-up, where ATR14 is undefined: the mean of the true ranges so far. Bar 0's true range = its high - low.

**D2. The swing size S (USD) at a moment t.**
- S = `max(10, 0.6 x the H1 ATR14 of the last H1 bar complete by t)`. Before any complete H1 bar, S = 10.
- At an M1 bar, S is read at that bar's close (its open + 1 minute).

**D3. The threshold of a TF bar j.**
- `thr[j] = max(S at avail_j, 1.0 x the TF's ATR14 at bar j)`, bar j included.
- The inner swings (rule 12) use `0.3 x S at avail_j`, with no ATR term.

**D4. The pivot: the swing detector, a causal ZigZag** over the bars i = 0, 1, ..., with the arrays h, l and thr.
- **Before the first pivot:** hi = the first bar holding the highest high of bars 0..i; lo = the first bar holding the
  lowest low. When hi != lo and h[hi] - l[lo] >= thr[i]:
  - if lo < hi: a trough at lo (price l[lo]) is confirmed at i, and a peak is tracked from e = hi;
  - otherwise: a peak at hi is confirmed at i, and a trough is tracked from e = lo.
- **Tracking a peak at bar e:**
  - if h[i] > h[e]: e = i;
  - **else**, if h[e] - l[i] >= thr[i]: a peak at e (price h[e]) is confirmed at i, and a trough is tracked from e = i.
- **Tracking a trough:** mirrored (l[i] < l[e] moves it; h[i] - l[e] >= thr[i] confirms it).
- A pivot is known at its confirming bar's `avail`. Pivots alternate peak / trough.
- A **swing (leg)** = two consecutive pivots. Its **size** = their price difference, at least the threshold at the
  confirming bar.

**D5. The latest two highs / lows at a TF bar j** (after the bar's update).
- The highs: P = the peaks confirmed by bar j (confirming bar <= j). The pair is (P[-2], P[-1]).
- **Except:** when the detector is tracking a peak after bar j and that tracked high h[e] > P[-1], the pair is
  (P[-1], h[e]).
- The lows are mirrored: when it is tracking a trough and l[e] < T[-1], the pair is (T[-1], l[e]).

**D6. HH / LH / HL / LL.**
- The highs: newer > older = **HH**; newer < older = **LH**; equal = EQ; fewer than two = unknown.
- The lows: newer > older = **HL**; newer < older = **LL**; equal = EQ; fewer than two = unknown.

**D7. The label.**
- **up** = HH and HL;
- **down** = LH and LL;
- **mixed** = every other known pair, EQ included;
- **unknown** = the highs or the lows are unknown.

**D8. The break and the bias.** At a TF bar j, after the pivots confirmed at j are added:
- if the last confirmed peak is not yet broken and close[j] > its price: a break up at j, and the bias = +1;
- then, if the last confirmed trough is not yet broken and close[j] < its price: a break down at j, and the bias = -1;
- each pivot is broken at most once; a newly confirmed pivot of that kind starts unbroken;
- the **bias** is the direction of the latest break. It persists, and it is unknown before the first break.

**D9. The side at a moment** (each TF read at its last complete bar).
- **+1:** the D1 label = up, the H4 label = up, and the H1 label is not down;
- **-1:** mirrored;
- **0:** otherwise;
- **NaN:** any of the three labels is unknown.
- `side_bias` is the same, with the biases.

**D10. The trend.**
- **+1:** the M15, M30 and H1 labels are all up;
- **-1:** all three are down;
- **0:** otherwise;
- **NaN:** any of them is unknown.
- `trend_bias` is the same, with the biases.

**D11. A level's breaks.** One state machine per level L. The down case is shown; an up level is the same with the
prices negated. RT = 0.25 x S at the bar. At each TF close c (the bar's high h, low l):
- **Before acceptance**, with a counter n:
  - if c < L: n += 1. At n = 1, record **break**. At n = 2, record **accepted**; the state becomes "away" if l <=
    L - RT, else "wait"; nothing more happens on this bar.
  - if c >= L: when n = 1, record **sweep**; then n = 0.
- **After acceptance**, from the next bar, until the level is reclaimed:
  - "wait" becomes "away" when l <= L - RT;
  - in "away", on a later bar than the one that made it away, h >= L - RT records a **retest**, with the extreme = h;
  - in "retest": the extreme = max(extreme, h). When c < L - RT, record **retest_fail** with the extreme, and the state
    is "away" again from this bar;
  - on every bar after acceptance, a counter rc = rc + 1 when c > L, else 0. At rc = 2, record **reclaim**: the level
    is finished and records nothing more.
- For a box edge, L is the box's current top / bottom at the bar. For a line, L is the line's value at the bar's open
  time.

**D12. The range box** (per TF), with cap_j = 3 x S at avail_j.
- ok(set) holds when highest - lowest <= cap, every peak member >= the middle, and every trough member <= the middle.
- At bar j, for each pivot p confirmed at j, in order:
  - **if a box is live:** when ok(members + p), p joins (top / bottom = the members' max / min). Otherwise the box ends
    at j ("outgrown").
  - **if no box is live:** walk x = p, p-1, p-2, ... The walk stops when pivot x's bar <= the bar of the last accepted
    box break, or when ok(x..p) fails. If the run holds >= 4 pivots, a new box is born at j. It becomes the reference,
    with fresh top and bottom level machines (D11).
- Then the reference box's two edges step on bar j. An accepted break of a live reference box ends it at j ("broken",
  frozen), and bar j becomes the last accepted break.
- An outgrown box stays the reference, still stepping, until a new box is born. Its accepted breaks do not set the
  last accepted break.

**D13. The trendlines** (per TF). At bar j, for each pivot p confirmed at j, of kind k:
- The candidates are the same-kind pivots p-2, p-4, ..., p-10 (those that exist).
- The slope to each candidate x = (price_p - price_x) / max(minutes between their bars' open times, 1).
- A support line (troughs) takes the largest slope; a resistance line (peaks) takes the smallest. On a tie, the nearer
  candidate wins.
- The line is **born** only when:
  - support: the slope > 0, and no close on the bars strictly between the two anchor bars is below the line's value
    at that bar's open time;
  - resistance: the slope < 0, and no close is above the line.
- Touches = 2 + the same-kind pivots strictly between the anchors whose price lies within 0.2 x S (at avail_j) of the
  line.
- The newest line of each kind replaces the previous one. Its D11 machine steps from the bar after its birth, with
  L = the line's value at each bar's open time.

**D14. The Fibonacci** at a TF bar j.
- start = the second-last confirmed pivot; end = the last.
- The levels = end - f x (end - start), for f = 0.236 / 0.382 / 0.5 / 0.618.
- H1 is the main reading, H4 the second.

**D15. The tests of a box edge.**
- Counted: the inner pivots (D3, D4) of the edge's kind, confirmed by the counting bar, whose bar lies between the
  box's first member and the counting bar.
- A peak counts when it is in the top quarter (price >= top - 0.25 x height). The bottom is mirrored.

#### 9. The interface (`dev2/swings.py`: read-only for the other roles, changed only through the measurer)
- `load_learning()` / `load_live()`: the M1 bars (UTC index). The filters are applied in the reader.
- `swing_size(m) -> np.ndarray`: S per M1 bar.
- `zigzag(h, lo, thr, state=False) -> (pivot_bar, price, kind, confirm_bar)`: the shape of `dev/patterns.py::zigzag`.
- `m1_pivots(m, share=1.0)`.
- `known_at(piv, d)` and `running(piv, h, lo, d)`.
- `analyze(m, tf, inner=False, s_fn=None) -> TF`, with these fields:
  - `.bars`, `.thr`, `.s`, `.piv`;
  - `.struct`, per bar: highs, lows, label, bias, bias_bar, the pairs, box, box_live, box_top, box_bot, sup, sup_val,
    res, res_val;
  - `.boxes`, `.lines`;
  - `.events`: bar, tag, kind, side, level, price, obj, avail;
  - `.inner`, and `.at(t_ns)`.
- `analyze_all(m)`; `readings_at(R, t_ns)` (rules 16-17); `fib_at(r, j)`; `edge_tests(r, box, upto, side)`.

#### 10. Questions to the measurer ("Owner" marks the ones for the owner)
1. **(Owner) What is one "test" of the range top?** Rule 12 counts 11 on 2026-10-19, against the owner's "about 7".
   - Is an approach that wiggles (06:30 / 06:45 / 07:00) one test?
   - If so, what separates two tests: price leaving the top by some USD, or a gap in time?
   - I will write the owner's answer as a rule before I count again.
2. **(Owner) How do you read "LH / LL" on H1?**
   - The trade-4 note lists the H1 candle highs one by one (4190, 4180, 4173, 4172, 4177, 4170, 4167, 4155, 4150).
   - The trade-size H1 swings cannot see a lower high there, because the 18:00 H1 bar holds both the retest high and a
     new low.
   - Is H1's trend read from the candle highs and lows, bar by bar? Or from the H1-sized swings read on a smaller TF
     (the post-hoc `h1_on_m1.py` reads down from 18:58)? Or from the bias (a close under the last H1 low, from 19:00)?
3. **(Owner) After the 17:20 break, the M5 bars closed back above 4165.6 at 17:50-18:15 (up to 4177).**
   - My rule calls two closes back inside a reclaim: the break failed. The owner reads the range as broken, and the
     18:15 retest as failing.
   - Should a reclaim need more: closes back inside by some distance, or a close above the last lower high?
   - Should a reclaimed level be able to break again? Now a reclaimed level records nothing more. For example, the M1
     line reclaimed at 15:41 records nothing at 17:20-18:30.
   - This touches V3-2's break-and-retest, so I ask before V3-2 rather than change it now.
4. **The owner's trendline is "drawn from 15 Oct",** with its anchors in the exam period.
   - The module's line is drawn from the day's own lows (08:25 / 13:30) and passes the retest within 1 USD.
   - Is that acceptable as the owner's line, or does the measurer want to read the owner's anchors?
5. **(Owner) Which swing is the Fibonacci on?**
   - It is the swing behind "the base on the 50 % at 4142-4150" and "the 23.6 below the 50 %".
   - Rule 8's H1 last leg (4165.61 -> 4190.25) puts the 50 % at 4177.93, so it is a different swing.
   - Its start and end prices and times would let me write a rule (the last H4 / D1 leg, or the swing from the day's
     high).
6. **When is a TF bar complete?**
   - The shared convention (`avail` = the last M1 + 1 minute) knows that a bar is complete a few minutes early when its
     last minutes have no ticks.
   - Should the swings use the clock end (the bar's open + the TF) for H1 / H4 / D1?
   - It is a one-line change in `tf_bars`, but it also concerns `indicators.bars`, the auditor's.
7. **The side on 2026-10-19 is unknown,** because D1 / H4 need bars from before 2026-10-18 (the exam).
   - For V3-2's acceptance on that day, may the measurer supply the D1 / H4 labels and biases at the day's open (the
     readings only, no outcomes)?
   - Or is V3-2 accepted on that day without the side?
8. **Which side and trend should V3-2 use?** V3-2 must say before it computes whether it uses the labels or the biases.
   - The labels give a side in about 17-21 % of the minutes, the biases in 29-42 %.
   - On 2026-10-19 the bias turned down 3 hours before the label (16:00 against 19:00, on M5-M30).
   - I propose to report both, using the bias for the trend and the label for the side. I will wait for the measurer's
     answer.

**Checkpoint: V3-1 is reported. V3-2 is not started.**


## V3-2 - the four entries in the owner's windows

### First: the measurer's two test gaps and the live path (2026-10-20 10:05-10:12 UTC = 17:05-17:12 Thai, `date -u`)
- `test_known_at_the_confirming_bar_exactly`: on the MAIN path the peak@28 is confirmed at bar 33; `known_at(piv, 32)`
  must give [0, 9, 18] and `known_at(piv, 33)` [0, 9, 18, 28]; also bars 3 / 4 around the first pivot.
- `test_running_leaves_out_the_pivot_bar`: hand-given pivots, a peak bar (high 120, low 90) whose own low is below
  every later low (96, 93, 97); `running(.., 5)` must be (4, 93, -1); the trough case mirrored ((4, 104, +1)).
- Both bugs added to `plant_bugs_v31.py` as #47 / #48: **48 of 48 CAUGHT** (`out_plant_bugs_v31.txt`); 28 tests pass.
- `swings.LIVE` = the repo store `data/history/FBS-Demo/XAUUSD/M1.parquet`, read with `open_time >= 2026-10-18`
  (it holds 2026-10-18 22:05 .. 2026-10-20 05:59 UTC, 1,845 bars).

### Written before computing (V3-2): the rules (2026-10-20 10:15 UTC = 17:15 Thai, `date -u`)

Nothing below has been run on any bars. The facts used are the brief, the measurer's answers (Q4 / Q6 / Q7 / Q8),
CHECKLIST rows 23 / 25 / 43, PROPOSALS proposal 2 and V3-1's own report. The open owner questions Q1 / Q2 / Q3 / Q5
keep V3-1's current rules (marked OPEN in the report).

**R0. Data, parts, costs.**
- The bars: `swings.load_learning()` (2025-08-01 .. 2026-04-17; August .. mid-October 2025 only warms the swings up),
  `swings.analyze` on M1, M5, M15, M30, H1, H4, D1 (M15 also with the inner swings, 0.3 x S, for the trail).
- The trades are counted in P1 (2025-10-18 .. 2026-01-15) and P2 (2026-01-16 .. 2026-04-17) by the decision time.
- The ticks: `data/ticks/XAUUSD/<UTC day>.parquet`, the day joined to the next; my reader refuses any day from
  2026-04-18 on. The exam is never loaded.
- The decision time = the moment the deciding TF bar is complete (`avail`, rule D0). The fill = the first tick at /
  after it (none within 5 minutes: no trade). A buy fills at the ask + slip, a sell at the bid - slip; **slip = 0** by
  default (a parameter). Market exits at the bid (buy) / ask (sell). The stop fills at the first tick at / beyond it
  (the gap included); the target is a limit filled at its price; one tick reaching both: the stop. A gap of more than
  30 minutes in the ticks: out at the last tick before it ("break"). A fill already past the stop: no trade.
- R = pnl / the initial risk (|the fill - the initial stop|). 0.01 lot: 1 USD of price = 1 USD.
- **One position at a time per entry type** (a signal while that type's trade is open is dropped). The four types are
  also reported together, one position at a time across all of them, in the order of the decision time.
- S = `swing_size` at the decision (rule D2), H = the H1 ATR14 at the decision (`h1_atr`).

**R1. The windows (by the decision time).**
- **Asia** 07:00-09:00 Thai (00:00-02:00 UTC). **London** 13:00-14:00 Thai (06:00-07:00 UTC).
- **NY 08:30**: 08:30-09:30 New York time (America/New_York, so the US summer time is followed).
- **NY open**: 09:30-13:30 New York time, reported per 30-minute bucket (09:30, 10:00, ... 13:00).
- **other**: the rest. Not part of any rule; reported apart as information (entry 3 inside / outside separately, as
  asked).

**R2. The entry TF.** Four settings, all reported:
- **vol** (the rule): the H1 ATR14 at the decision against P1's terciles. The terciles are computed once from the H1
  ATR at every P1 M1 bar inside the four windows (P1 only). Low tercile -> M1, middle -> M5, high -> M15 (the owner:
  "low volatility M1, higher M15"). An event on TF X is taken only when the decision's chosen TF is X.
- **M1**, **M5**, **M15**: that TF for every decision.
- The tercile cut points are printed before any trade is simulated.

**R3. The levels and their events** are V3-1's (rules D11-D13) on the entry TF: the reference box's top / bottom
(`box_top` / `box_bot`) and the newest support / resistance line (`sup` / `res`), with the events break, sweep,
accepted, retest, retest_fail and reclaim. The levels everyone sees (for entry 3 and for the base rate) are the
strategist's (`strategist/retest.py`, re-implemented in my code, not imported): the previous server day's high / low
(PDH / PDL, from the day's start) and the Asian range high / low (00:00-06:00 UTC, from 06:00 UTC), on M5, with H.
My re-implementation is checked against `strategist/retest_trades.parquet` and `reclaim_trades.parquet` by the entry
times (the check is reported; their costs are M1 / mlib, mine ticks, so only the times and sides are compared).

**R4. Entry 1 - break and retest.**
- The event: a `retest_fail` on the entry TF's box edge or line (D11). The trade goes with the break: a bottom /
  support broken down -> a **sell**; a top / resistance broken up -> a buy.
- Decision = the event bar's `avail`. Stop = the retest's extreme (the event's price) + 0.25 x S past it (trade 4:
  4177.06 + 2.5 = 4179.56 against the owner's 4180).
- The exits (R7), variants (a) and (b).
- **The splits** (reported, not filters), from the strategist's proposal 3:
  - aligned: every TF from the entry TF up to H1 (of M1, M5, M15, M30, H1) reads the break's way, by the labels
    (LH / LL for a sell) - and separately by the biases;
  - the level: a line or a box edge;
  - the first `retest_fail` of that level or a later one.
- **The base rate** beside it: the strategist's #25 on the levels everyone sees (-0.221 / -0.390, M1 + mlib costs;
  -0.218 / -0.380 on the ticks, spread only, PROPOSALS row 39), and my own re-simulation of the same entries in my
  simulator (stop = the retest's extreme + 0.25 H, 2 R, 120 min, as retest.py).
- The pass line (the strategist's): the aligned subset >= +0.15 in both parts and >= 0.3 R above the base rate.

**R5. Entry 2 - the aligned consolidation.** On the entry TF X:
- aligned: every TF from X up to H1 reads d (d = -1 sell, +1 buy) - by the **biases** (the measurer's Q8 answer:
  the bias for the trend); the label version is a second setting;
- the base: the last 6 bars of X (the decision bar included) span at most 2.0 x X's ATR14 (at the bar before the six),
  every one of the six lies after the last confirmed trade-size peak of X (for a sell; trough for a buy), and the six
  bars' top is below that peak (bottom above that trough);
- the trigger: the first bar at which the base holds (it did not hold at the bar before); then no new trigger until the
  base has failed for at least one bar;
- the entry: at the trigger's `avail`, a sell inside the base (a buy mirrored);
- the stop: past the structure that must break, the last confirmed peak of X + 0.25 x S (sell; trough - 0.25 x S buy);
- the exits (R7); split: the base within 0.25 x S of an H1 Fibonacci level (rule D14) or not.

**R6. Entry 3 - the fake break at a range edge** (#23 merged with #43, PROPOSALS proposal 2). The union of:
- (i) the close back inside: on the entry TF's box edges, a `sweep` (one close beyond, then a close back inside) or a
  `reclaim` (two closes back inside after an accepted break); on the levels everyone sees (M5), #23's reclaim (the
  first M5 close beyond by 0.1 H, then within 24 M5 bars an M5 close back inside by 0.1 H);
- (ii) the failed retest turn taken back into the range: on the entry TF's box edges, a `retest_fail` traded the
  other way; on the levels everyone sees, #25's turn (retest.py) traded the other way.
- The trade goes back into the range: a broken bottom -> a buy; a broken top -> a sell.
- Two stop settings: **mirror** = the same distance as the same-side rule's stop, measured from the fill (for (i):
  the distance from the decision bar's close to the break's extreme + 0.25 H; for (ii): the retest's extreme
  + 0.25 S (box) / 0.25 H (everyone) from the fill, mirrored); **ext** = the break's extreme (the furthest price
  beyond the level from the break bar to the decision bar) - 0.25 H for a buy (+ for a sell).
- Target 1 R; at most 120 minutes. The same moment from two sources is one trade (the first source in the order
  above).
- Reported inside the windows and outside them, separately; per source (box / everyone) and per kind ((i) / (ii)).
- The pass line (the strategist's): >= +0.15 in both parts with >= 30 trades each, in the windows.

**R7. The exits for entries 1, 2 and 4.**
- The target candidates Z (prices on the trade's side of the fill, known at the decision): the H1 and H4 Fibonacci
  levels (rule D14); the prices of the last 6 confirmed trade-size pivots of M15 and of H1; the entry TF's reference
  box top / bottom; PDH / PDL and the Asian high / low once known.
- **(b) the next level:** the target = the nearest Z at least 1 R from the fill; none -> 2 R. The stop stays.
- **(a) trail + the next zone:** the target = the nearest Z at least 2 R from the fill (none -> no target); the stop
  trails: every inner swing (0.3 x S, rule D3) pivot of the entry TF against the trade (a peak for a sell) whose bar is
  at / after the decision bar, confirmed after the decision, moves the stop to its price + 0.25 x S (sell; - for a
  buy), from the confirming bar's `avail`, only when that is tighter.
- The time limit: 120 minutes; 240 minutes for an entry in the NY-open window (the owner: NY runs up to 4 h).

**R8. Entry 4 - the fake first leg at an open.** The opens T0: Asia 00:00 UTC, London 06:00 UTC, NY 08:30 and NY 09:30
New York time; weekdays only.
- d = the trend at T0 by the biases (`trend_bias`, M15 / M30 / H1 all the same way); 0 / unknown -> no trade. The
  labels' `trend` is a second setting.
- p0 = the open of the first M1 bar at / after T0. The fake leg: from T0, price goes at least A = 0.3 x S against d
  past p0 (a high >= p0 + A for a sell).
- The entry: after the fake leg reached A, the first close of the entry TF back past p0 the way of d (a close < p0 for a
  sell), with the decision by T0 + 60 minutes. One per open.
- The stop: the fake leg's extreme (the highest high from T0 to the decision, for a sell) + 0.25 x S. Exits (R7).

**R9. The report** (DEV_PROMPT section 6 shape): per entry type x window x entry-TF setting x exit: trades, trades a
weekday, win (pnl > 0), R and its 95 % range (bootstrap 4,000, seed 7) with the normal range as a second computation,
USD, DD (the deepest fall of the running USD), the worst trade, the longest losing streak, the exits; week by week
(Thai weeks); the NY open per 30-minute bucket; per side source (the side by the labels and by the biases: with the
trade / none / against / unknown); the pooled P1 + P2 mean with its 95 % range; the neighbouring settings; the number of
settings tried. No "lead" from a cell under 40 trades.

**R10. The checks.**
- Hand-worked tests for: the windows (with the US summer time), the entry-TF choice, each entry's event -> trade
  translation (stop, side), the target picking, the trail schedule, the tick simulator (stop / target / gap / trail /
  same-tick / no fill), the metrics.
- Planted bugs against those tests (CAUGHT / MISSED).
- The look-ahead check: the bars after a cut replaced by another path; every entry decided by the cut, its side, stop,
  target and the trail steps known by the cut must be unchanged; a planted look-ahead must fail it.
- A second computation of every metric; 20 trades per main variant re-derived from the raw ticks by a plain loop.
- The losers by reason: **wrong way** (the best excursion before the exit < 0.5 R), **ran later** (stopped / timed
  out, then 1 R our way from the fill within 60 minutes after the exit), **no run** (the rest); one drawn per reason.

**R11. The acceptance on 2026-10-19** (the live bars; shape only: the entries are listed, no outcome is computed;
the side is not available that day, Q7). Tolerances, written now:
- **Trade 4:** an entry-1 sell with the decision in 18:25-19:00 Thai, the M1 close at the decision in 4167.0-4172.5,
  the stop in 4177.06-4182.0. FOUND on any entry-TF setting (each listed).
- **The base entry:** an entry-2 sell with the decision in 21:15-23:00 Thai, the M1 close at the decision in
  4142.0-4150.0, the stop in 4155.3-4165.0.
- **The triple-top sell:** a sell of any entry with the decision in 14:33-15:30 Thai, the close in 4176.0-4186.5.
- **The NY-open fake leg then the sell:** an entry-4 sell with the decision in 20:30-20:50 Thai, the close >= 4150.0.
- Every other entry that day is listed as an extra, with its reason.

### Added before computing (2026-10-20 10:31 UTC = 17:31 Thai, `date -u`): the owner's answers relayed by the measurer (17:2x-17:3x Thai)

Nothing of V3-2 had produced a trade yet: the first build (specs only, no ticks) was stopped as too slow and is rebuilt
under these rules.

18. **The structure is read on the M1 path (the owner: "to read H1, zoom into the smaller TF").** For every TF above
    M1 (M5, M15, M30, H1, H4, D1) the **primary** structure reading is that TF's swing size applied on the M1 path:
    - the threshold at an M1 bar d = max(S at d's close, 1.0 x the TF's ATR14 at its last bar complete by d's close)
      (rule D3 with the TF's ATR read causally; `h1_on_m1.py`'s construction);
    - the ZigZag (D4) on the M1 highs / lows with that threshold; the latest two highs / lows (D5), HH / LH / HL / LL
      (D6), the label (D7) and the bias (D8, on the M1 closes) at every M1 close;
    - a reading at a moment = the last M1 bar complete by it.
    - `swings.analyze_path(m, tf)` returns it as a `TF` (bars = the M1 bars); `analyze_all(.., path=True)` adds it as
      `R["<TF>@M1"]`; `readings_at(.., mode="path")` reads it. M1's own reading is the same in both modes.
    - The candle-bar reading (V3-1's D4-D8 on the TF's own bars) stays as the **secondary** variant, reported beside
      it ("bar"). The box, the lines and their events (D11-D13) stay on the TF's own bars.
    - **V3-2 uses the primary (path) reading** for the side, the trend, entry 1's aligned split, entry 2's alignment
      and entry 4's trend; each is also reported with the bar reading (a setting, counted).
19. **One test of a box edge (Q1, decided by the measurer for the owner):** a visit to the box's top quarter (a bar
    whose high >= top - 0.25 x height) counts as a test when price has left the top quarter by at least S since the
    previous counted test (a low <= top - 0.25 x height - S, S in force at that bar), the first visit counting
    from the box's first member. Read on the M1 bars, the box's top / height as given. The bottom is mirrored. It
    replaces V3-1's inner-swing count (rule 12 / D15); the measurer's count on 2026-10-19 (5 tests: 06:29, 09:10,
    11:53, 12:39, 13:58) is the acceptance line, not tuned to the owner's "about 7".
20. **Outside the windows (the owner: "flexible within reason"):** an outside entry may count when it is clean. V3-2
    keeps reporting inside / outside separately for every entry; "clean" is not defined yet, so no outside entry
    enters a rule's result in this checkpoint.
21. Q3 (the reclaim after 17:20) stays open: rule D11 is kept.

### Added before computing (2026-10-20 10:35 UTC = 17:35 Thai, `date -u`; specs being built, no trade simulated yet)
22. **The main variant per entry** (for the drawings, the loser reasons and the combined day), chosen by the rule's
    text, not by a result: the entry TF "vol"; exit (a) (the owner's management: the trail past the entry TF's swings,
    the next zone); the biases for the alignment / the trend (Q8); the path reading (rule 18). Entry 3: "vol", the
    "ext" stop (the proposal's own stop). The other settings are reported beside it and counted.
23. **One position at a time** is applied separately to the trades inside the windows (the rule) and to the trades
    outside them (information), so the outside report does not take trades away from the rule.
24. **The everyone-sees events of entry 3** sit on M5 and are taken in every entry-TF setting (the "vol" choice is
    applied to the box events only).

### V3-2 - the report (2026-10-20, written 12:3x-12:5x UTC = 19:3x-19:5x Thai, `date -u`)

**In one line:** the four entries are built, tested and run on the ticks (spread only, slip 0). **No main variant reaches
the goal: E1 -0.035 / -0.290, E2 -0.028 / +0.000, E3 -0.068 / +0.010, E4 +0.041 / -0.052 R (P1 / P2, inside the
windows); all four together -0.015 / -0.112.** The entries find the owner's four moments of 2026-10-19 by shape, but
trade 4 only on M5 / M15, not on the TF that the "vol" rule picks that day (M1). The strongest cells, seen after the run
and judged as below: **E4 (the fake first leg) with the label trend and exit (b): +0.292 / +0.418 (41 / 34 trades)**, and
E2 with the label alignment and exit (b): +0.147 / +0.243 (107 / 39).

#### 1. What I did (files in `dev2/`)
- The measurer's two test gaps closed; `swings.LIVE` -> the repo store (section "First" above). 48 / 48 V3-1 bugs caught.
- Rules R0-R11 and 18-24 written before computing (above). Rule 18 (each TF's structure on the M1 path, the primary
  reading) and rule 19 (one test of a box edge) added to `swings.py` (`analyze_path`, `path_threshold`,
  `analyze_all(.., path=True)`, `readings_at(.., mode=)`, `edge_visits`); the structure loop moved into `_structure()`
  unchanged (V3-1's 28 tests and its bug list still pass / are caught, see 3).
- `v32.py`: the windows, the entry-TF choice, the levels everyone sees (the strategist's #23 / #25 re-implemented), the
  four entries, the target candidates and the trail steps. `tsim32.py`: the tick simulator. `v32_build.py` -> the specs
  (`v32_specs.pkl`, `out_v32_build.txt`). `v32_run.py` -> the simulation and the report (`out_v32.txt`,
  `v32_trades.parquet`, `v32_base25.parquet`). `shape_v32.py` -> the acceptance (`out_shape_v32.txt`).
  Checks: `test_v32.py`, `plant_bugs_v32.py`, `lookahead_v32.py`, `recheck_v32.py`, the parity check
  (`out_parity_v32.txt`), `draw_v32.py` (`charts/v32/`, 28 charts, `index.txt`).
- R2's terciles from P1 (the H1 ATR at every P1 M1 bar in the windows): **q1 14.551, q2 18.449 USD**.
- 80 settings tried (E1 8, E2 32, E3 8, E4 32) + the base rate.

#### 2. The tests (`test_v32.py`, 27 pass; every expected number worked by hand in the test comments)
| Test | What it checks, and how | Pass line |
|---|---|---|
| windows_follow_the_us_summer_time | 13 moments on 2025-10-29 (EDT) and 11-05 (EST) -> Asia / London / NY0830 / NYopen / other; the NY bucket labels | each label exact |
| entry_tf_by_the_terciles | H 10 / 14.5 / 16 / 18.4 / 30 / NaN with q 14.5 / 18.4 | M1, M5, M5, M15, M15, '' |
| parts | the six boundary minutes of P1 / P2 / the exam | '', P1, P1, P2, P2, '' |
| entry1_from_the_box_bottom_retest_fail | V3-1's MAIN path: the retest_fail at bar 82 (extreme 98) | a sell at T0+83 min, stop 100.5, first, not a line, not aligned (M1 mixed) |
| entry2_base_trigger | a 100->120->100 walk then a 1-USD flat; the base first holds at bar 23 (span 4 <= 2 x ATR 2) | one sell trigger at bar 23, peak 120, top 104, bottom 100, stop 122.5 |
| entry2_needs_alignment | the same bars, alignment False | no trigger |
| aligned_reads_every_tf_up_to_h1_on_the_path | stub readings: H1@M1 -1, H1 (bars) +1 | path aligned, bar not; M1 label path; buy side not |
| entry3_box_events | MAIN: sweep@54, retest_fail@82, reclaim@93 on the box bottom, H 8 | buys with ext stops 97 / 88 / 86; mirror distances 4 / 16; mirror_of 100.5 |
| entry3_dedupe_keeps_the_first_source | four rows, two at the same moment and side | the priority order kept |
| entry4_fake_leg | Asia open 2025-11-05: p0 100, A 3 (bar 2 high 103), M1 close 99 at bar 6, M5 close 96 | sell at 00:07 (M1) / 00:10 (M5), stop 106.5; the label trend 0 -> none |
| pick_target | candidates 101 / 103 / 105 / NaN, risk 1 | 103 (2 R), 101 (1 R), 102 (default), NaN, 97 (sell) |
| trail_steps | MAIN inner peaks after bar 64: 98@81 (conf 83), 110@97 (conf 99) | steps at T0+84 -> 100.5 and T0+100 -> 112.5; one when t_out = T0+90 |
| candidates_hold_the_box_edges | at T0+61 | 121 and 99 in the list |
| sim_stop_and_target | a buy at the ask 100.2, stop 99, 2 R | stop at the bid 98.9 (-1.3, R -1.083); target +2.4 (R 2); mfe / mae |
| sim_sell_uses_the_ask_and_the_time_exit | a sell at the bid 100, t_out 5 min | out at the 5-min tick's ask 99.7, +0.3 |
| sim_gap_no_fill_and_fill_past_the_stop | a 40-min gap; the first tick 6 min late; a sell with its stop below | "break" at the last tick before the gap; None; None |
| sim_trail_only_tightens_and_starts_at_its_time | a sell, stop 103, steps 100.5 (tighter) and 104 (looser) at 2 min | stopped at the 3-min ask 100.6; dated at 1 min -> 101.0 |
| sim_mirror_stop_dist_and_slip | mirror_of 98 for a sell; stop_dist 1.5; slip 0.1 | stop 102.2, risk 2.2, target 97.8; 98.7; fill 100.3 |
| sim_one_tick_reaching_the_stop_and_the_target_is_a_stop | a trail step above the target, one tick reaches both | "stop" at the market 102.7 |
| sim_ran_later | stopped at 1 min, the bid 1 R up at 30 min (70 min outside the hour) | after_best 1.2 |
| ticks_refuse_the_exam | 2026-04-18 | RuntimeError; the cache returns None without reading |
| ticks_cache_goes_back_in_time | four later days loaded, then 2025-10-20 | the earlier day loads (the KeyError of the first run) |
| metrics_by_hand / drawdown_from_the_start | equity paths, a zero pnl, fills at the previous exit | DD 3 / 2, streak 3, one-at-a-time keeps 0 / 10 / 25, summ == summ2 |
| loser_reason | mfe / after_best against the risk | wrong way / ran later / no run |
| path_reading_h1_on_the_m1_path | MAIN, H1 path: threshold 10 to bar 58, 22 from bar 59 | pivots ..53, 63, 86 confirmed ..58, 74, 97; bar 80 mixed, bias -1 from 73; readings_at path vs bar |
| edge_visits_by_hand | top 10, bottom 0, S 3, nine bars | tests at bars 1, 6, 8; the bottom mirrored the same |

`test_swings.py`: 28 pass after the refactor.

#### 3. The planted bugs
- `plant_bugs_v32.py` -> `out_plant_bugs_v32.txt`: **44 of 44 CAUGHT** (windows / DST, the TF choice, each entry's side /
  stop / trigger, the alignment and the reading mode, the trail, the simulator's fill / stop / both-on-one-tick / trail /
  gap / lag / mirror / time / cache, the metrics, rules 18 / 19). The first run missed the cache bug (#34); I
  strengthened its test (four later days first), then it was caught.
- `plant_bugs_v31.py` re-run on the refactored `swings.py`: **48 of 48 CAUGHT** (`out_plant_bugs_v31.txt`).
- **A disclosure:** a mistaken shell line started an early copy of `plant_bugs_v32.py` that still held a mutant
  widening the exam guard of `tsim32.day_ticks` (`d > EXAM_START`). In that mutant's run, `test_ticks_refuse_the_exam`
  called `day_ticks(2026-04-18)` and so **read one exam-day tick file (2026-04-18) into memory** inside the test; the
  test failed on it (no error raised), nothing was printed, stored or computed from it. That mutant was removed from the
  list before the clean run, and no mutant may widen an exam guard again.

#### 4. The look-ahead check (`lookahead_v32.py` -> `out_lookahead_v32.txt`)
- Six cuts spread over P1 / P2 (2025-11-06 01:10, 12-10 15:20, 2026-01-08 06:40, 02-12 14:50, 03-11 00:45, 04-08
  16:05 UTC). After each cut the M1 bars are reflected about the last close (two days kept); the swings, the path
  readings, the everyone-sees levels and every entry are rebuilt from scratch on both copies.
- Compared for every entry decided by the cut, in every spec file (all TFs, all settings): the decision, the bar, the
  side, every stop, S, H, the window, the alignment columns (path and bar), the side / trend sources, the target
  candidates and the trail steps dated by the cut.
- **136,573 of 136,573 unchanged: PASSED** (1,224 s).
- **The power:** a planted look-ahead (every structure reading taken 15 minutes after the decision) changes 67 of
  16,746 entries on the first two cuts: **FAILED, i.e. caught.**

#### 5. The second computations
- Every metric cell: n / R / win / DD / streak by a plain loop (`summ2`): **759 of 759 cells equal**.
- 20 trades per setting re-derived from the raw tick files by an independent one-tick-at-a-time loop
  (`recheck_v32.py`): **1,600 of 1,600 agree** (80 settings x 20; the fill, the exit kind, the exit time, the pnl).
- My #25 re-run in my simulator, all hours, each alone: **-0.218 / -0.380 (41 / 46)**, exactly the strategist's tick
  numbers (PROPOSALS row 39).
- My re-implementation of the levels everyone sees against the strategist's trade lists (`out_parity_v32.txt`): #25
  88 / 88 entries equal (time and side); #23 130 of 131 equal, one entry a minute apart (2025-11-28 08:15 / 08:16 UTC:
  their entry is the next M1 bar's open, which is one minute later where an M1 bar is missing).

#### 6. The results (inside the owner's windows, one position at a time, ticks, spread only; `out_v32.txt`)
**The main variants** (rule 22: entry TF "vol", exit (a), the biases, the path reading; E3 "vol" + the ext stop):

| Entry | Part | Trades (a weekday) | Win | R [95 % boot] | USD | DD | Worst | Streak | Weeks + |
|---|---|---|---|---|---|---|---|---|---|
| E1 break and retest | P1 | 186 (2.91) | 0.31 | -0.035 [-0.24, +0.18] | -120.8 | 157.5 | -26.2 | 12 | 5 / 13 |
| | P2 | 125 (1.89) | 0.29 | -0.290 [-0.48, -0.08] | -542.2 | 617.4 | -58.9 | 19 | 2 / 14 |
| E2 aligned consolidation | P1 | 272 (4.25) | 0.37 | -0.028 [-0.11, +0.06] | -299.1 | 360.7 | -39.6 | 10 | 5 / 13 |
| | P2 | 87 (1.32) | 0.36 | +0.000 [-0.15, +0.16] | -99.2 | 240.6 | -88.5 | 7 | 4 / 14 |
| E3 fake break at an edge | P1 | 192 (3.00) | 0.47 | -0.068 [-0.19, +0.05] | -93.9 | 209.3 | -40.4 | 5 | 5 / 13 |
| | P2 | 157 (2.38) | 0.50 | +0.010 [-0.13, +0.14] | +66.8 | 254.8 | -182.5 | 7 | 7 / 14 |
| E4 fake first leg | P1 | 79 (1.23) | 0.41 | +0.041 [-0.18, +0.28] | +45.7 | 96.0 | -16.6 | 6 | 7 / 13 |
| | P2 | 63 (0.95) | 0.30 | -0.052 [-0.36, +0.31] | -330.5 | 409.1 | -74.4 | 6 | 4 / 13 |
| The four together | P1 | 403 (6.30) | 0.40 | -0.015 [-0.11, +0.08] | -192.5 | 389.5 | -39.6 | 12 | |
| | P2 | 262 (3.97) | 0.36 | -0.112 [-0.23, +0.01] | -928.1 | 964.8 | -182.5 | 13 | |

Pooled P1 + P2: E1 -0.137 [-0.28, +0.01] (311), E2 -0.021 [-0.10, +0.05] (359), E3 -0.033 [-0.12, +0.06] (349), E4
-0.000 [-0.20, +0.21] (142), the four together -0.053 [-0.13, +0.02] (665). The normal ranges (the second computation
of the range) agree with the bootstrap within 0.04 in these cells. The -182.5 USD trade is E3 on 2026-02-02 07:30 Thai (the crash week, H1 ATR
124 USD, a 180-USD stop; -1.01 R). The week-by-week tables (Thai weeks) are in `out_v32.txt` for each main variant and
the combined day.

**E1 against the base rate (#25):** the base rate in my simulator, inside the windows: -0.240 / -0.237 (19 / 25); all
hours -0.218 / -0.380. E1's splits (inside the windows):
- aligned by the labels (path): -0.031 / -0.018 (51 / 36); by the biases: -0.142 / -0.256 (101 / 74); by the bar labels
  +0.003 / -0.246 (26 / 27).
- a line: +0.038 / -0.315 (107 / 65); a box edge: -0.133 / -0.263 (79 / 60).
- the first fail of the level: -0.002 / -0.219 (136 / 94); a later one: -0.124 / -0.506 (50 / 31).
- **The pass line (the aligned subset >= +0.15 in both parts and 0.3 R above the base rate): FAIL** in every split.

**E3 inside / outside the windows (as asked):** inside -0.068 / +0.010 (192 / 157); outside +0.047 / -0.010 (189 / 195).
Per source inside: box (i) -0.178 / -0.089 (71 / 56), box (ii) -0.033 / -0.036 (85 / 57), everyone (i) = #23 at 1 R
+0.172 / +0.164 (20 / 25), everyone (ii) = #43 inside -0.063 / +0.241 (16 / 19). **Pass line (>= +0.15 with >= 30 a
part): FAIL**; my box edges dilute the levels everyone sees.

**Per window / bucket / TF / side source** (all in `out_v32.txt`). The notable rows (main variants, P1 / P2):
- E1 London -0.432 / -0.541 (21 / 12); E1 Asia +0.231 / -0.463.
- E2 NY bucket 09:30 +0.274 / +0.428 (24 / 5); E2 NY 11:00 -0.251 / -0.330.
- E4 NYopen +0.278 / -0.173 (33 / 18); E4 buys +0.144 / +0.086 (54 / 40), sells -0.182 / -0.293 (25 / 23).
- The side source does not separate in a way that holds in both parts (e.g. E1 "side with" by the path labels +0.113 /
  -0.046 (24 / 39)); the side by the labels is "none" in most trades (E1: 141 / 75 of 186 / 125).

**The losers by reason** (main variants): E1 wrong way 121, no run 65, ran later 31 (of 217); E2 199 / 22 / 7 (of 228);
E3 129 / 37 / 14 (of 180); E4 55 / 27 / 9 (of 91). The entry, not the exit, is still where most losers come from.
One loser per reason and a rule-picked sample (the first winner and loser of P1 and P2) per entry are drawn in
`charts/v32/` (28 charts, listed in `index.txt`).

**The settings positive in both parts** (80 tried; inside the windows; seen after the run; none is a lead under 40
trades a part):

| Cell | P1 R (n) | P2 R (n) | Pooled [95 %] | Neighbours |
|---|---|---|---|---|
| E4 vol, exit (b), the label trend, path | +0.292 (41) | +0.418 (34) | +0.349 [+0.08, +0.63] (75) | label bar +0.240 / +0.203 (36 / 25); M15 +0.256 / +0.402 (34 / 32); M5 +0.219 / +0.144 (40 / 40); exit (a) +0.006 / +0.191; the bias trend +0.179 / -0.006 |
| E2 vol, exit (b), the label alignment, path | +0.147 (107) | +0.243 (39) | +0.172 [+0.02, +0.32] (146) | label bar +0.106 / +0.029; M15 +0.193 / +0.176 (35 / 31); M5 +0.009 / +0.141; M1 +0.112 / +0.003; the bias alignment -0.017 / +0.013 |
| E1 M5, exit (b) | +0.112 (176) | +0.109 (223) | +0.110 [-0.02, +0.24] (399) | M5 exit (a) +0.169 / +0.030; vol / M1 / M15 negative in P2 |

- The E4 cell: P2 has 34 trades (under 40), so by the judging rule it is not a lead yet. Without its best 3 trades:
  +0.157 / +0.223. Weeks positive 10 / 13 and 9 / 12. Per open (P1 / P2): Asia +0.400 / +0.187 (9 / 9), London -0.455 /
  +0.826 (4 / 9), NY 08:30 +0.537 / +0.598 (12 / 5), NY open +0.235 / +0.192 (16 / 11). Exits: target 17 / 15, stop
  16 / 13, time 6 / 6. 0.6 trades a weekday.
- The E2 cell: without its best 3: +0.093 / +0.080. Weeks positive 9 / 13 and 10 / 14. 55 of 107 P1 exits are the time
  limit.
- **What the grid shows** (a description of the 80 cells, not a rule change): the labels (HH + HL / LH + LL on every TF)
  beat the biases for the alignment / trend, and exit (b) (the next level, the stop kept) beats exit (a) (the trail at
  0.25 S past the 0.3 S swings, the next zone >= 2 R). My main variant (rule 22: the biases, exit (a)) took the weaker
  of both.

#### 7. The acceptance on 2026-10-19 (`out_shape_v32.txt`; shape only, no outcome computed)
| The owner's trade | Tolerance (R11) | What the rules take | Verdict |
|---|---|---|---|
| Trade 4: the sell after the failed retest | E1 sell 18:25-19:00, close 4167.0-4172.5, stop 4177.06-4182 | E1 on **M5 and M15**: the sell decided 18:30 at 4172.11, stop 4179.56 (the M5 support line's retest_fail, extreme 4177.06; aligned by the path biases). Window "other" (outside the windows). | **FOUND on M5 / M15; MISSED by the "vol" rule**: that day's H1 ATR (12.2, warm-up) is under q1, so "vol" picks M1, where the same line was reclaimed at 15:41 (V3-1) and records nothing. It is also the 5th retest_fail of that line on M5 ("first" False). |
| The base on the Fibo 50 % | E2 sell 21:15-23:00, close 4142-4150, stop 4155.3-4165 | E2 M1 (bias, path) sells at 21:17 (4144.50), 21:27, 21:30, 22:01, 22:13 ... stop 4157.82 (the 21:00 lower high 4155.32 + 2.5); NY-open window; "vol" = M1 | **FOUND**; but E2 on M1 fires 72 times that day (all hours), far more than the owner's one entry |
| The triple-top sell after 14:33 | any sell 14:33-15:30, close 4176.0-4186.5 | E3 M1: the box top reclaimed at 14:37 (4185.44, ext stop 4193.44); E3 M5: 14:40 (4183.76) | **FOUND** (outside the windows) |
| The NY-open fake leg, then the sell | E4 sell 20:30-20:50, close >= 4150 | E4 sell at 20:35 (4160.34), p0 4161.68, the fake high 4167.18, stop 4169.68, on M1 and M5, by the biases and the labels (path); NY-open window | **FOUND** |

- **The extras that day** (all listed in `out_shape_v32.txt`): E1 M5 also sold 12:30, 16:00, 16:10, 16:25, 18:10 (repeat
  fails of the same support line) and bought 20:15 / 20:30 (a resistance line's retest_fail during the fall); E3 took
  buys at 17:22 / 17:29 (the range bottom swept and reclaimed - V3-1's Q3 reading), 19:10 / 19:35 (the Asian low
  reclaimed), 20:42; E4 bought the London open at 13:59. Reasons: E1 / E3 take every fail / reclaim of every level; no
  limit per window or per level was in the rules.
- The readings that day: the path H1 reads down from 18:58 (as `h1_on_m1.py`); the path trend (biases) down from 16:00,
  the labels' trend down from 18:58. **A caveat:** the path D1 / H4 readings on the live day are not meaningful - before
  a TF's first complete bar its path threshold is S alone (rule 18), and no D1 bar is complete before 22:04. The side
  stays as Q7 decided (accepted without it).
- Rule 19 on the day: **5 tests (06:29, 09:10, 11:53, 12:39, 13:58)**, the measurer's count exactly.

#### 8. What this says and what I would change next (for the measurer and the owner; nothing changed yet)
- The four entries as written lose or sit near 0 in the windows. The base rate of the retest (#25) stays below them,
  but no E1 split reaches the pass line.
- Two transformations to test next, written before running (proposed, not run): (1) E4 and E2 with the label trend and
  exit (b), frozen as they stand, checked on the older years where M1 exists (CHECKLIST rows 45-49: every lead so far
  pays only since 2025-10); (2) one entry per level per window (the first fail / reclaim only), which removes the
  repeats seen on 2026-10-19.
- The "vol" TF rule missed trade 4 (M1 on a calm day). The owner's words ("low volatility M1") and the trade disagree
  here: the owner read the trade on M5.

#### 9. Questions
1. **(Owner) Exit (b) and the labels did better than my declared main (exit (a), the biases).** May the next round take
   E4 / E2 with the labels and exit (b) as the main, judged on the older years (M1, the heavier costs) before any
   freeze?
2. **(Owner) The entry TF on a calm day:** trade 4 lived on M5 when "vol" said M1. Is the owner's "low volatility M1"
   about the H1 ATR, or about the M1 bars' size (a different measure)? Or should the TF be the one where the level's
   structure lives (the line was an M5 line)?
3. **E2 fires too often** (72 times on 2026-10-19 on M1, 4.25 a weekday in P1's windows one at a time). Should a base
   need a level (the Fibo / an H1 level) - the owner's base sat on the Fibo 50 % - or be one per lower high?
4. **Q3 / Q5 of V3-1 stay OPEN** with the current rules (Q1 is now rule 19, Q2 rule 18, both decided).
5. The strategist's `idx_of_day` keeps a day only when it has >= 50 M5 bars, counted over the whole day: a day's
   eligibility uses bars after the decision. I have not measured how often it changes a day (the look-ahead copies keep
   the same bar count, so the check cannot see it), and in live use it cannot be known; should it be "the previous day had >= 50"?

**Checkpoint: V3-2 is reported. V3-3 is not started.**
