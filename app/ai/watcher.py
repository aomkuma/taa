"""The watcher - the code watches every closed M1 bar, the AI is woken only when something happens (PLAN
§A37, TAA-1805; owner 2026-10-23: "is it too slow - should we send every TF?" and the budget "10-15 baht a
day"). Moved from research/2026-10-23-entry/watcher.py, which now drives it from the stored history; the
engine drives it from its own bars.

The AI is woken when:

- an M1 bar closed beyond a price the AI asked to watch (its last answer's ``watch_above`` / ``watch_below``);
- a new behaviour of the moving kind appeared (sweep, break, climax, runaway, handover) that was not there at
  its last call - at most once per ``COOLDOWN`` minutes;
- ``HEARTBEAT`` minutes passed since its last call, inside the owner's windows.

A Thai day's spend by the watcher's own calls is capped (``DAILY_CAP_USD``). A failed cycle never stops the
watcher: the error is logged, counted and written to ``watch_alerts.log`` (2026-10-23 23:45: the research
watcher died silently for 20 minutes when a file moved).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.strategy import knowledge as kn

log = logging.getLogger(__name__)

TH = "Asia/Bangkok"
HEARTBEAT, COOLDOWN = 30, 15  # minutes (the 30-minute check also keeps the 1-hour prompt cache warm)
MOVING = {"sweep", "break", "climax", "runaway", "handover"}
MODEL = "claude-sonnet-5-5"  # the owner's budget - about 0.01 USD a call with the cache
DAILY_CAP_USD = 0.40  # about 14 baht: no call once a Thai day's watcher spend reaches it
SOURCE = "watcher"


def wake_reasons(
    now: pd.Timestamp,
    last_call: pd.Timestamp | None,
    above: float | None,
    below: float | None,
    closes: list[float],
    new_behaviours: set[str],
    in_window: bool,
) -> list[str]:
    """Why the AI should be woken now (empty = let it sleep). ``closes`` = the M1 closes since the last check,
    ``new_behaviours`` = the behaviours present now and not at the AI's last call, ``in_window`` = inside the
    owner's windows (the regular check runs only there)."""
    if last_call is None:
        return ["the first call"]
    out = []
    if above is not None and any(c > above for c in closes):
        out.append(f"an M1 close over {above:.2f}")
    if below is not None and any(c < below for c in closes):
        out.append(f"an M1 close under {below:.2f}")
    minutes = (now - last_call).total_seconds() / 60
    moving = sorted(new_behaviours & MOVING)
    if moving and minutes >= COOLDOWN:
        out.append("new: " + ", ".join(moving))
    if in_window and minutes >= HEARTBEAT:
        out.append(f"{HEARTBEAT}-minute check")
    return out


def spent_today(rows: list[dict[str, Any]], now: pd.Timestamp) -> float:
    """The watcher's AI spend (USD) on the Thai day of ``now`` (manual and test calls are not counted - owner
    2026-10-23: the building cost is outside the budget)."""
    day = now.tz_convert(TH).date()
    return sum(
        float(r.get("cost_usd") or 0)
        for r in rows
        if r.get("source") == SOURCE and pd.Timestamp(r["as_of"]).tz_convert(TH).date() == day
    )


def session_entry(now: pd.Timestamp, reasons: list[str], rec: dict[str, Any]) -> str:
    """The decision as the session's markdown (the AI reads its own earlier calls from it)."""
    d = rec.get("decision") or {}
    veto = ", vetoed by " + ", ".join(rec["vetoed_by"]) if rec.get("vetoed_by") else ""
    return (
        f"\n### {now.tz_convert(TH):%H:%M} Thai - the AI woken by: {'; '.join(reasons)}\n"
        f"- **{d.get('decision', rec.get('status'))}** (size {rec.get('final_size')}{veto}; confidence "
        f"{d.get('confidence')}): {d.get('setup', rec.get('detail', ''))}\n"
        f"- entry {d.get('entry')}, stop {d.get('stop')}, target {d.get('target')}; watch above "
        f"{d.get('watch_above')} / below {d.get('watch_below')}\n- trigger: {d.get('trigger')}\n"
        + "".join(f"- {r}\n" for r in d.get("reasons", []))
        + f"- cost {rec.get('cost_usd')} USD, {rec.get('latency_ms')} ms\n"
    )


