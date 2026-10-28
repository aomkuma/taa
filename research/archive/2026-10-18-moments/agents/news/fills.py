"""Round 2, task 1: S2 under bad fills (ticks). Every order (entry stop, protective stop, time exit) fills at the
first tick at least LAT seconds after its trigger tick, on effective quotes: the spread is widened to X USD from
the release second to +5 s, then decays linearly to the feed's own spread by +15 s (mid +/- half the spread), so
a wide spread can itself trigger a stop order. Plus 0.07 slippage. D and the exit second H vary; S = 8 (x price /
4000) as frozen.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/fills.py [--test] [--all]

--all: every release with ticks (not only CPI / NFP) - for the latency cost estimate.
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import SLIP, events  # noqa: E402
from straddle import windows  # noqa: E402

TEST = "--test" in sys.argv
ALL = "--all" in sys.argv
T0, T1 = pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-14 08:18", tz="UTC")
S0 = 8.0


def quotes(w: dict, X: float) -> tuple[np.ndarray, np.ndarray]:
    sec, bid, ask = w["sec"], w["bid"], w["ask"]
    wgt = np.where((sec >= 0) & (sec < 5), 1.0, np.where((sec >= 5) & (sec < 15), (15 - sec) / 10, 0.0))
    spr = np.maximum(ask - bid, X * wgt)
    mid = (bid + ask) / 2
    return mid - spr / 2, mid + spr / 2


def after(sec: np.ndarray, j: int, lat: float) -> int:
    """The first tick at least *lat* seconds after tick j (j itself when lat = 0)."""
    if lat <= 0:
        return j
    k = int(np.searchsorted(sec, sec[j] + lat))
    return min(k, len(sec) - 1)


def sim(w: dict, D: float, H: float, lat: float, X: float) -> dict | None:
    sec, k0 = w["sec"], w["ref"]
    bid, ask = quotes(w, X)
    k = w["bid"][k0] / 4000
    D, S = D * k, S0 * k
    up, dn = w["ask"][k0] + D, w["bid"][k0] - D
    live = (sec >= 0) & (sec < 60)
    iu, idn = np.flatnonzero(live & (ask >= up)), np.flatnonzero(live & (bid <= dn))
    ju, jd = (iu[0] if len(iu) else 10**9), (idn[0] if len(idn) else 10**9)
    if ju == jd == 10**9:
        return None
    side, j = (1, ju) if ju < jd else (-1, jd)
    f = after(sec, j, lat)
    entry = ask[f] + SLIP if side > 0 else bid[f] - SLIP
    stop = entry - side * S
    rest = np.arange(f + 1, len(sec))
    adv = bid[rest] if side > 0 else ask[rest]
    hit = np.flatnonzero(((adv - stop) * side <= 0) & (sec[rest] < H))
    if len(hit):
        q = after(sec, rest[hit[0]], lat)
        ex, how = (bid[q] - SLIP if side > 0 else ask[q] + SLIP), "stop"
    else:
        q = int(np.searchsorted(sec, H + lat))
        q = min(q, len(sec) - 1)
        ex, how = (bid[q] - SLIP if side > 0 else ask[q] + SLIP), "time"
    usd = (ex - entry) * side
    return dict(t=w["t"], main=w["main"], side=side, trig_s=sec[j], fill_s=sec[f],
                slip_entry=(entry - (up if side > 0 else dn)) * side, how=how, usd=usd, R=usd / (S + SLIP))


GRID = dict(D=(1.0, 2.0, 3.0, 5.0), H=(30.0, 60.0, 120.0, 300.0), lat=(0.0, 0.3, 0.7, 1.5), X=(0.0, 1.0, 2.0, 4.0))


def main() -> None:
    ev = events(extra=True)
    if not ALL:
        ev = ev[ev.main.isin(["CPI", "NFP"])]
    ev = ev[(ev.t >= T0) & (ev.t < T1)] if TEST else ev[(ev.t >= pd.Timestamp("2025-10-01", tz="UTC")) & (ev.t < T0)]
    W = windows(ev)
    rows = []
    for D, H, lat, X in itertools.product(*GRID.values()):
        for w in W:
            r = sim(w, D, H, lat, X)
            if r:
                rows.append(dict(D=D, H=H, lat=lat, X=X, **r))
    d = pd.DataFrame(rows)
    tag = ("test" if TEST else "design") + ("_all" if ALL else "")
    d.to_parquet(f"research/2026-10-18-moments/agents/news/fills_{tag}.parquet")
    pd.set_option("display.width", 220)
    print(len(W), "windows")
    for (D, H), x in d.groupby(["D", "H"]):
        if H not in (60.0, 300.0):
            continue
        t = x.groupby(["lat", "X"]).R.mean().unstack("X").round(2)
        print(f"\nD {D:g}, exit +{H:g} s: R/trade by latency (rows) x spread X USD (cols)")
        print(t.to_string())


if __name__ == "__main__":
    main()
