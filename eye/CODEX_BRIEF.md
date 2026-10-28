# Brief for the second reader (Codex)

> **Retired, kept as a record (2026-10-28).** This brief was for the 50/50 split of the clock-sampled
> sheets, which never produced one answer (`TRIED.md` row 14), and the sheet images it refers to were
> deleted at the owner's word (recoverable from 937f75a). A new brief for Codex follows METHOD 2e once
> the owner has written it. What works now: the prompt piped on stdin to `codex exec`.

You are the second of two readers trading gold by eye. The owner's instruction, in full:

> Start from looking at price structure and finding an entry that has an edge. That is all. Any
> timeframe is fine; the principle is **enter on a timeframe, exit on that timeframe**. Trade it with your
> bare eyes.

You read **only the chart image attached to this prompt**. You have no price file, no indicator, no rule
set and no knowledge base, and you must not try to find any: the point of this exercise is what an eye can
take from the picture alone. Each sheet holds **six panels**, each a different moment of XAUUSD on M5,
about 90 bars (7.5 hours) up to the moment the panel's title names. Everything after that moment is
withheld until you have decided.

## What to produce, per panel

One block per panel, in this exact shape, and nothing else:

```
#<id> | <BUY|SELL|NONE> | entry=<price> | stop=<price> | target=<price>
structure: <one sentence - what the swings are doing, where the shelves and the origins of moves are>
why: <one sentence - why this entry has an edge, and what each of the three prices is taken from>
```

For `NONE`, write `entry=- stop=- target=-` and let `why` say what is missing.

## The rules the result is scored by

- **The entry must be a price the market can reach from where it is now.** If the level you want is already
  far behind price, that is `NONE`, and say so. A plan that never fills earns nothing and is counted.
- The entry fills if price trades through it within **2 hours** of the panel's cut-off.
- After the fill, the first of stop or target decides it. **A bar touching both counts as the stop.**
- If neither is touched within **4 hours**, the trade closes at that bar's close.
- R = the move your way divided by (entry - stop). **0.30 USD of spread** comes off every entry.
- The bar to beat is **+0.15 R a trade after costs**.

## What is worth knowing before you start

The system this replaces failed in a measured way: over its last 17 entries the direction was right 53.8 %
of the time, which is enough, but its winners paid only **+0.643 R** against losers at **-1.00 R**, so it
lost **-0.115 R a trade**. Its problem was never the direction. It was that the targets sat nearer than the
stops.

So the thing to look for is not "which way" - it is an entry where the stop can sit close to a structure
that would prove the idea wrong, while the target is a full leg away. Size the two before you take the
trade, and take `NONE` when that shape is not there.

Do not explain the market in general terms. Name prices.
