"""The sideways bot on the big picture (owner 2026-10-26: "sideways has to be measured on H1-H4"), tuned, then
all three bots run side by side on one account - with the numbers cross-checked a second way.

    .venv/Scripts/python research/2026-10-26-three-bots/round3.py
"""

from __future__ import annotations

import sys
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


def load() -> dict:
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    f = {}
    for tf in (Timeframe.M1, Timeframe.H1):
        x = to_frame(hs.load("FBS-Demo", "XAUUSD", tf, None, None))
        f[tf] = x[(x.index >= bots.START - pd.Timedelta(days=60)) & (x.index < bots.END + pd.Timedelta(days=3))]
    return f


def line(name: str, tr: list) -> None:
    if not tr:
        print(f"| {name} | 0 | - | - | - | - |")
        return
    d = pd.DataFrame([{"at": t.at, "r": t.r} for t in tr])
    wk = d.groupby(d["at"].dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("W")).r.sum()
    print(f"| {name} | {len(d)} | {(d.r > 0).mean():.0%} | {d.r.mean():+.3f} | {d.r.sum():+.1f} | "
          f"{int((wk > 0).sum())} / {int((wk <= 0).sum())} |")  # fmt: skip


def sweep(f: dict) -> None:
    print("\n== the sideways bot: the box from H4, entered on the M5 close out of it ==")
    print("| variant | trades | win % | R / trade | total R | weeks + / - |")
    print("|---|---|---|---|---|---|")
    for buf in (0.15, 0.3, 0.6, 1.0):
        for tp in (0.3, 0.5, 0.8):
            p = replace(bots.P(), bots=("RANGE",), range_tf="H4", range_mode="break",
                        tp_range=tp, buffer=buf, min_r=0.8)  # fmt: skip
            line(f"stop {buf:g} x quarter-box, TP {tp:g} of the box", bots.run(f, p))


def detail(f: dict, p: bots.P) -> list:
    tr = bots.run(f, p)
    d = pd.DataFrame([{"at": t.at, "side": t.side, "entry": t.entry, "stop": t.stop, "tp": t.tp,
                       "r": t.r, "out": t.out} for t in tr])  # fmt: skip
    d["risk"] = (d.stop - d.entry).abs()
    d["reward"] = (d.tp - d.entry).abs()
    print(f"\n== the chosen sideways bot, trade by trade ({len(d)} trades) ==")
    print(f"- stop distance: median {d.risk.median():.1f} USD (min {d.risk.min():.1f}, max {d.risk.max():.1f})")
    print(f"- take-profit distance: median {d.reward.median():.1f} USD; reward / risk median {(d.reward / d.risk).median():.1f}")
    print(f"- outcomes: {dict(d.out.value_counts())}")
    # the same total a second way: USD won / lost at 0.01 lot, where 1.00 of price = 1 USD
    usd = (d.r * d.risk).sum()
    print(f"- cross-check: {d.r.sum():+.1f} R; the same trades in USD at 0.01 lot = {usd:+.2f} USD")
    print(f"- worst single trade {d.r.min():+.2f} R; longest losing streak {streak(d.r.tolist())}")
    return tr


def streak(rs: list[float]) -> int:
    worst = cur = 0
    for r in rs:
        cur = cur + 1 if r < 0 else 0
        worst = max(worst, cur)
    return worst


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    sweep(f)
    best = {
        "DOWN": replace(bots.P(), bots=("DOWN",), box=0.2, retrace=(0.382, 0.786), buffer=0.2, min_r=1.2),
        "UP": replace(bots.P(), bots=("UP",), box=0.33, retrace=(0.382, 0.786), buffer=0.2, min_r=1.2),
        "RANGE": replace(bots.P(), bots=("RANGE",), range_tf="H4", range_mode="break",
                         tp_range=0.5, buffer=0.3, min_r=0.8),  # fmt: skip
    }
    detail(f, best["RANGE"])
    print("\n== all three side by side, one account ==")
    print("| bot | trades | win % | R / trade | total R | weeks + / - |")
    print("|---|---|---|---|---|---|")
    allt: list = []
    for name, p in best.items():
        got = bots.run(f, p)
        allt += got
        line(name, got)
    line("ALL", allt)
    d = pd.DataFrame([{"at": t.at, "r": t.r, "bot": t.bot} for t in sorted(allt, key=lambda x: x.at)])
    mo = d.groupby(d["at"].dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("M")).agg(
        trades=("r", "size"), r=("r", "sum")
    )
    print(f"\n- {len(d)} trades in 12 months = {len(d) / 12:.1f} a month; longest losing streak {streak(d.r.tolist())}")
    print("\n== month by month (all three) ==")
    print("| month | trades | R |")
    print("|---|---|---|")
    for m, row in mo.iterrows():
        print(f"| {m} | {int(row.trades)} | {row.r:+.1f} |")


if __name__ == "__main__":
    main()
