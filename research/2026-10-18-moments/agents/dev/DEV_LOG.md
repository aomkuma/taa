# Setup OWN V2 - the developer's log

The trading-system developer's log (brief: `../DEV_PROMPT.md`). Times in UTC. Learning parts only: P1 2025-10-18 ..
2026-01-16, P2 2026-01-16 .. 2026-04-18; nothing from 2026-04-18 on is loaded, computed, plotted or printed (the code
refuses it: `learning_ticks` raises `ExamPeriodError`, the event lists end before it, the charts refuse a window that
reaches it). Every count below counts each release minute once (the coordinator's 03:47 UTC note: count events
once, not once per minute).

## Checkpoint A1 - the two-way sweep detector (2026-10-19, 03:30 - 04:15 UTC)

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

### A1 follow-up (2026-10-19 04:20 UTC): the measurer's three missed bugs

The measurer's own planted bugs missed three; tests added (`test_a_tie_takes_the_side_that_reached_leg_first` now
also has the mirror - 3 down first, then 4 up: the side is down; `test_the_pre_release_range_and_the_sweeps_through_it`
now has a first leg to exactly the pre-release high and a sweep to exactly the pre-release low: neither counts;
`test_a_return_short_of_p0_is_not_the_third_leg`: back 11 of a 12 sweep came down but is not the third leg) and the
three bugs added to `plant_bugs_a1.py` (a tie always up; swept_pre on touching the high; the third leg = back >= 0.9 x
the sweep). Results under "Task P" below.

## Task P - the chart pattern at the level (2026-10-19, from 04:20 UTC)

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

- **05:00 UTC - the sell side's names.** The first drawing named the sells by the buy names ("H&S (inverse H&S)",
  "M (W)"): `unmirror` kept the variant. My own end-to-end M test asserted "W" - the test had the bug in it. Fixed in
  the code and the test (`test_the_sell_side_names`, the M test now expects "M").
- **05:10 UTC - a height cap, first try (rejected).** Drawn catch #7 (2026-03-03 18:29 Thai) was a "sweep, lower high"
  whose only point at the level was the sweep; the trigger was 100 USD below it (risk 114 USD) - a move away from the
  level, not a pattern at it. First cap: height <= 1 x H1 ATR. On the redraw it dropped the owner's own 2026-01-09 W
  (height 15.6, H1 ATR 11.1 before the release) and kept a 60-USD crash pattern (H1 ATR 57.9): it measured the wrong
  scale.
- **05:20 UTC - the height cap used (`HEIGHT_ATR = 4`).** A pattern's height (extreme to trigger) at most 4 x its own
  TF's ATR at the decision = two ZigZag swing sizes; a larger shape is a move, seen on the next TF up. The owner's W:
  15.6 / M1 ATR 4.33 = 3.6 (kept); the inverse H&S #1: 6.93 / 1.82 = 3.8 (kept); the two far-from-the-level crash
  patterns (the "sweep, lower high" decided 2026-03-03 11:29 UTC: 103.41 / 13.95 = 7.41, and 14:32 UTC: 50.24 / 9.61 =
  5.23) dropped. In `patterns_at`, for every family.
- **05:25 UTC - the picking rule:** a slot may not reuse a decision moment (TF and time) drawn in an earlier slot (the
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
