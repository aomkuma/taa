"""Charts of real V7b design trades (M5 candles 07:00-15:00 ET): the 08:00 window start, the 08:30 release, the
10:00 decision, entry, stop, exit. Run with the research venv (matplotlib):

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/fx/charts.py FILE N
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402

OUT = Path("research/2026-10-18-moments/agents/fx/charts")


def draw(ax, P: fx.Pair, tr) -> None:
    t_dec = tr.t  # entry bar open time (decision + 1 min)
    day_ny = t_dec.tz_convert(fx.NYC).normalize()
    a = (day_ny + pd.Timedelta(hours=7)).tz_convert("UTC")
    b = (day_ny + pd.Timedelta(hours=15)).tz_convert("UTC")
    i0, i1 = P.ot.searchsorted(a), P.ot.searchsorted(b)
    df = pd.DataFrame({"o": P.o[i0:i1], "h": P.h[i0:i1], "l": P.lo[i0:i1], "c": P.c[i0:i1]}, index=P.ot[i0:i1])
    m5 = df.resample("5min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    x = m5.index.tz_convert(fx.NYC)
    xs = np.arange(len(m5))
    up = m5.c >= m5.o
    ax.vlines(xs, m5.l, m5.h, color="0.35", lw=0.6)
    ax.bar(xs[up], (m5.c - m5.o)[up], bottom=m5.o[up], color="#2a9d8f", width=0.7)
    ax.bar(xs[~up], (m5.o - m5.c)[~up], bottom=m5.c[~up], color="#e76f51", width=0.7)

    def xpos(ts):
        return np.searchsorted(m5.index, ts.floor("5min"))

    for hh, lab in ((8, "08:00"), (8.5, "08:30 rel"), (10, "10:00"), (14, "14:00")):
        ts = (day_ny + pd.Timedelta(hours=hh)).tz_convert("UTC")
        ax.axvline(xpos(ts), color="0.6", ls=":", lw=0.8)
        ax.text(xpos(ts), m5.h.max(), lab, fontsize=6, color="0.4")
    ent = tr.entry
    stop = ent - tr.side * tr.sl
    ax.axhline(ent, color="#264653", lw=0.8)
    ax.axhline(stop, color="#e63946", lw=0.8, ls="--")
    xi = P.ot[int(tr.xi)]
    ax.plot([xpos(tr.t)], [ent], marker="^" if tr.side > 0 else "v", color="k", ms=6)
    ax.plot([xpos(xi)], [ent + tr.side * tr.pips], marker="x", color="k", ms=6)
    ax.set_xticks(xs[::12])
    ax.set_xticklabels([v.strftime("%H:%M") for v in x[::12]], fontsize=6)
    ax.tick_params(axis="y", labelsize=6)
    ax.set_title(f"{tr.pair} {t_dec.tz_convert(fx.NYC):%Y-%m-%d} {'BUY' if tr.side > 0 else 'SELL'} "
                 f"{tr.exit} {tr.pips:+.1f}p R {tr.R:+.2f} {tr.get('etype', '')}", fontsize=7)


def main() -> None:
    f, n = sys.argv[1], int(sys.argv[2])
    tag = Path(f).stem
    z = pd.read_parquet(f)
    z["t"] = pd.to_datetime(z.t, utc=True)
    rng = np.random.default_rng(5)
    los = z[z.exit == "stop"]
    win = z[z.R > 0.5]
    pick = pd.concat([los.iloc[rng.choice(len(los), min(n, len(los)), replace=False)],
                      win.iloc[rng.choice(len(win), min(n, len(win)), replace=False)]])
    OUT.mkdir(parents=True, exist_ok=True)
    cache = {}
    for kind, grp in (("losers", pick[pick.exit == "stop"]), ("winners", pick[pick.R > 0.5])):
        fig, axes = plt.subplots(int(np.ceil(len(grp) / 2)), 2, figsize=(11, 2.6 * np.ceil(len(grp) / 2)))
        for ax, tr in zip(np.ravel(axes), grp.itertuples()):
            if tr.pair not in cache:
                cache[tr.pair] = fx.Pair(tr.pair)
            draw(ax, cache[tr.pair], pd.Series(tr._asdict()))
        fig.tight_layout()
        fig.savefig(OUT / f"{tag}_{kind}.png", dpi=110)
        plt.close(fig)
        print("saved", OUT / f"{tag}_{kind}.png")


if __name__ == "__main__":
    main()
