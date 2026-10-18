# Setup OWN - the owner's own trade (current state)

The owner's goals and principles come first: `docs/OWNER_GOALS.md`. This file holds **the current state** of Setup
OWN: what trades in the bot, the windows and the method, and the research in progress. Every earlier round (the
hypotheses written before their outcome, then the results) is kept in `docs/OWN_SETUP_ROUNDS.md`. Results describe
the past, never a promise. Last update: 2026-10-19 02:00 Thai time.

## In the bot (DEMO since 2026-10-18 17:08 Thai; LIVE off)

| Setup | Code | What it does | Measured |
|---|---|---|---|
| **F1 CONF-72 v2** (lane `own`) | `app/strategy/own_setup.py` (`setup_own_conf72`) | The H1 tide, at a level (today / yesterday / Asia / round 50 / M15 / H1 read), price action, 2 of 3 M5 indicators, the 72-hour extreme less than 4 U in front or behind, no fast tape; the stop 1 M1 ATR beyond the level (3-10 U, floor 0.5 M15 ATR), the target 8 U; break-even at 4.8 U, 60 minutes; v2: a runner in a strong-volatility phase, the 10-bar scratch; half risk off the round 50 | 2026-03-01 .. 10-14: 35 trades, +0.219 R, +63 USD at 0.01 lot (the earlier window); engine = research 35 / 35 |
| **S2** - the CPI / NFP straddle (lane `news`) | `app/strategy/release_straddle.py`, `app/news/releases.py` | At 08:30:00 New York: a buy stop 2 U above the ask and a sell stop 2 U below the bid, one cancels the other, live 60 s; the stop 8 U; out at the end of the release minute (quotes, not bars) | ticks 2026-03-01 .. 10-14: 14 trades, +1.23 R, +144 USD; the release-second fills are the open risk |

Details: `docs/OWN_SETUP_ROUNDS.md` round 17; the setups table in `docs/STRATEGIES.md`. Neither has been run on the
current exam window yet.

## Windows and method (owner, 2026-10-18)

- **The exam:** the latest six months counted from today - on 2026-10-18: 2026-04-18 .. the data end (2026-10-14).
  Rules are designed before it and run on it once.