def tail(text: str, chars: int) -> str:
    from app.ai.trader import tail as _tail

    return _tail(text, chars)


@dataclass
class WatchState:
    last_call: str | None = None
    watch_above: float | None = None
    watch_below: float | None = None
    behaviours_at_call: list[str] = field(default_factory=list)
    behaviours: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> WatchState:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: raw.get(k) for k in cls.__dataclass_fields__ if k in raw})

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.__dict__), encoding="utf-8")


Decide = Callable[[pd.Timestamp, str, str | None], dict[str, Any]]


class AIWatcher:
    """Call :meth:`on_bar` at each closed M1 bar. ``frames`` gives the bars (the engine's or the stored
    history), ``decide(as_of, journal_text, model)`` asks the AI (app/ai/trader.decide bound to a provider),
    ``journal`` gives the session's journal text; state, the session notes, the decisions and the alerts live
    in ``store``."""

    def __init__(
        self,
        store: Path,
        frames: Callable[[], kn.Frames],
        decide: Decide,
        journal: Callable[[], str],
        *,
        entries: Callable[[], list[dict[str, Any]]] = kn.load,
        cap_usd: float = DAILY_CAP_USD,
        model: str = MODEL,
    ) -> None:
        self.store = store
        self.frames = frames
        self.decide = decide
        self.journal = journal
        self.entries = entries
        self.cap_usd = cap_usd
        self.model = model
        self.state = WatchState.load(store / "watch_state.json")
        self.failures = 0

    def _behaviours(self, now: pd.Timestamp) -> set[str]:
        return set(kn.behaviors_now(self.entries(), kn.features(self.frames(), now)))

    def _spent(self, now: pd.Timestamp) -> float:
        path = self.store / "decisions.jsonl"
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        return spent_today(rows, now)

    def on_bar(self, now: pd.Timestamp, closes: list[float]) -> dict[str, Any] | None:
        """One cycle at ``now`` (the last M1 bar's close); ``closes`` = the M1 closes since the last cycle.
        Returns the AI's decision record when it was woken, else None. Never raises."""
        try:
            return self._cycle(now, closes)
        except Exception as exc:  # a failed cycle must not stop the watcher; it is told, counted and written
            self.failures += 1
            log.exception("AI watcher cycle at %s failed (%d so far)", now, self.failures)
            self.store.mkdir(parents=True, exist_ok=True)
            with (self.store / "watch_alerts.log").open("a", encoding="utf-8") as fh:
                fh.write(f"{now.isoformat()} FAILED ({self.failures}): {type(exc).__name__}: {exc}\n")
            return None

    def _cycle(self, now: pd.Timestamp, closes: list[float]) -> dict[str, Any] | None:
        self.store.mkdir(parents=True, exist_ok=True)
        if now.minute % 5 == 0:
            self.state.behaviours = sorted(self._behaviours(now))
        last_call = pd.Timestamp(self.state.last_call) if self.state.last_call else None
        new = set(self.state.behaviours) - set(self.state.behaviours_at_call)
        reasons = wake_reasons(
            now,
            last_call,
            self.state.watch_above,
            self.state.watch_below,
            closes,
            new,
            kn.session(now) != "none",
        )
        if not reasons:
            return None
        spent = self._spent(now)
        if spent >= self.cap_usd:
            log.info("AI not woken at %s (%s): today's spend %.3f USD reached the cap", now, reasons, spent)
            return None
        session = self.store / f"session_{now.tz_convert(TH):%Y-%m-%d}.md"
        text = (
            tail(self.journal(), 3500)
            + "\n\nTHE AI'S OWN EARLIER CALLS:\n"
            + (tail(session.read_text(encoding="utf-8"), 1500) if session.exists() else "(none)")
        )
        rec = self.decide(now, text, self.model)
        d = rec.get("decision") or {}
        self.state = WatchState(
            now.isoformat(), d.get("watch_above"), d.get("watch_below"), list(self.state.behaviours),
            list(self.state.behaviours),
        )  # fmt: skip
        self.state.save(self.store / "watch_state.json")
        with session.open("a", encoding="utf-8") as fh:
            fh.write(session_entry(now, reasons, rec))
        return rec
