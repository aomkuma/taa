"""The research's driver for the AI watcher (TAA-1805): the logic lives in app/ai/watcher.py (one code path, PLAN
§A37); this loop only refreshes the stored history read-only every minute (all frames every 5 minutes, the day's
ticks before a call) and hands each new closed M1 bar to it. It stops after STOP_IDLE minutes without a new bar.

    .venv/Scripts/python research/2026-10-23-entry/watcher.py JOURNAL.md
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "knowledge"))

from app.ai.watcher import (  # noqa: E402,F401  (the names the research's notes cite)
    COOLDOWN, DAILY_CAP_USD, HEARTBEAT, MODEL, MOVING, AIWatcher, spent_today, wake_reasons,
)

STOP_IDLE = 60  # minutes without a new M1 bar: the market is closed


def refresh(frames: str) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts/download_history.py"), "--symbols", "XAUUSD", "--timeframes",  # noqa: S603
                    frames, "--days", "2"], cwd=ROOT, capture_output=True, check=False, timeout=300)


def main() -> None:
    import ai_trader
    import kb
    import zone_wait as zw

    journal = Path(sys.argv[1])

    def decide(as_of: pd.Timestamp, text: str, model: str | None) -> dict:
        subprocess.run([sys.executable, str(HERE / "fetch_day.py"), f"{as_of:%Y-%m-%d}"], cwd=ROOT,  # noqa: S603
                       capture_output=True, check=False, timeout=600)
        return ai_trader.decide(as_of, text, model, source="watcher")

    watcher = AIWatcher(ai_trader.STORE, frames=kb.frames, decide=decide,
                        journal=lambda: journal.read_text(encoding="utf-8"))
    last_bar, checked = None, None
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
        rec = watcher.on_bar(now, closes)
        if rec is not None:
            print(f"{now.tz_convert('Asia/Bangkok'):%H:%M} Thai: {(rec.get('decision') or {}).get('decision', rec['status'])}"
                  f" ({rec.get('cost_usd')} USD)", flush=True)
        time.sleep(max(5.0, 65 - pd.Timestamp.now(tz="UTC").second))


if __name__ == "__main__":
    main()
