"""Row 50 - the case for "the present regime" (the pre-registration is at the top of PROPOSALS.md). Gold's readings day
by day and month by month, 2021-09-01 .. 2026-04-17, against the three leads' results, and one switch per reading
("trade the leads only while X > threshold") chosen on the trades before 2026-01-16 and read once on P2.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/regime50.py > .../strategist/out_regime50.txt
Run from the repo root (gold.py reads relative paths).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # gold.py
sys.path.insert(0, str(HERE.parent / "precursors"))

EXAM = pd.Timestamp("2026-04-18", tz="UTC")
P2_START = pd.Timestamp("2026-01-16", tz="UTC")
NY = "America/New_York"
READ = ["dr", "atr", "jump", "spr_atr", "ny30", "eff"]
LOWER_IS_ON = {"spr_atr"}


# ---------------------------------------------------------------- pure functions (hand-tested in test_regime.py)
def release_jump(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, span_ns: int = 60 * 10**9) -> float:
    """The largest abs(mid - the last mid before t0) over the ticks in [t0, t0 + span); NaN without a tick before t0
    or none in the span."""
    k = int(np.searchsorted(t, t0, side="left"))
    if k == 0:
        return np.nan
    ref = (bid[k - 1] + ask[k - 1]) / 2
    e = int(np.searchsorted(t, t0 + span_ns, side="left"))
    if e <= k:
        return np.nan
    return float(np.max(np.abs((bid[k:e] + ask[k:e]) / 2 - ref)))


def choose_threshold(x: np.ndarray, r: np.ndarray, lower: bool = False) -> tuple[float, float]:
    """The threshold among the values of x maximising the summed r of the trades switched on (x > thr, or x < thr when
    `lower`); a tie goes to the lowest threshold (the highest when `lower`). NaN x is never on. Returns (thr, sum)."""
    ok = np.isfinite(x)
    best = None
    for c in np.unique(x[ok]):
        on = ok & ((x < c) if lower else (x > c))
        s = float(r[on].sum())
        if best is None or s > best[1] + 1e-12:
            best = (float(c), s)
        elif abs(s - best[1]) <= 1e-12 and ((c > best[0]) if lower else (c < best[0])):
            best = (float(c), s)
    return best if best is not None else (np.nan, 0.0)


def rolling_before(dates: np.ndarray, vals: np.ndarray, day, n: int, how: str = "median") -> float:
    """The median (or mean) of the last n finite values whose date is strictly before `day` (dates sorted)."""
    k = int(np.searchsorted(dates, day, side="left"))
    v = vals[:k]
    v = v[np.isfinite(v)][-n:]
    if len(v) < max(1, n // 2):
        return np.nan
    return float(np.median(v) if how == "median" else np.mean(v))


# ---------------------------------------------------------------- the daily readings
def daily() -> pd.DataFrame:
    import foundation as F
    import gold
    import indicators

    m = gold.bars("M1", before=EXAM)
    m = m[m.index >= pd.Timestamp("2021-09-01", tz="UTC")]
    m = m[["open", "high", "low", "close", "spread"]].astype(float)
    m = m[~m.index.duplicated(keep="last")].sort_index()
    m.index = pd.DatetimeIndex(m.index).as_unit("ns")  # gold.bars keeps microseconds (the NS-2 trap)
    assert m.index.max() < EXAM

    # D1 (MT5's own): range and the 20-day efficiency, keyed by the server date
    d1 = gold.bars("D1", before=EXAM)
    d1 = d1[d1.index >= pd.Timestamp("2021-07-01", tz="UTC")]
    c = d1.close.to_numpy(float)
    net = np.abs(pd.Series(c).diff(20).to_numpy())
    path = pd.Series(np.abs(np.diff(c, prepend=np.nan))).rolling(20).sum().to_numpy()
    D = pd.DataFrame({"dr": (d1.high - d1.low).to_numpy(float), "eff": net / path},
                     index=pd.DatetimeIndex(d1.index).tz_convert("Europe/Athens").tz_localize(None).normalize())

    # H1 from M1: the ATR(14); the M1 spread against the ATR of the last complete H1 bar
    h1 = indicators.bars(m, "1h")
    atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
    h1_start = pd.DatetimeIndex(h1["last"]).floor("1h")
    A = pd.DataFrame({"atr": atr}, index=h1_start)
    av = (h1_start + pd.Timedelta(hours=1)).as_unit("ns").asi8
    j = np.searchsorted(av, m.index.asi8, side="right") - 1
    ok = j >= 0
    sa = np.full(len(m), np.nan)
    sa[ok] = (m.spread.to_numpy()[ok] * 0.01 + 0.08) / atr[j[ok]]
    day_utc = m.index.tz_localize(None).normalize()
    S = pd.Series(sa, index=day_utc).groupby(level=0).median().rename("spr_atr")
    Aday = A.atr.groupby(A.index.tz_localize(None).normalize()).median()

    # the NY 08:30-12:30 range per New York date
    ny = m.index.tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    sel = (mins >= 510) & (mins < 750)
    g = pd.DataFrame({"h": m.high.to_numpy()[sel], "l": m.low.to_numpy()[sel]},
                     index=ny[sel].tz_localize(None).normalize()).groupby(level=0)
    nyr = (g.h.max() - g.l.min())
    nyc = g.h.size()
    ny30 = (nyr >= 30).astype(float).where(nyc >= 200)

    # the release-minute jump on 08:30-ET days
    cal = pd.read_csv(Path(gold.__file__).with_name("us_releases.csv"), dtype=str)
    cal = cal[cal.time_et == "08:30"].drop_duplicates("date")
    J = {}
    root = Path("data")
    for d in cal.date:
        day = pd.Timestamp(d)
        t0 = pd.Timestamp(f"{d} 08:30", tz=NY).tz_convert("UTC")
        if t0 >= EXAM or day < pd.Timestamp("2021-09-01"):
            continue
        f = None
        for sub in ("ticks", "ticks_old"):
            p = root / sub / "XAUUSD" / f"{t0:%Y-%m-%d}.parquet"
            if p.exists():
                f = p
                break
        if f is None:
            continue
        x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"])
        t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
        o = np.argsort(t, kind="stable")
        J[day] = release_jump(t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o], t0.value)
    jump = pd.Series(J, name="jump", dtype=float)

    idx = pd.bdate_range("2021-09-01", "2026-04-17")
    out = pd.DataFrame(index=idx)
    out["dr"], out["eff"] = D.dr.reindex(idx), D.eff.reindex(idx)
    out["atr"], out["spr_atr"] = Aday.reindex(idx), S.reindex(idx)
    out["ny30"], out["jump"] = ny30.reindex(idx), jump.reindex(idx)
    return out


def leads() -> pd.DataFrame:
    a = pd.read_parquet(HERE / "sw20_trades.parquet")
    a = a[a.t_in < pd.Timestamp("2023-10-18", tz="UTC").value][["stream", "t_in", "R_m1"]].rename(columns={"R_m1": "R"})
    b = pd.read_parquet(HERE / "states_events.parquet")
    b = b[b.R.notna()]
    b = b[(b.stream != "RC") | (b.win != "other")].assign(stream=lambda z: z.stream.replace({"RC": "RC_win"}))
    T = pd.concat([a, b[["stream", "t_in", "R"]]], ignore_index=True)
    T = T[T.R.notna()].sort_values("t_in").reset_index(drop=True)
    T["t"] = pd.to_datetime(T.t_in, utc=True)
    assert T.t.max() < EXAM
    T["day"] = T.t.dt.tz_localize(None).dt.normalize()
    T["month"] = T.t.dt.tz_localize(None).dt.to_period("M")
    return T


def main() -> None:
    import tsim

    tsim.idle()
    D = daily()
    T = leads()
    D.to_parquet(HERE / "regime50_daily.parquet")
    D["month"] = D.index.to_period("M")
    agg = {"dr": "median", "atr": "median", "jump": "median", "spr_atr": "median", "ny30": "mean", "eff": "median"}
    M = D.groupby("month").agg(agg)
    M["jump_n"] = D.groupby("month").jump.count()
    g = T.groupby("month")
    M["trades"], M["R"], M["sumR"] = g.size(), g.R.mean(), g.R.sum()
    pd.set_option("display.width", 220)
    print("=== month by month (readings: dr / atr / jump USD, spr_atr, ny30 share, eff; the three leads together)")
    print(M.round({"dr": 1, "atr": 1, "jump": 2, "spr_atr": 4, "ny30": 2, "eff": 2, "R": 3, "sumR": 1}).to_string())

    # the switch per reading: monthly (the previous calendar month) and rolling (before the day)
    dates = D.index.to_numpy()
    for k in READ:
        T[f"{k}_mon"] = T.month.map(lambda p, k=k: M[k].get(p - 1, np.nan)).astype(float)
        n, how = (5, "median") if k == "jump" else (20, "mean" if k == "ny30" else "median")
        vals = D[k].to_numpy(float)
        T[f"{k}_roll"] = [rolling_before(dates, vals, np.datetime64(d), n, how) for d in T.day]
    T.to_parquet(HERE / "regime50_trades.parquet")
    fit = T.t < P2_START
    p2 = ~fit
    print(f"\nthe leads always on: fit (2021-09 .. P1) {fit.sum()} trades summed R {T[fit].R.sum():+.1f}; "
          f"P2 {p2.sum()} trades R {T[p2].R.mean():+.3f} summed {T[p2].R.sum():+.1f}")
    print("\n=== the switch per reading (thr chosen on the fit trades; read once on P2)")
    rows = []
    for k in READ:
        for form in ("mon", "roll"):
            x = T[f"{k}_{form}"].to_numpy(float)
            lower = k in LOWER_IS_ON
            thr, s = choose_threshold(x[fit.to_numpy()], T.R.to_numpy()[fit.to_numpy()], lower)
            on = np.isfinite(x) & ((x < thr) if lower else (x > thr))
            T["on"] = on
            f_on, p_on = T[fit & on], T[p2 & on]
            # in time: the first day from which the switch stays on through the end of P1 (on every lead trade)
            late = T[(T.t >= pd.Timestamp("2025-06-01", tz="UTC")) & fit]
            off = late[~late.on]
            first_on = late.t.min() if not len(off) else (late[late.t > off.t.max()].t.min() if (late.t > off.t.max()).any() else pd.NaT)
            pre = T[(T.t >= pd.Timestamp("2021-09-01", tz="UTC")) & (T.t < pd.Timestamp("2025-10-01", tz="UTC"))]
            rows.append(dict(reading=k, form=form, thr=thr, fit_on=len(f_on), fit_sum=f_on.R.sum(),
                             pre_on=int(pre.on.sum()), pre_sum=pre[pre.on].R.sum(), on_from=first_on,
                             p2_on=len(p_on), p2_R=p_on.R.mean() if len(p_on) else np.nan, p2_sum=p_on.R.sum()))
            print(f"{k:8s} {form:4s} {'<' if lower else '>'} {thr:.4g}: fit on {len(f_on):4d} summed {f_on.R.sum():+6.1f} "
                  f"(2021-09 .. 2025-09 on {int(pre.on.sum()):4d} summed {pre[pre.on].R.sum():+6.1f}); stays on from "
                  f"{first_on if pd.notna(first_on) else '-'}; P2 on {len(p_on):3d} of {p2.sum()} R "
                  f"{(p_on.R.mean() if len(p_on) else np.nan):+.3f} summed {p_on.R.sum():+6.1f}")
    pd.DataFrame(rows).to_csv(HERE / "out_regime50_switch.csv", index=False)


if __name__ == "__main__":
    main()
