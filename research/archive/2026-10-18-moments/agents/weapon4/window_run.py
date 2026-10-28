"""The one window run (2026-03-01 .. 2026-10-14) of the frozen rules W5a and W7 (notes.md "FROZEN for the window").

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/window_run.py
"""
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w4lib as w  # noqa: E402
from w5_losers import feats  # noqa: E402

ROOT = w.ROOT
NY = ZoneInfo("America/New_York")
KIND = {0: "today", 1: "yesterday", 2: "asia", 3: "round", 4: "M15", 5: "H1"}
P = w.instr("XAUUSD")
a, b = w.WINDOW
days = w.days_in(a, b)


def others(D):
    """F1 v2 (the csv, minutes from this builder's F1 v2), S2 (CPI / NFP release times), S1 (overlap.py)."""
    f1 = pd.read_csv(ROOT / "research/2026-10-18-moments/shadow/f1_v2_window_trades.csv")
    f1["t"] = pd.to_datetime(f1.t, utc=True)
    h = pd.DatetimeIndex(D.t).hour
    S1f = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
    f1_mine = w.run_v2(S1f, P)
    print(f"F1 v2 check: csv {len(f1)} trades {f1.usd.sum():+.1f} USD; this builder {len(f1_mine)} trades"
          f" {f1_mine.usd.sum():+.1f} USD; same minutes {len(set(f1.t) & set(f1_mine.t))}")
    f1 = f1.merge(f1_mine[["t", "mins"]], on="t", how="left")
    f1["mins"] = f1.mins.fillna(60)
    f1["end"] = f1.t + pd.to_timedelta(f1.mins, unit="min")
    rel = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = rel[rel.event.isin(["CPI", "NFP"])]
    s2 = pd.DatetimeIndex(pd.to_datetime(rel.date + " " + rel.time_et).dt.tz_localize(NY).dt.tz_convert("UTC"))
    s2 = pd.Series(s2[(s2 >= pd.Timestamp(a, tz="UTC")) & (s2 < pd.Timestamp(b, tz="UTC"))])
    sys.path.insert(0, str(ROOT / "research/2026-10-17-s1"))
    import s1_funnel as sf

    point = json.load(open(f"{sf.H}/spec.json"))["spec"]["point"]
    m1 = sf.load("M1")
    m1 = m1[m1.index >= pd.Timestamp("2025-12-01", tz="UTC")]
    d = sf.outcomes(m1, sf.events(m1, 20), point, k=15, spreads_only=True, time_stop=240)
    nyt = d.t.dt.tz_convert(NY)
    nym = nyt.dt.hour * 60 + nyt.dt.minute
    utc = d.t.dt.hour + d.t.dt.minute / 60
    wd = d.t.dt.weekday
    keep = (wd < 5) & (utc >= 7) & (utc < 20) & ~((wd == 4) & (utc >= 16)) & ~((nym >= 480) & (nym < 720))
    s1 = sf.one_at_a_time(d[keep], 60)
    s1 = s1[(s1.t >= pd.Timestamp(a, tz="UTC")) & (s1.t < pd.Timestamp(b, tz="UTC"))].copy()
    s1["end"] = m1.index[s1.x.to_numpy()] + pd.Timedelta(minutes=1)
    print(f"others on the window: F1 v2 {len(f1)}, S1 {len(s1)}, S2 {len(s2)} releases")
    return f1, s1, s2


def inside(tt, other_t, other_end):
    ot, oe = other_t.to_numpy(), other_end.to_numpy()
    return np.array([((ot <= x) & (x < oe)).any() for x in tt.to_numpy()])


def coin_kinds(S, seeds=20):
    rs, ws, ks = [], [], []
    for s in range(seeds):
        z = w.plib.run(S, P, coin=np.random.default_rng(100 + s))
        rs.append(z.R.mean())
        ws.append((z.exit == "win").mean())
        ks.append(z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0).to_numpy())
    k = np.mean(ks, 0)
    return float(np.mean(rs)), float(np.std(rs)), float(np.mean(ws)), f"{100 * k[0]:.0f}/{100 * k[1]:.0f}/{100 * k[2]:.0f}"


def month_days(k):
    start = pd.Timestamp(k + "-01")
    end = min(start + pd.offsets.MonthBegin(), pd.Timestamp(b))
    return w.days_in(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))


