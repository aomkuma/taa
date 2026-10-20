"""The owner's framework, step 2 (notes.md, written before it is computed): at each window's open (Asia 07:00 Thai,
London 13:00 Thai, NY 09:30 NY), with the D1 side (three readings) and the M15 / H1 trend (a proxy until the second
developer's structure reader: the close against a rising / falling EMA50) known then - does price reach 10 USD the
trend's way before X USD against (a small-TF stop), within the window's span, more often when they agree?

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/framework2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402

EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
STOPS = (3.0, 5.0, 7.0, 10.0)
TARGET = 10.0


def trend_sign(close: np.ndarray, n: int = 50, slope: int = 5) -> np.ndarray:
    """+1: close above a rising EMA(n); -1: below a falling one; 0 otherwise (per bar, known at its close)."""
    e = np.array(F.ema(np.asarray(close, float), n), float)
    e[: n - 1] = np.nan
    rise = e - pd.Series(e).shift(slope).to_numpy()
    return np.where((close > e) & (rise > 0), 1, np.where((close < e) & (rise < 0), -1, 0))


def first_passage(o0: float, h: np.ndarray, lo: np.ndarray, side: int, target: float, stop: float) -> int:
    """From o0 over bars h / lo: +1 when `target` our way comes first, -1 when `stop` against comes first (a bar
    reaching both counts against - its order is unknown), 0 when neither."""
    fav = (h - o0) if side > 0 else (o0 - lo)
    adv = (o0 - lo) if side > 0 else (h - o0)
    for f, a in zip(fav, adv):
        if a >= stop:
            return -1
        if f >= target:
            return 1
    return 0


def main() -> None:
    import plib  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415
    from m15_trades import part_of  # noqa: PLC0415

    m = plib.load_learning(start=pd.Timestamp("2025-06-01", tz="UTC"))  # ends before EXAM_START; no exam row read
    tf = {}
    for rule in ("15min", "1h", "1D"):
        b = bars(m, rule)
        tf[rule] = (b, pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8)
    s15 = trend_sign(tf["15min"][0].close.to_numpy(float))
    s1h = trend_sign(tf["1h"][0].close.to_numpy(float))
    d1b, d1a = tf["1D"]
    dc, do = d1b.close.to_numpy(float), d1b.open.to_numpy(float)
    reads = {"ema20": trend_sign(dc, 20, 5), "candle": np.sign(dc - do).astype(int),
             "3day": np.sign(dc - pd.Series(dc).shift(3).to_numpy()).astype(int)}
    h, lo, op = (m[x].to_numpy(float) for x in ("high", "low", "open"))
    rows = []
    for name, zone, hh, mm, span in (("Asia 07:00 Thai", "Asia/Bangkok", 7, 0, 60), ("London 13:00 Thai", "Asia/Bangkok", 13, 0, 60),
                                     ("NY 09:30 NY", "America/New_York", 9, 30, 240)):
        for day in sorted({t.normalize() for t in m.index.tz_convert(zone)}):
            t0 = pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=hh, minute=mm, tz=zone).tz_convert("UTC")
            if t0.dayofweek >= 5:
                continue
            a = int(np.searchsorted(m.index, t0))
            e = int(np.searchsorted(m.index, t0 + pd.Timedelta(minutes=span)))
            if e - a < span * 0.8 or a == 0:
                continue
            t_ns = np.array([t0.value])
            k15, k1, kd = (int(at(tf[r][1], t_ns)[0]) for r in ("15min", "1h", "1D"))
            if min(k15, k1, kd) < 0:
                continue
            m15, m1h = int(s15[k15]), int(s1h[k1])
            rec = dict(window=name, t=t0, m15=m15, h1=m1h)
            for rn, rv in reads.items():
                rec[rn] = int(rv[kd])
            side = m1h if m1h != 0 and m15 == m1h else 0   # the M15-H1 trend (both agree), else none
            rec["side"] = side
            if side != 0:
                o0 = float(op[a])
                for X in STOPS:
                    rec[f"x{int(X)}"] = first_passage(o0, h[a:e], lo[a:e], side, TARGET, X)
                rec["mfe"] = float((h[a:e].max() - o0) if side > 0 else (o0 - lo[a:e].min()))
                rec["mae"] = float((o0 - lo[a:e].min()) if side > 0 else (h[a:e].max() - o0))
            rows.append(rec)
    D = pd.DataFrame(rows)
    D["part"] = part_of(pd.DatetimeIndex(D.t))
    D = D[D.part.isin(["P1", "P2"]) & (D.side != 0)]
    D.to_parquet(HERE / "framework2.parquet")
    pd.set_option("display.width", 220)
    for rn in reads:
        print(f"\n== the D1 reading '{rn}': the M15-H1 trend days, split by the D1 side agreeing / against / none")
        D["d1"] = np.where(D[rn] == D.side, "agree", np.where(D[rn] == -D.side, "against", "none"))
        out = []
        for (w, p, d1), G in D.groupby(["window", "part", "d1"]):
            r = dict(window=w, part=p, d1=d1, n=len(G))
            for X in STOPS:
                v = G[f"x{int(X)}"]
                r[f"+10 before -{int(X)}"] = f"{(v > 0).mean():.2f}/{(v < 0).mean():.2f}"
            r["mfe / mae med"] = f"{G.mfe.median():.1f} / {G.mae.median():.1f}"
            out.append(r)
        print(pd.DataFrame(out).to_string(index=False))


if __name__ == "__main__":
    main()
