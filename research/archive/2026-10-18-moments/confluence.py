"""Round 9 (docs/OWN_SETUP_ROUNDS.md): the entry needs every group to agree at the same minute - the H1 tide, price at a
support (a buy) / resistance (a sell), price action at that level, and two of three M5 indicators. Rules fixed in
the doc, no fitting; tested on 2026-03-01 .. 2026-10-14, all sessions, with the losers in three kinds.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/confluence.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from ny_lab import SLIP, M1  # noqa: E402

START, END = pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-14", tz="UTC")
TP, BE, HZ, RMIN, RMAX = 8.0, 0.6, 60, 3.0, 10.0
SESS = {0: "Asia", 1: "London", 2: "New York"}


def m5_signals(P: M1) -> pd.DataFrame:
    """M5 bars from M1 (close-time index): RSI, MACD histogram, Stochastic %K/%D, and the bar's shape."""
    m = pd.DataFrame({"open": P.o, "high": P.h, "low": P.lo, "close": P.c}, index=P.ot)
    b = m.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    c = b.close
    d = c.diff()
    rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    k = (100 * (c - b.low.rolling(14).min()) / (b.high.rolling(14).max() - b.low.rolling(14).min())).rolling(3).mean()
    dd = k.rolling(3).mean()
    out = pd.DataFrame(
        {
            "rsi": rsi, "rsi_d": rsi.diff(), "hist_d": hist.diff(),
            "k_cross_up": (k > dd) & (k.shift(1) <= dd.shift(1)),
            "k_cross_dn": (k < dd) & (k.shift(1) >= dd.shift(1)),
            "o": b.open, "h": b.high, "l": b.low, "c": c,
        }
    )
    out.index = out.index + pd.Timedelta(minutes=5)
    return out


def hammer(o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray, side: np.ndarray) -> np.ndarray:
    rng = np.maximum(h - lo, 1e-9)
    lower = (np.minimum(o, c) - lo) / rng
    upper = (h - np.maximum(o, c)) / rng
    pos = (c - lo) / rng
    return np.where(side > 0, (lower >= 0.5) & (pos >= 2 / 3), (upper >= 0.5) & (pos <= 1 / 3))


