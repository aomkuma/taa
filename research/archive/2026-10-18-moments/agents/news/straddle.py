"""News agent, the first-impulse straddle on ticks: at the release second, a buy stop D above the last ask and a
sell stop D below the last bid (one cancels the other), valid W seconds; then a target T, a stop S (USD from the
fill) and a time exit H seconds after the fill. Fills on ticks: an entry or a stop fills at the first tick beyond
its level at that tick's price (gaps included) +/- slippage; a target fills at its level.

Design: releases 2025-10-01 .. 2026-02-28 (ticks). Test (--test): 2026-03-01 .. 2026-10-14.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/straddle.py [--test] [--slip X]
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from lab import events  # noqa: E402

TEST = "--test" in sys.argv
SLIP = float(sys.argv[sys.argv.index("--slip") + 1]) if "--slip" in sys.argv else 0.07
T0, T1 = pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-14 08:18", tz="UTC")
TICKS = Path("data/ticks/XAUUSD")


def windows(ev: pd.DataFrame) -> list:
    out = []
    for r in ev.itertuples():
        f = TICKS / f"{r.t.strftime('%Y-%m-%d')}.parquet"
        if not f.exists():
            continue
        t = pd.read_parquet(f)
        ns = pd.to_datetime(t.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
        a, b = np.searchsorted(ns, [r.t.value - 5 * 10**9, r.t.value + 900 * 10**9])
        pre = np.searchsorted(ns, r.t.value) - 1
        if pre < a or b - pre < 50:
            continue
        sec = (ns[a:b] - r.t.value) / 1e9
        out.append(dict(t=r.t, main=r.main, all=r.all, sec=sec, bid=t.bid.to_numpy()[a:b], ask=t.ask.to_numpy()[a:b],
                        ref=pre - a))
    return out


def sim(w: dict, D: float, W: float, T: float, S: float, H: float, flip: bool = False) -> dict | None:
    sec, bid, ask, k0 = w["sec"], w["bid"], w["ask"], w["ref"]
    up, dn = ask[k0] + D, bid[k0] - D
    live = (sec >= 0) & (sec <= W)
    iu = np.flatnonzero(live & (ask >= up))
    idn = np.flatnonzero(live & (bid <= dn))
    ju = iu[0] if len(iu) else 10**9
    jd = idn[0] if len(idn) else 10**9
    if ju == jd == 10**9:
        return None
    side, j = (1, ju) if ju < jd else (-1, jd)
    if flip:  # the opposite side at the same tick (the coin's other half)
        side = -side
    entry = ask[j] + SLIP if side > 0 else bid[j] - SLIP
    rest = slice(j + 1, None)
    s2, b2, a2 = sec[rest], bid[rest], ask[rest]
    inn = s2 <= sec[j] + H
    if side > 0:
        hs = np.flatnonzero(inn & (b2 <= entry - S))
        ht = np.flatnonzero(inn & (b2 >= entry + T))
    else:
        hs = np.flatnonzero(inn & (a2 >= entry + S))
        ht = np.flatnonzero(inn & (a2 <= entry - T))
    js = hs[0] if len(hs) else 10**9
    jt = ht[0] if len(ht) else 10**9
    if js < jt:
        px = (b2[js] - SLIP) if side > 0 else (a2[js] + SLIP)
        ex = "stop"
    elif jt < 10**9:
        px = entry + side * T
        ex = "win"
    else:
        last = np.flatnonzero(inn)
        if not len(last):
            return None
        q = last[-1]
        px = (b2[q] - SLIP) if side > 0 else (a2[q] + SLIP)
        ex = "time"
    usd = (px - entry) * side
    # the losers' kind (stopped): did price reach the target from the entry within 120 min? (ticks to 15 min only)
    kind = ""
    if ex == "stop":
        fav = (b2 - entry) if side > 0 else (entry - a2)
        before = fav[: js + 1].max() if js + 1 > 0 else 0
        later = fav[js + 1 :]
        kind = "3" if len(later) and later.max() >= T else ("2" if before >= 0.5 * T else "1")
    return dict(t=w["t"], main=w["main"], side=side, fill_s=sec[j], gap=(entry - (up if side > 0 else dn)) * side,
                exit=ex, usd=usd, R=usd / (S + SLIP), kind=kind)


GRID = dict(D=(1.0, 2.0, 3.0, 5.0), W=(10.0, 60.0), T=(3.0, 5.0, 8.0, 12.0), S=(3.0, 5.0, 8.0), H=(30.0, 60.0, 180.0, 600.0))


def main() -> None:
    gold.below_normal_priority()
    ev = events(extra=True)
    ev = ev[(ev.t >= pd.Timestamp("2025-10-01", tz="UTC")) & (ev.t < (T1 if TEST else T0))]
    if TEST:
        ev = ev[ev.t >= T0]
    W_ = windows(ev)
    print(len(W_), "release windows with ticks;", pd.Series([w["main"] for w in W_]).value_counts().to_dict())
    rows = []
    for D, W, T, S, H in itertools.product(*GRID.values()):
        for w in W_:
            for flip in (False, True):
                r = sim(w, D, W, T, S, H, flip)
                if r:
                    rows.append(dict(D=D, W=W, T=T, S=S, H=H, flip=flip, **r))
    d = pd.DataFrame(rows)
    d.to_parquet(f"research/2026-10-18-moments/agents/news/straddle_{'test' if TEST else 'design'}.parquet")
    x = d[~d.flip]
    g = x.groupby(["D", "W", "T", "S", "H"]).agg(n=("usd", "size"), win=("exit", lambda v: (v == "win").mean()),
                                                usd=("usd", "mean"), R=("R", "mean"), gap=("gap", "mean"))
    o = d[d.flip].groupby(["D", "W", "T", "S", "H"]).R.mean()
    g["coinR"] = (g.R + o) / 2
    pd.set_option("display.width", 220)
    print(g.sort_values("R", ascending=False).head(30).round(3).to_string())
    print("\nshare of plans with R > 0:", round((g.R > 0).mean(), 2), " mean R over plans:", round(g.R.mean(), 3))


if __name__ == "__main__":
    main()
