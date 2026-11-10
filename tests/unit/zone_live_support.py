"""A small world for the zone runner's unit tests (eye/ZONE_LIVE.md L11.3): constructed bars of the kind
``tests/unit/test_zone_bot.py`` uses, a bar source that serves only the bars closed by the test clock, and the
real broker layer on FakeMT5 (``build_trading(..., fake=True)``).

The grid is ``lines 90 / 100 / 110, step 10`` (Z = 1.3158, away 5, P1 = line -/+ 1.3158 on the price side, P2 =
line +/- 1.9737 beyond, SL = line +/- 5, TP = line -/+ 10); the filler bars sit at 103, so the candidates of every
hour are BUY 100 and SELL 110. The bid is pinned by the test (``FakeMT5.price_override``); the ask is the bid + 0.2.

The world starts two seconds before the 10:00 open (hour 130): the first ``step(2)`` is that hour's decision."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.broker.execution import ExecutionGateway
from app.broker.factory import BrokerBundle, build_trading
from app.config import Settings, load_settings
from app.core.clock import ManualClock
from app.core.enums import TradingMode
from app.risk.kill_switch import KillSwitch
from app.storage.database import Database
from app.zone.core import PER_H, Bars, Grid, check_frame, cut_bars
from app.zone.params import ZoneParams
from app.zone.store import ZoneStore
from app.zone.trader import ProcessLock, RunnerConfig, ZoneRunner

Row = tuple[float, float, float, float]
FILL: Row = (103.0, 104.0, 102.0, 103.0)
START = pd.Timestamp("2025-01-01 00:00", tz="UTC")  # a Wednesday
N_FILL = 130  # hour 130 = Monday 2025-01-06 10:00 UTC
GRID = Grid(pd.Timestamp("2025-01-01", tz="UTC"), 100.0, 10.0, "test")  # lines 90, 100, 110
SERVER_OFFSET_H = 2  # the broker's server time (Europe/Athens in winter) is UTC+2
MAGIC = 7_310_100
LOGIN = 12345678


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def hour_time(k: int) -> pd.Timestamp:
    return START + pd.Timedelta(hours=k)


def frame(start: pd.Timestamp, minutes: int, rows: list[Row], spread: int = 0) -> pd.DataFrame:
    ot = [start + pd.Timedelta(minutes=minutes * k) for k in range(len(rows))]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df["open_time"] = ot
    df["close_time"] = [t + pd.Timedelta(minutes=minutes) for t in ot]
    df["time_server"] = [int(t.timestamp()) for t in ot]
    df["spread"] = spread
    df["tick_volume"] = 1
    df["real_volume"] = 0
    return check_frame(df, "constructed")


def make_full(
    last_hour: int = 150,
    exec_rows: dict[int, list[Row]] | None = None,
    exec_tf: str = "M15",
    spread: int = 0,
) -> Bars:
    """The whole script: ``last_hour`` hours of H1; the exec frame has the filler except the hours in ``exec_rows``
    (hour index -> that hour's exec rows); H1 bars are the aggregate of their exec rows. The D1 / H4 frames are
    flat (no pivot: sideways) and cover the whole script on the server's boundaries; the grid comes from the
    test."""
    per_h = PER_H[exec_tf]
    ex_rows: list[Row] = []
    h1_rows: list[Row] = []
    for k in range(last_hour):
        rows = (exec_rows or {}).get(k, [FILL] * per_h)
        assert len(rows) == per_h, f"hour {k}: {len(rows)} exec rows, {per_h} needed"
        ex_rows += rows
        h1_rows.append((rows[0][0], max(r[1] for r in rows), min(r[2] for r in rows), rows[-1][3]))
    h1 = frame(START, 60, h1_rows, spread)
    ex = frame(START, 60 // per_h, ex_rows, spread)
    # D1 / H4: flat (no pivot) and continuous over the whole script, opening on the broker's server boundaries
    # (UTC+2: the server's midnight is 22:00 UTC) - L2 expects every bar a quote was read in, every frame alike
    server_day = START - pd.Timedelta(hours=SERVER_OFFSET_H)
    d1 = frame(server_day, 1440, [FILL] * (last_hour // 24 + 2))
    h4 = frame(server_day, 240, [FILL] * (last_hour // 4 + 2))
    m15 = ex if exec_tf == "M15" else frame(START, 15, [FILL] * (last_hour * 4), spread)
    m5 = ex if exec_tf == "M5" else frame(START, 5, [FILL] * 20)
    return Bars(d1, h4, h1, m15, m5, 0.01)


class ScriptedBars:
    """``BarSource``: the scripted bars that the test clock has closed; the forming H1 bar's open."""

    def __init__(self, full: Bars, clock: ManualClock) -> None:
        self.full, self.clock = full, clock
        self.fail = False
        self.fail_tfs: set[str] = set()  # frames whose read fails (the others work)

    def _now(self) -> pd.Timestamp:
        return pd.Timestamp(self.clock.now_utc())

    def closed_bars(self, tf: str, after: pd.Timestamp | None) -> pd.DataFrame:
        if self.fail or tf in self.fail_tfs:
            raise OSError("bars unavailable")
        df = self.full.frame(tf)
        df = df[df["close_time"] <= self._now()]
        if after is not None:
            df = df[df["open_time"] > after]
        return df.reset_index(drop=True)

    def last_closed_open(self, tf: str) -> pd.Timestamp | None:
        if self.fail or tf in self.fail_tfs:
            raise OSError("bars unavailable")
        df = self.full.frame(tf)
        df = df[df["close_time"] <= self._now()]
        return None if df.empty else pd.Timestamp(df["open_time"].iloc[-1])

    def forming_h1(self) -> tuple[pd.Timestamp, float] | None:
        h1 = self.full.h1
        now = self._now()
        cur = h1[(h1["open_time"] <= now) & (h1["close_time"] > now)]
        if cur.empty:
            return None
        return pd.Timestamp(cur["open_time"].iloc[0]), float(cur["open"].iloc[0])


def settings(mode: str = "DEMO", **env: str) -> Settings:
    base = {
        "TRADING_MODE": mode,
        "MT5_LOGIN": str(LOGIN),
        "MT5_PASSWORD": "master-pass",
        "MT5_SERVER": "FBS-Demo",
        "MT5_TERMINAL_PATH": "x",
        "ENABLE_DEMO_TRADING": "true",
    }
    base.update(env)
    return load_settings(env_file=None, config_file="config.yaml", environ=base)


@dataclass
class World:
    clock: ManualClock
    bundle: BrokerBundle
    exe: ExecutionGateway
    src: ScriptedBars
    runner: ZoneRunner
    db: Database
    kill: KillSwitch
    full: Bars
    tmp: Path
    params: ZoneParams
    sets: Settings
    lines: list[str] = field(default_factory=list)

    @property
    def fake(self):  # type: ignore[no-untyped-def]
        assert self.bundle.fake is not None
        return self.bundle.fake

    @property
    def store(self) -> ZoneStore:
        assert self.runner.store is not None
        return self.runner.store

    def bid(self, price: float) -> None:
        self.fake.price_override["XAUUSD"] = price

    def step(self, seconds: float = 2.0, bid: float | None = None) -> None:
        if bid is not None:
            self.bid(bid)
        self.clock.advance(seconds)
        self.runner.cycle()

    def to(self, when: str | pd.Timestamp, bid: float | None = None) -> None:
        """Move the clock to ``when`` and run one cycle."""
        t = ts(when) if isinstance(when, str) else when
        if bid is not None:
            self.bid(bid)
        self.clock.set(t.to_pydatetime())
        self.runner.cycle()

    def orders(self) -> list:  # type: ignore[type-arg]
        return list(self.fake.orders)

    def positions(self) -> list:  # type: ignore[type-arg]
        return list(self.fake.positions)

    def order_prices(self) -> dict[str, float]:
        return {o.comment: o.price_open for o in self.fake.orders}

    def names(self) -> list[str]:
        return sorted(o.comment for o in self.fake.orders)


def make_world(
    tmp: Path,
    *,
    now: str = "2025-01-06 09:59:58",  # L8: the first decision is the first H1 open after the start
    exec_rows: dict[int, list[Row]] | None = None,
    exec_tf: str = "M15",
    params: ZoneParams | None = None,
    mode: str = "DEMO",
    start: bool = True,
    spread: int = 0,
    last_hour: int = 150,
    db: Database | None = None,
    fake_bid: float = 103.0,
    **env: str,
) -> World:
    params = params or ZoneParams(exec_tf=exec_tf, cancel_frac=0.9)
    clock = ManualClock(datetime(2025, 1, 6, 10, 0, 5, tzinfo=UTC))
    clock.set(ts(now).to_pydatetime())
    sets = settings(mode, **env)
    bundle = build_trading(sets, fake=True, clock=clock)
    bundle.client.connect()
    full = make_full(last_hour, exec_rows, exec_tf, spread)
    src = ScriptedBars(full, clock)
    if db is None:
        db = Database(f"sqlite:///{(tmp / 'engine.db').as_posix()}")
        db.create_all()
    kill = KillSwitch(tmp / "KILL_SWITCH", clock=clock)
    cfg = RunnerConfig(
        lot=0.01,
        cycle_seconds=2.0,
        stale_quote_seconds=30.0,
        preclose_seconds=15.0,
        epoch=ts("2025-01-01"),
        symbol="XAUUSD",
        market="XAUUSD",
        set_name="default",
        set_version=1,
        mode=TradingMode(mode),
        env=sets.env,
    )
    runner = ZoneRunner(
        cfg=cfg,
        params=params,
        clock=clock,
        gateway=bundle.gateway,
        execution=ExecutionGateway(bundle.client),
        bar_source=src,
        db=db,
        bars=cut_bars(full, pd.Timestamp(clock.now_utc())),
        kill_switch=kill,
        magic=MAGIC,
        grids_fn=lambda bars, p, end: [GRID],
        lock=ProcessLock(tmp / "runner.lock"),
    )
    w = World(clock, bundle, ExecutionGateway(bundle.client), src, runner, db, kill, full, tmp, params, sets)
    bundle_fake = bundle.fake
    assert bundle_fake is not None
    bundle_fake.price_override["XAUUSD"] = fake_bid
    if start:
        runner.start()
    return w


def quiet_logs() -> None:
    logging.getLogger("app.zone").setLevel(logging.INFO)
