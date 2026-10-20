"""Row 52 - gold-ETF holdings (SPDR GLD + GLDM daily tonnes) against the three leads (the pre-registration is at the top
of PROPOSALS.md). Holdings of day D are used only from the next weekday after D, 16:00 New York.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/etf52.py > .../strategist/out_etf52.txt
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import xlsx_min

HERE = Path(__file__).resolve().parent
P2_START = pd.Timestamp("2026-01-16", tz="UTC")
NY = "America/New_York"
READ = ["ch20", "ch60", "up20", "vs52"]


def public_from(day: pd.Timestamp) -> pd.Timestamp:
    """The holdings dated `day` count as public from the next weekday after it, 16:00 New York (UTC)."""
    d = pd.Timestamp(day).normalize() + pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d += pd.Timedelta(days=1)
    return (d + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC")


def features(t: np.ndarray) -> pd.DataFrame:
    """The readings on a daily tonnes series (ordered by date)."""
    s = pd.Series(np.asarray(t, float))
    up = (s.diff() > 0).astype(float)
    up[s.diff().isna()] = np.nan
    return pd.DataFrame({"ch20": s / s.shift(20) - 1, "ch60": s / s.shift(60) - 1,
                         "up20": up.rolling(20).sum(), "vs52": s / s.rolling(260, min_periods=200).max() - 1})


def load(name: str) -> pd.Series:
    R = xlsx_min.rows(str(HERE / "etf" / f"{name}_archive.xlsx"), "xl/worksheets/sheet2.xml")
    head = R[0]
    i_d, i_t = head.index("Date"), head.index("Tonnes of Gold")
    out = {}
    for r in R[1:]:
        if len(r) > i_t and isinstance(r[i_t], float) and r[i_d]:
            out[pd.Timestamp(pd.to_datetime(r[i_d], format="%d-%b-%Y"))] = r[i_t]
    return pd.Series(out).sort_index()


def main() -> None:
    import cot51
    import regime50 as G

    gld, gldm = load("gld"), load("gldm")
    S = pd.concat({"gld": gld, "gldm": gldm}, axis=1).dropna()
    S = S[S.index >= pd.Timestamp("2019-06-01")]
    S["tonnes"] = S.gld + S.gldm
    F = features(S.tonnes.to_numpy())
    F.index = S.index
    F["tonnes"] = S.tonnes
    F["pub"] = [public_from(d) for d in F.index]
    F.to_csv(HERE / "out_etf52_daily.csv")
    print(f"GLD {gld.index.min():%Y-%m-%d} .. {gld.index.max():%Y-%m-%d} ({len(gld)} days); GLDM {gldm.index.min():%Y-%m-%d} .. "
          f"{gldm.index.max():%Y-%m-%d}; joined from 2019-06: {len(S)} days")
    pub = pd.DatetimeIndex(F.pub).as_unit("ns").asi8
    assert (np.diff(pub) > 0).all()

    T = pd.read_parquet(HERE / "regime50_trades.parquet")[["stream", "t_in", "R", "t", "day", "month"]]
    for k in READ:
        v = F[k].to_numpy(float)
        T[f"{k}_roll"] = [cot51.known_at(pub, v, int(t)) for t in T.t_in]
        ends = {p: cot51.known_at(pub, v, pd.Timestamp(p.start_time, tz="UTC").value) for p in T.month.unique()}
        T[f"{k}_mon"] = T.month.map(ends).astype(float)
    T["tonnes_mon"] = T.month.map({p: cot51.known_at(pub, F.tonnes.to_numpy(float), pd.Timestamp(p.start_time, tz="UTC").value)
                                   for p in T.month.unique()}).astype(float)
    T.to_parquet(HERE / "etf52_trades.parquet")

    M = T.groupby("month").agg(trades=("R", "size"), R=("R", "mean"), sumR=("R", "sum"), tonnes=("tonnes_mon", "first"),
                               **{k: (f"{k}_mon", "first") for k in READ})
    pd.set_option("display.width", 220)
    print("\n=== month by month: GLD + GLDM holdings known at the START of the month; the three leads")
    print(M.round({"R": 3, "sumR": 1, "tonnes": 1, "ch20": 3, "ch60": 3, "up20": 0, "vs52": 3}).to_string())

    fit, p2 = T.t < P2_START, T.t >= P2_START
    print(f"\nalways on: fit {fit.sum()} summed {T[fit].R.sum():+.1f}; P2 {p2.sum()} R {T[p2].R.mean():+.3f} summed {T[p2].R.sum():+.1f}")
    print("\n=== the switch per reading (on when higher; thr chosen on the fit trades, read once on P2)")
    rows = []
    for k in READ:
        for form in ("mon", "roll"):
            x = T[f"{k}_{form}"].to_numpy(float)
            thr, _ = G.choose_threshold(x[fit.to_numpy()], T.R.to_numpy()[fit.to_numpy()])
            on = np.isfinite(x) & (x > thr)
            T["on"] = on
            f_on, p_on = T[fit & on], T[p2 & on]
            pre = T[T.t < pd.Timestamp("2025-10-01", tz="UTC")]
            share = T[T.t >= pd.Timestamp("2025-03-01", tz="UTC")].groupby("month").on.mean()
            am = share.reindex([pd.Period("2025-04"), pd.Period("2025-05")]).to_numpy().round(2).tolist()
            pres = share.reindex(pd.period_range("2025-10", "2026-04", freq="M")).to_numpy().round(2).tolist()
            rows.append(dict(reading=k, form=form, thr=thr, fit_on=len(f_on), fit_sum=f_on.R.sum(), pre_on=int(pre.on.sum()),
                             pre_sum=pre[pre.on].R.sum(), apr_may=am, oct_apr=pres, p2_on=len(p_on),
                             p2_R=p_on.R.mean() if len(p_on) else np.nan, p2_sum=p_on.R.sum()))
            print(f"{k:5s} {form:4s} > {thr:.4g}: fit on {len(f_on):4d} summed {f_on.R.sum():+6.1f} (2021-09 .. 2025-09 on "
                  f"{int(pre.on.sum()):4d} summed {pre[pre.on].R.sum():+6.1f}); share on 2025-04/05 {am} 2025-10..2026-04 {pres}; "
                  f"P2 on {len(p_on):3d} R {(p_on.R.mean() if len(p_on) else np.nan):+.3f} summed {p_on.R.sum():+6.1f}")
    pd.DataFrame(rows).to_csv(HERE / "out_etf52_switch.csv", index=False)

    print("\n=== the public holdings after the learning data (month ends; described only)")
    x = F[F.index >= pd.Timestamp("2025-09-01")]
    print(x.groupby(x.index.to_period("M")).last()[["tonnes", "ch20", "ch60", "up20", "vs52"]].round(3).to_string())


if __name__ == "__main__":
    main()
