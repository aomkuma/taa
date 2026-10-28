# TR1 round-1 exit findings on P1

Computed after `EXIT_DESIGN_P1.md` was written. All four families used the same 138 fixed entries. P2 and the exam
were still locked.

## Outcome

- FAST: +0.011 mean R, +1.56 total R, +4.32 USD at 0.01 lot, 16.21R maximum drawdown and 6/13 positive weeks.
- SWING: +0.386 mean R, +53.23 total R, +281.55 USD, 19.19R drawdown and 8/13 positive weeks.
- SPLIT: +0.265 mean R, +36.52 total R, +192.92 USD, 13.16R drawdown and 9/13 positive weeks.
- STATE: -0.032 mean R, -4.45 total R, -15.10 USD, 18.47R drawdown and 5/13 positive weeks.

All 138 paths were executable through their relevant deadline inside P1. The 95% individual-trade bootstrap
intervals remained wide and crossed zero for every family. SWING and SPLIT are both tail-driven: after removing the
best trade they retain +0.212R and +0.147R respectively, but after removing the best three they fall to -0.027R and
-0.017R. This concentration must be treated as a weakness, not hidden by the headline mean.

London supplied most of the P1 runner result: SWING/SPLIT averaged +1.102R/+0.723R there, versus +0.003R/+0.002R in
Asia and +0.058R/+0.077R in New York. No session is removed after seeing that result; all three remain frozen for
P2.

## P1 selection

SPLIT is selected for round 1. It gives up some of SWING's headline mean while retaining two thirds of every runner,
and it improved the predeclared steadiness measures: lower drawdown, more positive weeks and a shorter losing streak
(10 versus 14). It also remained above zero after removing the best trade. This selection is provisional until the
independent exit replay, mutant checks and twelve chart audits pass.

FAST, SWING and STATE remain controls in the saved comparison; they are not eligible to replace SPLIT after P2 is
opened. A P2 failure is a failed round, not permission to switch to whichever control looks best there.