def main() -> None:
    P = M1()
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[(d.t >= START) & (d.t < END)].copy()
    cr = pd.read_parquet("data/research/own_ml_cr_levels.parquet")
    cr["t"] = pd.to_datetime(cr.t, utc=True)
    d = d.merge(cr, on="t", how="left")
    side = d.side.to_numpy()
    p = d.e.to_numpy() - 1
    o, h, lo, c = P.o, P.h, P.lo, P.c
    atr = d.atr1.to_numpy()
    # the nearest level behind the trade (support for a buy, resistance for a sell), in float64 from the bars; the
    # day's and the Asian range only as they stood 15 minutes before (a level that already existed)
    n = len(c)
    bday = pd.Series(P.ot.tz_convert("Europe/Athens").date)
    day_hi = pd.Series(h).groupby(bday).cummax().to_numpy()
    day_lo = pd.Series(lo).groupby(bday).cummin().to_numpy()
    dly = pd.DataFrame({"h": h, "l": lo, "d": bday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    prev = dly.shift(1)
    uday = pd.Series(P.ot.normalize())
    asia = pd.Series(P.ot.hour < 7)
    asia_hi = pd.Series(np.where(asia, h, np.nan)).groupby(uday).cummax().groupby(uday).ffill().to_numpy()
    asia_lo = pd.Series(np.where(asia, lo, np.nan)).groupby(uday).cummin().groupby(uday).ffill().to_numpy()
    q = np.clip(p - 15, 0, n - 1)
    same_bday = bday.to_numpy()[q] == bday.to_numpy()[p]
    same_uday = uday.to_numpy()[q] == uday.to_numpy()[p]
    x = c[p]
    cands = {
        "today's extreme": np.where(side > 0, np.where(same_bday, day_lo[q], np.nan), np.where(same_bday, day_hi[q], np.nan)),
        "yesterday's extreme": np.where(side > 0, prev.l.reindex(bday.to_numpy()[p]).to_numpy(), prev.h.reindex(bday.to_numpy()[p]).to_numpy()),
        "Asian extreme": np.where(side > 0, np.where(same_uday, asia_lo[q], np.nan), np.where(same_uday, asia_hi[q], np.nan)),
        "round 50": np.where(side > 0, np.floor(x / 50) * 50, np.ceil(x / 50) * 50),
        "M15 level": x - side * np.where(side > 0, d.cr_M15_sup, d.cr_M15_res).astype(float),
        "H1 level": x - side * np.where(side > 0, d.cr_H1_sup, d.cr_H1_res).astype(float),
    }
    names = np.array(list(cands))
    L = np.vstack(list(cands.values())).T  # level prices
    gap = (x[:, None] - L) * side[:, None]  # > 0: the level lies behind the price
    gap[~np.isfinite(gap) | (gap <= 0)] = np.inf
    j = gap.argmin(1)
    dist = gap[np.arange(len(j)), j]
    kind = names[j]
    level = x - side * dist
    tide = (d.h1_e20_slope > 0).to_numpy() & (d.h1_c_e50 > 0).to_numpy()
    ext5 = np.where(side > 0, np.array([lo[i - 4 : i + 1].min() for i in p]), np.array([h[i - 4 : i + 1].max() for i in p]))
    at_level = np.isfinite(dist) & (dist <= 3 * atr) & ((ext5 - level) * side <= atr)
    # price action at the level
    m5 = m5_signals(P)
    k5 = m5.index.searchsorted(d.t, side="right") - 1
    r5 = m5.iloc[k5]
    pa_m1 = hammer(o[p], h[p], lo[p], c[p], side)
    pa_m5 = hammer(r5.o.to_numpy(), r5.h.to_numpy(), r5.l.to_numpy(), r5.c.to_numpy(), side)
    prev_bear = (c[p - 1] - o[p - 1]) * side < 0
    engulf = prev_bear & ((c[p] - o[p - 1]) * side > 0) & ((c[p] - o[p]) * side > 0)
    ext3 = np.where(side > 0, np.array([lo[i - 2 : i + 1].min() for i in p]), np.array([h[i - 2 : i + 1].max() for i in p]))
    reclaim = ((level - ext3) * side >= 0.1 * atr) & ((c[p] - level) * side > 0)
    pa = pa_m1 | pa_m5 | engulf | reclaim
    # indicators, two of three
    rsi_ok = np.where(side > 0, (r5.rsi_d > 0) & (r5.rsi < 50), (r5.rsi_d < 0) & (r5.rsi > 50))
    macd_ok = np.where(side > 0, r5.hist_d > 0, r5.hist_d < 0)
    stoch_ok = np.where(side > 0, r5.k_cross_up, r5.k_cross_dn)
    ind = (rsi_ok.astype(int) + macd_ok.astype(int) + stoch_ok.astype(int)) >= 2
    # the stop beyond the level, 3-10 USD
    fill = o[p + 1] + np.where(side > 0, P.sp[p + 1] + SLIP, -SLIP)
    risk = (fill - (level - side * atr)) * side
    risk_ok = (risk >= RMIN) & (risk <= RMAX)
    print("Funnel (minute x side rows, 2026-03-01 .. 10-14):")
    m = np.ones(len(d), dtype=bool)
    for name, cond in (("all rows", m), ("H1 tide", tide), ("at a level", at_level), ("price action", pa), ("indicators 2/3", ind), ("stop 3-10 USD", risk_ok)):
        m = m & cond
        print(f"  + {name:16} {int(m.sum()):7}")
    pa_name = np.where(pa_m1, "M1 hammer", np.where(pa_m5, "M5 hammer", np.where(engulf, "M1 engulfing", "sweep + reclaim")))
    ind_name = np.char.add(np.char.add(np.where(rsi_ok, "RSI ", ""), np.where(macd_ok, "MACD ", "")), np.where(stoch_ok, "Stoch", ""))
    sig = d[m].assign(sl=risk[m], level=level[m], level_kind=kind[m], pa_kind=pa_name[m], ind_kind=ind_name[m],
                      fill=fill[m], dist=dist[m], atr_=atr[m]).sort_values("t")

    def run(x: pd.DataFrame, coin: np.random.Generator | None = None) -> pd.DataFrame:
        rows, free, count = [], pd.Timestamp(0, tz="UTC"), {}
        for r in x.drop_duplicates("t").itertuples():
            key = (r.t.normalize(), r.session)
            if r.t < free or count.get(key, 0) >= 2:
                continue
            s = int(r.side) if coin is None else int(coin.choice([-1, 1]))
            out = P.trade(int(r.e), s, TP, float(r.sl), BE, HZ) | {
                "t": r.t, "session": r.session, "sl": float(r.sl), "side": s, "level": r.level, "level_kind": r.level_kind,
                "pa_kind": r.pa_kind, "ind_kind": r.ind_kind, "fill": r.fill, "dist": r.dist, "atr": r.atr_, "e": int(r.e)}
            rows.append(out)
            free, count[key] = r.t + pd.Timedelta(minutes=int(out["mins"])), count.get(key, 0) + 1
        return pd.DataFrame(rows)

    res, coin = run(sig), run(sig, np.random.default_rng(9))
    days = pd.bdate_range(START, END).size
    by_m = res.usd.groupby(res.t.dt.strftime("%Y-%m")).sum()
    print(f"\nTEST 2026-03-01 .. 10-14: {len(res)} trades ({len(res) / days:.2f}/day), win {100 * (res.exit == 'win').mean():.0f}%,"
          f" {res.usd.mean():+.2f} USD/trade ({(res.usd / (res.sl + SLIP)).mean():+.3f} R), {res.usd.sum():+.1f} USD at 0.01 lot,"
          f" months+ {(by_m > 0).sum()}/{len(by_m)}; exits {res.exit.value_counts().to_dict()}")
    for s, g in res.groupby("session"):
        print(f"   {SESS[int(s)]:8}: {len(g)} trades, win {100 * (g.exit == 'win').mean():.0f}%, {g.usd.sum():+.1f} USD")
    for mo, g in res.groupby(res.t.dt.strftime("%Y-%m")):
        print(f"   {mo}: {len(g):3} trades, win {100 * (g.exit == 'win').mean():3.0f}%, {g.usd.sum():+7.1f} USD")
    for name, z in (("ours", res), ("coin", coin)):
        v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
        print(f"   losers {name}: wrong way {100 * v['1']:.0f}%, fell short {100 * v['2']:.0f}%, too early {100 * v['3']:.0f}%"
              f"  ({name} total {z.usd.sum():+.1f} USD)")
    res.to_parquet("data/research/own_confluence_test.parquet")


if __name__ == "__main__":
    main()
