"""The owner's habits (2026-10-17), measured on gold M1, 2026-04-14 .. 10-14 (the latest six months):

1. Asia (07:00-09:00 Thai = 00:00-02:00 UTC) "often makes a small fake move before going the big way": the first
   leg of k x R from the start's open (R = the trailing 20-day median of that start's 2-hour range) and whether
   the close at +2 h / +6 h lies on the other side of the open (the leg was fake), against every other half-hour
   start of the day (the base rate: a random walk also reverses often).
2. New York "is volatile at the open and 1-2 hours after": the median 15-minute range by Thai clock time.
3. The losers of round 1 (moments, q70 stop): how many were right on direction but stopped first (the target
   reached within 60 minutes of the entry after the stop).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/owner_habits.py
"""

from __future__ import annotations

import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from moments import END, OUT, START  # noqa: E402

TH = ZoneInfo("Asia/Bangkok")
KS = (0.1, 0.2, 0.3)


def first_legs(m1: pd.DataFrame) -> pd.DataFrame:
    ot = m1.index
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    pos = {t: i for i, t in enumerate(ot)}
    days = [d for d in pd.date_range(START - pd.Timedelta(days=40), END - pd.Timedelta(days=1), freq="D") if d.weekday() < 5]
    rows = []
    for d in days:
        for k30 in range(0, 41):
            s = d + pd.Timedelta(minutes=30 * k30)
            i = pos.get(s)
            if i is None or i + 360 >= len(o) or ot[i + 120] != s + pd.Timedelta(minutes=120):
                continue
            rows.append((s, i, h[i : i + 120].max() - lo[i : i + 120].min()))
    st = pd.DataFrame(rows, columns=["s", "i", "rng2h"])
    st["slot"] = st.s.dt.strftime("%H:%M")
    st["R"] = st.groupby("slot").rng2h.transform(lambda x: x.shift(1).rolling(20, min_periods=10).median())
    st = st[(st.s >= START) & st.R.notna()].copy()
    out = []
    for s, i, R in zip(st.s, st.i, st.R, strict=True):
        p0 = o[i]
        rec = {"s": s}
        for k in KS:
            up, dn = p0 + k * R, p0 - k * R
            leg, at = 0, -1
            for j in range(i, i + 90):  # the first leg within 90 minutes
                hu, hd = h[j] >= up, lo[j] <= dn
                if hu and hd:
                    break
                if hu or hd:
                    leg, at = (1 if hu else -1), j
                    break
            rec[f"leg{k}"] = leg
            rec[f"at{k}"] = at - i if leg else np.nan
            for hz in (120, 360):
                rec[f"fake{k}_{hz}"] = np.nan if leg == 0 else float((c[i + hz - 1] - p0) * leg < 0)
            if leg:  # how far the fake leg went before the turn: the leg's extreme until the close at +2 h
                seg = h[i : i + 120].max() - p0 if leg > 0 else p0 - lo[i : i + 120].min()
                rec[f"ext{k}"] = seg
        rec["R"] = R
        out.append(rec)
    return pd.DataFrame(out)


def main() -> None:
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= START - pd.Timedelta(days=60)) & (m1.index < END + pd.Timedelta(days=2))]

    # 1. first legs
    f = first_legs(m1)
    f["th"] = f.s.dt.tz_convert(TH).dt.strftime("%H:%M")
    print("1. First leg of k x R from the start's open; share whose close at +2 h / +6 h is on the other side (fake)")
    print("   R = trailing 20-day median 2-hour range of that start (USD, median shown)")
    for k in KS:
        g = f.dropna(subset=[f"fake{k}_120"])
        tab = g.groupby("th").agg(
            n=(f"fake{k}_120", "size"),
            fake2h=(f"fake{k}_120", "mean"),
            fake6h=(f"fake{k}_360", "mean"),
            leg_min=(f"at{k}", "median"),
            R=("R", "median"),
        )
        base2, base6 = g[f"fake{k}_120"].mean(), g[f"fake{k}_360"].mean()
        print(f"\n k = {k}: all starts n {len(g)}, fake at +2 h {base2:.2f}, at +6 h {base6:.2f}")
        sel = tab.loc[[x for x in ("06:30", "07:00", "07:30", "08:00", "08:30", "09:00", "19:00", "19:30", "20:00", "20:30", "21:00") if x in tab.index]]
        print(sel.round(2).to_string())
    k = 0.2
    asia = f[f.th.isin(["07:00", "07:30", "08:00", "08:30"])].dropna(subset=[f"fake{k}_120"])
    fk = asia[asia[f"fake{k}_120"] == 1]
    print(f"\n Asia 07:00-08:30 Thai, k 0.2: the fake legs' size before the turn (USD): median {fk[f'ext{k}'].median():.2f},"
          f" q75 {fk[f'ext{k}'].quantile(0.75):.2f}, q90 {fk[f'ext{k}'].quantile(0.9):.2f}; R median {asia.R.median():.2f}")
    by_month = asia.groupby(asia.s.dt.to_period("M"))[f"fake{k}_120"].agg(["mean", "size"]).round(2)
    print(" Asia 07:00-08:30 Thai fake share at +2 h by month:", by_month.to_dict("index"))

    # 2. volatility profile by Thai clock time
    r15 = (m1.high.resample("15min").max() - m1.low.resample("15min").min()).dropna()
    r15 = r15[(r15.index >= START) & (r15.index < END) & (r15.index.weekday < 5)]
    prof = r15.groupby(r15.index.tz_convert(TH).strftime("%H:%M")).median()
    day_med = r15.median()
    print(f"\n2. Median 15-minute range by Thai time (USD; all-day median {day_med:.2f}); x = over the all-day median")
    hours = prof.groupby(prof.index.str[:2]).mean()
    print("   hourly:", " ".join(f"{h}:{v:.1f}" for h, v in hours.items()))
    ny = prof[(prof.index >= "18:00") & (prof.index <= "23:45")]
    print("   18:00-23:45 Thai:", " ".join(f"{t} {v:.1f} ({v / day_med:.1f}x)" for t, v in ny.items()))

    # 3. round 1 losers
    t = pd.read_parquet(f"{OUT}_exits.parquet")
    t = t[(t.kind == "moment") & t.r_S70.notna()].copy()
    o, h, lo = (m1[k].to_numpy(float) for k in ("open", "high", "low"))
    ot = m1.index
    e = ot.searchsorted(t.te)
    later = []
    for ei, side, tp, mins in zip(e, t.side, t.tp_dist, t.min_S70, strict=True):
        entry = o[ei]
        j0, j1 = ei + int(mins), min(ei + 60, len(o))
        if j0 >= j1:
            later.append(np.nan)
            continue
        best = h[j0:j1].max() - entry if side > 0 else entry - lo[j0:j1].min()
        later.append(float(best >= tp))
    t["right_later"] = later
    t["th"] = t.t.dt.tz_convert(TH).dt.strftime("%H:%M")
    los = t[t.r_S70 < -0.5]
    print(f"\n3. Round 1 losers at the moments (stopped, R < -0.5): {len(los)} of {len(t)}")
    print("   share that reached the target within 60 minutes of the entry after the stop (right way, stopped first):")
    print(los.groupby("pb").right_later.agg(["mean", "size"]).round(2).to_string())
    print(los.groupby("th").right_later.agg(["mean", "size"]).round(2).to_string())
    print("   minutes to the stop, losers (median):", los.groupby("pb").min_S70.median().to_dict())
    f.to_parquet("data/research/own_first_legs.parquet")


if __name__ == "__main__":
    main()
