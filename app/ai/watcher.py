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

from app.ai.plan import plan_due, plan_key
from app.ai.trader import EFFORT, QUIET_EFFORT
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
    plan_levels: tuple[float, ...] = (),
    prev_close: float | None = None,
    holding: bool = False,
) -> list[str]:
    """Why the AI should be woken now (empty = let it sleep). ``closes`` = the M1 closes since the last check,
    ``new_behaviours`` = the behaviours present now and not at the AI's last call, ``in_window`` = inside the
    owner's windows (the regular check runs only there), ``plan_levels`` = the entries of the day plan's
    scenarios: a close arriving within PLAN_NEAR of one wakes it (``prev_close`` = the close before
    ``closes``; owner 2026-10-25: be awake at the plan's level to trade it on the spot). Outside the windows
    it sleeps unless ``holding`` (an open position or a waiting order to manage): R09 stops new trades there,
    and 34 of the 66 calls of 2026-07-06 were spent there (owner 2026-10-25: "60-odd alerts - something is
    wrong"); a watched price wakes it again only WATCH_COOLDOWN minutes after its last call."""
    if last_call is None:
        return ["the first call"]
    if not in_window and not holding:
        return []
    out = []
    minutes = (now - last_call).total_seconds() / 60
    if minutes >= WATCH_COOLDOWN:
        if above is not None and any(c > above for c in closes):
            out.append(f"an M1 close over {above:.2f}")
        if below is not None and any(c < below for c in closes):
            out.append(f"an M1 close under {below:.2f}")
    moving = sorted(new_behaviours & MOVING)
    if moving and minutes >= COOLDOWN:
        out.append("new: " + ", ".join(moving))
    if in_window and minutes >= HEARTBEAT:
        out.append(f"{HEARTBEAT}-minute check")
    path = ([prev_close] if prev_close is not None else []) + list(closes)
    for lv in plan_levels if minutes >= WATCH_COOLDOWN else ():  # 07-06 07:09-07:11: woken every minute
        near = [abs(c - lv) <= PLAN_NEAR for c in path]
        if any(near[1:] if prev_close is not None else near) and not (prev_close is not None and near[0]):
            out.append(f"at the plan's level {lv:.2f}")
    return out


def position_tail(journal: str) -> str:
    """The position note at the very end of the text, so no cut can drop it (07-06, ISSUES 11)."""
    k = journal.rfind("THE SYSTEM'S POSITION NOW")
    return "" if k < 0 else "\n\n" + journal[k:]


def plan_order(s: dict[str, Any]) -> str:
    """A day plan's scenario as the order it stands for."""
    return (
        f"{s.get('name')} {s.get('side')} ({s.get('where')}): entry {s.get('entry')}, stop {s.get('stop')}, "
        f"take-profit {s.get('take_profit')} - trigger: {s.get('trigger')}"
    )


def orders_block(orders: list[str], reasons: list[str]) -> str:
    """The plan's orders as the default answer (owner 2026-10-25, 06-07 Jul: every planned trade printed and
    the AI waited for more each time)."""
    if not orders:
        return ""
    at = [r for r in reasons if r.startswith("at the plan's level")]
    head = (
        "\n\nTHE DAY PLAN'S ORDERS - THE DEFAULT ANSWER (L20): when price is at or through a scenario's "
        "trigger, that scenario's order IS your decision - at market, or pending at its entry - unless a "
        "HARD "
        "checklist item fails (name it); a scenario whose entry is near is placed now as a pending order."
    )
    if at:
        head += f" You were woken {at[0]}."
    return head + "\n" + "\n".join(f"- {o}" for o in orders)


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
    weapon = f" {d['weapon']}" if d.get("weapon") else ""
    return (
        f"\n### {now.tz_convert(TH):%H:%M} Thai - the AI woken by: {'; '.join(reasons)}\n"
        f"- **{d.get('decision', rec.get('status'))}**{weapon} (size {rec.get('final_size')}"
        f"{veto}; confidence {d.get('confidence')}): {d.get('setup', rec.get('detail', ''))}\n"
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
    last_plan: str | None = None  # 'YYYY-MM-DD:kind' of the last day plan written (app/ai/plan.py)
    plan_levels: list[float] = field(default_factory=list)  # its scenarios' entries: wake there
    plan_orders: list[str] = field(default_factory=list)  # its scenarios as orders, shown at every call
    last_close: float | None = None  # the last M1 close seen (arriving at a plan level)

    @classmethod
    def load(cls, path: Path) -> WatchState:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: raw.get(k) for k in cls.__dataclass_fields__ if k in raw})

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.__dict__), encoding="utf-8")


PLAN_NEAR = 1.0  # USD: an M1 close this close to a plan scenario's entry wakes the AI
PLAN_RETRY = 10  # minutes before a failed plan is asked again
WATCH_COOLDOWN = 5  # minutes after a call before a watched price wakes it again (07-06: 07:00 then 07:02)
Decide = Callable[[pd.Timestamp, str, str | None, str], dict[str, Any]]
Plan = Callable[[pd.Timestamp, str], dict[str, Any]]


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
        plan: Plan | None = None,
        holding: Callable[[], bool] = lambda: False,
    ) -> None:
        self.store = store
        self.frames = frames
        self.decide = decide
        self.journal = journal
        self.entries = entries
        self.cap_usd = cap_usd
        self.model = model
        self.plan = plan  # the day plan at each window's start (P26), before any decision
        self.holding = holding  # an open position or a waiting order: woken outside the windows too
        self._plan_retry_at: pd.Timestamp | None = None
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
        kind = plan_due(now, self.state.last_plan)
        retry_at = self._plan_retry_at
        if kind is not None and retry_at is not None and now < retry_at:
            kind = None  # a failed plan waits PLAN_RETRY minutes (07-06: the quota stopped the calls)
        if kind is not None and self.plan is not None:  # the day's plan first (owner 2026-10-25, P26)
            rec = self.plan(now, kind)
            retry = (rec or {}).get("status") not in (None, "OK") and "plan" not in (rec or {})
            if not retry:
                self.state.last_plan = plan_key(now, kind)
            self._plan_retry_at = now + pd.Timedelta(minutes=PLAN_RETRY) if retry else None
            scenarios = ((rec or {}).get("plan") or {}).get("scenarios") or []
            self.state.plan_levels = [float(s["entry"]) for s in scenarios if s.get("entry") is not None]
            self.state.plan_orders = [plan_order(s) for s in scenarios]
            self.state.save(self.store / "watch_state.json")
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
            tuple(self.state.plan_levels),
            self.state.last_close,
            self.holding(),
        )
        if closes:
            self.state.last_close = closes[-1]
        if not reasons:
            self.state.save(self.store / "watch_state.json")
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
            + orders_block(self.state.plan_orders, reasons)
            + position_tail(self.journal())
        )
        quiet = all(r.endswith("-minute check") for r in reasons)  # the regular check only: think less
        rec = self.decide(now, text, self.model, QUIET_EFFORT if quiet else EFFORT)
        d = rec.get("decision") or {}
        self.state = WatchState(
            now.isoformat(), d.get("watch_above"), d.get("watch_below"), list(self.state.behaviours),
            list(self.state.behaviours), self.state.last_plan, list(self.state.plan_levels),
            list(self.state.plan_orders), self.state.last_close,
        )  # fmt: skip
        self.state.save(self.store / "watch_state.json")
        with session.open("a", encoding="utf-8") as fh:
            fh.write(session_entry(now, reasons, rec))
        return rec
