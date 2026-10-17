"""Round 3 dataset (docs/OWN_SETUP.md "Round 3"): every minute of the active windows, both sides, features at the
previous bar's close and the +5 USD labels for stops of 4 / 6 / 8 USD.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ml_dataset.py
"""

from __future__ import annotations

import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as win

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

LO, HI = pd.Timestamp("2025-08-01", tz="UTC"), pd.Timestamp("2026-10-14", tz="UTC")
FIRST = pd.Timestamp("2025-10-14", tz="UTC")
POINT, SLIP = 0.01, 0.07
TARGET, STOPS, HORIZON = 5.0, (4.0, 6.0, 8.0), 30
WINDOWS = [  # session, zone, start, end (local)
    ("asia", "UTC", "00:00", "02:00"),
    ("london", "Europe/London", "08:00", "09:30"),
    ("ny", "America/New_York", "08:15", "11:15"),
]
PAIRS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCHF": 1, "USDCAD": 1}
OUT = "data/research/own_ml.parquet"


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False).mean()


def tf_features(m1: pd.DataFrame, rule: str, minutes: int, name: str, t: pd.DatetimeIndex) -> pd.DataFrame:
    """EMA position / slope and RSI of closed *rule* bars, as of each decision time *t* (bar ends <= t)."""
    b = m1.resample(rule, label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    c = b["close"]
    atr = (b["high"] - b["low"]).rolling(14).mean()
    e20, e50 = ema(c, 20), ema(c, 50)
    d = c.diff()
    rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
    f = pd.DataFrame(
        {
            f"{name}_c_e20": (c - e20) / atr,
            f"{name}_c_e50": (c - e50) / atr,
            f"{name}_e20_slope": (e20 - e20.shift(3)) / atr,
            f"{name}_rsi": rsi,
            f"{name}_pos20": (c - b["low"].rolling(20).min()) / (b["high"].rolling(20).max() - b["low"].rolling(20).min()),
        }
    )
    ends = b.index + pd.Timedelta(minutes=minutes)
    k = ends.searchsorted(t, side="right") - 1
    out = f.iloc[np.clip(k, 0, None)].reset_index(drop=True)
    out[k < 0] = np.nan
    return out


def main() -> None:
    global LO, FIRST, OUT
    args = sys.argv[1:]  # optional: --long (training history from 2023-11; FX M1 starts 2023-09)
    if "--long" in args:
        LO, FIRST, OUT = pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2023-11-01", tz="UTC"), "data/research/own_ml_long.parquet"
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= LO) & (m1.index < HI + pd.Timedelta(days=1))]
    ot = m1.index
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    v = m1["tick_volume"].to_numpy(float)
    sp = m1["spread"].to_numpy(float) * POINT
    n = len(o)

    # candidate entry bars: the bar opening at minute m of an active window
    days = [d for d in pd.date_range(FIRST, HI - pd.Timedelta(days=1), freq="D") if d.weekday() < 5]
    cand = []
    for d in days:
        for sess, zone, a, b in WINDOWS:
            z = ZoneInfo(zone)
            t0 = pd.Timestamp(f"{d.date()} {a}").tz_localize(z).tz_convert("UTC")
            t1 = pd.Timestamp(f"{d.date()} {b}").tz_localize(z).tz_convert("UTC")
            for t in pd.date_range(t0, t1 - pd.Timedelta(minutes=1), freq="min"):
                cand.append((t, sess, t0))
    cd = pd.DataFrame(cand, columns=["t", "session", "t0"])
    pos = pd.Series(np.arange(n), index=ot)
    cd["e"] = pos.reindex(cd.t).to_numpy()
    cd = cd.dropna(subset=["e"])
    cd["e"] = cd.e.astype(int)
    cd = cd[(cd.e > 1500) & (cd.e + HORIZON < n)]
    # the previous bar must be the minute before (no gap) and the horizon contiguous enough
    cd = cd[(ot[cd.e - 1] == cd.t - pd.Timedelta(minutes=1)) & (ot[cd.e + HORIZON - 1] <= cd.t + pd.Timedelta(minutes=HORIZON + 5))]
    e = cd.e.to_numpy()
    p = e - 1  # the decision bar
    print("candidates", len(cd))

    # ---- labels, both sides
    W = HORIZON
    H, L, S = win(h, W)[e], win(lo, W)[e], win(sp, W)[e]
    lab = {}
    for side in (1, -1):
        entry = o[e] + (sp[e] + SLIP if side > 0 else -SLIP)
        fav = (H - entry[:, None]) if side > 0 else (entry[:, None] - (L + S))
        adv = (entry[:, None] - L) if side > 0 else ((H + S) - entry[:, None])
        hit_t = np.where((fav >= TARGET).any(1), (fav >= TARGET).argmax(1), 10**6)
        last = c[e + W - 1] - (SLIP if side > 0 else -(sp[e + W - 1] + SLIP))
        timeout = (last - entry) * side
        for sl in STOPS:
            stop_t = np.where((adv >= sl).any(1), (adv >= sl).argmax(1), 10**6)
            win_ = hit_t < stop_t  # both in one bar = the stop
            stopped = (stop_t <= hit_t) & (stop_t < 10**6)
            usd = np.where(win_, TARGET, np.where(stopped, -sl - SLIP, timeout))
            lab[(side, sl)] = (win_.astype(np.int8), usd, np.minimum(np.minimum(hit_t, stop_t), W - 1) + 1)
        lab[(side, "mfe")] = fav.max(1)

    # ---- features at the decision bar p (closed)
    F = pd.DataFrame(index=range(len(cd)))
    atr14 = pd.Series(np.maximum(h - lo, np.abs(np.r_[np.nan, c[:-1]] - h))).rolling(14).mean().to_numpy()
    F["atr1"] = atr14[p]
    for k in (1, 2, 3, 5, 10, 15, 30, 60):
        F[f"ret{k}"] = c[p] - c[p - k]
        F[f"ret{k}_atr"] = F[f"ret{k}"] / F.atr1
    for k in (5, 15, 60):
        hh, ll = win(h, k)[p - k + 1].max(1), win(lo, k)[p - k + 1].min(1)
        F[f"rng{k}"] = hh - ll
        F[f"pos{k}"] = (c[p] - ll) / np.maximum(hh - ll, 1e-9)
    F["body"] = (c[p] - o[p]) / np.maximum(h[p] - lo[p], 1e-9)
    F["upwick"] = (h[p] - np.maximum(o[p], c[p])) / np.maximum(h[p] - lo[p], 1e-9)
    F["dnwick"] = (np.minimum(o[p], c[p]) - lo[p]) / np.maximum(h[p] - lo[p], 1e-9)
    F["bar_rng_atr"] = (h[p] - lo[p]) / F.atr1
    ups = (np.sign(c - o)).astype(float)
    F["dir3"] = win(ups, 3)[p - 2].sum(1)
    F["dir10"] = win(ups, 10)[p - 9].sum(1)
    vmean = pd.Series(v).rolling(60).mean().to_numpy()
    F["vol1"] = v[p] / np.maximum(vmean[p], 1)
    F["vol5"] = win(v, 5)[p - 4].sum(1) / np.maximum(5 * vmean[p], 1)
    F["spread"] = sp[p]
    # broker day levels
    bday = pd.Index(ot.tz_convert("Europe/Athens").date)
    g = pd.DataFrame({"h": h, "l": lo, "d": bday})
    day_hi = g.groupby("d").h.cummax().to_numpy()
    day_lo = g.groupby("d").l.cummin().to_numpy()
    dly = g.groupby("d").agg(h=("h", "max"), l=("l", "min"))
    dly["rng"] = dly.h - dly.l
    prev = dly.shift(1)
    adr = dly.rng.shift(1).rolling(20).mean()
    pdh = prev.h.reindex(bday[p]).to_numpy()
    pdl = prev.l.reindex(bday[p]).to_numpy()
    F["adr20"] = adr.reindex(bday[p]).to_numpy()
    F["day_rng_adr"] = (day_hi[p] - day_lo[p]) / F.adr20
    F["day_pos"] = (c[p] - day_lo[p]) / np.maximum(day_hi[p] - day_lo[p], 1e-9)
    F["to_day_hi"], F["to_day_lo"] = day_hi[p] - c[p], c[p] - day_lo[p]
    F["to_pdh"], F["to_pdl"] = pdh - c[p], c[p] - pdl
    utc_day = ot.normalize()
    asia = (ot.hour < 7)
    ah = pd.Series(np.where(asia, h, np.nan)).groupby(utc_day).cummax().to_numpy()
    al = pd.Series(np.where(asia, lo, np.nan)).groupby(utc_day).cummin().to_numpy()
    ah = pd.Series(ah).groupby(utc_day).ffill().to_numpy()
    al = pd.Series(al).groupby(utc_day).ffill().to_numpy()
    F["to_asia_hi"], F["to_asia_lo"] = ah[p] - c[p], c[p] - al[p]
    F["to_round_up"] = np.ceil(c[p] / 50) * 50 - c[p]
    F["to_round_dn"] = c[p] - np.floor(c[p] / 50) * 50
    # higher timeframes
    tdec = pd.DatetimeIndex(cd.t.to_numpy())
    for rule, mins, name in (("15min", 15, "m15"), ("60min", 60, "h1")):
        tf = tf_features(m1, rule, mins, name, tdec)
        for col in tf.columns:
            F[col] = tf[col].to_numpy()
    # the dollar
    usd = []
    for pair, sgn in PAIRS.items():
        x = pd.read_parquet(f"data/history/FBS-Demo/{pair}/M1.parquet", columns=["open_time", "close"])
        x.index = pd.DatetimeIndex(pd.to_datetime(x.open_time, utc=True))
        x = x.close[~x.index.duplicated()].reindex(ot).ffill()
        lr = np.log(x)
        sc = lr.diff().abs().rolling(5 * 1380, min_periods=1000).median()
        usd.append(sgn * (lr / sc))
    for k in (1, 5, 15, 60):
        parts = [(u.to_numpy()[p] - u.to_numpy()[p - k]) / np.sqrt(k) for u in usd]
        F[f"usd{k}"] = np.nanmean(np.vstack(parts), 0)
    # time
    F["session"] = cd.session.map({"asia": 0, "london": 1, "ny": 2}).to_numpy()
    F["min_in"] = ((cd.t - cd.t0).dt.total_seconds() / 60).to_numpy()
    F["weekday"] = cd.t.dt.weekday.to_numpy()
    rel = gold.releases()
    rt = np.sort(rel.t.to_numpy())
    tv = cd.t.to_numpy()
    k = np.searchsorted(rt, tv, side="right") - 1
    since = (tv - rt[np.clip(k, 0, None)]) / np.timedelta64(1, "m")
    F["since_release"] = np.where((k >= 0) & (since <= 240), since, 999)
    k2 = np.searchsorted(rt, tv, side="left")
    until = (rt[np.clip(k2, 0, len(rt) - 1)] - tv) / np.timedelta64(1, "m")
    F["until_release"] = np.where((k2 < len(rt)) & (until <= 120), until, 999)

    # ---- two rows per candidate: directional features signed by the side
    signed = [col for col in F.columns if col.startswith(("ret", "usd", "body", "dir")) or col.endswith(("_c_e20", "_c_e50", "_e20_slope"))]
    rows = []
    for side in (1, -1):
        G = F.copy()
        for col in signed:
            G[col] = G[col] * side
        if side < 0:  # the room ahead / behind swaps for a sell
            for a, b in (("to_day_hi", "to_day_lo"), ("to_pdh", "to_pdl"), ("to_asia_hi", "to_asia_lo"), ("to_round_up", "to_round_dn")):
                G[a], G[b] = F[b].to_numpy(), F[a].to_numpy()
            for col in ("pos5", "pos15", "pos60", "day_pos", "m15_pos20", "h1_pos20"):
                G[col] = 1 - F[col]
            G["m15_rsi"], G["h1_rsi"] = 100 - F.m15_rsi, 100 - F.h1_rsi
            G["upwick"], G["dnwick"] = F.dnwick.to_numpy(), F.upwick.to_numpy()
        G["side"] = side
        G["t"] = cd.t.to_numpy()
        G["e"] = e
        G["mfe"] = lab[(side, "mfe")]
        for sl in STOPS:
            w_, usd_, mins_ = lab[(side, sl)]
            G[f"y{int(sl)}"], G[f"usd{int(sl)}"], G[f"min{int(sl)}"] = w_, usd_, mins_
        rows.append(G)
    D = pd.concat(rows, ignore_index=True)
    for col in D.columns:
        if D[col].dtype == np.float64:
            D[col] = D[col].astype(np.float32)
    D.to_parquet(OUT)
    print(D.shape, "hit rates:", {f"sl{int(s)}": round(float(D[f'y{int(s)}'].mean()), 3) for s in STOPS})


if __name__ == "__main__":
    main()
