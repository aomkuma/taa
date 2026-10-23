"""The watcher - the code watches every M1 bar, the AI is woken only when something happens (owner 2026-10-23: "is
it too slow - should we send every TF?" -> the code watches every bar cheaply; the AI judges when there is a reason).

Every minute: the M1 bars refreshed read-only (scripts/download_history.py), every 5 minutes all frames and the
behaviours (knowledge/kb.py). The AI (ai_trader.decide) is woken when:
- an M1 bar closed beyond a price the AI asked to watch (its last answer's watch_above / watch_below);
- a new behaviour of the moving kind appeared (sweep, break, climax, runaway, handover) that was not there at its last
  call - at most once per COOLDOWN minutes;
- HEARTBEAT minutes passed since its last call (an M15 check).
On waking: the day's ticks and bars refreshed (fetch_day.py), the AI decides with the session's journal, the code's
brakes apply; the answer is appended to ai/session_<Thai date>.md (and ai/decisions.jsonl, ai/raw/). Never trades.
It stops after STOP_IDLE minutes without a new M1 bar (the market closed).

    .venv/Scripts/python research/2026-10-23-entry/watcher.py JOURNAL.md
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "knowledge"))

STATE = HERE / "ai" / "watch_state.json"
TH = "Asia/Bangkok"
HEARTBEAT, COOLDOWN, STOP_IDLE = 30, 15, 60  # minutes (the 30-minute check also keeps the 1-hour prompt cache warm)
MOVING = {"sweep", "break", "climax", "runaway", "handover"}
MODEL = "claude-sonnet-5-5"  # the owner's budget (2026-10-23: 10-15 baht a day) - about 0.01 USD a call with the cache
DAILY_CAP_USD = 0.40  # about 14 baht: no call once a Thai day's AI spend reaches it


def wake_reasons(now: pd.Timestamp, last_call: pd.Timestamp | None, above: float | None, below: float | None,
                 closes: list[float], new_behaviours: set[str], in_window: bool) -> list[str]:
    """Why the AI should be woken now (empty = let it sleep). ``closes`` = the M1 closes since the last check,
    ``new_behaviours`` = the behaviours present now and not at the AI's last call, ``in_window`` = inside the
    owner's windows (the hourly check runs only there)."""
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


def spent_today(rows: list[dict], now: pd.Timestamp) -> float:
    """The watcher's AI spend (USD) on the Thai day of ``now``, from ai/decisions.jsonl rows (manual and test calls,
    source != 'watcher', are not counted - owner 2026-10-23: the day's building cost is outside the budget)."""
    day = now.tz_convert(TH).date()
    return sum(float(r.get("cost_usd") or 0) for r in rows
               if r.get("source") == "watcher" and pd.Timestamp(r["as_of"]).tz_convert(TH).date() == day)


def refresh(frames: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts/download_history.py"), "--symbols", "XAUUSD", "--timeframes",  # noqa: S603
                    frames, "--days", "2"], cwd=ROOT, capture_output=True, check=False, timeout=300)


def main() -> None:
    import ai_trader
    import kb
    import zone_wait as zw

    journal = Path(sys.argv[1])
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    last_bar, behaviours, checked = None, set(state.get("behaviours", [])), None
    while True:
        refresh("M1")
        m1 = zw.load("M1")
        bar = m1.index[-1]
        now = bar + pd.Timedelta(minutes=1)  # the last M1 bar's close (its data are closed)
        if last_bar is not None and bar == last_bar:
            idle = (pd.Timestamp.now(tz="UTC") - now).total_seconds() / 60
            if idle > STOP_IDLE:
                print(f"no new M1 bar for {idle:.0f} min - the market is closed; stopping", flush=True)
                return
            time.sleep(30)
            continue
        closes = m1[m1.index >= (checked or bar)].close.tolist()
        last_bar, checked = bar, now
        if now.minute % 5 == 0:
            refresh("M5,M15,H1,H4,D1")
            behaviours = set(kb.behaviors_now(kb.load(), kb.features(now)))
        last_call = pd.Timestamp(state["last_call"]) if state.get("last_call") else None
        new = behaviours - set(state.get("behaviours_at_call", []))
        reasons = wake_reasons(now, last_call, state.get("watch_above"), state.get("watch_below"), closes, new,
                               kb.session(now) != "none")
        log = ai_trader.OUT
        spent = spent_today([json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else [], now)
        if reasons and spent >= DAILY_CAP_USD:
            print(f"{now.tz_convert(TH):%H:%M} woken by {'; '.join(reasons)} - skipped: today's AI spend {spent:.3f} USD "
                  f"reached the cap {DAILY_CAP_USD}", flush=True)
            reasons = []
        if reasons:
            subprocess.run([sys.executable, str(HERE / "fetch_day.py"), f"{now:%Y-%m-%d}"], cwd=ROOT,  # noqa: S603
                           capture_output=True, check=False, timeout=600)
            session = HERE / "ai" / f"session_{now.tz_convert(TH):%Y-%m-%d}.md"
            text = (ai_trader.tail(journal.read_text(encoding="utf-8"), 3500) + "\n\nTHE AI'S OWN EARLIER CALLS:\n"
                    + (ai_trader.tail(session.read_text(encoding="utf-8"), 1500) if session.exists() else "(none)"))
            rec = ai_trader.decide(now, text, MODEL, source="watcher")
            d = rec.get("decision") or {}
            state = {"last_call": now.isoformat(), "watch_above": d.get("watch_above"), "watch_below": d.get("watch_below"),
                     "behaviours_at_call": sorted(behaviours), "behaviours": sorted(behaviours)}
            STATE.write_text(json.dumps(state), encoding="utf-8")
            line = (f"\n### {now.tz_convert(TH):%H:%M} Thai - the AI woken by: {'; '.join(reasons)}\n"
                    f"- **{d.get('decision', rec['status'])}** (size {rec.get('final_size')}"
                    f"{', vetoed by ' + ', '.join(rec['vetoed_by']) if rec.get('vetoed_by') else ''}; confidence "
                    f"{d.get('confidence')}): {d.get('setup', rec.get('detail', ''))}\n"
                    f"- entry {d.get('entry')}, stop {d.get('stop')}, target {d.get('target')}; watch above "
                    f"{d.get('watch_above')} / below {d.get('watch_below')}\n- trigger: {d.get('trigger')}\n"
                    + "".join(f"- {r}\n" for r in d.get("reasons", []))
                    + f"- cost {rec.get('cost_usd')} USD, {rec.get('latency_ms')} ms\n")
            with session.open("a", encoding="utf-8") as fh:
                fh.write(line)
            print(line, flush=True)
        time.sleep(max(5.0, 65 - pd.Timestamp.now(tz="UTC").second))


if __name__ == "__main__":
    main()