def report(name, S, f1, s1, s2):
    z = w.run(S, P)
    F = feats(S, P)[["t", "side", "level_kind", "c4u", "hour", "sl_u", "ret15", "ret60", "hrs_ext", "atr_ratio",
                     "spr_atr", "h1_ce50"]]
    z = z.merge(F, on=["t", "side"], how="left")
    cr, csd, cw, ck = coin_kinds(S)
    win = (z.exit == "win").mean()
    print(f"\n==== {name}: WINDOW {a} .. {b} ({days} weekdays), real costs, 0.01 lot")
    print(f"  {len(z)} trades ({len(z) / days:.2f}/day), win {100 * win:.0f}%, R {z.R.mean():+.3f}, USD {z.usd.sum():+.1f}")
    print(f"  coin (20 seeds, same minutes): R {cr:+.3f} +- {csd:.3f}, win {100 * cw:.0f}% -> edge {100 * (win - cw):+.1f} pts;"
          f" kinds ours {w.plib.kinds(z)} / coin {ck}; longs {100 * (z.side > 0).mean():.0f}%")
    print("  " + w.account(z) + f"; exits {z.exit.value_counts().to_dict()}")
    g = z.groupby(z.t.dt.strftime("%Y-%m"))
    print(f"  months+ {(g.usd.sum() > 0).sum()}/{g.ngroups}")
    for k, v in g:
        print(f"    {k}: {len(v):3} trades ({len(v) / month_days(k):.2f}/d) win {100 * (v.exit == 'win').mean():3.0f}%"
              f" R {v.R.mean():+.3f} USD {v.usd.sum():+7.1f}")
    same_f1 = z.t.isin(set(f1.t)).to_numpy()
    in_f1 = inside(z.t, f1.t, f1.end)
    in_s1 = inside(z.t, s1.t, s1.end)
    s2v = pd.DatetimeIndex(s2).as_unit("ns").asi8
    zt = pd.DatetimeIndex(z.t).as_unit("ns").asi8
    near_s2 = np.array([(np.abs(s2v - x) <= 1800 * 10**9).any() for x in zt])
    f1d, s1d, s2d = set(f1.t.dt.date), set(s1.t.dt.date), set(s2.dt.date)
    zd = z.t.dt.date
    alone = ~zd.isin(f1d | s2d)
    print(f"  overlap: same minute as an F1 v2 trade {same_f1.sum()}, inside an F1 trade {in_f1.sum()}, inside an S1 trade"
          f" {in_s1.sum()}, within 30 min of a CPI/NFP release {near_s2.sum()}")
    print(f"  trades on days without F1 or S2: {alone.sum()} ({alone.sum() / days:.2f}/day) R {z[alone].R.mean():+.3f}"
          f" USD {z[alone].usd.sum():+.1f}; also without S1: {(~zd.isin(f1d | s2d | s1d)).sum()}")
    new = z[~same_f1 & ~in_f1]
    print(f"  trades not F1's (not its minute, not inside an F1 trade): {len(new)} ({len(new) / days:.2f}/day)"
          f" R {new.R.mean():+.3f} USD {new.usd.sum():+.1f}")
    alld = set(pd.bdate_range(a, b, inclusive="left").date)
    print(f"  weekdays with any trade: F1 + S2 {len(alld & (f1d | s2d))} of {days}; + this rule {len(alld & (f1d | s2d | set(zd)))};"
          f" with S1 too {len(alld & (f1d | s2d | s1d | set(zd)))}")
    print(f"  stopped losers {(z.exit == 'stop').sum()}: kinds {w.plib.kinds(z)}; by bucket (n, R, [stops' kinds 1/2/3])")
    for col, bins in (("level_kind", None), ("c4u", [-1e9, 0, 2, 4]), ("hour", [-1, 1.99, 6.99, 11.99, 16.99, 20]),
                      ("sl_u", [0, 4, 5.5, 7.5, 20]), ("atr_ratio", [0, 1.2, 2]), ("ret60", [-99, -1, 1, 3, 99]),
                      ("hrs_ext", [-1, 0.5, 2, 24, 99]), ("side", None)):
        bb = z[col].map(KIND) if col == "level_kind" else (z[col] if bins is None else pd.cut(z[col], bins))
        print(f"    {col}: " + "; ".join(f"{k} {len(v)} {v.R.mean():+.2f} [{w.plib.kinds(v) if (v.exit == 'stop').any() else '-'}]"
                                         for k, v in z.groupby(bb, observed=True)))
    return z


def main():
    w.jlib.gold.below_normal_priority()
    D = w.build(P, 1, a, b, [(0, 20)], "XAUUSD_M1_window")
    R = w.build(P, 1, a, b, [(0, 20)], "XAUUSD_M1_window_round0", kinds=["round"], round_offset=0.0)
    f1, s1, s2 = others(D)
    X = D.copy()
    X["n_ind"] = 2
    z5 = report("W5a F1-wide (FROZEN)", w.signals(X, 3, 10, 8, 0.6, 60), f1, s1, s2)
    z7 = report("W7 round-72 (FROZEN)", w.signals(R, 3, 10, 8, 0.6, 60, c4=4.0), f1, s1, s2)
    z5.to_csv(HERE / "window_W5a_trades.csv", index=False)
    z7.to_csv(HERE / "window_W7_trades.csv", index=False)


if __name__ == "__main__":
    main()
