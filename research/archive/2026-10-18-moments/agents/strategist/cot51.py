"""Row 51 - managed-money positioning in COMEX gold (CFTC disaggregated COT) against the three leads (the
pre-registration is at the top of PROPOSALS.md). The release-lag alignment is the critical part: a report's values are
used only from its publication time.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/cot51.py > .../strategist/out_cot51.txt
Run from the repo root.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # gold.py
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
P2_START = pd.Timestamp("2026-01-16", tz="UTC")
NY = "America/New_York"
CODE = "088691"
EXTRA_CLOSED = [pd.Timestamp(d) for d in ("2024-12-24", "2025-12-24", "2025-12-26")]
# CFTC press release 9138-25: report date -> the new publish date (the 2025 funding lapse)
SHUTDOWN = {"2025-09-30": "2025-11-19", "2025-10-07": "2025-11-21", "2025-10-14": "2025-11-25",
            "2025-10-21": "2025-12-02", "2025-10-28": "2025-12-05", "2025-11-04": "2025-12-09",
            "2025-11-10": "2025-12-12", "2025-11-18": "2025-12-16", "2025-11-25": "2025-12-19",
            "2025-12-02": "2025-12-23", "2025-12-09": "2025-12-30", "2025-12-16": "2026-01-06",
            "2025-12-23": "2026-01-09", "2025-12-30": "2026-01-13", "2026-01-06": "2026-01-16",
            "2026-01-13": "2026-01-20", "2026-01-20": "2026-01-23"}
READ = ["mm_net", "mm_oi", "d4", "d13", "pct52", "dist52"]


def publish_time(asof: pd.Timestamp, holidays: set) -> pd.Timestamp:
    """When a report dated `asof` became public (UTC): the shutdown table's date if listed; else the Friday of the
    report's week, or the next Monday when a holiday falls from the report date through that Friday; 15:30 New York."""
    a = pd.Timestamp(asof).normalize()
    key = f"{a:%Y-%m-%d}"
    if key in SHUTDOWN:
        day = pd.Timestamp(SHUTDOWN[key])
    else:
        fri = a + pd.Timedelta(days=(4 - a.weekday()) % 7)
        span = pd.date_range(a, fri)
        day = fri + pd.Timedelta(days=3) if any(d in holidays for d in span) else fri
    return (day + pd.Timedelta(hours=15, minutes=30)).tz_localize(NY).tz_convert("UTC")


def known_at(pub_ns: np.ndarray, vals: np.ndarray, t_ns: int) -> float:
    """The value of the latest report published at or before t (pub_ns sorted); NaN when none."""
    k = int(np.searchsorted(pub_ns, t_ns, side="right")) - 1
    return float(vals[k]) if k >= 0 else np.nan


def pct_last(x: np.ndarray, i: int, n: int = 52, min_n: int = 26) -> float:
    """The share of x[i-n+1 .. i] (this one included) that is <= x[i]."""
    w = x[max(0, i - n + 1):i + 1]
    w = w[np.isfinite(w)]
    if len(w) < min_n:
        return np.nan
    return float(np.mean(w <= x[i]))


def holidays() -> set:
    h = USFederalHolidayCalendar().holidays("2019-12-01", "2026-12-31")
    return set(pd.DatetimeIndex(h).normalize()) | set(EXTRA_CLOSED)


def load_cot() -> pd.DataFrame:
    rows = []
    for f in sorted((HERE / "cftc").glob("fut_disagg_txt_*.zip")):
        z = zipfile.ZipFile(f)
        d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
        d = d[d.CFTC_Contract_Market_Code.astype(str).str.strip() == CODE]
        rows.append(d[["Report_Date_as_YYYY-MM-DD", "M_Money_Positions_Long_All", "M_Money_Positions_Short_All",
                       "Open_Interest_All"]])
    C = pd.concat(rows).drop_duplicates("Report_Date_as_YYYY-MM-DD")
    C.columns = ["asof", "mm_long", "mm_short", "oi"]
    C["asof"] = pd.to_datetime(C["asof"])
    C = C.sort_values("asof").reset_index(drop=True)
    C["mm_net"] = C.mm_long - C.mm_short
    C["mm_oi"] = C.mm_net / C.oi
    C["d4"] = C.mm_net.diff(4)
    C["d13"] = C.mm_net.diff(13)
    x = C.mm_net.to_numpy(float)
    C["pct52"] = [pct_last(x, i) for i in range(len(x))]
    H = holidays()
    C["pub"] = [publish_time(a, H) for a in C["asof"]]
    return C


