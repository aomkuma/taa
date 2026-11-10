"""The run-zone runner: the real-time driver of the setup of ``eye/ZONE_RULES.md`` on the broker account
(``eye/ZONE_LIVE.md``, L0 - L10).

One logic, two drivers: the bar-by-bar life of a setup is ``app.zone.core.step_setup``; the questions the
runner asks of it before a bar has closed are in ``app.zone.live``. This module is the second driver: it keeps
the closed bars, reads the quote, decides each cycle which orders should rest (``_wants``), sends or removes
them through the broker layer (write-ahead, ``app.zone.store``), and follows the deals.

**Ours** is a placement this process sent (L3, Words); everything else of the magic is not ours. Whatever the
runner cannot know or cannot do in the normal case turns it **hands-off** (L8): placing stops, every order of
the magic is removed, no position is touched, until the magic is flat - then it starts anew at the next H1
open. A start that finds the magic not flat is hands-off too; nothing of a previous process is carried over.

Everything is injected: the clock, the gateway (read side), the execution (send side) and the bar source, so
the unit tests and the replay of L11 drive the same code. Nothing here imports the strategy engine, the
decision engine, the checklist or the arbitration (rule 0 of ZONE_RULES: a setup of its own).
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import sys
import time as _time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

from app.broker import mt5_constants as c
from app.broker.execution import COMMENT_MAX, CheckResult, RequestBuilder, SendResult
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.models import (
    AccountSnapshot,
    BrokerOrder,
    BrokerPosition,
    Deal,
    HistoryOrder,
    TerminalSnapshot,
)
from app.broker.retcodes import RetcodeClass
from app.config import EnvSettings
from app.core.clock import Clock, ServerClock
from app.core.enums import Side, Timeframe, TradingMode
from app.core.errors import SafetyViolation, TaaError
from app.market_data.candle_service import normalize_rates
from app.market_data.data_models import SymbolSpec, Tick
from app.risk.kill_switch import KillSwitch
from app.risk.mode_gates import evaluate_gate
from app.storage.database import Database
from app.storage.models import ZoneLiveRequestRow
from app.zone import live
from app.zone.core import (
    PER_H,
    TH,
    Bars,
    ExecBars,
    Fill,
    Grid,
    H1Reader,
    Visit,
    ZoneError,
    bar_values,
    build_grids,
    build_state,
    check_frame,
    grid_index,
    month_steps,
    plan_setup,
    start_life,
    visits_at_bar,
    warmup_index,
)
from app.zone.core import SetupPlan as _SetupPlan
from app.zone.params import ZoneParams
from app.zone.store import RESERVING, ZoneStore

log = logging.getLogger(__name__)

NAMES = live.NAMES
Key = live.Key
DEVIATION_POINTS = 50  # the slippage limit of a market close / the marketable entry (gold: 0.50 USD)
MAX_TRIES = 3  # P2 refusals in a setup (L8), SL modify tries of a position (L5)
MAX_N = 999  # the highest placement number of a name (L3)
HOUR = pd.Timedelta(hours=1)
DECIDE_SECONDS = 60.0  # the hour's decision is made only in the first 60 s of the H1 bar (L2)
FRAMES = ("D1", "H4", "H1", "M15")  # always kept fresh; M5 as well when it is exec_tf
NY = "America/New_York"  # the broker's daily break (17:00 New York) and weekend follow it (Words)
STOPPED_ENDS = ("interrupted", "hands-off", "restart")  # an end of these is never the hour's setup (L4)
VOL_EPS = 1e-9
REMOVAL_WHY = {  # the removal reasons (``_removal_reason``), for the log
    "stop": "a stop request",
    "kill": "the kill switch",
    "gate": "the gate failed",
    "stale": "the data has been stale for more than one bar",
    "rule": "the rules",
}
STOP_NOW_SECONDS = (
    60.0  # `zone stop --now`: the runner leaves after this long, whatever the removals stand at (L10)
)


class AccountSwitched(RuntimeError):
    """The account is not the pinned one: nothing may be sent (L1)."""


class ZoneStartError(RuntimeError):
    """The runner cannot start; the message says why."""


# --- what the runner is given
# ---------------------------------------------------------------------------------


class ZoneGateway(Protocol):
    """The read side of the broker (``ReadOnlyMT5Gateway`` implements it; so does the replay broker)."""

    server_clock: ServerClock

    def terminal(self) -> TerminalSnapshot: ...

    def account(self) -> AccountSnapshot: ...

    def symbol_spec(self, symbol: str) -> SymbolSpec: ...

    def tick(self, symbol: str) -> Tick | None: ...

    def positions(self, symbol: str | None = None) -> list[BrokerPosition]: ...

    def orders(self, symbol: str | None = None) -> list[BrokerOrder]: ...

    def deals(self, start_utc: datetime, end_utc: datetime) -> list[Deal]: ...

    def history_orders(self, start_utc: datetime, end_utc: datetime) -> list[HistoryOrder]: ...


class ZoneExecution(Protocol):
    """The send side (``ExecutionGateway`` implements it)."""

    def send(self, request: dict[str, Any]) -> SendResult: ...

    def check(self, request: dict[str, Any]) -> CheckResult: ...


class BarSource(Protocol):
    """The broker's closed bars, and the open of the forming H1 bar (L2)."""

    def closed_bars(self, tf: str, after: pd.Timestamp | None) -> pd.DataFrame:
        """Closed bars of the frame with ``open_time > after`` (a candle frame, UTC times)."""
        ...

    def last_closed_open(self, tf: str) -> pd.Timestamp | None:
        """The open time of the broker's last closed bar of the frame."""
        ...

    def forming_h1(self) -> tuple[pd.Timestamp, float] | None:
        """(open time, open price) of the forming H1 bar; None when the market is shut."""
        ...


class GatewayBarSource:
    """``BarSource`` over the read-only MT5 gateway."""

    def __init__(self, gateway: ReadOnlyMT5Gateway, symbol: str, clock: Clock) -> None:
        self.gateway, self.symbol, self.clock = gateway, symbol, clock

    def _closed(self, tf: str, count: int) -> pd.DataFrame:
        frame = Timeframe(tf)
        raw = self.gateway.rates_from_pos(self.symbol, frame, 0, count)
        df = normalize_rates(raw, frame, self.gateway)
        if df.empty:
            return df
        now = pd.Timestamp(self.clock.now_utc())
        return df[df["close_time"] <= now].reset_index(drop=True)

    def closed_bars(self, tf: str, after: pd.Timestamp | None) -> pd.DataFrame:
        period = Timeframe(tf).seconds
        now = pd.Timestamp(self.clock.now_utc())
        count = 600 if after is None else max(10, int((now - after).total_seconds() / period) + 5)
        df = self._closed(tf, count)
        if after is not None and not df.empty:
            df = df[df["open_time"] > after].reset_index(drop=True)
        return df

    def last_closed_open(self, tf: str) -> pd.Timestamp | None:
        df = self._closed(tf, 3)
        return None if df.empty else pd.Timestamp(df["open_time"].iloc[-1])

    def forming_h1(self) -> tuple[pd.Timestamp, float] | None:
        raw = self.gateway.rates_from_pos(self.symbol, Timeframe.H1, 0, 1)
        if raw.empty:
            return None
        df = normalize_rates(raw, Timeframe.H1, self.gateway)
        now = pd.Timestamp(self.clock.now_utc())
        if df["close_time"].iloc[-1] <= now:
            return None
        return pd.Timestamp(df["open_time"].iloc[-1]), float(df["open"].iloc[-1])


@dataclass(frozen=True)
class RunnerConfig:
    """The runner's own settings (``zone_live`` of config.yaml, L9) and what it runs as."""

    lot: float
    cycle_seconds: float
    stale_quote_seconds: float
    preclose_seconds: float
    epoch: pd.Timestamp
    symbol: str
    market: str
    set_name: str
    set_version: int
    mode: TradingMode
    env: EnvSettings


GridsFn = Callable[[Bars, ZoneParams, pd.Timestamp], list[Grid]]


def default_grids(bars: Bars, params: ZoneParams, end: pd.Timestamp) -> list[Grid]:
    """Rule 3's grids from the stored series (``end`` exclusive for events)."""
    months = month_steps(bars.d1, bars.h4, params, end)
    return build_grids(bars.h4, months, params, bars.point, end)


class ProcessLock:
    """An exclusive lock file held for the life of the process (L1: one runner)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Any = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")  # noqa: SIM115 - held open for the life of the process
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            raise ZoneStartError(f"another zone runner holds the lock {self.path}") from exc
        self._fh = fh

    def release(self) -> None:
        if self._fh is None:
            return
        if sys.platform == "win32":
            import msvcrt

            with contextlib.suppress(OSError):  # closing the handle releases the lock anyway
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        self._fh.close()
        self._fh = None


# --- the live series
# -------------------------------------------------------------------------------------------


class LiveBars:
    """The stored frames plus the closed bars appended since; rows are never reordered, so a row index is
    stable."""

    def __init__(self, bars: Bars, exec_tf: str) -> None:
        self.point = bars.point
        self.frames = {tf: bars.frame(tf) for tf in ("D1", "H4", "H1", "M15", "M5")}
        self.tfs = FRAMES + (("M5",) if exec_tf == "M5" else ())
        self._last: dict[
            str, tuple[pd.DataFrame, pd.Timestamp | None]
        ] = {}  # frame -> its last open (a cache)
        self._opens: dict[
            str, tuple[pd.DataFrame, np.ndarray]
        ] = {}  # frame -> its open times in ns (a cache)

    def bars(self) -> Bars:
        f = self.frames
        return Bars(f["D1"], f["H4"], f["H1"], f["M15"], f["M5"], self.point)

    def last_open(self, tf: str) -> pd.Timestamp | None:
        df = self.frames[tf]
        cached = self._last.get(tf)
        if cached is not None and cached[0] is df:  # every change of a frame assigns a new frame object
            return cached[1]
        last = None if df.empty else pd.Timestamp(df["open_time"].iloc[-1])
        self._last[tf] = (df, last)
        return last

    def has_bar(self, tf: str, open_ts: pd.Timestamp) -> bool:
        """Whether the series holds the bar of the frame opening at ``open_ts``."""
        df = self.frames[tf]
        cached = self._opens.get(tf)
        if cached is None or cached[0] is not df:
            ns = df["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
            cached = (df, ns)
            self._opens[tf] = cached
        ns = cached[1]
        k = int(np.searchsorted(ns, open_ts.value, side="left"))
        return k < len(ns) and int(ns[k]) == open_ts.value

    def append(self, tf: str, df: pd.DataFrame) -> int:
        """Append the bars newer than the last one; the number of rows added."""
        if df.empty:
            return 0
        cur = self.frames[tf]
        last = self.last_open(tf)
        new = df if last is None else df[df["open_time"] > last]
        if new.empty:
            return 0
        merged = pd.concat([cur, new[list(cur.columns)]], ignore_index=True)
        self.frames[tf] = check_frame(merged, tf)
        return len(new)


# --- the candidate
# ---------------------------------------------------------------------------------------------


@dataclass
class FillRec:
    name: str
    j: int  # the exec row of the bar the deal fell in
    price: float  # the setup's logic price (P1 / P2, unrounded)
    broker_price: float
    position: int
    deal: int | None
    time: pd.Timestamp
    volume: float
    key: Key | None = None  # the key of the placement that filled


@dataclass
class ClosedRec:
    time: pd.Timestamp
    price: float
    reason: int


@dataclass
class Cand:
    """A live candidate of an hour (one ``zone_live_setup`` row)."""

    id: int
    hour_open: pd.Timestamp
    visit: Visit
    plan: _SetupPlan
    sent: live.SentPrices
    status: str = "live"  # live | ended
    dropped: bool = False
    chosen: bool = False
    touch_key: tuple[int, float, float] | None = None  # L4: the candidates' order (bar, nearer o, line)
    visited_at: pd.Timestamp | None = None
    fills: dict[str, FillRec] = field(default_factory=dict)
    closed: dict[int, ClosedRec] = field(default_factory=dict)
    close_reason: dict[int, str] = field(default_factory=dict)  # positions the runner closed: "BE"
    be_in_force: set[int] = field(default_factory=set)  # positions whose BE stop is confirmed in force (L5)
    be_on: bool = False
    be_sl: float | None = None  # the logic stop
    be_sent: float | None = None
    be_j: int | None = None
    p2_gone: bool = False  # BUY: P2 removed ahead of the break-even
    p1_refused: bool = False
    p2_off: bool = False  # P2 given up after three refusals
    refusals: dict[str, int] = field(default_factory=dict)
    outcome: str | None = None
    end_close: pd.Timestamp | None = None
    exit_how: str | None = None
    outs: dict[int, ClosedRec] = field(default_factory=dict)  # the first exit deal seen of each position
    out_last: dict[int, pd.Timestamp] = field(default_factory=dict)  # the last exit deal of each position
    drop_reason: str | None = (
        None  # "other": dropped for the other candidate's visit (a missed touch revives)
    )
    remaining: dict[int, float] = field(default_factory=dict)  # volume still open of each filled position
    faults: dict[int, str] = field(default_factory=dict)  # fills the logic did not allow, closed at market
    cancel_seen: int | None = (
        None  # L5 rule 3: the exec bar in which the quotes met the blocked P1's fill test
    )
    next_j: int = 0  # L5: the next exec row whose close steps this setup has not run (its own bar loop)
    drop_final: bool = False  # L4: the drop is final (P1 refused, the hour lost, the hour's close)
    # L5: the bar of a first fill accepted on the quotes of the forming bar - the setup's outcome waits for
    # that bar's close, where the fill is judged again on its true extremes
    rejudge_j: int | None = None
    exit_pending: bool = False  # its last position closed in that bar: ended for every later deal and order
    interrupted_for: str | None = None  # why it ended `interrupted` (a removal reason): its orders keep it

    @property
    def side(self) -> str:
        return self.visit.side

    @property
    def sgn(self) -> int:
        return self.plan.sgn

    @property
    def is_live(self) -> bool:
        return self.status == "live"

    @property
    def unfinished(self) -> bool:
        """No final outcome yet (Words "Ended"): under way, or dropped for the other's visit and not final
        - whatever its life has reached meanwhile (the store's ``end_unfinished`` reads the same from the
        row)."""
        return self.is_live or (self.dropped and not self.drop_final)

    def logic_price(self, name: str) -> float:
        return self.plan.p1 if name == "P1" else self.plan.p2

    def fill_list(self, upto: int | None = None) -> tuple[Fill, ...]:
        """The setup's fills (logic prices); with ``upto`` only those on a bar at or before it."""
        return tuple(
            Fill(f.name, f.j, self.logic_price(f.name))
            for f in self.fills.values()
            if upto is None or f.j <= upto
        )


@dataclass
class PendingEntry:
    """L5 / L8 causes 2 and 3 - a position or a filled order of ours seen whose entry deal is not read yet:
    the ONE record of a pending entry (``ZoneRunner.entries``). It ends only when its entry deal is read."""

    kind: str  # "position" | "order"
    ticket: int
    key: Key
    at: (
        pd.Timestamp
    )  # the broker's time of the entry (the position's open, the order's fill): it waits from it
    since: pd.Timestamp  # the first cycle that saw it: the one-bar timer of L8

    @property
    def setup(self) -> int:
        return self.key[0]


@dataclass
class HourState:
    open: pd.Timestamp
    i: int
    o: float
    reserved: bool
    cands: dict[str, Cand] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    chosen: Cand | None = None
    chosen_key: tuple[int, float, float] | None = None
    undecided: str | None = None  # why the runner did not decide this hour (L2, L8)
    decided: bool = False
    decided_at: pd.Timestamp | None = None
    first_quote_at: pd.Timestamp | None = None  # L2: the hour's first quote (the open, or the reopening)
    cut_at: pd.Timestamp | None = None  # an interruption or hands-off began in the hour (L4: later visits)


@dataclass
class Forming:
    n: int
    hi: float
    lo: float


@dataclass
class Ctx:
    """One cycle's view of the broker and of the clock."""

    now: pd.Timestamp
    tick: Tick | None = None
    orders: list[BrokerOrder] = field(default_factory=list)
    positions: list[BrokerPosition] = field(default_factory=list)
    deals: list[Deal] = field(default_factory=list)
    history: list[HistoryOrder] = field(default_factory=list)
    account: AccountSnapshot | None = None
    terminal: TerminalSnapshot | None = None
    connected: bool = False
    quote_fresh: bool = False
    bars_fresh: bool = False
    market_closed: bool = False
    gate_ok: bool = False
    gate_reason: str = ""
    kill: bool = False
    stale_long: bool = False
    stopping: bool = False
    exec_fresh: bool = True
    all_read: bool = False  # every read of the cycle is in (phase 3): ``_judge`` judges from all of it
    gate_known: bool = False  # the gate was evaluated on this cycle's account and terminal snapshots
    holds: dict[int, pd.Timestamp] = field(default_factory=dict)  # L5: setup -> the time it waits from
    remove_all: bool = False
    can_place: bool = False
    ahead: bool = False
    n: int = 0
    qrow: int | None = None  # the exec row of this cycle's quote (None: not known yet, ``_quote_row``)
    ex: ExecBars | None = None
    fx: Forming | None = None
    open_places: dict[tuple[int, str], ZoneLiveRequestRow] = field(default_factory=dict)
    read_failed: bool = False  # a read of this cycle failed (L8): the data is not fresh for this cycle
    removal_tried: set[int] = field(default_factory=set)  # tickets whose removal was sent this cycle
    removal_done: set[int] = field(default_factory=set)  # tickets whose removal the broker confirmed


_HISTORY_STATES = {
    c.ORDER_STATE_FILLED: "filled",
    c.ORDER_STATE_CANCELED: "cancelled",
    c.ORDER_STATE_REJECTED: "cancelled",
    c.ORDER_STATE_EXPIRED: "expired",
}


