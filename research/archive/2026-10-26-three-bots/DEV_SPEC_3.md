# DEV_SPEC 3 — the decision becomes a weighted score behind one hard rule (2026-10-27)

The owner asked for this round to be shared work: *"share what we discussed with Codex and work together
to make the system actually usable."* So this spec starts with the whole picture, not just the task.

## What we found today, in numbers

**1. The entry, not the exit, is where it breaks.** Over 248 trades, 2023-09 .. 2026-10, with the exits
stripped to stop-and-target so the entry is measured alone (`geometry.py`):

| bot / period | winners' median MAE | losers' median MAE | **losers' median MFE** |
|---|---|---|---|
| DOWN never seen | 0.36 R | 1.08 R | **0.37 R** |
| DOWN in the fit window | 0.27 R | 1.04 R | **0.17 R** |
| UP never seen | 0.36 R | 1.05 R | **0.48 R** |
| UP in the fit window | 0.32 R | 1.09 R | **0.32 R** |
| RANGE never seen | 0.50 R | 1.08 R | **0.52 R** |
| RANGE in the fit window | 0.39 R | 1.06 R | **0.68 R** |

A winner barely dips; a loser walks straight into the stop and **never goes anywhere in our favour**. So
the stop is not too tight, and widening it does not help - the counterfactual on the real M1 path, same
entry, same target, stop k times wider, confirms it (DOWN never seen: x1.0 -0.267, x1.5 -0.228, x2.0
-0.296; UP and RANGE get monotonically worse). **The losers are not stopped out early - they are wrong
from the first minute.** That makes this a selection problem.