def main() -> None:
    import gold
    import regime50 as G

    C = load_cot()
    C.to_csv(HERE / "out_cot51_reports.csv", index=False)
    late = C[C.pub - pd.to_datetime(C["asof"]).dt.tz_localize("UTC") > pd.Timedelta(days=6)]
    print(f"reports {len(C)}: {C['asof'].min():%Y-%m-%d} .. {C['asof'].max():%Y-%m-%d}; published later than 6 days: "
          f"{len(late)} ({', '.join(f'{a:%m-%d}->{p:%Y-%m-%d}' for a, p in zip(late.loc[:, 'asof'], late.pub, strict=True))})")
    pub = pd.DatetimeIndex(C.pub).as_unit("ns").asi8
    assert (np.diff(pub) > 0).all(), "publication times must rise with the report dates"

    T = pd.read_parquet(HERE / "regime50_trades.parquet")[["stream", "t_in", "R", "t", "day", "month"]]
    d1 = gold.bars("D1", before=EXAM)
    d1 = d1[d1.index >= pd.Timestamp("2020-06-01", tz="UTC")]
    hi = d1.high.rolling(260, min_periods=200).max().to_numpy()
    dist = d1.close.to_numpy() / hi - 1
    d1_av = np.r_[pd.DatetimeIndex(d1.index).as_unit("ns").asi8[1:], np.iinfo(np.int64).max]  # complete at the next open

    for k in READ[:-1]:
        v = C[k].to_numpy(float)
        T[f"{k}_roll"] = [known_at(pub, v, int(t)) for t in T.t_in]
    T["dist52_roll"] = [known_at(d1_av, dist, int(t)) for t in T.t_in]
    # monthly: the value known at the end of the previous calendar month
    for k in READ:
        ends = {}
        for p in T.month.unique():
            t_end = pd.Timestamp((p - 1).end_time.normalize() + pd.Timedelta(days=1), tz="UTC").value
            if k == "dist52":
                ends[p] = known_at(d1_av, dist, t_end)
            else:
                ends[p] = known_at(pub, C[k].to_numpy(float), t_end)
        T[f"{k}_mon"] = T.month.map(ends).astype(float)
    T.to_parquet(HERE / "cot51_trades.parquet")

    # the month table (values known at the month's end, i.e. the next month's monthly switch input)
    M = T.groupby("month").agg(trades=("R", "size"), R=("R", "mean"), sumR=("R", "sum"),
                               **{k: (f"{k}_mon", "first") for k in READ})
    pd.set_option("display.width", 220)
    print("\n=== month by month: the readings known at the START of the month (the previous month's end); the leads")
    print(M.round({"R": 3, "sumR": 1, "mm_net": 0, "mm_oi": 3, "d4": 0, "d13": 0, "pct52": 2, "dist52": 3}).to_string())

    fit, p2 = T.t < P2_START, T.t >= P2_START
    print(f"\nalways on: fit {fit.sum()} trades summed {T[fit].R.sum():+.1f}; P2 {p2.sum()} R {T[p2].R.mean():+.3f} "
          f"summed {T[p2].R.sum():+.1f}")
    print("\n=== the switch per reading (on when higher; thr chosen on the fit trades, read once on P2)")
    rows = []
    for k in READ:
        for form in ("mon", "roll"):
            x = T[f"{k}_{form}"].to_numpy(float)
            thr, s = G.choose_threshold(x[fit.to_numpy()], T.R.to_numpy()[fit.to_numpy()])
            on = np.isfinite(x) & (x > thr)
            T["on"] = on
            f_on, p_on = T[fit & on], T[p2 & on]
            pre = T[T.t < pd.Timestamp("2025-10-01", tz="UTC")]
            share = T[T.t >= pd.Timestamp("2025-03-01", tz="UTC")].groupby("month").on.mean()
            am = share.reindex([pd.Period("2025-04"), pd.Period("2025-05")]).to_numpy()
            pres = share.reindex(pd.period_range("2025-11", "2026-04", freq="M")).to_numpy()
            rows.append(dict(reading=k, form=form, thr=thr, fit_on=len(f_on), fit_sum=f_on.R.sum(), pre_on=int(pre.on.sum()),
                             pre_sum=pre[pre.on].R.sum(), apr_may=am.round(2).tolist(), present=pres.round(2).tolist(),
                             p2_on=len(p_on), p2_R=p_on.R.mean() if len(p_on) else np.nan, p2_sum=p_on.R.sum()))
            print(f"{k:7s} {form:4s} > {thr:.4g}: fit on {len(f_on):4d} summed {f_on.R.sum():+6.1f} (2021-09 .. 2025-09 on "
                  f"{int(pre.on.sum()):4d} summed {pre[pre.on].R.sum():+6.1f}); share on 2025-04/05 {am.round(2).tolist()} "
                  f"2025-11..2026-04 {pres.round(2).tolist()}; P2 on {len(p_on):3d} R "
                  f"{(p_on.R.mean() if len(p_on) else np.nan):+.3f} summed {p_on.R.sum():+6.1f}")
    pd.DataFrame(rows).to_csv(HERE / "out_cot51_switch.csv", index=False)

    # POST-HOC (written after the month table showed managed money LOW in the paying months): the same protocol with
    # "on when LOWER", for every reading - a description to report as seen-after, never a lead
    print("\n=== POST-HOC, seen after the month table: on when LOWER (same choice rule; ties -> the highest threshold)")
    for k in READ:
        for form in ("mon", "roll"):
            x = T[f"{k}_{form}"].to_numpy(float)
            thr, s = G.choose_threshold(x[fit.to_numpy()], T.R.to_numpy()[fit.to_numpy()], lower=True)
            on = np.isfinite(x) & (x < thr)
            T["on"] = on
            f_on, p_on = T[fit & on], T[p2 & on]
            pre = T[T.t < pd.Timestamp("2025-10-01", tz="UTC")]
            share = T[T.t >= pd.Timestamp("2025-03-01", tz="UTC")].groupby("month").on.mean()
            am = share.reindex([pd.Period("2025-04"), pd.Period("2025-05")]).to_numpy()
            pres = share.reindex(pd.period_range("2025-11", "2026-04", freq="M")).to_numpy()
            print(f"{k:7s} {form:4s} < {thr:.4g}: fit on {len(f_on):4d} summed {f_on.R.sum():+6.1f} (2021-09 .. 2025-09 on "
                  f"{int(pre.on.sum()):4d} summed {pre[pre.on].R.sum():+6.1f}); share on 2025-04/05 {am.round(2).tolist()} "
                  f"2025-11..2026-04 {pres.round(2).tolist()}; P2 on {len(p_on):3d} R "
                  f"{(p_on.R.mean() if len(p_on) else np.nan):+.3f} summed {p_on.R.sum():+6.1f}")

    # the public positioning after the learning data (CFTC figures only; no price data of ours)
    print("\n=== the public COT figures 2025-09 .. the latest (report date, published, mm_net, mm_oi, d4, d13, pct52)")
    x = C[C["asof"] >= pd.Timestamp("2025-09-01")]
    print(x[["asof", "pub", "mm_long", "mm_short", "mm_net", "mm_oi", "d4", "d13", "pct52"]].round(
        {"mm_oi": 3, "pct52": 3}).to_string(index=False))


if __name__ == "__main__":
    main()
