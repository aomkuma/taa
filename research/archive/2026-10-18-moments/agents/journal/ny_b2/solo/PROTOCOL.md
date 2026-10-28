# The solo exam of the NY-B2 journal - protocol (written 2026-10-23 before exam week 1)

Owner (2026-10-23): the exam is the same weekly journal run on the 26 exam weeks, but I learn, decide and change things
by myself, with no weekly discussion; the report comes at the end.

## Disclosure

Before this protocol I ran the frozen-rules read of the same weeks (CHECKLIST 65, `../out_exam.txt`) and saw its weekly
totals (base -0.276 a trade; bad stretches in late April and July; the re-test's 10 trades). That knowledge could bend
my decisions. To limit it, the decision rules below are fixed now, every decision is written in `DECISIONS.md` with the
numbers it rests on (computed only from trades before the week's end), and the frozen read stays as the "no learning"
baseline the solo result is compared with.

## Start state (the end of the learning journal, week 26)

- Piece B2 in the NY window (the bot's trades, 20:30-23:00 Thai), the realistic exit: half at +1 R, the rest's stop
  to the entry, the rest to 0.1 step before the next zone-grid line (at least 0.25 step away), out at 120 min.
- Skip rules in force: H1 vol > 1.1x its 20-day median (from journal week 16); within 10 USD of a zone line (week 14);
  10:00-10:30 New York (week 20).
- Piece re-test after a strong D1 bar (retest_week.py), both sides.
- Accounts: 100 USD at 7.5 % and 300 USD at 3 %, fresh at exam week 1; equity sizing, at least 0.01 lot.

## Each week

1. Run the week (`solo_week.py`): every trade's outcome under the state in force; realized results go to the
   append-only `ledger.csv` (later changes never rewrite earlier weeks).
2. Write the week in `DECISIONS.md`: what the market did / what we did / what a trader would have done.
3. Review (`solo_review.py`, trades before the week's end only, learning weeks included as evidence) and decide.
   Changes take effect from the next week.

## Decision rules (fixed)

- **A skip rule in force is deleted** when, counted from the week it took effect (exam weeks for the three start
  rules, since their forward record in the learning journal already counts: near-line +1.86, 10:00 NY +0.75, vol
  -1.05), the trades it would skip have made more than +1.0 R in total. Every trade a rule would skip counts.
- **A new skip rule** starts as a shadow (recorded, not applied) the week it is proposed from an observation; it is
  applied once its shadow record over at least 4 weeks has saved at least 1.0 R; at most 2 skip rules in force.
- **The exit**: the candidates (no break-even on the rest; no band; 90-min hold) are tracked every week; the exit
  switches to a candidate when it beats the current exit by at least 1.5 R over the last 8 exam weeks and is not
  worse over all the trades before the week's end.
- **A new piece** (a with-the-move or other entry the market showed and no piece traded) must pass, on data before the
  week's end only: gate 1 - its entry alone at least +0.10 R a trade in both halves of its test data; gate 2 - the
  same sign on the old years (2023-2025 bars / ticks). Then it trades from the next week.
- **A piece is stopped** when its exam-forward record falls below -3 R; it can come back only through the gates.
- Judged by the market: the realized ledger, both accounts; no profitability claim.
