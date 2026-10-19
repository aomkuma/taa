# Setup OWN V2 - the developer's log

The trading-system developer's log (brief: `../DEV_PROMPT.md`). Times in UTC. Learning parts only: P1 2025-10-18 ..
2026-01-16, P2 2026-01-16 .. 2026-04-18; nothing from 2026-04-18 on is loaded, computed, plotted or printed (the code
refuses it: `learning_ticks` raises `ExamPeriodError`, the event lists end before it, the charts refuse a window that
reaches it). Every count below counts each release minute once (the coordinator's 03:47 UTC note: count events
once, not once per minute).

## Checkpoint A1 - the two-way sweep detector (2026-10-19; its times were not read from the clock)

### Written before computing (pre-registration)

- **What it computes:** at every weekday's 08:30 and 10:00 New York minute of P1 / P2 (the fixed set), and at every
  release minute of the calendar (`gold.releases()` + `agents/news/extra_releases.csv`: also 14:00 / 14:30 FOMC,
  the minutes, the press conference), on the tick mid: the first minute's leg, then which comes first within 15
  minutes of the release - a new extreme beyond the first minute's (continued) or 10 USD past p0 the other way
  (faked: the sweep) - then how far price comes back after the sweep (the third leg).
- **How it is judged:** no trades and no R at A1. The detector is right when (1) it catches the owner's own example,
  2026-01-09 13:30 UTC, as the fake drop then the sweep up then down, and (2) the owner, shown the drawn cases,
  confirms that it finds what the owner means. The code first had to reproduce the researcher's published table
  (`news_sweep.py`) with the researcher's rules, so any later difference is a deliberate change, not a bug.

### 1. What I did (files in `research/2026-10-18-moments/agents/dev/`)

| File | What it is |
|---|---|
| `sweep_detector.py` | The detector: `first_minute` (the readings at the decision, ticks before release + 60 s only), `race` (the label, reads the future by design), `detect`, the event lists (`fixed_events`, `calendar_events`), `scan`, `learning_ticks` (refuses the exam), `m1_from_ticks`, `thai`, `summary`; `main` writes the tables. |
| `test_sweep_detector.py` | 28 hand-worked tests (.venv). |
| `charts_a1.py` | Picks the cases by a written rule and draws them (M1 of the tick mid, Thai time, plus a tick zoom of the first minutes); one HTML page with data-URI PNGs (venv-research). |
| `test_charts_a1.py` | 4 hand-worked tests of the chart helpers (venv-research). |
| `plant_bugs_a1.py` | 57 planted bugs (45 in the detector, 12 in the chart helpers), each run against the tests in a temporary copy; the unedited sources run first as the control. |
| `lookahead_a1.py` | The no-look-ahead check on the real ticks of every learning event. |
| `a1_detections.parquet` | Every event x 4 variants (2 side rules x 2 continuation thresholds), both sets. |
| `out_sweep_detector.txt`, `out_plant_bugs_a1.txt`, `out_lookahead_a1.txt`, `out_charts_a1.txt` | The runs' outputs. |
| `charts/a1_sweeps.html` (+ `charts/a1_sweeps/01..10.png`) | The 10 drawn cases. |

### Learned -> changed -> why -> result

1. **Reproduced the researcher first.** With the researcher's rules (side = the first 3-USD move, continued = any new
   extreme) my code gives exactly the published table (08:30 P1: 62 days, continued 0.37, faked 0.03, neither 0.06,
   quiet 0.53; P2 0.49 / 0.17 / 0.02 / 0.32; 10:00 P1 0.58 / 0.08 / 0.10 / 0.24; P2 0.69 / 0.14 / 0.05 / 0.12; the
   same 27 faked minutes and sweep medians). So the base is the same.
