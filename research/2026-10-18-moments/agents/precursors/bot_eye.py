"""Me as the bot (owner, 2026-10-19: "make yourself the bot - check every picture against the bot's, and when the bot
runs compare both sides"): the chart read again from the raw M1 bars with code written apart from the bot's
(picture.py, fingerprint.py, moments.py, plib.tf_bars, foundation.atr), from the rules' text in notes.md - the
timeframe bars, MT5's ATR, the 3-ATR ZigZag, and every reading of the picture: the 120 bars' way and each third's,
the swing structure with the swing still forming, the close against the last top / bottom, where the close sits and
at an edge, the size, the deepest pullback, the smoothness, the last leg, and the zoom to the smaller timeframe. On a
random sample of the present library's moments every reading must equal the bot's.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/bot_eye.py [N]
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
MINUTES = {"M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
SMALL = {"H4": "H1", "H1": "M30", "M30": "M15", "M15": "M5", "M5": "M1", "M1": "M1"}
WINDOW, K_SWING, K_FINE = 120, 3.0, 1.5


def make_bars(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    """A timeframe's OHLC from M1 - open the first, high the highest, low the lowest, close the last - and `done`, the
    time its last M1 bar closes. H4 counts the broker's day (Europe/Athens), the others UTC."""
    if tf == "M1":
        out = m1[["open", "high", "low", "close"]].reset_index(drop=True)
        out["done"] = (m1.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8
        return out
    if tf == "H4":
        key = m1.index.tz_convert("Europe/Athens").tz_localize(None).floor("4h")
    else:
        key = m1.index.tz_localize(None).floor(f"{MINUTES[tf]}min")
    when = pd.Series(m1.index.as_unit("ns").asi8, index=m1.index)
    g = pd.DataFrame({"open": m1.open.to_numpy(), "high": m1.high.to_numpy(), "low": m1.low.to_numpy(),
                      "close": m1.close.to_numpy(), "t": when.to_numpy(), "key": key}).groupby("key", sort=True)
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                        "done": g.t.max() + 60 * 10**9})
    return out.reset_index(drop=True)


def mt5_atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    """The mean of the last n true ranges; the first bar has none (no previous close)."""
    prev = np.concatenate([[np.nan], c[:-1]])
    tr = np.maximum(h, prev) - np.minimum(lo, prev)
    out = np.full(len(h), np.nan)
    for i in range(n, len(h)):  # bars 1..n are the first full window
        out[i] = tr[i - n + 1:i + 1].sum() / n
    return out


def swings(h: np.ndarray, lo: np.ndarray, atr: np.ndarray, k: float) -> list[tuple[int, float, int, int]]:
    """(bar, price, +1 top / -1 bottom, the bar that confirmed it): from the first bar with an ATR, the highest high and
    lowest low until they are k ATRs apart - the earlier of them is the first swing; then the extreme of the current
    leg (an equal price moves it later); price coming back k ATRs (of the bar doing it) from the extreme confirms it."""
    out: list[tuple[int, float, int, int]] = []
    start = next(i for i in range(len(h)) if np.isfinite(atr[i]))
    mode, top, bot, ext = 0, start, start, start
    for i in range(start, len(h)):
        need = k * atr[i]
        if not np.isfinite(need):
            continue
        if mode == 0:
            top = i if h[i] > h[top] else top
            bot = i if lo[i] < lo[bot] else bot
            if h[top] - lo[bot] >= need:
                if bot < top:
                    out.append((bot, lo[bot], -1, i))
                    mode, ext = 1, top
                else:
                    out.append((top, h[top], 1, i))
                    mode, ext = -1, bot
        elif mode == 1:
            if h[i] >= h[ext]:
                ext = i
            elif h[ext] - lo[i] >= need:
                out.append((ext, h[ext], 1, i))
                mode, ext = -1, i
        else:
            if lo[i] <= lo[ext]:
                ext = i
            elif h[i] - lo[ext] >= need:
                out.append((ext, lo[ext], -1, i))
                mode, ext = 1, i
    return out


class Swings:
    """The swings in the order they were confirmed, with their confirmation bars for a binary search."""

    def __init__(self, items: list) -> None:
        self.items = items
        self.conf = [x[3] for x in items]
        assert self.conf == sorted(self.conf) and [x[0] for x in items] == sorted(x[0] for x in items)

    def __getitem__(self, k):
        return self.items[k]


def structure(sw, h: np.ndarray, lo: np.ndarray, close: float, first: int, last: int) -> tuple[int, int]:
    """From the swings confirmed by bar `last` whose bar is in [first, last]: the structure (1 higher tops and higher
    bottoms, -1 lower and lower, 0 mixed, 9 fewer than two of either - the swing still forming counts: after a bottom
    the highest high since it is the newest top, after a top the lowest low) and the close against the last confirmed
    top / bottom (1 above, -1 below, 0 between, 9 without both)."""
    kk = bisect.bisect_right([s[3] for s in sw] if isinstance(sw, list) else sw.conf, last)  # swings confirmed by `last`
    known = sw[:kk] if isinstance(sw, list) else sw.items[:kk]
    j = kk
    while j > 0 and known[j - 1][0] >= first:  # the swing bars rise with their confirmation
        j -= 1
    inside = known[j:]
    tops = [s[1] for s in inside if s[2] == 1]
    bots = [s[1] for s in inside if s[2] == -1]
    brk = 9
    if tops and bots:
        brk = 1 if close > tops[-1] else (-1 if close < bots[-1] else 0)
    if known and known[-1][0] >= first:
        b, _, kind, _ = known[-1]
        if kind == -1:
            tops = tops + [float(h[b:last + 1].max())]
        else:
            bots = bots + [float(lo[b:last + 1].min())]
    if len(tops) < 2 or len(bots) < 2:
        return 9, brk
    up_t, up_b = tops[-1] > tops[-2], bots[-1] > bots[-2]
    return (1 if up_t and up_b else (-1 if not up_t and not up_b else 0)), brk


