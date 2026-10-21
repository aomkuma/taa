"""Row 60 - larger-time-frame trades for the calm gold (pre-registered at the top of PROPOSALS.md).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/lt60.py learn   # LEARN; freezes lt60_frozen.json
    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/lt60.py test    # TEST once
Run from the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # gold.py
TICKS = Path("D:/taa-data/ticks/XAUUSD")
LEARN = (pd.Timestamp("2021-09-01", tz="UTC"), pd.Timestamp("2023-10-01", tz="UTC"))
TEST = (pd.Timestamp("2023-10-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC"))
FROZEN = HERE / "lt60_frozen.json"
MIN, HOUR = 60 * 10**9, 3600 * 10**9
CALM = 12.0
SETTINGS = {"PDB": [1.5, 2.0, None], "H4PB": [1.5, 2.0, None], "DON20": [1.0, 2.0, None]}  # target in R; None = time


def period_of(phase: str):
    if phase == "learn":
        return LEARN
    if phase == "test":
        if not FROZEN.exists():
            raise RuntimeError("TEST is read only after the LEARN run froze the settings")
        return TEST
    raise ValueError(phase)


# ---------------------------------------------------------------- the simulator (pure; tested)
def lsim(t, bid, ask, t_in: int, side: int, d: float, k_tgt: float | None, t_out: int, max_lag: int = 5 * MIN):
    """Enter at the first tick at / after t_in (ask for a buy, bid for a sell; within max_lag). The stop at d from the
    fill: the first later tick at / beyond it, filled at that tick's price (gaps included, no gap exit). The target
    k_tgt x d as a limit at its level. Otherwise out at the last tick before t_out. -> (pnl, R, exit, exit_ns) or None."""
    f = int(np.searchsorted(t, t_in, side="left"))
    if f >= len(t) or t[f] - t_in > max_lag or not d > 0:
        return None
    e = ask[f] if side > 0 else bid[f]
    end = int(np.searchsorted(t, t_out, side="left")) - 1  # the last tick before t_out
    if end <= f:
        return None
    px = bid[f + 1:end + 1] if side > 0 else ask[f + 1:end + 1]
    fav = side * (px - e)
    i_s = np.flatnonzero(fav <= -d)
    i_t = np.flatnonzero(fav >= k_tgt * d) if k_tgt is not None else np.array([], int)
    cand = []
    if len(i_s):
        cand.append((int(i_s[0]), 0, "stop", float(fav[i_s[0]])))
    if len(i_t):
        cand.append((int(i_t[0]), 1, "target", float(k_tgt * d)))
    if cand:
        i, _, why, pnl = min(cand)
    else:
        i, why, pnl = len(fav) - 1, "time", float(fav[-1])
    return pnl, pnl / d, why, int(t[f + 1 + i])


def d1_trend(close: np.ndarray, j: int, n: int = 20) -> int:
    """The sign of close[j] - close[j - n] (0 when unknown)."""
    if j < n:
        return 0
    return int(np.sign(close[j] - close[j - n]))


def avail_of(open_ns: np.ndarray, period_ns: int) -> np.ndarray:
    """A bar is complete at min(the next bar's open, its open + its period)."""
    nxt = np.r_[open_ns[1:], open_ns[-1] + period_ns]
    return np.minimum(nxt, open_ns + period_ns)


# ---------------------------------------------------------------- events
def events(phase: str) -> pd.DataFrame:
    import gold

    a, b = period_of(phase)
    bars = {}
    for tf, per in (("H1", HOUR), ("H4", 4 * HOUR), ("D1", 24 * HOUR)):
        x = gold.bars(tf, before=b)
        x = x[x.index >= a - pd.Timedelta(days=200)][["open", "high", "low", "close"]].astype(float)
        x = x[~x.index.duplicated(keep="last")].sort_index()
        x.index = pd.DatetimeIndex(x.index).as_unit("ns")
        assert x.index.max() < b
        x["t_open"] = x.index.asi8
        x["avail"] = avail_of(x.t_open.to_numpy(), per)
        x["sday"] = x.index.tz_convert("Europe/Athens").tz_localize(None).normalize()
        bars[tf] = x
    H1, H4, D1 = bars["H1"], bars["H4"], bars["D1"]
    pc = H1.close.shift(1)
    atr_h1 = pd.concat([H1.high - H1.low, (H1.high - pc).abs(), (H1.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    pcd = D1.close.shift(1)
    atr_d1 = pd.concat([D1.high - D1.low, (D1.high - pcd).abs(), (D1.low - pcd).abs()], axis=1).max(axis=1).rolling(14).mean()
    d_av, d_c, d_h, d_l = D1.avail.to_numpy(), D1.close.to_numpy(), D1.high.to_numpy(), D1.low.to_numpy()
    h1_av, h1_atr = H1.avail.to_numpy(), atr_h1.to_numpy()

    def calm_atr(t: int) -> float:
        i = int(np.searchsorted(h1_av, t, side="right")) - 1
        return float(h1_atr[i]) if i >= 0 else np.nan

    def last_d1(t: int) -> int:
        return int(np.searchsorted(d_av, t, side="right")) - 1

    # the week's open: the first H1 open of each server week (Monday-based)
    wk = H1.sday - pd.to_timedelta(H1.sday.dt.weekday, unit="D")
    H1["wk"] = wk.to_numpy()
    wopen = H1.groupby("wk").open.first()
    wfirst = H1.groupby("wk").avail.first()  # known once the week's first H1 bar has opened (its open is known at once;
    # the cautious side: from that bar's completion)

    E, seen = [], set()

    def add(cand, t_dec, side, d, t_out, key):
        if key in seen or not (a.value <= t_dec < b.value):
            return
        seen.add(key)
        E.append(dict(cand=cand, t_in=int(t_dec), side=int(side), d=float(d), t_out=int(t_out), atr=calm_atr(int(t_dec))))

    for r in H1.itertuples():
        t_dec = int(r.avail)
        j = last_d1(t_dec)
        if j < 21:
            continue
        tr = d1_trend(d_c, j)
        pdh, pdl = d_h[j], d_l[j]
        same_day_prev = D1.sday.iloc[j] < r.sday  # the last complete D1 is an earlier server day
        # 1 PDB: the first H1 close beyond the previous day's high / low, with the trend
        if same_day_prev and tr != 0:
            if (tr > 0 and r.close > pdh) or (tr < 0 and r.close < pdl):
                nd = r.sday + pd.offsets.BDay(1)
                t_out = (nd + pd.Timedelta(days=1)).tz_localize("Europe/Athens").tz_convert("UTC").value
                # the stop distance from the bar's opposite side, measured from the close (the fill adds the spread)
                dist = (r.close - r.low) if tr > 0 else (r.high - r.close)
                add("PDB", t_dec, tr, max(dist, 10.0), t_out, ("PDB", r.sday))
        # 3 DON20: the first H1 close beyond the 20 complete D1 bars' high / low
        hi20, lo20 = d_h[j - 19:j + 1].max(), d_l[j - 19:j + 1].min()
        side = 1 if r.close > hi20 else (-1 if r.close < lo20 else 0)
        if side and np.isfinite(atr_d1.iloc[j]):
            add("DON20", t_dec, side, max(float(atr_d1.iloc[j]), 10.0), t_dec + 48 * HOUR, ("DON20", r.sday))
    for r in H4.itertuples():
        t_dec = int(r.avail)
        j = last_d1(t_dec)
        if j < 21:
            continue
        tr = d1_trend(d_c, j)
        if tr == 0:
            continue
        lv = [d_h[j], d_l[j]]
        w = r.sday - pd.Timedelta(days=r.sday.weekday())
        if w in wopen.index and wfirst[w] <= t_dec:
            lv.append(float(wopen[w]))
        hit = any(r.open > L and r.low <= L and r.close > L for L in lv) if tr > 0 else \
            any(r.open < L and r.high >= L and r.close < L for L in lv)
        if hit:
            dist = (r.close - r.low) if tr > 0 else (r.high - r.close)
            add("H4PB", t_dec, tr, max(dist, 10.0), t_dec + 48 * HOUR, ("H4PB", r.sday))
    return pd.DataFrame(E)


def ticks(day: pd.Timestamp, end: pd.Timestamp):
    if day >= end:
        return None
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"]).sort_values("time_utc", kind="stable")
    return (pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), x.bid.to_numpy(float),
            x.ask.to_numpy(float))


def window(t_in: int, t_out: int, end: pd.Timestamp, cache: dict):
    """The ticks from the entry's day to the time limit's day (never a day at / after `end`)."""
    d0 = pd.Timestamp(int(t_in), tz="UTC").normalize()
    d1 = pd.Timestamp(int(t_out), tz="UTC").normalize()
    parts = []
    for d in pd.date_range(d0, d1, freq="D"):
        if d not in cache:
            cache[d] = ticks(d, end)
        if cache[d] is not None:
            parts.append(cache[d])
    for k in [k for k in cache if k < d0]:
        del cache[k]
    if not parts:
        return None
    return tuple(np.concatenate(z) for z in zip(*parts, strict=True))


def simulate(E: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    rows, cache = [], {}
    for r in E.sort_values("t_in").itertuples():
        w = window(r.t_in, r.t_out, end, cache)
        if w is None:
            continue
        for k in SETTINGS[r.cand]:
            s = lsim(*w, r.t_in, r.side, r.d, k, r.t_out)
            if s:
                rows.append(dict(cand=r.cand, setting=f"target {k} R" if k else "time only", t_in=r.t_in, atr=r.atr,
                                 d=r.d, pnl=s[0], R=s[1], exit=s[2], t_exit=s[3]))
    return pd.DataFrame(rows)


def ci95(x, n_boot=4000, seed=7):
    if len(x) < 2:
        return np.nan, np.nan
    m = np.random.default_rng(seed).choice(x, size=(n_boot, len(x)), replace=True).mean(1)
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def choose(T: pd.DataFrame) -> dict:
    out = {}
    for cand in SETTINGS:
        g = T[(T.cand == cand) & (T.atr < CALM)].groupby("setting").R.mean()
        out[cand] = str(g.idxmax()) if len(g) else ""
    return out


def main() -> None:
    import tsim

    phase = sys.argv[1] if len(sys.argv) > 1 else "learn"
    a, b = period_of(phase)
    tsim.idle()
    E = events(phase)
    T = simulate(E, b)
    T.to_parquet(HERE / f"lt60_{phase}.parquet")
    t = pd.to_datetime(T.t_in, utc=True)
    T["year"] = (t.dt.year.where(t.dt.month >= 10, t.dt.year - 1)).astype(str)
    frozen = json.loads(FROZEN.read_text()) if phase == "test" else None
    L = [f"=== {phase.upper()} {a:%Y-%m-%d} .. {b - pd.Timedelta(days=1):%Y-%m-%d}; calm (H1 ATR < {CALM:g}); events "
         f"{E.cand.value_counts().to_dict()}"]
    for cand in SETTINGS:
        for s in sorted(T[T.cand == cand].setting.unique()):
            if phase == "test" and s != frozen[cand]:
                continue
            x = T[(T.cand == cand) & (T.setting == s) & (T.atr < CALM)]
            lo, hi = ci95(x.R.to_numpy())
            yrs = " | ".join(f"{y} {len(g)} {g.R.mean():+.3f}" for y, g in x.groupby("year"))
            L.append(f"{cand:6s} {s:14s} {len(x):4d}  R {x.R.mean():+.3f} ({lo:+.3f} .. {hi:+.3f})  win {(x.pnl > 0).mean():.2f}"
                     f"  median stop {x.d.median():5.1f}  USD {x.pnl.sum():+8.1f}  exits {x.exit.value_counts().to_dict()} | {yrs}")
    if phase == "learn":
        ch = choose(T)
        FROZEN.write_text(json.dumps(ch, indent=1))
        L.append(f"\nFROZEN (best LEARN R): {ch}")
    else:
        Lr = pd.read_parquet(HERE / "lt60_learn.parquet")
        L.append("\nPASS (TEST >= +0.10 on >= 60 calm trades, 95 % low > 0, LEARN >= +0.10):")
        for cand, s in frozen.items():
            x = T[(T.cand == cand) & (T.setting == s) & (T.atr < CALM)]
            lx = Lr[(Lr.cand == cand) & (Lr.setting == s) & (Lr.atr < CALM)]
            lo, _ = ci95(x.R.to_numpy())
            ok = len(x) >= 60 and x.R.mean() >= 0.10 and lo > 0 and lx.R.mean() >= 0.10
            L.append(f"  {cand:6s} {s:14s} LEARN {lx.R.mean():+.3f} ({len(lx)}) TEST {x.R.mean():+.3f} ({len(x)}, low {lo:+.3f})"
                     f" -> {'PASS' if ok else 'FAIL'}")
    txt = "\n".join(L)
    (HERE / f"out_lt60_{phase}.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
