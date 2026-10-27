"""Where each bot's profit really comes from, before believing the totals (memory: cross-check every number).

Per bot: the R split by how the trade ended (take-profit, stop, or closed at the Thai day's end), and how long
trades are held - a scalp system that earns most of its R from positions carried to the next morning is not the
system the owner asked for.

    .venv/Scripts/python research/2026-10-26-three-bots/audit.py
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

# The one definition lives in bots.SHIPPED, next to P, so the two can never drift apart
# (2026-10-27: measuring P() instead of this produced an afternoon of wrong conclusions).
BEST = bots.SHIPPED


def load() -> dict:
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    f = {}
    for tf in (Timeframe.M1, Timeframe.H1):
        x = to_frame(hs.load("FBS-Demo", "XAUUSD", tf, None, None))
        f[tf] = x[
            (x.index >= bots.START - pd.Timedelta(days=60)) & (x.index < bots.END + pd.Timedelta(days=3))
        ]
    return f


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    f = load()
    rows = []
    for name, p in BEST.items():
        for t in bots.run(f, p):
            rows.append({"bot": name, "out": t.out, "r": t.r, "at": t.at, "closed": t.extra["closed"]})
    d = pd.DataFrame(rows)
    d["hours"] = (pd.to_datetime(d["closed"]) - pd.to_datetime(d["at"])).dt.total_seconds() / 3600

    print("== where each bot's R comes from ==")
    print("| bot | how it ended | trades | R | share of that bot's R |")
    print("|---|---|---|---|---|")
    for bot, g in d.groupby("bot"):
        tot = g.r.sum()
        for out, h in g.groupby("out"):
            share = f"{h.r.sum() / tot * 100:+.0f}%" if tot else "-"
            print(f"| {bot} | {out} | {len(h)} | {h.r.sum():+.1f} | {share} |")

    print("\n== how long a trade is held ==")
    for bot, g in d.groupby("bot"):
        print(f"- {bot}: median {g.hours.median():.1f} h, longest {g.hours.max():.1f} h; "
              f"held over 4 h: {int((g.hours > 4).sum())} of {len(g)}")  # fmt: skip

    print("\n== with a time stop: the trade closed this long after it opened, at that bar's close ==")
    print("| time stop | trades | win % | R / trade | total R |")
    print("|---|---|---|---|---|")
    m1 = f[Timeframe.M1]
    for hours in (1, 2, 4, 8, None):
        out = []
        for name, p in BEST.items():
            for t in bots.run(f, p):
                limit = t.at + pd.Timedelta(hours=hours) if hours else t.extra["closed"]
                x = m1[(m1.index >= t.at) & (m1.index < min(limit, t.extra["closed"]))]
                sell = t.side == "SELL"
                risk = abs(t.stop - t.entry)
                px = None
                for _, b in x.iterrows():
                    if (b.high >= t.stop) if sell else (b.low <= t.stop):
                        px = t.stop
                        break
                    if (b.low <= t.tp) if sell else (b.high >= t.tp):
                        px = t.tp
                        break
                if px is None:
                    px = float(x.close.iloc[-1]) if len(x) else t.entry
                gain = (t.entry - px) if sell else (px - t.entry)
                out.append((gain - p.spread) / risk)
        s = pd.Series(out)
        label = f"{hours} h" if hours else "none (to the day's end)"
        print(f"| {label} | {len(s)} | {(s > 0).mean():.0%} | {s.mean():+.3f} | {s.sum():+.1f} |")


if __name__ == "__main__":
    main()