2. **Learned: the first minute often moves 3+ USD both ways, and then "the first 3-USD move" names the wrong leg.**
   20 of the 177 first minutes with a leg (fixed set) moved 3+ both ways, and 11 of the researcher's 27 faked minutes
   are such minutes. In those the side was set by a few-second blip and the "sweep" was the first minute's own larger
   move carrying on. Example 2026-03-03 15:00 UTC (chart #9): 3.7 down in the first seconds, then up 26.8 inside the
   first minute (closing +12.5), a new high +31.1 at minute 3.8 - the researcher's rule reads "first leg down,
   faked, sweep up 31". 2025-11-20 13:30 (NFP): up 4.3, then down 18.7 inside the first minute - read as "first leg
   up 4.3, sweep down 12.3".
   **Changed:** the first leg's side = the first minute's larger move (what its M1 candle shows; a tie goes to the
   side that reached 3 USD first). The researcher's rule stays as the variant `side_rule="first"`.
3. **Learned: "continued" by a cent is not a continuation.** With any new extreme counted, 8 fixed minutes were
   "continued" by a new extreme of 0.04 - 2.84 USD right after the first minute (minute 1.0 - 2.5), followed by a
   16 - 40 USD sweep the other way - the owner's shape (chart #10: +0.13, then 40.2 down). It also makes the
   comparison "continuation 3-5 x more frequent" uneven: a 1-cent new extreme against a 10-USD move the other way.
   **Changed:** continued = a new extreme at least one LEG (3 USD) beyond the first minute's (`CONT_EXTRA = 3`). The
   researcher's 0 stays as a variant. Of the 141 fixed minutes continued by the old rule, 72 % (P1) / 81 % (P2) went
   3+ USD further and 28 % / 34 % 10+ USD further.
4. **Added for the owner's words "sweeps the lows / the highs" and "then it comes down":** the 30-minute pre-release
   range (did the first leg go beyond it, did the sweep go beyond the other side), and `came_down` = back at least
   half the sweep within 15 minutes of the sweep's extreme. The researcher's "third leg" (back through p0) misses the
   owner's own example (back 12.9 of 18.6, not through p0); both are kept.
5. **A test caught a code gap:** on a tie between the two sides an invalid `side_rule` passed silently; the
   validation now comes first. Two of my own hand-worked expectations were wrong (15.0 is exactly 3 beyond 12, not
   more; there are 130 weekdays, not 129) and were corrected after recomputing by hand.

### 2. The tests

`.venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_sweep_detector.py -q` -> **28 passed in 1.99s**

Ticks are given in seconds around a release at T0 = 10,000 s; p0 = 100 unless stated.

| Test | What it checks | How (the hand-worked numbers) |
|---|---|---|
| `test_the_owner_case_fake_drop_sweep_up_then_down` | the whole owner sequence and every time stamp | 97 at +10 s (first leg, t_leg), 96.5 at +20 s (leg1 3.5, t_ext), 111 at +200 s (10 past p0: faked, decided there), 112 at +300 s (sweep 12 at minute 5.0), 95 at +600 s (back 17, through p0, came down); give_back 0, not two-sided |
| `test_faked_without_the_third_leg_but_came_down` | came down without crossing p0 | leg up 3.5, sweep to 88 (12), back to 95 = 7 >= 6, below p0 |
| `test_came_down_needs_half_the_sweep` [2 cases] | the half-sweep edge | back 5.9 of 12 -> False; exactly 6.0 -> True |
| `test_the_third_leg_counts_a_return_exactly_to_p0` | the p0 edge | back to exactly 100 -> third, back 12 |
| `test_faked_needs_exactly_run_past_p0` | the 10-USD edge | 110.0 -> faked; 109.99 -> neither |
| `test_continued_needs_a_new_extreme_one_leg_beyond_the_first_minute` | +3 rule, decision time, cont | leg1 5; 92.1 (2.9 beyond) no; 91.9 (3.1) continued at +200 s; 90 at +250 s: cont 5.0 at +250 s; the old rule decides at +100 s |
| `test_a_new_extreme_of_exactly_one_leg_is_not_yet_continued` | the +3 edge | 92.0 = exactly 8.0 = 5 + 3, then 110 -> faked |
| `test_a_small_new_extreme_then_the_sweep_is_faked_not_continued` | the deliberate change vs the researcher | 94.9 (0.1 beyond), then 115 -> faked, sweep 15 at minute 5.0; the old rule: continued |
| `test_neither_and_the_race_window_ends_at_15_minutes` | the window's end | 108 only; 130 exactly at +15:00 and 135 at +15:01 are outside -> neither |
| `test_the_race_starts_after_the_first_minute` | the first minute is not raced | up 11 then down 12 inside the minute (side down, leg1 12); 84.5 later = 3.5 beyond -> continued, not faked by the 11 up |
| `test_the_sweep_is_the_extreme_inside_the_window_only` | sweep extreme and window | faked at +200 s; 113 at +800 s is the sweep (13); 140 at +905 s ignored |
| `test_back_is_measured_for_15_minutes_after_the_sweeps_extreme` | back's own window | sweep 112 at +300 s; 104 at +1000 s counts (back 8), 90 at +1201 s does not |
| `test_quiet_and_the_first_minutes_edges` | the 60-s and 3-USD edges | 102.9 inside, 97 exactly at +60 s -> quiet (up1 2.9); exactly 3.0 inside -> a leg |
| `test_p0_is_the_tick_before_the_release_not_at_it` | p0 | a tick AT the release is the first leg, p0 = 100; no tick before -> None |
| `test_race_without_a_first_minute_reading` | race's empty inputs | None -> {}; quiet -> {"outcome": "quiet"} |
| `test_the_side_is_the_first_minutes_larger_move` | the side rule (both variants) | +4 at 5 s, 97 at 20 s, 88 at 30 s, 98 at 59 s: side down, leg1 12, t_leg 20 s, t_ext 30 s, give_back 10, two-sided; 84.9 later -> continued; the researcher's side: up 4, "faked", sweep 15.1 |
| `test_a_tie_takes_the_side_that_reached_leg_first` | tie + bad rule name | +4 then -4: up; side_rule="close" raises |
| `test_the_pre_release_range_and_the_sweeps_through_it` | the 30-min range and both sweeps | 150 at -30:01 ignored; high 104 / low 97; first leg to 96 sweeps the low, sweep to 110 the high; equal to the low is not beyond; 111 under a high of 112 is not; the mirror case |
| `test_the_first_minutes_readings_do_not_see_after_the_decision` | no look-ahead (unit) | every tick from +60 s replaced by 500 random ones: readings equal (both rules); moving the +59 s tick changes them |
| `test_the_owner_example_2026_01_09_on_the_real_ticks` | the owner's example on the real ticks | p0 4473.34, low 4459.23 (leg 14.11), high 4491.96 (sweep 18.62 at minute 10.4), 4479.08 (back 12.88), pre-release low 4462.14 / high 4474.80: faked, came down, not through p0, both ranges swept; also faked under the researcher's rules |
| `test_scan_uses_the_mid_and_keeps_the_event_columns` | scan | a day where the bid drops 3 but the spread widens 2: the mid moves 2 -> quiet, p0 100.2; columns kept; a day without ticks skipped |
| `test_the_exam_is_refused` | the exam guard | 2026-04-18 (UTC and naive) raises; 2026-04-17 loads; both event lists refuse an end past the exam start |
| `test_the_fixed_minutes_follow_new_york_time` | NY time, weekends | Fri 31 Oct 2025 EDT 12:30 / 14:00 UTC, Mon 3 Nov EST 13:30 / 15:00, the weekend empty; 13 / 16 Mar 2026 EDT; 260 minutes 2025-10-20 12:30 .. 2026-04-17 14:00 |
| `test_the_calendar_minutes` | the merged calendar | 2026-01-09 13:30 NFP; 2025-11-20 13:30 CLM+NFP; 2026-02-20 GDP+PCE; FOMC 2026-01-28 19:00 (14:00 NY), PC 19:30; 2026-03-18 18:00 (EDT); 'check' flag; 62 minutes 2025-10-24 .. 2026-04-16 while the files hold later ones |
| `test_m1_candles_from_ticks` | M1 OHLC | minute 0: 10 / 12 / 9 / 9 (3 ticks); minute 1 (tick at exactly 60 s): 11 / 11.5 / 11 / 11.5; a tick at 180 s outside |
| `test_thai_time` | UTC -> Thai | 13:30 -> 20:30; 18:05 -> 01:05 |
| `test_summary_by_hand` | the table | 4 P1 rows: 2 faked / 1 continued / 1 quiet, medians 15 / 3 / 17.5, shares 0.5 / 0.5; P2 neither, NaN |

`data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_charts_a1.py -q` -> **4 passed,
14 warnings in 2.29s** (the warnings are matplotlib's own pyparsing deprecations)

| Test | What it checks | How |
|---|---|---|
| `test_pick_by_the_written_rule` | the case-selection rule | 12 hand-made minutes x 4 variants; expected OWNER, B (P1 08:30 median 15), C (P2 08:30 tie at 27.5 -> the earlier), E (median 14), G (continued tie at 4 -> the earlier; a no-release minute excluded), J, K (not came down, B / C already drawn), I_ (side rules disagree, largest move 12), F (strict rule says continued) |
| `test_variant_labels_put_the_detector_first` | the caption line | F's four labels, the detector first |
| `test_headline_and_the_minutes_axis` | titles, the x axis | faked / through p0 / did not come down / continued strings; 90 s = 1.5 minutes |
| `test_draw_the_owner_example_and_refuse_the_exam` | a real picture + the guard | 2026-01-09 drawn, title "#1 2026-01-09 20:30 Thai (08:30 NY, NFP) - P1 - FAKED: first leg down 14.1, sweep up 18.6...", PNG > 10 KB; a case at 2026-04-17 23:30 raises (its window reaches the exam) |

### 3. The planted bugs

`.venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_a1.py` (`out_plant_bugs_a1.txt`): controls
PASSED (28 passed / 4 passed), then **57 of 57 CAUGHT, 0 MISSED**:

- `sweep_detector` (45): p0 at the release; the tick at +60 s in the first minute; a strict 3-USD leg; the researcher's
  side always; a tie going down; leg1 = the first 3-USD tick; t_leg either way; give_back's sign; two_sided by the max;
  swept_pre on touching; a 60-minute pre-range; the first post-release tick in the pre-range; c1 = the tick after the
  minute; the race from the release; the first research definition (10 past p0 its way, raced from the release);
  cont_extra ignored; continued at exactly +3; a strict 10-USD fake; the window from the decision; the sweep where it
  first passed 10; back from p0; back's window from the release; a strict third leg; a strict half; swept_other on the
  wrong side; t_back one tick early; faked / continued decided at their extremes; cont from p0; detect ignoring the
  side rule; the exam guard letting 2026-04-18 in; the fixed minutes in UTC; Saturdays in; the fixed list and the
  calendar reaching the exam; the extra releases read as UTC; the calendar keeping later rows; one name a minute; scan
  on the bid; scan dropping the event columns; M1 labelled by the close; M1 close = the high; Tokyo time; summary
  swapping faked / continued; summary counting the faked days only.
- `charts_a1` (12): the median of the cases left; a tie to the later; continued at no-release minutes; 'largest' not
  skipping drawn cases; the side rules compared at +0; the strict rule read on the first-move side; the sweep's side
  not flipped; 'through p0' never said; the detector not first in the caption; minutes in seconds; the exam guard on
  the release only; the title in UTC.

### 4. The no-look-ahead check

`.venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_a1.py` (`out_lookahead_a1.txt`), 266 release
minutes (the fixed set plus the calendar's 14:00 / 14:30 minutes) x 2 side rules x 2 replacements:
- **Replaced:** every tick at / after the decision (release + 60 s) - (a) by 3,000 random ticks at other times (a
  sine of +-40 USD plus a random walk), (b) by the real later ticks mirrored around the last price.
- **Stayed equal:** every first-minute reading (p0, pre_hi / pre_lo, up1 / dn1, c1, first, leg1, t_leg, t_ext,
  give_back, two_sided, swept_pre): **1064 of 1064**.
- **Power:** the same replacement changed the label on 722 of 1064; moving only the last tick before the decision by
  5 USD changed the readings on 532 of 532.
- **The label reads only its windows:** every tick from release + 30 minutes replaced, the label stayed equal on
  **532 of 532**. PASSED.

### 5. The result

**The detector** (first leg = the first minute's larger move of 3+ USD; faked = 10 USD past p0 the other way before a
new extreme 3 USD beyond the first minute's; continued = that new extreme first; within 15 minutes of the release; on
the tick mid). Each release minute counted once.

Fixed set (every weekday's 08:30 / 10:00 NY minute with ticks: P1 62 days, P2 65 days):

| Part | NY | Minutes | Faked | Continued | Neither | Quiet | Faked: sweep / its minute / back (medians) | Came down | Through p0 |
|---|---|---|---|---|---|---|---|---|---|
| P1 | 08:30 | 62 | 3 | 13 | 13 | 33 | 14.6 USD / 10.4 / 12.9 | 0.67 | 0.33 |
| P1 | 10:00 | 62 | 7 | 29 | 11 | 15 | 15.9 / 11.9 / 11.4 | 0.57 | 0.43 |
| P2 | 08:30 | 65 | 10 | 26 | 8 | 21 | 19.1 / 12.5 / 19.0 | 0.60 | 0.50 |
| P2 | 10:00 | 65 | 10 | 41 | 6 | 8 | 17.5 / 10.9 / 29.1 | 1.00 | 0.90 |

Calendar set (the release minutes; 62 in the parts, 61 with ticks - 2026-04-03, NFP on Good Friday, has an empty
tick file):

| Part | NY | Minutes | Faked | Continued | Neither | Quiet | Faked: sweep / minute / back | Came down | Through p0 |
|---|---|---|---|---|---|---|---|---|---|
| P1 | 08:30 | 16 | 2 | 4 | 6 | 4 | 14.5 / 9.4 / 16.7 | 1.00 | 0.50 |
| P1 | 10:00 | 3 | 0 | 2 | 0 | 1 | | | |
| P1 | 14:00 | 4 | 0 | 3 | 0 | 1 | | | |
| P1 | 14:30 | 2 | 0 | 1 | 0 | 1 | | | |
| P2 | 08:30 | 26 | 5 | 13 | 5 | 3 | 13.3 / 8.5 / 26.5 | 0.80 | 0.80 |
| P2 | 10:00 | 4 | 1 | 2 | 1 | 0 | 23.3 / 6.9 / 35.7 | 1.00 | 1.00 |
| P2 | 14:00 | 4 | 2 | 0 | 2 | 0 | 11.6 / 7.2 / 29.9 | 1.00 | 1.00 |
| P2 | 14:30 | 2 | 0 | 1 | 0 | 1 | | | |

Faked counts under the four variants (side rule x the continuation threshold; the detector = larger / +3):

| Set | Part | NY | first / +0 (the researcher's) | first / +3 | larger / +0 | larger / +3 |
|---|---|---|---|---|---|---|
| fixed | P1 | 08:30 | 2 | 2 | 3 | 3 |
| fixed | P1 | 10:00 | 5 | 7 | 5 | 7 |
| fixed | P2 | 08:30 | 11 | 12 | 7 | 10 |
| fixed | P2 | 10:00 | 9 | 12 | 7 | 10 |
| calendar | P1 | 08:30 | 2 | 2 | 2 | 2 |
| calendar | P1 | 14:00 | 1 | 1 | 0 | 0 |
| calendar | P2 | 08:30 | 8 | 8 | 4 | 5 |
| calendar | P2 | 10:00 | 0 | 0 | 1 | 1 |
| calendar | P2 | 14:00 | 2 | 2 | 1 | 2 |

Described, not judged (for A2):
- Fixed set: 30 faked in 26 weeks (about 1.2 a week); 8 of them at a calendar release minute. Calendar set: 10 in
  26 weeks.
- The fake's side: P1 9 of 10 faked were a first leg DOWN then a sweep up (P1 was a climb); P2 10 down / 10 up. By
  the first leg's side: P1 down 9 of 44 faked, up 1 of 32; P2 down 10 of 46, up 10 of 55.
- Of the 30 fixed faked: the first leg went beyond the 30-minute pre-release range in 14, the sweep beyond the other
  side in 14, both in 6; 9 were two-sided first minutes; in 5 the sweep's extreme sat at minute 14+ (the window cut it).
- The tick spread in this feed is 0.39 USD at most in every release's first minute (61 of 61; median 0.39 before and
  after): the feed does not show the release widening.

**The drawn cases:** `research/2026-10-18-moments/agents/dev/charts/a1_sweeps.html` (10 cases; chosen by the rule written
in `charts_a1.py` before drawing: the owner's example; per part x minute the faked one nearest its group's median
sweep; per part the continued release minute nearest the median continuation; the largest faked that did not come
down; the largest first minute the two side rules read differently; the largest sweep the old 'any new extreme' rule
calls continued). Thai time on every axis:

1. **2026-01-09 20:30 Thai, NFP, P1 - FAKED (all four variants agree).** The owner's example: the first minute fell
   14.1 to 4459.2 in 12 s, below the 30-minute pre-release low (4462.1), and closed the minute only 2.3 down; then it
   swept up 18.6 to 4492.0 at minute 10.4, above the pre-release high (4474.8); it came back 12.9 to 4479.1 by 20:50
   Thai, not through p0. Afterwards it rose again to about 4496 at 21:10 - 21:13 Thai, where the level-break rule bought.
2. **2026-01-05 20:30 Thai, 08:30 NY (no release in the calendar), P1 - FAKED.** A small two-sided first minute (up
   3.3 / down 3.5), then up 14.6 at minute 11.0, back only 3.2 (did not come down). A noise-sized first minute.
3. **2026-01-08 22:00 Thai, 10:00 NY, P1 - FAKED.** Fell 5.1 in 45 s and closed near the low; then a steady climb of
   15.9 by minute 11.9 that kept going past the window; back 5.3 (did not come down) - a turn up rather than a two-way
   sweep.
4. **2026-01-30 20:30 Thai, PPI, P2 - FAKED.** The first minute went up 5.7 then down 12.3 (closed 11.2 down); then up
   21.7 past p0 at minute 5.6, then down 56 through p0 - all three legs. The researcher's side rule reads the same
   minute as "first leg up 5.7, sweep down".
5. **2026-01-27 22:00 Thai, 10:00 NY, P2 - FAKED.** A two-sided first minute (up 3.0, down 6.5), up 15.5 at minute
   11.5, back 18.4 through p0: three legs.
6. **2025-12-09 22:00 Thai, JOLTS, P1 - CONTINUED.** Down 6.8 in the first minute, then 8.4 further down.
7. **2026-01-29 20:30 Thai, jobless claims, P2 - CONTINUED.** Down 9.4 in the first minute, then 9.8 further down.
8. **2026-03-23 19:30 Thai, 08:30 NY, P2 - FAKED, did not come down.** Fell 15.6 in 28 s, then rallied 51.9 by
   minute 14.7 and kept rising to about +95 by 20:00 Thai: the window cut the "sweep" - a reversal into a run, not a
   sweep that comes back.
9. **2026-03-03 22:00 Thai, 10:00 NY, P2 - CONTINUED (the researcher's side rule: FAKED).** 3.7 down in the first
   seconds, then up 26.8 inside the first minute, a new high +31.1 at minute 3.8. Is the first leg the dip or the rise?
10. **2026-03-24 19:30 Thai, 08:30 NY, P2 - FAKED by the detector only (the three other variants: continued).** The
    first minute fell 3.8, then jumped to +3.9 at its 59th second (the larger side by 0.1), a new high only 0.13
    beyond at minute 1.0, then 40.2 down by minute 10.2, back 28.4. A near tie decides the side: fragile.

### 6. Questions to the measurer (and through you, the owner)

1. **The first leg's side.** Is the "fake drop in the first minute" the first minute's larger move (my detector) or
   its first 3-USD move (the researcher's)? 20 of the 177 first minutes with a leg moved 3+ USD both ways; in 13 of
   them the two rules pick opposite sides, and 11 of the researcher's 27 fakes are such minutes. Charts #4, #9, #10.
2. **"Continued" threshold.** I count a continuation only at a new extreme 3 USD beyond the first minute's; the
   researcher counted any new extreme. Should the owner's pattern include "a slightly lower low just after the first
   minute, then the sweep up" (chart #10)? This also changes the brief's "continuation is 3-5 x more frequent".
3. **The 15-minute window.** 5 of the 30 fakes still ran at minute 15 (chart #8 ran on to about +95). Should the sweep
   be followed until it stalls, and is a sweep that never comes back the owner's pattern at all?
4. **"Then it comes down".** Should the detector require the third leg to call it the owner's pattern? I measure it
   two ways: back at least half the sweep (P1 6 of 10, P2 16 of 20 fixed fakes; the owner's example passes) and back
   through p0 (the owner's example fails).
5. **Which minutes.** 22 of the 30 fixed-set fakes sit at 08:30 / 10:00 minutes without a release in our calendar (it
   lacks ISM, consumer sentiment, durable goods, home sales and others at those times). For A2, should I use every
   08:30 / 10:00 minute, only the calendar's (10 fakes in six months), or extend the calendar from official sources?
   Charts #2 and #3 look like noise or a plain turn, not a news fake.
6. **Costs at the release (for A3).** The feed's spread never exceeds 0.39 USD at a release (61 of 61 minutes). A
   real account widens at news. Should A3 add a release-spread / slippage charge beyond the brief's 0.07, and how much?

Not started: A2.

### A1 follow-up (2026-10-19; not read from the clock): the measurer's three missed bugs

The measurer's own planted bugs missed three; tests added (`test_a_tie_takes_the_side_that_reached_leg_first` now
also has the mirror - 3 down first, then 4 up: the side is down; `test_the_pre_release_range_and_the_sweeps_through_it`
now has a first leg to exactly the pre-release high and a sweep to exactly the pre-release low: neither counts;
`test_a_return_short_of_p0_is_not_the_third_leg`: back 11 of a 12 sweep came down but is not the third leg) and the
three bugs added to `plant_bugs_a1.py` (a tie always up; swept_pre on touching the high; the third leg = back >= 0.9 x
the sweep). Results under "Task P" below.

## Task P - the chart pattern at the level (2026-10-19; finished by 05:49 UTC, the log's file time)

The owner (11:15 Thai): "none of them is a place to enter - the price is very steep, there is no price structure";
"at least it must show an inverted H&S - something like this around the price level"; "chart patterns of all kinds -
at least M1 must show a chart pattern, and so must every TF used to enter"; "look at all TFs together, the smallest is
M1 ... enter on a TF, exit on that same TF".

### Written before computing (P1): the rules

Nothing is counted and no outcome is computed at this checkpoint: the detector, its tests and 12 drawn catches for
the owner to confirm.

- **Data:** M1 bars of the MT5 history (bid OHLC), read with a parquet filter from 2025-09-01 (warm-up) to before
  2026-04-18 - the exam rows are never read. M5 / M15 bars from M1 on the clock; a bar of any TF is known at its open +
  its length (never earlier). Patterns only at decisions inside P1 / P2.
- **The decision:** at each bar's close on the TF (M1, M5), closed bars only. A trade would enter at the first price at
  / after it (drawn: the next bar's open).
- **Swings on each TF (`zigzag`):** a causal ATR ZigZag, ATR(14) MT5 formula, threshold ZZ_K = 2.0 x the ATR at the
  bar. A peak is confirmed at the first bar whose low is the threshold or more below the highest high since the last
  trough (a bar that makes a new high first extends the peak); troughs mirrored. At a decision bar d the structure =
  the pivots confirmed by d plus the running extreme since the last confirmed pivot (provisional).
- **The patterns (buy side; the sell side is the exact mirror, highs <-> lows).** From the structure at d: T3 = the
  last trough (the running one, or the last confirmed one when the running extreme is a peak), before it P2 (peak),
  T2 (trough), P1 (peak), T1 (trough). ATR = the TF's ATR at d. Each has a trigger; the breakout is the FIRST close
  beyond the trigger after T3 (close[d] > trigger, every close from T3's bar to d - 1 at or below it).
  1. **Inverse head and shoulders** (sell: head and shoulders): T1 = left shoulder, T2 = head, T3 = right shoulder,
     the neckline through P1 and P2. The head below both shoulders by at least 0.5 ATR; height H = the neckline at
     the head's bar - the head; the shoulders within 0.5 H of each other; the neckline's two points within 0.5 H of
     each other; trigger = the neckline at d; from T1 to d at most 60 bars. Extreme = the head.
  2. **W (double bottom)** (sell: M): T2 and T3 the two lows, P2 the middle peak; H = P2 - the lower low; EQ =
     max(0.5 ATR, 0.15 H). "W": |T3 - T2| <= EQ. "W, the 2nd low swept the 1st": T2 - 0.35 H <= T3 < T2 - EQ. Trigger
     = P2; from T2 to d at most 40 bars. Extreme = the lower low.
  3. **Sweep, then the turn** (only at a level): T2 = the sweep low, past the level's zone (by at most 0.5 H1 ATR);
     T3 = a higher low, T3 > T2 + EQ, back at or above the zone's bottom; trigger = P2 (the high between the sweep and
     the higher low); from T2 to d at most 40 bars. Extreme = T2.
  4. **Base, then its break:** the longest run of 8 .. 40 bars ending at d - 1 whose high - low <= 1.5 x the ATR at
     d - 1; the breakout: close[d] above the base's high (buy) or below its low (sell). Extreme = the base's low (buy)
     / high (sell). Both sides at any level (a break up from a base at support is the bounce, down is the break).
  - The stop (drawn): the extreme - 0.2 ATR (buy; + for a sell).
- **Where they count:**
  - **At the owner's H1 levels:** `zones.levels_at` at the decision time (the four kinds the owner picked), zone =
    the level +- 0.1 x H1 ATR (the touches' width). A buy pattern counts when its extreme is in the zone, or below it
    by a sweep of at most 0.5 H1 ATR with the breakout close back above the zone's bottom; sells mirrored. A base
    counts when its range overlaps the zone. Several levels: the nearest to the extreme.
  - **After the news first-minute fake:** at each 08:30 / 10:00 NY minute whose first minute moved 3+ USD
    (`sweep_detector.first_minute`, the larger side - known at the release + 60 s; the label of what came after is
    NOT used), the release bar's M1 low (a down first leg) / high (up) is a level from the release + 1 min to + 15 min,
    for patterns of the other side (the owner: buy after the fake drop), with the same zone and sweep rules.
- **The TFs agreeing (drawn as a label, not a filter yet):** for an M1 entry, the M5 TF agrees when an M5 pattern of
  the same side at the same level broke out within the last 30 minutes ("M5 pattern"); else the M5 structure as it
  stands from its last two confirmed troughs and peaks: up (both higher), down (both lower), mixed. An M5 entry needs
  an M5 pattern at the level and an M1 pattern of the same side at the same level within the last 30 minutes.
- **The next level (drawn):** the nearest level of `levels_at` beyond the entry in the trade's way (more than one zone
  away). The exit rule (the entry TF's structure turning against the trade, or the next level) comes with the trades.
- **The 12 drawn catches, by rule (not by eye):** slots - M1 entries at the H1 levels, one per family (inverse H&S /
  H&S, W / M, sweep-turn, base) in P1 on the buy side and in P2 on the sell side (8); M5 entries at the H1 levels, P1
  buy and P2 sell (2); after a news fake, one per part (2; 2026-01-09 13:30 takes the P1 slot if it has a catch). In
  each slot the catch whose decision is nearest the part's middle (P1 2025-12-02 12:00 UTC, P2 2026-03-02 12:00 UTC).
  An empty slot stays empty and is reported.

### Amendments to the written rules (each found on the drawn catches by their shape, never by an outcome)

- **(1) The sell side's names.** The first drawing named the sells by the buy names ("H&S (inverse H&S)",
  "M (W)"): `unmirror` kept the variant. My own end-to-end M test asserted "W" - the test had the bug in it. Fixed in
  the code and the test (`test_the_sell_side_names`, the M test now expects "M").
- **(2) A height cap, first try (rejected).** Drawn catch #7 (2026-03-03 18:29 Thai) was a "sweep, lower high"
  whose only point at the level was the sweep; the trigger was 100 USD below it (risk 114 USD) - a move away from the
  level, not a pattern at it. First cap: height <= 1 x H1 ATR. On the redraw it dropped the owner's own 2026-01-09 W
  (height 15.6, H1 ATR 11.1 before the release) and kept a 60-USD crash pattern (H1 ATR 57.9): it measured the wrong
  scale.
- **(3) The height cap used (`HEIGHT_ATR = 4`).** A pattern's height (extreme to trigger) at most 4 x its own
  TF's ATR at the decision = two ZigZag swing sizes; a larger shape is a move, seen on the next TF up. The owner's W:
  15.6 / M1 ATR 4.33 = 3.6 (kept); the inverse H&S #1: 6.93 / 1.82 = 3.8 (kept); the two far-from-the-level crash
  patterns (the "sweep, lower high" decided 2026-03-03 11:29 UTC: 103.41 / 13.95 = 7.41, and 14:32 UTC: 50.24 / 9.61 =
  5.23) dropped. In `patterns_at`, for every family.
- **(4) The picking rule:** a slot may not reuse a decision moment (TF and time) drawn in an earlier slot (the
  inverse H&S of #1 is also a higher-low turn at the same bar; drawing it twice told the owner nothing).

### P1 - 1. What I did (files in `research/2026-10-18-moments/agents/dev/`)

| File | What it is |
|---|---|
| `patterns.py` | The detector: `load_m1` (a parquet row filter - the exam rows are never read), `tf_bars` (a bar known at open + its length), `zigzag` (causal ATR ZigZag), `structure` (the swings at a bar), `find_buy` (inverse H&S, W, the higher-low turn), `find_base`, the mirror for sells, `patterns_at`, `at_level`, `next_level`, `m_structure`, `TF`, `level_inputs` (as touches.py), `news_levels`, `locate`, `agree`; `main` writes `p_catches.parquet` (the located catches, no outcomes) and `p_news_levels.parquet`. |
| `test_patterns.py` | 31 hand-worked tests (.venv). |
| `charts_p.py` | The 12 slots, the written picking rule, the pictures (entry TF + the other TF), one HTML page (venv-research). |
| `test_charts_p.py` | 5 hand-worked tests of the picking rule, the labels, the titles and one real drawing (venv-research). |
| `plant_bugs_p.py` | 58 planted bugs in `patterns.py`, 13 in `charts_p.py`; the harness of `plant_bugs_a1.py`. |
| `lookahead_p.py` | The no-look-ahead check: truncation of the ZigZag, and every reading at the decision with the later M1 bars replaced. |
| `charts/p_patterns.html` (+ `charts/p_patterns/01..12.png`) | The 12 drawn catches. |
| `out_charts_p.txt`, `out_plant_bugs_p.txt`, `out_lookahead_p.txt` | The runs' outputs. |

### P1 - 2. The tests

`.venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_patterns.py -q` -> **31 passed in 2.03s**

| Test | What it checks | How (the hand-worked numbers) |
|---|---|---|
| `test_zigzag_by_hand` | pivots and their confirming bars | ATR 1 (threshold 2): bar 1 10.8 - 9 = 1.8 not yet; bar 2 12 - 9 = 3 -> trough 0 (9) at 2; bar 3 12 - 9.5 -> peak 2 (12) at 3; bar 4 extends to 8; bar 5 10.5 - 8 -> trough 4 at 5 |
| `test_zigzag_confirms_at_exactly_the_threshold` | ">= threshold" for the first pivot, a peak and a trough | 11 - 9 = 2.0 confirms at bar 1; a low of exactly 9.0 confirms the peak 11, a high of exactly 11.0 the trough 9 |
| `test_zigzag_an_equal_extreme_moves_the_pivot_later` | ties move the pivot | an equal high (12) at bar 3 -> the peak is bar 3, confirmed at 4; an equal low (9.5) -> the trough is bar 5, confirmed at 6 |
| `test_zigzag_skips_the_warm_up_and_extends_on_an_outside_bar` | NaN ATR, outside bars | bars 0-1 unused; bar 5 makes a new high 14 and a low 3 below the old peak: the high wins, confirmed by bar 6 |
| `test_zigzag_equals_the_precursors_zigzag_on_real_bars` | an independent implementation | `fingerprint.zigzag` on the real M1 2026-01-05 .. 01-10: all four arrays equal (300+ pivots) |
| `test_structure_at_a_bar` | the swings known at d | d 2 / 4 / 5 by hand (confirmed + the running extreme), keep=2; equal lows -> the earliest; an outside peak bar's own low is not the running trough |
| `test_first_close_above` | the breakout | closes 5, 5 at a line of 5 then 6 -> yes; 5 > 4.9 earlier -> no; 6 at 6 -> no; bar a itself above -> no |
| `test_w_equal_lows` | W | T2 100, P2 106, T3 100.3: EQ max(0.5, 0.9) -> W, trigger 106, height 6 |
| `test_w_whose_second_low_sweeps_the_first` | the swept W and its floor | 98.5 (H 7.5, floor 97.375) -> swept W; 99.0 -> W; 96.5 below the floor 96.675 -> none |
| `test_the_higher_low_turn_candidate` | the higher low | 102 > 100 + 0.9 -> the turn, extreme 100; with ATR 4 (EQ exactly 2.0): 102.0 -> W, 102.25 -> the turn |
| `test_only_the_first_close_above_and_the_span` | first close, span, the running peak | a close above at bar 9 already -> none; at the trigger -> none; 41 bars -> none; T3 confirmed with a running peak -> found |
| `test_inverse_head_and_shoulders` | the inverse H&S | neckline (3, 106)-(9, 106.5): 106.9167 at bar 14, 106.25 at the head -> height 7.25; close 107 -> found (and its inner higher-low turn); 106.9 -> not |
| `test_inverse_head_and_shoulders_edges` [4] | each rule alone | the hand case found (close 120); head 100.6 not 0.5 below 101; shoulders 4.3 apart > 3.625; neck points 5 apart > 4.75 |
| `test_inverse_head_and_shoulders_span` | 60 bars | from the left shoulder: bar 60 found, bar 61 not |
| `test_an_m_end_to_end_through_the_mirror` | ZigZag + structure + mirror + the cap | a 15-bar M, ATR 1.5: confirmations 4 / 7 / 10 / 13; at bar 14 the M (trigger 100.8, extreme 106.4, stop 106.7, height 5.6); none at 13; the precomputed mirror equal; ATR 1.39 (cap 5.56 < 5.6) -> dropped, found with the cap at 5 |
| `test_the_sell_side_names` | the mirror's names and prices | every buy variant's sell name; unmirror negates extreme / trigger / higher low / points / neckline |
| `test_a_base_then_its_break` | base | 10 bars within 1.0, close 101 -> base (0..9); bar 1 too high -> 2..9; 7 tight bars -> none; close inside / exactly at the high -> none; close below -> sell |
| `test_a_base_reads_the_atr_before_the_breakout_bar` | the width's ATR | the breakout bar's ATR 0.1 ignored; ATR 0.5 at d - 1 -> 1.0 > 0.75: none |
| `test_at_level_by_hand` | at / swept / close back | 99.6 at 100 (zone 0.5); exactly 99.5 at; 99.0 swept (close back above 99.5) / not (close 99.4); 97.4 too far from 100, swept 98; sells mirrored |
| `test_at_level_for_the_sweep_turn_and_the_base` | the turn needs a sweep, the base an overlap, the nearest wins | turn at the level -> none; swept + higher low back -> swept; higher low not back -> none; base 100.6.. -> none, 100.4.. -> base; two levels -> the nearer |
| `test_next_level` | the next level | from 101 up: 104; down: 95; from 103.7 up: 108 (104 within a zone); none above 109 |
| `test_the_tf_structure` | up / down / mixed / none | troughs 100 -> 101 and peaks 105 -> 106: up; then mixed; too few: none; down |
| `test_tf_bars_on_the_clock` | M5 from M1 | OHLC by hand, a last close (2.0) below the bar's highest close; avail open + 5 min even for the partial bar; M1 avail open + 1 min |
| `test_load_m1_never_reads_the_exam` | the reader | an end past the exam raises; 2026-01-09 13:30 low 4459.03 (the tick bid low); the last day's max < the exam |
| `test_news_levels_reads_the_first_minute_only` | the news level | a 4-USD first leg down -> the release bar's low 95.5; a later tick changed: equal |
| `test_locate_at_a_level_and_its_next_level` | locate | the synthetic M at 106.3 (zone 0.6): at, t_dec 14:15, entry 100.4 (next open), next level 98.0; a level 0.8 away -> none; before the learning start -> none |
| `test_locate_after_a_news_leg` | the news level | an up first leg at 14:05, the M at 14:15 -> at the news leg; a down first leg -> none; 21 minutes after -> none |
| `test_agree_with_the_other_tf` | agree | same side, 0.1 apart, 10 min before -> "M"; 31 min before / the other side / 0.5 apart excluded; structure down |

`data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_charts_p.py -q -W ignore` -> **5 passed in 2.27s**

| Test | What it checks | How |
|---|---|---|
| `test_the_slots_in_order` | the 12 slots | their names and order |
| `test_pick_by_the_written_rule` | the picking rule | 16 hand-made catches: the nearest the middle; a tie -> the earlier; a moment drawn before is skipped; an off-level catch not in an H1 slot; the wrong side skipped; an M5 entry needs an M1 pattern; the owner's release first, its earliest catch; empty slots stay empty -> b, c, f, -, g, i, -, -, k, -, l2, o |
| `test_title_and_agreement` | the titles | the owner's W title by hand (risk 18.73); a sell after a news leg with no next level; both agreement lines; Thai time |
| `test_label_below` | where each point's label goes | a buy's lows (L1, L2, LS, Head, RS, S, HL) below, P / N1 above; a sell's tops (H1, H2, LS, Head, RS, S, LH) above, T / N1 below |
| `test_draw_the_owner_w` | a real drawing | the 2026-01-09 W on both panels without error, PNG > 10 KB, the first tick 20:10 Thai |

Also re-run after the A1 follow-up: `test_sweep_detector.py` **29 passed in 2.09s**; `test_charts_a1.py` **4 passed**;
`plant_bugs_a1.py` **60 of 60 CAUGHT** (the three new ones - "a tie always goes up", "swept_pre counts touching the
high", "the third leg = back >= 0.9 x the sweep" - each CAUGHT by its new test).

### P1 - 3. The planted bugs

`.venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_p.py` (`out_plant_bugs_p.txt`): both controls PASSED
(31 passed / 5 passed), then **71 of 71 CAUGHT, 0 MISSED**. Two found gaps on the way, each closed by a test before this
run: "a TF bar's close = its high" (my bar test had rising closes, so last = max) and "pick: the side ignored" (my
hand-made wrong-side candidate shared a moment already drawn). Each bug, with the test that caught it:

- CAUGHT #01 patterns: load_m1 may read into the exam - `test_load_m1_never_reads_the_exam`
- CAUGHT #02 patterns: a TF bar known one minute early - `test_tf_bars_on_the_clock`
- CAUGHT #03 patterns: a TF bar's close = its high - `test_tf_bars_on_the_clock`
- CAUGHT #04 patterns: zigzag: the first pivot needs more than the threshold - `test_zigzag_confirms_at_exactly_the_threshold`
- CAUGHT #05 patterns: zigzag: a peak needs more than the threshold - `test_zigzag_confirms_at_exactly_the_threshold`
- CAUGHT #06 patterns: zigzag: a trough needs more than the threshold - `test_zigzag_confirms_at_exactly_the_threshold`
- CAUGHT #07 patterns: zigzag: an equal high does not move the peak - `test_zigzag_an_equal_extreme_moves_the_pivot_later`
- CAUGHT #08 patterns: zigzag: an equal low does not move the trough - `test_zigzag_an_equal_extreme_moves_the_pivot_later`
- CAUGHT #09 patterns: zigzag: the first pivot is the later extreme - `test_zigzag_by_hand`
- CAUGHT #10 patterns: structure: a pivot confirmed AT d left out - `test_structure_at_a_bar`
- CAUGHT #11 patterns: structure: the running extreme includes the pivot's own bar - `test_structure_at_a_bar`
- CAUGHT #12 patterns: structure: the running trough's tie goes to the later bar - `test_structure_at_a_bar`
- CAUGHT #13 patterns: structure: one pivot too many kept - `test_structure_at_a_bar`
- CAUGHT #14 patterns: first close: at the line counts as above - `test_first_close_above`
- CAUGHT #15 patterns: first close: the pattern's last low bar not checked - `test_first_close_above`
- CAUGHT #16 patterns: find_buy: the last trough is always the last item - `test_only_the_first_close_above_and_the_span`
- CAUGHT #17 patterns: W: equal lows strict - `test_the_higher_low_turn_candidate`
- CAUGHT #18 patterns: W: EQ ignores the height - `test_w_whose_second_low_sweeps_the_first`
- CAUGHT #19 patterns: W: the swept second low may go twice as deep - `test_w_whose_second_low_sweeps_the_first`
- CAUGHT #20 patterns: W: 5 bars more span - `test_only_the_first_close_above_and_the_span`
- CAUGHT #21 patterns: the higher low needs no margin - `test_w_equal_lows`
- CAUGHT #22 patterns: IHS: the head need not be 0.5 ATR lower - `test_inverse_head_and_shoulders_edges[2-100.6-the`
- CAUGHT #23 patterns: IHS: the shoulders twice as loose - `test_inverse_head_and_shoulders_edges[0-105.5-the`
- CAUGHT #24 patterns: IHS: no neckline slope rule - `test_inverse_head_and_shoulders_edges[3-111.0-the`
- CAUGHT #25 patterns: IHS: the height from the left neck point - `test_inverse_head_and_shoulders`
- CAUGHT #26 patterns: IHS: the trigger = the right neck point - `test_inverse_head_and_shoulders`
- CAUGHT #27 patterns: IHS: the span strict - `test_inverse_head_and_shoulders_span`
- CAUGHT #28 patterns: IHS: the neckline anchored on the wrong point - `test_inverse_head_and_shoulders`
- CAUGHT #29 patterns: base: the width from the breakout bar's ATR - `test_a_base_reads_the_atr_before_the_breakout_bar`
- CAUGHT #30 patterns: base: 7 bars are enough - `test_a_base_then_its_break`
- CAUGHT #31 patterns: base: a close at the high breaks it - `test_a_base_then_its_break`
- CAUGHT #32 patterns: base: the box one bar short - `test_a_base_then_its_break`
- CAUGHT #33 patterns: mirror: the kinds not flipped - `test_an_m_end_to_end_through_the_mirror`
- CAUGHT #34 patterns: unmirror: the trigger stays mirrored - `test_an_m_end_to_end_through_the_mirror`
- CAUGHT #35 patterns: the stop on the wrong side - `test_an_m_end_to_end_through_the_mirror`
- CAUGHT #36 patterns: at_level: exactly one zone away is out - `test_at_level_by_hand`
- CAUGHT #37 patterns: at_level: the sweep may go twice as far - `test_at_level_by_hand`
- CAUGHT #38 patterns: at_level: a sweep need not close back - `test_at_level_by_hand`
- CAUGHT #39 patterns: at_level: the sweep-turn may sit at the level - `test_at_level_for_the_sweep_turn_and_the_base`
- CAUGHT #40 patterns: at_level: the higher low need not be back - `test_at_level_for_the_sweep_turn_and_the_base`
- CAUGHT #41 patterns: at_level: the base must cover the level itself - `test_at_level_for_the_sweep_turn_and_the_base`
- CAUGHT #42 patterns: at_level: the first level wins, not the nearest - `test_at_level_for_the_sweep_turn_and_the_base`
- CAUGHT #43 patterns: next_level: the pattern's own level not excluded - `test_next_level`
- CAUGHT #44 patterns: next_level: min / max swapped - `test_next_level`
- CAUGHT #45 patterns: m_structure: up on either - `test_the_tf_structure`
- CAUGHT #46 patterns: m_structure: a pivot confirmed AT d left out - `test_the_tf_structure`
- CAUGHT #47 patterns: locate: the decision at the bar's open - `test_locate_at_a_level_and_its_next_level`
- CAUGHT #48 patterns: locate: the entry at the decision bar's close - `test_locate_at_a_level_and_its_next_level`
- CAUGHT #49 patterns: locate: the news level lives 30 minutes - `test_locate_after_a_news_leg`
- CAUGHT #50 patterns: locate: the news side not flipped - `test_locate_after_a_news_leg`
- CAUGHT #51 patterns: locate: decisions before the learning start kept - `test_locate_at_a_level_and_its_next_level`
- CAUGHT #52 patterns: news_levels: the wrong side of the release bar - `test_news_levels_reads_the_first_minute_only`
- CAUGHT #53 patterns: agree: no time window - `test_agree_with_the_other_tf`
- CAUGHT #54 patterns: agree: any level - `test_agree_with_the_other_tf`
- CAUGHT #55 patterns: agree: either side - `test_agree_with_the_other_tf`
- CAUGHT #56 patterns: patterns_at: the height cap twice as loose - `test_an_m_end_to_end_through_the_mirror`
- CAUGHT #57 patterns: unmirror: the sell keeps the buy name - `test_an_m_end_to_end_through_the_mirror`
- CAUGHT #58 patterns: unmirror: the sell keeps the buy labels - `test_an_m_end_to_end_through_the_mirror`
- CAUGHT #59 charts_p: pick: the earliest, not the nearest the middle - `test_pick_by_the_written_rule`
- CAUGHT #60 charts_p: pick: a tie not broken by the earlier - `test_pick_by_the_written_rule`
- CAUGHT #61 charts_p: pick: a moment drawn before may be drawn again - `test_pick_by_the_written_rule`
- CAUGHT #62 charts_p: pick: an M5 entry without an M1 pattern - `1 error in 1.64s`
- CAUGHT #63 charts_p: pick: H1 slots take catches off the H1 levels - `test_pick_by_the_written_rule`
- CAUGHT #64 charts_p: pick: the side ignored - `test_pick_by_the_written_rule`
- CAUGHT #65 charts_p: pick: the owner's release not first - `test_pick_by_the_written_rule`
- CAUGHT #66 charts_p: pick: the owner's release, the latest catch - `test_pick_by_the_written_rule`
- CAUGHT #67 charts_p: slots: the families in another order - `test_the_slots_in_order`
- CAUGHT #68 charts_p: title: the risk signed - `test_title_and_agreement`
- CAUGHT #69 charts_p: thai: UTC on the axis - `test_title_and_agreement`
- CAUGHT #70 charts_p: agreement: the other TF named wrong - `test_title_and_agreement`
- CAUGHT #71 charts_p: label_below: a sell's tops below - `test_label_below`

### P1 - 4. The no-look-ahead check

`.venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_p.py` (`out_lookahead_p.txt`):

1. **Truncation:** the production ZigZag runs once over the whole series. At 150 random M1 and 150 random M5 decision
   bars of P1 / P2, its pivots confirmed by bar d equal the ZigZag run on the bars up to d only: **M1 150 of 150, M5
   150 of 150**.
2. **Replacement:** at every located catch (1,893) and at 300 random M1 and 150 random M5 decisions (2,343 in all), on
   a window of M1 from 7 days before to 1 day after the decision: everything read at the decision - the patterns
   breaking out at that bar (family, side, variant, trigger, extreme, stop, every point), the owner's H1 levels and the
   H1 ATR at that moment (`zones.levels_at`), the other TF's structure - computed, then every M1 bar from the decision
   on replaced by a random path (+-40 USD, other highs / lows / closes) and computed again: **2,343 of 2,343 equal.
   PASSED.**
   - **Power:** the same replacement changed the structure 10 bars after the decision in 2,343 of 2,343; moving only
     the decision bar's close by 3 ATR changed the patterns found at it in 237 of 479 decisions that had one. The other
     242 moves went the breakout's own way (+3 ATR on a buy breakout keeps it a breakout), so they changed nothing.
3. The news level: `test_news_levels_reads_the_first_minute_only` (a later tick changed, the level equal); the label of
   what came after (A1's `race`) is not read anywhere in Task P.

### P1 - 5. The result: the 12 drawn catches (nothing counted, no outcome computed)

`research/2026-10-18-moments/agents/dev/charts/p_patterns.html` (PNGs in `charts/p_patterns/`). Thai time; points as
stored in `p_catches.parquet`. Left: the entry TF with the level's zone (purple), the pattern's points (orange), the
neckline / trigger, the decision (blue line), the entry (blue arrow, the next bar's open), the stop (red dashed), the
next level (green dashed); right: the other TF.

1. **2025-12-02 09:45, P1, M1 inverse H&S at the x2 level 4217.43 (the head swept it).** LS 09:07 4215.39, N1 09:17
   4223.24, Head 09:31 4214.32, N2 09:37 4220.40, RS 09:41 4216.79; the first close above the falling neckline (4219.41)
   at 09:44; entry 4221.43, stop 4213.96 (7.47 USD), next level 4244.58. M5 structure as it stands: down.
2. **2025-12-02 20:24, P1, M1 W at the previous day's low 4205.25 (swept).** L1 20:13 4202.06, P 20:18 4207.34, L2
   20:20 4202.01; entry 4207.53, stop 4201.49 (6.04), next level 4226.20. M5: up.
3. **2025-12-04 21:33, P1, M1 sweep then the higher low at the x3+ / flip level 4205.00.** S 21:19 4202.51 (past the
   zone), P 21:23 4210.23, HL 21:30 4205.00 (back at the level); entry 4211.42, stop 4202.10 (9.32), next level
   4214.07 - only 2.65 above the entry. M5: mixed.
4. **2025-12-02 23:09, P1, M1 base then the break up on the x3+ / flip level 4168.42.** The base 23:00 - 23:07
   (4166.88 - 4174.25, 8 bars) after a fast drop; entry 4174.17, stop 4166.01 (8.16), next level 4201.55. M5: up. The
   base is 7.4 USD wide: "tight" against that hour's M1 ATR (4.35), not tight to the eye.
5. **2026-03-04 00:04, P2, M1 head and shoulders at the x2 level 5128.87 (the crash night).** LS 23:23 5126.01, N1
   23:34 5107.65, Head 23:37 5134.64, N2 23:46 5100.46, RS 23:49 5115.71; the close below the neckline (5090.27) at
   00:03; entry 5084.69, stop 5136.35 (51.66 - the night's M1 ATR 8.53, the H1 zone +-7.2), next level 5074.30 (10
   below). M5: down.
6. **2026-03-02 16:21, P2, M1 M at the last top 5393.02 (swept).** H1 16:09 5400.05, T 16:11 5389.59, H2 16:17
   5398.65; entry 5388.73, stop 5400.86 (12.13), next level 5340.76. M5: mixed.
7. **2026-03-03 21:42, P2, M1 sweep then the lower high at the x2 level 5128.87 (the crash night, 2.4 hours before
   #5).** S 21:29 5147.20, T 21:36 5102.26, LH 21:39 5133.09; the close below T at 21:41; entry 5085.59, stop 5149.65
   (64.06; height 44.94 = 3.7 M1 ATR), next level 5074.30. M5: mixed. The level is only the sweep's; the breakout is
   43 USD below it.
8. **2026-03-02 16:46, P2, M1 base then the break down at the last top 5393.02 (25 minutes after #6).** The base
   16:37 - 16:44 (5394.57 - 5398.30); entry 5392.28, stop 5398.83 (6.55), next level 5340.76. M5: mixed.
9. **2025-11-27 22:25, P1, M5 W at the x3+ / flip level 4156.94 (swept), with an M1 W agreeing.** L1 21:40 4152.92, P
   21:45 4158.93, L2 21:55 4152.88 (M5 bars); entry 4159.58, stop 4152.33 (7.25), next level 4168.42. M1 structure:
   down.
10. **2026-03-05 15:05, P2, M5 base then the break down at the x2 level 5167.80, with an M1 M agreeing.** The base
    14:10 - 14:55 (5158.90 - 5167.87); entry 5156.16, stop 5169.20 (13.04), next level 5104.52. M1: mixed.
11. **2026-01-09 20:32, P1, M1 W whose second low swept the first - the owner's NFP example.** L1 20:20 4461.94, P
    20:25 4474.63, L2 20:30 4459.03 (the release minute's fake drop, at the x3+ / flip level 4459.43); the first close
    above P at 20:31 (4476.85); entry 4476.89, stop 4458.16 (18.73), next level 4479.41 - only 2.52 above the entry.
    M5: mixed. It is also at the news level (the release bar's low); the H1 level is shown.
12. **2026-03-02 22:09, P2, M1 W whose second low swept the first, after the 10:00 NY first minute.** L1 21:52
    5320.53 (before the release), P 21:53 5340.32, L2 22:06 5310.83 (6 minutes after the release, 9.5 below the
    release bar's low 5320.30); entry 5345.03, stop 5308.90 (36.13), next level 5419.09. M5: mixed.

### P1 - 6. Questions to the measurer (and through you, the owner)

1. **Are these the patterns meant?** Each picture has its slot and its points; the owner's confirmation (or the cases
   that are wrong, and why) comes before any count or trade.
2. **The swing size of "a pattern on M1":** the ZigZag swing is 2 x the TF's ATR(14). On calm P1 days that makes
   patterns of 5 - 15 USD; on the 2026-03-03 crash night 30 - 50 USD (#5, #7). Keep it relative, or cap it in USD?
3. **The sweep allowance:** a pattern's extreme may go past the level's zone (+-0.1 H1 ATR) by up to 0.5 H1 ATR (7 - 30
   USD by the day). Your touches measured 90 % of turns within about 7 USD past. Use that (the touches' 90th
   percentile, in H1 ATRs) instead?
4. **The base after a fast move (#4):** "tight" is 1.5 x the ATR at the bar before the break, and after a fast drop the
   ATR is high, so a 7.4-USD range counts. Judge the base against a calmer ATR (e.g. the day's median)?
5. **The TFs agreeing:** for an M1 entry I only label the M5 (a same-side M5 pattern in the last 30 minutes, or the M5
   structure up / down / mixed); I filter nothing yet. #1 is an M1 buy at support with the M5 structure down. Should
   an entry need the M5 not against it (the owner: "the direction from the TF right above the entry as it stands
   now")?
6. **Several patterns on one bar:** an inverse H&S is often also a higher-low turn on the same bar. For the trade, one
   entry; which family names it does not change the entry, but the stop does (the head vs the sweep low) - take the
   nearer stop or the farther?
7. **The next level is sometimes very close** (#3 2.65 USD, #11 2.52 USD above the entry, against stops of 9 and 19).
   For the exit, skip the levels nearer than, e.g., one risk?
8. **The levels' inputs:** `zones.levels_at` gets its H1 / D1 bars from `indicators.bars` (known at the last M1 minute
   + 1), as `touches.py` does; my own TFs are known only at open + their length. A bar missing its last minutes would
   be known a minute or so early in the levels. Keep the researcher's (comparable with touches.parquet) or use the
   strict one?

Not started: counting, trades and R (they wait for the owner's confirmation of the catches); Task A2.

## Task P2 - the pattern catches as trades, A (at the breakout) against B (wait for the structure) (2026-10-19; the rules written at 05:49 UTC, the code from 06:24 UTC by `date -u`)

The owner (12:46 Thai): "run the backtest with the pictures you got, and you will know whether it is a quality setup -
or else wait for the price structure to reveal itself and enter then; see whether that makes a better profit." The
measurer: this replaces "no counts before the confirmation". P1's measurement: 60 + 9 tests passed, 71 of 71 of my
bugs and 13 of 13 of the measurer's caught, the entry = the next open on 1,475 of 1,476 M1 catches (the other has no
next bar before the daily break - dropped here).

### Written before computing (P2): the rules

- **The catches:** every row of `p_catches.parquet` (M1 and M5, at the H1 levels or after a news leg) with a finite
  entry. P1 and P2 only; ticks of a day after 2026-04-17 are never loaded (a trade cannot reach them: the weekend).
- **One position at a time per variant**, all catches (both TFs, all families) in one stream by entry time; a catch
  whose entry comes before the open trade's exit is skipped. Several catches at the same entry time: the one with the
  smallest risk read at the decision (|the decision close - the stop|). No daily cap.
- **Entry A, at the breakout:** the first tick at / after the decision (the breakout bar's close).
- **Entry B, wait for the structure (buy; sells mirrored):** on the entry TF, from the bar after the breakout bar d:
  1. the post-breakout high = the highest high from bar d on, extended by any bar that makes a new high (a bar that
     makes a new high does not also count as the pullback);
  2. the pullback = a bar whose low is at least 1 x the entry TF's ATR (at d) below the post-breakout high; from then
     the high is frozen and the pullback low is the lowest low since;
  3. the confirmation = the first close above the frozen post-breakout high after the pullback (a higher low held,
     then the high broken); the entry at the first tick at / after that bar's close;
  4. no trade if any bar's low reaches the pattern's extreme first (the structure failed), or if no confirmation
     within 30 entry-TF bars after the breakout bar.
  - Stop **B1**: the pullback low - 0.2 x ATR; stop **B2**: the pattern's own stop (A's).
- **The stop (A):** the pattern's stop (the extreme - 0.2 x ATR at d, from the catch). A trade whose entry fill is
  already past its stop is not taken.
- **The exits (the entry TF, the owner's "enter on a TF, exit on that same TF"):** the first of -
  1. **stop:** the first tick at / beyond the stop (a buy: bid <= stop), filled at that tick (the gap included);
  2. **target:** the catch's next level, only when it is more than one risk (|entry - stop|) beyond the entry; a limit
     at the level (a buy: the first bid >= it, filled at it);
  3. **structure:** at the close of each entry-TF bar that opens at / after the entry, a buy closes below the last
     trough of the entry TF's ZigZag confirmed by that bar (a sell: above the last confirmed peak) - out at the first
     tick at / after that close;
  4. **time:** 60 entry-TF bars after the entry (M1 1 hour, M5 5 hours) - out at the first tick at / after it;
  5. **break:** before a gap of more than 30 minutes in the ticks (the daily break, the weekend) - out at the last tick
     before it.
  - Out at market = the bid (a buy) / the ask (a sell). On one tick: stop before target before structure before time.
- **Costs:** the spread in the tick bid / ask; entry slippage 0.07 USD (a buy at ask + 0.07, a sell at bid - 0.07). A
  news trade (entry within 15 minutes after a release minute of the calendar or an 08:30 / 10:00 NY news leg) also
  pays 0.5 / 1 / 2 USD more at entry - four cost runs: 0 (the main tables) / 0.5 / 1 / 2.
- **R** = USD / the risk at the fill (|entry fill - stop|); 0.01 lot: 1 USD of price = 1 USD.
- **Settings:** three - A, B1, B2 (each with the four news costs as cost runs, not settings). Nothing else is varied.
- **The report, per part, A / B1 / B2 side by side:** trades and trades a weekday (Mon-Fri of the part), win %, R
  and USD after costs with a 95 % range of R (mean +- 1.96 x sd / sqrt(n)), max drawdown, worst trade, longest losing
  streak (USD), the exits; split by family, by TF, by level kind, by the other TF agreeing (a same-side pattern / its
  structure with the trade / against / mixed or none), and big (the pattern's height or the risk above 20 USD) against
  the rest.
- **How it is judged:** each variant by the smaller R of P1 / P2 (never one part), against the goal (+0.15 R a trade
  after costs); A against B by the same.
- **Losers by reason (what came after x what was there):** after the entry, within the trade's own time limit, on the
  ticks: **wrong way** (1 risk against before 1 risk our way), **ran later** (1 risk our way first - the trade was out
  before it paid), **no run** (neither); x the other TF at the decision: **with** (a same-side pattern, or its
  structure with the trade), **against**, **mixed / none**. One loser drawn per reason (the nearest its reason's median
  USD), for the variant with the larger smaller-part R.

### P2 - how two phrases of the written rules are coded (written before computing, 06:27 UTC by `date -u`)

- "the smallest risk read at the decision" for a B entry: its decision is the confirmation bar's close, so the risk
  read there is |the confirming close - the B stop|.
- "each entry-TF bar that opens at / after the entry" (the structure exit): the entry = the entry decision time (the
  breakout bar's close for A, the confirming bar's close for B); the fill is the first tick at / after it.
- The 95 % range of R = mean +- 1.96 x the sample sd / sqrt(n); the longest losing streak = the most consecutive
  trades with USD < 0 (the larger loss on a tie of length), with its USD.

### P2 - the owner's two added rules (13:37 Thai), applied

- "Beware of interpreting correctly while the metric is wrong": every reported metric is recomputed by a second,
  separate program (`verify_p2.py`, which imports none of `p2_trades`, `sweep_detector`, `tick_straddle`), 20 trades a
  variant are re-derived from the raw tick files, and one position at a time is checked - section P2-5.
- "Never read a loss as like a coin flip": no random-side baseline, no "chance" verdict; the result is split by what
  was there (section P2-6).

### P2 - 1. What I did (files in `research/2026-10-18-moments/agents/dev/`)

| File | What it is |
|---|---|
| `p2_trades.py` | `confirm_b` (entry B), `last_pivot_prices`, `structure_exit_time`, `simulate` (the ticks), `news_times` / `is_news`, `agreement_group`, `candidates` (A / B1 / B2), `Ticks` (a day + the next, never the exam), `one_trade`, `run_stream` (one position at a time), `weekdays`, `stats`, `reason`; `main` writes `p2_trades.parquet`, `p2_metrics.csv` and `out_p2_trades.txt`. |
| `test_p2_trades.py` | 20 hand-worked tests. |
| `verify_p2.py` / `test_verify_p2.py` | The second, separate computation of every metric, the raw-tick re-derivation, the one-position check; 7 hand-worked tests. |
| `losers_p2.py` / `test_losers_p2.py` | The losers joined to their catches, one drawn per reason; 2 tests. |
| `p2_splits.py` | P1 / P2 side by side for every split (`out_p2_splits.txt`). |
| `plant_bugs_p2.py`, `plant_bugs_verify_p2.py` | 57 and 17 planted bugs. |
| `lookahead_p2.py` | The no-look-ahead check of the trades. |
| `charts/p2_losers_B2.html` (+ `charts/p2_losers_B2/01..09.png`) | One B2 loser per reason. |

### P2 - 2. The tests (run at 06:51 UTC)

- `test_p2_trades.py` **20 passed in 1.57s**; `test_verify_p2.py` **7 passed in 1.55s**; `test_losers_p2.py` **2 passed
  in 1.65s**; the earlier files again: `test_sweep_detector.py` + `test_patterns.py` **60 passed**, `test_charts_a1.py` +
  `test_charts_p.py` **9 passed**.

| Test | What it checks | How (the hand-worked numbers) |
|---|---|---|
| `test_confirm_b_by_hand` | entry B | bar 1 a new high 106 (not a pullback); bar 2's low 104.8 is 1.2 >= 1 ATR below: the pullback; bar 3 dips to 104.5; bar 4 closes 106.2 > 106: confirmed at 4, pull 104.5 |
| `test_confirm_b_fails` | no trade | a low at the extreme 100 first; max_wait 3 (the confirmation is the 4th bar); 1.25 ATR -> still bar 4; 1.6 ATR -> no pullback |
| `test_confirm_b_pullback_threshold_and_new_high_bars` | the edges | a dip of exactly 1.0 ATR is the pullback (pull 105.0); a new-high bar with a deep low is not; bar 5 confirms with pull 105.4 |
| `test_confirm_b_closes_at_the_high_is_not_above` | strict | a close of exactly 106.0 does not confirm |
| `test_confirm_b_sell_is_the_mirror` | sells | the negated series: k 4, hi -106, pull -104.5 |
| `test_last_pivot_prices` | the confirmed pivots per bar | a trough confirmed at bar 3 counts from bar 3 (not its own bar 1), the next from bar 9; the peak from 6 |
| `test_structure_exit_time` | the structure exit | a close 98.9 below the trough 99 at bar 5 -> out at its close (6 min); a close AT 99 -> no; bar 9 closing at the limit counts, after it not; a sell above the peak 105; a bar opening before the entry not read |
| `test_simulate_stop_with_its_gap` | stop | in 100.27 (ask 100.2 + 0.07); the bid 97.5 through the stop 98 -> filled 97.5, -2.77 USD, R -2.77 / 2.27; a tick exactly at 98 fills |
| `test_simulate_target_is_a_limit` | target | filled at 104.0 although the tick was 104.6 |
| `test_simulate_structure_time_break_and_order` | the other exits | structure at the first tick at / after 15 s (and AT 20 s); time at the first tick >= 25 s; the ticks end: break; a gap of 1801 s: out before it, of exactly 1800 s: not a break; stop before structure on one tick |
| `test_simulate_sell_costs_and_refusals` | sells, news cost | a sell in at bid - 0.07 - 1.0 = 98.93, its stop read on the ask (102.1); its target on the ask; refused past the stop or without a tick |
| `test_is_news` | news entries | 1000 s release: 999 no, 1000 / 1900 yes, 1901 no |
| `test_agreement_group` | with / against / mixed | a same-side pattern; up for a buy, down for a sell; the opposite; mixed / none |
| `test_candidates_a_and_b` | the candidates | A at the decision with the pattern's stop, risk 4.7; B1 at bar 4 with the stop 104.3, risk 1.9; B2 the pattern's stop; no confirmation -> none; ties by the smaller risk |
| `test_run_stream_one_at_a_time_target_and_news` | the stream | a target exit at 300 s; an entry at 100 s skipped; an entry AT 300 s taken; a next level within one risk -> no target; a news entry pays 1.0 more; time exits after 60 M1 bars |
| `test_one_trade_target_needs_more_than_one_risk` | the target rule | binary prices, no slippage: risk exactly 2.0, a level exactly 2.0 away -> none, 2.25 away -> the target |
| `test_weekdays` | trades a weekday | P1 64, P2 66 weekdays |
| `test_stats_by_hand` | the metrics | USD 2, -1, -1, 3, -2: R 0.1 with its range, USD 1, drawdown 2 (also when given out of order), worst -2, streak 2 / -2, exits; a first loss of 3 is a drawdown of 3; a flat trade breaks the streak; the streak in time order |
| `test_reason_by_hand` | the losers' reasons | ran later / wrong way / no run; exactly one risk our way counts; only up to the first tick at / after the limit; a sell read on the ask (the bid 2.13 our way but the ask only 1.93: no run) |
| `test_ticks_never_load_the_exam` | the tick reader | 2026-04-17's span holds only its own day; 2026-04-18 is not loaded |
| `test_verify_p2.py` (7) | the second computation | its own weekdays (64 / 66 / a weekend 0); its own metrics on the same hand table and on a sell, a first loss, a flat trade, the streak in time order; the re-derivation of a stop / target / time / structure / break / sell trade and each wrong field found (fill price, stop tick, target first hit, time tick, break of exactly 30 min, USD only); the raw ticks in ns (the 13:30 low bid 4459.03); an exam day refused even with a (fake, temporary) file there; one position at a time |
| `test_losers_p2.py` (2) | the losers' join and title | only the variant's losers at cost 0 joined on TF / time / family / side; a missing catch raises; the title by hand |

### P2 - 3. The planted bugs

- `plant_bugs_p2.py` (`out_plant_bugs_p2.txt`): controls PASSED (20 / 2 passed), **57 of 57 CAUGHT** - 50 in
  `p2_trades.py` (entry B's edges and mirror, the pivots by their confirming bar, the structure exit's bar range and
  strictness, the entry price and slippage and news cost, the stop's gap and edge and the ask for sells, the target as
  a limit, the order on one tick, the break and time ticks, R from the fill's risk, news windows, agreement, the B
  stops, ties, the target's one-risk rule, the time limit, the position limit, the drawdown from 0, flat trades in the
  streak, the 1.96, the time order, the weekdays, the reasons) and 7 in `losers_p2.py`. On the way: one planted bug
  (removing a `continue` in B's first phase) was equivalent - the high bounds every close there, it changes nothing -
  and was replaced by "the high not frozen after the pullback" (CAUGHT); seven gaps (exact 1-ATR pullback, a close at
  the trough, a tick at the stop, a tick at the structure time, an entry at the exit moment, a first-trade drawdown,
  flat trades / time order in the streak) got tests first.
- `plant_bugs_verify_p2.py`: control PASSED (7 passed), **17 of 17 CAUGHT** (five gaps closed by tests first: flat
  trades, the time order, the USD alone, an exam-day file).

### P2 - 4. The no-look-ahead check

`lookahead_p2.py` (`out_lookahead_p2.txt`), 150 seeded catches a variant, on a window of M1 from 7 days before to 2
days after: **A 150 of 150, B1 84 of 84, B2 82 of 82** trades equal (the entry tick and price, the stop, the risk, the
exit's reason, tick and price, the USD) when every M1 bar opening after the exit and every tick after it were replaced
by other prices; **B confirmations 84 of 84 and 82 of 82** equal when every bar from the confirmation's close on was
replaced. Power: replacing everything from the entry decision on changed the exit of 150 / 84 / 82 of them. PASSED.

### P2 - 5. The numbers checked by a second program (the owner's rule)

`verify_p2.py` (`out_verify_p2.txt`): **384 of 384** metric values agree with `p2_metrics.csv` (24 variant x part x
news-cost rows x 16 metrics); **60 of 60** trades re-derived from the raw tick files agree (the fill tick and price
with the 0.07, no tick past the stop between the fill and the exit, the exit tick and price for its reason, the USD
and R); **0** entries before a previous exit in 12 variant x cost streams (10,129 trades). PASSED. The check found one
bug - in itself: the tick files hold milliseconds and its first reader treated them as nanoseconds (every fill tick
"failed"); fixed, and a test now pins the unit on 2026-01-09.

### P2 - 6. The result (news cost 0; `out_p2_trades.txt`, `out_p2_splits.txt`)

Three settings (A, B1, B2), each run with the four news costs. One position at a time, no daily cap.

| | A P1 | A P2 | B1 P1 | B1 P2 | B2 P1 | B2 P2 |
|---|---|---|---|---|---|---|
| trades (a weekday) | 522 (8.2) | 565 (8.6) | 382 (6.0) | 364 (5.5) | 352 (5.5) | 348 (5.3) |
| win % | 35.8 | 35.8 | 34.8 | 32.1 | 38.6 | 38.2 |
| R a trade | -0.047 | -0.045 | -0.043 | -0.082 | -0.026 | -0.014 |
| 95 % range of R | -0.141 .. +0.047 | -0.137 .. +0.046 | -0.179 .. +0.092 | -0.220 .. +0.056 | -0.111 .. +0.059 | -0.101 .. +0.073 |
| USD | -78.92 | -301.83 | -114.84 | -500.35 | -67.91 | +48.08 |
| max drawdown USD | 393.76 | 512.21 | 263.66 | 593.51 | 313.07 | 454.52 |
| worst trade USD | -29.66 | -97.41 | -24.85 | -52.73 | -35.60 | -54.21 |
| longest losing streak | 11 (-65.35) | 16 (-98.67) | 9 (-32.66) | 10 (-103.67) | 9 (-39.21) | 11 (-125.53) |
| exits stop / target / structure / time / break | 137 / 37 / 242 / 88 / 18 | 138 / 50 / 269 / 84 / 24 | 153 / 21 / 143 / 57 / 8 | 140 / 31 / 136 / 43 / 14 | 29 / 8 / 234 / 71 / 10 | 25 / 19 / 220 / 68 / 16 |

- **The smaller part's R:** A -0.047, B1 -0.082, **B2 -0.026** (with +2 USD news slippage: -0.051 / -0.088 / -0.029). No
  variant reaches the goal (+0.15 R); none is positive in both parts. Waiting for the structure with the pattern's own
  stop (B2) is the best of the three by 0.02 - 0.03 R, with fewer trades (5.3 - 5.5 a weekday against 8.2 - 8.6) and
  far fewer stops (29 / 25 against 137 / 138); the tight stop under the pullback (B1) is the worst (153 / 140 stops).
- **Risk sizes:** the median risk A 7.7 / 12.5 USD, B2 10.5 / 18.5 (B2 enters farther from the pattern's stop); the
  largest 189 USD (A P2) - P2's wide days. A P2's worst trade is -97.41 USD = -1.01 R on a 96.75-USD risk (an M5 W 69
  USD tall, 2026-02-02 21:35 Thai). Because the risk varies, R and USD can differ in sign (B2 P2: R -0.014, USD +48).
- **The news costs barely move the totals:** 12 - 22 news trades a part.

**Where it pays and where it does not** (`p2_splits.py`: 36 cells a variant, 108 in all; a cell is flagged when it is
positive in both parts with >= 20 trades in each - with 108 cells looked at, a flag is a lead, not a result):

| | A | B1 | B2 |
|---|---|---|---|
| inverse H&S / H&S | -0.107 / +0.249 | **+0.054 / +0.504** (31 / 26) | **+0.047 / +0.149** (29 / 25) |
| W / M | -0.028 / -0.049 | -0.047 / -0.062 | -0.034 / +0.016 |
| sweep then the turn | -0.157 / -0.131 | -0.147 / -0.456 | -0.142 / -0.209 |
| base then the break | -0.029 / -0.069 | +0.001 / -0.217 | +0.081 / -0.110 |
| M1 entries | -0.022 / -0.087 | -0.037 / -0.165 | -0.046 / -0.048 |
| M5 entries | -0.141 / +0.117 | -0.074 / +0.250 | **+0.066 / +0.117** (62 / 71) |
| other TF with / against | -0.064 / +0.056 ; -0.067 / -0.080 | -0.106 / -0.042 ; +0.077 / -0.186 | -0.054 / +0.029 ; +0.026 / -0.069 |
| big (height or risk > 20 USD) | +0.076 / -0.077 | +0.229 / -0.141 | **+0.075 / +0.024** (56 / 158) |

- **Pays in both parts:** the head-and-shoulders family when entered after the structure confirms (B1, B2; on M1 too:
  B1 +0.134 / +0.256, B2 +0.063 / +0.061); M5 entries in B2; big patterns in B2; (B1 in the Asia session +0.017 /
  +0.033). None of them is +0.15 in both parts, and they are 25 - 71 trades a part.
- **Loses in both parts, in every variant: the sweep then the turn** (-0.13 .. -0.46). W / M, the largest family (70 -
  73 % of the trades), sits near 0 and decides the total.
- **The other TF agreeing does not separate them** (with / against change sign between the parts).

**The losers by reason** (B2, the variant with the larger smaller-part R, as written before computing; the share of the
part's losers): **wrong way 0.44 / 0.46** (one risk against first), **no run 0.49 / 0.42**, **ran later 0.08 / 0.12**;
across the other TF (with / against / mixed) the shares are alike, so the other TF does not explain them. A's losers:
wrong way 0.66 / 0.66, ran later 0.16 / 0.15. Winners average +0.77 R (B2) / +1.17 R (A), losers -0.52 / -0.72.
One drawn per reason: `research/2026-10-18-moments/agents/dev/charts/p2_losers_B2.html` -
1. wrong way x mixed / none (75): 2026-01-27 00:25 Thai, M1 base break down at x2 5095.67 - out by the structure,
   -8.18 USD.
2. no run x mixed / none (71): 2026-03-17 09:03, M1 base break up at x3+ / flip 5020.34 - out at the time, -5.94.
3. no run x with (70): 2026-02-11 10:30, M5 W at x3+ / flip 5044.49 - out at the time, -5.59.
4. wrong way x with (68): 2026-01-06 20:46, M1 W at the previous day's high 4455.58 - the stop just under the W's lows
   was taken (-8.94), then price rose about 15 USD.
5. no run x against (55): 2026-01-07 15:18, M1 W at x3+ / flip 4460.00 - out by the structure, -3.46.
6. wrong way x against (51): 2025-12-22 22:13, M1 sweep then lower high at the 5-day high 4427.29 - out by the
   structure, -8.95.
7. ran later x with (19): 2025-11-04 17:05, M5 base break down at x3+ / flip 3998.53 - out by the structure, -4.73.
8. ran later x mixed / none (16): 2025-12-24 20:03, M1 M at x2 4495.23 - out by the structure, -3.81.
9. ran later x against (6): 2025-11-03 21:28, M1 M at x3+ / flip 4021.64 - out by the structure, -4.66.

### P2 - 7. Questions and what I would do next

1. **B2 as the base?** Waiting for the structure with the pattern's own stop is the best of the three in both parts
   (still below 0). Keep B2 as the base for the next changes?
2. **The head-and-shoulders family and M5 entries pay in both parts under B2** (+0.047 / +0.149 and +0.066 / +0.117),
   chosen after looking at 108 cells. Next I would write ONE rule before computing (e.g. B2, inverse H&S / H&S on M1
   and M5, plus any family on M5) and test it on P1 / P2 - but it gives about 0.5 - 1.5 trades a weekday, short of 2 -
   3. Go ahead, or first measure why those families pay (their MFE / MAE paths)?
3. **The sweep then the turn loses everywhere.** Change its conditions (the owner: never drop - e.g. the turn only with
   the M5 structure turned too, or the higher low confirmed by the ZigZag) or set it aside for now?
4. **The exits:** the structure exit takes 63 - 66 % of B2's trades and the next level is rarely more than one risk away
   (8 / 19 targets). Is "a close past the last confirmed trough of the entry TF" what the owner means by the structure
   turning against the trade? An exit study (how far the winners ran after the structure exit) would come before any
   change.
5. **The trades a weekday:** A makes 8.2 - 8.6, B 5.3 - 6.0, with one position at a time. A daily cap needs a reading
   known at the decision to choose by; none of the readings measured here separates the losers - so I have not added
   one.

## Task P3 - changes to B2, one at a time (the owner's go-ahead 14:51 UTC; these rules written from 14:53 UTC, `date -u`)

The measurer's P2 measurement: 87 + 11 tests passed; 57 / 57 and 17 / 17 planted bugs; 7 of its 8 bugs caught - the
miss "M5 held 60 minutes, not 60 bars" now has a hand test (`test_an_m5_trade_is_held_60_m5_bars`: 300 minutes) and is
in `plant_bugs_p2.py`; its independent check equal everywhere (60 / 60 trades, 1244 / 1244 structure exits).

### Written before computing (P3): the rules

**The base is B2 exactly as in P2** (the entry after the structure confirms, the pattern's own stop, the exits stop /
next level when more than one risk away / the structure close / 60 entry-TF bars / the break, costs 0.07 + the news
costs, one position at a time). The new engine must reproduce P2's B2 numbers exactly before any change is run.

Each change below is ONE setting, run alone against B2, P1 / P2:

1. **L - the late entry.** Refuse a B entry when its confirming close has already covered the pattern's measured move:
   side x (the confirming close - the trigger) >= the pattern's height. The yardstick is the pattern's own: the height
   (extreme to trigger) is the classic measured move from the breakout line. Why not "past the level": for an inverse
   H&S, a W or a turn the extreme sits at the level and the trigger is already about one height past it, so "more than
   the height past the level" is true of nearly every breakout entry by construction - it would refuse nearly all.
   (The trigger of an inverse H&S is the neckline's value at the breakout bar.)
2. **Xa - out on the pattern's own invalidation.** Replace the structure close (any newer ZigZag trough) by: out at the
   first tick at / after the close of an entry-TF bar (opening at / after the entry decision, closing by the time
   limit) that closes past the pattern's invalidation - the last point of the pattern on the extreme's side: the right
   shoulder (H&S), the second low / high (W / M), the higher low / lower high (the turn), the base's far edge (the box's
   low for a break up, its high for a break down). The stop, the target and the time are unchanged.
3. **Xb - break-even, then trail.** Replace the structure close by: once a tick is one risk our way (a buy: the bid >=
   the fill + the risk), the stop moves to the fill (break-even); then at the close of every entry-TF bar after that
   tick the stop rises (a buy) to the last trough of the entry TF's ZigZag confirmed by that bar minus 0.2 x the
   pattern's ATR, when that is higher (a sell mirrored, the peaks plus 0.2 ATR); the stop never moves back. A moved
   stop fills like the stop (the first tick at / beyond it, the gap included); its exit is named "trail". The target
   and the time are unchanged.
4. **Xab - Xa and Xb together.**
5. **ST - the sweep then the turn, with the M5 agreeing.** A "sweep, higher low" (a "sweep, lower high") is traded
   only when, at its entry decision, either the M5 ZigZag's last confirmed trough is above the one before it (a higher
   low; for sells the last confirmed peak below the one before it), or (an M1 catch) an M5 pattern of the same side at
   the same level broke out within the 30 minutes before its breakout (`other_pattern`). Every other family as B2.
6. **LEAD - one rule from the leads' paths.** First, measured on B2's trades from the fill over each trade's own window
   (60 entry-TF bars), on the ticks: the MAE and the MFE (in R and USD) and the minute of each, for the H&S family
   against the rest and M5 entries against M1, per part. The rule is then written here, from what differs, BEFORE it
   is run.

- **Settings:** six (L, Xa, Xb, Xab, ST, LEAD), each against B2. A combination of the ones that help comes only after,
  and is named as a seventh setting if run.
- **The report per setting, P1 / P2 side by side against B2:** trades a weekday, win %, R with its 95 % range, USD, max
  drawdown, worst trade, longest losing streak, the exits; the smaller part's R decides.
- **The checks:** hand tests, planted bugs and the look-ahead check for every new function; the second computation of
  every metric and 20 trades a setting re-derived from the raw ticks (the trailing stop's schedule included); one
  position at a time; the losers by reason drawn for the best setting; the splits by what was there.

### P3 - the leads' paths, and the LEAD rule written before it is run (written at the clock time below)

`p3_paths.py` (`out_p3_paths.txt`, tests `test_p3_paths.py` 3 passed): B2's trades from the fill over their own
windows, medians P1 / P2 -
- **the H&S family against the rest:** MAE 0.55 / 0.51 R against 0.68 / 0.69; MFE 0.57 / 0.59 against 0.65 / 0.63;
  the stop reached (MAE >= 1 R) 0.24 / 0.28 against 0.29 / 0.31; the same risk in USD (12.1 / 18.1 against 10.5 /
  18.5);
- **M5 against M1:** MAE 0.55 / 0.58 against 0.70 / 0.69; MFE 0.61 / 0.56 against 0.64 / 0.64; MAE >= 1 R 0.26 / 0.24
  against 0.29 / 0.33; the risk 2.4 x wider (24.5 / 37.8 USD against 9.5 / 15.7) - in M1 ATRs at the decision 10.3 /
  11.2 against 4.9 / 5.0;
- **what differs:** the leads go less against the trade after the fill at a similar run our way. For M5 it comes with
  twice the room against the M1 noise; for the H&S it does not (6.1 / 6.3 M1 ATRs against 5.2 / 5.6), and across all
  trades the wider-room half loses the MFE as much as the MAE (MAE 0.59 / 0.62 against 0.74 / 0.76, but MFE 0.55 /
  0.46 against 0.76 / 0.86) - so the room alone is not what the leads have; the setups themselves hold better (an H&S
  already has a higher low - its right shoulder - before B adds another; an M5 pattern is a slower structure);
- also seen: the turn rarely runs (P2 MFE 0.32 R, 2 R reached on 0 - 3 %); the base runs the most (MFE >= 1 R on 0.50 /
  0.48) but its exits do not keep it.

**LEAD (one setting): B2 traded only for the H&S family (any TF) and for M5 entries (any family);** every other rule
as B2. Written from the paths above. Its test on P1 / P2 is NOT independent: the two leads were picked from these same
parts (108 cells); only the exam can test it.
Written at 15:09 UTC.

### P3 - two oddities found by the second computation, and the change written before computing with it

1. **Stale fills on Sunday evenings (a data gap).** The tick files exist Monday - Friday only (143 files in 2025-10-01
   .. 2026-04-17, no Sunday), but the M1 bars hold the Sunday-evening session (1,903 bars, 22:00 - 23:59 UTC). A pattern
   decided on a Sunday evening was filled at "the first tick at / after the decision" - Monday 00:00 UTC, up to 6,840 s
   (1 h 54 min) late; when its time limit had already passed, it exited on its own fill tick. 9 - 11 trades a variant in
   P2 (A 11, B1 9, B2 10) and in P3 (B2 10, L 4, LEAD 3, ST / Xa / Xb / Xab 10). `verify_p3.py` flagged two of them (the
   time tick). **The change (written now, before computing with it):** a candidate whose first tick comes more than 60
   seconds after its entry decision is not taken - there was no price at the decision in the data. It applies to every
   P3 setting, B2 included, so P3's B2 differs from P2's by those trades; both are reported.
2. **A reported time stored rounded.** `t_be` (the break-even tick) is a tick time in ns in a column that also holds
   "none", so pandas stored it as a float: about 256 ns of rounding at 1.76e18 (bar closes are multiples of 2048 ns and
   survive; the trades themselves are not affected). `verify_p3.py` flagged 10 break-even ticks. **The fix:** `t_be`
   and `t_struct` stored as integers with a missing value (Int64).

### P3 - 1. What I did (files in `research/2026-10-18-moments/agents/dev/`)

| File | What it is |
|---|---|
| `p3_trades.py` | `invalidation`, `close_exit_time`, `trail_schedule`, `simulate3` (the moving stop; no trade without a tick within 60 s of the decision), `m5_turned`, `candidates3` (B2 + L / ST / LEAD), `one_trade3`, `run_stream3` (ns times as Int64), `metrics_table`; writes `p3_trades_all.parquet`, `p3_metrics_all.csv`, `out_p3_trades.txt`. B2 in this engine reproduced P2's B2 exactly (2,800 of 2,800 rows) before the stale-fill change. |
| `test_p3_trades.py` | 16 hand-worked tests. |
| `p3_paths.py` / `test_p3_paths.py` | The leads' paths (MAE / MFE and their minutes); 3 tests. |
| `verify_p3.py` / `test_verify_p3.py` | The second computation (imports none of p2_trades / p3_trades / patterns / sweep_detector; its own bars, `foundation.atr`, `fingerprint.zigzag`); 4 tests. |
| `plant_bugs_p3.py`, `plant_bugs_verify_p3.py` | 34 and 12 planted bugs. |
| `lookahead_p3.py` | The look-ahead check of the new settings. |
| `losers_p2.py` (now also P3), `p2_splits.py` (now any file) | `charts/p3_losers_ST.html`, `out_p3_splits.txt`. |
| `test_p2_trades.py` | + the measurer's missed bug: `test_an_m5_trade_is_held_60_m5_bars` (21 tests). |

### P3 - 2. The tests (run at 15:25 UTC by `date -u`; every file)

`test_p3_trades.py` **16 passed in 1.50s**, `test_p3_paths.py` **3 passed in 1.39s**, `test_verify_p3.py` **4 passed in 1.39s**, `test_p2_trades.py`
**21 passed in 1.69s**, `test_losers_p2.py` **2 passed in 1.91s**; the earlier files 29 + 31 + 7 + 5 + 4 passed. What they check, by hand:
- the invalidation (the right shoulder / the 2nd low / the higher low / the base's far edge); the close past a price
  (at the price is not past; the bar before the entry not read; a bar closing at the limit read); the trailing values
  (the last confirmed trough - the buffer; a sell's peak + the buffer);
- `simulate3` without a trail equals P2's `simulate` on four hand cases; break-even at +1 risk (100.27 after 102.6),
  exactly +1 risk with binary prices; a +1 risk only after the stop reports no break-even; the trailing steps (a step
  before break-even ignored - it would have stopped a tick; below break-even ignored; up to 101.5; never back; a step
  at a tick's time applies to that tick); a sell's trail; the close exit's name and the stop first on one tick; a fill
  61 s after the decision refused, 60 s taken; a 1.76e18 + 64 ns break-even time kept exact (Int64);
- `m5_turned` (a higher low / a lower high confirmed by the bar); `candidates3` (B2's fields; L refuses a close exactly
  one height past the trigger, keeps 2.3; ST with the M5 turned / with an M5 pattern / not for an M5 entry's M1
  pattern / other families untouched; LEAD keeps the H&S on M1 and any M5, drops a W on M1); `one_trade3`'s four exit
  modes (incl. a confirmed trough above every close: the structure exits, the trail mode does not) and an M5 trade held
  300 minutes; the exit counts;
- the paths (a buy's MFE 6 at minute 6 with the tick at / after the limit; a sell on the ask; never against; no tick);
- `verify_p3`: its exit counts; a trailing trade re-derived (a wrong break-even tick, an exit after the moving stop was
  crossed, the stop / trail name, a later +1 risk after a stop, a step before break-even); a stale fill; a close exit's
  tick; its own bars (the first close, at the limit, before the entry; the invalidation price and time; the trailing
  values).

### P3 - 3. The planted bugs

`plant_bugs_p3.py` **34 of 34 CAUGHT** (four gaps closed by tests first: a step before break-even that would have
stopped a tick, a step applying one tick late, a close exactly at the measured move, a structure exit in trail mode);
`plant_bugs_verify_p3.py` **12 of 12 CAUGHT** (four gaps closed first); `plant_bugs_p2.py` gains the measurer's missed
bug ("M5 held 60 minutes, not 60 bars").

### P3 - 4. The no-look-ahead check

`lookahead_p3.py`, 100 seeded catches a setting, a window of M1 around each, every M1 bar and tick after the exit
replaced: **L 35 / 35, Xa 50 / 50, Xb 63 / 63, Xab 60 / 60, ST 51 / 51 equal** (the entry, stop, risk, exit reason /
tick / price, USD, the break-even time, the stop level at the exit); power: everything from the entry decision replaced
changed every one. **It FAILED first** (Xb 34 / 54, Xab 41 / 54): the break-even time was searched over the whole
window, so a trade stopped out earlier could report a break-even tick from after its exit - the trades were equal, the
reported reading read the future. Fixed (no break-even time after the exit), tested, planted, PASSED.

### P3 - 5. The numbers checked by a second program

`verify_p3.py` (`out_verify_p3.txt`): **1,008 of 1,008** metric values agree (56 setting x part x cost rows x 18);
**140 of 140** trades re-derived (20 a setting) from the raw ticks and its own bars agree - the fill (within 60 s),
every tick against the stop level as it stood, the break-even tick, the exit's tick / price / name, the USD and R, and
from its own M1 / M5 bars with `fingerprint.zigzag`: the structure-exit times, the invalidation prices and exit times,
every trailing value; **0** entries before a previous exit in 28 streams (16,092 trades). PASSED. Its first run found
the two oddities above (the Sunday-evening stale fills, the float-rounded break-even time) and imported the measurer's
own `precursors/verify_p2.py` by its name - it now asserts it imports mine.

### P3 - 6. The result (news cost 0; one position at a time; `out_p3_trades.txt`)

| | B2 P1 | B2 P2 | L P1 | L P2 | Xa P1 | Xa P2 | Xb P1 | Xb P2 | Xab P1 | Xab P2 | ST P1 | ST P2 | LEAD P1 | LEAD P2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| trades (a weekday) | 348 (5.4) | 342 (5.2) | 276 (4.3) | 258 (3.9) | 305 (4.8) | 313 (4.7) | 315 (4.9) | 321 (4.9) | 316 (4.9) | 321 (4.9) | 343 (5.4) | 330 (5.0) | 114 (1.8) | 121 (1.8) |
| win % | 38.5 | 38.9 | 37.7 | 39.5 | 42.3 | 43.8 | 43.8 | 45.2 | 43.4 | 44.5 | 38.5 | 39.1 | 35.1 | 41.3 |
| R | -0.025 | -0.009 | -0.048 | +0.007 | -0.037 | -0.033 | -0.037 | -0.035 | -0.037 | -0.037 | -0.024 | -0.008 | -0.047 | +0.078 |
| 95 % range | -0.111..+0.061 | -0.097..+0.080 | -0.146..+0.050 | -0.098..+0.111 | -0.142..+0.067 | -0.139..+0.072 | -0.136..+0.061 | -0.128..+0.058 | -0.134..+0.061 | -0.130..+0.055 | -0.111..+0.062 | -0.099..+0.082 | -0.191..+0.097 | -0.079..+0.235 |
| USD | -61.95 | +95.86 | -53.36 | +155.83 | -91.74 | +81.38 | -77.71 | -345.23 | -78.62 | -323.22 | -55.73 | +138.47 | -121.05 | +281.47 |
| max DD USD | 299.51 | 433.16 | 331.71 | 296.06 | 402.92 | 434.06 | 382.59 | 711.39 | 373.25 | 710.26 | 298.61 | 369.60 | 306.67 | 285.78 |
| worst USD | -35.60 | -54.21 | -35.60 | -52.63 | -38.63 | -71.81 | -38.63 | -271.88 | -38.63 | -269.81 | -35.60 | -54.21 | -35.60 | -54.21 |
| losing streak | 9 (-39.21) | 11 (-125.53) | 11 (-54.91) | 9 (-87.01) | 9 (-51.67) | 10 (-130.17) | 9 (-52.57) | 10 (-123.98) | 9 (-51.67) | 10 (-123.98) | 9 (-39.21) | 10 (-55.11) | 7 (-85.48) | 8 (-146.09) |
| exits stop/trail/target/structure/invalid/time/break | 28/0/8/233/0/69/10 | 24/0/19/217/0/66/16 | 28/0/8/186/0/49/5 | 17/0/16/168/0/46/11 | 70/0/12/0/30/183/10 | 73/0/20/0/24/173/23 | 91/41/11/0/0/162/10 | 87/46/20/0/0/147/21 | 68/41/11/0/31/155/10 | 67/46/20/0/25/142/21 | 28/0/8/229/0/69/9 | 24/0/19/208/0/63/16 | 9/0/2/73/0/24/6 | 12/0/6/61/0/33/9 |

- **B2 here = P2's B2 without its 10 stale Sunday-evening fills:** -0.025 / -0.009 (P2's: -0.026 / -0.014).
- **The smaller part's R:** B2 -0.025; L -0.048; Xa -0.037; Xb -0.037; Xab -0.037; **ST -0.024**; LEAD -0.047. With +2 USD
  news slippage: B2 -0.028, ST -0.027. **No change reaches the goal or is positive in both parts; ST equals B2 within
  0.001.** Settings tried: 6 (+ B2).
- **Why the filters did not help as streams (L, LEAD), split by what was there:** inside B2's own stream the trades L
  refuses ARE worse in both parts (the late ones -0.059 / -0.049 R, the rest -0.012 / +0.012) - but run as a stream, L
  frees the one position for other candidates, and those replacement trades were worse in P1. The same for LEAD: the
  leads were +0.047 / +0.149 (H&S) and +0.066 / +0.117 (M5) inside B2's stream, but traded alone they take other trades
  (the ones B2 had skipped while busy) and P1 turns negative (-0.047). A filter's own effect and the stream's
  replacement effect come together; the cells of P2's splits were partly a product of which trades B2's stream took.
- **The exits (Xa / Xb / Xab), on the same entries as B2:** they win more often (0.43 - 0.45 against 0.36 - 0.40) but
  the R moves +0.02 - 0.03 in P1 and -0.015 - -0.04 in P2 - not steady. Without B2's structure close the losers run to
  the full stop more often (Xb: 87 - 91 stops against 24 - 28) - and on the crash days that stop can be 270 USD away.
- **The turn with the M5 agreeing (ST):** it kept 44 of B2's 68 turns; they still lose (-0.110 / -0.262 R against B2's
  turns -0.142 / -0.205).
- **The splits of B2 / ST** (`out_p3_splits.txt`, 72 cells): positive in both parts with >= 20 trades - M5 entries
  (+0.066 / +0.128; ST +0.066 / +0.117), the big patterns (+0.075 / +0.031), the H&S family in B2 (+0.047 / +0.149),
  ST's sells (+0.032 / +0.010), ST in Asia (+0.002 / +0.046). The W / M family (70 % of the trades) stays near 0 (-0.033 /
  +0.019) and decides the total.

**The measurer's oddity (the -271.88 USD trade of Xb / Xab):** it follows the written rules - an M5 M ("the 2nd high
swept the 1st") decided 2026-02-02 12:45 Thai: H1 4694.09, T 4603.82, H2 4713.41, height 109.59 <= 4 x M5 ATR 27.63 =
110.51 (just inside the cap), at the previous day's low 4682.08 by a sweep; B confirmed 8 M5 bars later after a pullback
of more than 1 ATR (the pullback high 4573.66), the confirming close 4446.38 - 157.44 USD past the trigger; the stop the
pattern's own (4718.94) -> risk 271.57. B2 did not hold it (its position was busy then); Xb / Xab, without the structure
close, held it to the stop. **L refuses it** (157.44 >= the height 109.59) - L is meant to block exactly such entries,
but L measures the entry against the pattern's height, not the size of the risk, so it does not cap the risk (L's
largest is 190.29). Trades with a risk above 50 / 100 USD (news cost 0, both parts): B2 32 (4.6 %, +31 of +34 USD) / 6
(0.9 %, -173); L 20 (-7 of +102) / 4 (+17); Xa 32 (+157 of -10) / 6 (-61); Xb 33 (-263 of -423) / 7 (-345); Xab 33 (-237
of -402) / 7 (-343); ST 30 (+29 of +83) / 6 (-173); LEAD 25 (10.6 %, -19 of +160) / 7 (-115). Xb's and Xab's losses are
mostly those few trades.

**The losers by reason (ST, the best by the smaller part, as written)** - `charts/p3_losers_ST.html`, one drawn per
reason; the shares of the part's losers P1 / P2: wrong way 0.43 / 0.46, no run 0.50 / 0.41, ran later 0.08 / 0.12 - the
other TF (with / against / mixed) alike across them. Winners +0.78 R, losers -0.53 R (P1).

### P3 - 7. Questions and what I would do next

1. **The one-position stream mixes a filter's effect with its replacement trades.** Should a filter be judged on the
   same candidates (as "the trades L refuses: -0.059 / -0.049 against -0.012 / +0.012") and the stream only at the end?
   Or should the stream pick by a reading known at the decision when two candidates compete (now: the earlier one)?
2. **The risk size:** a cap on the risk (e.g. in H1 ATRs) is not a rule yet; the 270-USD trades come from B entries
   long after the pattern on the crash days. Write one?
3. **The W / M family is 70 % of the trades and sits at 0.** Split it further (the swept second low against equal lows,
   the level kind, the session) before any new exit work?
4. **The turn still loses with the M5 agreeing.** Its paths: it rarely runs (2 R on 0 - 3 %). Change it again (e.g. the
   turn only after the sweep closed back inside the zone on the same bar) or set it aside for now?

## Task P4 - B2 only in the owner's windows (the coordinator's go-ahead read at 15:25 UTC; these rules written at the clock time below)

The owner (22:18 Thai): "trade only the windows I gave; outside them, the lowest priority - unless the setup is really
clean and clear." The measurer's split of P2's B2 trades: Asia 07-09 Thai +0.092 / +0.203, London 13-14 Thai +0.076 /
+0.074, the two together +0.087 / +0.161, the NY open + 2 h -0.072 / -0.059.

### Written before computing (P4): the rules

- **The windows, by the entry decision time** (B2's confirming close, `t_entry`):
  - **Asia:** 07:00 - 09:00 Thai clock (UTC+7, no summer time) = 00:00 - 02:00 UTC;
  - **London:** 13:00 - 14:00 Thai clock = 06:00 - 07:00 UTC (the owner's Thai-clock hour, not London's clock);
  - **New York:** the cash open 09:30 New York time + 2 hours = 09:30 - 11:30 NY (summer / winter time by the date;
    20:30 - 22:30 Thai in US summer, 21:30 - 23:30 in winter);
  - each window includes its start and excludes its end.
- **W - the core rule (one setting):** B2 exactly as in P3 (the P3 engine with the 60-s fill rule), with candidates
  only when `t_entry` is inside a window; outside: no trade. One position at a time across the three windows (one
  stream); a trade entered in a window runs to its own exit.
- **WL - an assumption, reported separately:** the same with London widened to 12:30 - 14:30 Thai ("plus or minus a
  little if it is running" - "a little" is not defined; 30 minutes is my assumption).
- **The report:** W and WL per part, and W's trades split per window: trades a weekday, win %, R with its 95 % range,
  USD, max DD, worst trade, losing streak, the exits; the second computation (`verify_p3.py` on W / WL's files, with its
  own check that every entry is inside a window) and 20 trades a setting re-derived from the raw ticks; the losers by
  reason, one drawn per reason per window (W).
- **The NY window:** first measured from what was there (the paths MAE / MFE, the family, the level kind, the M5 and M15
  structure at the entry, the news minutes inside the window, the minute after the open), each per part; then ONE change
  to its conditions written here before it is run (the window kept), tested on P1 / P2 as setting WN (W with the NY
  change).
- **Freeze:** a setting with >= +0.15 R in both parts and at least 30 trades in each part is frozen (its exact
  specification here, the exam command given, not run).
Written at 15:30 UTC.

### P4 - the NY window measured, and the change written before it is run

`p4_ny.py` (`out_p4_ny.txt`, tests `test_p4_ny.py` 2 passed), W's 49 / 49 NY trades against Asia / London:
- the paths: NY's trades run as far (MFE 0.68 / 0.72 R, +1 R on 0.31 / 0.37 - Asia 0.65 / 0.61 and 0.34 / 0.32), with
  larger risks (17.8 / 26.6 USD against Asia 11.7 / 24.1) and taller patterns;
- the minutes after the 09:30 open: 0 - 30 -0.003 / -0.197 (20 / 20), **30 - 60 (10:00 - 10:30 NY, right after the
  10:00 data minute) -0.298 / -0.208 (12 / 13)**, 60 - 120 -0.046 / +0.213 (17 / 16) - the only bucket negative in both;
- not steady between the parts: the M5 structure (against +0.065 / +0.098 but with -0.188 / -0.012), the M15
  structure, a release in the hour before (-0.165 / -0.069 against -0.047 / -0.063), a release inside the trade, M1 /
  M5, the side; the turn family loses in NY too (-0.175 / -0.390, 7 / 7).

**WN (one setting): W with no NY entry decision from 10:00 to 10:30 New York time** (the half hour after the 10:00 NY
data minute); the NY window kept otherwise (09:30 - 10:00 and 10:30 - 11:30), Asia and London as W. Chosen after ~25
NY cells, so a lead; P1 / P2 cannot test it independently.
Written at 15:37 UTC.

### P4 - the report

**1. What I did:** `p4_trades.py` (`window_of`, `in_windows`, `ny_after_ten` / `no_ny_ten` for WN, `SmallTicks` - a
cache of the last 4 days, since all the days at once ran out of memory -, `run`, `metrics_by_window`), `test_p4_trades.py`
(6), `plant_bugs_p4.py`; `verify_p4.py` (its own windows and US summer-time rule, verify_p3's re-derivation) with
`test_verify_p4.py` (3) and `plant_bugs_verify_p4.py`; `p4_ny.py` (`rel_struct`, `news_flags`) with `test_p4_ny.py` (2);
`losers_p2.py` now draws one window's losers; pages `charts/p4_Asia_losers_W.html`, `p4_London_losers_W.html`,
`p4_NY_losers_W.html`.

**2. Tests:** `test_p4_trades.py` 6 passed (Asia / London on the Thai clock with their edges, +-30 min for London; New York
in winter 14:30 - 16:30 UTC and summer 13:30 - 15:30 UTC with the 8 March switch; the candidates kept and named; the
cache keeps the day and the next as before and at most 4; WN skips 10:00 - 10:30 NY in both seasons and only NY's;
the metrics per window); `test_verify_p4.py` 3 passed (its own summer-time rule: 2025 9 Mar - 2 Nov, 2026 8 Mar - 1 Nov;
its windows; its NY minute); `test_p4_ny.py` 2 passed (the structure relative to the trade; a release 60 min before is
in, 61 out, one at the limit is not inside).

**3. Planted bugs:** `plant_bugs_p4.py` **13 of 13 CAUGHT** (the window edges, the Thai clock as UTC, London on one side
or on London's clock, New York without summer time / to 10:30 / from 09:00, every candidate kept, the windows not
split, WN's edges and WN filtering nothing; one first bug - WN filtering Asia / London too - was equivalent, since 10:00
- 10:30 NY never falls in them, and was replaced); `plant_bugs_verify_p4.py` **7 of 7 CAUGHT**.

**4. Look-ahead:** the window functions read only the entry decision's time (the tests show it); the trades are P3's
engine, whose look-ahead check passed (L / Xa / Xb / Xab / ST 35 - 63 of 35 - 63 equal).

**5. The second computation:** `verify_p4.py` - every entry decision in its window by its own clock **2,776 of 2,776**;
WN's entries at 10:00 - 10:30 NY **0**; the metrics per setting x part x cost x window **1,728 of 1,728**; **60 of 60**
trades (20 a setting) re-derived from the raw ticks and its own bars; **0** entries before a previous exit (12
streams). PASSED.

**6. The result (news cost 0; W = the core rule; R with its 95 % range):**

| W | P1 trades (a weekday) | P1 R | P1 range | P2 trades | P2 R | P2 range | win % P1 / P2 | USD P1 / P2 | DD P1 / P2 | worst P1 / P2 | streak P1 / P2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 115 (1.80) | -0.024 | -0.172..+0.125 | 109 (1.65) | +0.036 | -0.113..+0.185 | 39.1 / 41.3 | -97.37 / +86.36 | 193.02 / 240.25 | -35.60 / -135.81 | 9 (-65.52) / 6 (-103.03) |
| Asia | 41 (0.64) | +0.074 | -0.210..+0.357 | 38 (0.58) | +0.182 | -0.081..+0.445 | 43.9 / 42.1 | -15.08 / +259.06 | 83.48 / 49.82 | -35.60 / -18.97 | 4 / 7 |
| London | 25 (0.39) | -0.052 | -0.402..+0.297 | 22 (0.33) | +0.012 | -0.279..+0.304 | 28.0 / 45.5 | -18.43 / -102.48 | 72.36 / 151.91 | -34.48 / -135.81 | 5 / 3 |
| NY | 49 (0.77) | -0.090 | -0.278..+0.097 | 49 (0.74) | -0.066 | -0.291..+0.159 | 40.8 / 38.8 | -63.86 / -70.22 | 110.19 / 252.04 | -22.08 / -52.50 | 9 / 5 |

- Exits (stop / target / structure / time / break): W all P1 8 / 3 / 78 / 25 / 1, P2 6 / 6 / 72 / 25 / 0.
- **WL** (London 12:30 - 14:30 Thai, my assumption): all -0.046 / +0.062 (136 / 132 trades); its London -0.105 / +0.099
  (46 / 45).
- **WN** (W without NY entries 10:00 - 10:30 NY): **all +0.004 / +0.070** (104 / 98 trades, 1.6 / 1.5 a weekday; ranges
  -0.157..+0.165 / -0.088..+0.229; USD -40.33 / +157.52; DD 159.50 / 182.23; worst -35.60 / -135.81); its NY -0.034 /
  -0.007 (38 / 38). With +2 USD news slippage +0.004 / +0.070.
- **The smaller part's R:** W -0.024, WL -0.046, **WN +0.004**. **Nothing reaches +0.15 in both parts: no rule is
  frozen.** Asia alone is positive in both (+0.074 / +0.182, 41 / 38 trades) but below +0.15 in P1.
- **Why my London differs from the measurer's split (+0.076 / +0.074 from P2's B2 trades):** in P2's stream the
  position was often busy with a trade from outside the windows; in W only the windows' candidates compete, so W takes
  window trades B2 had skipped - the same stream effect as P3's L and LEAD (and the 10 stale Sunday fills are gone).
- **The losers by reason, per window** (W; wrong way / no run / ran later, x the other TF): Asia 45 losers, London 30,
  NY 59 - one drawn per reason in each page above.
Written at 15:44 UTC.

## Task P5 - the owner's whole pattern set on the trade's swing scale (rules written at the clock time below)

The owner marked about 11 formations on 2026-10-19 (M / W, a triple top whose last top swept the earlier ones, a
descending channel broken, a V then a failed retest, the NY-open fake leg, a base at the bottom); "that's it - and
there are triple tops and channel breaks too". They live on swings of about the trade's size (10+ USD legs), not on the
2 x M1-ATR swings of P / P1 - P4.

### Written before computing (P5): the rules

- **The scale.** At each M1 bar: H = the ATR(14) of the last H1 bar complete by that M1 bar's close. The main swing =
  0.6 x H (P1's median H1 ATR is 16.3 USD -> about 10 USD, the owner's trade; P2's 28.1 -> about 17); the inner swing =
  0.3 x H. One causal ZigZag on M1 with the inner swing (`patterns.zigzag(h, lo, H, 0.3)`); every formation is built
  from its pivots and must be at least one main swing tall. EQ = 0.25 x the main swing (equal tops / lows), SW = 0.5 x
  the main swing (how far a later top / low may sweep past the earlier ones). A formation spans at most 300 M1 bars.
  The breakout = the first M1 close beyond the trigger after the formation's last point (buy side; sells mirrored).
- **On 2026-10-19 only (the shape check):** that day is after the data end and outside every part; the bars before
  2026-10-18 are the exam's and are not read (the live file is read with a filter from 2026-10-18 00:00 UTC). With no
  earlier H1 bars, H on that day = the mean true range of that day's H1 bars completed so far (the first one from the
  first hour). Nothing on that day is used for any outcome or any setting.
- **The set** (buy side; T = trough, P = peak, the last ones of the structure; a buy's height = its top - its bottom):
  1. **Double bottom:** T_a, P, T_b; T_b within [T_a - SW, T_a + EQ] (a 2nd low that sweeps the 1st by up to SW is
     "swept"); height P - min(T) >= main; trigger P.
  2. **Triple bottom:** T1, P1, T2, P2, T3; T2 within [T1 - SW, T1 + EQ]; T3 within [min(T1, T2) - SW, max(T1, T2) +
     EQ]; height max(P1, P2) - min(T) >= main; trigger P2 (the last high between).
  3. **Inverse H&S:** as P's rules on these pivots: the head below both shoulders by >= EQ; the shoulders within 0.5 x
     the height of each other; the neckline's points within 0.5 x the height; height >= main; trigger the neckline at d.
  4. **Channel break:** the last four confirmed pivots (two peaks, two troughs); the upper line through the peaks, the
     lower through the troughs, parallel (|slope_u - slope_l| <= 0.5 x the larger |slope|); the width at the last pivot
     >= the inner swing; at least 30 bars from the first pivot; the first close above the upper line (buy) or below the
     lower line (sell) after the last pivot.
  5. **Break and retest:** a confirmed peak Pk that rose at least one main swing from the trough before it; a later
     close above Pk (the break); then the last trough T, after the break, within [Pk - EQ, Pk + EQ] (held at the broken
     level from above); trigger = the highest high from the break to T; height trigger - T >= the inner swing.
  6. **The fake first leg at an open** (07:00 Thai, 13:00 Thai, 09:30 NY): p0 = the close before the open; the first
     move of an inner swing from p0 within the first 15 minutes sets the fake side (both in one bar: the larger); the
     trade is the other side: the first close beyond p0 the other way within 60 minutes of the open; extreme = the fake
     leg's extreme; trigger p0.
  7. **Base / range break:** the longest run of 20 .. 240 bars ending at d - 1 within one main swing (high - low); the
     breakout close above it (buy) or below it (sell).
  8. **A-B-C-D-E triangle:** the last five confirmed pivots alternate with A, C, E one kind (descending highs for peaks
     / ascending lows for troughs) and B, D the other (the opposite); the line through A and C and the line through B
     and D converge; |A - B| >= main; the first close beyond either line after E - the side by the break.
- **Pictures in formation (the owner's scenario planning), reported at the decision only:** two tops - the last
  confirmed peak P_a, the confirmed trough T after it, and the next peak P_b (confirmed, or the running one) within
  [P_a - EQ, P_a + SW]; max(P) - T >= main; the close now below P_b by >= EQ and above T; no close above max(P) since
  P_b. Reported once per P_b, with two scenarios (each a trigger, a stop, a target):
  - **A, the top holds:** sell on a close below the lowest low since P_b; the stop above the highest top + 0.2 x the
    inner swing; the target the trigger minus max(P) - T;
  - **B, the breakout:** buy on a close above max(P); the stop the lowest low since P_b - 0.2 x the inner swing; the
    target the trigger plus max(P) - T.
  Two bottoms mirrored. Which one the chart revealed (the first trigger closed beyond) is drawn, not traded.
- **Not before the owner's confirmation:** no trade, no R, no count of outcomes - including the "planning ahead against
  completed patterns" measurement, which needs outcomes.
- **The checkpoint:** the detector with its tests, planted bugs and the look-ahead check; the shape check on 2026-10-19
  (found / missed / extra against the owner's 11, the day drawn); 12 learning-part catches drawn by rule: families 1 - 8
  in order, each the catch inside the owner's windows nearest the middle of P1 (odd slots) or P2 (even slots); slots 9
  - 10 a picture in formation nearest the middle of P1 / P2; slots 11 - 12 a double / triple top-bottom from the other
  part than its first slot.
Written at 15:48 UTC.

### P5 - the shape check's matching rule (written before the detector runs on 2026-10-19)

The owner's 11 formations (Thai times; the measurer's table) count as **found** when a catch of a matching family
breaks out (its decision) inside the formation's time span or within 30 minutes after it: #1 M -> double top; #2 the
wide W -> double bottom; #3 a small M, then a W -> double top or double bottom; #4 the M at about 4184.7 -> double top;
#5 W / higher low -> double bottom, triple bottom or break up / retest; #6 the triple top -> triple top; #7 the
descending channel broken at 17:20 -> channel break; #8 the V, then the failed retest at 4177 -> break down, retest;
#9 a small W, then a lower high -> double bottom or break down, retest; #10 the NY-open fake leg up, then the drop ->
open: fake up, then down; #11 the base / W at the bottom -> base break or double bottom. Spans: #2 05:00 - 08:26, #8
17:46 - 18:30, #9 19:03 - 19:20, #10 20:30 - 21:30, #11 20:47 - 22:00; the others as in the table. A catch inside no
span is **extra**. The pictures in formation are listed with their scenarios; the owner's example (two tops 4186.2 /
4186.51, the low 4182.26 at 14:03) is looked for by its times.
Written at 15:55 UTC.

### P5 - the split with the second developer (read at 16:04 UTC), and where P5 stands

The coordinator's message (read at 16:04 UTC; DEV_PROMPT.md "The split with the second developer", 23:05 Thai): the
trade-size swings and the structure per TF are dev2's V3-1; in P5 I import dev2's swing module read-only and build no
second one; the scenario planning (P5 item 5) moved to dev2's V3-3. **`agents/dev2/` does not exist at 16:05 UTC, so P5
waits for it.**

**Done before the message (the rules above, written at 15:48 / 15:55 UTC):**
- `p5_patterns.py`: the pattern set (double / triple, H&S, break and retest, channel, triangle, base, the fake first leg
  at an open) as functions of a swing sequence `seq` (`patterns.structure` at bar d: (bar, price, kind, provisional)) and
  the sizes main / inner. Its own swing source is one line, `Chart.__init__`: `patterns.zigzag(h, lo, H, 0.3)` - the
  existing P ZigZag at 0.3 x the H1 ATR (no new ZigZag code). This line is what dev2's module replaces.
- `test_p5_patterns.py` **14 passed**; `plant_bugs_p5.py` **31 of 31 CAUGHT** (five gaps closed by tests first: the head
  less than EQ below the shoulders, a level that rose less than a main swing, a channel of 20 bars, the breakout bar's
  own width, a close at the box top; one first bug - "19 bars make a base" - was equivalent, since the fast test r20[d -
  1] <= the width means the 20 bars ending at d - 1 fit, and was replaced by "the shortest run" and "a close at the top
  breaks").
- The learning scan (`out_p5_patterns.txt`, counts only, no outcome): 12,192 catches on 155 days, 2,805 inside the
  owner's windows; **base breaks 7,862 (64 %)** - the base rule is too loose as written (a run of 20 bars within one main
  swing is common on M1); on 2026-10-19 34 of 55.
- The shape check on 2026-10-19 (`out_p5_day.txt`; the day's H 11.9 - 13.5 USD -> main 7.2 - 8.1, inner 3.6 - 4.0):
  **found 4 of 11** (#1 M - double top 07:16; #2 the wide W - double bottom 08:34; #7 the channel - channel breaks 15:12 /
  15:51 / 17:42; #10 the NY-open fake leg - 20:35); **missed 7**; 55 catches, 8 extra. Why each was missed, read from
  the pivots (no rule changed for it):
  - #3: the W at 09:32 / 09:51 (4169.13 / 4170.68, the peak 4178.32 between) IS caught as a double bottom - at 10:06,
    34 minutes after the span's end (the rule's limit is 30), so it is counted extra;
  - #4: the M 4184.68 (11:57) / 4184.49 (12:10) over the trough 4178.86 is 5.82 tall < the main swing 7.47;
  - #5: the W 13:14 / 13:32 (4174.89 / 4171.09, the peak 4180.00 between) sweeps 3.80 past the first low > SW 3.72;
    the owner's W (4174 at 12:29 / 4171 at 13:32, the high 4186.18 between) has seven inner pivots between its lows, and the set
    reads consecutive pivots only;
  - #6: the triple top 12:57 / 14:00 / 14:33 has nine inner pivots between its first and last top (the owner's 2nd top 4186.51 at
    13:58 is not a pivot; the inner peak is 4189.19 at 14:00);
  - #8: the failed retest at 4177.06 (18:16) is 5.0 above the nearest broken trough (4172.06, 15:37) > EQ 1.83;
  - #9: the higher low 4163.79 (19:20) is 5.1 above 4158.69 (19:03): no double bottom; no broken level near 4170;
  - #11: the base at the bottom has not broken by the data's end (22:03; the highest close after 21:54 is 4147.51).
  The pattern: the inner swing 0.3 x H (about 3.7 USD) splits the owner's 10-USD legs into many pivots, so formations
  built from consecutive pivots miss them - the swings of the trade's size are the missing piece, which is dev2's V3-1.
- The pictures in formation (`forming_tops`, `forming_at`; 2 tests, 5 planted bugs) were written before the message;
  they are item 5, now dev2's - I stop them here and do not develop them further.

**Waiting for dev2's swing module (not started, so as not to redo them on a scale that will change):** the
look-ahead check of P5, the day drawn, the 12 learning-part catches drawn. **What I need from dev2, through the
measurer:** the module's path and, per M1 bar, causal swing pivots in the shape of `patterns.zigzag`'s output (pivot
bar, price, kind +1 / -1, the bar that confirmed it) - or a function giving the swings known at the close of bar d -
plus the size value its rule uses (to set the formations' main / EQ / SW).
Written at 16:06 UTC.

## Checkpoint P5a - the filters on B2's fixed candidate set, a risk cap, a tighter base (the coordinator's answers read at 16:08 UTC; these rules written at the clock time below)

The coordinator (relaying TEAM.md): judge a filter on the same candidates first, the stream only at the end; test a
risk cap in H1 ATRs whose value is written before computing, from P1's trades' risks only; tighten the base rule before
drawing and count again; the shape check's match rule stays span + 30 min, near misses listed apart; W / M split only on
the new swings; wait for dev2's swings before the P5 look-ahead check and the drawings.

### Written before computing (P5a): the rules

- **The fixed candidate set:** B2's 1,042 candidates (`p3_trades.candidates3` with B2's setting, from
  `p_catches.parquet`), **each traded alone** with B2's exit (`one_trade3`, exit "structure", the 60-s fill rule) - no
  one-position rule, so every candidate has its own trade whatever the others do. A candidate with no tick within 60 s
  has no trade (as in the streams). Overlapping candidates (the same moment found by more than one pattern / TF) each
  count; their trades are not independent, so the 95 % ranges are narrower than they should be - the number of distinct
  entry times is reported with them.
- **The filters, as flags on that set** (each from the code that was tested, by membership: a B2 candidate is kept by a
  filter when the same candidate - t_dec, t_entry, side, tf, family, name, stop - is in `candidates3` with that filter's
  setting):
  - **L** (refuse a confirming close at / past one pattern height beyond the trigger), **LEAD** (keep only the H&S family
    and M5 entries), **ST** (keep a turn only with the M5 agreeing);
  - **CAP** (new): refuse a candidate whose risk at the decision (`risk_dec` = |the confirming close - the stop|) is
    above X x H1 ATR, the H1 ATR = the ATR(14) of the last H1 bar complete by the entry decision (`t_entry`).
    **X = the 95th percentile of risk_dec / H1 ATR over B2's P1 trades** (the P3 stream, news cost 0, 348 trades),
    rounded up to 0.05 - only their risks are read, no outcome. (Why the 95th: the cap is meant to cut the few
    outsized risks - B2 had 32 trades of 690 above 50 USD and 6 above 100 - not to reshape the set.) The value is
    written below before any result.
- **The judgement on the fixed set**, per part, news cost 0 (and +2 USD on news trades for the smaller part): for each
  filter the kept and the refused candidates' trades - n, distinct entry times, win %, R with its 95 % range, USD; and the
  same inside the owner's windows (W, `p4_trades.window_of` on t_entry).
- **Then as streams** (one position at a time, `run_stream3`): L, LEAD, ST are P3's streams (unchanged, already
  measured); CAP is run new on all hours, and W + CAP (the P4 core rule with the cap) - news costs 0 / 0.5 / 1 / 2.
- **A freeze** only for >= +0.15 R in both parts with >= 30 trades in each.
- **The tighter base (P5, family 7) - B5T:** the longest run ending at d - 1 of **at least 60 M1 bars** (one H1 bar's time:
  the scale H is the H1 bar's average range, so a base must hold at least one H1 bar) and at most 240, whose range (the
  highest high - the lowest low) is within one main swing (0.6 x H at d - 1, as before); **at one of the owner's H1
  levels**: the box overlaps a level's zone at the decision (`zones.levels_at` at t_dec with the breakout close, as Task
  P; `patterns.at_level`'s base rule: box low <= level + z and box high >= level - z, z = 0.1 x that H1 ATR); the
  breakout close beyond the box as before. Reported: the catch count on the learning parts (per part, per side, inside
  the windows, distinct boxes) against the loose rule's 7,862, and the count on 2026-10-19 (shape only). No outcome.
Written at 16:10 UTC.

**The cap's value (from P1's risks only, read at 16:10 UTC):** risk_dec / H1 ATR over B2's 348 P1 trades - median 0.663,
75th 1.003, 90th 1.590, **95th 1.863**, 99th 2.823, max 3.735 -> **X = 1.90 H1 ATR**. Written at 16:10 UTC, before any
result with it.

### P5a - stopped by the coordinator (read at 16:12 UTC = 23:12 Thai)

The owner (23:11 Thai): "should we stop and wait? Otherwise whatever is built and tested will lose anyway" - anything
built on the old micro-swing structure stands on the foundation the owner considers wrong. Stop P5a, start no new
B2-based test.

- **Finished:** the P5a rules above (written 16:10 UTC); the cap's value X = 1.90 H1 ATR from P1's 348 B2 risks only
  (16:10 UTC; risks read, no outcome).
- **Written but not tested and never run** (the step I was in when the stop came): `p5a_filters.py` (the fixed-set
  trades, the filter flags by membership, CAP, the CAP / W + CAP streams). It passes `ruff check --select F,E9,B`
  only; it has no tests, no planted bugs and no second computation, so it is not to be used as it stands.
- **Left, not started:** the fixed-set judgement of L / LEAD / ST / CAP, the CAP streams, the tighter base rule's code
  and count (B5T is written above, not coded), all their tests and checks.
- **Next, after dev2's V3-1 swings and structure reader are measured and shown to the owner:** (1) the P5 pattern set
  on those swings, with the shape check, the look-ahead check and the drawings; (2) an independent second
  implementation of the structure reading (HH / HL, LH / LL per TF) to cross-check dev2's.
Written at 16:12 UTC.