def way(x: float) -> int:
    return 1 if x >= 1.0 else (-1 if x <= -1.0 else 0)


def read(d: dict, bi: int) -> dict:
    """Every reading of one timeframe's picture: the WINDOW bars ending at bar bi."""
    h, lo, c, atr, sw = d["h"], d["lo"], d["c"], d["atr"], d["sw"]
    a0 = max(bi - WINDOW + 1, 0)
    a = atr[bi]
    hi, lw = h[a0:bi + 1].max(), lo[a0:bi + 1].min()
    pos = (c[bi] - lw) / (hi - lw) if hi > lw else 0.5
    r = dict(size=(hi - lw) / a, pos=pos, edge=1 if pos >= 0.95 else (-1 if pos <= 0.05 else 0), net_way=way((c[bi] - c[a0]) / a))
    fall = (np.maximum.accumulate(h[a0:bi + 1]) - lo[a0:bi + 1]).max() / a  # the deepest drop from a running high
    rise = (h[a0:bi + 1] - np.minimum.accumulate(lo[a0:bi + 1])).max() / a  # the deepest rise from a running low
    r["retr"] = fall if r["net_way"] > 0 else (rise if r["net_way"] < 0 else max(fall, rise))
    steps = np.abs(np.diff(c[a0:bi + 1])).sum()
    r["er"] = abs(c[bi] - c[a0]) / steps if steps > 0 else 0.0
    n = bi - a0 + 1
    for j in range(3):
        s0, s1 = a0 + j * n // 3, a0 + (j + 1) * n // 3 - 1
        r[f"seg{j}"] = way((c[s1] - c[s0]) / a)
    r["struct"], r["brk"] = structure(sw, h, lo, c[bi], a0, bi)
    kk = bisect.bisect_right(sw.conf, bi)
    if kk:
        mv = (c[bi] - sw.items[kk - 1][1]) / a
        r["leg_way"], r["leg"] = int(np.sign(mv)), abs(mv)
    else:
        r["leg_way"], r["leg"] = 0, np.nan
    r["a0"] = a0
    return r


def main() -> None:
    sys.path.insert(0, str(HERE))
    import plib  # noqa: PLC0415 - only the data store (gold.bars through plib.load)

    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    m1 = plib.load()
    P = pd.read_parquet(HERE / "present_3y.parquet")
    pick = np.sort(np.random.default_rng(13).choice(len(P), size=n_sample, replace=False))
    t_ns = pd.DatetimeIndex(P.t_dec.to_numpy()[pick]).as_unit("ns").asi8
    data = {}
    for tf in TFS:
        b = make_bars(m1, tf)
        h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
        atr = mt5_atr(h, lo, c)
        data[tf] = dict(h=h, lo=lo, c=c, atr=atr, done=b.done.to_numpy(), sw=Swings(swings(h, lo, atr, K_SWING)))
        print(tf, "bars", len(b), "swings", len(data[tf]["sw"].items), flush=True)
    fine = dict(data["M1"], sw=Swings(swings(data["M1"]["h"], data["M1"]["lo"], data["M1"]["atr"], K_FINE)))
    keys = ("size", "pos", "edge", "net_way", "retr", "er", "seg0", "seg1", "seg2", "struct", "brk", "leg_way", "leg")
    bad = {}
    for tf in TFS:
        d = data[tf]
        sm = fine if tf == "M1" else data[SMALL[tf]]
        for j, t in enumerate(t_ns):
            bi = int(np.searchsorted(d["done"], t, side="right")) - 1
            r = read(d, bi)
            if r["struct"] == 9 or r["brk"] == 9:  # the zoom: the smaller timeframe's swings over the same span
                first = 0 if r["a0"] == 0 else int(np.searchsorted(sm["done"], d["done"][r["a0"] - 1], side="right"))
                last = int(np.searchsorted(sm["done"], d["done"][bi], side="right")) - 1
                s, b_ = structure(sm["sw"], sm["h"], sm["lo"], d["c"][bi], first, last)
                r["struct"] = s if r["struct"] == 9 else r["struct"]
                r["brk"] = b_ if r["brk"] == 9 else r["brk"]
            for k in keys:
                mine, bots = r[k], P[f"{tf}_{k}"].iloc[pick[j]]
                same = (np.isnan(mine) and np.isnan(bots)) if isinstance(mine, float) and np.isnan(mine) else (
                    abs(float(mine) - float(bots)) <= 1e-9 * max(1.0, abs(float(bots))))
                if not same:
                    bad.setdefault(f"{tf}_{k}", []).append((str(pd.Timestamp(t, tz="UTC")), mine, bots))
        print(tf, "compared", flush=True)
    print(f"\n{n_sample} moments x {len(TFS)} timeframes x {len(keys)} readings: "
          f"{sum(len(v) for v in bad.values())} differences")
    for k, v in bad.items():
        print(k, len(v), v[:3])


if __name__ == "__main__":
    main()
