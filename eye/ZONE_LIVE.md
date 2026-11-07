# The run-zone setup on the broker - the specification

**What this is**: the real-time runner that trades the run-zone setup of `eye/ZONE_RULES.md` on the MT5 account,
through the system's existing broker layer and its LIVE gate. The rules are ZONE_RULES.md's - **this file adds only
how they run in real time**; where a rule is not restated here, ZONE_RULES.md holds. The simulation (`eye/zone_bot.py`;
`app/zone/core.py` `simulate_setup`, `step_setup`, `find_visits`) is the reference the runner must agree with (L11).

The owner (2026-11-02): *"put it on LIVE once it is done"*; *"0.01, no DEMO"*; *"I watch the trades and take the risk
myself"*; *"the system already sends orders to MT5 - you only have to make it use our zone setup correctly"*.
The owner (2026-11-04): *"let it go - it can do nothing about it. Get the normal case right first; an abnormal case
where the SL cannot be moved is out of our control anyway."* - **this file specifies the normal case exactly; an
abnormal case is handed to the broker (L8, hands-off).**
Each rule says whose it is: **(owner)** or **[Claude]** (a form the owner did not give, for the owner to change).

## Words - each defined once, used only in this sense

- **Terms of the setup** - the set and its parameters (`exec_tf`, `near_frac`, `away_frac`, `cancel_frac`, `order_life_h`,
  `be_mode`, `be_frac`, ...), the grid and its step, the anchor, pivots, lines, arming, a visit and its touch, the
  skips 5a - 5d (momentum, busy, abnormal, the state / trend), P1, P2, SL, TP - are ZONE_RULES.md's and mean what it
  says. `exec_tf` is the set's. All times are the broker's server time converted through `ServerClock` (UTC inside);
  deal times to the millisecond (`time_msc`).
- `sgn` +1 BUY / -1 SELL; `S` the step of the grid in force; `Z = near_frac x S`; `per_h` the `exec_tf` bars in an
  hour; `j` an `exec_tf` bar, `j0` the first `exec_tf` bar of the hour; a bar's `close_time` = its open + its period
  (the stored value the simulation uses); "at a bar's close" = at the first cycle after its `close_time`. Every
  comparison is the simulation's, with the same `>=` / `<=`.
- **Cycle**: one pass of the runner, every `cycle_seconds` (L9): read the broker, judge, act.
- **Candidate**: one side's line chosen at an H1 open (L4). It is **live** (it passed the skips and gets orders) or
  **skipped**; a live candidate whose P1 is refused before it is the hour's setup is no longer live - it is `dropped`,
  and a later touch of it is treated as a skipped visit (it leaves the hour free; its record is `undecided`). One `zone_live_setup` row per live candidate.
- **The hour's setup**: the live candidate whose visit came first in the hour (L4). Only it reserves (L6). "Setup"
  alone means a live candidate, before or after its visit.
- **Outcomes** (a setup's end; `dropped` for the other candidate's visit becomes final only at the hour's close, L4), named as the simulation names them (`app/zone/core.py` `Setup.outcome`, `Setup.how`):
  `no fill` (expiry, withdrawal, an unvisited candidate's hour over), `cancel` (the closed-hour cancel, a blocked P1
  touched), `traded` (its last position closed) with **how** `SL`, `TP`, `BE` or `close` (closed by the runner - no
  simulation counterpart); and the runner's own: `dropped` (lost the hour to the other candidate, or P1 refused),
  `interrupted` (L7), `hands-off` (L8), `restart` (L8). **Ended** = has a final outcome; nothing of an ended setup is
  wanted. A candidate `dropped` for the other's visit is not ended until the hour's close: it has no orders meanwhile
  (none is wanted while it is dropped) but can be made the hour's setup again (L4). Only `no fill`, `cancel` and `traded` of the hour's setup reserve (L6).
- **Logic price** = the unrounded price of the simulation; **sent price** = the price sent, rounded to the tick;
  **broker price** = the price of the broker's deal.
- **Order names**: P1 and P2 (ZONE_RULES rule 6). A **placement** is one place request of a name; its `n` counts the
  placements of that name in the setup (0, 1, ...). The **current placement** of a name is its newest one.
- **Wanted**: an order is wanted while its setup is not ended and the rules of L4 - L5 and L7 allow it to rest now.
- **The key**: the comment `Z<setup id>-<P1|P2>-<n>` (L3). It ties a broker order, deal or position to its placement.
- **Ours**: an order, deal or position whose key is a placement this process sent (or of unknown outcome, L8). Any
  other order or position of the magic is **not ours**.
- **Managing**: removing orders, extending their expiry, the break-even, the closes L4 / L5 require, reading fills and
  exits. **Placing**: sending a new place request. L7 says when placing is stopped and managing goes on; only an
  account switch (L1) stops all managing; hands-off (L8) stops all of it but the removal of orders.
- **Within one `exec_tf` bar** = within one `exec_tf` period of the moment the condition began (the send, or the first
  cycle that saw it).
- **A fault** is logged at ERROR; a bar-boundary difference (L11) at WARNING.
- **The magic**: the orders and positions of XAUUSD with the zone runner's magic number on the pinned account (L1);
  nothing else is read, touched, or counted in "flat".
- **Hands-off** (L8): placing stopped, every order of the magic removed, no position touched, until the magic is
  **flat** - no order and no position of the magic on the pinned account.
- **Fresh** (L2) / **stale**: the data test for placing. **Market closed**: no quote newer than `stale_quote_seconds` and
  no H1 bar of the runner's series (the stored bars and those appended since) at this weekday and hour, in server
  time, in any of the previous four weeks.

## L0. Shape - one logic, two drivers [Claude]

- **One logic**: the pure zone logic (the step, the grids, the arming, the visits' readings, the skips, the setup's
  prices and its bar-by-bar life) is in `app/zone/core.py`; the parameters `ZoneParams` in `app/zone/params.py`.
  `eye/zone_bot.py` keeps its command line, its outputs and charts and imports the logic from `app.zone.core`;
  `eye/zone_config.py` keeps its command line and re-exports `app.zone.params`. The reading of
  `data/bot_config.db` (the parameter sets) is in `app/zone/params.py`'s store functions (standard-library `sqlite3`
  only, allowed in the pure layer), called only by the drivers.
- The bar-by-bar life of a setup is written once, as `step_setup` in `core.py`: given the setup's state after bar
  `j-1` and bar `j`'s values, it returns the state after bar `j`. `simulate_setup` loops it over stored bars; the
  runner uses its tests (`expired_at`, `moved_away`, `closed_hour_cancel`, `entry_blocked`, the break-even trigger)
  through `app/zone/live.py`, which calls `core.py` and holds no second copy of a rule.
- **Two drivers**: the simulation (`eye/zone_bot.py`) and the runner **`app/zone/trader.py`** (real time, broker
  orders), with its state store `app/zone/store.py`.
- `tests/unit/test_architecture.py` `LAYERS`: `app.zone` 6 - `core`, `params`, `live`, the pure modules (may import
  `app.core`, `app.indicators`),
  `app.zone.store` 10, `app.zone.trader` 10 (may import `app.zone.store`, `app.broker`, `app.risk`, `app.storage`,
  `app.config`, `app.market_data`); `docs/archive/CODING_STANDARDS.md` notes the change, as the test asks.
