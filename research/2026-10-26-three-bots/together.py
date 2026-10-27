"""Three traders side by side (owner 2026-10-26: "the bots are like three traders, each trading its own setup at
the same time") - and is the sideways setup worth more work?

Three questions, on the same 12 months as bots.py:

1. **How much of the trading time is each condition?** Every M5 close inside the owner's windows, labelled by the
   ZigZag read on H1 - so we know which setup the hours are actually in;
2. **One position or three?** Each bot run with its own best conditions, then the trades combined two ways:
   ONE TRADER (one position at a time across all three, the next signal skipped while a trade is open) and
   THREE TRADERS (each bot holds its own position, so they can overlap);
3. **Why the sideways trades lose:** every RANGE loser - how far it ran against the entry, whether its
   take-profit was reached later that day, and what the opposite side would have made.

    .venv/Scripts/python research/2026-10-26-three-bots/together.py
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

BEST = {
    "DOWN": replace(bots.P(), bots=("DOWN",), box=0.2, retrace=(0.382, 0.786), buffer=0.2, min_r=1.2),
    "UP": replace(bots.P(), bots=("UP",), box=0.33, retrace=(0.382, 0.786), buffer=0.2, min_r=1.2),
    "RANGE": replace(bots.P(), bots=("RANGE",), range_mode="break", tp_range=0.3, buffer=0.6, min_r=0.5),
}


def census(f: dict) -> None:
    """Every M5 close inside the windows, by condition."""
    m1, h1 = f[Timeframe.M1], f[Timeframe.H1]
    counts: dict[str, int] = {}
    for day in pd.date_range(bots.START, bots.END, freq="D"):
        if day.weekday() >= 5:
            continue
        for w0, w1 in bots.windows(day):
            seg = m1[(m1.index >= w0) & (m1.index < w1)]
            if not len(seg):
                continue
            marks = pd.date_range(w0, w1, freq="5min")
            for t in marks:
                hx = h1[h1.index + pd.Timedelta(hours=1) <= t].iloc[-400:]
                if len(hx) < 60:
                    continue
                mk, _ = bots.market(hx)
                counts[mk] = counts.get(mk, 0) + 1
    total = sum(counts.values()) or 1
    print("\n== how much of the trading time each condition holds ==")
    print("| condition | M5 closes in the windows | share |")
    print("|---|---|---|")
    for k in ("DOWN", "UP", "RANGE", "NONE"):
        if k in counts:
            print(f"| {k} | {counts[k]} | {counts[k] / total:.0%} |")


def combine(all_trades: list, one_position: bool) -> pd.DataFrame:
    """The trades as one trader (one position at a time) or three (each bot its own)."""
    rows = sorted(all_trades, key=lambda t: t.at)
    kept, free_until = [], None
    for t in rows:
        if one_position and free_until is not None and t.at < free_until:
            continue
        kept.append(t)
        free_until = t.extra["closed"]
    return pd.DataFrame([{"bot": t.bot, "at": t.at, "r": t.r, "out": t.out} for t in kept])


def show(df: pd.DataFrame, title: str) -> None:
    if not len(df):
        print(f"\n== {title}: no trades ==")
        return
    wk = df.groupby(df["at"].dt.tz_convert(bots.TH).dt.tz_localize(None).dt.to_period("W")).r.sum()
    print(f"\n== {title}: {len(df)} trades, {df.r.sum():+.1f} R, {df.r.mean():+.3f} R / trade, "
          f"weeks {int((wk > 0).sum())} + / {int((wk <= 0).sum())} - ==")
    print("| bot | trades | win % | R / trade | total R |")
    print("|---|---|---|---|---|")
    for bot, g in df.groupby("bot"):
        print(f"| {bot} | {len(g)} | {(g.r > 0).mean():.0%} | {g.r.mean():+.3f} | {g.r.sum():+.1f} |")


def range_losers(f: dict, trades: list) -> None:
    m1 = f[Timeframe.M1]
    bad = [t for t in trades if t.bot == "RANGE" and t.r < 0]
    print(f"\n== the {len(bad)} sideways losers: what happened after ==")
    reached, opposite_win, gone = 0, 0, []
    for t in bad:
        sell = t.side == "SELL"
        end = pd.Timestamp(t.at).normalize() + pd.Timedelta(days=1)
        after = m1[(m1.index >= t.extra["closed"]) & (m1.index < end)]
        if not len(after):
            continue
        hit = ((after.low <= t.tp) if sell else (after.high >= t.tp)).any()
        reached += bool(hit)
        risk = abs(t.stop - t.entry)
        # the opposite side, same entry, stop and target mirrored
        opp_stop, opp_tp = 2 * t.entry - t.stop, 2 * t.entry - t.tp
        held = m1[(m1.index >= t.at) & (m1.index < end)]
        res = 0.0
        for _, b in held.iterrows():
            if (b.low <= opp_stop) if sell else (b.high >= opp_stop):
                res = -1.0
                break
            if (b.high >= opp_tp) if sell else (b.low <= opp_tp):
                res = abs(opp_tp - t.entry) / risk
                break
        opposite_win += res > 0
        gone.append(res)
    print(f"- the take-profit was reached later the same day in {reached} of {len(bad)}: the level was right, the stop was hit first")
    print(f"- the same moment traded the OTHER way: {opposite_win} of {len(bad)} would have won, {sum(gone) / max(len(gone), 1):+.2f} R each")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    f = {}
    for tf in (Timeframe.M1, Timeframe.H1):
        x = to_frame(hs.load("FBS-Demo", "XAUUSD", tf, None, None))
        f[tf] = x[(x.index >= bots.START - pd.Timedelta(days=40)) & (x.index < bots.END + pd.Timedelta(days=3))]
    census(f)
    all_trades: list = []
    for name, p in BEST.items():
        got = bots.run(f, p)
        all_trades += got
        print(f"- {name} alone: {len(got)} trades, {sum(t.r for t in got):+.1f} R")
    show(combine(all_trades, one_position=False), "THREE TRADERS (each bot its own position)")
    show(combine(all_trades, one_position=True), "ONE TRADER (one position at a time)")
    range_losers(f, all_trades)


if __name__ == "__main__":
    main()
