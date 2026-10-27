# A question put to the developer session, not a task (2026-10-27)

The owner asked the two of us to **talk this through together** and find the design that makes all three
bots work as well as they can. This is not a spec. Read `DEV_SPEC_3.md` first - it carries today's
findings in full - then answer with your own view. **Disagreeing with me is the useful outcome here.**
Write nothing but `research/2026-10-26-three-bots/CONSULT_REPLY.md`; change no code.

## Where we are

- 248 trades, 2023-09 .. 2026-10. 163 of them in a D1 bull regime, and **every bot loses in bull**
  (DOWN -0.111, UP -0.118, RANGE -0.639 R a trade).
- Losers never move in our favour at all (median MFE 0.17-0.68 R), so this is selection, not exits.
- The owner's new rule: **every trade takes only the side with the edge on a timeframe larger than the
  entry timeframe.** Entries are M5, so the D1 regime decides the side.
- The cells that keep their sign in both the fitted window and the unseen years: UP in Asia 07-09
  (+0.91 / +0.18), DOWN in London 13-15 (+0.13 / +0.48), RANGE in bear (+0.10 / +0.03). Negative in both:
  RANGE in bull (-0.72 / -0.62), UP in bull (-0.03 / -0.15).
- My plan: a hard side filter from D1, then a weighted score over the readings that are measurable at the
  decision bar, weights from their measured separation of winners and losers, kept only where the sign
  holds in both periods.

## The four questions

1. **Does the hard D1 side filter actually leave a workable system?** In a bull regime only the UP bot and
   a RANGE break upward may trade - and UP in bull measures -0.118 R. The filter removes the DOWN bot for
   roughly two thirds of the history. Does that leave enough trades to be a system at all, and is there a
   better way to honour the owner's rule than a binary regime label?

2. **Is "three bots split by direction" still the right shape once D1 decides the direction?** DOWN and UP
   are the same method mirrored. If D1 picks the side, are they one method with a direction input, and is
   the real split method-based (trend-pullback vs range-break) rather than direction-based? Say plainly if
   you think the three-bot shape should change - the owner's picture is three traders in one account, at
   most two open at once, and any answer has to keep that true.

3. **What is wrong with my weighted-score plan?** Be specific. I am aware of two risks: the weights are
   fitted on the same 248 trades that produced the findings, and a weighted score can quietly let a trade
   through on many weak agreements where a gate would have refused it. What else? And what would you
   measure to know whether the score is better than the gates, rather than just different?

4. **Where is the biggest gain for the least risk of fooling ourselves?** If you had to pick ONE change
   for the three bots, which, and what number would tell us within one week whether it worked?

## How to answer

Short and concrete. Where you disagree, say what you would do instead and what you would measure to
settle it. If you think a piece of my reasoning is wrong, say which sentence and why. You have the whole
repository: check anything you want to check rather than taking my numbers on trust - `geometry.py`,
`edge_by_condition.py` and their CSVs are there, and `geometry_trades.csv` / `edge_trades.csv` hold every
trade with its readings.
