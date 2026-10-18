# Inverted setups — why the bot trades the classic setups the other way

> **Removed from the code on 2026-10-14 (owner).** The inverted copies (`<name>_inverted`) no longer exist; a counter-trend trigger is faded inside its setup instead (`fade_counter_trend`, docs/archive/SETUP_REVIEW.md §16). This file is kept as the history of the experiment.

Status: **switched off 2026-10-12** (owner; a year of two-world backtests, SETUP_REVIEW §15: the inverted
harmonic lost on every symbol). Traded on DEMO 2026-10-09 .. 10-12. Read this before changing anything named
`*_inverted`, the `risk.inverted` config or `app/strategy/inverted.py`.

## 1. Why this looks wrong, and why it exists

Classic technical analysis says: when a breakout, a pattern or a harmonic completion fires, trade **in** its
direction, with the stop where the idea is invalidated and a target at least 1.5-2 R away. Every setup in this
repository was built that way (docs/STRATEGIES.md).

The inverted setups take exactly those signals and trade the **opposite** side. That contradicts the textbook on
purpose. The reason is measurement, not theory:

- One year of replay (2025-10-15 .. 2026-10-05, net of costs, docs/archive/SETUP_REVIEW.md §3-§11) showed every setup
  below the owner's target (≥ +0.15 R/trade): `setup_breakout` −0.15 R (3,750 signals, M15), `setup_pattern_breakout`
  −0.23 R, `setup_fib_pullback` −0.16 R, and the breakout direction did **worse than a random direction**.
- On the eight traded symbols, a break of an S/R zone closed back inside within 12 bars **66-69 %** of the time
  (M15 and H1, every symbol alike; SETUP_REVIEW §12). Many breaks are false breaks.
- The owner (a discretionary trader) observed the same on his own charts: the setups often enter at the moment
  price shakes out the other side, then the original trade is stopped and price goes the other way.

So the question became: **if the classic signal is on the wrong side more often than not, does the opposite trade
at the same prices make money?** The inverted setups answer that forward, on the DEMO account.

## 2. What an inverted trade is (exactly)

For every original strategy `X`, `X_inverted` (built by `inverted(cls)` in `app/strategy/inverted.py`, registered
in `app/strategy/catalog.py`) runs the original **unchanged** and turns each entry signal into:

| | Original | Inverted |
|---|---|---|
| Side | BUY | **SELL** (and the other way round) |
| Entry | ask (BUY) / bid (SELL) | the other side of the same quote |
| Stop loss | original SL | **the original's take-profit price** |
| Take profit | original TP | **the original's stop-loss price** |
| R:R | e.g. 2.0 | the inverse, e.g. 0.5 |
| Reason codes | original codes | + `INVERTED` |

Consequences that matter:

