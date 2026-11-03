# The run-zone setup on the broker - the specification

**What this is**: the real-time runner that trades the run-zone setup of `eye/ZONE_RULES.md` on the MT5 account,
through the system's existing broker layer and its LIVE gate. The rules are ZONE_RULES.md's - **this file adds only
how they run in real time**; where a rule is not restated here, ZONE_RULES.md holds. The simulation (`eye/zone_bot.py`,
`simulate_setup`, `find_visits`, `apply_rules`) is the reference the runner must agree with (L11).

The owner (2026-11-02): *"put it on LIVE once it is done"*; *"0.01, no DEMO"*; *"I watch the trades and take the risk
myself"*; *"the system already sends orders to MT5 - you only have to make it use our zone setup correctly"*.
Each rule says whose it is: **(owner)** or **[Claude]** (a form the owner did not give, for the owner to change).

Words: `sgn` +1 BUY / -1 SELL; `S` the step of the grid in force; `Z = near_frac x S`; `per_h` the `exec_tf` bars in an
hour; `j` an `exec_tf` bar, `j0` the first `exec_tf` bar of the hour; a bar's `close_time` = its open + its
period (the stored value the simulation uses); "at a bar's close" = at the first cycle after its `close_time`.
Every comparison below is the simulation's, with the same `>=` / `<=`.

## L0. Shape - one logic, two drivers [Claude]

