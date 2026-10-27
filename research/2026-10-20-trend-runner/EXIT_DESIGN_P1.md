# TR1 round-1 exit design

Written before computing any TR1 exit-family P1 result: 2026-10-20. Only the descriptive opportunity labels were
known. The entry population is fixed to 0.25 H, M1 and all Asia/London/New York anchors as documented in
`OPPORTUNITY_FINDINGS_P1.md`.

## Common execution rules

- One initial R is the spread-aware entry price to the fixed buffered pullback stop saved with the opportunity.
- A long is marked and stopped on bid; a short is marked and stopped on ask.
- Raw quotes retain file order, including equal timestamps.
- A gap through a stop exits at the worse executable quote. A target gap is booked at the declared target price.
- A stop has priority over any other action on the same ordered quote.
- No exit uses a future bar. A structure stop can change only when its confirming bar is available and on the first
  raw quote at or after that time.
- A structure stop can tighten but never widen. If a newly active stop is already through the current quote, that
  quote is the exit.
- Primary slippage is zero. Entry spread and exit-side spread are inherently present in bid/ask quotes.
- Maximum runner duration is eight hours from entry. The time exit uses the first executable quote at or after the
  deadline.
- A path without either a stop or a quote at/after the exit deadline inside the evaluation period is censored. It is
  retained and counted but excluded from complete-path means. This is an evaluation boundary rule, not a live-entry
  filter.

## Structure trail shared by SWING, SPLIT and activated STATE

The trail starts at the initial stop. Before graduation it watches causal M5 radius-1 pullback pivots formed after
entry: lows for a long and highs for a short. A pivot becomes actionable after its right-hand M5 bar closes. Its stop
is beyond the pivot by the larger of entry spread and 0.10 times M5 ATR(14) at confirmation.

When the executable mark first reaches +3R, the trail graduates from M5 to M15. The existing stop is retained, so
graduation cannot widen risk. M5 pivots confirmed after graduation are ignored. Only M15 pivots whose confirmation
is at or after graduation may tighten the stop. This intentionally trades some locked-in profit for fewer exits from
small pullbacks after a large move.

If +3R and a structure confirmation occur on the same timestamp, quote file order is respected: the active stop is
checked, the +3R graduation is recorded, then structure confirmations available at that timestamp are applied.

## Exit families

### FAST control

Use the initial stop, a fixed +2R target and a 60-minute maximum duration. At a quote, priority is stop, target, then
time exit. This is the deliberately short-horizon control.

### SWING

Use the common M5-to-M15 structure trail, no profit target and the eight-hour maximum duration.

### SPLIT

Use the common structure trail. Close one third at exactly +1R; keep two thirds on the SWING trail. Before the +1R
partial, a stop closes the entire position. The reported R is `1/3 * 1R + 2/3 * runner R` after the partial, otherwise
the full-position runner result. Maximum duration is eight hours.

### STATE

Begin as FAST. It may convert once to the SWING trail only when both conditions have occurred no later than 60
minutes after entry:

1. the executable mark has reached +1R; and
2. a post-entry M5 pullback pivot in the trade direction has been confirmed and its buffered stop would tighten the
   initial stop (mechanical higher-low evidence for a long or lower-high evidence for a short).

The conversion occurs on the first quote at or after both facts are available. A pre-existing +2R target is executed
before conversion if that quote crosses it; the system cannot cancel a target after observing its fill price. If the
gate is incomplete at 60 minutes, STATE takes the FAST time exit. Once converted, the +2R target and 60-minute limit
are cancelled, the qualifying structure pivot may tighten the stop immediately, and the common eight-hour trail
applies.

## Evaluation declared in advance

All four exits are run over exactly the same selected entries. Report complete and censored counts, mean/median R,
win rate, total R, 95% bootstrap interval for mean R, weekly concentration, best-trade removals, holding time, exit
reasons and session/direction splits. P1 selects at most one exit family; the complete code/rule hashes are then
frozen before enabling P2 once.
