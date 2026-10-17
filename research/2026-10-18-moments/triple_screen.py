"""Round 5 (docs/OWN_SETUP.md): the triple screen with H1 at most. Screen 1 the H1 trend, screen 2 a pullback
against it (M15 RSI or the last hour's range), screen 3 the entry timing (M1 bar or ticks). Variants chosen on
2025-10-14 .. 2026-04-14, tested once on 2026-04-14 .. 10-14.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/triple_screen.py
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

TOOLS = [(5, 4), (5, 6), (8, 6), (10, 8)]
DEV, TEST, END = "2025-10-14", "2026-04-14", "2026-10-14"


def load() -> pd.DataFrame:
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    lab = pd.read_parquet("data/research/own_ml_arsenal_labels.parquet")
    d = pd.concat([d, lab.drop(columns=["t", "e", "side"])], axis=1)
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[d.t >= pd.Timestamp(DEV, tz="UTC")]
    tk = pd.read_parquet("data/research/own_ml_ticks.parquet")
    tk["t"] = pd.to_datetime(tk.t, utc=True)
    d = d.merge(tk, on="t", how="left")
    s = d.side.to_numpy()
    for col in ("tk_ret5", "tk_ret15", "tk_ret30", "tk_ret60", "tk_imb60"):
        d[col] = d[col] * s  # signed by the side, as the M1 features already are
    return d


SCREEN1 = {
    "A": lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0),
    "B": lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.h1_c_e20 > 0),
}
SCREEN2 = {
    "none": lambda d: pd.Series(True, index=d.index),
    "rsi40": lambda d: d.m15_rsi < 40,
    "rsi45": lambda d: d.m15_rsi < 45,
    "rsi50": lambda d: d.m15_rsi < 50,
    "pos30": lambda d: d.pos60 < 0.3,
    "pos50": lambda d: d.pos60 < 0.5,
}
SCREEN3 = {
    "none": lambda d: pd.Series(True, index=d.index),
    "bar": lambda d: d.ret1 > 0,
    "ticks": lambda d: (d.tk_ret15 > 0) & (d.tk_imb60 > 0),
    "bars3": lambda d: d.ret3 > 0,
}


def run(x: pd.DataFrame, tool: tuple[int, int], cap: int = 2) -> pd.DataFrame:
    t_, sl = tool
    x = x[x[f"y_{t_}_{sl}"] >= 0].sort_values("t").drop_duplicates("t")
    keep, free, count = [], pd.Timestamp(0, tz="UTC"), {}
    for t, s, mins in zip(x.t, x.session, x[f"min_{t_}_{sl}"], strict=True):
        key = (t.normalize(), s)
        ok = t >= free and count.get(key, 0) < cap
        keep.append(ok)
        if ok:
            free, count[key] = t + pd.Timedelta(minutes=int(mins)), count.get(key, 0) + 1
    out = x[np.array(keep, dtype=bool)].copy()
    out["usd"], out["win"] = out[f"usd_{t_}_{sl}"], out[f"y_{t_}_{sl}"] == 1
    return out


def summary(r: pd.DataFrame, days: int) -> str:
    if len(r) == 0:
        return "0 trades"
    by_m = r.usd.groupby(r.t.dt.strftime("%Y-%m")).sum()
    return (f"{len(r):4} trades ({len(r) / days:.2f}/day) win {100 * r.win.mean():3.0f}%  {r.usd.mean():+.2f} USD/trade"
            f"  {r.usd.sum():+8.1f} USD  months+ {(by_m > 0).sum()}/{len(by_m)}")


def main() -> None:
    d = load()
    dev = d[d.t < pd.Timestamp(TEST, tz="UTC")]
    test = d[(d.t >= pd.Timestamp(TEST, tz="UTC")) & (d.t < pd.Timestamp(END, tz="UTC"))]
    dd, td = dev.t.dt.normalize().nunique(), test.t.dt.normalize().nunique()
    res = []
    for (a, f1), (b, f2), (c, f3), tool in itertools.product(SCREEN1.items(), SCREEN2.items(), SCREEN3.items(), TOOLS):
        r = run(dev[f1(dev) & f2(dev) & f3(dev)], tool)
        res.append(dict(s1=a, s2=b, s3=c, tool=tool, n=len(r), per_day=len(r) / dd, usd=r.usd.sum(),
                        usd_tr=r.usd.mean() if len(r) else np.nan, win=r.win.mean() if len(r) else np.nan))
    R = pd.DataFrame(res)
    ok = R[R.per_day >= 1.0].sort_values("usd", ascending=False)
    pd.set_option("display.width", 200)
    print(f"Earlier six months ({dd} days): {len(R)} variants, {len(ok)} with at least a trade a day; the best 12:")
    print(ok.head(12).round(3).to_string(index=False))
    print("\nEvery variant, earlier six months: positive", int((R.usd > 0).sum()), "of", len(R),
          "; with >= 1/day:", int((ok.usd > 0).sum()), "of", len(ok))
    print("\nBy screen (mean USD per trade over the variants with >= 1/day):")
    for col in ("s1", "s2", "s3", "tool"):
        print(" ", col, ok.groupby(col).usd_tr.mean().round(2).to_dict())
    best = ok.iloc[0]
    f = SCREEN1[best.s1], SCREEN2[best.s2], SCREEN3[best.s3]
    print(f"\nChosen: screen 1 {best.s1}, screen 2 {best.s2}, screen 3 {best.s3}, tool {best.tool}")
    for name, part, days in (("earlier six months (chosen on)", dev, dd), ("LATEST SIX MONTHS (test, once)", test, td)):
        r = run(part[f[0](part) & f[1](part) & f[2](part)], best.tool)
        print(f"  {name}: {summary(r, days)}")
        if "LATEST" in name:
            for s, g in r.groupby("session"):
                print(f"     session {['Asia', 'London', 'New York'][int(s)]}: {summary(g, days)}")
            for mo, g in r.groupby(r.t.dt.strftime("%Y-%m")):
                print(f"     {mo}: {len(g):3} trades, win {100 * g.win.mean():3.0f}%, {g.usd.sum():+7.1f} USD")
            r.to_parquet("data/research/own_triple_screen_test.parquet")
    print("\nThe next five variants on the test too (for stability, not for choosing):")
    for _, v in ok.iloc[1:6].iterrows():
        g = SCREEN1[v.s1], SCREEN2[v.s2], SCREEN3[v.s3]
        r = run(test[g[0](test) & g[1](test) & g[2](test)], v.tool)
        print(f"  {v.s1}/{v.s2}/{v.s3}/{v.tool}: earlier {v.usd:+.1f} USD; latest {summary(r, td)}")


if __name__ == "__main__":
    main()
