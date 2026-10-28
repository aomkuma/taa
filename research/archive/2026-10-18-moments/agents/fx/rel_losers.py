"""Step 4: why do the V3 losers lose (design halves only)? Features at the decision, splits of net R, the coin side
on the same events with the same stop distance.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/rel_losers.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
sys.path.insert(0, "research/2026-10-18-moments")
import fxlib as fx  # noqa: E402
import gold  # noqa: E402
import lab  # noqa: E402
import reltrades as rt  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
rel = gold.releases()
r830 = rel[rel.time_et == "08:30"].copy()
r830["day"] = pd.to_datetime(r830.date)
ETYPE = r830.groupby("day").event.agg(lambda s: "+".join(sorted(s)))


def features(P: fx.Pair, ev: pd.DataFrame) -> pd.DataFrame:
    ctx = lab.context(P)
    i0 = lab.local_index(P, fx.NYC, 8).reindex(ev.day).to_numpy()  # bar closing 08:00 ET
    i930 = lab.local_index(P, fx.NYC, 9.5).reindex(ev.day).to_numpy()
    i945 = lab.local_index(P, fx.NYC, 9.75).reindex(ev.day).to_numpy()
    out = pd.DataFrame(index=ev.index)
    ok = np.isfinite(i0)
    i0 = np.where(ok, i0, 0).astype(int)
    s = np.sign(ev.move.to_numpy())  # the move's direction
    # H1 trend as of 08:00 ET (before the move): sign of close - EMA50 if the EMA20 slope agrees, else 0
    c, e50, sl20 = ctx.h1_c.to_numpy()[i0], ctx.h1_ema50.to_numpy()[i0], ctx.h1_slope.to_numpy()[i0]
    tr = np.sign(c - e50) * (np.sign(sl20) == np.sign(c - e50))
    out["move_with_trend"] = (tr * s).astype(int)  # +1: the move went with the prior H1 trend
    atr = ev.h1_atr.to_numpy()
    out["q"] = np.abs(ev.move.to_numpy()) / atr
    # did the move break the previous NY day's high (up) / low (down)?
    out["broke_pd"] = np.where(s > 0, ev.whi.to_numpy() > ev.pdh.to_numpy(), ev.wlo.to_numpy() < ev.pdl.to_numpy())
    # the last 30 / 15 minutes into the decision, in the move's direction (ATR)
    i930 = np.where(np.isfinite(i930), i930, 0).astype(int)
    i945 = np.where(np.isfinite(i945), i945, 0).astype(int)
    out["last30"] = s * (ev.px.to_numpy() - P.c[i930]) / atr
    out["last15"] = s * (ev.px.to_numpy() - P.c[i945]) / atr
    # where the decision close sits in the 08-10 range, from the move's start (0) to its extreme (1)
    rng = (ev.whi - ev.wlo).to_numpy()
    out["pos_in_range"] = np.where(s > 0, (ev.px.to_numpy() - ev.wlo.to_numpy()) / rng,
                                   (ev.whi.to_numpy() - ev.px.to_numpy()) / rng)
    out["pullback"] = 1 - out.pos_in_range  # 0 = at the extreme
    out["etype"] = ev.day.map(ETYPE).fillna("none").to_numpy()
    out["wd"] = pd.DatetimeIndex(ev.day).dayofweek
    # the prior day's trend: the move vs (prev close - the close of 2 days ago) not available; use pdc vs dop
    out["move_vs_overnight"] = s * np.sign(ev.px.to_numpy() - ev.pdc.to_numpy())
    return out


def main() -> None:
    v = rt.VARIANTS["V3 + stop beyond the 08-10 extreme +0.5ATR"]
    rows = []
    rng = np.random.default_rng(7)
    for p in fx.PAIRS:
        Pn = fx.Pair(p)
        ev = rt.build(Pn, v["dec"], v["exit"])
        ev = ev[ev.half.isin(H) & ev.rel].reset_index(drop=True)
        q = (ev.move.abs() / ev.h1_atr).to_numpy()
        side = -np.sign(ev.move.to_numpy()).astype(int)
        side[q < 1] = 0
        atr = ev.h1_atr.to_numpy()
        ext = np.where(side < 0, ev.whi.to_numpy(), ev.wlo.to_numpy())
        sl = np.maximum(np.abs(ext - ev.px.to_numpy()) + 0.5 * atr, atr)
        z = lab.simulate(Pn, ev, side, sl, None)
        coin_side = np.where(side != 0, rng.choice([-1, 1], len(side)), 0)
        zc = lab.simulate(Pn, ev, coin_side, sl, None)
        zcont = lab.simulate(Pn, ev, -side, sl, None)
        ft = features(Pn, ev)
        z = z.join(ft, on="ev")
        z["coinR"] = zc.set_index("ev").R.reindex(z.ev).to_numpy()
        z["coin_kind"] = zc.set_index("ev").kind.reindex(z.ev).to_numpy()
        z["coin_exit"] = zc.set_index("ev").exit.reindex(z.ev).to_numpy()
        z["contR"] = zcont.set_index("ev").R.reindex(z.ev).to_numpy()
        z["pair"] = p
        z["day"] = ev.day.to_numpy()[z.ev]
        rows.append(z)
    z = pd.concat(rows, ignore_index=True)
    z.to_parquet("research/2026-10-18-moments/agents/fx/v3_design_trades.parquet")
    print(f"V3 design: n={len(z)} net R {z.R.mean():+.3f}, coin {z.coinR.mean():+.3f}, the opposite side {z.contR.mean():+.3f}")
    print("exits:", z.exit.value_counts().to_dict(), " coin exits:", z.coin_exit.value_counts().to_dict())
    st = z[z.exit == "stop"]
    print("stopped:", len(st), "kinds", fx.kinds(z), " coin kinds", fx.kinds(z.assign(exit=z.coin_exit, kind=z.coin_kind)))
    print(f"losers (R<0): {(z.R < 0).sum()}, of which stops {len(st)}, time exits below 0 {((z.exit == 'time') & (z.R < 0)).sum()}")
    print("mins to the stop: median", st.mins.median(), " quartiles", st.mins.quantile([.25, .75]).tolist())

    def split(col, bins=None):
        x = z.copy()
        if bins is not None:
            x[col] = pd.cut(x[col], bins)
        g = x.groupby(col, observed=True).agg(n=("R", "size"), R=("R", "mean"), coin=("coinR", "mean"),
                                               win=("pips", lambda s: 100 * (s > 0).mean()),
                                               stop_share=("exit", lambda s: 100 * (s == "stop").mean()))
        gh = x.groupby([col, "half"], observed=True).R.mean().unstack()
        print(f"\n-- by {col}")
        print(pd.concat([g, gh], axis=1).round(3).to_string())

    split("move_with_trend")
    split("q", [1, 1.5, 2, 3, 5, 99])
    split("broke_pd")
    split("last30", [-9, -0.25, 0, 0.25, 0.5, 9])
    split("last15", [-9, -0.1, 0.1, 0.3, 9])
    split("pullback", [-0.01, 0.1, 0.25, 0.5, 1.01])
    split("move_vs_overnight")
    split("wd")
    x = z.copy()
    x["et"] = x.etype.str.replace("+", "/")
    for e in ("CPI", "NFP", "PPI", "PCE", "GDP"):
        y = x[x.et.str.contains(e)]
        print(f"  {e}: n={len(y)} R {y.R.mean():+.3f} coin {y.coinR.mean():+.3f}")


if __name__ == "__main__":
    main()