- **Not the strategy engine**: the runner does not use `app/engine/orchestrator.py`, the decision engine, the
  checklist, arbitration, the breakers or the risk sizer (rule 0 of ZONE_RULES: a setup of its own). It uses: the
  broker factory (`build_trading`), `evaluate_gate` (`app/risk/mode_gates.py`), the `ExecutionGateway` and
  `RequestBuilder`, the read-only market-data gateway, `ServerClock`, the kill switch, and the storage layer.

## L1. Modes, the gate, the account (owner; the system's rules)

- `TRADING_MODE` from `.env`: LIVE (the owner's) or DEMO (supported by the code, not run - the owner: no DEMO);
  PAPER / BACKTEST refuse to start the runner.
- LIVE needs `ENABLE_LIVE_TRADING=true` and `LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-<MT5_LOGIN>` - **set by the
  owner**, never by code or by Claude.
- **Before every place request** the runner evaluates `evaluate_gate` on **fresh** `gateway.account()` /
  `gateway.terminal()` snapshots (`risk_config_ok` = the runner's settings validated at start; `kill_switch_active` =
  the kill switch; `latched_breakers` = none; `day_plan_ok` = True, detail "zone runner: no day plan" - **the owner,
  2026-11-02: the zone runner does not use the day plan**). A failed gate: no order, a log line; L7 says what happens
  to resting orders.
- **The account is pinned**: at start the runner records the login and server. A fresh snapshot with another login
  or server: the runner stops placing and managing, sends nothing to any account, logs ERROR every cycle, and waits
  for the owner (a restart; it pins the account it then finds, and L8's start applies). Orders left on the old account
  expire by their broker expiry (L3). Every stored row carries the login and server.
- **The account must be a hedging account** (`margin_mode` = `ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`): P1 and P2 are two
  positions with their own SL / TP. Any other margin mode refuses the start [Claude].
- **One symbol**: XAUUSD (the market of the set). **Lot 0.01 a position, fixed** (owner) - `lot` (L9), refused at start
  unless `volume_min <= lot <= volume_max` and a multiple of `volume_step`.
- **Magic**: one number reserved for the zone runner in `app/engine/magic_registry.py`, read by `app/cli` and handed to
  the runner (the runner does not import `app.engine`); the runner reads and touches
  only orders and positions of XAUUSD with that magic, on the pinned account.
- **One runner**: an exclusive lock (`data/zone_runner.lock`, held for the process's life) - a second runner refuses
  to start.

## L2. Bars and quotes in real time [Claude]

- At start: the stored bars **of the pinned server** (`data/history/<server>/XAUUSD`, the history store is organized
  by trade server; the simulation's runs read `FBS-Demo`) are loaded - none for that server, or any frame (D1, H4, H1, M15, and M5 when it is `exec_tf`) whose
  stored series starts later than the simulation's stored series of that frame (`FBS-Demo`, measured 2026-11-04: D1
  2021-09-01, H4 2023-04-02, H1 and M15 2023-08-01, M5 2025-10-05 - so the steps, grids, pivots and arming are
  the simulation's), refuses the start (the owner fetches that server's history
  first); a series that starts earlier is cut to the simulation's first bar of that frame, and each
  frame (D1, H4, H1, M15 - always, the state gate reads it - and M5 when it is `exec_tf`) is brought up to date with
  the broker's **closed** bars through the read-only gateway, merged by bar open time (a stored bar is never replaced). **The broker's bars must reach back to the
  stored files' last bar** and agree with the stored bars they overlap (open time; open, high, low, close within one
  tick); if they do not (a gap, another server's time base or prices), the start is refused and says which frame and
  bar - the owner brings the history up to date. The runner keeps them in
  memory and appends each newly closed bar; it does not write them to the store.
- Every cycle: the quote (bid, ask, time) and the bars closed since the last cycle. **The steps at a bar's close**
  (L4's visits, arming and missed touches, L5's outcomes and break-even) run at the first cycle at which that closed
  bar can be read from the broker, in bar order; until then they wait (and the data is not fresh, L7). The forming bar is never used,
  except the **open of the forming H1 bar** (the hour's open `o`, L4) read from the broker's current H1 bar, and
  **the forming `exec_tf` bar's bid high / low so far** - the extremes of the quotes the runner has read in it (L5's
  withdrawal and BUY P2 removal); at the bar's close the closed bar's true extremes are applied (L5).
- **Fresh data** (for placing only): the quote is younger than `stale_quote_seconds`, and every frame's last closed
  bar equals the broker's last closed bar of that frame. While the market is closed (the weekend, the daily break)
  nothing is placed and nothing is stale-removed (L7); the first cycle after the reopening judges freshness anew. A
  failed read of anything from the broker (the quote, the bars - the forming H1 bar included -, the account, the
  terminal, the orders, positions, deals or history) makes the data not fresh at once, for that cycle (L8).
  **The hour's decision** (L4) is made at the first cycle within the first 60 seconds **from the hour's first quote**
  (the H1 open, or - after the daily break or the weekend - the reopening, which comes minutes into the H1 bar) - **as
  the runner knows it**, the earliest it can have been: the later of the H1 open and the **last pre-hour read** -
  the time, taken just before the request, of the last successful quote read of this process whose quote was stamped
  before the hour (the market had not yet quoted in the hour then); with no such read in this process, the H1 open.
  Only a successful quote read moves it (a failed quote read leaves it; a failure of another read does not touch it).
  A failed read, a pause or a start between that read and the hour's first quote read leaves the window counted from
  that earlier time, so a late recovery never opens a new 60 s; continuous cycles through the daily break or the
  weekend place the window at the reopening - at which placing
  is allowed (L7: the data fresh, the gate passing, the kill switch off, the terminal connected, nothing pending) and
  the close steps of every bar closed at that open are done - the H1 bar's visits and arming, its `exec_tf` bars'
  closes, and the grids, pivots and steps of the D1 / H4 bars and the month that start then (ZONE_RULES 3: the grid in
  force at the hour);
  if no such cycle comes by then, the hour is undecided - no candidates, no orders, its visits recorded `undecided`
  (a reserved hour excepted, L4)
  (L4), logged - and a decision is never made later in an hour.
- **The arming epoch**: the line arming (ZONE_RULES rule 4) is computed from closed H1 bars starting at `epoch` (L9;
  default 2023-10-01, the simulation's start) - the same arming the simulation computes on a run from that date - up
  to the last closed H1 bar, and kept up to date at each H1 close (L4). The grids, pivots, weekly ATR and monthly steps
  are computed as the simulation computes them - over the whole stored series from each file's first bar, each known
  by t (ZONE_RULES 2, 3); `epoch` limits only the arming. **A candidate's step `S`, line and prices are fixed at the
  hour's decision** for its whole life (the simulation plans a setup from its visit's grid); a later grid in force
  changes only later hours' candidates. The set's version is pinned at start; a change of the set in the database takes effect
  only at a restart (logged).

## L3. The setup's prices and orders [Claude]

- Prices (ZONE_RULES rule 6) are computed unrounded as in the simulation (the setup's **logic prices**), then sent
  rounded to the symbol's tick: P1 and P2 to the nearest tick; the SL rounded away from the entries (a BUY's SL, below
  them, rounded down; a SELL's, above, up) and the TP rounded toward them (a BUY's TP, above them, rounded down; a
  SELL's, below, up) - so P1 and P2 carry the same SL and the same TP. The stored setup row keeps
  both. (The parity check, L11, allows one tick.)
- Every order is a limit (`RequestBuilder.limit_entry`), `lot`, the magic, SL and TP attached, and the comment
  `Z<setup id>-<P1|P2>-<n>` - the setup id in decimal, at most 25 characters in all (`app/broker/execution.py`
  `COMMENT_MAX`); the setup id is the row's id. The start refuses if a setup id of 12 digits would not fit with
  `n` up to 999; a placement with `n` over 999 -> hands-off. **Reading a key**: `Z`, the setup id's digits,
  `-`, `P1` or `P2`, `-`, then `n` = the digits up to the first non-digit; text the broker adds after it (e.g.
  `[sl 95.00]`) is ignored. A comment that does not read as a key is not ours.
- **A broker expiry on every order** (the backstop if the runner dies): `ORDER_TIME_SPECIFIED`, at the close of the
  current H1 bar + 1 minute. Only the orders of an hour's setup are extended - in its own hour and every later hour until it
  ends (a candidate not yet the hour's setup is removed in its hour's pre-close window and never extended): from the first cycle at or after its current expiry
  minus 10 minutes (the H1 close - 9 minutes), the runner sets the expiry to the current expiry + 1 hour (an
  order modify - `RequestBuilder.modify_order`, `TRADE_ACTION_MODIFY`, the same price, SL, TP and the new expiry),
  retried each cycle while refused, without a cap (the 3-tries cap of L8 is for SL modifies; an order whose
  extension never takes expires and is placed again below) (the 1 and 10 minutes are fixed). A wanted order that expired anyway (its history
  state is expired) is placed again as the next placement (`n` + 1) - once that state is seen, so never beside a live
  one; an expired P1 first has its P2 removed, and both are placed again, P1 first (P2 never rests without P1). The runner never relies on the expiry for a rule; it removes orders itself. The symbol must allow specified
  expiry (`expiration_mode`); if it does not, the start is refused.
- **An order already marketable when placed** (BUY: ask <= P; SELL: bid >= P, on the cycle's quote, `P` the **sent**
  price - what the broker would fill; every rule of L4 - L5 tests the **logic** prices, as the simulation does) is sent as a market
  order (as `RequestBuilder` builds a market order: its deviation and the symbol's filling mode) with the same SL and
  TP instead of a limit. Its fill is a visit of its candidate (L4). It counts as **filled at its logic price P** in the
  setup's logic once the broker's deal exists; the broker's price is recorded beside it. No deal within one `exec_tf`
  bar -> hands-off. It is the only market entry. A marketable P2 is sent only after its P1 has filled (L4's order of
  placement).
- **P1 refused** (placing it, or its market form, gets a refusal): P2 is not placed, or is removed if it was; the
  candidate, before it is the hour's setup, ends `dropped` (`refused`, logged; no reservation; the other candidate
  keeps its orders); a P1 refused after its candidate became the hour's setup (any placement of it, the first included) -> hands-off
  (L8). **P2 never rests
  without its setup's P1 resting or filled.**
- **A new placement of a name** is sent only once every earlier placement of that name is known gone without a fill
  (its removal confirmed, its history state cancelled or expired, or its place request refused - it never existed) -
  never beside one whose removal is refused or of unknown outcome. A retry is always a new placement (`n` + 1).
- **Removing a setup's orders**: P2 first; P1 once the broker shows the P2 gone (removed or filled). A refused P2
  removal holds P1 back and is retried each cycle; a removal (of P1 or P2) still refused or of unknown outcome after
  one `exec_tf` bar -> hands-off (L8).

## L4. The hour - which lines rest orders (ZONE_RULES rules 4, 5) [Claude]

The simulation decides at the H1 bar's close which lines were visited, and simulates their setups from `j0`, the
hour's open. In real time, orders must rest from `j0`:

- **At the hour's decision** (L2: the first cycle within 60 s of the hour's first quote at which placing is allowed; the
  hour is the broker's H1 bar):
  - The open `o` is the forming H1 bar's open (L2). The grid is the one in force at the hour.
  - **The candidates**: on each side, the nearest **armed** line of the grid - BUY: the highest armed line `L < o`;
    SELL: the lowest armed line `L > o` (a line equal to `o` is no candidate, as in the simulation). Lines nearer `o`
    that are disarmed are passed over. Only these two can be the first visit of the hour on their side (to reach a
    farther line price crosses the nearer one first). **A farther line of a side has the nearer one's skip class**:
    the readings 5a, 5c and 5d (the visit's `mom_body`, `mom_median`, `mom_run`, `ema_dist`, `atr`, `share` -
    `find_visits` in `app/zone/core.py`, computed at the H1 bar `i` from the bars closed before it, and the side
    `sgn`; `mom_run` is compared with the
    grid's step) depend only on the hour and the side, never on the line, and 5b on the hour - so when the
    nearest armed line is skipped, every farther line of that side is skipped too, and the side has no setup that
    hour.
  - **The skips at the open**: when the hour is reserved (L6), the hour has no candidates (no rows, no orders); its
    visits are classified at the H1 close in the simulation's order like any other (`momentum` when 5a applies, else
    `busy`) - whether or not a decision cycle came (a reserved hour needs no decision). Else each
    candidate is read with the visit readings of the simulation for a visit at this hour and side (5a momentum, 5c
    abnormal, 5d the state - all from bars closed before the hour); a candidate that passes is **live** (a new row,
    its placements from `n` = 0) and gets its orders (L3) as L5 allows - a P1 blocked at `j0` (L5 rule 3) gets its
    first placement (`n` = 0) at the first bar it is not blocked, P2 with it. **P1 is always sent before P2**, and P2
    only once P1's place is `sent` or filled; a P2 already marketable is sent at market only after P1 has filled (it
    lies beyond P1, so P1 is then marketable too and fills first). A candidate that fails is **skipped**.
- **The candidates' order** (the simulation's rule 4 order): the earlier `exec_tf` touch bar, then the one nearer `o`,
  then the lower line.
- **The first visit of the hour**: the first quote **from the hour's decision on** with the bid within `Z` of a
  candidate - the decision cycle's own quote included (a candidate already within `Z` then is visited at once); before
  the decision there are no candidates, and a touch before it is an explained difference (L11) (BUY: bid <=
  L + Z; SELL: bid >= L - Z), or a deal of one of its orders (a fill means the bid reached it), whichever the runner
  sees first - the real order of the touches decides, also inside one `exec_tf` bar (where the simulation's fixed
  in-bar order may differ: an explained difference, L11). Both candidates seen in the same cycle: the candidates'
  order (the same touch bar: the nearer `o`, then the lower line). The candidates' order also decides L4's
  both-filled race (each candidate's touch bar there = the `exec_tf` bar of its first entry deal, by `time_msc`) and a
  touch the quotes missed (below).
  - The first visited candidate **live** -> it is **the hour's setup** (also when its life already ended before the
    visit by `no fill` or `cancel` - it keeps that outcome and reserves, L6; a candidate ended `interrupted`,
    `hands-off` or `restart` before its visit is never the hour's setup and that visit is recorded `undecided`; the
    hour's setup interrupted after its visit keeps its visit's record): the other candidate's orders are removed
    at once and it is `dropped`, and no other setup starts this hour (5b). Until the hour's close a candidate dropped
    this way (never one whose P1 was refused - that `dropped` is final at once) keeps following its bar loop (L5) with no orders, so that a missed touch (below) can still make it the hour's
    setup; at the hour's close its `dropped` is final.
  - The first visited candidate **skipped** -> nothing is reserved; the other candidate stays as it is, and its own
    visit (later, or in the same cycle second in the candidates' order) makes it the hour's setup if it is live (a
    skipped visit leaves the hour free, as in the simulation).
  - **Both live candidates filled before the runner removed one**: the hour's setup is the first in the candidates'
    order; the other candidate's positions are closed at market, its orders removed, its row ends `dropped`, logged at
    WARNING (an explained difference, L11: both touched between two cycles).
  - **A touch the quotes missed** (the bid came within `Z` between two cycles and no deal followed): at each `exec_tf`
    close the closed bar's bid low / high are checked against both candidates - except the bar in which the hour's
    decision was made, whose extremes may come from before the decision: in that bar no missed touch is looked for
    (only the touches seen in the quotes after the decision count). A missed touch found in a later bar is a visit
    in that bar. A missed touch of a **skipped** candidate changes nothing. A missed touch of a **live** candidate that comes
    first in the candidates' order before the runner chose the hour's setup (a skipped first visit is no choice; its
    bar earlier than the chosen one's, or the same bar and first by the order) makes it the hour's setup: it is no longer `dropped`; its orders are placed again as its life
    allows (the next placements; it has no fill - it had no orders since it was dropped); the other candidate's orders
    are removed, its positions closed at market, and it ends `dropped` whatever its life had reached (a `no fill` or
    `cancel` of it is replaced; it reserves nothing); the promoted candidate's placements wait until those closes are
    done (L7); logged at WARNING (`missed touch` - an explained
    difference, L11).
- **The hour's visits, recorded**: at each H1 close the runner computes the simulation's visits of that closed bar
  (`app.zone.core`, the function `find_visits` uses, with the runner's arming) - every line the bar visited, the
  farther ones too - and classifies each in the simulation's order: `momentum` (5a), `busy` (5b), `abnormal` (5c),
  `trend` (5d, the state), else the setup's outcome (`no fill`, `cancel`, `traded` - the simulation's names) - recorded at once as `setup` with
  the setup's id, and given its outcome when the setup ends (a setup still open at the end of a replay is compared
  with the simulation's `pending`, or `traded` with how `open`); a
  touch of a candidate dropped for a refused P1 `undecided`; a later visit in the hour of a candidate dropped for the
  other's visit `busy` (the simulation: the hour's setup holds the hour); in an hour that is not reserved and that the runner did not decide (placing not allowed through the
  60 s from its first quote, L2; started mid-hour; hands-off) every visit is recorded `undecided`, and in a decided hour every visit after
  an interruption (L7) or hands-off began in it is recorded `undecided` too (no fault; excluded from the parity
  check). A row
  per visit; a disagreement with what the runner did in a decided hour is logged at WARNING when it is one of L11's
  explained differences (the in-bar touch order, a missed touch, the bar boundary), else as a fault (ERROR). **The
  in-bar touch order** is recognised so: the hour's setup is one candidate, the simulation classes the other
  candidate's visit `setup`, and the two visits' touch bars (the `exec_tf` bar of each visit's first touch, as the
  simulation computes it) are the same bar. Then the row of the visit the runner traded carries the hour's setup id
  and its outcome whatever its class, and both rows are noted `in-bar touch order`.
- **The arming** is updated at each H1 close from that closed bar - **after** that bar's visits are computed, which use
  the arming as it stood before the bar - exactly as the simulation does: every line the bar
  visited (bid low / high within Z, open on the far side) is disarmed - ordered or not, live or skipped - and re-armed
  by the simulation's rule.
- **The end of the hour**: in the last `preclose_seconds` of the H1 bar, the orders of a live candidate not yet visited
  are removed (so none can fill in the next hour). A touch in that window still counts (found at the bar's close at
  the latest): the candidate is then the hour's setup and its orders are placed again at once as L5 allows (the next
  placements). A live candidate not yet ended and with no visit by the hour's close (judged after the close steps of the hour's last
  `exec_tf` bar, its missed-touch check included) ends `no fill` (one whose life already ended in
  the hour - a cancel - keeps that outcome). The hour's setup lives on (L5).

## L5. The setup's life, bar by bar (ZONE_RULES rules 6, 7) [Claude]

Every **live candidate** follows the simulation's bar loop (`step_setup`) from `j0` - before its visit too - so that the
setup the hour turns out to have is exactly the simulation's. "Removed" means its resting P1 / P2 orders are removed.

Before the setup's first fill, for each bar `j`, in the simulation's order:
1. **Expiry**: `j >= j0 + order_life_h x per_h` -> removed at the bar's open; outcome `no fill`.
   **Withdrawal**, only for `j > j0`: the bar's bid high (BUY) reaches `L + away_frac x S` / its bid low (SELL) reaches
   `L - away_frac x S` - at any moment of the bar, including its open -> removed at once; outcome `no fill` (the
   simulation applies it to the whole bar, before the fill tests). Judged on the quotes so far and again at the bar's
   close on its true high / low: a withdrawal the quotes missed ends the setup `no fill` at the close (its orders
   removed; a fill of it in that bar is closed as L5's other fills - an explained difference, L11).
2. **The closed-hour cancel**: `(close[j-1] - open[j-per_h]) x -sgn >= cancel_frac x S` -> removed at the bar's open.
   Its outcome is decided at the bar's close: `no fill` when the bar also met the withdrawal (j > j0), else `cancel`.
3. **The fill-moment block** (P1 only): `(P1 - open[j-per_h]) x -sgn >= cancel_frac x S` -> P1 is **blocked for bar
   `j`**: P1 and P2 removed (or not placed) for the bar. If during bar `j` the fill test of the blocked P1 is met (BUY:
   ask <= P1; SELL: bid >= P1) -> the setup is cancelled (its orders removed at once); its outcome is decided at the
   bar's close: `no fill` when the bar also met the withdrawal (j > j0), else `cancel` (the simulation tests
   withdrawal first). (The simulation's P2 block never changes
   an outcome: P2 lies beyond P1, P1 is tested first, and after the first fill no block applies - so P2 has no block
   of its own.)

- **The pre-close window**: a resting order can fill on the first tick of a bar, before the runner has seen the bar
  open. So in the last `preclose_seconds` (L9) of every `exec_tf` bar, the runner judges rules 1 - 3 for the next bar
  ahead at every cycle of the window, **for a setup with no fill only** - expiry and the block exactly (they use only
  known values), the closed-hour cancel with the cycle's bid as the coming close (the withdrawal is not judged ahead:
  it is judged on the quotes as they come) - and removes in advance every order those would remove; at the next
  bar's open, with the true values, an order that turned out allowed is placed again (the next placement). A fill
  inside the window that the true values would have forbidden is a bar-boundary difference (L11).