- **One logic**: the pure zone logic of `eye/zone_bot.py` (the step, the grids, the arming, the visits' readings, the
  skips, the setup's prices and its bar-by-bar life) and `eye/zone_config.py` (`ZoneParams`, the parameter database)
  move into a new package **`app/zone/`**: `params.py` (zone_config's content), `core.py` (zone_bot's logic - no
  broker, no clock, no file writes). `eye/zone_bot.py` keeps its command line, its outputs and charts and imports the
  logic from `app.zone.core`; `eye/zone_config.py` keeps its command line and re-exports `app.zone.params`.
- The bar-by-bar life of a setup is written once, as a step function in `core.py`: given the setup's state after bar
  `j-1` and bar `j`'s values, it returns the state after bar `j` (fills, exit, break-even, withdrawal, cancels).
  `simulate_setup` loops it over stored bars; the runner uses the same function's pieces for its decisions at each
  bar's open and close (L5). No second copy of a rule.
- **Two drivers**: the simulation (`eye/zone_bot.py`) and the runner **`app/zone/trader.py`** (real time, broker
  orders), with its state store `app/zone/store.py`.
- `tests/unit/test_architecture.py` `LAYERS`: `app.zone` 6 (pure, like strategies; may import `app.core`,
  `app.indicators`), `app.zone.store` 10, `app.zone.trader` 10 (may import `app.broker`, `app.risk`, `app.storage`,
  `app.config`, `app.market_data`); `docs/archive/CODING_STANDARDS.md` notes the change, as the test asks.
- **Not the strategy engine**: the runner does not use `app/engine/orchestrator.py`, the decision engine, the
  checklist, arbitration, the breakers or the risk sizer (rule 0 of ZONE_RULES: a setup of its own). It uses: the
  broker factory (`build_trading`), `evaluate_gate` (`app/risk/mode_gates.py`), the `ExecutionGateway` and
  `RequestBuilder`, the read-only market-data gateway, `ServerClock`, the kill switch, and the storage layer.

## L1. Modes, the gate, the account (owner; the system's rules)

- `TRADING_MODE` LIVE or DEMO from `.env`; PAPER / BACKTEST refuse to start the runner.
- LIVE needs `ENABLE_LIVE_TRADING=true` and `LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-<MT5_LOGIN>` - **set by the
  owner**, never by code or by Claude.
- **Before every request that can open exposure** (placing an order) the runner evaluates `evaluate_gate` on **fresh**
  `gateway.account()` / `gateway.terminal()` snapshots (`risk_config_ok` = the runner's settings validated at start;
  `kill_switch_active` = the kill switch; `latched_breakers` = none - the engine's breakers do not run here;
  `day_plan_ok` = True, detail "zone runner: no day plan" - **the owner, 2026-11-02: the zone runner does not use the
  day plan** (*"not used"*); the zone has its own market filters (5c, 5d) and the owner watches the trades). A
  failed gate: no order, a log line, the reason written.
- **The account is pinned**: at start the runner records the account login and server; a fresh snapshot with another
  login or server stops all new orders and alerts in the log until a restart (resting orders of the pinned account
  are not touched from another account). Every stored row carries the login and server.
- **One symbol**: XAUUSD (the market of the set). **Lot 0.01 a position, fixed** (owner) - `lot` (L9), refused at start
  unless `volume_min <= lot <= volume_max` and a multiple of `volume_step`.
- **Magic**: one number reserved for the zone runner in `app/engine/magic_registry.py`; the runner reads and touches
  only orders and positions of XAUUSD with that magic, on the pinned account.
- **One runner**: an exclusive lock (a lock file under `data/`, held for the process's life) - a second runner refuses
  to start.

## L2. Bars and quotes in real time [Claude]

- At start: the stored bars (`data/history/FBS-Demo/XAUUSD`, the files the simulation reads) are loaded, and each
  frame (D1, H4, H1, M15 - always, the state gate reads it - and M5 when it is `exec_tf`) is brought up to date with the broker's **closed** bars through the read-only
  gateway; the runner keeps them in memory and appends each newly closed bar (it may also write them to the store
  through `history_store`'s merge).
- Every cycle (`cycle_seconds`): the quote (bid, ask, time) and the bars closed since the last cycle. The forming bar
  is never used, except the **open of the forming H1 bar** (L4 - its side) read from the broker's current H1 bar.
- **Fresh data**: new orders only when the quote is younger than `stale_quote_seconds` and every frame's last closed bar
  equals the broker's last closed bar of that frame (the runner is not behind the broker). The weekend close and the
  reopening are not stale by this test. Stale -> no new order, a log line; resting orders and positions are still
  managed (L5).
- **The arming epoch**: the line arming (ZONE_RULES rule 4) is computed from closed H1 bars starting at `--epoch`
  (default 2023-10-01, the simulation's start) - the same arming the simulation computes on a run from that date.
  Grids and pivots use the whole stored series, as the simulation does. The set's version is pinned at start; a
  change of the set in the database takes effect only at a restart (logged).

## L3. The setup's prices and orders [Claude]

- Prices (ZONE_RULES rule 6) are computed unrounded as in the simulation, then sent rounded to the symbol's tick:
  P1 and P2 to the nearest tick, SL to the tick farther from the entry, TP to the tick nearer the entry. The stored
  setup row keeps both. (The parity check, L11, allows one tick.)
- Every order is a limit (`RequestBuilder.limit_entry`), `lot`, the magic, SL and TP attached, and a comment
  `Z<setup id>-<P1|P2>-<n>` (`n` counts re-placements) - unique, the key that ties a broker order, deal or position
  to its row.
- **A broker expiry on every order** (a backstop if the runner dies): `ORDER_TIME_SPECIFIED`, expiring at the close of
  the current H1 bar + 1 minute; while the order is still wanted the runner extends it by one hour from 10 minutes
  before it (an order modify - a `RequestBuilder.modify_order` added in `app/broker`, `TRADE_ACTION_MODIFY` with the
  same price, SL, TP and the new expiry), retried each cycle if refused. A wanted order that expired anyway (its
  ticket's history state is expired) is placed again under a new comment (`n` + 1) - only once that state is seen,
  so never beside a live one. The runner never relies on the expiry for a rule; it removes orders itself. The symbol
  must allow specified expiry (`expiration_mode`); if it does not, the runner refuses to start and says so.
- **An order already marketable when placed** (BUY: ask <= P; SELL: bid >= P - the price is already through it) is
  sent as a market order with the same SL and TP instead of a limit. It counts as **filled at the order's price P in
  the setup's logic** (as the simulation fills it) only once the broker's deal exists; the broker's price is recorded
  beside it. This is the only market entry.
- **P1 refused** (placing it, or its market form, gets a refusal): P2 is not placed, or is removed if it was; the
  candidate is dropped for the hour (`refused`, logged). P2 never rests without P1 placed or filled.

## L4. The hour - which lines rest orders (ZONE_RULES rules 4, 5) [Claude]

The simulation decides at the H1 bar's close which lines were visited, and simulates their setups from `j0`, the
hour's open. In real time, orders must rest from `j0`:

- **At each H1 open** (the first cycle at or after the open of the new H1 bar; the hour is the broker's H1 bar):
  - The open `o` is the forming H1 bar's open (L2). The grid is the one in force at the hour.
  - **The candidates**: on each side, the nearest **armed** line of the grid - BUY: the highest armed line `L < o`;
    SELL: the lowest armed line `L > o` (a line equal to `o` is no candidate, as in the simulation). Lines nearer `o`
    that are disarmed are passed over. Only these two can be the first visit of the hour on their side (to reach a
    farther line price crosses the nearer one first, which is disarmed - no visit - or armed - the candidate).
  - **The skips at the open**: when a setup is reserved (L6), neither candidate gets orders this hour. Else each
    candidate is read with the visit readings of the simulation for a visit at this hour and side (5a momentum, 5c
    abnormal, 5d the state - all from bars closed before the hour); a candidate that passes is **live** and gets its
    P1 and P2 orders (L3), unless the fill-moment block (L5) holds at `j0`. A candidate that fails is **skipped**.
- **The first visit of the hour**: the first quote of the hour with the bid within `Z` of a candidate (BUY: bid <=
  L + Z; SELL: bid >= L - Z), or a deal of one of its orders (a fill means the bid reached it), whichever the runner
  sees first. Both candidates seen in the same cycle: the one with the earlier `exec_tf` touch, then the one nearer
  `o` (rule 4's order).
  - The first visited candidate **live** -> it is **the setup**: the other candidate's orders are removed at once and no
    other setup starts this hour (5b).
  - The first visited candidate **skipped** -> nothing is reserved; the other candidate stays as it is (in the
    simulation a skipped visit leaves the hour free).
  - **Both live candidates filled before the runner removed one** (two deals): the later deal's position is closed at
    market and its orders removed; a log line names it as a fault. (The two P1s are at least `S - 2Z` apart.)
  - **A touch the quotes missed** (the bid came within `Z` between two cycles and no deal followed - a BUY touch inside
    the spread below P1): at each `exec_tf` close the closed bar's low / high are checked against both candidates. A
    touch found there is a visit in that bar. A missed touch of a **skipped** candidate changes nothing (a skipped
    visit leaves the hour free). A missed touch of a **live** candidate that makes another first visit than the
    runner chose (its bar is earlier than the chosen one's, or the same bar and nearer `o`), or that comes before any
    chosen visit, makes it the hour's setup: the other
    candidate's orders are removed, and a position of the other candidate is closed at market, logged as a fault
    (`missed touch`).
- **The hour's visits, recorded** [Claude]: at each H1 close the runner computes the simulation's visits of that
  closed bar (`app.zone.core`, the same function `find_visits` uses, with the runner's arming) - every line the bar
  visited, the farther ones too - and classifies each in the simulation's order: 5a momentum, then 5b busy, 5c
  abnormal, 5d the state, else the hour's setup. The record (a row per visit) must agree with what the runner did
  in the hour (the setup it followed, the candidates it skipped); a disagreement is logged as a fault.
- **The arming** is updated at each H1 close from that closed bar, exactly as the simulation does: every line the bar
  visited (bid low / high within Z, open on the far side) is disarmed - ordered or not, live or skipped - and re-armed
  by the simulation's rule.
- **The end of the hour**: in the last `preclose_seconds` of the H1 bar (L5's pre-close window), the orders of a
  candidate not yet visited are removed; a touch in that window still makes it the hour's visit (L4, found at the
  bar's close at the latest). At the next H1 open the decision is made again (if the candidate is again the
  nearest armed line and passes, the same prices are placed again under the new hour's setup row). A visited live
  candidate is the setup and lives on (L5).

## L5. The setup's life, bar by bar (ZONE_RULES rules 6, 7) [Claude]

Every **live candidate** follows the simulation's bar loop from `j0` - before its visit too - so that the setup the hour
turns out to have is exactly the simulation's. "Removed" means its resting P1 / P2 orders are removed.

For each bar `j`, before any fill of the setup, the simulation's order (`simulate_setup`): (1) expiry, then
withdrawal, (2) the closed-hour cancel, (3) the fill tests with the fill-moment cancel:
1. **Expiry**: `j >= j0 + order_life_h x per_h` -> removed at the bar's open; outcome `no fill`.
   **Withdrawal**, only for `j > j0`: the bar's bid high (BUY) reaches `L + away_frac x S` / its bid low (SELL) reaches
   `L - away_frac x S` - at any moment of the bar, including its open -> removed; outcome `no fill`.
2. **The closed-hour cancel**: `(close[j-1] - open[j-per_h]) x -sgn >= cancel_frac x S` -> removed at the bar's open.
   Its outcome is decided at the bar's close: `no fill` when the bar also met the withdrawal (j > j0) - the simulation
   tests withdrawal first - else `cancel`.
3. **The fill-moment block**: for P1 and for P2, `(P - open[j-per_h]) x -sgn >= cancel_frac x S` -> that order is
   **blocked for bar `j`**: removed (or not placed) for the bar. If during bar `j` a fill test of a blocked P1 is met
   (BUY: ask <= P1; SELL: bid >= P1) -> the setup is cancelled; outcome `cancel`. A blocked P2 alone never cancels; it is
   placed again as soon as P1 fills during the bar (the simulation allows P2 after P1 in the same bar), or at the next
   bar's open if not blocked then.
- **The pre-close window** [Claude]: a resting order can fill on the first tick of a bar, before the runner has seen
  the bar open. So in the last `preclose_seconds` (default 15) of every `exec_tf` bar, the runner judges rules 1 - 3
  for the next bar ahead - expiry and the blocks exactly (they use only known values), the closed-hour cancel with
  the current bid as the coming close - and removes in advance every order those would remove; at the next bar's
  open, with the true values, an order that turned out allowed is placed again. A candidate's orders are also removed
  in the last `preclose_seconds` of the H1 bar (L4's end of the hour). A fill inside the window that the true values
  would have forbidden is a difference to explain by that tick (L11).

**Fills** are the broker's deals (by the comment, L3): P1 and P2 each open a position with the setup's SL and TP.
After the first fill, rules 1 - 4 no longer apply (the simulation's `if not fills`); an unfilled P2 rests (blocks no
longer apply) until the break-even or the end.

At each `exec_tf` bar **close** `j`, with at least one position open:
5. **The break-even** (owner; rule 7), when `be_mode` is `entry` and it is not yet on: `avg` = the mean of the setup's
   fill prices (the setup's logic prices), `mid = avg + be_frac x (TP - avg)`; BUY: `high[j] >= mid`; SELL: `low[j] +
   spread[j] x point <= mid` -> it is on, **once**: the BE stop is `avg + sgn x spread[j] x point` (rounded to the tick
   toward the TP side), fixed for the rest of the setup; the unfilled P2 is removed; the SL of every open position
   is modified to it (`modify_stops`).
   - A modify refused because the price is already beyond the BE stop (BUY bid <= BE stop; SELL ask >= BE stop): the
     position is closed at market; the setup's exit is recorded as `BE` **at the BE stop price** in the setup's
     logic (the simulation's exit at the next bar), with the broker's price beside it.
   - Any other refusal: retried each cycle; after 3 refusals the positions are closed at market, logged as a fault.
   - **P2 removed ahead, BUY only**: the BUY trigger uses only the bid high, which can only rise during the bar, so
     the moment the bar's bid high so far reaches `mid` the trigger is certain and the unfilled P2 is removed at
     once - before the close, so it cannot fill on the next bar's first tick. The SELL trigger depends on the bar's
     spread, known only at the close, so a SELL P2 is removed at the close. The SL move itself waits for the close
     (the simulation's stop moves from the next bar).

**The exits** are the broker's (SL, TP or BE stop hit), read from the deals. The setup's exit = the first exit deal;
how = `SL`, `TP`, or `BE` (the stop after the break-even). **When the last position closes, every order of the setup is
removed at once** (an unfilled P2 never outlives its setup). Two positions closed by different kinds in one bar: the
setup's how is the first deal's.

## L6. The setup's end and the reservation (rule 5b) [Claude]

- A setup ends at its outcome: `no fill`, `cancel`, or its exit (the last position closed). Only **the hour's setup**
  (the first visited live candidate, L4) makes a reservation - also when its life ended (a cancel, a withdrawal) before
  its visit in the hour, as in the simulation, which simulates it from `j0`. A live candidate never visited makes none.
- **The reservation** lasts to the **`close_time` of the `exec_tf` bar in which the end happened** (its open + the
  period - a Friday exit reserves to that bar's `close_time`, not to Monday's open) - for expiry (rule 1) the bar
  `j0 + order_life_h x per_h` itself, as in the simulation. An hour whose open is at or before the reservation's end
  gets no orders (L4).
- An `open` outcome does not exist live: a setup is open until it ends.

## L7. What the runner never does

- No order without SL; no SL moved against a position (asserted before every modify: BUY new SL > old SL, SELL new SL
  < old SL).
- No market entry except L3's marketable order and the closes of L4 and L5.
- Never more than one setup's orders at a time, except the two candidates of an hour before its first visit (at most
  four orders, two setups' worth, never two filled - L4).
- Never another magic's, another symbol's or another account's orders or positions.
- No order while the gate fails, the kill switch is on, the connection is down, or the data is stale; positions are
  still managed, and removing an order, the BE modify and the closes of L4 / L5 are always allowed.
- **Resting entries are removed** (every unfilled P1 / P2 of the magic, no expiry extended) when the kill switch is on
  (as the system's `PlanSupervisor` does), when the gate fails, and when the data has been stale for longer than one
  `exec_tf` bar (the rules of L5 can no longer be judged). They are placed again by the normal rules once all is
  clear - a setup whose rules still allow its orders gets them back; a candidate only at the next hour's decision.
  A candidate whose orders were removed this way (`interrupted`) cannot become the hour's setup: a touch of it in
  the rest of its hour is recorded (a visit of an interrupted candidate, logged) and reserves nothing.

## L8. State, failures and restart [Claude]

- **The tables**, in the system's engine database (`ENGINE_DB_URL`, default `data/taa_engine.db`), created by a
  migration of the storage layer: `zone_live_setup` (one row per live candidate: account, server, set and version,
  hour, line, side, step, prices unrounded and sent, state, fills, BE on and stop, exit, outcome, reservation end) and
  `zone_live_request` (one row per request: setup id, comment, kind - place / remove / modify / close - state, broker
  order / position ticket, retcode, times). The comment is unique.
- **Write-ahead**: a request row is written `intent` before `order_send`, then `sent` (with the ticket) or `refused`
  (with the retcode) after it, in its own transaction.
- **An unknown outcome** (no reply, a timeout, a crash between intent and the answer) - by the request's kind:
  - **place** (a limit or the marketable market order - can open exposure): **never sent again**. The row stays
    `intent` and is searched by its comment every cycle in the broker's open orders, positions, order history and
    deals since the intent's time. Found -> `sent` with the ticket (a deal -> the fill is recorded), and from then on
    managed like any order of the setup (removed when the setup's rules say so). Never found while the setup lives ->
    the setup goes on without that order; at the setup's end the search goes on for one more hour, then the row is
    `unseen` (logged). A setup missing its P1 this way gets no P2 (L3).
  - **remove / modify / close** (they carry no comment): judged by the broker's state of the ticket - a remove is
    done when the order is no longer open (history state cancelled, or filled - then the fill is recorded); a modify
    is done when the position's SL (or the order's expiry) equals the request's; a close is done when the position
    is gone. Not done -> sent again (these are safe to repeat: they open nothing). **A target that no longer exists**
    (the position closed, the order filled, cancelled or expired) ends the request as `moot` - never retried; what
    happened to the target (the exit, the fill) is recorded from the deals and the history.
- **Partial results**: P1 accepted and P2 refused -> P2 is retried each cycle while the setup allows it (a refusal 3
  times -> the setup goes on with P1 only, logged). P1 refused -> L3. **A close refused** (L4's later fill, L5's BE
  fallback, any close the rules require): retried every cycle until the position is gone - the position keeps its
  broker SL / TP meanwhile; every third refusal is logged as a fault; a close is never given up. A remove refused -> retried each cycle. **A fill the setup's logic does not
  allow** - an order that fills after its setup ended (cancel, withdrawal, expiry, its exit), after the break-even
  removed P2, while blocked (L5 rule 3), or of a candidate the hour no longer allows - is closed at market at once and
  logged (a fault, or the bar boundary of L11 when it happened there); it is never part of a setup. One of
  two BE modifies refused -> L5's refusal rule for that position. A partial fill (volume below `lot`) is a position of
  that volume, recorded; the order's rest is removed.
- **A restart starts fresh from the next hour** (the owner, 2026-11-03: *"ข. เริ่มใหม่ชั่วโมงถัดไป"* - a restart
  begins again from the next hour; the runner does not try to carry on as if it had never stopped). After a restart
  the runner may miss setups the simulation trades, or keep a fill the simulation would not have had - that is the
  owner's choice; parity with the simulation (L11.2) is required for uninterrupted runs only.
  - **Two kinds of work.** *Managing* - reconciling requests, removing orders, owed closes, the BE, reading exits -
    runs every cycle from the first one and is never held back by anything else (one refused removal never stops an
    owed close or a BE). *Placing* a new order is allowed only once the **barrier** below is passed.
  - **The barrier** (placing waits for all of it): a successful read of the broker's orders, positions, deals and
    order history of the magic (a failed read is never an empty account); every `place` intent from before the
    restart reconciled by its comment (found, or `unseen` one hour after the restart - never re-sent); **no resting
    order of the magic** at the broker; and the next H1 open reached. The first decision is made at the **first H1
    open after the barrier has passed** - never in the middle of an hour (a barrier passed at 11:30 -> the first
    decision at 12:00).
  - **A late arrival**: an order or position of the magic that appears at any time after the restart with the
    comment of a place sent before the restart (an `unseen` intent that shows up late) belongs to no live setup: the
    order is removed at once, a fill of it is a disallowed fill (L8) - closed at market - unless it is a position of
    a setup still being managed for its positions (below), and logged. New orders are not placed while such an order
    is resting (it is an unwanted order, L7).
  - **A stop move never worsens**: before any SL modify - new, retried, or one of unknown outcome being judged -
    the broker's current SL of the position is read; if it is already at the requested level or better for the
    position, nothing is sent and the request is done. A retried modify never moves a stop back.
  - **Requests of unknown outcome** from before the restart follow the rules above by kind: a place is reconciled by
    its comment and never re-sent; a remove / modify / close is judged by its ticket's state and sent again if not
    done (`moot` if the target is gone).
  - **Resting orders**: every resting order of the magic is removed, **P2 before P1** of the same setup; a refused
    removal is retried every cycle. An order that fills before its removal is confirmed is judged as a fill below.
  - **Fills and exits while down**: the deals since the setup's last recorded state are read by comment; entry deals
    and exit deals of a setup's own placed orders (a place row of that setup was `sent`, or its intent reconciled)
    are recorded at their times, whatever the row said - so a setup whose positions filled and closed while down
    ends with those exits (how, price, time). If the broker history no longer shows them, the row's last state
    stands (logged).
  - **Which setup a position belongs to**: an open position of the magic belongs to a setup only if its comment is
    one of that setup's placed orders. If that setup was still unfinished at the restart, the position is kept and
    managed (the owner's choice above - a fill while down is not re-judged against the bars). If the setup had
    already ended before the restart (cancel, withdrawal, expiry, its exit), the fill is a disallowed fill (L8) -
    closed at market. A position whose comment is no placed order of any row of this account is a stray: left as it
    is and named in the log and in `zone status` (never adopted, never closed without the owner).
  - **A setup with open positions** goes on for those positions only: no new fill (its orders are removed); its
    exits from the deals; **its break-even** (L5 rule 5), when not yet on: the `exec_tf` bars from the bar of its
    first fill up to the last closed one are judged in time order, each bar against the fills made at or before it
    (`avg` of those fills - the row's logic prices, the broker's open price where the row has none), with the
    parameters of the row's own set version. If a bar triggers it, the BE is on from that bar: the BE stop is set
    (if the broker's SL is already at it or better for the position, nothing is sent and the BE is recorded on; if
    the price is already beyond it, L5's refused-modify rule - closed at market), and a position whose fill came
    after the trigger bar is a disallowed fill (L5 removed P2) - closed at market. The setup ends when its last
    position is gone; its reservation (L6) runs to the `close_time` of the bar of that last exit.
  - **Every other unfinished row** ends at the restart, outcome `restart` (logged). A row that was the chosen setup
    of its hour keeps L6's reservation: to the `close_time` of the `exec_tf` bar in which the restart came (L6 is
    inclusive: a visit at or before it is busy). A candidate that was never chosen makes no reservation (L6).
  - **The hour of the restart**: its candidates from before the restart can no longer become the hour's setup (like
    L7's `interrupted`); its visits are recorded with the classification `restart` (excluded from parity). Hours
    while the runner was down have no visit records (logged as a gap). The arming is rebuilt from the closed H1 bars
    from `epoch` (as at a first start). The first decision is at the next H1 open, under 5b.
  - **A stop request** (L10) is finished when the runner exits: its row is closed then. At a new `zone run`, any stop
    row left open by a runner that died is closed (logged) - `zone run` is the owner's explicit start.
- **A failed broker read is never an empty account**: if the positions, orders, deals or history cannot be read, the
  start (or the cycle) does nothing that depends on them - no obligation cleared, no order placed, no fill judged -
  and retries.

## L9. Settings

The zone's parameters come from the zone set in `data/bot_config.db` (`--market`, `--set`; ZONE_RULES rule 1), version
pinned at start. The runner's own settings - `lot` (0.01, owner), `cycle_seconds` (2), `stale_quote_seconds` (30),
`preclose_seconds` (15), `epoch` (2023-10-01) - come from a new `zone_live:` section of `config.yaml`, a model added to `AppConfig` in
`app/config.py` (unknown fields are refused, as for every section) [Claude].

## L10. The command line [Claude]

- `python -m app.cli zone run --market XAUUSD --set default` - the mode from `.env`; runs until stopped.
- `python -m app.cli zone status` - the pinned account, the hour's candidates, the setup, its orders and positions, the
  last requests, any stray order or position.
- `python -m app.cli zone stop` - writes a stop request (a row the runner reads every cycle) and waits for the runner's
  acknowledgement: the runner removes every unfilled order of the zone magic, keeps open positions with their SL / TP
  (and still manages them: the BE, the exit, the leftover P2 removal) and places nothing new; it then exits only when
  no position is open, or at once with `--now` (the positions keep their broker SL / TP and are the owner's). Ctrl+C in
  the runner's window = the same stop.

## L11. Acceptance - what a build must show

1. **The move changes nothing**: the eye tests and the stored-bar acceptance (`ZONE_ACCEPT=1`) pass with only their
   imports and patch targets moved to `app.zone`; no assertion is changed; `eye/zone_bot.py` gives the same 109 setups
   with the same numbers (ZONE_RULES rule 12).
2. **The runner against the simulation** - a replay on stored bars:
   - A **replay broker** (a test double in `tests/`, not FakeMT5): it serves the runner the stored closed bars up to
     the replay time and the forming H1 bar's open; it drives the quote path of each `exec_tf` bar from its stored
     values: open -> the extreme nearer the open -> the other extreme -> close, walked in steps of one tick, the ask =
     bid + the bar's spread; it fills a limit at its price when the path crosses it (BUY: ask <= P; SELL: bid >= P), an
     SL at its price, a TP at its price, on the tick where the path crosses them, independent of the runner's cycles.
   - **Time**: the ticks of a bar are spread evenly over its period, the first at its open time, the last
     `preclose_seconds` / 2 before its `close_time`; the replay clock moves tick by tick. The runner's cycle runs in
     two modes, both required: after every tick (no polling gap), and every `cycle_seconds` of replay time (the real
     polling, so ticks fall between cycles).
   - The runner runs on it unchanged (its clock and broker injected), on two spans at least: 2024-03 and 2026-03 (M15),
     and one M5 span with `exec_tf` M5.
   - **Both ways**: every simulated visit - every line `find_visits` returns, farther lines included - has its runner
     record with the same classification (momentum, busy, abnormal, trend, or the setup's outcome; momentum before
     busy), and every runner record has its simulated visit. For each setup: outcome, visit hour, line, side, each
     fill (P1 / P2, its `exec_tf` bar and price), the BE (its bar and stop), the exit (bar, how, price), and the
     reservation end. Prices agree within one tick; bars exactly. Each difference is listed with the bar that
     explains it; the admitted causes are only: the order of touches inside one bar (the simulation's fixed in-bar
     order vs the path); **the bar boundary** (L5) - a fill or touch inside the pre-close window or in the first
     `cycle_seconds` of the next bar, where the runner's judgment from the last quote before the close differs from
     the true close (a removed order not yet placed again, or a kept order that the true close forbids); **a P2
     re-placed after its P1 filled in the same bar** - a P2 touch before the runner placed it again; a missed touch (L4) in the polling mode; and the tick rounding
     (L3) - a bar whose extreme lies within one tick of an order, SL or TP price; the
     setups after it must agree again once the reservation of the differing setup has ended. Any other difference is
     a fault.
   - **The gate is strict** [Claude, 2026-11-03]: the automatic acceptance requires **zero raw differences** (prices
     within one tick, bars exact) and no runner log line at ERROR or above. A run with any difference does not pass
     automatically: each difference is listed with its bar and the path's facts (the ticks around it, the runner's
     decisions and the simulation's), the harness may *suggest* one of the admitted causes above, and the run is
     accepted only once each difference is explained by hand against those facts and recorded in
     `eye/BOT_RESEARCH.md`. An automatic cause classifier never passes a run on its own.
   - **What the broker-side checks cover** [Claude, 2026-11-03]: exposure and protection - every entry's symbol, type,
     side, lot, magic, comment, price, SL, TP and expiry; no request sent twice; never two live orders of one setup
     and name; P2 never resting without P1 placed or filled; no order resting after its setup's end (beyond the bar
     boundary of L5); every fill, exit and stop move matching the simulation both ways; every market close justified;
     the end state equal to the simulation's. The exact cycle at which an order is placed or removed (the candidates'
     hour end, the losing candidate, the blocks, the BE removal of P2) is checked by the runner's unit tests (L11.3),
     not by the replay gate - a timing fault that changes a fill, an exit or a stop is caught by the comparison.
3. **Unit tests** on FakeMT5 or the replay broker: the candidates at the open (nearest armed, a disarmed nearer line
   passed over, equality to the open, a reserved hour); the first visit removes the other candidate's orders; a
   skipped first visit leaves the other; both filled -> the later closed; rules 1 - 4 each, at the bar the simulation
   applies them (the closed-hour cancel before any visit; no withdrawal in `j0`; a blocked P1 touched on the bid but
   not the ask does not cancel; a blocked P2 re-placed after P1 fills in the bar); a marketable order; the BE once,
   both SLs, P2 removed, a refused modify closed at the BE price in the logic; the leftover P2 removed when the last
   position closes; the reservation end (an exit inside a bar reserves to its `close_time`, a Friday exit does not
   block Monday's open; expiry); the withdrawal and the closed-hour cancel in one bar -> `no fill`; the pre-close
   window removes and re-places; a missed touch found at the bar's close; the M15 frame kept fresh with `exec_tf` M5;
   write-ahead with a crash before the send, after the broker accepted, and with the accepted order visible only
   after several cycles (never a duplicate, the ticket recovered); a remove and a modify with an unknown outcome
   judged by the ticket's state; the broker expiry set and extended each hour; P1 refused (no P2 alone); P2 refused; a remove refused while the order fills; a partial fill; a restart (L8, fresh from the next hour) with
   candidates resting (all removed, nothing placed until the next hour), with a setup pending (ended `restart`), with
   positions (managed to their end, BE judged on the bars closed while down, the reservation to the last exit's bar),
   with positions closed while down (exits from the deals), with an owed close (resumed first), with an unknown
   place intent (reconciled, never re-sent), with a stray magic order and a stray position; an account switch stops new orders;
   the gate evaluated fresh before each order (LIVE without the two `.env` values refused; no day plan needed - the
   gate passes without the plan file); the kill switch, lost
   connection and stale data stop new orders but keep managing; a second runner refused; `zone stop` acknowledged and
   nothing placed after it; PAPER / BACKTEST refused.
4. **Independence**: `app/zone` imports nothing from `eye/` nor from the Fibonacci bot; the runner imports nothing from
   `app/engine/orchestrator`, the decision engine, the checklist, arbitration or the strategies (a test reads the
   imports).
5. **Gates**: ruff, mypy, bandit, the architecture test, the full suite.

## L12. Not in this build

The web / PWA view, alerts outside the log, several symbols, sizing other than the fixed lot, DEMO runs (the owner: no
DEMO). Turning LIVE on is the owner's: the two `.env` values, then the owner's word to start the runner (CLAUDE.md).