- **The exits are the same prices.** Whenever the original would have hit its stop, the inverted trade hits its
  take-profit, and the other way round. Its P/L per trade ≈ −(original's price move) − **two spreads** (the
  original's spread is not recovered and the inverted trade pays its own) − commission.
- **Win rate goes up, payoff goes down.** An inverted trade wins small and often (its TP is the original's short
  stop) and loses large and less often (its stop is the original's far target).
- **Risk per trade is unchanged.** The lot is sized from the wider stop at the same risk percent, so lots are
  smaller. Heat, margin, daily/weekly loss, breakers, news, sessions and the mode gate apply as for any trade.
- A signal without a take-profit has no stop for the inverted trade: HOLD `NO_TARGET`.
- Position management (break-even, trailing) is measured in R of the wider stop, so it rarely triggers before TP.
- `should_close` asks the original strategy with the opposite side.

## 3. What had to change to let it trade

| Blocker | Change |
|---|---|
| Min R:R (1.0 in config, the PWA profile and presets) rejects R:R ≈ 0.5 | `risk.inverted.min_risk_reward` (0.2) for signals with reason code `INVERTED` only; the profile's min R:R does not apply to them (`app/engine/decision_engine.py`, `decide`) |
| SL cap 3 ATR rejects the original's far target as a stop | `risk.inverted.max_sl_atr_multiple` (12) for `INVERTED` signals only |
| An original and its inverted copy cancel each other (arbitration CONFLICT, opposite positions) | `config.yaml`: the 9 `*_inverted` are `enabled: true`, the 9 originals `enabled: false` (still scanned and shadow-tracked) |
| Users would see inverted setups as theories/alerts | `advised = False`: never offered as pattern theories (`app/advisory/requirements.py`, `preferences.py`); personal alerts already need R:R ≥ 1 |
| Strategy names / codes in the PWA | `STRATEGY_NAMES`, `strategy.*`, `strategyName.*`, reason codes `INVERTED` / `NO_TARGET` (TH/EN) |

Code default: `risk.inverted` is `None`, so without the config entry inverted signals cannot trade (the golden
tests and every other deployment are unchanged).

## 4. What we expect (honest numbers)

Re-simulated from the same year of replay, exits at the original prices, both spreads and commission included,
in R of the **original** risk (`docs/archive/SETUP_REVIEW.md` §13 when written):

| Setup | Original | Inverted |
|---|---|---|
| setup_breakout (3,750) | −0.154 | **+0.036** |
| setup_pattern_breakout (901) | −0.229 | **+0.059** |
| setup_fib_pullback (378) | −0.163 | **+0.055** |
| setup_elliott_wave (552) | −0.075 | −0.029 |
| setup_candle_reversal (331) | −0.107 | −0.094 |
| setup_neckline_break (89) | −0.002 | −0.144 |
| example_trend_pullback (55) | +0.025 | −0.109 |
| setup_harmonic_prz (821, 8 symbols) | +0.015 | **−0.196** |

- **Corrected 2026-10-11 (SETUP_REVIEW §14):** the table above is the identity −(original) − two spreads. The
  full re-simulation (`research hypotheses --inverted`) also pays the bar-based fills' cost on both sides and
  reports R of the inverted trade's **own** risk (what the account risks): breakout −0.002, pattern breakout
  −0.005, fib −0.025, elliott −0.025, candle reversal −0.095, neckline −0.103, trend pullback −0.062, harmonic
  −0.118 R per trade. None is above zero; harmonic and candle reversal are below zero with the CI.
- Inverting **does not reach the target** on history. The costs (spread ≈ 5-10 % of the original stop per side)
  eat most of what the original lost.
- It helps where the original direction was worse than random (the breakout family); it hurts where the original
  direction carries information (harmonic: +0.16 R over the other direction).
- The DEMO run measures whether the current market behaves like the year of history.

## 5. What to focus on (the work that remains)

1. **Measure with the backtester, per setup, in two worlds** (owner, 2026-10-11): two separate
   `app.cli backtest` runs over the same period, started together, one for the original (`X`) and one for the
   inverted (`X_inverted`), each with its own account, the same history and the same config. Report both side
   by side (trades, win rate, R per trade, net, max drawdown). DEMO is a live check, not the evidence; the
   research harness is for quick hypotheses only. Research runs use a config copy with the loss breakers and
   the trade filters at their widest (`data/research/config_paired_bt.yaml`: 0.5 % risk, drawdown 50 %,
   consecutive losses 50 with no pause, 5 positions per symbol, spread/SL 1.0, min R:R 0.01), so a breaker
   does not cut the sample (the first harmonic run latched MAX_DRAWDOWN at 10 % within three weeks).
2. **Switch nothing off from the harness alone.** The two-world backtests decide which side of each setup
   works, if any; the owner decides what the bot trades.
3. **Costs are the lever.** The inverted edge on breakouts is mostly eaten by two spreads. Test filters that keep
   only signals where the spread is a small share of the original stop (cost share), and higher timeframes (H1)
   where the spread share is smaller.
4. **Context, not blind inversion.** The real question is *which* breaks fail. Use the H4/D1 market map features
   recorded on every signal (`ctx:h4_*`, `ctx:d1_*`: consolidation vs trend, zone with/against, room to the
   opposing zone; docs/INDICATORS.md "Market map") and the pre-run behaviour study (SETUP_REVIEW §12: sessions,
   pre-NY, pre-news, illiquid mornings) to find where inversion works and where the original works. A rule only
   counts when it holds walk-forward on the half and the symbols it was not chosen on.
5. **Goal stays the same:** ≥ +0.15 R/trade net, CI lower bound > 0 in both halves, ≥ 300 trades a year on the
   eight symbols, max drawdown ≤ 15 R (memory: owner's target, 2026-10-09). State the gap after every
   experiment.

## 6. Safety and limits

- DEMO only. LIVE stays off; inverted trading on LIVE needs the owner's explicit go-ahead after the DEMO evidence.
- The inverted R:R floor and SL cap are exceptions for `INVERTED` signals only; no other risk rule is relaxed.
- A large inverted stop means fewer, smaller lots; one loss can erase several wins. Watch the consecutive-loss
  and daily-loss breakers.
- Shadow keeps recording the **originals**, so both sides of every signal stay measurable.

## 7. Where things are

| What | Where |
|---|---|
| Wrapper and flip | `app/strategy/inverted.py` (`inverted`, `flip`) |
| Catalog | `app/strategy/catalog.py` (`ORIGINALS`, `INVERTED`, `STRATEGIES`) |
| Decision exception | `app/engine/decision_engine.py` (`decide`: `risk.inverted`), `app/config.py` (`InvertedRiskConfig`) |
| Config | `config.yaml` → `risk.inverted`, `strategies.items` (`*_inverted`) |
| Not advised | `BaseStrategy.advised`, `app/advisory/requirements.py` (`pattern_setups`) |
| Tests | `tests/unit/test_strategy_inverted.py`, `tests/unit/test_decision_engine.py::TestInvertedLimits` |
| Research | `docs/archive/SETUP_REVIEW.md` (§3-§13), `app/learning/research.py`, `data/research/` |
