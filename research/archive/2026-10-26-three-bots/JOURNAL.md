# The three bots' journal, week by week

The owner (2026-10-27): *"go day by day, week by week, to test the work we have done."* One account, the
three bots side by side, at most two open at once. 300 USD, the aggressive preset, real stored ticks for
fills and spread. Every week: what happened, what it cost, what was learned, what changed.

The fit window of the parameters is **2025-10-20 .. 2026-10-24** (`bots.py`), so days inside it are marked.
The owner on that: *"so it has seen the data, fine - if it has seen it and still loses, well then."*

---

## Week 1 - 19 to 27 October 2026 (7 trading days)

| day (Thai) | trades | R | USD | account |
|---|---|---|---|---|
| Mon 19 - Tue 20 | 0 | - | - | 300.00 |
| Wed 21 | 1 | +2.53 | +26.87 | 326.87 |
| Thu 22 | 2 | +6.22 | +63.90 | 390.77 |
| Fri 23 | 0 | - | - | 390.77 |
| Mon 26 | 2 | -2.01 | -29.76 | 361.01 |
| Tue 27 | 1 | -1.02 | -15.23 | **345.78** |
| **total** | **6** | **+5.73** | **+45.78** | **+15.3 %** |

### The split nobody arranged

| | trades | R | win rate |
|---|---|---|---|
| 21-23 Oct, **inside the fit window** | 3 | **+8.75** | 100 % |
| 26-27 Oct, **never seen** | 3 | **-3.02** | 0 % |

Six trades prove nothing on their own, but the direction matches what was measured before the week ran:
the same parameters gave +0.280 R on the year they were fitted on and -0.289 R on years they had not seen
(`selection_bias.py`).

### What the three losers have in common

All six trades were sells, five of them from `trend_box_down`. On 26-27 October gold rose from 4,004 to
4,026 and the bot sold into it three times, because the H1 ZigZag still read lower highs and lower lows -
a backward-looking trend read that keeps selling through the turn.

| entry (Thai) | risk USD | worst against | best in favour | result |
|---|---|---|---|---|
| 26 Oct 13:15 | 14.06 | 1.00 R | 0.29 R | -1.00 R |
| 26 Oct 20:15 | 15.59 | 1.00 R | **1.40 R** | -1.01 R |
| 27 Oct 08:25 | 15.07 | 1.01 R | 0.01 R | -1.02 R |

### The lever tested this week: break-even on the down bot

The 26 Oct 20:15 trade was +1.40 R in front and still took a full stop. `trend_box_down` is the one bot
without a move to break-even. The arithmetic on MAE/MFE suggested it would have saved 1.01 R - but MAE and
MFE do not say which came first, so the question was put through the engine instead, with
`break_even: true` on that bot alone and nothing else changed.

| | trades | R | USD |
|---|---|---|---|
| as it is (no break-even on DOWN) | 6 | **+5.73** | +45.78 |
| break-even at +0.5 R on DOWN | 7 | **+2.48** | +18.21 |

| entry (Thai) | without | with break-even |
|---|---|---|
| 21 Oct 19:25 | **+2.53** | -0.01 (BE) |
| 22 Oct 07:15 | **+1.67** | -0.04 (BE) |
| 26 Oct 20:15 | -1.01 | **-0.01** (BE) |

**Rejected.** It saves one loser and destroys two winners. The reason is in the numbers that were already
there: the two winners went 0.81 R and 0.38 R *against* the entry before they ran. A stop at break-even is
inside the noise this entry routinely sits in.

**What that says about the entry, which matters more than the lever:** a trade that normally goes 0.4-0.8 R
against before working is entered too early in its own retest, or its stop is too tight for the place it is
entered in. That is the next thing to measure - the entry's geometry, not another exit rule.

### Carried into the code

- `break_even` is now a parameter of both trend bots (`TrendBoxParams`), default unchanged: off for DOWN,
  on for UP. The lever can be re-tested on any window without touching code.
