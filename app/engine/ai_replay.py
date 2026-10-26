"""The AI trader in a backtest - replays of past days through the live entry point (PLAN §A37, TAA-1807).

The live engine's :class:`~app.engine.ai_trader.AITraderLane` runs unchanged: on each closed M1 bar it hands
the bars to the watcher, which wakes the AI and runs the brakes; the decision goes to the ``ai_trader``
strategy by :func:`~app.engine.ai_trader.hand_over`, which waits for its price on the stored ticks and enters
through the backtest's decision engine. Only two things differ from live: the bars come from the history
store at the replay's clock (:class:`HistoryCandles`), and the provider is a
:class:`~app.ai.replay.ReplayProvider` (answers stored by input hash).

The AI's answer arrives right after the bar close here; live it arrives 5-60 s later (a caveat for entries in
the first seconds of a minute).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from app.ai.providers import AIProvider
from app.ai.replay import ReplayProvider
from app.config import AITraderConfig
from app.core.clock import Clock, ManualClock
from app.core.enums import Side, Timeframe
from app.engine.ai_trader import COUNTS, AITraderLane, hand_over, position_note
from app.market_data.data_models import CandleFrame, QualityReport
from app.news.releases import Release
from app.strategy.ai_lane import AITrader, AITraderParams


class HistoryCandles:
    """``closed_candles`` over stored history: the last ``count`` bars closed by the clock's now."""

    def __init__(self, frames: Mapping[Timeframe, pd.DataFrame], clock: Clock) -> None:
        self.clock = clock
        self.frames = {tf: df.sort_values("open_time").reset_index(drop=True) for tf, df in frames.items()}
        self._close = {
            tf: pd.DatetimeIndex(pd.to_datetime(df["close_time"], utc=True)) for tf, df in self.frames.items()
        }

    def closed_candles(self, symbol: str, tf: Timeframe, count: int) -> CandleFrame:
        now = self.clock.now_utc()
        df = self.frames[tf]
        n = int(self._close[tf].searchsorted(pd.Timestamp(now), side="right"))
        rows = df.iloc[max(0, n - count) : n].reset_index(drop=True)
        return CandleFrame(symbol, tf, rows, QualityReport(), now)