**2. The selection problem has a name, and it was already measured.** On the knowledge base's own split
(`edge_by_condition.py`, P25: side x the D1 regime x the owner's windows):

| bot | D1 regime | trades | R a trade | in fit / never seen |
|---|---|---|---|---|
| DOWN | bear | 24 | +0.164 | +0.240 / -0.020 |
| DOWN | **bull** | 49 | **-0.111** | +0.140 / **-0.244** |
| UP | bear | 11 | +0.224 | -0.013 / +0.422 |
| UP | **bull** | 76 | **-0.118** | -0.029 / -0.150 |
| RANGE | bear | 22 | +0.069 | +0.099 / +0.032 |
| RANGE | **bull** | 38 | **-0.639** | **-0.723 / -0.616** |

163 of the 248 trades happened in a bull regime, and every bot loses there. That is the whole story of
the negative results. The knowledge base already held this as **F20** and the brake **R08 / S11** -
"bull regime (D1 over a rising 50-day mean) → no M5 sell" - and the bots never used it.

**3. The bots decide on 4.5 % of what the system can measure, and weigh none of it.**

| decision path | measures used | of 132 available |
|---|---|---|
| `trend_box_down` / `trend_box_up` | 6 | 4.5 % |
| `range_break` | 3 | 2.3 % |
| `ai_trader` | 18 | 13.6 % |

Every one is a pass/fail gate. Nothing counts how many readings agree. Week 1's three losers passed all
six gates; the reading that would have stopped them (the D1 regime) was not among the six.

## The owner's rule for this round

> **Every trade takes only the side that has the edge on a timeframe LARGER than the entry timeframe.**
> (owner, 2026-10-27, for the whole system - the rule bots and the AI alike)

Our entries are M5. So the side is decided above M5, and the measurement above says the D1 regime decides
it. This is a **hard filter, not a weight**: a bot whose direction disagrees with the larger timeframe's
edge side does not trade, however good its own trigger looks.

## The division of work

- **The research session (not you):** which of the 132 measures can actually be read at the decision bar,
  each one's measured power to separate winners from losers on the 248 trades, split fitted / never seen,
  and the weights that come out of it. **You do not choose, tune or judge any weight.**
- **You:** the mechanism that carries them. Build the vessel; the research session fills it. Everything
  you add must be inert until weights are supplied, and `config.yaml` stays untouched.

## Task A — one place that answers "which side has the edge above this frame"

New module `app/strategy/edge_side.py`.

```python
def edge_side(frames: Mapping[Timeframe, pd.DataFrame], at: pd.Timestamp, entry: Timeframe) -> Side | None
```

- Reads the **D1 regime** from the lane's H1 frame: shift the close-stamped index back one hour, resample
  to `1D`, take only bars closed at `at`, a 50-day rolling mean of the close.
  - `BUY` when the close is over a mean that is rising (bull),
  - `SELL` when the close is under a mean that is falling (bear),
  - `None` when neither (mixed, or fewer than 50 closed D1 bars).
- `entry` is the entry timeframe and must be **smaller than D1**; raise `ValueError` if it is not, so the
  rule can never be read from a frame at or below the entry frame.
- Needs 50 closed D1 bars, so about 1,200 closed H1 bars. If the frame is shorter, return `None` - never
  guess from a short mean.
- Pure function, no I/O, no clock reads.

Hand-worked tests: bull, bear, both mixed cases, exactly 50 bars, 49 bars, a D1 bar that has not closed
yet (the same shape as `test_an_unclosed_h4_bar_never_reaches_the_zigzag`), and the `ValueError`.

## Task B — the trend and range bots obey it, behind one parameter

Add `require_edge_side: bool = False` to `TrendBoxParams` and `RangeBreakParams`.

When `True`, as the **first** gate after `in_window` (before any other work):

- `side = edge_side(ctx.frames, at, ctx.market.entry_timeframe)`
- `trend_box_down` holds with reason `"AGAINST_EDGE_SIDE"` unless `side is Side.SELL`.
- `trend_box_up` holds unless `side is Side.BUY`.
- `range_break` computes its break first, then holds unless the break's side equals `side`.
- `side is None` **blocks every bot**: no clear edge side above the entry frame, no trade. Write this in
  the docstring - it is the owner's rule, not a default worth softening.

## Task C — the vessel for the weighted decision

New module `app/strategy/weighing.py`. No strategy calls it yet; this round only builds and tests it.

```python
@dataclass(frozen=True)
class Weight:
    name: str          # the reading's name
    weight: float      # how much it counts, >= 0
    wants: str         # "high" | "low" | "true" | "false": which direction supports the trade

@dataclass(frozen=True)
class Scale:
    weights: tuple[Weight, ...]
    threshold: float   # the score needed to trade, 0..1

def score(readings: Mapping[str, float | bool | None], scale: Scale) -> ScoreResult
```

`ScoreResult` carries: the total score **normalised to 0..1 over the weights that could be read**, the
list of readings that supported the trade, the list that opposed it, and the list that was missing. A
reading absent or `None` is **left out of both the numerator and the denominator** - never counted as
agreement. An empty scale, or one where nothing could be read, scores `0.0` and supports nothing.

Boolean readings: `wants="true"` scores its full weight when the value is `True`, zero when `False`.
Numeric readings: the caller passes values already normalised to 0..1, and `wants="low"` scores
`weight * (1 - value)`. Document that normalisation is the caller's job - do not invent one.

Hand-worked tests, every number worked out by hand in the test: all agree, all disagree, a mix, a missing
reading changing the denominator, `wants="low"`, an empty scale, a zero weight, and a threshold exactly
met (document and test whether `>=` or `>` - pick `>=` and say so).

## The absolute rules (unchanged from DEV_SPEC 2, they worked)

1. Everything defaults OFF/inert; defaults must be byte-identical to today. Prove it: the full suite and
   the parity numbers unchanged.
2. Never re-implement production logic inside a test.
3. Every new test proven to bite: break the one line it covers, run that test, confirm it fails, restore.
   Report each one.
4. At least 10 new planted bugs for this round in `plant_bugs_3.py`, crash-safe, output committed, caught
   and MISSED both reported honestly.
5. No `.env`, no `TRADING_MODE`, no DEMO/LIVE, no credentials, no commit, no push, no deploy.
6. `ruff format`, `ruff check app tests`, `mypy app`, `bandit`, full `pytest` all green before you stop.
7. Do not change any default or `config.yaml`. Do not touch `geometry*.py`, `edge_by_condition.py`,
   `JOURNAL.md`, or anything under `research/2026-10-26-three-bots/weights*` - the research session is in
   those right now.
8. **If anything here contradicts anything else, stop and write it in `DEV_NOTES_3.md` instead of
   guessing.** Last round you found the spec clear; say so again if it is, and say where it is not.

## What to write when done

`DEV_NOTES_3.md`: each task, the tests x the mutation proving each bites, the planted-bug table, the
proof defaults are unchanged (suite counts, parity numbers), anything unclear, and what you did not do.
