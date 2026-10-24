"""The AI trader lane in the engine (PLAN §A37, TAA-1805): on each closed M1 bar of one symbol the engine
hands the bars to the AI watcher (app/ai/watcher.py), which wakes the AI trader (app/ai/trader.py) when
something happens - the very modules the research's watcher and replays run.

The bars are fetched on the engine loop (the MT5 client is single-threaded); the watcher's cycle, which may
wait 5-15 s for the AI, runs on one background thread, so the loop never waits for it. A new bar while a call
is still running is not lost: its closes are carried to the next cycle. In TAA-1805 the decisions are recorded
only; TAA-1806 turns them into signals through the decision engine.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from app.ai import trader
from app.ai.providers import AIProvider
from app.ai.watcher import AIWatcher
from app.config import AITraderConfig
from app.core.enums import Side, Timeframe
from app.market_data.data_models import CandleFrame
from app.news.releases import Release
from app.strategy import knowledge as kn
from app.strategy.ai_lane import AIOrder, AITrader

log = logging.getLogger(__name__)

# closed bars handed to the readers per frame: M5 from 1,400 x 5 M1 bars (rhythm), 2,600 bars of the rest, the
# D1 history for the zone grid's anchors (research/2026-10-23-entry: rhythm_scan, picture_read, knowledge)
COUNTS = {Timeframe.M1: 7200, Timeframe.M15: 2700, Timeframe.H1: 2700, Timeframe.H4: 2700, Timeframe.D1: 2500}


class ClosedCandles(Protocol):
    def closed_candles(self, symbol: str, tf: Timeframe, count: int) -> CandleFrame: ...


def to_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Candle rows (``CANDLE_COLUMNS``) as the readers take them: indexed by the bar's open (UTC), the last
    copy of a bar kept - the same shape as the research's stored history (research zone_wait.load)."""
    out = df.assign(t=pd.to_datetime(df["open_time"], utc=True)).drop_duplicates("t", keep="last")
    return out.set_index("t").sort_index()[["open", "high", "low", "close", "tick_volume"]]