- **Learning:** the latest 12 months first (2025-10-18 ..; "to see results quickly; if it works, run the three
  years as before"). Walk-forward: at each month's start the settings with the best mean R over the previous six
  months' closed trades (at least 20) trade that month; the stop and the evidence library learn from earlier days
  only.
- **Reports:** week by week (Thai weeks, Monday 00:00 .. Sunday 24:00 Thai), with the worst trade, the longest losing
  streak and the drawdown in USD at 0.01 lot; every losing trade traced to the picture the bot saw (H1 the last
  120 bars), and a learning-log row per round (learned -> changed -> why -> result).
- **Code before results:** every building block has hand-worked unit tests, planted bugs the tests must catch, and
  an independent re-derivation; the indicators are MT5's own formulas (`foundation.py`); no learning run before
  the code is proven.

## The owner's moments (the focus windows; DST-aware, weekdays)

| Window | Local time | Thai time (summer / winter of that zone) |
|---|---|---|
| Asia 07:00, 08:00 | 06:55-07:30, 07:55-08:30 Bangkok | 07:00, 08:00 |
| Asia 09-12 | 09:00-12:00 Bangkok | 09:00-12:00 |
| Frankfurt | 07:55-08:30 Berlin | 13:00 / 14:00 |
| London | 08:00-12:00 London | 14:00-18:00 / 15:00-19:00 |
| New York 08:00, 08:30 | 07:55-08:30, 08:25-09:00 New York | 19:00, 19:30 / 20:00, 20:30 |
| New York 09:30, 10:00 | 09:25-10:00, 09:55-10:30 New York | 20:30, 21:00 / 21:30, 22:00 |
| New York 11-14 | 11:00-14:00 New York | 22:00-01:00 / 23:00-02:00 |

Code: `research/2026-10-18-moments/agents/precursors/plib.py` (`WINDOWS`, `window_mask`, `ny_mask`).

## The learning loop: every run's losers in three kinds (owner, 2026-10-17)

The owner: "learning from the losing trades is the heart of developing a trade"; "combine it with the three
kinds of losers and write it down as the way we learn". After every run (harness, backtest, DEMO), each trade
stopped out before its target is put in one kind (`loser_kinds.py`), and each kind points at its own lever:

| Kind | What happened | What it says | The lever to try next |
|---|---|---|---|
| 1 Wrong way | less than half the way to the target before the stop, and no run to the target afterwards | the side was wrong | the direction screens: the H1 tide, the pullback depth, the session or hour (skip where kind 1 dominates), the location against support / resistance |
| 2 Right way, fell short | at least half the way to the target, then back to the stop; no run afterwards | the target was too far for that moment, or the stop stayed too long at risk | the exit: a nearer target (a smaller tool), a partial profit or the stop to break-even at about 0.5-0.6 of the target, a shorter time stop |
| 3 Right way, entered too early | stopped first, then the target reached from the original entry within 120 minutes | the timing or the stop: the entry's shake-out took the stop | the entry timing (screen 3: wait for the turn, ticks), a better entry price (a pullback limit), or a stop beyond the usual shake-out |

**Never conclude "it is a coin flip"** (owner, 2026-10-17: "that is too easy; find why it loses"). The coin-flip side
is only a yardstick; every report names the concrete reasons its losers lost (from the trades and their charts:
where in the move, the H1 swing and phase, the session phase, the level's quality, the stop against the normal
swing, the spread at that hour, news nearby, what came right before the entry), how many losers each reason
covers, how the winners differed, and the change that attacks the largest reason.

Each kind is always read **against a coin-flip side at the same minutes** (the same stops and targets): a kind is
a finding only where it differs from the coin's split (round 2: 41 / 14 / 45 % for both - no finding). The next
change attacks the kind that is largest *above the coin's*, is written down before it is computed, and is judged
on data it was not found on.

## Research in progress: Setup OWN V2 - the library of researched pictures (owner, 2026-10-18 / 19)

As agreed (2026-10-18 17:02 Thai): research the patterns after which price runs to the 5-10 USD target, then let the
bot match the chart in front of it to any researched result and decide whether to trade.

- **The library:** three years of the owner's snap times plus the start of every 10 U run inside the owner's windows
  (29,073 moments from 2023-11; `moments.py`), each with what the bot saw per timeframe (the core codes, the 120-bar
  outline and the picture: size, position, the last leg, the way, the swing structure, the close against the last
  top / bottom, the deepest pullback, smoothness, the way of each third) and what followed. Evidence only from other
  episodes (>= 7 days before the decision).
- **The bot's reading (2026-10-19):** audited by eye on every timeframe; where a timeframe's own swings are too few,
  it reads them from the next smaller timeframe over the same span (the zoom; unreadable readings 1.5-3.9 % -> 0 %).
- **V2b** (the same core codes): the matches looked different to the owner's eye; the exam -0.169 R. **The same
  picture** (every part alike, as the owner reads it): almost never repeats - 0.0-0.1 % of snaps have one earlier
  episode, none has three; the bot could not trade on it.
- **V2s** (the same situation on M5 + M1): it repeats, and its lean told the way of the next half hour's 10 U run in
  both halves (checked four ways: an independent recount, by day, two placebos). Traded at the snap: learning
  -0.020 R, **the exam -0.085 R** (278 trades, -240 USD at 0.01 lot; checked 723 / 723 trades): when the lean was
  right the price first dipped a median 5-6 USD and took the stop in half of them. Waiting for the dip (V2e: a limit
  3 / 5 USD away, or an M1 turn): every variant negative on the learning half; the exam not run.
- **Status (2026-10-19 02:00 Thai):** to be concluded with the owner - the lean's edge is smaller than what the
  10 U target, the stop and the costs need. Details: `research/2026-10-18-moments/agents/precursors/notes.md`.

## Stopped: LV3 - the owner's reading of the chart (2026-10-18)

The owner on a losing trade's picture (2026-09-02): with every larger timeframe's trend, wait for price to bounce
into an earlier level, then enter the trend's way; on the 2026-03-09 sell: "the M1 legs were not complete - at least
3-5 legs, the newest peak lower; one M1 bar has no weight". From that:

- **LV** (a limit at the level) lost: levels run through more often than they turn. **LV2**: the levels from the
  larger timeframes (M15 / M30 / H1 swings, a zone at most 0.25 ATR wide, important zones weigh more), the bounce's
  start on the entry timeframe, a stop beyond the level learned from the data, exits on the entry timeframe. Design
  over three years: every cell negative, best -0.032 R a trade (the learned stop at p90; p70 -0.094).
- **LV3** = LV2 with the entry at the M1 legs: enter when the pause has at least N M1 peaks (troughs for a buy), the
  newest one lower (higher) than the pause's extreme, and the extreme reached the level zone. N = 3, 4, 5 or adaptive;
  M1 swings of 1.5 / 2.0 ATR; target T1 / T2 (>= 5 USD); the learned stop p80 / p90 - 32 cells, chosen walk-forward.
- **Entry timeframe:** the smallest of M1 / M5 / M15 / M30 whose ATR covers 5 USD; H1 the largest.
- **Every trade records its library evidence** (R13): per layer (H4 + H1, M30 + M15, M5 + M1) the pattern of earlier
  days it matches (>= 80 % of the core attributes), how often it occurred and what followed - with, against, faked,
  flat; "none" when nothing matches.
- **Status (2026-10-18 23:00 Thai):** proven - 126 research tests pass and every planted bug that changes a result is
  caught; the independent re-derivation matched all 510 distinct signals and all 134 trades in six runs on the
  12 months (M1 swings of 1.5 and 2.0 ATR). Next: the walk-forward run on the latest 12
  months, reported week by week.
- **First walk-forward (2026-10-18 23:00 Thai), latest 12 months:** learning half +0.013 R (66 trades), the exam
  -0.139 R, -198 USD at 0.01 lot (95 trades, max drawdown 194 USD); the library evidence at entry did not separate
  winners from losers. **Why (measured on the data before the exam, each component alone against a no-effect
  baseline):** the larger timeframes' trend, the pullback, the levels (no kind - yesterday's, the 72-hour, round 50s,
  the Asian range, swings - turns price beyond chance) and the LV3 signal all measure at 50 %. LV3 stops as a setup.
- **The method from now on (owner, 2026-10-19):** every component is proven twice - its code, and its premise in the
  data against a no-effect baseline in two separate parts - before it is assembled into a setup or tuned.
- Rules (written before each computation), requirements R1-R13, every result and every bug found:
  `research/2026-10-18-moments/agents/precursors/notes.md`.

## Void or superseded

- Round 18's library numbers (indicators not MT5's, chained levels): void; the library is rebuilt.
- LV2's first window run (-0.072 R): void (the zone bug); the 2026-03-01 and 2026-04-14 windows: superseded.