def _ts(value: datetime | pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(value)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def classify_exit(reason: int, *, be_in_force: bool, own_close_at_be: bool) -> str:
    """L5 "The exits" - how a setup exited, from the kind of its FIRST exit deal (the one place that decides):
    ``TP`` (deal reason TP); ``SL`` (deal reason SL) unless that position's BE stop was confirmed in
    force, then ``BE``; the runner's own close (deal reason EXPERT) is ``BE`` only when it was L5's close
    at the BE price (``own_close_at_be``), else ``close``; anything else is ``close``. A queued close never
    decides on its own: a broker SL / TP deal is what it is."""
    if reason == c.DEAL_REASON_TP:
        return "TP"
    if reason == c.DEAL_REASON_SL:
        return "BE" if be_in_force else "SL"
    if reason == c.DEAL_REASON_EXPERT and own_close_at_be:
        return "BE"
    return "close"


def _unknown(res: SendResult) -> bool:
    """No reply, a timeout, a lost connection: the order may or may not exist (L8)."""
    return res.retcode is None or res.retcode_class is RetcodeClass.UNKNOWN


# --- the runner
# ------------------------------------------------------------------------------------------------


class ZoneRunner:
    def __init__(
        self,
        *,
        cfg: RunnerConfig,
        params: ZoneParams,
        clock: Clock,
        gateway: ZoneGateway,
        execution: ZoneExecution,
        bar_source: BarSource,
        db: Database,
        bars: Bars,
        kill_switch: KillSwitch,
        magic: int,
        grids_fn: GridsFn = default_grids,
        persist: Callable[[str, pd.DataFrame], None] | None = None,
        lock: ProcessLock | None = None,
    ) -> None:
        self.cfg, self.params, self.clock = cfg, params, clock
        self.gw, self.exe, self.src, self.db = gateway, execution, bar_source, db
        self.kill, self.magic = kill_switch, int(magic)
        self.grids_fn, self.persist, self.lock = grids_fn, persist, lock
        self.builder = RequestBuilder(DEVIATION_POINTS)
        self.exec_tf = params.exec_tf
        self.per_h = PER_H.get(self.exec_tf, 0)
        self.period_s = Timeframe(self.exec_tf).seconds
        self.period = pd.Timedelta(seconds=self.period_s)
        self.live = LiveBars(bars, self.exec_tf)
        # filled by start()
        self.spec: SymbolSpec | None = None
        self.store: ZoneStore | None = None
        self.login = 0
        self.server = ""
        self.risk_config_ok = False
        self.started = False
        self.started_at: pd.Timestamp | None = None
        self.initialized = False  # the first successful broker read (L8: the start) has been taken
        self.bootstrap_error: str | None = None  # why the start's bootstrap failed (it is retried each cycle)
        # the series' derived readings
        self.reader: H1Reader | None = None
        self.grids: list[Grid] = []
        self.gstart = np.array([], dtype="int64")
        self.armed: dict[tuple[float, float, float], bool] = {}
        self.start_i = 0
        self._fresh: dict[str, bool] = {}
        self._rows_done = 0  # the exec rows closed when the run began (every setup starts after them)
        self.start_hour_i = 0
        self.decide_from: pd.Timestamp | None = None  # the first H1 open at which candidates may be made
        self._reader_key: tuple[int, ...] = ()  # the frame lengths the reader was built from
        self._grid_key: tuple[Any, ...] = ()  # what the grids were built from (``_ensure_grids``)
        self._grid_horizon: pd.Timestamp | None = None  # the grids reach this far (never shrinks)
        self._exb: ExecBars | None = None
        self._ex_close_ns: np.ndarray | None = None
        self._h1_ny_hours: set[int] = set()  # the New York wall-clock hours (naive ns) of the H1 bars
        self._h1_ny_len = -1
        # the hour and the candidates
        self.hour: HourState | None = None
        self.prev_hours: dict[int, HourState] = {}
        self.cands: dict[int, Cand] = {}
        self.res_by: dict[int, pd.Timestamp] = {}  # L6: the reservation end of each hour's setup that ended
        # ours (L3): the placements this process sent, and what the broker last accepted of them
        self.ours: dict[Key, int] = {}
        self.place_payload: dict[Key, dict[str, Any]] = {}
        self.order_expect: dict[int, dict[str, Any]] = {}
        self.pos_expect: dict[int, dict[str, Any]] = {}
        self.our_positions: set[int] = set()
        self.seen_orders: dict[int, Key] = {}  # orders of ours seen resting
        self.removes_sent: set[int] = set()
        self.closes_sent: set[int] = set()
        self.exits_checked: set[int] = set()
        # real time
        self.fx: Forming | None = None
        self.seen_deals: set[int] = set()
        self.pending: dict[tuple[str, int], tuple[int, dict[str, Any]]] = {}
        self.close_wanted: dict[int, str] = {}
        self.be_tries: dict[int, int] = {}
        # L8: the timers of the conditions that turn hands-off after one exec_tf bar
        self.unknown_since: dict[Key, pd.Timestamp] = {}
        self.gone_since: dict[int, pd.Timestamp] = {}
        self.exit_since: dict[int, pd.Timestamp] = {}
        self.remove_since: dict[int, pd.Timestamp] = {}
        self._remove_seen: dict[int, pd.Timestamp] = {}  # the last cycle that saw each removal timer
        self.close_since: dict[int, pd.Timestamp] = {}
        self.market_since: dict[Key, pd.Timestamp] = {}
        self.not_ours_orders: dict[int, str] = {}
        self.not_ours_positions: dict[int, str] = {}
        self.hands_off: str | None = None
        self.hands_off_at: pd.Timestamp | None = None
        self.stale_since: pd.Timestamp | None = None
        self.stale_owed = False  # L7: an overdue stale removal not yet performed (outlives the recovery)
        self.leave_unacknowledged = False  # the --now timeout exit with removals unconfirmed (L10)
        # L5: THE registry of the pending entries - ("position" | "order", ticket) -> the entry (``_track``)
        self.entries: dict[tuple[str, int], PendingEntry] = {}
        self.buffered: set[int] = set()  # setups with an entry deal read but not judged yet (``_absorb``)
        # order tickets judged not wanted, and why ("stop", "kill", "gate", "stale" or "rule"): removed every
        # cycle until gone (L8) - a stale-only one waits while the market is closed (L7)
        self.unwanted: dict[int, str] = {}
        self.account_switched = False
        self.pending_filling: int | None = None
        self.stopping = False
        self.stop_id: int | None = None
        self.exit_now = False
        self.exit_now_at: pd.Timestamp | None = None  # when `--now` was first in force (L10: 60 s from then)
        self.last_orders: list[BrokerOrder] = []  # the orders of the magic at the last successful read
        # L10: the order of events - an orders read confirms the removals only when it was taken after the
        # stop request and after the last placement (a running sequence; the comments of the placements sent)
        self._seq = 0
        self.last_orders_seq = -1
        self.stop_seq = -1
        self.place_seq = -1
        self.placed_seq: dict[str, int] = {}
        # L7 / L8: an interruption owed (its reason) - latched when it falls due, done once nothing is left
        self.interrupt_owed: str | None = None
        self.stop_acked = False
        self.finished = False
        self.last_cycle_at: pd.Timestamp | None = None
        # L2: the last pre-hour read - (read time, quote time) of the last successful quote read, and for each
        # hour open the read time of the last successful read whose quote was stamped before that hour
        self.quote_last: tuple[pd.Timestamp, pd.Timestamp] | None = None
        self.pre_reads: dict[pd.Timestamp, pd.Timestamp] = {}
        # L2: per frame, the opens of the bars this process read a quote inside, not yet held by the series
        self.expected: dict[str, set[pd.Timestamp]] = {tf: set() for tf in self.live.tfs}
        self._outstanding_logged: set[tuple[str, pd.Timestamp]] = set()
        self.last_gate = (True, "")
        self._status_text = ""
        self._status_at: pd.Timestamp | None = None

    @property
    def next_j(self) -> int:
        """The first exec row that some setup in memory has not closed yet (every earlier row is closed for
        every setup; each setup keeps its own bar loop, ``Cand.next_j``)."""
        return min((cd.next_j for cd in self.cands.values()), default=self._rows_done)

    @property
    def res_end(self) -> pd.Timestamp | None:
        return max(self.res_by.values()) if self.res_by else None

    @res_end.setter
    def res_end(self, value: pd.Timestamp | None) -> None:
        self.res_by = {} if value is None else {0: value}

    # =========================================================================================== start

    def start(self) -> None:
        """L1, L2, L8 - the checks, the lock, the pinned account, the bars; then the first cycle."""
        cfg = self.cfg
        if not cfg.mode.may_send_broker_orders:
            raise ZoneStartError(f"the zone runner needs DEMO or LIVE (TRADING_MODE={cfg.mode.value})")
        if cfg.symbol != "XAUUSD" or cfg.market != "XAUUSD":
            raise ZoneStartError("the zone runner trades XAUUSD only")
        if self.exec_tf not in PER_H:
            raise ZoneStartError(f"exec_tf {self.exec_tf} is not M5 or M15")
        if len(live.make_comment(10**12 - 1, "P1", MAX_N)) > COMMENT_MAX:
            raise ZoneStartError("a key with a 12-digit setup id would not fit the broker's comment")
        if self.lock is not None:
            self.lock.acquire()
        try:
            self._start_checked()
            self.started = True
            self.cycle()
            if self.bootstrap_error is not None and not self.initialized:
                raise ZoneStartError(self.bootstrap_error)
        except BaseException:
            self.started = False
            if self.lock is not None:
                self.lock.release()
            raise

    def _start_checked(self) -> None:
        cfg = self.cfg
        spec = self.gw.symbol_spec(cfg.symbol)
        self.spec = spec
        step = spec.volume_step
        if (
            not (spec.volume_min <= cfg.lot <= spec.volume_max)
            or abs(cfg.lot / step - round(cfg.lot / step)) > 1e-9
        ):
            raise ZoneStartError(
                f"lot {cfg.lot} is outside {spec.volume_min}..{spec.volume_max} or not a multiple of {step}"
            )
        if not spec.expiration_mode & c.SYMBOL_EXPIRATION_SPECIFIED:
            raise ZoneStartError(f"{cfg.symbol} does not allow orders with a specified expiration")
        acct = self.gw.account()
        if acct.margin_mode != c.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING:
            raise ZoneStartError(f"the account is not a hedging account ({acct.margin_mode_name})")
        self.login, self.server = acct.login, acct.server
        self.store = ZoneStore(self.db, acct.login, acct.server)
        now = self.now()
        self.started_at = now
        store = self.store
        # L8: nothing of a previous process carries over - its unfinished rows end ``restart``, its requests
        # are closed (their keys are not ours), a stop row left open by a runner that died is closed
        ended = store.end_unfinished(now.to_pydatetime(), "restart", "ended at a new zone run")
        if ended:
            log.warning("the unfinished setups %s of a previous run ended `restart`", ended)
        closed = store.close_requests(now.to_pydatetime(), "closed at a new zone run")
        if closed:
            log.warning("%s request(s) of a previous run closed: their keys are not ours", closed)
        while (stale := store.pending_stop()) is not None:
            store.acknowledge_stop(
                stale.id, now.to_pydatetime(), "closed at a new zone run: its runner did not finish"
            )
            log.warning(
                "stop request %s (by %s) was left open: closed at this start", stale.id, stale.requested_by
            )
        self.risk_config_ok = True  # the settings above were validated
        self._check_overlap(spec.tick_size)
        self._update_bars()
        log.info(
            "zone runner started on %s@%s (%s), set %s v%s, lot %s, magic %s",
            acct.login,
            acct.server,
            cfg.mode.value,
            cfg.set_name,
            cfg.set_version,
            cfg.lot,
            self.magic,
        )

    def _check_overlap(self, tick: float) -> None:
        """L2 - the broker's closed bars must reach back to each stored frame's last bar and agree with the
        stored bars they overlap; else the start is refused, the frame and the bar named."""
        from app.zone.history_check import check_overlap

        for tf in self.live.tfs:
            stored = self.live.frames[tf]
            if len(stored) < 2:
                raise ZoneStartError(f"{tf}: too few stored bars to start from")
            after = pd.Timestamp(stored["open_time"].iloc[-2])
            try:
                broker = self.src.closed_bars(tf, after)
            except (TaaError, ZoneError, OSError, ValueError) as exc:
                raise ZoneStartError(f"{tf}: the broker's bars cannot be read at the start: {exc}") from exc
            res = check_overlap(tf, stored.iloc[-1:], broker, tick)
            if not res.ok:
                raise ZoneStartError(f"the stored history does not join the broker's: {res.reason}")

    def _first_read(self, ctx: Ctx) -> None:
        """L8 - the start, at the first successful broker read: the arming rebuilt from the epoch, the first
        decision at the first H1 open after the start; a magic that is not flat -> hands-off until it is.
        The start is complete only when all of this succeeded: a failure leaves the runner not initialized
        (retried at the next cycle, and refusing the first start), never cleared by a flat-book cycle."""
        try:
            self._ensure_reader()
            ex_n = len(self._exec())
            self.start_hour_i = len(self.live.frames["H1"])
            self._rows_done = ex_n
            self._build_arming(len(self._reader()))
        except (ZoneError, ZoneStartError) as exc:
            self.bootstrap_error = f"the start could not be completed: {exc}"
            raise
        self.bootstrap_error = None
        self.initialized = True
        self.decide_from = self._next_open(self.started_at or ctx.now)  # after the start, not the first read
        if ctx.orders or ctx.positions:
            self._enter_hands_off(
                f"the magic is not flat at the start ({len(ctx.orders)} order(s), "
                f"{len(ctx.positions)} position(s))",
                ctx.now,
            )
        log.info("the first decision at the H1 open %s", self.decide_from)

    @staticmethod
    def _next_open(t: pd.Timestamp) -> pd.Timestamp:
        """The first H1 open after ``t`` (L8: never the hour under way, nor one opening at ``t`` itself)."""
        return t.floor("h") + HOUR

    def _build_arming(self, upto: int) -> None:
        """L2 - the line arming from the closed H1 bars from the epoch up to the row before ``upto``, as the
        simulation computes it; the later rows are closed one by one by the normal path."""
        r = self._reader()
        first = max(
            int(np.searchsorted(r.h1_open_ns, self.cfg.epoch.value, side="left")), warmup_index(self.params)
        )
        self.start_i = first
        self.armed = {}
        for i in range(first, min(upto, len(r))):
            g = live.grid_at(self.grids, self.gstart, int(r.h1_open_ns[i]))
            if g is not None:
                visits_at_bar(r, i, g, self.armed, self.params, readings=False)

    def _ensure_reader(self) -> None:
        """The full reader of the closed bars, rebuilt whenever a bar of any frame it reads has been added -
        an exec bar published after its H1 bar included (L2: the decision uses every bar closed at the open,
        ``j0`` among them); decisions slice it."""
        bars = self.live.bars()
        key = tuple(len(self.live.frames[tf]) for tf in ("D1", "H4", "H1", "M15", "M5"))
        if self._reader_key != key:
            if len(bars.h1) == 0:
                raise ZoneStartError("no H1 bars")
            self._ensure_grids()
            self.reader = H1Reader.build(bars, self.params, build_state(bars))
            self._reader_key = key

    def _ensure_grids(self, upto: pd.Timestamp | None = None) -> None:
        """ZONE_RULES 3 / L2 - the grids, rebuilt whenever what decides them changes: the D1 and H4 bars (the
        H4 pairs from closed bars only, the weekly ATR of the monthly step) and the Thai month they must
        reach. They reach the last closed H1 bar and, for a decision, through the decision hour ``upto`` - a
        month start is a calendar event, in force from its start though no H1 bar has closed in it yet (the
        market closed across it); the horizon never shrinks."""
        bars = self.live.bars()
        if len(bars.h1) == 0:
            raise ZoneStartError("no H1 bars")
        end = _ts(bars.h1["open_time"].iloc[-1]) + 2 * HOUR
        if upto is not None:
            end = max(end, upto + HOUR)
        if self._grid_horizon is not None:
            end = max(end, self._grid_horizon)
        self._grid_horizon = end
        key = (len(bars.d1), len(bars.h4), end.tz_convert(TH).strftime("%Y-%m"))
        if key != self._grid_key:
            self.grids = self.grids_fn(bars, self.params, end)
            self.gstart = grid_index(self.grids) if self.grids else np.array([], dtype="int64")
            self._grid_key = key

    def _reader_upto(self, i: int) -> H1Reader:
        """The reader as it was at the open of the H1 bar ``i``: no later bar is in it (no look-ahead)."""
        r = self._reader()
        return replace(
            r,
            o=r.o[:i],
            hi=r.hi[:i],
            lo=r.lo[:i],
            c=r.c[:i],
            rng=r.rng[:i],
            h1_open_ns=r.h1_open_ns[:i],
            ema=r.ema[:i],
            atr=r.atr[:i],
        )

    def _read_failed(self, ctx: Ctx, what: str, exc: BaseException) -> None:
        """L8 - the ONE place a failed read of the cycle is noted: the data is not fresh for this cycle (no
        placing, ``_placing_allowed``) and the stale timer runs from this failure."""
        log.warning("%s could not be read: %s", what, exc)
        ctx.read_failed = True
        if not self.account_switched:
            self.stale_since = self.stale_since or ctx.now

    def _forming(self, ctx: Ctx) -> tuple[pd.Timestamp, float] | None:
        try:
            fh = self.src.forming_h1()
        except (TaaError, OSError, ValueError) as exc:
            self._read_failed(ctx, "the forming H1 bar", exc)
            return None
        return None if fh is None else (_ts(fh[0]), float(fh[1]))

    def _note_quote_read(self, requested: pd.Timestamp, tick: Tick) -> None:
        """L2 - a successful quote read (``requested``: the time taken just before the request). The read
        before it is the last pre-hour read of every hour open after the previous quote's stamp up to this
        one's: it was the last whose quote was stamped before that hour."""
        q = _ts(tick.time_utc)
        prev = self.quote_last
        if prev is not None and q > prev[1]:
            p_read, p_quote = prev
            h, n = q.floor("h"), 0
            while h > p_quote and n < 6:
                self.pre_reads[h] = p_read
                h, n = h - HOUR, n + 1
            for old in [k for k in self.pre_reads if k < q.floor("h") - 6 * HOUR]:
                del self.pre_reads[old]
        self.quote_last = (requested, q)
        # L2: the bar of every frame holding this quote is expected once it has closed
        for tf in self.live.tfs:
            b = self._bar_open(tf, q)
            if b not in self.expected[tf] and not self.live.has_bar(tf, b):
                self.expected[tf].add(b)

    def _bar_open(self, tf: str, t: pd.Timestamp) -> pd.Timestamp:
        """The open of the frame's bar holding ``t``: bars open on multiples of their period in server time
        (D1 at the server's midnight, H4 every four server hours)."""
        sc = self.gw.server_clock
        period = Timeframe(tf).seconds
        s = int(sc.utc_to_server_epoch(t.to_pydatetime()))
        return _ts(sc.server_epoch_to_utc(s - s % period))

    def _outstanding(self, now: pd.Timestamp) -> list[tuple[str, pd.Timestamp]]:
        """L2 - THE test of the expected bars: every closed bar this process read a quote inside (each frame
        alike - D1, H4, H1, M15, ``exec_tf``) that the series does not hold yet. While any is outstanding the
        data is not fresh (no placing, L7; the stale timer runs), its frame's later steps wait, and no hour
        begins (its decision, by its 60 s, or undecided)."""
        out = []
        for tf in self.live.tfs:
            period = pd.Timedelta(seconds=Timeframe(tf).seconds)
            for b in sorted(self.expected[tf]):
                if self.live.has_bar(tf, b):
                    self.expected[tf].discard(b)
                elif b + period <= now:
                    out.append((tf, b))
        return out

    def _hour_first_quote(self, open_ts: pd.Timestamp) -> pd.Timestamp:
        """L2 - the hour's first quote as the runner knows it: the later of the H1 open and the last pre-hour
        read (the time just before the request of the last successful quote read whose quote was stamped
        before the hour); with no such read in this process, the H1 open."""
        last = self.quote_last
        if last is None:
            return open_ts
        pre = last[0] if last[1] < open_ts else self.pre_reads.get(open_ts)
        return open_ts if pre is None else max(open_ts, pre)

    # ================================================================================================ the
    # cycle

    def run(self, sleep: Callable[[float], None] = _time.sleep) -> None:
        """Cycle until stopped (``finished``)."""
        if not self.started:
            self.start()
        try:
            while not self.finished:
                self.cycle()
                if self.finished:
                    break
                sleep(self.cfg.cycle_seconds)
        except KeyboardInterrupt:
            log.warning("Ctrl+C: stopping like `zone stop` (orders removed; positions managed until flat)")
            self.request_stop_local()
            while not self.finished:
                try:
                    self.cycle()
                    if self.finished:
                        break
                    sleep(self.cfg.cycle_seconds)
                except KeyboardInterrupt:
                    log.warning("Ctrl+C again: leaving once the removals are confirmed (`--now`)")
                    self.request_stop_local(now=True)
        finally:
            self._close_stop_rows()
            if self.lock is not None:
                self.lock.release()

    def _close_stop_rows(self) -> None:
        """A stop request is finished when the runner exits: every stop row still open is closed then."""
        if self.store is None or self.leave_unacknowledged:
            return
        try:
            while (st := self.store.pending_stop()) is not None:
                self.store.acknowledge_stop(
                    st.id, self.now().to_pydatetime(), "closed when the runner exited"
                )
        except Exception as exc:  # the exit must not fail on bookkeeping
            log.warning("a stop request could not be closed at the exit: %s", exc)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _removals_confirmed(self) -> bool:
        """L10 - THE confirmation that every unfilled order of the magic is removed: the last successful
        orders read shows none, and it was taken after the stop request and after the last placement."""
        return (
            not self.last_orders
            and self.last_orders_seq > self.stop_seq
            and self.last_orders_seq > self.place_seq
        )

    def _unresolved_orders(self) -> list[str]:
        """What may still rest at the broker: the orders of the last successful read, and every placement
        sent after it (its outcome not read)."""
        out = [f"order {o.ticket} {o.comment!r} at {o.price_open}" for o in self.last_orders]
        out += [f"placement {k}" for k, seq in self.placed_seq.items() if seq > self.last_orders_seq]
        return out

    def request_stop_local(self, now: bool = False) -> None:
        if not self.stopping:
            self.stop_seq = self._next_seq()
        self.stopping = True
        self.exit_now = self.exit_now or now
        if self.exit_now and self.exit_now_at is None:
            self.exit_now_at = self.now()

    def now(self) -> pd.Timestamp:
        return _ts(self.clock.now_utc())

    def _store(self) -> ZoneStore:
        if self.store is None:
            raise ZoneStartError("the runner is not started")
        return self.store

    def _spec(self) -> SymbolSpec:
        if self.spec is None:
            raise ZoneStartError("the runner is not started")
        return self.spec

    def cycle(self) -> None:
        """One pass: the stop request, the broker's state, the bars, the checks of L8, the hours and closed
        bars in time order, the real-time parts, then the orders the rules want. A failed broker read ends the
        pass before anything that depends on it (L8); an uncaught error ends it hands-off (L8, cause 8)."""
        if not self.started:
            raise ZoneStartError("the runner is not started")
        self._store()
        now = self.now()
        ctx = Ctx(now)
        read_ok = False
        try:
            # phase 0 (L8 safety first): the stop deadline from memory, before any store or broker read
            self._stop_deadline(now)
            if not self.finished:
                self._read_stop_requests(now)  # a failed read leaves what is in memory untouched
                self._stop_deadline(now)
            if self.finished:
                self.last_cycle_at = now
                self._publish(ctx)
                return
            # phase 1: the account (L1's pin) and the open orders - nothing else (a failure: `_read_failed`)
            if not self._read_core(ctx):
                self._publish(ctx)
                return
            # phase 2: the conditions from what is read so far; the removals owed; the stop's progress that
            # needs only the account and the orders (L8 safety first, L10)
            self._judge(ctx)
            if self.account_switched:
                raise AccountSwitched("the gate saw another account")
            # L1 / L8: the closed market's time, from phase 2's reads, whatever the later ones give; the
            # checks of hands-off that need only these reads; then the removals owed
            self._pause_stale_removal_timers(ctx)
            self._track_orders(ctx)
            self._safety(ctx)
            self._stop_progress(ctx)
            if self.finished:
                self.last_cycle_at = now
                self._publish(ctx)
                return
            # phase 3: every other read and step
            read_ok = True
            try:
                if not self._read_rest(ctx):
                    read_ok = False
                    self._publish(ctx)
                    return
                self._update_bars_into(ctx)
                ctx.all_read = True
                self._judge(ctx)
                if self.account_switched:
                    raise AccountSwitched("the gate saw another account")
                self._steps(ctx)
            except AccountSwitched:
                raise
            except Exception as exc:  # L8 cause 8: it cannot know what this cycle left undone
                log.error("an uncaught error inside the cycle: %s", exc, exc_info=True)
                self._enter_hands_off(f"an uncaught error inside a cycle: {exc!r}", now)
                if self.hands_off is not None:
                    self._guarded("the hands-off removals", self._hands_off_removals, ctx)
        except AccountSwitched:
            read_ok = False
            log.critical("the account is not the pinned one: no request is sent until a restart")
        except Exception as exc:  # L8 cause 8: it cannot know what this cycle left undone
            log.error("an uncaught error inside the cycle: %s", exc, exc_info=True)
            self._enter_hands_off(f"an uncaught error inside a cycle: {exc!r}", now)
        if read_ok:
            self._guarded("the end of the cycle", self._after, ctx)
        self.last_cycle_at = now
        self._publish(ctx)

    def _guarded(self, what: str, fn: Callable[[Ctx], None], ctx: Ctx) -> None:
        """A step that must not end the cycle's other work: its error is logged and is cause 8 (L8)."""
        try:
            fn(ctx)
        except AccountSwitched:
            log.critical("the account is not the pinned one: no request is sent until a restart")
        except Exception as exc:
            log.error("an error in %s: %s", what, exc, exc_info=True)
            self._enter_hands_off(f"an uncaught error inside a cycle ({what}): {exc!r}", ctx.now)

    def _steps(self, ctx: Ctx) -> None:
        """Every step of the cycle but the safety ones: the exec bars, the arming, the checks, the hours, the
        real-time parts, the orders the rules want."""
        self._set_exec(ctx)
        if not self.initialized:
            self._first_read(ctx)
        if self.hands_off is None:
            self._track(ctx)
        if self.hands_off is None:
            self._advance(ctx)
            self._decide(ctx)
            self._realtime(ctx)
            self._manage(ctx)
        else:
            self._advance(ctx)  # the bars, the arming and the visit records go on (L4)
            self._hands_off_cycle(ctx)

    def _read_stop_requests(self, now: pd.Timestamp) -> None:
        """The stop requests of the store (L10). A failure is logged and changes nothing in memory: an active
        ``--now`` and its deadline stand."""
        try:
            store = self._store()
            st = store.pending_stop()
            if st is not None and st.id != self.stop_id:  # a later row (e.g. with `now`) upgrades a stop
                if not self.stopping:
                    self.stop_seq = self._next_seq()
                self.stopping, self.stop_id = True, st.id
                self.stop_acked = False
                log.warning("stop requested by %s%s", st.requested_by, " (now)" if st.now else "")
            # L10: a `--now` request takes effect whatever stop is still unacknowledged before it, and
            # its 60 s run from that request
            if self.stopping and not self.exit_now:
                for row in store.pending_stops():
                    if row.now:
                        self.exit_now = True
                        self.exit_now_at = min(now, _ts(row.requested_at))
                        log.warning("stop --now requested by %s", row.requested_by)
                        break
        except Exception as exc:
            log.warning("the stop requests could not be read this cycle: %s", exc)

    def _safety(self, ctx: Ctx) -> None:
        """L8 phase 2 - the removals already owed, right after the reads of the account and the open orders,
        before every other read and step: hands-off, and what ``_judge`` found owed from these reads (a stop,
        the kill switch, a failed gate, the stale data while the market is open), an order judged not wanted
        earlier."""
        everything = self.hands_off is not None or ctx.remove_all
        if ctx.remove_all and self.hands_off is None:
            self._owe_safety(ctx, self._removal_reason(ctx))
        # an order judged not wanted earlier keeps its reason: a stale-only removal is owed only while the
        # market is open (``remove_all`` carries it then); every other reason does not wait for the market
        owed = (
            list(ctx.orders)
            if everything
            else [o for o in ctx.orders if o.ticket in self.unwanted and self._removal_due(o.ticket, ctx)]
        )
        resting = {o.ticket for o in ctx.orders}
        self.unwanted = {t: why for t, why in self.unwanted.items() if t in resting}
        if owed:
            self._remove_in_order(owed, ctx, timers=self.hands_off is None)

    # ---------------------------------------------------------------------------------------- reading the
    # broker

    def _read_core(self, ctx: Ctx) -> bool:
        """Phase 1 - the account (the L1 pin) and the open orders; the terminal snapshot too when it can be
        read (the gate). Nothing else: a failure of these reads ends the cycle."""
        if self.account_switched:  # latched until a restart (L1): ERROR every cycle while it waits
            log.error(
                "the account is not the pinned one (%s@%s): nothing is sent to any account until a restart",
                self.login,
                self.server,
            )
            return False
        try:
            acct = self.gw.account()
            if (acct.login, acct.server) != (self.login, self.server):
                log.critical(
                    "the account changed to %s@%s (pinned %s@%s): nothing is touched until a restart",
                    acct.login,
                    acct.server,
                    self.login,
                    self.server,
                )
                self.account_switched = True
                return False
            seq = self._next_seq()  # taken before the request: the read shows what was sent before it
            orders = self.gw.orders(self.cfg.symbol)
        except (TaaError, OSError, ValueError) as exc:
            self._read_failed(ctx, "the account or the open orders", exc)
            return False
        try:
            ctx.terminal = self.gw.terminal()
        except (TaaError, OSError, ValueError) as exc:
            # L2 / L8: a failed read of anything - the terminal included - vetoes placing for the whole cycle,
            # whatever a later read of it gives
            self._read_failed(ctx, "the terminal", exc)
        sym = self.cfg.symbol
        ctx.account = acct
        ctx.orders = [o for o in orders if o.magic == self.magic and o.symbol == sym]
        self.last_orders = list(ctx.orders)
        self.last_orders_seq = seq
        return True

    def _read_rest(self, ctx: Ctx) -> bool:
        """Phase 3's reads - the terminal when phase 1 could not read it, the quote, the positions, the deals
        and the history orders. A failure ends the cycle (L8)."""
        try:
            term = ctx.terminal if ctx.terminal is not None else self.gw.terminal()
            requested = self.now()
            ctx.tick = self.gw.tick(self.cfg.symbol)
            if ctx.tick is not None:
                self._note_quote_read(requested, ctx.tick)
            positions = self.gw.positions(self.cfg.symbol)
            since = self._deals_since()
            end = (ctx.now + timedelta(hours=1)).to_pydatetime()
            deals = self.gw.deals(since.to_pydatetime(), end)
            history = self.gw.history_orders(since.to_pydatetime(), end)
        except (TaaError, OSError, ValueError) as exc:
            self._read_failed(ctx, "the broker (terminal, quote, positions, deals or history)", exc)
            return False
        sym = self.cfg.symbol
        ctx.terminal = term
        ctx.positions = [p for p in positions if p.magic == self.magic and p.symbol == sym]
        # the deals of the magic, and the deals of a position of ours whatever the deal's own magic: a close
        # by hand carries magic 0, and it is exactly the exit L8 cause 7 must see
        mine = (
            self.our_positions
            | {p.ticket for p in ctx.positions}
            | {d.position_id for d in deals if d.magic == self.magic and d.symbol == sym}
        )
        ctx.deals = sorted(
            (
                d
                for d in deals
                if d.symbol == sym and (d.magic == self.magic or (d.position_id and d.position_id in mine))
            ),
            key=lambda d: d.time_utc,
        )
        ctx.history = [h for h in history if h.magic == self.magic and h.symbol == sym]
        return True

    def _deals_since(self) -> pd.Timestamp:
        """L8: deals and history are read from the process's start on."""
        start = self.started_at or self.now()
        return start.floor("s") - pd.Timedelta(seconds=1)

    def _update_bars(self, ctx: Ctx | None = None) -> tuple[list[int], bool]:
        """L2 - the closed bars since the last cycle (every frame; M15 always); the new exec rows, and whether
        every frame equals the broker's last closed bar (``self._fresh`` says which frames do). A failed read
        of a frame is noted on the cycle (``_read_failed``)."""
        new_exec: list[int] = []
        fresh: dict[str, bool] = {}
        for tf in self.live.tfs:
            ok_tf = True
            try:
                df = self.src.closed_bars(tf, self.live.last_open(tf))
                before = len(self.live.frames[tf])
                added = self.live.append(tf, df)
                if added and self.persist is not None:
                    self.persist(tf, df)
                if tf == self.exec_tf and added:
                    new_exec = list(range(before, before + added))
                    self._exb = None
            except (TaaError, ZoneError, OSError, ValueError) as exc:
                if ctx is not None:
                    self._read_failed(ctx, f"the {tf} bars", exc)
                else:
                    log.warning("%s bars could not be updated: %s", tf, exc)
                ok_tf = False
            if ok_tf:
                try:
                    ok_tf = self.src.last_closed_open(tf) == self.live.last_open(tf)
                except (TaaError, OSError, ValueError) as exc:
                    if ctx is not None:
                        self._read_failed(ctx, f"the broker's last closed {tf} bar", exc)
                    else:
                        log.warning("the broker's last closed %s bar could not be read: %s", tf, exc)
                    ok_tf = False
            fresh[tf] = ok_tf
        # L2: an expected bar not yet readable makes its frame not fresh (both broker reads may still agree on
        # the older bar)
        for tf, b in self._outstanding(self.now() if ctx is None else ctx.now):
            fresh[tf] = False
            if (tf, b) not in self._outstanding_logged:
                self._outstanding_logged.add((tf, b))
                log.warning(
                    "the %s bar opening %s is expected (a quote was read in it) but not readable yet", tf, b
                )
        self._fresh = fresh
        return new_exec, all(fresh.values())

    def _update_bars_into(self, ctx: Ctx) -> list[int]:
        new_exec, ok = self._update_bars(ctx)
        ctx.bars_fresh = ok
        ctx.exec_fresh = self._fresh.get(self.exec_tf, False)
        return new_exec

    def _reader(self) -> H1Reader:
        if self.reader is None:
            raise ZoneStartError("the runner has not read the bars yet")
        return self.reader

    def _exec_close_ns(self) -> np.ndarray:
        self._exec()
        if self._ex_close_ns is None:
            raise ZoneStartError("no exec bars")
        return self._ex_close_ns

    def _exec(self) -> ExecBars:
        if self._exb is None:
            frame = self.live.frames[self.exec_tf]
            self._exb = ExecBars.from_frame(frame)
            self._ex_close_ns = (
                frame["close_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
            )
        return self._exb

    def _ex_open_ns(self) -> np.ndarray:
        frame = self.live.frames[self.exec_tf]
        return frame["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")

    def _market_closed(self, now: pd.Timestamp) -> bool:
        """Words - no H1 bar of the runner's series at this weekday and hour, in New York time, in any of the
        previous four weeks (the caller has found no recent quote). The broker's daily break and weekend
        follow New York (the break at 17:00 New York); each H1 bar's open in UTC is read as New York
        wall-clock time, and the weeks are counted back in that wall-clock time, so a daylight-saving change
        moves nothing."""
        h1 = self.live.frames["H1"]
        if self._h1_ny_len != len(h1):
            ny = h1["open_time"].dt.tz_convert(NY).dt.tz_localize(None).dt.floor("h")
            self._h1_ny_hours = set(ny.astype("int64").tolist())
            self._h1_ny_len = len(h1)
        local = now.tz_convert(NY).tz_localize(None).floor("h")
        return not any((local - pd.Timedelta(weeks=k)).value in self._h1_ny_hours for k in range(1, 5))

    def _judge(self, ctx: Ctx) -> None:
        """L2 / L7 / L8 - the ONE place the cycle's conditions are judged, from what the cycle has read so
        far. Phase 2 calls it after the account, the orders and the terminal (the quote is then the last one
        this process read, the bars as the last cycle left them); phase 3 calls it again once every read is
        in (``ctx.all_read``). Both calls apply the same rules, so the removals of phase 2 and the steps of
        phase 3 never disagree:

        * the quote is fresh when younger than ``stale_quote_seconds``; the market is closed when it is not
          and no H1 bar of the series sits at this weekday and hour in the previous four weeks (Words);
        * any failed read of the cycle (``ctx.read_failed`` - the terminal included) makes the cycle not
          fresh: no placing for the whole cycle (L2, L8);
        * the stale removal is sent only while the market is open (L7: nothing is stale-removed while it is
          closed): while the data has been stale for more than one bar, and while its debt lasts
          (``_stale_debt``: through the recovery and a close, until nothing is owed);
        * an expected bar not readable yet (``_outstanding``) makes its frame not fresh (``_update_bars``);
        * the gate on this cycle's account and terminal snapshots (a snapshot that could not be read is no
          gate failure assumed, L8 - but no placing); the kill switch; a stop request."""
        cfg, now = self.cfg, ctx.now
        if ctx.all_read:
            stamp = None if ctx.tick is None else _ts(ctx.tick.time_utc)
        else:
            stamp = None if self.quote_last is None else self.quote_last[1]
        ctx.quote_fresh = stamp is not None and (now - stamp).total_seconds() <= cfg.stale_quote_seconds
        ctx.market_closed = not ctx.quote_fresh and self._market_closed(now)
        ctx.connected = ctx.terminal is not None and bool(getattr(ctx.terminal, "connected", True))
        if ctx.all_read:
            stale = ctx.read_failed or not (ctx.quote_fresh and ctx.bars_fresh)
            if not ctx.market_closed and stale:  # L7: nothing is stale-timed while the market is closed
                self.stale_since = self.stale_since or now
        else:
            stale = self.stale_since is not None  # as the last judgement (or a failed read) left it
        overdue = self.stale_since is not None and (now - self.stale_since).total_seconds() > self.period_s
        self._stale_debt(ctx, overdue)
        ctx.stale_long = not ctx.market_closed and (self.stale_owed or (stale and overdue))
        ctx.kill = self.kill.is_active()
        ctx.gate_known = ctx.account is not None and ctx.terminal is not None
        if ctx.gate_known:
            ok, why = self._gate(ctx.account, ctx.terminal)
            self.last_gate = (ok, why)
        else:
            ok, why = True, "the terminal could not be read (no gate failure assumed)"
        ctx.gate_ok, ctx.gate_reason = ok, why
        ctx.stopping = self.stopping
        ctx.remove_all = ctx.stopping or ctx.kill or not ok or ctx.stale_long
        ctx.can_place = bool(
            ctx.all_read
            and not ctx.read_failed
            and ctx.connected
            and ctx.gate_known
            and ok
            and not ctx.kill
            and ctx.quote_fresh
            and ctx.bars_fresh
            and not ctx.stopping
            and not self.stale_owed
        )
        bar_open = live.bar_open_of(now, self.period_s)
        close_in = (bar_open + self.period - now).total_seconds()
        ctx.ahead = close_in <= cfg.preclose_seconds
        ctx.open_places = {}

    def _quote_row(self, t: pd.Timestamp) -> int | None:
        """L2 / L5 - THE exec bar a quote stamped ``t`` belongs to, by its server time: the forming bar, the
        row after the series' last closed bar, when the quote's bar opens after it and no expected bar before
        it is still missing (``_outstanding``); else None - a quote of a bar already closed, or one whose
        predecessor is not read yet, is judged by nothing (the steps run in bar order: its visit, the latch,
        the withdrawal and the BUY P2 extremes wait; the closed bar's own extremes are applied at its
        close)."""
        b = self._bar_open(self.exec_tf, t)
        last = self.live.last_open(self.exec_tf)
        if last is not None and b <= last:
            return None
        if any(tf == self.exec_tf and o < b for tf, o in self._outstanding(t)):
            return None
        return len(self._exec())

    def _set_exec(self, ctx: Ctx) -> None:
        """The exec bars and the forming bar's extremes (not a safety step: ``_safety`` runs without them)."""
        ex = self._exec()
        ctx.ex, ctx.n = ex, len(ex)
        tick = ctx.tick
        ctx.qrow = None if tick is None or not ctx.quote_fresh else self._quote_row(_ts(tick.time_utc))
        if ctx.qrow is not None and tick is not None:
            if self.fx is None or self.fx.n != ctx.qrow:
                self.fx = Forming(ctx.qrow, tick.bid, tick.bid)
            else:
                self.fx.hi, self.fx.lo = max(self.fx.hi, tick.bid), min(self.fx.lo, tick.bid)
            ctx.fx = self.fx
        elif self.fx is not None and self.fx.n == ctx.n:
            ctx.fx = self.fx

    def _stale_debt(self, ctx: Ctx, overdue: bool = False) -> None:
        """L7 / L2 - THE stale debt (``stale_owed``): latched the moment the stale data falls due (more
        than one bar, the market open) with something to remove or interrupt; it outlives the recovery and
        the market's close (it is sent at the first cycle after the reopening) and is released only once
        nothing is owed - no unfilled order of the magic rests (this cycle's orders read) and no setup
        without a fill is left to interrupt (a setup waiting for its entry deal defers it)."""
        owed = bool(ctx.orders) or any(self._left_to_interrupt(cd) for cd in self.cands.values())
        if overdue and not ctx.market_closed and owed and not self.stale_owed:
            self.stale_owed = True
            log.warning("the data has been stale since %s: the removals owed are performed", self.stale_since)
        elif self.stale_owed and not owed:
            self.stale_owed = False
            log.info("the stale removals owed are done")

    def _settle_stale(self, ctx: Ctx) -> None:
        """L8 - the ONE place the stale condition ends, after every read of the cycle: market closed, or
        every read succeeded and was fresh. A read that fails later in the cycle never lets it end."""
        if ctx.market_closed or (ctx.quote_fresh and ctx.bars_fresh and not ctx.read_failed):
            self.stale_since = None

    def _gate(
        self,
        acct: AccountSnapshot | None = None,
        term: TerminalSnapshot | None = None,
        ctx: Ctx | None = None,
    ) -> tuple[bool, str]:
        """L1 - the live gate on fresh account and terminal snapshots (read here when not given)."""
        if acct is None or term is None:
            try:
                acct, term = self.gw.account(), self.gw.terminal()
            except (TaaError, OSError, ValueError) as exc:
                if ctx is not None:
                    self._read_failed(ctx, "the account / terminal snapshot", exc)
                return False, f"snapshots failed: {exc}"
        if (acct.login, acct.server) != (self.login, self.server):
            self.account_switched = True  # latched: not an ordinary failed gate (L1)
            return False, "the account is not the pinned one"
        res = evaluate_gate(
            self.cfg.mode,
            self.cfg.env,
            account=acct,
            terminal=term,
            risk_config_ok=self.risk_config_ok,
            kill_switch_active=self.kill.is_active(),
            latched_breakers=(),
            day_plan_ok=True,
            day_plan_detail="zone runner: no day plan",
        )
        return res.passed, "; ".join(f"{cond.value}: {detail}" for cond, detail in res.failures)

    # ======================================================================================= L8: tracking

    def _track(self, ctx: Ctx) -> None:
        """The broker's state of what this process sent, and the checks of L8's hands-off: a place of unknown
        outcome searched by its key (cause 1), orders of ours gone or filled unexplained (2), positions open
        without their entry deal or gone without an exit deal (3), anything of the magic not ours (4), a fill
        of another volume (5), removals / closes / market entries not done (6), the owner's hand (7)."""
        store = self._store()
        now = ctx.now
        lot = self.cfg.lot
        orders = {o.ticket: o for o in ctx.orders}
        positions = {p.ticket: p for p in ctx.positions}
        ins = [d for d in ctx.deals if d.entry == c.DEAL_ENTRY_IN]
        in_by_key = {k: d for d in ins if (k := live.parse_comment(d.comment)) is not None}
        in_by_order = {d.order: d for d in ins if d.order}
        in_positions = {d.position_id for d in ins}
        pos_by_key = {k: p for p in ctx.positions if (k := live.parse_comment(p.comment)) is not None}
        hist_by_ticket = {h.ticket: h for h in ctx.history}
        hist_by_key = {k: h for h in ctx.history if (k := live.parse_comment(h.comment)) is not None}

        for p in ctx.positions:
            k = live.parse_comment(p.comment)
            if k is None or k not in self.ours:
                self.not_ours_positions[p.ticket] = f"{p.comment!r} at {p.price_open}"
                self._enter_hands_off(
                    f"a position of the magic that is not ours: {p.ticket} {p.comment!r}", now
                )
                return
        for d in ins:
            k = live.parse_comment(d.comment)
            if d.ticket not in self.seen_deals and (k is None or k not in self.ours):
                self._enter_hands_off(
                    f"an entry deal of the magic that is not ours: {d.ticket} {d.comment!r}", now
                )
                return
        self.our_positions |= {d.position_id for d in ins} | set(positions)

        # 5: a fill whose volume is not the lot
        for d in ins:
            if d.ticket not in self.seen_deals and abs(d.volume - lot) > VOL_EPS:
                self._enter_hands_off(f"a fill of {d.volume}, not {lot}: deal {d.ticket} {d.comment!r}", now)
                return
        for p in ctx.positions:
            if abs(p.volume - lot) > VOL_EPS:
                self._enter_hands_off(f"position {p.ticket} {p.comment!r} holds {p.volume}, not {lot}", now)
                return

        # 1: the place requests of this run, their broker state (only the open ones are read: the rows of a
        # filled, cancelled or expired placement are done, and they grow with every placement of a run)
        for row in self._open_place_rows():
            key = live.parse_comment(row.comment or "")
            if row.order_state != "open" or key is None or key not in self.ours:
                continue
            ro = next((x for x in ctx.orders if live.parse_comment(x.comment) == key), None)
            rd = in_by_key.get(key)
            if ro is not None or rd is not None or key in pos_by_key:
                ticket = ro.ticket if ro is not None else (rd.order if rd is not None and rd.order else None)
                if row.state != "sent" or (ticket is not None and row.order_ticket != ticket):
                    store.update_request(
                        row.id,
                        state="sent",
                        order_ticket=ticket or row.order_ticket,
                        sent_at=row.sent_at or now.to_pydatetime(),
                    )
                self._end_pending(self.unknown_since, key)
                continue
            h = hist_by_key.get(key) or (
                hist_by_ticket.get(int(row.order_ticket)) if row.order_ticket else None
            )
            st = None if h is None else _HISTORY_STATES.get(h.state)
            if h is not None and h.state == c.ORDER_STATE_REJECTED:
                st = "expired"  # never rested: gone without a fill, like an expired one
            if h is not None and st in ("cancelled", "filled"):
                # found in the history only: its ticket is known from now on like an accepted one's (L8) - a
                # cancel the runner did not request is cause 7, a fill without its entry deal cause 2's timer
                self._known_order(h.ticket, key)
                self._end_pending(self.unknown_since, key)
                continue
            if st == "expired":
                fields: dict[str, Any] = {"order_state": st, "closed_at": now.to_pydatetime()}
                if row.state in ("intent", "unknown"):
                    fields["state"] = "moot"
                store.update_request(row.id, **fields)
                self._end_pending(self.unknown_since, key)
                continue
            if row.state in ("intent", "unknown"):
                since = self.unknown_since.setdefault(key, _ts(row.intent_at))
                if now - since > self.period:
                    self._enter_hands_off(f"the place {row.comment} of unknown outcome was not found", now)
                    return

        # remove / modify / close of unknown outcome, judged by the ticket
        self._settle_pending(ctx)

        tick = self._spec().tick_size
        # 2: orders of ours that left the open orders
        for ticket, key in list(self.seen_orders.items()):
            if ticket in orders:
                self._end_pending(self.gone_since, ticket)
                continue
            h = hist_by_ticket.get(ticket)
            st = None if h is None else _HISTORY_STATES.get(h.state)
            if st == "cancelled":
                if ticket not in self.removes_sent:
                    self._enter_hands_off(
                        f"order {ticket} ({live.make_comment(*key)}) was cancelled by hand", now
                    )
                    return
                self._mark_place(key, "cancelled", now)
                del self.seen_orders[ticket]
                self._end_pending(self.gone_since, ticket)
                continue
            if st == "expired":
                self._mark_place(key, "expired", now)
                del self.seen_orders[ticket]
                self._end_pending(self.gone_since, ticket)
                continue
            if ticket in in_by_order or key in in_by_key:
                del self.seen_orders[ticket]
                self._end_pending(self.gone_since, ticket)
                continue
            since = self.gone_since.setdefault(ticket, now)
            if now - since > self.period:
                what = (
                    "shown filled without its entry deal"
                    if st == "filled" or key in pos_by_key
                    else ("gone without a history state or a deal")
                )
                self._enter_hands_off(f"order {ticket} ({live.make_comment(*key)}) {what}", now)
                return

        # 3 (and 2): the pending entries (L5) - THE registry ``self.entries``: a position of ours seen without
        # its entry deal, an order of ours shown filled in the history without its entry deal
        for p in ctx.positions:
            if p.ticket in in_positions:
                why = self._position_differs(p, tick)
                if why:
                    self._enter_hands_off(
                        f"position {p.ticket} {p.comment!r} was changed by hand: {why}", now
                    )
                    return
                continue
            pk = live.parse_comment(p.comment)
            if pk is not None:
                self.entries.setdefault(
                    ("position", p.ticket), PendingEntry("position", p.ticket, pk, _ts(p.time_utc), now)
                )
        for h in ctx.history:
            k = live.parse_comment(h.comment)
            if (
                h.state == c.ORDER_STATE_FILLED
                and k is not None
                and k in self.ours
                and h.ticket not in in_by_order
                and k not in in_by_key
            ):
                at = _ts(h.time_done_utc or h.time_setup_utc)
                self.entries.setdefault(("order", h.ticket), PendingEntry("order", h.ticket, k, at, now))
        # a pending entry ends only when its entry deal is read: the disappearance of the position or of the
        # history row never ends it (L8)
        for ek, e in list(self.entries.items()):
            if e.kind == "position":
                explained = e.ticket in in_positions
            else:
                explained = e.ticket in in_by_order or e.key in in_by_key
            if explained:
                del self.entries[ek]
            elif now - e.since > self.period:
                if e.kind == "position":
                    what = "is open" if e.ticket in positions else "was open, then gone,"
                    why = f"position {e.ticket} {what} without its entry deal"
                else:
                    why = (
                        f"order {e.ticket} ({live.make_comment(*e.key)}) shown filled without its entry deal"
                    )
                self._enter_hands_off(why, now)
                return
        ctx.holds = self._holds()

        # 3: positions of ours gone without an exit deal; 7: an exit deal that is not SL / TP / ours
        out_vol: dict[int, float] = {}
        for d in ctx.deals:
            if d.entry == c.DEAL_ENTRY_IN or d.position_id not in self.our_positions:
                continue
            out_vol[d.position_id] = out_vol.get(d.position_id, 0.0) + d.volume
            if d.ticket in self.exits_checked:
                continue
            self.exits_checked.add(d.ticket)
            ours_close = d.reason == c.DEAL_REASON_EXPERT and d.position_id in self.closes_sent
            if d.reason not in (c.DEAL_REASON_SL, c.DEAL_REASON_TP) and not ours_close:
                self._enter_hands_off(
                    f"position {d.position_id} was closed by deal {d.ticket} of reason {d.reason}: "
                    "neither its SL / TP nor the runner's own close",
                    now,
                )
                return
        for d in ins:
            pos = d.position_id
            if live.parse_comment(d.comment) not in self.ours:
                continue
            if pos in positions or out_vol.get(pos, 0.0) >= d.volume - VOL_EPS:
                self._end_pending(self.exit_since, pos)
                continue
            since = self.exit_since.setdefault(pos, now)
            if now - since > self.period:
                self._enter_hands_off(f"position {pos} is gone without an exit deal explaining it", now)
                return

        # 6: closes and market entries not done within one exec_tf bar (the removals: ``_track_orders``)
        for ticket in list(self.close_since):
            if ticket not in positions:
                del self.close_since[ticket]
            elif now - self.close_since[ticket] > self.period:
                self._enter_hands_off(f"the close of position {ticket} was not done within one bar", now)
                return
        for key in list(self.market_since):
            if key in in_by_key:
                del self.market_since[key]
            elif now - self.market_since[key] > self.period:
                self._enter_hands_off(
                    f"the market entry {live.make_comment(*key)} made no deal in one bar", now
                )
                return

        ctx.open_places = {
            (r.setup_id, r.name): r
            for r in self._open_place_rows()
            if r.order_state == "open" and live.parse_comment(r.comment or "") in self.ours
        }

    def _open_place_rows(self) -> list[ZoneLiveRequestRow]:
        """The place requests of this run whose order is still open (``intent`` / ``sent`` / ``unknown``)."""
        return self._store().requests(
            kinds=("place",), states=("intent", "sent", "unknown"), order_states=("open",)
        )

    def _pause_stale_removal_timers(self, ctx: Ctx) -> None:
        """L1 "Within one exec_tf bar" - for a stale removal waiting for the reopening (L2), the time the
        market is closed does not count: each closed cycle moves the start of its one-bar timer (L8 cause 6)
        on by the time since the timer was last seen."""
        seen = self._remove_seen
        for ticket, since in list(self.remove_since.items()):
            last = seen.get(ticket)
            if last is not None and ctx.market_closed and self.unwanted.get(ticket) == "stale":
                self.remove_since[ticket] = since + (ctx.now - last)
            seen[ticket] = ctx.now
        for ticket in [t for t in seen if t not in self.remove_since]:
            del seen[ticket]

    def _track_orders(self, ctx: Ctx) -> None:
        """L8 "safety first" - the checks of hands-off that need only the account and the orders reads (and
        the timers already running), done in phase 2 whatever the later reads give: an order of the magic
        that is not ours (cause 4), a resting order of ours changed by hand (cause 7), a removal not done
        within one bar (cause 6). The checks that need the positions, the deals or the history stay in
        ``_track``."""
        if not self.initialized or self.hands_off is not None:
            return
        now = ctx.now
        orders = {o.ticket: o for o in ctx.orders}
        tick = self._spec().tick_size
        # 4: an order of the magic that is not ours
        for o in ctx.orders:
            k = live.parse_comment(o.comment)
            if k is None or k not in self.ours:
                self.not_ours_orders[o.ticket] = f"{o.comment!r} at {o.price_open}"
                self._enter_hands_off(
                    f"an order of the magic that is not ours: {o.ticket} {o.comment!r}", now
                )
                return
        # 7: a resting order of ours differs from what the broker last accepted
        for o in ctx.orders:
            k = live.parse_comment(o.comment)
            if k is None:
                continue
            self._known_order(o.ticket, k)
            exp = self.order_expect.get(o.ticket)
            if exp is None:
                continue
            why = self._order_differs(o, exp, tick)
            if why:
                self._enter_hands_off(f"order {o.ticket} {o.comment!r} was changed by hand: {why}", now)
                return

        # 2: an order of ours gone from the open orders is timed from this read (its explanation - a
        # history state, a deal - needs the later reads: ``_track``)
        for ticket in self.seen_orders:
            if ticket not in orders:
                self.gone_since.setdefault(ticket, now)
        # 6: a removal not done within one exec_tf bar (the closed market's time taken out, L1)
        for ticket in list(self.remove_since):
            if ticket not in orders:
                del self.remove_since[ticket]
            elif now - self.remove_since[ticket] > self.period:
                self._enter_hands_off(f"the removal of order {ticket} was not done within one bar", now)
                return

    def _end_pending(self, timers: dict[Any, pd.Timestamp], key: Any) -> None:
        """L8 - the ONE way a broker condition's timer ends in ``_track``: its explanation has been read (the
        caller tests it). What the condition watches disappearing is never an explanation."""
        timers.pop(key, None)

    def _holds(self) -> dict[int, pd.Timestamp]:
        """L5 - read from THE registry of pending entries (``self.entries``): each setup that waits, and the
        broker time from which it waits - its bar loop (the close steps of the entry's bar and every later
        one), its deals from then on, and every other judgement of it (``_waits``). A setup waits for its own
        pending entries only; the other setups go on - except where L4's hour-wide order is at stake: while a
        pending entry can still make its candidate the hour's setup (``_entry_is_visit``, ``_may_take_hour``),
        the hour's other candidates wait with it."""
        holds: dict[int, pd.Timestamp] = {}
        for e in self.entries.values():
            holds[e.setup] = min(holds.get(e.setup, e.at), e.at)
        for e in self.entries.values():
            cand = self.cands.get(e.setup)
            hour = None if cand is None else self._hour_of(cand)
            if cand is None or hour is None or not self._entry_is_visit(cand, e.key[1], e.at):
                continue
            key = (self._row_at(e.at), cand.visit.from_open, cand.visit.line)
            if self._may_take_hour(cand, key, hour):
                for other in hour.cands.values():
                    if other is not cand:
                        holds[other.id] = min(holds.get(other.id, e.at), e.at)
        return holds

    def _known_order(self, ticket: int, key: Key) -> None:
        """L8 - a placement's ticket becomes known (the accepted reply, a snapshot of the open orders, the
        history search of a place of unknown outcome): the ONE place that records it, so that causes 2 (it
        left the book unexplained or filled without its entry deal) and 7 (changed or cancelled by hand) apply
        to it from then on, whichever way it became known."""
        self.seen_orders[ticket] = key
        if ticket not in self.order_expect and key in self.place_payload:
            self.order_expect[ticket] = self._expect_of(self.place_payload[key])

    def _expect_of(self, request: dict[str, Any]) -> dict[str, Any]:
        exp = request.get("expiration")
        return {
            "price": float(request.get("price", 0.0)),
            "volume": float(request.get("volume", 0.0)),
            "sl": float(request.get("sl", 0.0)),
            "tp": float(request.get("tp", 0.0)),
            "exp": int(exp) if exp else None,  # the latest expiry the broker accepted
            "exp_pend": set(),  # expiries of modifies sent and not yet confirmed or refused
        }

    def _order_differs(self, o: BrokerOrder, exp: dict[str, Any], tick: float) -> str:
        half = tick / 2
        if abs(o.price_open - exp["price"]) > half:
            return f"price {o.price_open} (accepted {exp['price']})"
        if abs(o.volume - exp["volume"]) > VOL_EPS:
            return f"volume {o.volume} (accepted {exp['volume']})"
        if abs(o.sl - exp["sl"]) > half:
            return f"SL {o.sl} (accepted {exp['sl']})"
        if abs(o.tp - exp["tp"]) > half:
            return f"TP {o.tp} (accepted {exp['tp']})"
        if exp["exp"] is not None:
            have = (
                None
                if o.expiration_utc is None
                else int(self.gw.server_clock.utc_to_server_epoch(o.expiration_utc))
            )
            if have != exp["exp"] and have not in exp["exp_pend"]:
                return f"expiry {o.expiration_utc} (accepted {exp['exp']}, pending {sorted(exp['exp_pend'])})"
        return ""

    def _position_differs(self, p: BrokerPosition, tick: float) -> str:
        """L8 cause 7: a position's SL or TP is not its fill's nor a value the runner sent for it."""
        k = live.parse_comment(p.comment)
        if p.ticket not in self.pos_expect and (k is None or k not in self.place_payload):
            return ""
        exp = self._pos_exp(p)
        half = tick / 2
        # the latest stop the broker accepted, and the one of a modify still under way (L8 cause 7)
        allowed = [exp["sl"], *exp["pend"]]
        if not any(abs(p.sl - x) <= half for x in allowed):
            return f"SL {p.sl} (accepted {exp['sl']}, pending {sorted(exp['pend'])})"
        if abs(p.tp - exp["tp"]) > half:
            return f"TP {p.tp} (sent {exp['tp']})"
        return ""

    def _pos_exp(self, p: BrokerPosition) -> dict[str, Any]:
        """What the runner last had accepted for a position: ``sl`` (the latest accepted), ``pend`` (stops
        of modifies sent and not yet confirmed or refused), ``tp``. It starts from the placement's SL / TP."""
        exp = self.pos_expect.get(p.ticket)
        if exp is None:
            k = live.parse_comment(p.comment)
            req = self.place_payload.get(k) if k is not None else None
            sl, tp = (float(req.get("sl", 0.0)), float(req.get("tp", 0.0))) if req else (p.sl, p.tp)
            exp = {"sl": sl, "tp": tp, "pend": set()}
            self.pos_expect[p.ticket] = exp
        return exp

    def _modify_confirmed(self, pos: BrokerPosition, sl: float) -> None:
        """A stop modify of unknown outcome is seen in force: it is now the latest accepted stop."""
        exp = self._pos_exp(pos)
        exp["sl"] = sl
        exp["pend"].discard(sl)
        k = live.parse_comment(pos.comment)
        cand = self.cands.get(k[0]) if k is not None else None
        if cand is not None and cand.be_sent is not None and abs(sl - cand.be_sent) < 1e-9:
            cand.be_in_force.add(pos.ticket)

    def _mark_place(self, key: Key, state: str, now: pd.Timestamp) -> None:
        row = self._store().request_by_comment(live.make_comment(*key))
        if row is not None and row.order_state == "open":
            self._store().update_request(row.id, order_state=state, closed_at=now.to_pydatetime())

    def _settle_pending(self, ctx: Ctx) -> None:
        """Remove / modify / close requests of unknown outcome, judged by the broker's state of the ticket."""
        store = self._store()
        tick = self._spec().tick_size
        hist_by_ticket = {h.ticket: h for h in ctx.history}
        for key, (rid, payload) in list(self.pending.items()):
            kind, ticket = key
            order = next((o for o in ctx.orders if o.ticket == ticket), None)
            pos = next((p for p in ctx.positions if p.ticket == ticket), None)
            state: str | None = None
            if kind == "remove":
                if order is None:
                    h = hist_by_ticket.get(ticket)
                    state = "sent" if h is not None and h.state == c.ORDER_STATE_CANCELED else "moot"
            elif kind == "expiry":
                if order is None:
                    state = "moot"
                elif order.expiration_utc is not None and int(
                    self.gw.server_clock.utc_to_server_epoch(order.expiration_utc)
                ) >= int(payload.get("expiration", 0)):
                    state = "sent"
                    oexp = self.order_expect.get(ticket)
                    if oexp is not None:  # in force: now the latest accepted expiry
                        oexp["exp"] = int(payload.get("expiration", 0))
                        oexp["exp_pend"].discard(oexp["exp"])
            elif kind == "sltp":
                if pos is None:
                    state = "moot"
                elif live.stop_at_or_beyond(
                    pos.sl, float(payload.get("sl", 0.0)), pos.side is Side.BUY, tick
                ):
                    state = "sent"  # L8: at the level or nearer the TP: nothing is sent again
                    self._modify_confirmed(pos, float(payload.get("sl", 0.0)))
            elif kind == "close" and pos is None:
                state = "sent"
                self.close_wanted.pop(ticket, None)
            if state is not None:
                store.update_request(rid, state=state, closed_at=ctx.now.to_pydatetime())
                del self.pending[key]

    # ======================================================================================== hands-off

    def _enter_hands_off(self, why: str, now: pd.Timestamp) -> None:
        """L8 - placing stops; every resting order of the magic is removed; no position is touched; every
        setup not ended ends ``hands-off``; until the magic is flat."""
        if self.hands_off is not None:
            return
        self.hands_off, self.hands_off_at = why, now
        log.error(
            "HANDS-OFF: %s - placing stops, every order of the magic is removed, no position is touched, "
            "until the magic is flat",
            why,
        )
        for cand in list(self.cands.values()):
            if cand.unfinished:
                cand.dropped = False
                self._end(cand, "hands-off", None)
                log.error("setup %s ends hands-off", cand.id)
        if self.hour is not None and self.hour.cut_at is None:
            self.hour.cut_at = now
        self.close_wanted.clear()
        self.pending = {k: v for k, v in self.pending.items() if k[0] == "remove"}

    def _hands_off_cycle(self, ctx: Ctx) -> None:
        if self.hour is not None and self.hour.cut_at is None:
            self.hour.cut_at = ctx.now
        self._record_unjudged_entries(ctx)
        if not ctx.orders and not ctx.positions:
            self._leave_hands_off(ctx)
            return
        # `zone status` names what of the magic is not ours, for the whole hands-off (a position of it is the
        # owner's to close)
        for o in ctx.orders:
            if live.parse_comment(o.comment) not in self.ours:
                self.not_ours_orders.setdefault(o.ticket, f"{o.comment!r} at {o.price_open}")
        for p in ctx.positions:
            if live.parse_comment(p.comment) not in self.ours:
                self.not_ours_positions.setdefault(p.ticket, f"{p.comment!r} at {p.price_open}")
        self._hands_off_removals(ctx)

    def _hands_off_removals(self, ctx: Ctx) -> None:
        self._remove_in_order(list(ctx.orders), ctx, timers=False)

    def _leave_hands_off(self, ctx: Ctx) -> None:
        """L8 - the magic is flat: every request of the run closed, its keys no longer ours, a fresh start at
        the first H1 open after now, with no reservation."""
        now = ctx.now
        self._store().close_requests(now.to_pydatetime(), "closed when the hands-off ended")
        log.warning(
            "the magic is flat: the hands-off (%s, since %s) ends; the first decision at %s",
            self.hands_off,
            self.hands_off_at,
            self._next_open(now),
        )
        self.hands_off = self.hands_off_at = None
        self.seen_deals |= {d.ticket for d in ctx.deals}  # nothing of the hands-off is taken up again
        self.exits_checked |= {d.ticket for d in ctx.deals}
        self.ours.clear()
        self.place_payload.clear()
        self.order_expect.clear()
        self.pos_expect.clear()
        self.seen_orders.clear()
        self.cands.clear()
        self.pending.clear()
        self.close_wanted.clear()
        self.be_tries.clear()
        self.stale_owed = False
        self.unwanted.clear()
        self.interrupt_owed = None
        self.entries.clear()
        self.buffered = set()
        for timer in (
            self.unknown_since,
            self.gone_since,
            self.exit_since,
            self.remove_since,
            self.close_since,
            self.market_since,
        ):
            timer.clear()
        self.not_ours_orders.clear()
        self.not_ours_positions.clear()
        self.res_by = {}
        self.decide_from = self._next_open(now)
        if self.hour is not None and not self.hour.decided:
            self.hour.undecided = self.hour.undecided or "hands-off"

    # =============================================================================================== bars

    def _advance(self, ctx: Ctx) -> None:
        """The hours and the closed bars in time order: at each H1 open the hour's state; each closed bar
        with the broker's fills and exits of that bar, setup by setup (``_run_setups``); at each H1 close the
        arming and the visit records."""
        self._ensure_reader()
        n = len(self._exec())
        if not ctx.bars_fresh:
            # L2: a frame is behind. Nothing moves to another hour; the setups under way go on with the exec
            # bars that did arrive (their life needs only those)
            if self.hour is not None:
                self._run_setups(ctx, n)
                self._absorb(ctx)
            return
        while True:
            nxt = self._next_hour(ctx)
            if nxt is None:
                break
            i, open_ts, o = nxt
            if self.hour is not None:
                self._run_setups(ctx, self._rows_before(open_ts))
                if self._hour_waits(open_ts):
                    break  # L5: a setup the hour's close needs waits for its entry deal
                self._close_hour(ctx)
            try:
                self._begin_hour(open_ts, o, i, ctx)
            except ZoneError as exc:
                log.warning("no candidates at %s: %s", open_ts, exc)
                self.hour = HourState(open_ts, i, o, self._reserved(open_ts), undecided=str(exc))
        self._run_setups(ctx, n)
        self._absorb(ctx)

    def _rows_before(self, t: pd.Timestamp) -> int:
        """The number of exec rows opening before ``t``."""
        return int(np.searchsorted(self._ex_open_ns(), t.value, side="left"))

    def _hour_waits(self, open_ts: pd.Timestamp) -> bool:
        """L4 / L5 / L6 - the hour under way closes (and the next one begins) only once the close steps of its
        last exec bar are done for every setup that the close needs: the hour's own candidates (its visit
        records, ``no fill`` of an unvisited one) and a live hour's setup of an earlier hour (the reservation
        of the next hour). Only a setup that waits for its entry deal (``_holds``) can lag."""
        hour = self.hour
        if hour is None:
            return False
        r = self._rows_before(open_ts)
        return any(
            cd.next_j < r and (cd.hour_open == hour.open or (cd.chosen and cd.is_live and not cd.dropped))
            for cd in self.cands.values()
        )

    def _next_hour(self, ctx: Ctx) -> tuple[int, pd.Timestamp, float] | None:
        h1 = self.live.frames["H1"]
        idx = self.start_hour_i if self.hour is None else self.hour.i + 1
        if idx < len(h1):
            return idx, _ts(h1["open_time"].iloc[idx]), float(h1["open"].iloc[idx])
        fh = self._forming(ctx)
        if fh is None or not ctx.bars_fresh or ctx.tick is None:
            return None
        if self.hour is not None and fh[0] <= self.hour.open:
            return None
        if self._outstanding(ctx.now):
            return None  # L2: the close steps of every expected bar come before the hour (and its decision)
        return len(h1), fh[0], fh[1]

    def _run_setups(self, ctx: Ctx, upto: int) -> None:
        """L5 - every setup's own bar loop through the exec rows before ``upto``, in row order across the
        setups: at each row, the broker's fills and exits of the setups at that row are judged against the
        state their earlier bars left, then the row's close steps. A setup that waits for an entry deal
        (``ctx.holds``) stops at the row of that entry; the others go on. Once its deal is read, the waiting
        setup catches up here, bar by bar."""
        holds = {sid: self._row_at(t) for sid, t in ctx.holds.items()}
        start = min((cd.next_j for cd in self.cands.values()), default=upto)
        for j in range(start, upto):
            group = [
                cd
                for cd in list(self.cands.values())
                if cd.next_j == j and (self.hands_off is not None or j < holds.get(cd.id, upto))
            ]
            if not group:
                continue
            self._absorb(ctx, upto_row=j)
            self._on_exec_close(j, ctx, group)
            for cd in group:
                cd.next_j = j + 1
        self._rows_done = max(self._rows_done, upto)

    def _close_hour(self, ctx: Ctx) -> None:
        hour = self.hour
        if hour is None:
            return
        if hour.i < len(self.live.frames["H1"]):
            self.prev_hours[hour.i] = hour  # the record of its bar compares with what it did
            self._process_closed_h1_row(hour.i, ctx)
        self._finish_hour(hour)
        for k in [k for k in self.prev_hours if k < hour.i - 3]:
            del self.prev_hours[k]

    def _replay_life(self, cand: Cand, upto: int) -> None:
        """The setup's life from its first bar through the bar ``upto`` (a revival at that bar - never
        later)."""
        ex = self._exec()
        for j in range(cand.plan.j0, min(upto, len(ex) - 1) + 1):
            if cand.dropped or not cand.is_live:
                return
            if cand.fills:
                self._be_check(cand, j, ex)
            else:
                self._life_step(cand, j, ex)

    def _row_at(self, t: pd.Timestamp) -> int:
        """The exec row of the bar a time falls in (the forming bar is the row after the last closed one)."""
        return int(np.searchsorted(self._exec_close_ns(), t.value, side="right"))

    # --------------------------------------------------------------------------------------- the record

    def _save(self, cand: Cand) -> None:
        store = self._store()
        state = {
            "fills": [
                {
                    "name": f.name,
                    "j": f.j,
                    "price": f.price,
                    "broker_price": f.broker_price,
                    "position": f.position,
                    "deal": f.deal,
                    "time": f.time.isoformat(),
                    "volume": f.volume,
                    "comment": None if f.key is None else live.make_comment(*f.key),
                }
                for f in cand.fills.values()
            ],
            "closed": {
                str(p): {"time": r.time.isoformat(), "price": r.price, "reason": r.reason}
                for p, r in cand.closed.items()
            },
            "close_reason": {str(p): r for p, r in cand.close_reason.items()},
            "p2_gone": cand.p2_gone,
            "p1_refused": cand.p1_refused,
            "p2_off": cand.p2_off,
            "refusals": cand.refusals,
            "h1_open": cand.visit.h1_open,
            "anchor": cand.visit.anchor,
            "touch_key": list(cand.touch_key) if cand.touch_key else None,
            "be_j": cand.be_j,
            "be_sent": cand.be_sent,
            "dropped": cand.dropped,
            "drop_final": cand.drop_final,
            "life_outcome": cand.outcome,
            "drop_reason": cand.drop_reason,
            "faults": {str(p): w for p, w in cand.faults.items()},
        }
        exit_how, exit_price, exit_broker, exit_time = self._exit_summary(cand)
        store.update_setup(
            cand.id,
            self.now().to_pydatetime(),
            state="dropped" if cand.dropped else cand.status,
            # L4: a drop for the other's visit is not final before the hour's close - the row has no outcome
            # until then (its life outcome is kept beside, in ``fills_json``); the start ends it ``restart``
            chosen=cand.chosen,
            visited_at=None if cand.visited_at is None else cand.visited_at.to_pydatetime(),
            fills_json=json.dumps(state),
            be_on=cand.be_on,
            be_sl=cand.be_sl,
            exit_how=exit_how,
            exit_price=exit_price,
            exit_broker_price=exit_broker,
            exit_time=None if exit_time is None else exit_time.to_pydatetime(),
            outcome=None if cand.dropped and not cand.drop_final else cand.outcome,
            end_close_time=None if cand.end_close is None else cand.end_close.to_pydatetime(),
            note="" if not cand.drop_reason else f"dropped: {cand.drop_reason}",
        )

    def _exit_summary(self, cand: Cand) -> tuple[str | None, float | None, float | None, pd.Timestamp | None]:
        if cand.exit_how is None or not cand.closed:
            return None, None, None, None
        first = min(cand.closed.values(), key=lambda r: r.time)
        how = cand.exit_how
        logic = {"SL": cand.plan.sl, "TP": cand.plan.tp, "BE": cand.be_sl}.get(how)
        return how, logic, first.price, first.time

    # --------------------------------------------------------------------------------------- fills / exits

    def _event_key(self, d: Deal) -> tuple[float, ...]:
        """L5 - deals in time order (to the millisecond); at one time every entry first - P1 before P2, two
        candidates in L4's order - then the exits: stops before TP, then any other; then by deal ticket."""
        t = float(_ts(d.time_utc).value // 1_000_000)
        if d.entry == c.DEAL_ENTRY_IN:
            k = live.parse_comment(d.comment)
            cand = None if k is None else self.cands.get(k[0])
            if cand is None or k is None:
                return (t, 0.0, math.inf, math.inf, math.inf, math.inf, 2.0, float(d.ticket))
            touch = cand.touch_key[0] if cand.touch_key is not None else self._row_at(_ts(d.time_utc))
            rank = 0.0 if k[1] == "P1" else 1.0
            return (
                t,
                0.0,
                float(touch),
                cand.visit.from_open,
                cand.visit.line,
                float(cand.id),
                rank,
                float(d.ticket),
            )
        rr = 0.0 if d.reason == c.DEAL_REASON_SL else 1.0 if d.reason == c.DEAL_REASON_TP else 2.0
        return (t, 1.0, rr, 0.0, 0.0, 0.0, 0.0, float(d.ticket))

    def _absorb(self, ctx: Ctx, upto_row: int | None = None) -> None:
        """The broker's fills and exits of ours not yet taken, in L5's order. An entry is judged only against
        exec bars that cover its time - not after the next bar to judge, not past the end of a local series
        that is behind; it waits (the position keeps its broker SL / TP, nothing new is placed) and is judged
        at its own bar once the frame catches up. Nothing later in the order is taken before it, nor after an
        entry whose deal is not read yet (L5)."""
        if self.hands_off is not None:
            return
        open_positions = {p.ticket for p in ctx.positions}
        ex_n = len(self._exec())
        pos_setup: dict[int, int] = {}  # position -> its setup (an exit deal carries no key)
        for cd in self.cands.values():
            for f in cd.fills.values():
                pos_setup[f.position] = cd.id
            for pos in cd.faults:
                pos_setup.setdefault(pos, cd.id)
        for p in ctx.positions:
            if (pk := live.parse_comment(p.comment)) is not None:
                pos_setup.setdefault(p.ticket, pk[0])
        ours_in = set()
        for d in ctx.deals:
            if d.entry == c.DEAL_ENTRY_IN and (k := live.parse_comment(d.comment)) in self.ours:
                ours_in.add(d.position_id)
                if k is not None:
                    pos_setup.setdefault(d.position_id, k[0])
        events = [
            d
            for d in ctx.deals
            if d.ticket not in self.seen_deals
            and (
                (d.entry == c.DEAL_ENTRY_IN and live.parse_comment(d.comment) in self.ours)
                or (
                    d.entry != c.DEAL_ENTRY_IN
                    and (d.position_id in ours_in or d.position_id in self.our_positions)
                )
            )
        ]
        blocked: set[int | None] = set()  # setups whose deal waits: their later deals wait too (L5)
        buffered: set[int] = set()  # setups with an entry deal read but not judged yet (L10)
        self.buffered = buffered
        for d in sorted(events, key=self._event_key):
            t = _ts(d.time_utc)
            row = self._row_at(t)
            k = live.parse_comment(d.comment) if d.entry == c.DEAL_ENTRY_IN else None
            sid = k[0] if k is not None else pos_setup.get(d.position_id)
            if sid in blocked:
                if k is not None:
                    buffered.add(k[0])
                continue
            cand = None if sid is None else self.cands.get(sid)
            held = None if sid is None else ctx.holds.get(sid)
            # a deal of a setup is judged only after the close steps of its setup's earlier bars (its own
            # bar loop, ``Cand.next_j``), never while the setup waits for an entry deal
            limit = cand.next_j if cand is not None else (ex_n if upto_row is None else upto_row)
            waits = held is not None and t >= held
            if d.entry == c.DEAL_ENTRY_IN:
                waits = waits or row > limit or (row >= ex_n and not ctx.exec_fresh)
            else:
                waits = waits or row > limit
            if waits:
                blocked.add(sid)
                if d.entry == c.DEAL_ENTRY_IN:
                    if k is not None:
                        buffered.add(k[0])
                    # L4: an entry that can still make its candidate the hour's setup holds the hour's order
                    hour = None if cand is None or k is None else self._hour_of(cand)
                    if (
                        cand is not None
                        and k is not None
                        and hour is not None
                        and self._entry_is_visit(cand, k[1], t)
                        and self._may_take_hour(cand, (row, cand.visit.from_open, cand.visit.line), hour)
                    ):
                        blocked |= {other.id for other in hour.cands.values()}
                continue
            self.seen_deals.add(d.ticket)
            if d.entry == c.DEAL_ENTRY_IN:
                self._on_in(d, row, d.position_id in open_positions, ctx)
            else:
                self._on_out(d)
            if self.hands_off is not None:
                return

    def _record_entry(self, d: Deal, key: Key) -> None:
        """The broker's evidence of an entry deal of ours, kept apart from any judgement of its setup: its
        placement's row gets the fill (``filled``, the deal and the position) - L8's record, also under
        hands-off, where the deal is recorded only (L5)."""
        store = self._store()
        self.our_positions.add(d.position_id)
        req = store.request_by_comment(live.make_comment(*key))
        if req is not None:
            store.update_request(
                req.id,
                state="sent",
                order_state="filled",
                position_ticket=d.position_id,
                deal_ticket=d.ticket,
                closed_at=_ts(d.time_utc).to_pydatetime(),
            )

    def _record_unjudged_entries(self, ctx: Ctx) -> None:
        """L5 - under hands-off nothing of a setup is judged or acted on again, and its entry deals read from
        then on are recorded only (``_record_entry``)."""
        for d in ctx.deals:
            if d.entry != c.DEAL_ENTRY_IN or d.ticket in self.seen_deals:
                continue
            key = live.parse_comment(d.comment)
            if key is None or key not in self.ours:
                continue
            self.seen_deals.add(d.ticket)  # recorded: never judged later
            self._record_entry(d, key)
            log.warning("hands-off: the entry deal %s of %s is recorded only", d.ticket, d.comment)

    def _on_in(self, d: Deal, j: int, position_open: bool, ctx: Ctx) -> None:
        """One entry deal of ours at its bar ``j`` (L5 "Fills"): a visit of its candidate (L4), then the
        setup's fill when its life allows it at that bar; any other fill is closed at market."""
        key = live.parse_comment(d.comment)
        if key is None:
            return
        sid, name, _n = key
        when = _ts(d.time_utc)
        self._record_entry(d, key)
        self.market_since.pop(key, None)
        cand = self.cands.get(sid)
        if cand is not None and self._entry_is_visit(cand, name, when):
            self._consider_visit(cand, (j, cand.visit.from_open, cand.visit.line), when)  # the bid reached it
        why = self._disallowed(cand, key, j, when, ctx)
        if why is None and cand is not None:
            if not cand.fills and j >= len(self._exec()):
                cand.rejudge_j = j  # judged on the quotes so far: again at the bar's close (L5)
            cand.fills[name] = FillRec(
                name, j, cand.logic_price(name), d.price, d.position_id, d.ticket, when, d.volume, key=key
            )
            cand.remaining[d.position_id] = d.volume
            self._save(cand)
            log.info(
                "setup %s %s filled at %s (logic %s) on bar %s", sid, name, d.price, cand.logic_price(name), j
            )
            return
        boundary = self.last_cycle_at is None or self.last_cycle_at < live.bar_open_of(when, self.period_s)
        explained = boundary or (why or "").startswith(("withdrawn", "the other candidate"))
        if cand is not None:
            cand.faults[d.position_id] = f"{name}: {why}"
            self._save(cand)
        level = logging.WARNING if explained else logging.ERROR
        if position_open:
            log.log(
                level,
                "%sthe fill %s of setup %s is not the setup's (%s): closed at market",
                "" if explained else "FAULT: ",
                live.make_comment(*key),
                sid,
                why,
            )
            self._owe_close(d.position_id, f"not the setup's fill: {why}")
        else:
            log.log(
                level,
                "%sthe fill %s of setup %s (already closed) was not the setup's (%s)",
                "" if explained else "FAULT: ",
                live.make_comment(*key),
                sid,
                why,
            )

    def _disallowed(self, cand: Cand | None, key: Key, j: int, when: pd.Timestamp, ctx: Ctx) -> str | None:
        """L5 - why an entry of ours is not one of the setup's fills (None: it is)."""
        sid, name, n = key
        if cand is None:
            return "its setup is not under way"
        if n < self._store().count_places(sid, name) - 1:
            return "a superseded placement"
        if name in cand.fills:
            return f"a second {name} fill"
        if not cand.is_live:
            return f"after the setup's end ({cand.outcome})"
        if cand.exit_pending:
            return "after the setup's end (its exit, the bar still to be judged)"
        if cand.dropped:
            return f"the candidate was dropped ({cand.drop_reason})"
        hour = self._hour_of(cand)
        if hour is not None and hour.chosen is not None and hour.chosen is not cand:
            return "the other candidate has the hour"
        if not cand.chosen and when >= cand.hour_open + HOUR:
            return "its hour ended without a visit"
        if name == "P2":
            if "P1" not in cand.fills:
                return "a P2 without its P1 filled"
            if cand.be_on and cand.be_j is not None and j > cand.be_j:
                return "a P2 after the break-even"
            return None
        return self._rule_check(cand, j, ctx)

    def _rule_check(self, cand: Cand, j: int, ctx: Ctx) -> str | None:
        """Rules 1 - 3 of L5 at the P1's bar: expired, the closed-hour cancel, the fill-moment block, the
        withdrawal (the bar's high / low, the forming bar's so far)."""
        ex = self._exec()
        plan = cand.plan
        if not 0 <= j - plan.per_h < len(ex):
            return None
        oh = float(ex.open[j - plan.per_h])
        if live.expired_at(plan, j):
            return "expired (rule 1)"
        if 0 <= j - 1 < len(ex) and live.closed_hour_cancel(plan, j, float(ex.close[j - 1]), oh):
            return "the closed-hour cancel (rule 2)"
        if live.entry_blocked(plan, plan.p1, oh):
            return "blocked (rule 3)"
        if j >= len(ex):
            hi_lo = (ctx.fx.hi, ctx.fx.lo) if ctx.fx is not None and ctx.fx.n == j else None
        else:
            hi_lo = (float(ex.high[j]), float(ex.low[j]))
        if hi_lo is not None and live.moved_away(plan, j, hi_lo[0], hi_lo[1]):
            return "withdrawn (rule 1)"
        return None

    def _on_out(self, d: Deal) -> None:
        """An exit deal at its own bar. A position is closed when the volume of its exit deals reaches the
        volume filled."""
        pos = d.position_id
        for cand in list(self.cands.values()):
            if any(f.position == pos for f in cand.fills.values()):
                when = _ts(d.time_utc)
                cand.outs.setdefault(pos, ClosedRec(when, d.price, d.reason))
                cand.out_last[pos] = max(when, cand.out_last.get(pos, when))
                cand.remaining[pos] = cand.remaining.get(pos, 0.0) - d.volume
                if cand.remaining[pos] <= VOL_EPS:
                    self._position_gone(cand, pos)
                return

    def _position_gone(self, cand: Cand, pos: int) -> None:
        rec = cand.outs.get(pos)
        if rec is None or pos in cand.closed:
            return
        self.close_wanted.pop(pos, None)
        cand.closed[pos] = rec
        self._maybe_finish(cand)

    def _maybe_finish(self, cand: Cand) -> None:
        """The setup's exit is its first exit deal; it ends when its last position has closed (L5)."""
        if not cand.is_live or not cand.fills:
            return
        if any(f.position not in cand.closed for f in cand.fills.values()):
            self._save(cand)
            return
        if cand.rejudge_j is not None:
            # an exit inside the first fill's bar: the setup is over for every later deal and order, its
            # outcome waits for that bar's judgement on its true extremes (L5)
            cand.exit_pending = True
            self._save(cand)
            return
        pos, first = min(cand.closed.items(), key=lambda kv: kv[1].time)
        last = max(cand.out_last.get(p, r.time) for p, r in cand.closed.items())
        how = classify_exit(
            first.reason,
            be_in_force=pos in cand.be_in_force,
            own_close_at_be=cand.close_reason.get(pos) == "BE" and pos in self.closes_sent,
        )
        cand.exit_how = how
        cand.close_reason.clear()
        # L6: the reservation runs to the close of the bar in which the LAST position closed
        end = live.bar_open_of(last, self.period_s) + self.period
        self._end(cand, "traded", end)
        log.info("setup %s exited %s at %s", cand.id, how, first.price)

    # ================================================================================================ bar
    # events

    def _on_exec_close(self, j: int, ctx: Ctx, cands: list[Cand]) -> None:
        """A closed ``exec_tf`` bar ``j`` for the setups ``cands`` (those whose bar loop is at ``j``): missed
        touches (L4), then each candidate's life or break-even (L5)."""
        ex = self._exec()
        frame = self.live.frames[self.exec_tf]
        bar_open = _ts(frame["open_time"].iloc[j])
        for cand in cands:
            if cand.drop_final or cand.hour_open > bar_open:
                continue
            if bar_open >= cand.hour_open + HOUR:
                continue
            if self._decision_bar(cand) == j:
                continue  # L4: no missed touch from the bar in which the hour was decided
            v = cand.visit
            touched = ex.low[j] <= v.line + v.z if cand.sgn > 0 else ex.high[j] >= v.line - v.z
            if touched:
                self._consider_visit(cand, (j, v.from_open, v.line), bar_open)
        for cand in cands:
            if not cand.is_live or j < cand.plan.j0:
                continue  # a candidate dropped for the other's visit keeps its life: it has no orders (L4)
            if cand.rejudge_j == j:
                # L5: the first fill's bar - its fills accepted on the quotes so far - is judged again on the
                # closed bar's true extremes, in the simulation's in-bar order (the withdrawal before the
                # fills); its exits waited for this judgement
                cand.rejudge_j = None
                if live.moved_away(cand.plan, j, float(ex.high[j]), float(ex.low[j])):
                    log.warning(
                        "setup %s: the bar %s of its first fill reached the withdrawal level between two "
                        "cycles - `no fill`, its fills and their exits not the setup's (an explained "
                        "difference, L11)",
                        cand.id,
                        j,
                    )
                    self._void_fills(cand, "withdrawn (rule 1) on the closed bar of the fill")
                    self._end(cand, "no fill", _ts(ex.close_time.iloc[j]))
                    continue
                self._maybe_finish(cand)  # an exit inside the bar: the setup ends now
                if not cand.is_live:
                    continue
            if cand.fills:
                self._be_check(cand, j, ex)
            else:
                self._life_step(cand, j, ex)

    def _decision_bar(self, cand: Cand) -> int | None:
        hour = self._hour_of(cand)
        return None if hour is None or hour.decided_at is None else self._row_at(hour.decided_at)

    def _life_step(self, cand: Cand, j: int, ex: ExecBars) -> None:
        """Rules 1 - 3 on the closed bar: the simulation's own step, before any fill."""
        plan = cand.plan
        if j - plan.per_h < 0:
            return
        after = live.life_at_close(plan, start_life(plan), j, bar_values(ex, j, plan.per_h, self.live.point))
        end = _ts(ex.close_time.iloc[j])
        if after.status == "withdrawn":
            self._end(cand, "no fill", end)
        elif after.status == "cancel" or cand.cancel_seen == j:
            self._end(
                cand, "cancel", end
            )  # a touch seen in the quotes cancels even if the bar's spread hides it

    def _be_check(self, cand: Cand, j: int, ex: ExecBars) -> None:
        plan = cand.plan
        if cand.be_on or not plan.be_entry:
            return
        if all(f.position in cand.closed for f in cand.fills.values()):
            return
        fills = cand.fill_list(upto=j)  # only fills on this bar or before it count (as in step_setup)
        if not fills:
            return
        on, stop = live.be_probe(
            plan, fills, j, float(ex.high[j]), float(ex.low[j]), float(ex.spread[j]) * self.live.point
        )
        if on:
            cand.be_on, cand.be_sl, cand.be_j = True, stop, j
            cand.be_sent = live.be_stop_sent(stop, cand.sgn, self._spec().tick_size)
            self._save(cand)
            log.info("setup %s: break-even on at bar %s, stop %s (sent %s)", cand.id, j, stop, cand.be_sent)

    def _end(self, cand: Cand, outcome: str, end_close: pd.Timestamp | None) -> None:
        """The setup ends; the hour's setup reserves by ``no fill``, ``cancel`` or its exit (L6)."""
        cand.status, cand.outcome, cand.end_close = "ended", outcome, end_close
        if end_close is not None and cand.chosen and outcome in RESERVING:
            self.res_by[cand.id] = end_close
        self._save(cand)
        if cand.chosen:
            self._store().set_visit_outcome(cand.id, outcome)
        log.info("setup %s ended: %s (reservation to %s)", cand.id, outcome, self.res_by.get(cand.id))

    def _drop(self, cand: Cand, reason: str, *, final: bool) -> None:
        """L4 - ``dropped``: for the other candidate's visit (``final`` False: until the hour's close a missed
        touch can still make it the hour's setup), or at once (P1 refused, a lost hour)."""
        cand.dropped, cand.drop_reason = True, reason
        if final:
            cand.status, cand.outcome, cand.drop_final = "ended", "dropped", True
            self.res_by.pop(cand.id, None)
        self._save(cand)

    # ---------------------------------------------------------------------------------------------- the hour

    def _reserved(self, open_ts: pd.Timestamp) -> bool:
        """5b / L6 - while the hour's setup has not ended every later hour is reserved; after its end, to the
        close of its end bar."""
        if any(
            c_.chosen and c_.is_live and not c_.dropped and c_.hour_open != open_ts
            for c_ in self.cands.values()
        ):
            return True
        end = self.res_end
        return end is not None and open_ts <= end

    def _process_closed_h1_row(self, i: int, ctx: Ctx) -> None:
        """Rule 4's arming from the closed H1 bar ``i``, exactly as the simulation does, and L4's visit
        records."""
        r = self._reader()
        store = self._store()
        if i < self.start_i or i >= len(r):
            return
        g = live.grid_at(self.grids, self.gstart, int(r.h1_open_ns[i]))
        if g is None:
            return
        vs = visits_at_bar(r, i, g, self.armed, self.params)
        if not vs:
            return
        hour = self.prev_hours.get(i)
        if hour is None or (hour.undecided and not hour.reserved):
            classified = [(v, "undecided") for v in vs]
        else:
            classified = live.classify_hour(vs, self.params, hour.reserved)
        ex_open = self.live.frames[self.exec_tf]["open_time"]
        records: list[dict[str, Any]] = []
        explained_by = self._explained_visits(hour, classified)
        for v, cls in classified:
            chosen = hour.chosen if hour is not None else None
            is_chosen = chosen is not None and chosen.side == v.side and chosen.visit.line == v.line
            if hour is not None and cls != "undecided":
                mine = hour.cands.get(v.side)
                mine = mine if mine is not None and mine.visit.line == v.line else None
                cut = hour.cut_at
                touch_open = _ts(ex_open.iloc[v.touch_j]) if 0 <= v.touch_j < len(ex_open) else hour.open
                if cut is not None and touch_open + self.period > cut and not is_chosen:
                    cls = "undecided"  # L4: a visit after an interruption or hands-off began in the hour
                elif (
                    cls == "setup"
                    and mine is not None
                    and not is_chosen
                    and (mine.drop_reason == "refused" or mine.outcome in STOPPED_ENDS)
                ):
                    cls = "undecided"
            agreed = cls == "undecided" or hour is None or (is_chosen if cls == "setup" else not is_chosen)
            why = explained_by.get(id(v)) if not agreed else None
            explained = why is not None
            if why is not None:
                log.warning(
                    "the visit record of %s %s at %s is %s, the runner did otherwise: %s (an explained "
                    "difference, L11)",
                    v.side,
                    v.line,
                    v.time,
                    cls,
                    why,
                )
            elif not agreed:
                log.error(
                    "FAULT: the visit record of %s %s at %s is %s, the runner did otherwise",
                    v.side,
                    v.line,
                    v.time,
                    cls,
                )
            records.append(
                {
                    "hour_open": v.time.to_pydatetime(),
                    "side": v.side,
                    "line": v.line,
                    "classification": cls,
                    "setup_id": chosen.id
                    if is_chosen and chosen is not None and (cls == "setup" or explained)
                    else None,
                    "outcome": chosen.outcome
                    if is_chosen and chosen is not None and not chosen.is_live
                    else None,
                    "agreed": agreed,
                    "note": why if why is not None else ("" if agreed else "disagrees with the runner"),
                }
            )
        store.add_visits(ctx.now.to_pydatetime(), records)

    def _explained_visits(
        self, hour: HourState | None, classified: list[tuple[Visit, str]]
    ) -> dict[int, str]:
        """L11 - THE explained differences of an hour's visit records (visit -> its note): the in-bar touch
        order (the runner traded the other candidate that touched in the same bar), and a touch before the
        hour's decision (L2 / L4: the simulation's setup visit touched in the decision bar, where no missed
        touch is looked for - its extremes may come from before the decision; the runner's own choice, if
        any, then differs too)."""
        out: dict[int, str] = {}
        in_bar = self._in_bar_touch_order(hour, classified)
        if in_bar is not None:
            for v in in_bar:
                out[id(v)] = "in-bar touch order"
        if hour is None or hour.decided_at is None:
            return out
        dj = self._row_at(hour.decided_at)
        chosen = hour.chosen

        def unseen(v: Visit) -> bool:  # the runner's candidate of that visit saw no visit of it at all
            mine = hour.cands.get(v.side)
            return mine is not None and mine.visit.line == v.line and mine.visited_at is None

        early = [
            v
            for v, cls in classified
            if cls == "setup"
            and v.touch_j == dj
            and unseen(v)
            and not (chosen is not None and chosen.side == v.side and chosen.visit.line == v.line)
        ]
        if early:
            for v in early:
                out.setdefault(id(v), "touch before the decision")
            for v, _cls in classified:
                if chosen is not None and chosen.side == v.side and chosen.visit.line == v.line:
                    out.setdefault(id(v), "touch before the decision")
        return out

    @staticmethod
    def _in_bar_touch_order(
        hour: HourState | None, classified: list[tuple[Visit, str]]
    ) -> tuple[Visit, Visit] | None:
        """L4 - the in-bar touch order: the hour's setup is one candidate, the simulation classes the other
        candidate's visit ``setup``, and the two visits' touch bars are the same ``exec_tf`` bar. Returns the
        two visits (the one the runner traded, the one the simulation takes), else None."""
        chosen = None if hour is None else hour.chosen
        if chosen is None:
            return None
        traded = next(
            ((v, cls) for v, cls in classified if v.side == chosen.side and v.line == chosen.visit.line),
            None,
        )
        sim = next(((v, cls) for v, cls in classified if cls == "setup"), None)
        if traded is None or sim is None or traded[0] is sim[0] or traded[1] == "setup":
            return None
        if traded[0].touch_j != sim[0].touch_j:
            return None
        return traded[0], sim[0]

    def _finish_hour(self, hour: HourState) -> None:
        """L4 - at the hour's close: a drop for the other's visit is final (it replaces a life outcome the
        candidate reached meanwhile); a live candidate with no visit ends ``no fill`` (one whose life already
        ended keeps its outcome)."""
        for cand in hour.cands.values():
            if cand.dropped and not cand.drop_final:  # its life outcome, if any, gives way now
                cand.status, cand.outcome, cand.drop_final = "ended", "dropped", True
                self._save(cand)
            elif not cand.chosen and cand.is_live and not cand.dropped:
                self._end(cand, "no fill", hour.open + HOUR)

    def _begin_hour(self, open_ts: pd.Timestamp, o: float, i: int, ctx: Ctx) -> None:
        """The hour's state at its H1 open. A reserved hour has no candidates; the decision itself waits for
        the first cycle in the hour's first 60 s at which placing is allowed (``_decide``). The hour of the
        start, of a hands-off, and an hour already closed when it was first seen are undecided."""
        hour = HourState(open_ts, i, o, self._reserved(open_ts))
        self.hour = hour
        if self.hands_off is not None:
            hour.undecided = "hands-off"
        elif self.decide_from is None or open_ts < self.decide_from:
            hour.undecided = "before the first decision of the run"
        elif i < len(self.live.frames["H1"]):
            hour.undecided = "the hour was closed when first seen"
        elif hour.reserved:
            hour.skipped.update({"BUY": "busy", "SELL": "busy"})
        if hour.undecided:
            hour.skipped.update({"BUY": "undecided", "SELL": "undecided"})

    def _placing_allowed(self, ctx: Ctx) -> bool:
        """L7 - placing is allowed: the data fresh, the gate passing, the kill switch off, the terminal
        connected, no stop, no close owed, no unwanted order still resting, nothing L8 turns hands-off."""
        return bool(
            ctx.can_place
            and not ctx.read_failed
            and self.hands_off is None
            # L7 / L8 causes 1, 2, 3, 6: a pending entry, a place or a market entry of unknown outcome, an
            # entry deal read but not judged yet - anything of ours that can still open a position unseen
            and not self._may_open_unseen()
            and self.interrupt_owed is None  # L7: an interruption owed is done before anything new
            and not self.close_wanted
            and not self.remove_since
            and not self.gone_since
            and not self.exit_since
        )

    def _decide(self, ctx: Ctx) -> None:
        """L2 / L4 - the hour's decision at the first cycle within 60 s from the hour's first quote (the H1
        open, or the reopening after the daily break or the weekend, minutes into the H1 bar) at which placing
        is allowed; none by then: the hour is undecided."""
        hour = self.hour
        if hour is None or hour.decided or hour.undecided or hour.reserved:
            return
        hour.first_quote_at = self._hour_first_quote(hour.open)  # fixed once the hour's first quote is read
        if (ctx.now - hour.first_quote_at).total_seconds() > DECIDE_SECONDS:
            hour.undecided = "placing was not allowed through the 60 s from its first quote"
            hour.skipped.update({"BUY": "undecided", "SELL": "undecided"})
            log.warning(
                "hour %s is undecided: placing was not allowed through the 60 s from its first quote (%s)",
                hour.open,
                hour.first_quote_at,
            )
            return
        if not self._placing_allowed(ctx):
            return
        hour.decided, hour.decided_at = True, ctx.now
        self._ensure_grids(hour.open)  # the grid in force at the hour (ZONE_RULES 3)
        g = live.grid_at(self.grids, self.gstart, hour.open.value)
        if g is None or hour.i < self.start_i:
            return
        r = self._reader_upto(hour.i)
        try:
            vis = live.candidate_visits(r, g, self.armed, hour.o, hour.open.value, self.params)
        except (ZoneError, RuntimeError) as exc:
            hour.undecided = f"no candidates: {exc}"
            log.warning("hour %s has no candidates: %s", hour.open, exc)
            return
        to_create: list[tuple[str, Visit]] = []
        for side, v in vis.items():
            reason = live.skip_reason(v, self.params)
            if reason is not None:
                hour.skipped[side] = reason
                continue
            to_create.append((side, v))
        for side, cand in self._create_cands(to_create, ctx):
            hour.cands[side] = cand

    def _create_cands(self, wanted: list[tuple[str, Visit]], ctx: Ctx) -> list[tuple[str, Cand]]:
        """The hour's candidates: all their rows in ONE transaction."""
        if not wanted:
            return []
        store = self._store()
        plans = []
        for side, v in wanted:
            plan = plan_setup(v, self.params)
            plans.append((side, v, plan, live.sent_prices(plan, self._spec().tick_size)))
        fields = [
            {
                "market": self.cfg.market,
                "zone_set": self.cfg.set_name,
                "set_version": self.cfg.set_version,
                "hour_open": v.time.to_pydatetime(),
                "side": v.side,
                "line": v.line,
                "step": v.step,
                "p1": plan.p1,
                "p2": plan.p2,
                "sl": plan.sl,
                "tp": plan.tp,
                "p1_sent": sent.p1,
                "p2_sent": sent.p2,
                "sl_sent": sent.sl,
                "tp_sent": sent.tp,
                "state": "live",
                "chosen": False,
                "fills_json": json.dumps({"h1_open": v.h1_open, "anchor": v.anchor}),
            }
            for _side, v, plan, sent in plans
        ]
        ids = store.add_setups(ctx.now.to_pydatetime(), fields)
        out: list[tuple[str, Cand]] = []
        for cid, (side, v, plan, sent) in zip(ids, plans, strict=True):
            cand = Cand(cid, v.time, v, plan, sent, next_j=plan.j0)  # its bar loop starts at j0 (L5)
            self.cands[cid] = cand
            self._save(cand)
            log.info(
                "hour %s: candidate %s at %s (setup %s), P1 %s P2 %s SL %s TP %s",
                v.time,
                v.side,
                v.line,
                cid,
                sent.p1,
                sent.p2,
                sent.sl,
                sent.tp,
            )
            out.append((side, cand))
        return out

    # ------------------------------------------------------------------------------------------- the first
    # visit

    def _consider_visit(self, cand: Cand, key: tuple[int, float, float], when: pd.Timestamp) -> None:
        """L4 - a quote within Z, a deal, or (from a closed bar) a missed touch: the earliest live visit of
        the hour makes the hour's setup; a missed touch earlier than the chosen one takes the hour from it."""
        hour = self._hour_of(cand)
        if hour is None or not self._visit_counts(cand, hour):
            return
        touched = cand.touch_key is None or key < cand.touch_key
        if touched:
            cand.touch_key = key
        if cand.visited_at is None:
            cand.visited_at = when
        if touched:
            self._save(cand)
        if hour.chosen is cand:
            return
        if hour.chosen is None:
            self._choose(cand, key, hour)
            return
        if self._may_take_hour(cand, key, hour):
            old = hour.chosen
            log.warning(
                "missed touch: setup %s was visited before setup %s - it takes the hour (an explained "
                "difference, L11)",
                cand.id,
                old.id,
            )
            self._lose_hour(old, "missed touch: the other candidate is first in the candidates' order")
            old.chosen = False
            self._drop(old, "missed touch", final=True)
            hour.chosen = None
            if (
                cand.dropped
            ):  # the eclipsed candidate takes the hour: its life ran on, its orders may come back
                cand.dropped, cand.drop_reason = False, None
            self._choose(cand, key, hour)

    @staticmethod
    def _visit_counts(cand: Cand, hour: HourState) -> bool:
        """L4 - can a visit of the candidate count for its hour at all: not one dropped for a refused P1 (or a
        lost hour), never one ended ``interrupted`` / ``hands-off`` / ``restart`` before its visit."""
        if cand.hour_open != hour.open:
            return False
        if cand.drop_final:
            return False
        return cand.is_live or cand.dropped or cand.outcome in ("no fill", "cancel")

    def _may_take_hour(self, cand: Cand, key: tuple[int, float, float], hour: HourState) -> bool:
        """L4 - would a visit of the candidate with the touch ``key`` (bar, nearer ``o``, line) make it the
        hour's setup: the hour has none yet, or the visit comes first in the candidates' order. THE test of
        the hour's choice: ``_consider_visit`` acts on it, ``_holds`` / ``_absorb`` hold the hour's order on
        it."""
        if not self._visit_counts(cand, hour) or hour.chosen is cand:
            return False
        return hour.chosen is None or (hour.chosen_key is not None and key < hour.chosen_key)

    @staticmethod
    def _entry_is_visit(cand: Cand, name: str, when: pd.Timestamp) -> bool:
        """L4 - an entry deal of the candidate is a visit of it: the first fill of its name, of the hour's
        setup or inside the candidate's hour."""
        return name not in cand.fills and (cand.chosen or when < cand.hour_open + HOUR)

    def _hour_of(self, cand: Cand) -> HourState | None:
        for hour in (self.hour, *self.prev_hours.values()):
            if hour is not None and hour.open == cand.hour_open and cand in hour.cands.values():
                return hour
        return None

    def _choose(self, cand: Cand, key: tuple[int, float, float], hour: HourState) -> None:
        hour.chosen, hour.chosen_key = cand, key
        cand.chosen = True
        for other in hour.cands.values():
            if other is not cand and not other.dropped and other.outcome not in STOPPED_ENDS:
                if other.fills:
                    log.warning(
                        "both candidates filled: setup %s lost the hour, its positions closed (an explained "
                        "difference, L11)",
                        other.id,
                    )
                    self._lose_hour(
                        other, "both filled: the other candidate is first in the candidates' order"
                    )
                    self._drop(other, "both filled", final=True)
                else:
                    # L4: dropped for the other's visit - final only at the hour's close: a life outcome
                    # it already has (`no fill`, `cancel`) is kept, so a missed touch can still make it the
                    # hour's setup with that outcome (and its reservation)
                    self._drop(other, "other", final=False)
        if not cand.is_live and cand.end_close is not None and cand.outcome in RESERVING:
            self.res_by[cand.id] = cand.end_close
        self._save(cand)
        log.info(
            "hour %s: setup %s (%s %s) is the hour's setup", hour.open, cand.id, cand.side, cand.visit.line
        )

    def _void_fills(self, cand: Cand, why: str) -> None:
        """L5 "any other fill" - THE way fills stop being the setup's: each becomes a fault, its open position
        is closed at market (its close is not the setup's exit), and the fill and its exit records are dropped
        from the setup."""
        for name, f in list(cand.fills.items()):
            cand.faults[f.position] = f"{name}: {why}"
            if f.position not in cand.closed:
                self._owe_close(f.position, why)
            del cand.fills[name]
            # its exits are not the setup's either: their records go with it
            for rec in (cand.remaining, cand.closed, cand.outs, cand.out_last, cand.close_reason):
                rec.pop(f.position, None)
            cand.be_in_force.discard(f.position)
        if not cand.fills:
            cand.exit_how, cand.rejudge_j, cand.exit_pending = None, None, False

    def _lose_hour(self, loser: Cand, why: str) -> None:
        """L4 - the fills of the candidate that lost the hour are not its fills any more: closed at market."""
        self._void_fills(loser, why)
        self.res_by.pop(loser.id, None)
        self._save(loser)

    def _realtime(self, ctx: Ctx) -> None:
        """The parts that cannot wait for a bar's close: the first visit by the quote, the BUY P2 removed
        ahead of the break-even."""
        hour = self.hour
        tick = ctx.tick
        if (
            hour is not None
            and hour.decided
            and tick is not None
            and ctx.quote_fresh
            and not ctx.stopping
            and hour.open <= ctx.now < hour.open + HOUR
        ):
            hits = []
            for cand in hour.cands.values():
                if cand.dropped or self._waits(cand, ctx):
                    continue  # L5: a setup waiting for an entry deal judges no visit meanwhile
                v = cand.visit
                near = tick.bid <= v.line + v.z if cand.sgn > 0 else tick.bid >= v.line - v.z
                if near and ctx.qrow is not None:
                    hits.append(((ctx.qrow, v.from_open, v.line), cand))
            for key, cand in sorted(hits, key=lambda h: h[0]):  # the candidates' order (L4)
                self._consider_visit(cand, key, ctx.now)
        self._latch_blocked_touch(ctx)
        if ctx.fx is not None:
            for cand in self.cands.values():
                if (
                    cand.is_live
                    and not cand.dropped
                    and cand.sgn > 0
                    and "P1" in cand.fills
                    and "P2" not in cand.fills
                    and not cand.be_on
                    and not cand.p2_gone
                    and cand.plan.be_entry
                    and not self._waits(cand, ctx)  # L5: its break-even waits with its bar loop
                ):
                    on, _stop = live.be_probe(
                        cand.plan, cand.fill_list(), ctx.fx.n, ctx.fx.hi, ctx.fx.lo, 0.0
                    )
                    if on:
                        cand.p2_gone = True
                        self._save(cand)
                        log.info("setup %s: the BUY break-even is certain, P2 removed ahead", cand.id)

    def _latch_blocked_touch(self, ctx: Ctx) -> None:
        """L5 rule 3 - during bar ``n`` a blocked P1.s fill test is met by the quotes (BUY: ask <= P1; SELL:
        bid >= P1): the setup is cancelled at once (its orders are no longer wanted); the bar's close decides
        ``cancel`` or ``no fill`` (``_life_step``)."""
        tick, ex, n = ctx.tick, ctx.ex, ctx.qrow
        if tick is None or ex is None or n is None or n < 1:
            return  # L2: a quote whose bar is not known is judged by nothing
        for cand in self.cands.values():
            plan = cand.plan
            if (
                not cand.is_live  # a candidate dropped for the other's visit keeps its life (L4)
                or cand.fills
                or cand.cancel_seen is not None
                or self._waits(cand, ctx)
                or n < plan.j0
                or n - plan.per_h < 0
            ):
                continue
            if not live.entry_blocked(plan, plan.p1, float(ex.open[n - plan.per_h])):
                continue
            met = tick.ask <= plan.p1 if cand.sgn > 0 else tick.bid >= plan.p1
            if met:
                cand.cancel_seen = n
                log.warning(
                    "setup %s: the blocked P1 %s was met by the quotes: cancelled at once", cand.id, plan.p1
                )

    # ========================================================================================== desired
    # orders

    def _order_of(self, ctx: Ctx, cand: Cand, name: str) -> BrokerOrder | None:
        for o in ctx.orders:
            key = live.parse_comment(o.comment)
            if key is not None and key[0] == cand.id and key[1] == name:
                return o
        return None

    def _wants(self, cand: Cand, name: str, ctx: Ctx) -> bool:
        """Should the order ``name`` of the candidate rest now (L3 - L5, L7)?"""
        if ctx.remove_all or cand.dropped or not cand.is_live or cand.exit_pending or name in cand.fills:
            return False
        if cand.cancel_seen is not None:
            return False  # L5 rule 3: blocked P1 met, cancelled at once
        if cand.fills:  # the first fill is in: rules 1 - 3 no longer apply; only P2 rests, until the BE
            return (
                name == "P2"
                and "P1" in cand.fills
                and not cand.be_on
                and not cand.p2_gone
                and not cand.p2_off
            )
        if name == "P2":
            if cand.p1_refused or cand.p2_off:
                return False
            row = ctx.open_places.get((cand.id, "P1"))
            if row is None or row.state != "sent" or not self._wants(cand, "P1", ctx):
                return False
        return self._before_fill_ok(cand, name, ctx)

    def _before_fill_ok(self, cand: Cand, name: str, ctx: Ctx) -> bool:
        ex = ctx.ex
        if ex is None:
            return False
        plan, n, per_h = cand.plan, ctx.n, cand.plan.per_h
        if not cand.chosen and ctx.now >= cand.hour_open + HOUR - pd.Timedelta(
            seconds=self.cfg.preclose_seconds
        ):
            return False  # L4: the end of the hour, a candidate not visited
        if n - per_h < 0 or n < 1:
            return False
        oh = float(ex.open[n - per_h])
        if live.expired_at(plan, n):
            return False
        if ctx.fx is not None and ctx.fx.n == n and live.moved_away(plan, n, ctx.fx.hi, ctx.fx.lo):
            return False
        if live.closed_hour_cancel(plan, n, float(ex.close[n - 1]), oh):
            return False
        if live.entry_blocked(plan, plan.p1, oh):  # L5 rule 3: P1's block removes both; P2 has none
            return False
        if ctx.ahead and ctx.tick is not None:  # L5: the pre-close window judges the next bar ahead
            m = n + 1
            ohm = float(ex.open[m - per_h])
            if live.expired_at(plan, m):
                return False
            if live.closed_hour_cancel(plan, m, ctx.tick.bid, ohm):
                return False
            if live.entry_blocked(plan, plan.p1, ohm):
                return False
        return True

    def _waits(self, cand: Cand, ctx: Ctx) -> bool:
        """L5 - THE gate of every judgement of a setup outside its bar loop (its interruption, a visit by the
        quotes, a latched touch, the BUY P2 removed ahead): the setup waits while ``_holds`` (the registry of
        pending entries) holds it. Removals for safety do not pass through it, and hands-off does not wait (it
        has ended every setup already, L8)."""
        return self.hands_off is None and cand.id in ctx.holds

    def _manage(self, ctx: Ctx) -> None:
        """Owed closes and the break-even first, then removals, then placements - the desired state against
        the broker's."""
        if ctx.remove_all or self._interruption_due(ctx):  # L7: a setup without a fill ends interrupted
            reason = self._removal_reason(ctx) if ctx.remove_all else (self.interrupt_owed or "rule")
            self._interrupt_unfilled(ctx.now, reason)
            if not any(self._left_to_interrupt(cd) for cd in self.cands.values()):
                self.interrupt_owed = (
                    None  # done: none is left (a setup waiting for its entry deal defers it)
                )
        self._enforce_be(ctx)
        if self.hands_off is not None:
            return
        self._run_closes(ctx)
        removals: list[BrokerOrder] = []
        reason = self._removal_reason(ctx)
        for o in ctx.orders:
            key = live.parse_comment(o.comment)
            if key is None:
                removals.append(o)
                self._owe_removal(o.ticket, "rule")
                continue
            own = self.cands.get(key[0])
            current = key[2] == self._store().count_places(key[0], key[1]) - 1
            if own is None or not current:
                removals.append(o)  # not the current placement of a setup under way
                self._owe_removal(o.ticket, "rule")
            elif ctx.remove_all:
                removals.append(o)  # L7: removals for safety never wait
                self._owe_removal(o.ticket, reason)
            elif self._waits(own, ctx):
                pass  # L5: its orders' judgements wait for the entry deal (the order rests as it is)
            elif not self._wants(own, key[1], ctx):
                removals.append(o)
                # the orders of a setup ended `interrupted` are owed for the reason of its interruption
                self._owe_removal(o.ticket, own.interrupted_for or "rule")
            elif ctx.can_place:
                self._maybe_extend(o, own, ctx)
        self._remove_in_order([o for o in removals if self._removal_due(o.ticket, ctx)], ctx)
        if not removals:  # L7: nothing new while an unwanted order rests
            for cand in list(self.cands.values()):
                for name in NAMES:
                    # L7: placing permission is judged before EVERY request - a place of unknown outcome, a
                    # market entry or a pending entry that arose a request ago stops the rest of the loop
                    if not self._placing_allowed(ctx):
                        break
                    if self._order_of(ctx, cand, name) is not None:
                        continue
                    if self._wants(cand, name, ctx) and self._may_place(cand, name):
                        self._place(cand, name, ctx)
        for cid in [cid for cid, cd in self.cands.items() if self._final(cd, ctx)]:
            del self.cands[cid]

    @staticmethod
    def _removal_reason(ctx: Ctx) -> str:
        """Why every order is removed this cycle (``remove_all``): a stop, the kill switch, a failed gate, or
        the stale data - the first that applies; ``rule`` when none does."""
        if ctx.stopping:
            return "stop"
        if ctx.kill:
            return "kill"
        if not ctx.gate_ok:
            return "gate"
        return "stale" if ctx.stale_long else "rule"

    def _owe_removal(self, ticket: int, reason: str) -> None:
        """An order judged not wanted, with its reason (``_safety`` retries it every cycle); a reason other
        than the stale data replaces a stale one (it does not wait for the market)."""
        if reason != "stale" or ticket not in self.unwanted:
            self.unwanted[ticket] = reason

    def _owe_safety(self, ctx: Ctx, reason: str) -> None:
        """L7 / L8 - THE latch of a safety cause (a stop, the kill switch, a failed gate, the stale data),
        wherever it is read: owed the moment it falls due, with its reason, whatever the later reads give -
        every order of the magic read is owed for removal (retried every cycle until confirmed), and the
        interruption is owed (done once the steps run; placing waits for it)."""
        for o in ctx.orders:
            self._owe_removal(o.ticket, reason)
        if reason != "stale" or self.interrupt_owed is None:
            self.interrupt_owed = reason

    def _interruption_due(self, ctx: Ctx) -> bool:
        """L7 - an interruption owed from an earlier cycle (``interrupt_owed``) is done now: one owed for the
        stale data alone waits while the market is closed, every other reason does not wait for anything."""
        owed = self.interrupt_owed
        return owed is not None and (owed != "stale" or not ctx.market_closed)

    def _removal_due(self, ticket: int, ctx: Ctx) -> bool:
        """L7 / L2 - THE test of whether an owed removal is sent now: one owed for the stale data alone waits
        while the market is closed (it is sent at the first cycle after the reopening); every other reason -
        hands-off, a stop, the kill switch, a failed gate, the rules - does not wait for the market."""
        return self.unwanted.get(ticket) != "stale" or not ctx.market_closed

    def _without_fill(self, cand: Cand) -> bool:
        """L1 "Without a fill" - THE one definition (L7, L10): none of the setup's entries read (a fill
        judged, or an entry deal read and not judged yet) or pending (L5). A place of unknown outcome does not
        hold it: filled after the setup ended, it is closed at market (L5 "any other fill")."""
        return (
            not cand.fills
            and cand.id not in self.buffered
            and not any(e.setup == cand.id for e in self.entries.values())
        )

    def _left_to_interrupt(self, cand: Cand) -> bool:
        """L7 / L10 - THE scope of an interruption: every unfinished row without a fill (``_without_fill``) -
        a candidate dropped for the other's visit and not yet final included; one waiting for its entry deal
        is not without a fill."""
        return cand.unfinished and self._without_fill(cand)

    def _interrupt_unfilled(self, now: pd.Timestamp, reason: str) -> None:
        """Every setup under way without a fill (``_without_fill``) ends ``interrupted`` (no reservation, L7 /
        L10), for ``reason`` (a removal reason: "stop", "kill", "gate", "stale"). At a ``--now`` exit
        (``exiting``) every unfinished row without a fill, a candidate dropped for the other's visit and not
        yet final included; the rest end ``restart`` at the next start (L8)."""
        if self.hands_off is not None:
            return  # every setup has ended `hands-off` already
        for cand in list(self.cands.values()):
            if not self._left_to_interrupt(cand):
                continue
            log.warning("setup %s ends interrupted (%s)", cand.id, REMOVAL_WHY.get(reason, reason))
            cand.interrupted_for = reason
            cand.dropped = False  # its drop was not final: it ends `interrupted`
            self._end(cand, "interrupted", None)
            if self.hour is not None and cand.hour_open == self.hour.open and self.hour.cut_at is None:
                self.hour.cut_at = now

    def _interrupt_before_exit(self, now: pd.Timestamp) -> None:
        """L10 - every ``--now`` exit (the removals confirmed, or the 60 s) first ends ``interrupted`` every
        unfinished row without a fill; the rest end ``restart`` at the next start (L8). It never holds the
        exit back: a failure is logged."""
        try:
            self._interrupt_unfilled(now, "stop")
        except Exception as exc:  # the exit must not fail on bookkeeping; the rows end `restart` at the start
            log.error("stop --now: the setups without a fill could not be ended `interrupted`: %s", exc)

    def _may_open_unseen(self, setup_id: int | None = None) -> bool:
        """L10 / L5 / L8 - THE test of what of ours can still open a position the runner has not judged: an
        entry pending (a position or a filled order seen without its entry deal), a place of unknown outcome,
        a market entry not done (accepted or of unknown outcome, its entry deal not read), an order of ours
        gone without its explanation, an entry deal read but not judged yet (buffered). For one setup, or for
        any. The ordinary stop exits only when none is left (L10); placing waits meanwhile (L7)."""

        def mine(sid: int) -> bool:
            return setup_id is None or sid == setup_id

        return (
            any(mine(e.setup) for e in self.entries.values())
            or any(mine(k[0]) for k in self.unknown_since)
            or any(mine(k[0]) for k in self.market_since)
            # an order of ours gone without its explanation (L8 causes 1 - 2): it may have filled unseen
            or any(t not in self.seen_orders or mine(self.seen_orders[t][0]) for t in self.gone_since)
            or any(mine(sid) for sid in self.buffered)
        )

    def _may_place(self, cand: Cand, name: str) -> bool:
        """L3 - a new placement of a name only once every earlier placement of it is known gone without a
        fill (its removal confirmed, its history state cancelled or expired, or its request refused)."""
        for r in self._store().requests(setup_id=cand.id, kinds=("place",)):
            if r.name != name:
                continue
            if r.state == "refused" or r.order_state in ("cancelled", "expired", "refused"):
                continue
            if r.position_ticket is not None and int(r.position_ticket) in cand.faults:
                continue  # a fill that was not the setup's: closed, gone
            return False
        return True

    def _final(self, cand: Cand, ctx: Ctx) -> bool:
        """A candidate leaves memory once it is over and nothing of it rests at the broker."""
        if cand.is_live and not cand.dropped:
            return False
        if self.hour is not None and cand.hour_open >= self.hour.open:
            return False  # the hour under way may still need it (a missed touch, its visit record)
        if any(f.position not in cand.closed for f in cand.fills.values()):
            return False
        if any(p in {q.ticket for q in ctx.positions} for p in cand.faults):
            return False
        if self._may_open_unseen(cand.id):
            return False  # L5 / L8: an entry of it is still to be read or judged
        for o in ctx.orders:
            key = live.parse_comment(o.comment)
            if key is not None and key[0] == cand.id:
                return False
        return not any(sid == cand.id for sid, _name in ctx.open_places)

    # ---------------------------------------------------------------------------------------------- requests

    def _send(
        self,
        kind: str,
        setup_id: int,
        request: dict[str, Any],
        *,
        pkey: tuple[str, int] | None = None,
        name: str = "",
        comment: str | None = None,
        market: bool = False,
        order_ticket: int | None = None,
        position_ticket: int | None = None,
    ) -> tuple[int, SendResult]:
        """L8 - the intent is written (committed) before ``order_send``; then ``sent``, ``refused`` or
        ``unknown``. ``pkey`` follows a remove / modify / close until the broker shows it done."""
        if self.account_switched:
            raise AccountSwitched(f"{kind} refused: the account is not the pinned one")
        store = self._store()
        reuse = self.pending.get(pkey) if pkey is not None and pkey[0] != "sltp" else None
        now = self.now().to_pydatetime()
        if reuse is not None:
            rid = reuse[0]
            store.update_request(rid, payload_json=json.dumps(request))
        else:
            rid = store.add_request(
                now,
                setup_id=setup_id,
                kind=kind,
                name=name,
                comment=comment,
                payload_json=json.dumps(request),
                market=market,
                order_ticket=order_ticket,
                position_ticket=position_ticket,
            )
        if pkey is not None:
            self.pending[pkey] = (rid, request)
        try:
            res = self.exe.send(request)
        except SafetyViolation:
            raise
        except Exception as exc:  # the outcome is unknown
            log.error("order_send raised (%s): outcome unknown", exc)
            res = SendResult(None, RetcodeClass.UNKNOWN, "NO_RESULT")
        if _unknown(res):
            store.update_request(
                rid, state="unknown", retcode=res.retcode, detail=f"outcome unknown: {res.description}"
            )
        elif res.ok:
            fields: dict[str, Any] = {"retcode": res.retcode, "sent_at": now, "state": "sent"}
            if kind == "place":
                fields.update(order_ticket=res.order or None, deal_ticket=res.deal or None)
            elif kind != "close":  # a close is done only when the position is gone
                fields.update(closed_at=now)
                if pkey is not None:
                    self.pending.pop(pkey, None)
            store.update_request(rid, **fields)
        else:
            fields = {"state": "refused", "retcode": res.retcode, "detail": res.description}
            if kind == "place":
                fields.update(order_state="refused", closed_at=now)
            store.update_request(rid, **fields)
        return rid, res

    def _place(self, cand: Cand, name: str, ctx: Ctx) -> None:
        """L3 - a limit order (or, already marketable, a market order) with SL and TP, the key, the expiry."""
        spec, store = self._spec(), self._store()
        tick = ctx.tick
        if tick is None:
            return
        ok, why = self._gate(ctx=ctx)  # fresh, before every request that can open exposure
        if not ok:
            log.warning("no order: the gate failed (%s)", why)
            if not ctx.read_failed and not self.account_switched:
                # L7: the gate failing, wherever it is read - the same removals and interruption as the
                # cycle's own gate, and nothing more is placed in this cycle
                ctx.gate_ok, ctx.gate_reason, ctx.can_place, ctx.remove_all = False, why, False, True
                self.last_gate = (False, why)
                self._owe_safety(ctx, "gate")
            return
        n = store.count_places(cand.id, name)
        if n > MAX_N:
            self._enter_hands_off(f"setup {cand.id} {name}: a placement number over {MAX_N}", ctx.now)
            return
        buy = cand.sgn > 0
        price = cand.sent.p1 if name == "P1" else cand.sent.p2
        comment = live.make_comment(cand.id, name, n)
        side = Side.BUY if buy else Side.SELL
        marketable = tick.ask <= price if buy else tick.bid >= price
        if marketable and name == "P2" and "P1" not in cand.fills:
            return  # L3 / L4: a marketable P2 only after its P1 has filled (confirmed by its entry deal)
        try:
            if marketable:
                request = self.builder.market_entry(
                    spec,
                    side,
                    self.cfg.lot,
                    tick.ask if buy else tick.bid,
                    cand.sent.sl,
                    cand.sent.tp,
                    magic=self.magic,
                    comment=comment,
                )
            else:
                expiry = live.broker_expiry(ctx.now)
                filling = self._pending_filling(spec, side, price, cand, comment, expiry)
                request = self.builder.limit_entry(
                    spec,
                    side,
                    self.cfg.lot,
                    price,
                    cand.sent.sl,
                    cand.sent.tp,
                    magic=self.magic,
                    comment=comment,
                    filling=filling,
                    expiration_server=self.gw.server_clock.utc_to_server_epoch(expiry.to_pydatetime()),
                )
        except SafetyViolation as exc:
            log.error("the request for %s of setup %s was refused by the builder: %s", name, cand.id, exc)
            return
        key = (cand.id, name, n)
        self.ours[key] = 0  # ours from the send on, whatever its outcome (L3, Words)
        self.place_payload[key] = request
        self.place_seq = self._next_seq()  # L10: an orders read before this one cannot confirm it removed
        self.placed_seq[comment] = self.place_seq
        rid, res = self._send("place", cand.id, request, name=name, comment=comment, market=marketable)
        self.ours[key] = rid
        row = store.request_by_comment(comment)
        if row is not None and row.order_state == "open":
            ctx.open_places[(cand.id, name)] = row
        if marketable and (res.ok or _unknown(res)):
            self.market_since[key] = ctx.now
        if res.ok and not marketable and res.order:
            self._known_order(int(res.order), key)  # tracked from the moment the broker accepted it
        if _unknown(res):
            self.unknown_since.setdefault(key, ctx.now)  # a blocker from this moment (L7)
            log.error(
                "setup %s %s: no reply to the place request %s - searched by its key", cand.id, name, comment
            )
            return
        if res.ok:
            return
        self._on_refused(cand, name, res, ctx)

    def _pending_filling(
        self, spec: SymbolSpec, side: Side, price: float, cand: Cand, comment: str, expiry: pd.Timestamp
    ) -> int:
        if self.pending_filling is not None:
            return self.pending_filling
        for filling in RequestBuilder.pending_fillings(spec):
            request = self.builder.limit_entry(
                spec,
                side,
                self.cfg.lot,
                price,
                cand.sent.sl,
                cand.sent.tp,
                magic=self.magic,
                comment=comment,
                filling=filling,
                expiration_server=self.gw.server_clock.utc_to_server_epoch(expiry.to_pydatetime()),
            )
            if self.exe.check(request).ok:
                self.pending_filling = filling
                return filling
        return RequestBuilder.pending_fillings(spec)[0]

    def _on_refused(self, cand: Cand, name: str, res: SendResult, ctx: Ctx) -> None:
        cand.refusals[name] = cand.refusals.get(name, 0) + 1
        log.warning("setup %s %s refused: %s (%s)", cand.id, name, res.description, cand.refusals[name])
        if name == "P1":
            cand.p1_refused = True
            if cand.chosen:  # L3: a P1 refused after its candidate became the hour's setup
                self._enter_hands_off(
                    f"setup {cand.id}: P1 refused after it became the hour's setup", ctx.now
                )
                return
            log.warning("setup %s: P1 refused - the candidate is dropped (P2 never rests alone)", cand.id)
            self._drop(cand, "refused", final=True)
            return
        if cand.refusals[name] >= MAX_TRIES:
            cand.p2_off = True
            log.warning("setup %s: P2 refused %s times - the setup goes on with P1 only", cand.id, MAX_TRIES)
        self._save(cand)

    def _remove_in_order(self, removals: list[BrokerOrder], ctx: Ctx, *, timers: bool = True) -> None:
        """L3 - removing a setup's orders: P2 first; a P1 once its setup's P2 is gone (the broker confirmed
        its removal, or it does not rest). A refused P2 removal holds P1 back; retried each cycle."""
        gone: set[int] = ctx.removal_done
        p2_resting: dict[int, list[int]] = {}
        for o in ctx.orders:
            k = live.parse_comment(o.comment)
            if k is not None and k[1] == "P2":
                p2_resting.setdefault(k[0], []).append(o.ticket)

        def rank(o: BrokerOrder) -> int:
            k = live.parse_comment(o.comment)
            return 0 if k is not None and k[1] == "P2" else 1

        for o in sorted(removals, key=rank):
            k = live.parse_comment(o.comment)
            if o.ticket in ctx.removal_tried:
                continue  # sent already this cycle (`_safety`): retried next cycle if not confirmed
            if timers:
                self.remove_since.setdefault(o.ticket, ctx.now)
            if k is not None and k[1] == "P1":
                held = [t for t in p2_resting.get(k[0], []) if t not in gone]
                if held:
                    log.warning(
                        "order %s (P1 of setup %s) stays until its P2 %s is gone", o.ticket, k[0], held
                    )
                    continue
            ctx.removal_tried.add(o.ticket)
            if self._remove_order(o.ticket, o.comment, 0 if k is None else k[0]):
                gone.add(o.ticket)

    def _remove_order(self, ticket: int, comment: str, setup_id: int) -> bool:
        """Removing is always allowed; a refused removal is retried every cycle. True when the broker
        confirmed the removal."""
        self.removes_sent.add(ticket)
        _rid, res = self._send(
            "remove",
            setup_id,
            RequestBuilder.remove_order(ticket),
            pkey=("remove", ticket),
            order_ticket=ticket,
            name=(live.parse_comment(comment) or (0, "", 0))[1],
        )
        if res.ok:
            k = live.parse_comment(comment)
            if k is not None:
                self._mark_place(k, "cancelled", self.now())
            return True
        if not _unknown(res):
            log.warning("removing order %s was refused (%s): tried again next cycle", ticket, res.description)
        return False

    def _maybe_extend(self, order: BrokerOrder, cand: Cand, ctx: Ctx) -> None:
        """L3 - only the orders of an hour's setup are extended: from 10 minutes before the expiry, by an
        hour."""
        if order.expiration_utc is None or not cand.chosen:
            return
        expiry = _ts(order.expiration_utc)
        if not live.needs_extension(expiry, ctx.now):
            return
        new_epoch = self.gw.server_clock.utc_to_server_epoch(live.extended_expiry(expiry).to_pydatetime())
        request = self.builder.modify_order(self._spec(), order, expiration_server=new_epoch)
        exp = self.order_expect.get(order.ticket)
        if exp is not None:
            exp["exp_pend"].add(int(new_epoch))  # under way: the old and the new expiry are both the runner's
        _rid, res = self._send(
            "modify",
            cand.id,
            request,
            pkey=("expiry", order.ticket),
            order_ticket=order.ticket,
            name=(live.parse_comment(order.comment) or (0, "", 0))[1],
        )
        if exp is not None:
            if res.ok:  # accepted: the latest expiry the broker took
                exp["exp"] = int(new_epoch)
                exp["exp_pend"].discard(int(new_epoch))
            elif not _unknown(res):
                exp["exp_pend"].discard(int(new_epoch))  # refused: changes nothing to compare

    # ----------------------------------------------------------------------------------- break-even and
    # closes

    def _enforce_be(self, ctx: Ctx) -> None:
        """L5 - every open position of a setup with the break-even on gets the BE stop; with the price already
        beyond it the position is closed at market (exit BE at the BE stop in the logic); a modify not in
        force after 3 tries -> hands-off."""
        tick, spec = ctx.tick, self._spec()
        if tick is None:
            return
        half = spec.tick_size / 2
        pos_by = {p.ticket: p for p in ctx.positions}
        for cand in list(self.cands.values()):
            if not cand.be_on or cand.be_sent is None or not cand.is_live:
                continue
            for f in list(cand.fills.values()):
                pos = pos_by.get(f.position)
                if pos is None or f.position in self.close_wanted:
                    continue
                new = cand.be_sent
                exp = self._pos_exp(pos)
                if abs(pos.sl - new) < half:
                    cand.be_in_force.add(
                        pos.ticket
                    )  # the BE stop is in force (L5: it names the exit's `how`)
                    exp["sl"] = new
                    exp["pend"].discard(new)
                    continue
                buy = cand.sgn > 0
                if (buy and not new > pos.sl) or (not buy and not new < pos.sl):
                    continue  # L7: a stop move never worsens
                # L5 / L8: the cap of 3 tries comes before any further modify or the BE close - an SL that
                # cannot be moved is out of our control, however the price stands
                tries = self.be_tries.get(pos.ticket, 0)
                if tries >= MAX_TRIES:
                    self._enter_hands_off(
                        f"the break-even SL of position {pos.ticket} is not in force after {MAX_TRIES} tries",
                        ctx.now,
                    )
                    return
                beyond = tick.bid <= new if buy else tick.ask >= new
                if beyond:
                    log.warning(
                        "setup %s: the price is beyond the BE stop: position %s closed at market",
                        cand.id,
                        pos.ticket,
                    )
                    cand.close_reason[pos.ticket] = "BE"
                    self._owe_close(pos.ticket, "break-even beyond")
                    self._save(cand)
                    continue
                self.be_tries[pos.ticket] = tries + 1
                exp["pend"].add(new)  # a modify under way: the old and the new stop are both the runner's
                request = self.builder.modify_stops(spec, pos, new, pos.tp or None)
                _rid, res = self._send(
                    "modify",
                    cand.id,
                    request,
                    pkey=("sltp", pos.ticket),
                    position_ticket=pos.ticket,
                    name=f.name,
                )
                if res.ok:  # accepted: the latest stop the broker took (L8 cause 7 compares with it)
                    exp["sl"] = new
                    exp["pend"].discard(new)
                    cand.be_in_force.add(pos.ticket)
                elif not _unknown(res):
                    exp["pend"].discard(new)  # refused: changes nothing to compare
                    log.warning(
                        "the BE modify of %s was refused (%s), try %s", pos.ticket, res.description, tries + 1
                    )

    def _owe_close(self, position: int, why: str) -> None:
        """L4 / L5 - THE way a close becomes owed: from this moment it is wanted (retried every cycle) and
        timed (L8 cause 6: not done within one bar -> hands-off), whatever a later read gives - a close that
        cannot be sent for want of a quote is timed all the same."""
        self.close_wanted[position] = why
        self.close_since.setdefault(position, self.now())

    def _run_closes(self, ctx: Ctx) -> None:
        """A close is retried every cycle until the position is gone (hands-off after one bar, L8)."""
        tick, spec = ctx.tick, self._spec()
        if tick is None:
            return
        pos_by = {p.ticket: p for p in ctx.positions}
        for ticket, why in list(self.close_wanted.items()):
            pos = pos_by.get(ticket)
            if pos is None:
                self.close_wanted.pop(ticket, None)
                continue
            self.closes_sent.add(ticket)
            price = tick.bid if pos.side is Side.BUY else tick.ask
            request = self.builder.close(spec, pos, price, comment="zone-close")
            key = live.parse_comment(pos.comment)
            _rid, res = self._send(
                "close", key[0] if key else 0, request, pkey=("close", ticket), position_ticket=ticket
            )
            if res.ok:
                log.info("position %s closed at market (%s)", ticket, why)
            elif not _unknown(res):
                log.warning(
                    "the close of %s was refused (%s): tried again next cycle", ticket, res.description
                )

    # ======================================================================================== after /
    # publishing

    def _stop_progress(self, ctx: Ctx, *, flat: bool = False) -> None:
        """L10 - a stop's progress. The acknowledgement rests on phase 1's successful account / orders read
        alone: once no unfilled order of the magic remains it is written, whatever the other reads give. The
        exit that needs only the orders (``--now``; under hands-off) follows at once; the ordinary exit also
        needs ``flat`` - no position open and no entry pending (``_after``, from the later reads)."""
        if not self.stopping:
            return
        if not self.stop_acked and self._removals_confirmed():
            if self.stop_id is not None:
                self._store().acknowledge_stop(
                    self.stop_id, ctx.now.to_pydatetime(), "unfilled orders removed, nothing new is placed"
                )
            self.stop_acked = True
            log.warning("stop acknowledged: no unfilled order of the zone magic remains")
        # every exit on the removals confirmed NOW (an earlier acknowledgement may predate an order that
        # appeared since)
        confirmed = self.stop_acked and self._removals_confirmed()
        if confirmed and (self.exit_now or self.hands_off is not None or flat):
            if self.exit_now:
                self._interrupt_before_exit(ctx.now)
            self.finished = True
            self._close_stop_rows()
            log.warning("the zone runner stops (%s)", "now" if self.exit_now else "no position to manage")

    def _after(self, ctx: Ctx) -> None:
        """The end of a cycle whose reads all succeeded: the stale condition settled; the stop's ordinary exit
        once no position is open and no entry is pending (L10)."""
        self._settle_stale(ctx)
        if ctx.stale_long:  # the debt acted on this cycle: released once this cycle's steps left nothing owed
            self._stale_debt(ctx)
        # L10: no position open and nothing of ours can still open one unseen
        # ... and no setup's outcome still waiting for its first fill's bar to be judged on its close (L5)
        waiting = any(cd.rejudge_j is not None for cd in self.cands.values())
        self._stop_progress(ctx, flat=not ctx.positions and not self._may_open_unseen() and not waiting)

    def _stop_deadline(self, now: pd.Timestamp) -> None:
        """L10 - with ``--now`` the runner exits 60 s after the request even when a removal is not confirmed:
        the orders still resting are named in the log (they keep their broker expiry)."""
        if not (self.stopping and self.exit_now) or self.finished:
            return
        if self.exit_now_at is None:
            self.exit_now_at = now
            return
        if (now - self.exit_now_at).total_seconds() < STOP_NOW_SECONDS:
            return
        confirmed = self._removals_confirmed()  # only an orders read after the request and the last placement
        unresolved = [] if confirmed else self._unresolved_orders()
        for what in unresolved:
            log.error("stop --now: %s was not confirmed removed; it keeps its broker expiry", what)
        if not confirmed and not unresolved:
            log.error("stop --now: no orders read after the request confirms the removals")
        self._interrupt_before_exit(now)  # L10: every --now exit, this one too
        self.finished = True
        if confirmed:
            self._close_stop_rows()
        else:
            self.leave_unacknowledged = True  # L10: the removals were never confirmed - no acknowledgement
        log.warning(
            "the zone runner stops (now: %s s passed; %s outstanding)",
            int(STOP_NOW_SECONDS),
            len(unresolved),
        )

    def status(self, ctx: Ctx | None = None) -> dict[str, Any]:
        hour = self.hour
        return {
            "login": self.login,
            "server": self.server,
            "mode": self.cfg.mode.value,
            "set": f"{self.cfg.set_name} v{self.cfg.set_version}",
            "hands_off": self.hands_off,
            "hands_off_since": None if self.hands_off_at is None else self.hands_off_at.isoformat(),
            "hour": None if hour is None else hour.open.isoformat(),
            "hour_reserved": None if hour is None else hour.reserved,
            "hour_undecided": None if hour is None else hour.undecided,
            "skipped": {} if hour is None else hour.skipped,
            "candidates": [
                {
                    "id": cd.id,
                    "side": cd.side,
                    "line": cd.visit.line,
                    "status": "dropped" if cd.dropped else cd.status,
                    "chosen": cd.chosen,
                    "fills": sorted(cd.fills),
                    "be": cd.be_sent if cd.be_on else None,
                    "outcome": cd.outcome,
                }
                for cd in self.cands.values()
            ],
            "orders": [] if ctx is None else [(o.ticket, o.comment, o.price_open) for o in ctx.orders],
            "positions": []
            if ctx is None
            else [(p.ticket, p.comment, p.price_open, p.sl, p.tp) for p in ctx.positions],
            "not_ours_orders": self.not_ours_orders,
            "not_ours_positions": self.not_ours_positions,
            "gate": {"ok": self.last_gate[0], "reason": self.last_gate[1]},
            "stopping": self.stopping,
            "account_switched": self.account_switched,
            "stale_since": None if self.stale_since is None else self.stale_since.isoformat(),
            "reservation_end": None if self.res_end is None else self.res_end.isoformat(),
        }

    def _publish(self, ctx: Ctx) -> None:
        try:
            text = json.dumps(self.status(ctx), default=str, sort_keys=True)
            now = ctx.now
            if (
                text == self._status_text
                and self._status_at is not None
                and (now - self._status_at).total_seconds() < 10
            ):
                return
            self._store().set_state("status", text, now.to_pydatetime())
            self._status_text, self._status_at = text, now
        except Exception as exc:  # the status is for the owner's eyes; it never stops a cycle
            log.warning("the status could not be written: %s", exc)
