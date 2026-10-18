# AI chart reader - feasibility plan (owner, 2026-10-18)

The owner's idea: "let the AI look at the price chart and send signals to the bot - it can watch price patterns and
see them the way a human does, but without a human's bias. Snap the chart every minute, send the last 3-5 images to
the AI, and backtest the same way: show the images, let it decide, then check the next images (the future) for
profit or loss."

This file is the plan for testing whether that works before anything trades. Nothing here is built yet.

## What exists

- `app/ai/providers.py` calls Claude (`AnthropicProvider`, structured JSON answers, a daily call and cost budget in
  `config.yaml` → `ai`), and `app/ai/gate.py` already lets an AI veto entries. It sends text only; images need a
  small extension (image content blocks).
- The research harness has every M1 bar of gold since 2020 and the candidate tables of F1's base confluence
  (`research/2026-10-18-moments/agents/journal/`), with the outcome of each trade (the "answer key").

## The test design

1. **One chart renderer for backtest and live.** For a decision minute, 3-5 panels from closed bars only: H1 (about
   120 bars, EMA 20/50), M15 (96), M5 (72), M1 (90), optionally F1's levels and the 72-hour extreme. **Anonymised**:
   no dates, no times, no price axis (prices as ATR distances from the last close) - see the risks below.
2. **A fixed question with a fixed answer format**: BUY / SELL / NONE, confidence 0-100, a stop and a target in ATR,
   one sentence why; temperature 0.
3. **The answer key** is computed from the bars after the decision (the 5 USD / 8 U target or the stop first, real
   costs) and is never shown to the model.
4. **Controls, every time:**
   - **The flipped chart:** the same image upside down. A model that reads direction must flip its answer.
   - **The coin:** a random side on the same minutes.
   - **The base rate:** every candidate traded.
   - **Repeats:** a sample asked twice, to check that the answers are consistent.

## Where to point it first (the cheap, sharp question)

F1's base confluence fires about 4 times a day and loses (-0.08 R) unless price sits at the 72-hour extreme
(`docs/OWN_SETUP.md`, round 17). **If the AI can pick the winners among those ~4 a day, the "one trade a day" goal
is met with an edge we already understand.** So the first test asks the AI about those moments (a few thousand),
not every minute (100,000+).

## Stages and gates

| Stage | What | Calls | Cost (Sonnet-class, ~3k tokens a call) | Gate to go on |
|---|---|---|---|---|
| 0 | Renderer, anonymiser, the answer key, the image support in the provider | 0 | 0 | the images look like the owner's charts |
| 1 | Pilot: about 500 base moments after the model's knowledge cutoff (2026-07 .. 10-14) + 100 random minutes | ~700 | ~5-10 USD | the AI's trades >= +0.10 R and better than the flipped chart by more than the noise (about 0.1 R at this size) |
| 2 | All base moments, the design years and the window, month by month | ~10,000 | ~60-100 USD | the owner's bar: >= +0.15 R, about 1 trade a day, most months positive |
| 3 | In the bot as a filter on F1's base signals (PAPER, shadow first), with the `ai` budget caps | ~20 a day | ~0.2 USD a day | live results inside the backtest band |
| 4 | (Only if 1-3 pass) the every-minute scan the owner described | ~720 a day | ~6-12 USD a day | - |

## Risks to measure, not assume

- **Memory instead of reading:** the model may have seen gold's history up to its training cutoff. Anonymised
  charts, and a test only on data after the cutoff, keep it honest.
- **"No bias":** a model has biases too (for example a lean to buying, or to seeing patterns everywhere). The
  flipped chart and the BUY/SELL balance measure them.
- **The prior:** in this research gold's minute moves are close to a random walk, and a model on 62 numeric features
  reached AUC 0.53-0.58. The AI sees the same candles as a picture. The realistic hope is a better filter where a
  small edge already exists, not a prediction from nothing. The pilot answers this cheaply.
- **Cost and latency:** about 2-6 s a call, which is fine for decisions at an M1 bar close. Budgets are capped in
  config.
- **Spending on the owner's API account** needs the owner's go-ahead for each stage.

## Pilot results (2026-10-18)

| Round | Model, images | Moments | Result | Cost |
|---|---|---|---|---|
| 1 | Haiku 4.5, plain 4-panel | 674 base moments (window) | AI trades -0.087 R; the coin -0.095; it says BUY on 67 % (the signals 41 %); its confidence is always 72 or 35 | 0.46 USD |
| 1b | Opus 5.5, structure overlays (`render_v2.py`) | 45 + flips | NONE on 40 of 44; 4 trades -0.34 R; flip-consistent 93 % | 0.42 USD |
| 2 | Haiku 4.5, p_buy / p_sell (`ask_prob.py`) | 111 clear signals (F1's C4 passes): design 2025-03..26-02 (77, after its cutoff), window (34) | see below | 0.16 USD |

Round 2 in detail (`analyze_prob.py`):
- **The answers are consistent:** the flipped image gets the mirrored answer on 92 % of the pairs.
- **But they barely vary.** Eight answer pairs cover most moments, e.g. 25/72, 62/28 and 72/28.
- **The AI favours the signal's side on 95 %.** It reads the same trend as F1's H1 tide.
- **The score does not rank the outcomes.** The score is p(signal side) - p(other side). Its rank correlation with
  the R is +0.010.
- **Design thirds are flat:** the top third made +0.071 R, the middle -0.079 R and the bottom +0.105 R.
- **The window thirds look ordered but do not hold.** Top +0.349 R (9 trades), middle +0.290 R (15), bottom
  -0.160 R (10). Design does not confirm this, so it is noise at this size.
- **The three moments where it disagreed all lost** (-0.68 R). Three trades is too few to use.

Conclusion: in this form the model repeats the trend that F1's rules already use. It adds no information on which of
F1's clear signals win. Total spend so far is about 1.08 USD of the owner's 5 USD.
