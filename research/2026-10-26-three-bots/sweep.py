"""Tune each bot alone (owner 2026-10-26: profit first): variants of bots.py's conditions, one bot at a time, run
in parallel; each line = trades, win %, R / trade after the spread, total R, weeks + / -.

    .venv/Scripts/python research/2026-10-26-three-bots/sweep.py ROUND
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bots  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

F: dict = {}


def load() -> None:
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    for tf in (Timeframe.M1, Timeframe.H1):  # only the year tested (each worker holds its own copy)
        x = to_frame(hs.load("FBS-Demo", "XAUUSD", tf, None, None))
        F[tf] = x[(x.index >= bots.START - pd.Timedelta(days=40)) & (x.index < bots.END + pd.Timedelta(days=3))]


def one(args: tuple[str, bots.P]) -> str:
    if not F:
        load()
    name, p = args
    tr = bots.run(F, p)
    if not tr:
        return f"| {name} | 0 | - | - | - | - |"
    df = pd.DataFrame([{"at": t.at, "r": t.r} for t in tr])
    wk = df.groupby(df["at"].dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("W")).r.sum()
    return (f"| {name} | {len(df)} | {(df.r > 0).mean():.0%} | {df.r.mean():+.3f} | {df.r.sum():+.1f} | "
            f"{(wk > 0).sum()} / {(wk <= 0).sum()} |")


ROUNDS = {
    "1": [
        *[(f"DOWN box {b} retr {r} buf {u} minR {m}", replace(bots.P(), bots=("DOWN",), box=b, retrace=r, buffer=u, min_r=m))
          for b in (0.2, 0.33) for r in ((0.382, 0.786), (0.236, 0.618)) for u in (0.2, 0.5) for m in (0.8, 1.2)],
        *[(f"UP box {b} retr {r} buf {u} minR {m}", replace(bots.P(), bots=("UP",), box=b, retrace=r, buffer=u, min_r=m))
          for b in (0.2, 0.33) for r in ((0.382, 0.786), (0.236, 0.618)) for u in (0.2, 0.5) for m in (0.8, 1.2)],
        *[(f"RANGE tp {tp} buf {u} minR {m}", replace(bots.P(), bots=("RANGE",), tp_range=tp, buffer=u, min_r=m))
          for tp in (0.3, 0.5, 0.8) for u in (0.2, 0.6) for m in (0.5, 1.0)],
    ],
    "2": [
        *[(f"DOWN best d1 {d} run {r} minTP {m}", replace(bots.P(), bots=("DOWN",), box=0.2, min_r=1.2, d1=d, run=r, min_tp=m))
          for d in (False, True) for r in (1.2, 0) for m in (5.0, 3.0)],
        *[(f"UP d1 {d} box {b} minR {mr}", replace(bots.P(), bots=("UP",), box=b, min_r=mr, d1=d))
          for d in (False, True) for b in (0.2, 0.33) for mr in (0.8, 1.2)],
        *[(f"RANGE {mode} tp {tp} buf {u} minR {m}", replace(bots.P(), bots=("RANGE",), range_mode=mode, tp_range=tp, buffer=u, min_r=m))
          for mode in ("opposite", "break") for tp in (0.3, 0.6) for u in (0.2, 0.6) for m in (0.5, 1.0)],
    ],
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    jobs = ROUNDS[sys.argv[1] if len(sys.argv) > 1 else "1"]
    print("| variant | trades | win % | R / trade | total R | weeks + / - |")
    print("|---|---|---|---|---|---|")
    with ProcessPoolExecutor(max_workers=4) as ex:
        for line in ex.map(one, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
