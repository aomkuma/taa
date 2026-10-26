"""The morning plan of a replay day, written by the system BEFORE the day is traded (owner 2026-10-25, P26: "before
testing a trading day ... summarise it to me").

The same AI lane the replay runs (app/engine/ai_replay.build_replay over the stored bars, the answers by input
hash, a miss answered by the Claude CLI) takes one step at 07:01 Thai: the watcher writes the morning plan
(app/ai/plan.py) before its first decision. The plan is printed for the owner; then the store is rolled back to the
day's start, so the full replay (day.py) starts clean - its first step asks the same questions on the same bars
and gets the same stored answers, the same plan.

    .venv/Scripts/python research/2026-10-24-replay/plan_day.py 2026-07-06
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from day import CLI, ROOT, RUN  # noqa: E402

from app.ai.replay import ClaudeCLIProvider  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.core.clock import SystemClock  # noqa: E402
from app.engine.ai_replay import build_replay  # noqa: E402
from app.engine.ai_trader import COUNTS  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.news.releases import load_releases  # noqa: E402

TH = "Asia/Bangkok"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    day = date.fromisoformat(sys.argv[1])
    settings = load_settings(
        env_file=None, config_file=str(ROOT / "config.yaml"), environ={"TRADING_MODE": "BACKTEST"}
    )
    cfg = settings.config.ai.trader
    end = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1)
    hist = ParquetHistoryStore(ROOT / "data/history")
    frames = {tf: hist.load("FBS-Demo", cfg.symbol, tf, None, end) for tf in COUNTS}
    releases = load_releases(settings.path(cfg.calendar_file))
    inner = ClaudeCLIProvider(CLI, SystemClock(), model=cfg.model)
    store = RUN / "store"
    replay = build_replay(cfg, frames, releases, store, RUN / "answers", inner, store / "journal.md")
    first = datetime(
        day.year, day.month, day.day, 0, 0, tzinfo=UTC
    )  # 07:00 Thai: the step the day run takes first
    replay.step(first, None)
    rows = [json.loads(x) for x in (store / "plans.jsonl").read_text(encoding="utf-8").splitlines()]
    for pl in rows:
        if pd.Timestamp(pl["as_of"]) >= first:
            print(json.dumps(pl, indent=1, ensure_ascii=False))
    sys.stdout.flush()
    subprocess.run(
        [sys.executable, str(HERE / "rollback.py"), day.isoformat()], check=True, stdout=sys.stderr
    )  # noqa: S603


if __name__ == "__main__":
    main()