**Fills** are the broker's entry deals of the setup's orders: P1 and P2 each open a position with the setup's SL and
TP. **Deals are taken in time order** (`time_msc`; entries and exits together) - **at one time every entry first,
P1 before P2, then the exits - stops (SL, BE) before TP, then any other, then by deal ticket** (the simulation fills
before it tests exits, and tests the stop before the TP), whatever order the broker lists them in;
only then is it judged whether the setup ended. **A deal waits while an entry of its setup is pending** (a position
or a filled order of ours seen whose entry deal is not yet read): the buffered deals are judged together, in this order,
once it is read (placing stops meanwhile, L7; hands-off after one `exec_tf` bar, L8). **The setup's whole bar loop
waits with them**: its close steps (rules 1 - 3, the break-even, its exits) for the pending entry's bar and every later
bar run only once the entry is read, then bar by bar in order - so a break-even never counts fills it has not seen.
**Every other judgement of the setup waits too** - its interruption (L7, a `zone stop`, L10), a touch latched by
rule 3, its end - until the entry is read; the wait holds while the condition is unexplained, also when the position
disappears (L8: a broker condition ends only when it is explained). Removals for safety (L7, L8) do not wait, and
**hands-off does not wait**: it ends every setup not ended `hands-off` at once (L8), and nothing of the setup is judged
or acted on again - its buffered deals are recorded only (no fill judged, no close at market). **The setup's fills** are, in that order: the first fill of each name that the
life allows at its bar - P1 when rules 1 - 3 allow it, P2 once P1 has filled and before the break-even. A fill whose
judging needs a bar not yet read (rule 2 needs `close[j-1]`) waits until it is (L2 - its position keeps its broker SL
/ TP; placing waits, L7), then is judged at its own bar. **Any other
fill of the setup's orders** (a fill of a placement already removed or superseded, a second fill of a name, a fill
after the setup ended, a fill the rules of its bar forbid once that bar is read - a P1 in a blocked or withdrawn bar,
a P2 without its P1 filled, a P2 after the break-even) is closed at market at once and logged
- the bar boundary of L11 when it happened there, else a fault. Such a position is not part of the setup: the setup
keeps its own outcome (`no fill`, `cancel`, or its exit), its close is not the setup's exit, and the reservation is
the setup's own (L6). After the first fill, rules 1 - 3 no longer apply;
the unfilled P2 rests until the break-even or the end (removed by L7 meanwhile, it is placed again once L7 clears, as
the next placement - unless the setup has reached P2's refusal cap, L8).

At each `exec_tf` bar **close** `j`, with at least one position of the setup open:
4. **The break-even** (owner; rule 7), when `be_mode` is `entry` (`off`: none) and it is not yet on: `avg` = the mean
   of the setup's fills' logic prices, `mid = avg + be_frac x (TP - avg)` with the logic TP; BUY: `high[j] >= mid`; SELL: `low[j] +
   spread[j] x point <= mid` (`spread[j]` the closed bar's `spread` field in points - the same field the stored bars carry - `point` the
   symbol's) -> it is on at bar
   `j`, **once**: the BE stop is `avg + sgn x spread[j] x point` - unrounded in the logic (the BE exit price), sent rounded to the
   tick toward the TP side (the "beyond" test below and the broker use the sent stop) - fixed for the
   rest of the setup; the unfilled P2 is removed; the SL of every open position of the setup is modified to it
   (`modify_stops`).
   - **The price already beyond the BE stop** (BUY bid <= BE stop; SELL ask >= BE stop), checked by the runner on the
     cycle's quote before it sends the modify (and again before each retry): no modify is sent - that position is
     closed at market; the setup's exit is recorded as `BE` **at the BE stop price** in
     the setup's logic (the simulation's exit at bar `j + 1`), with the broker's price beside it.
   - Any other refusal of a position's modify, or an unknown outcome: judged by the broker's SL (L8) and retried each
     cycle; not in force after 3 tries (a try = one send of the modify for that position, the first included;
     refused or unknown alike) -> hands-off (L8: the
     position keeps its broker SL / TP - the owner, 2026-11-04: an SL that cannot be moved is out of our control).
   - **P2 removed ahead, BUY only**: the BUY trigger uses only the bid high, which can only rise during the bar, so
     the moment the bar's bid high so far reaches `mid` the unfilled P2 is removed - before the close, so it cannot
     fill on the next bar's first tick. A P2 filled in that bar before its removal took effect is the setup's fill
     (the simulation tests fills before the break-even). The BE itself is on at the close. A SELL P2 is removed at the
     close (its trigger needs the bar's spread); a SELL P2 filled after the BE bar's `close_time` and before the runner
     has read and processed that closed bar is a bar-boundary difference (L11), closed as L5's other fills.

**The exits** are the broker's (SL, TP or BE stop hit), read from the exit deals by position. How the setup exited =
the kind of its first exit deal: `TP` (deal reason TP); `SL` (deal reason SL while the position's stop in force was
the original SL); `BE` (deal reason SL while the stop in force was the BE stop - its modify confirmed - or L5's close
at the BE price); `close` (any other close by the runner - it has no logic exit price; only the broker's is recorded). The setup **ends at its exit**
when its last position has closed (its open volume is zero); **every order of the setup is then removed at once**.

## L6. The setup's end and the reservation (rule 5b) [Claude]

- Only **the hour's setup** makes a reservation, and only by `no fill`, `cancel` or its exit (ZONE_RULES 5b) - also when
  its life ended before its visit in the hour, as in the simulation, which simulates it from `j0`. Any other outcome
  (`dropped`, `interrupted`, `hands-off`, `restart`) and any candidate that is not the hour's setup reserve nothing.
  **While the hour's setup has not ended, every later hour is reserved.**
- **The reservation** lasts to the **`close_time` of the `exec_tf` bar in which the end happened** (a Friday exit
  reserves to that bar's `close_time`, not to Monday's open); for expiry (rule 1), the `close_time` of bar
  `j0 + order_life_h x per_h`. An hour whose open is at or before the reservation's end gets no orders (L4).
- An `open` outcome does not exist live: a setup is open until it ends.

## L7. What the runner never does, and when it stops placing

- No order without SL; no SL moved against a position (asserted before every modify: BUY new SL > old SL, SELL new SL
  < old SL).
- No market entry except L3's marketable order; no market close except those L4, L5 and L8 name.
- Never more than one setup's orders at a time, except the two candidates of an hour before its first visit (at most
  four orders). **Two setups' exposure** exists only in L4's race - both candidates filled between two cycles, or a missed touch
  giving the hour to the other candidate - and
  only until the loser's positions are closed (at once; hands-off if not done within one `exec_tf` bar).
- Never another magic's, another symbol's or another account's orders or positions.
- **Placing stops** while the gate fails, the kill switch is on (the system's kill switch, read every cycle), the
  terminal is not connected (`terminal().connected` false, or a broker call raises a connection error), the data is
  not fresh (L2), a close the runner owes is not done (L8), an order of the magic that is not wanted still rests
  (its removal not yet confirmed), or **any condition is pending that L8 turns into hands-off after one `exec_tf`
  bar** (causes 1, 2, 3 and 6: a place of unknown outcome, an order or a position of ours gone unexplained or filled
  without its entry deal, a removal,
  a close or a market entry not yet done) - each may still become exposure; and from a `zone stop` request on (L10).
  Managing goes on.
- **Resting orders are removed** (every unfilled order of the magic, no expiry extended) at once when the kill switch
  is on or the gate fails, and when the data has been stale - a lost connection included, the removals sent once it is
  back - for longer than one `exec_tf` bar while the market is open
  (the rules of L5 can no longer be judged; timed from the first stale cycle). A setup with a fill keeps its positions managed; a setup without a fill
  **ends `interrupted`** (no reservation); the next decision is at the next H1 open once all is clear (L2).

## L8. Records, unknown outcomes, hands-off and the start [Claude; hands-off the owner's, 2026-11-04]

- **The tables**, in the system's engine database (`ENGINE_DB_URL`, default `data/taa_engine.db`), created by a
  migration of the storage layer: `zone_live_setup` (one row per live candidate: account, server, set and version,
  hour, line, side, step, prices logic and sent, state, outcome, its fills (name, placement `n`, deal and position
  tickets, deal time, logic and broker price, volume), BE on and its bar and stop, exit (how, time, logic and broker
  price), reservation end), `zone_live_visit` (L4's visit records: hour, line, side, class, the setup id and its outcome when the class is
  `setup`), `zone_live_stop` (a
  `zone stop` request: requested at, by, `now`, acknowledged at - the runner writes the acknowledgement) and
  `zone_live_request` (one row per request: setup id, kind - place / remove / modify /
  close - name and `n` and the key for a place (unique; empty for the other kinds), state - `intent`, `sent`,
  `refused`, `unknown`, `moot` - broker order / position ticket, retcode, times). They are the record for the owner and for
  `zone status`; **the runner never rebuilds a setup from them** (the start below).
- **Write-ahead**: a request row is written `intent` before `order_send`, then `sent` (with the ticket) or `refused`
  (with the retcode) after it, in its own transaction. If the `intent` row cannot be written, nothing is sent. If the
  row after the send cannot be written, it stays `intent` and is judged as an unknown outcome (below).
- **An uncaught error inside a cycle** (the code, the store): logged at ERROR, the cycle ends, and the runner goes
  hands-off (it cannot know what that cycle left undone).
- **An unknown outcome**: `order_send` returned no result, or a retcode of the unknown class (a timeout, no connection -
  `RetcodeClass.UNKNOWN`); any other retcode is a refusal or a success.
  - **remove / modify / close** (they open nothing): judged by the broker's state of the ticket - a remove is done when
    the order is no longer open (its history state cancelled, or filled - then it is a fill to judge, L5); a modify of an SL is
    done when the SL is at the requested level or nearer the TP; a modify of an order's expiry when the expiry is at
    the requested time or later; a close is done
    when the position is gone. Not done -> sent again next cycle, within the caps of L8 (a removal, a close or a
    market entry not done within one `exec_tf` bar, an SL modify not in force after 3 tries -> hands-off). A target that no longer exists (the position closed,
    the order filled, cancelled or expired) ends the request (`moot`).
  - **place** (it can open exposure): **never sent again**. The row is `unknown` and is searched by its key every
    cycle in the open orders, the positions, the deals and the order history. Found -> it is that placement's order
    or fill, managed as any other (its row `sent` with the ticket; its ticket known from then on as an accepted
    one's, L8 causes 2 and 7) - found filled in the history, its entry deal is awaited as cause 2 says; found in the
    history expired -> it is gone without a fill (its row `moot`); found cancelled -> cause 7 (a cancel the runner
    did not request: the runner sends no remove for a placement it has not found). **Not found within one `exec_tf`
    bar -> hands-off.**
- **A close refused** (L4, L5): retried every cycle (placing stops meanwhile, L7); the position keeps its broker SL /
  TP; still not done after one `exec_tf` bar -> hands-off.
- **P2 refused** when P1 is placed: retried each cycle while P2 is wanted; 3 refusals in the setup (counted per setup, never reset) -> no further P2 placement in it; the setup goes on
  with P1 only (logged).
- **Hands-off** (the owner, 2026-11-04: *"let it go"*). **When**: at a start that finds the magic not flat (below);
  and while running, when the runner cannot know or cannot do what the normal case needs -
  1. a place of unknown outcome not found within one `exec_tf` bar;
  2. an order of ours that left the open orders without a history state or a deal explaining it, **or shown filled
     (in the history, or by a position of ours) without its entry deal read**, within one `exec_tf` bar;
  3. a position of ours gone without an exit deal explaining it, **or open without its entry deal read**, within one
     `exec_tf` bar;
  4. an order or a position of the magic that is not ours;
  5. a fill whose volume is not `lot` (a partial fill);
  6. a removal, a close or a market entry not done within one `exec_tf` bar (L3, L8), an SL modify not in force after 3
     tries (L5),
     a placement `n` over 999 (L3), a P1 refused after its candidate became the hour's setup (L3);
  7. **the owner acting by hand** on an order or a position of the magic (the owner: *"I watch the trades and take the
     risk myself"*; this rule confirmed by the owner, 2026-11-04: *"ตกลง"* - agreed): an exit deal that is neither SL nor TP (`DEAL_REASON_SL`, `DEAL_REASON_TP`) nor the
     runner's own close (a close request of the runner for that position, `DEAL_REASON_EXPERT`) - by hand
     (`CLIENT`, `MOBILE`, `WEB`) or the broker's stop-out (`SO`); a wanted order cancelled without the runner's remove request; a **resting order** of ours whose
     price, volume, SL, TP or expiry differs from the values the broker last accepted from the runner (a refused or
     pending modify changes nothing to compare); a **position** of ours whose volume, SL or TP differs from its fill
     and the values the broker last accepted from the runner (its open price is the broker's fill and is not
     compared - a market fill may slip); checked every cycle. The owner has taken over; the runner resumes when the magic is flat.
  8. an uncaught error inside a cycle (L8 above).
  **What**: placing stops; every resting order of the magic is removed (ours P2 before P1 of a key, the rest in any
  order; retried each cycle); **no position is touched** - each keeps its broker SL / TP and runs to its end at the
  broker - the runner sends no close, no modify and no break-even for it, and a `zone stop` changes nothing of it; every setup
  not ended ends `hands-off` (logged ERROR, shown in `zone status`). A position that is not ours is the owner's to
  close; `zone status` names it. **Until**: the magic is flat (a successful read: no order, no position). Then every
  request of the run is closed (`unknown` ones `moot`), its keys are no longer ours (anything of them that appears
  later is "not ours" - cause 4), and the runner starts anew: the first decision at the first H1 open after it (L4),
  with no reservation.
- **A broker condition ends only when it is explained** [Claude]: the conditions L8 times toward hands-off from the
  broker's state - a place of unknown outcome, an order or a position of ours not yet explained (gone, or filled /
  open without its entry deal), the stale data - end only when the state that explains them is read: the deal, the
  history state, a cycle whose every read succeeded and was fresh. The disappearance of what such a condition watches
  never ends it: an order or a position gone without its explanation stays under cause 2 or 3, timed from that
  condition's own start. A place of unknown outcome found (as an order, a position or a deal) is explained there; a
  position of it seen without its entry deal is a new condition (cause 3) timed from that sighting. A **request** (remove, modify, close, market entry) is done or `moot` exactly as above (a
  target that no longer exists ends the request); what that disappearance leaves unexplained - a position gone
  without its exit deal, an order gone without its history state - is a condition of its own under cause 2 or 3, timed
  from the disappearance. A timer is never restarted by another condition beginning or ending. The runner's own
  conditions keep their own ends (the kill switch off, the gate passing, a `zone stop` - L7, L10).
- **Safety first in each cycle** [Claude]: the stop deadline (L10) is checked at the very start of every cycle,
  before any store or broker read and whatever the reads give (an active `--now` is held in memory; reading a new stop
  request may fail without touching it). The removals owed (hands-off, a stop, the kill switch, a failed
  gate, the stale data, an order already judged not wanted in an earlier cycle) are sent right after the reads they need - the
  account (L1's pin) and the open orders, nothing else (a failure of any other read does not hold them back; a failure
  of these two -> next cycle) - before and apart from every other step (the removals this
  cycle's own steps find come after them); an error in another step (the bars, the arming, the visits, the decision)
  never holds them back (it is cause 8 for that cycle, logged).
- **The start** (every `zone run`, the first one and every restart): the broker's orders, positions and deals are read
  (a failed read is never an empty account: nothing is decided until a read succeeds); deals and history are read
  from the process's start on. Every unfinished row of the
  store ends `restart`, and every request of a previous process is closed (`intent` and `unknown` ones `moot`) - its
  keys are not ours, so anything of them that appears later is "not ours" (hands-off cause 4); any stop request left open by a runner that died is closed (logged - `zone run` is the owner's
  explicit start). If the magic is not flat -> hands-off until it is (its resting orders removed, its positions left to the broker;
  the rows of the previous process have already ended `restart`, so no row ends `hands-off` here); if it is flat, no
  hands-off. The arming is rebuilt from the closed H1 bars
  from `epoch` (L2). The first decision is at the first H1 open after the start (or after the flat book) - never in
  the middle of an hour - with no reservation: nothing of a previous process's rows (their reservation ends included)
  decides anything after a start.
- **A failed broker read is never an empty account**: if the positions, orders, deals, history, account or terminal
  cannot be read, the cycle does nothing that depends on them - no fill judged, no order placed, nothing marked gone,
  no gate failure assumed - and retries. A failed read makes the data not fresh at once (placing stops, L7), and
  L7's stale timer runs from the first failed read - one grace period of one `exec_tf` bar, not two.

## L9. Settings

The zone's parameters come from the zone set in `data/bot_config.db` (`--market`, `--set`; ZONE_RULES rule 1), version
pinned at start. The runner's own settings - `lot` (0.01, owner), `cycle_seconds` (2), `stale_quote_seconds` (30),
`preclose_seconds` (15), `epoch` (2023-10-01) - come from a `zone_live:` section of `config.yaml`, a model in
`AppConfig` (`app/config.py`; unknown fields are refused, as for every section) [Claude].

## L10. The command line [Claude]

- `python -m app.cli zone run --market XAUUSD --set default` - the mode from `.env`; runs until stopped.
- `python -m app.cli zone status` - the pinned account, hands-off or not, the hour's candidates, the setup, its orders
  and positions, the last requests, any order or position of the magic that is not ours.
- `python -m app.cli zone stop` - under hands-off: the runner exits once every order of the magic is removed (the
  positions are the broker's). Otherwise it writes a stop request (a row the runner reads every cycle) and waits up to 60 s for
  the runner's acknowledgement (else it says so and exits): every setup of the runner without a fill ends `interrupted` (no reservation; a setup with a pending entry waits
  until its entry is read, L5); the runner writes the acknowledgement once it has read the
  request and the broker confirms every unfilled order of the magic removed; it places nothing new; open positions are
  still managed (the BE, the exit, the leftover P2 removal) and the runner exits when none is open and no entry is
  pending (an unexplained one ends by L8: its deal read, or hands-off), or with `--now`
  as soon as the removals are confirmed (the positions keep their broker SL / TP and are the owner's). A removal not
  confirmed: the runner keeps retrying and managing (without `--now` it never exits early); `zone stop` reports it
  after its 60 s and exits itself; with `--now` the runner exits after 60 s, the order named in the log (it keeps its
  broker expiry), and the request stays unacknowledged.
  Ctrl+C in the runner's window = `zone stop`; a second Ctrl+C = `--now`.

## L11. Acceptance - what a build must show

1. **The move changes nothing**: the eye tests and the stored-bar acceptance (`ZONE_ACCEPT=1`) pass with only their
   imports and patch targets moved to `app.zone`; no assertion is changed; `eye/zone_bot.py` gives the same 109 setups
   with the same numbers (ZONE_RULES rule 12).
2. **The runner against the simulation** - a replay on stored bars, **uninterrupted runs only** (an interrupted run
   is hands-off by design):
   - A **replay broker** (a test double in `tests/`, not FakeMT5): it serves the runner the stored closed bars up to
     the replay time and the forming H1 bar's open; it drives the quote path of each `exec_tf` bar from its stored
     values: open -> the extreme nearer the open -> the other extreme -> close, walked in steps of one tick, the ask =
     bid + the bar's spread; it fills a limit at its price when the path crosses it (BUY: ask <= P; SELL: bid >= P), an
     SL at its price, a TP at its price, on the tick where the path crosses them, independent of the runner's cycles.
   - **Time**: the ticks of a bar are spread evenly over its period, the first at its open time, the last
     `preclose_seconds` / 2 before its `close_time`; the replay clock moves tick by tick. The runner's cycle runs in
     two modes, both required: after every tick (no polling gap) - and, through any gap between two ticks longer than
     `stale_quote_seconds` (the daily break, the weekend, a quiet market), every `cycle_seconds` of replay time, as the
     live runner keeps cycling (L2's last pre-hour read) -, and every `cycle_seconds` of replay time.
   - The runner runs on it unchanged (its clock and broker injected; the replay broker reports the server `FBS-Demo`,
     and the runner's store is the simulation's stored bars **cut at the replay's start**, so L2's start checks and
     freshness hold as on a live start; the replay starts a few seconds before an H1 open), on **one month, 2026-03,
     with the set's `exec_tf` (M15)** (the owner, 2026-11-07: *"run the replay on one month and compare it with the
     earlier result; if one month matches, assume it matches"*); before the set is switched to another `exec_tf`, that
     frame is replayed on the same month.
   - **Both ways**, from the runner's first decided hour on (an uninterrupted replay has no undecided hour after it;
     one that has any fails): every simulated visit - every line `find_visits` returns, farther lines included - has
     its runner record with the same classification (`momentum`, `busy`, `abnormal`, `trend`, or the setup's outcome), and every
     runner record has its simulated visit (the records come from L4's visits at the H1 close, not from the rows). For
     each setup: outcome and how (by the names of Words), visit hour, line, side, each fill (P1 / P2, its
     `exec_tf` bar and price), the BE (its bar and stop), the exit (bar, how, price), and the reservation end. Prices
     agree within one tick; bars exactly.
   - **The gate**: zero **unexplained** differences and no runner log line at ERROR or above. Each difference is
     listed with its bar and the path's facts (the ticks around it, the runner's decisions and the simulation's); the
     harness may *suggest* a cause, and the run is accepted only once each difference is explained by hand against
     those facts and recorded in `eye/BOT_RESEARCH.md`. The causes that can explain one (the list is closed): the order of touches inside
     one bar (the simulation's fixed in-bar order vs the path); the bar boundary (L5's pre-close window, and the time from a bar's `close_time` to the first
     cycle that has read and processed that closed bar, L2); a P2 placed after its P1 filled within the same bar (a marketable P1, or both placed
     again at a bar's open) and touched before it rested; L4's both-filled race (both candidates filled between two cycles); a missed touch (L4) in the polling
     mode; a withdrawal level or a BUY break-even level reached between two cycles (the polling mode - found at the
     bar's close, L5); a touch before the hour's decision placed the orders (L2); a SELL P2 filled before the BE bar's close was
     processed (L5); the tick rounding (L3) - an extreme within one tick of a price; **a TP inside the fill bar** (the broker's TP
     fires on any tick; the simulation counts a TP only on a bar after every fill). The setups after a difference must
     agree again once its reservation has ended.
   - **The broker-side checks**, unconditional: every entry's symbol, type, side, lot, magic, key, price, SL, TP and
     expiry; no place request sent twice; never two live placements of one name; P2 never resting without its P1
     resting or filled; never two setups' exposure beyond L4's race (L7); no order resting after its setup's end (beyond the bar boundary);
     every market close justified. **The comparisons** (every fill, exit and stop move against the simulation, both
     ways, and the end state) are judged with the explained differences above. The exact cycle at which an
     order is placed or removed is checked by the unit tests (3), not by the replay.
3. **Unit tests** on FakeMT5 or the replay broker:
   - the hour: the candidates at the open (nearest armed, a disarmed nearer line passed over, equality to the open, a
     reserved hour, a stale hour - no orders); the first visit removes the other candidate's orders; a skipped first
     visit leaves the other; both filled -> the loser by the candidates' order closed, the deals also in reversed order
     and at equal distance (the lower line); a missed touch found at the bar's close;
   - the life: rules 1 - 3 each at the bar the simulation applies them (the closed-hour cancel before any visit; no
     withdrawal in `j0`; a blocked P1 touched on the bid but not the ask does not cancel; a P1 blocked at `j0` placed
     at the first unblocked bar); the withdrawal and the closed-hour cancel in one bar -> `no fill`; the pre-close
     window removes and re-places; a marketable order; the fills - a second fill of a name, a fill of a superseded
     placement, a fill after the end, a P2 without P1, a P2 after the BE: each closed;
   - the BE once, both SLs, P2 removed (BUY ahead, a P2 filled in the trigger bar kept), the price already beyond the BE stop closed at the
     BE price in the logic, three other refusals -> hands-off (no market close, the broker SL / TP kept); the leftover P2 removed when the last position closes;
   - the reservation end (an exit inside a bar reserves to its `close_time`, equality blocks; a Friday exit does not
     block Monday's open; expiry);
   - a pending entry: P1's position seen with its entry deal not yet read and P2's deal read - P2 waits, then both are
     the setup's fills;
   - a pending entry across a bar close: P2's position seen before the close, its deal read after it - the break-even
     of that bar judged with both fills (`be_frac` 0.5; BUY P1 110, P2 85, TP 176, high 140: on with both, mid 136.75; off with P1
     alone, mid 143);
   - the deal order: P2's entry and P1's exit at the same `time_msc` (a gap through P2 and the SL), listed by the
     broker in either order - P2 is the setup's fill, then both exits;
   - the rules of this file, each named: a closed bar read late (its close steps wait; a fill meanwhile judged at its
     own bar); no missed touch from the decision's own bar; a decision only within 60 s of the hour's first quote (a reopening hour decided at its first quote); a new placement only after the
     earlier one is known gone; the touch in the end-of-hour window re-placing; an expired P1 with its P2;
   - the requests: write-ahead with a crash before the send and after the broker accepted; a place of unknown outcome
     found in a later cycle (managed, never sent twice) and not found within one bar (hands-off); a remove and a modify
     of unknown outcome judged by the ticket's state; the expiry set and extended each hour, an expired wanted order
     placed again; P1 refused (no P2 alone); P2 refused three times; a P2 removal refused (P1 held; hands-off after one
     bar); a close refused (placing stopped; hands-off after one bar); a modify refused three times (hands-off);
   - hands-off: each of its eight causes (the owner's hand: a manual close, a manual cancel, a pending order's price, SL, TP or expiry changed, a position's SL or TP changed; and a slipped market fill that is NOT hands-off); every order removed, no position touched, rows ended `hands-off`, the first
     decision at the first H1 open after the book is flat;
   - the start: an empty store and a flat magic (the first decision at the next H1 open); unfinished rows ended
     `restart`; orders or positions of the magic at start (hands-off); a failed first read (nothing decided);
   - a failed read: healthy quotes but failing account / terminal / history reads - placing stops at once, resting
     orders removed after one `exec_tf` bar;
   - the account and the gate: an account switch stops everything; a netting account refused; the gate evaluated fresh
     before each place (LIVE without the two `.env` values refused; no day plan needed); the kill switch, a lost
     connection and stale data stop placing but keep managing, and remove resting orders as L7 says; a second runner
     refused; `zone stop` acknowledged and nothing placed after it; PAPER / BACKTEST refused; the key read with broker
     text after it.
4. **Independence**: `app/zone` imports nothing from `eye/` nor from the Fibonacci bot; the runner imports nothing from
   `app/engine/orchestrator`, the decision engine, the checklist, arbitration or the strategies (a test reads the
   imports).
5. **Gates**: ruff, mypy, bandit, the architecture test, the full suite.

## L12. Not in this build

The web / PWA view, alerts outside the log, several symbols, sizing other than the fixed lot, runs on DEMO (`zone run` accepts
`TRADING_MODE=DEMO` - the code supports it - but this build is not tested there; the owner: no DEMO), carrying a setup across a restart or managing (the break-even, closes) positions left at a restart or under
hands-off (the owner, 2026-11-04: out of our control - the broker's SL / TP). Turning LIVE on is the owner's: the two
`.env` values, then the owner's word to start the runner (CLAUDE.md).