class AIReplay:
    """One AI lane in a backtest: :meth:`step` at each M1 close of its symbol (the engine calls it after the
    broker and the lanes stepped); the decision goes to the lane's ``ai_trader`` strategy as live
    (``Engine._ai_hand_over``)."""

    def __init__(self, lane: AITraderLane, clock: ManualClock) -> None:
        self.lane = lane
        self.clock = clock
        self.decisions: list[tuple[datetime, dict[str, Any], str]] = []  # (bar close, record, what was done)
        self._held: set[tuple[str, float, str]] = set()  # the open trades seen at the last step
        self._errors = 0  # AI calls failed in a row

    @property
    def symbol(self) -> str:
        return self.lane.cfg.symbol

    def _live(self, at: datetime, positions: Sequence[Any], closed: Sequence[Any]) -> None:
        """The trades opened and closed since the last step, appended to the store's trades_live.jsonl."""
        self._held, rows = live_events(self._held, positions, closed, at)
        if rows:
            self.lane.store.mkdir(parents=True, exist_ok=True)
            with (self.lane.store / "trades_live.jsonl").open("a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, default=str) + "\n")

    def step(
        self,
        at: datetime,
        strategy: AITrader | None,
        positions: Sequence[tuple[Side, float, float | None, float | None, datetime]] = (),
        closed: Sequence[Any] | None = None,
    ) -> str | None:
        """One engine cycle at the bar close ``at`` with the strategy's open positions (side, entry, stop,
        target, opened); returns what the strategy did with a new decision."""
        self.clock.set(at)
        self._live(at, positions, closed or ())
        pending = None if strategy is None else strategy.pending(self.symbol, at)
        self.lane.position = position_note(list(positions), pending)
        self.lane.tick()
        if strategy is not None:  # C9: a position gone at its take-profit blocks its side for a while
            strategy.note_positions(self.symbol, list(positions), self.lane.m1)
            strategy.confirm_orders(self.symbol, self.lane.m1, at)  # a touched order waits for its signal
        orders = self.lane.take_plan_orders()
        if orders is not None and strategy is not None:
            strategy.set_plan_orders(self.symbol, orders)
        rec = self.lane.take_decision()
        if rec is None:
            return None
        self._errors = self._errors + 1 if rec.get("status") not in ("OK", None) else 0
        if self._errors >= MAX_ERRORS:
            raise RuntimeError(
                f"{self._errors} AI calls failed in a row ({rec.get('detail')}): the replay stops"
            )
        done = "none"
        if strategy is not None:
            p: AITraderParams = strategy.params
            done = hand_over(strategy, self.symbol, rec, p.pending_minutes)
        self.decisions.append((at, rec, done))
        return done


MAX_ERRORS = 3  # failed AI calls in a row that stop a replay (07-06: the quota ran out mid-day)


def live_events(
    held: set[tuple[str, float, str]],
    positions: Sequence[tuple[Side, float, float | None, float | None, datetime]],
    closed: Sequence[Any],
    at: datetime,
) -> tuple[set[tuple[str, float, str]], list[dict[str, Any]]]:
    """The trades opened (new in ``positions``) and closed (``closed``, the broker's ClosedTrades) at ``at``,
    as rows for the live report (owner 2026-10-25: report a trade when it opens and when it closes)."""
    now = {(p[0].value, round(p[1], 2), pd.Timestamp(p[4]).isoformat()) for p in positions}
    rows: list[dict[str, Any]] = []
    for side, entry, sl, tp, opened in positions:
        key = (side.value, round(entry, 2), pd.Timestamp(opened).isoformat())
        if key not in held:
            rows.append({"event": "OPEN", "at": pd.Timestamp(opened).isoformat(), "side": side.value,
                         "entry": entry, "sl": sl, "tp": tp})  # fmt: skip
    for x in closed:
        key = (x.side.value, round(x.entry_price, 2), pd.Timestamp(x.entry_time).isoformat())
        if key not in held:  # opened and closed inside one step: its OPEN first
            rows.append({"event": "OPEN", "at": pd.Timestamp(x.entry_time).isoformat(), "side": x.side.value,
                         "entry": x.entry_price, "sl": x.sl_initial, "tp": x.tp_initial})  # fmt: skip
        risk = abs(x.entry_price - (x.sl_initial or x.entry_price))
        r = None if risk == 0 else (x.exit_price - x.entry_price) * x.side.sign / risk
        rows.append({
            "event": "CLOSE", "at": pd.Timestamp(x.exit_time).isoformat(), "side": x.side.value,
            "entry": x.entry_price, "exit": x.exit_price, "reason": x.exit_reason.value, "r": r,
            "usd": x.profit + x.commission + x.swap, "lots": x.volume,
        })  # fmt: skip
    return now, rows


def build_replay(
    cfg: AITraderConfig,
    frames: Mapping[Timeframe, pd.DataFrame],
    releases: tuple[Release, ...],
    store: Path,
    answers: Path,
    inner: AIProvider | None,
    journal: Path | None = None,
    spend: Literal["stored", "api", "none"] = "none",
) -> AIReplay:
    """The AI lane over stored ``frames`` (every timeframe of :data:`~app.engine.ai_trader.COUNTS`), its
    answers from ``answers`` (a miss asks ``inner``; None: SKIPPED), the watcher's files in ``store``."""
    missing = sorted(tf.value for tf in COUNTS if tf not in frames)
    if missing:
        raise ValueError(f"the AI replay needs the stored {missing} bars")
    clock = ManualClock(datetime(2000, 1, 1, tzinfo=UTC))
    # live answers through the CLI on the owner's plan first (owner 2026-10-24: CLI tier 1, API tier 2)
    provider = ReplayProvider(answers, clock, inner, spend=spend)
    lane = AITraderLane(
        cfg, HistoryCandles(frames, clock), provider, releases, store, journal or store / "journal.md",
        background=False,
    )  # fmt: skip
    return AIReplay(lane, clock)