class AITraderLane:
    def __init__(
        self,
        cfg: AITraderConfig,
        candles: ClosedCandles,
        provider: AIProvider,
        releases: tuple[Release, ...],
        store: Path,
        journal: Path,
        *,
        background: bool = True,
    ) -> None:
        self.cfg = cfg
        self.candles = candles
        self.provider = provider
        self.releases = releases
        self.store = store
        self.journal_path = journal
        self._frames: kn.Frames | None = None
        self._last_open: pd.Timestamp | None = None
        self._checked: pd.Timestamp | None = None
        self._executor = (
            ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-trader") if background else None
        )
        self._running: Future[dict[str, Any] | None] | None = None
        self.cycles = 0
        self._decision: dict[str, Any] | None = None  # the last finished decision, not yet handed over
        self.watcher = AIWatcher(
            store,
            frames=self._current_frames,
            decide=self._decide,
            journal=self._journal,
            cap_usd=cfg.daily_cap_usd,
            model=cfg.model,
        )

    # --- the engine loop ---

    def tick(self) -> bool:
        """Called on every engine cycle; starts at most one watcher cycle per new closed M1 bar, never waits.
        Returns True when one was started."""
        if self._running is not None:
            if not self._running.done():
                return False
            self._decision = self._running.result() or self._decision  # the watcher never raises
            self._running = None
        m1 = self.candles.closed_candles(self.cfg.symbol, Timeframe.M1, 2)
        if m1.last_open_time is None:
            return False
        opened = pd.Timestamp(m1.last_open_time)
        opened = opened.tz_localize("UTC") if opened.tzinfo is None else opened.tz_convert("UTC")
        if self._last_open is not None and opened <= self._last_open:
            return False
        self._frames = self.frames()
        now = opened + pd.Timedelta(minutes=1)  # the bar's close: everything read is closed by it
        since = self._checked if self._checked is not None else opened
        closes = [float(x) for x in self._frames.m1[self._frames.m1.index >= since].close]
        self._last_open, self._checked = opened, now
        self.cycles += 1
        if self._executor is None:
            self._decision = self.watcher.on_bar(now, closes) or self._decision
        else:
            self._running = self._executor.submit(self.watcher.on_bar, now, closes)
        return True

    def take_decision(self) -> dict[str, Any] | None:
        """The AI's last finished decision, once (on the engine loop)."""
        rec, self._decision = self._decision, None
        return rec

    def frames(self) -> kn.Frames:
        """The closed bars of every frame the readers need, from the engine's candle service."""
        get = {
            tf: to_frame(self.candles.closed_candles(self.cfg.symbol, tf, n).df) for tf, n in COUNTS.items()
        }
        return kn.Frames(
            get[Timeframe.M1], get[Timeframe.M15], get[Timeframe.H1], get[Timeframe.H4], get[Timeframe.D1],
            self.releases,
        )  # fmt: skip

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    # --- the watcher's callables (the background thread) ---

    def _current_frames(self) -> kn.Frames:
        if self._frames is None:
            raise RuntimeError("no bars fetched yet")
        return self._frames

    def _journal(self) -> str:
        return self.journal_path.read_text(encoding="utf-8") if self.journal_path.exists() else ""

    def _suspensions(self) -> dict[str, str]:
        path = self.store / "suspended.json"
        rows: dict[str, str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return rows

    def _decide(self, as_of: pd.Timestamp, text: str, model: str | None) -> dict[str, Any]:
        return trader.decide(
            self.provider, kn.load(), self._current_frames(), as_of, text,
            model=model, suspensions=self._suspensions(), store=self.store, source="watcher",
        )  # fmt: skip


def order_from(rec: dict[str, Any], pending_minutes: int) -> AIOrder | None:
    """An AI decision record as an order for the ``ai_trader`` strategy: a SELL / BUY with a size the brakes
    left ('half' / 'full') and its entry and stop; else None."""
    d = rec.get("decision") or {}
    size = rec.get("final_size")
    if d.get("decision") not in ("SELL", "BUY") or size not in ("half", "full"):
        return None
    if d.get("entry") is None or d.get("stop") is None:
        return None
    at = pd.Timestamp(rec["as_of"]).to_pydatetime()
    return AIOrder(
        side=Side.SELL if d["decision"] == "SELL" else Side.BUY,
        entry=float(d["entry"]),
        stop=float(d["stop"]),
        target=None if d.get("target") is None else float(d["target"]),
        risk_scale=0.5 if size == "half" else 1.0,
        setup=str(d.get("setup", "")),
        reasons=tuple(str(x) for x in d.get("reasons", [])),
        kb_ids=tuple(str(x) for x in d.get("kb_ids", [])),
        confidence=int(d.get("confidence") or 0),
        decided_at=at,
        valid_until=at + timedelta(minutes=pending_minutes),
        key=f"step-{pd.Timestamp(rec['as_of']):%Y%m%d%H%M}",
        watch_above=None if d.get("watch_above") is None else float(d["watch_above"]),
        watch_below=None if d.get("watch_below") is None else float(d["watch_below"]),
    )


def hand_over(strategy: AITrader, symbol: str, rec: dict[str, Any], pending_minutes: int) -> str:
    """What the strategy does with the AI's decision: a new order (it replaces a waiting one), an exit of the
    lane's open position, or a WAIT that withdraws a waiting order. Returns what was done."""
    d = rec.get("decision") or {}
    order = order_from(rec, pending_minutes)
    if order is not None:
        strategy.accept(symbol, order)
        return "order"
    if d.get("decision") == "EXIT":
        strategy.request_exit(symbol)
        return "exit"
    if d.get("decision") in ("WAIT", "SELL", "BUY"):  # a wait, or an entry the brakes vetoed
        strategy.cancel(symbol)
        return "cancel"
    return "none"
