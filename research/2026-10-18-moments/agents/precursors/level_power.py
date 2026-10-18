"""Which kinds of level turn gold's price (2026-10-18; notes.md "Which kinds of level turn price"): every first touch
of a level inside the owner's windows before the exam, and what came first afterwards - back 1 M15 ATR from the
level (it turned price) or 1 M15 ATR through it. A line with no effect gives 50 %; the control is a grid of
"round" numbers shifted by 13 USD.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/level_power.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import foundation as F  # noqa: E402
import plib  # noqa: E402

HORIZON = 120  # minutes to resolve
COOL = 60  # a level counts again only after 60 minutes without a touch
START = pd.Timestamp("2023-09-01", tz="UTC")


def first_passage(h: np.ndarray, lo: np.ndarray, j: int, up_lv: float, dn_lv: float, n: int) -> int:
    """From bar j + 1 on: +1 when a high reaches up_lv first, -1 when a low reaches dn_lv first, 0 both in one bar or
    neither within n bars."""
    for k in range(j + 1, min(j + 1 + n, len(h))):
        u, d = h[k] >= up_lv, lo[k] <= dn_lv
        if u and d:
            return 0
        if u:
            return 1
        if d:
            return -1
    return 0


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.load()
    m = m[(m.index >= START - pd.Timedelta(days=10)) & (m.index < plib.EXAM_START)]
    t = m.index
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    # everything a touch at bar j is measured against is known before bar j opens (bars complete by its open)
    t_ns = t.as_unit("ns").asi8
    # the M15 ATR known at each minute (the last closed M15 bar)
    b15 = plib.tf_bars(m, "15min")
    a15 = F.atr(b15.high.to_numpy(float), b15.low.to_numpy(float), b15.close.to_numpy(float), 14)
    k15 = np.searchsorted(pd.DatetimeIndex(b15["avail"]).as_unit("ns").asi8, t_ns, side="right") - 1
    atr = np.where(k15 >= 0, a15[np.maximum(k15, 0)], np.nan)
    # the server day (Athens) for day levels; the Asian session = 00:00-07:00 UTC of that server day
    sday = t.tz_convert("Europe/Athens").normalize().tz_localize(None).to_numpy()
    days, di = np.unique(sday, return_inverse=True)
    dh = pd.Series(h).groupby(di).max().to_numpy()
    dl = pd.Series(lo).groupby(di).min().to_numpy()
    yday_hi = np.where(di >= 1, dh[np.maximum(di - 1, 0)], np.nan)
    yday_lo = np.where(di >= 1, dl[np.maximum(di - 1, 0)], np.nan)
    # today so far (before this bar)
    run_hi = pd.Series(h).groupby(di).cummax().shift(1).to_numpy().copy()
    run_lo = pd.Series(lo).groupby(di).cummin().shift(1).to_numpy().copy()
    first = np.r_[True, di[1:] != di[:-1]]
    run_hi[first], run_lo[first] = np.nan, np.nan
    hour = t.hour.to_numpy()
    asia = hour < 7
    ah = pd.Series(np.where(asia, h, np.nan)).groupby(di).max().to_numpy()
    al = pd.Series(np.where(asia, lo, np.nan)).groupby(di).min().to_numpy()
    # known from 07:00 UTC until the server day ends (21:00 / 22:00 UTC): the bars after that belong to the next
    # server day, whose Asian session has not happened yet (look-ahead fixed 2026-10-19)
    done = (hour >= 7) & (hour < 21)
    asia_hi = np.where(done, ah[di], np.nan)
    asia_lo = np.where(done, al[di], np.nan)
    # 72 hours, ending an hour before the bar (as F1's extreme)
    s_h, s_l = pd.Series(h, index=t), pd.Series(lo, index=t)
    h72 = s_h.rolling("72h").max().shift(60).to_numpy()
    l72 = s_l.rolling("72h").min().shift(60).to_numpy()
    # fractal swings of H1 and M15 (2 bars each side), known 2 bars later, the last 120 bars
    swing_sets = {}
    for tf, rule in (("H1", "1h"), ("M15", "15min")):
        b = plib.tf_bars(m, rule)
        bh, bl = b.high.to_numpy(float), b.low.to_numpy(float)
        ph, pl = F.fractals(bh, bl, 2)
        av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        kb = np.searchsorted(av, t_ns, side="right") - 1
        swing_sets[tf] = (ph, pl, bh, bl, kb)
    win = plib.window_mask(t).any(axis=1).to_numpy() & np.asarray(t >= START)
    pc = np.r_[np.nan, c[:-1]]

    def nearest(prices: np.ndarray, x: float) -> tuple[float, float]:
        above = prices[prices > x]
        below = prices[prices < x]
        return (above.min() if len(above) else np.nan), (below.max() if len(below) else np.nan)

    events = []
    last_touch: dict[tuple[str, float], int] = {}
    for j in np.nonzero(win)[0]:
        a = atr[j]
        x = pc[j]
        if not (np.isfinite(a) and a > 0 and np.isfinite(x)):
            continue
        cand = {
            "yesterday hi/lo": (yday_hi[j], yday_lo[j]),
            "today hi/lo so far": (run_hi[j], run_lo[j]),
            "Asia hi/lo": (asia_hi[j], asia_lo[j]),
            "72-hour hi/lo": (h72[j], l72[j]),
            "round 50": (np.ceil(x / 50) * 50, np.floor(x / 50) * 50),
            "grid 50 shifted 13 (control)": (np.ceil((x - 13) / 50) * 50 + 13, np.floor((x - 13) / 50) * 50 + 13),
        }
        for tf, (ph, pl, bh, bl, kb) in swing_sets.items():
            k = kb[j]
            if k < 5:
                continue
            ok_h = ph[(ph <= k - 2) & (ph >= k - 120)]
            ok_l = pl[(pl <= k - 2) & (pl >= k - 120)]
            prices = np.r_[bh[ok_h], bl[ok_l]]
            cand[f"{tf} swings"] = nearest(prices, x) if len(prices) else (np.nan, np.nan)
        for kind, (res, sup) in cand.items():
            for lv, side in ((res, 1), (sup, -1)):  # side +1: a level above, touched from below
                if not np.isfinite(lv):
                    continue
                touched = (h[j] >= lv > x) if side > 0 else (lo[j] <= lv < x)
                if not touched:
                    continue
                key = (kind, round(lv, 2))
                if j - last_touch.get(key, -10**9) < COOL:
                    last_touch[key] = j
                    continue
                last_touch[key] = j
                fp = first_passage(h, lo, j, lv + a, lv - a, HORIZON)
                if fp == 0:
                    continue
                turned = (fp == -1) if side > 0 else (fp == 1)
                # the no-effect baseline from where price stood when the measuring starts (the touch bar's close):
                # a driftless walk between lv - a and lv + a reaches the turn side first with this chance
                x0 = min(max(c[j], lv - a), lv + a)
                base = (lv + a - x0) / (2 * a) if side > 0 else (x0 - (lv - a)) / (2 * a)
                events.append((kind, side, t[j], turned, base))
    E = pd.DataFrame(events, columns=["kind", "side", "t", "turned", "base"])
    E["part"] = np.where(E.t < pd.Timestamp("2025-01-01", tz="UTC"), "2023-09..2024-12", "2025-01..2026-04-17")
    E.to_parquet(HERE / "level_power.parquet")
    g = E.groupby(["kind", "part"]).agg(n=("turned", "size"), turned=("turned", "mean"), no_effect=("base", "mean"))
    g["se"] = np.sqrt(g.turned * (1 - g.turned) / g.n)
    g["edge"] = g.turned - g.no_effect
    g["edge_in_se"] = g.edge / g.se
    pd.set_option("display.width", 200)
    print("first touches inside the owner's windows, before the exam: back 1 M15 ATR first (turned) vs 1 ATR through;")
    print("no_effect = a driftless walk from the touch bar's close between the two")
    print(g.round(3).to_string())


if __name__ == "__main__":
    main()
