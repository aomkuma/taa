"""Row 57 - the walk-forward of the PROCESS for PLAN-1's London 13:00 ORB and NY 08:30 straddle (the pre-registration
is at the top of PROPOSALS.md). Step 1 builds the tick trades 2021-09 .. 2026-04-17 with the measurer's own rule code
(precursors/vol16_old.py's loop, check_plan1.manage, ns1_ticks.straddle); step 2 runs the folds.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/wf_process.py build   # -> wf_trades.parquet
    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/wf_process.py folds   # -> out_wf_process.txt
Run from the repo root.
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
OLD_TICKS = Path("D:/taa-data/ticks/XAUUSD")
NEW_TICKS = HERE.parents[3] / "data/ticks/XAUUSD"
SWITCH = pd.Timestamp("2025-10-01", tz="UTC")
MIN = 60 * 10**9
FOLD0, LAST_END = pd.Timestamp("2022-10-01", tz="UTC"), EXAM


# ---------------------------------------------------------------- the folds (pure; tested)
def folds(first: pd.Timestamp = FOLD0, end: pd.Timestamp = LAST_END, months: int = 3, fit_months: int = 12):
    """[(fit_start, trade_start, trade_end)]: quarters from `first`, the last cut at `end`."""
    out, s = [], first
    while s < end:
        e = min(s + pd.DateOffset(months=months), end)
        out.append((s - pd.DateOffset(months=fit_months), s, e))
        s = s + pd.DateOffset(months=months)
    return out


def fit_mask(T: pd.DataFrame, fit_start: pd.Timestamp, trade_start: pd.Timestamp) -> np.ndarray:
    """The trades a fold may learn from: entered at / after fit_start and EXITED before its trading start."""
    return ((T.t_in >= fit_start) & (T.t_exit < trade_start)).to_numpy()


def trade_mask(T: pd.DataFrame, trade_start: pd.Timestamp, trade_end: pd.Timestamp) -> np.ndarray:
    return ((T.t_in >= trade_start) & (T.t_in < trade_end)).to_numpy()


def candidate_bands(atr: np.ndarray) -> list[tuple[float, float]]:
    """The 10 bands from the quartiles of `atr`: 4 quartiles, 3 adjacent pairs, 2 triples, all; outer edges open."""
    q = np.r_[-np.inf, np.quantile(atr, [0.25, 0.5, 0.75]), np.inf]
    return [(float(q[i]), float(q[j])) for w in (1, 2, 3, 4) for i in range(0, 5 - w) for j in [i + w]]


def choose_band(atr: np.ndarray, R: np.ndarray, min_n: int = 20, min_r: float = 0.10):
    """(band or None, its fit R, its fit n): the best fit R among bands with >= min_n trades (a tie -> more trades);
    None (stand aside) when none qualifies or the best is below min_r."""
    if len(atr) == 0:
        return None, np.nan, 0
    best = None
    for lo, hi in candidate_bands(atr):
        m = (atr >= lo) & (atr < hi)
        n = int(m.sum())
        if n < min_n:
            continue
        r = float(R[m].mean())
        if best is None or r > best[1] + 1e-12 or (abs(r - best[1]) <= 1e-12 and n > best[2]):
            best = ((lo, hi), r, n)
    if best is None or best[1] < min_r:
        return None, (best[1] if best else np.nan), (best[2] if best else 0)
    return best


def in_band(atr: np.ndarray, band) -> np.ndarray:
    if band is None:
        return np.zeros(len(atr), bool)
    return (atr >= band[0]) & (atr < band[1])


# ---------------------------------------------------------------- step 1: the trades
def ticks(day: pd.Timestamp):
    if day >= EXAM:
        raise RuntimeError("exam day requested")
    f = (OLD_TICKS if day < SWITCH else NEW_TICKS) / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"]).sort_values("time_utc", kind="stable")
    return (pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), x.bid.to_numpy(float),
            x.ask.to_numpy(float))


def build() -> pd.DataFrame:
    import check_plan1 as C
    import gold
    import ns1_ticks as N

    m1 = gold.bars("M1", before=EXAM)
    m1 = m1.loc[m1.index >= pd.Timestamp("2021-08-15", tz="UTC"), ["high", "low", "close"]].copy()
    h = gold.bars("H1", before=EXAM)[["high", "low", "close"]]
    assert m1.index.max() < EXAM and h.index.max() < EXAM
    pc = h.close.shift(1)
    atr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    a_t, a_v = (h.index + pd.Timedelta(hours=1)).as_unit("ns").asi8, atr.to_numpy()

    def atr_at(t_ns: int) -> float:
        i = int(np.searchsorted(a_t, t_ns, side="right")) - 1
        return float(a_v[i]) if i >= 0 else np.nan

    rows = []
    o = m1.index.as_unit("ns").asi8
    hi_, lo_, cl_ = m1.high.to_numpy(), m1.low.to_numpy(), m1.close.to_numpy()
    for day in pd.bdate_range("2021-09-01", "2026-04-17", tz="UTC"):
        tk = ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        # London ORB (vol16_old's loop = check_plan1.london's rule, slippage 0)
        t0 = day + pd.Timedelta(hours=6)
        i0, i15, i75 = (int(np.searchsorted(o, (t0 + pd.Timedelta(minutes=k)).value)) for k in (0, 15, 75))
        if i15 > i0 and o[i0] - t0.value <= 5 * MIN:
            rh, rl = hi_[i0:i15].max(), lo_[i0:i15].min()
            H = atr_at(t0.value)
            if np.isfinite(H) and rh - rl <= 1.5 * H:
                c = cl_[i15:i75]
                k = np.flatnonzero((c > rh) | (c < rl))
                if len(k):
                    side = 1 if c[k[0]] > rh else -1
                    t_dec = int(o[i15 + k[0]] + MIN)
                    f = int(np.searchsorted(t, t_dec, side="left"))
                    if f < len(t) and t[f] - t_dec <= 5 * MIN:
                        e = ask[f] if side > 0 else bid[f]
                        stop = rl if side > 0 else rh
                        risk = (e - stop) * side
                        if risk > 0:
                            r = C.manage(t, bid, ask, f, e, side, stop, e + side * 2 * risk, t[f] + 60 * MIN)
                            if r is not None:
                                rows.append(dict(piece="ORB", t_in=int(t[f]), t_exit=int(r[1]), atr=atr_at(t_dec),
                                                 pnl=(r[0] - e) * side, R=(r[0] - e) * side / risk))
        # NY straddle (ns1_ticks.straddle = check_plan1.ny's rule)
        tn = pd.Timestamp(f"{day:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        s = N.straddle(t, bid, ask, tn)
        if s is not None:
            rows.append(dict(piece="STR", t_in=int(tn), t_exit=int(tn + 30 * MIN), atr=atr_at(tn), pnl=s["pnl"], R=s["R"]))
    T = pd.DataFrame(rows)
    T["t_in"] = pd.to_datetime(T.t_in, utc=True)
    T["t_exit"] = pd.to_datetime(T.t_exit, utc=True)
    assert T.t_in.max() < EXAM
    return T


# ---------------------------------------------------------------- step 2: the folds
def run_folds(T: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, oos = [], []
    for fs, ts, te in folds():
        for piece in ("ORB", "STR"):
            P = T[T.piece == piece]
            F, O = P[fit_mask(P, fs, ts)], P[trade_mask(P, ts, te)]
            fa, fr = F.atr.to_numpy(float), F.R.to_numpy(float)
            band, br, bn = choose_band(fa, fr)
            v = (F.atr >= 12) & (F.atr < 16)
            vol_ok = v.sum() >= 20 and F.R[v].mean() >= 0.10
            oa = O.atr.to_numpy(float)
            sel = {"a": in_band(oa, band), "b1": in_band(oa, (12.0, 16.0) if vol_ok else None),
                   "b0": in_band(oa, (12.0, 16.0)), "c": np.ones(len(O), bool)}
            for k, msk in sel.items():
                oos.append(O[msk].assign(proc=k, fold=f"{ts:%Y-%m}"))
            rows.append(dict(fold=f"{ts:%Y-%m}", piece=piece, fit_n=len(F), band=band, band_fit_R=br, band_fit_n=bn,
                             vol16_fit_n=int(v.sum()), vol16_fit_R=float(F.R[v].mean()) if v.any() else np.nan,
                             vol16_on=bool(vol_ok), oos_all=len(O),
                             **{f"{k}_n": int(m.sum()) for k, m in sel.items()},
                             **{f"{k}_R": float(O.R[m].mean()) if m.any() else np.nan for k, m in sel.items()}))
    return pd.DataFrame(rows), pd.concat(oos, ignore_index=True)


def year_of(t: pd.Series) -> pd.Series:
    y = t.dt.year.where(t.dt.month >= 10, t.dt.year - 1)
    return y.astype(str) + "-" + ((y + 1) % 100).map(lambda v: f"{v:02d}")


def ci95(x: np.ndarray, n_boot: int = 4000, seed: int = 7) -> tuple[float, float]:
    if len(x) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(1)
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "folds"
    path = HERE / "wf_trades.parquet"
    if mode == "build":
        import tsim

        tsim.idle()
        T = build()
        T.to_parquet(path)
        parts = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}
        for piece in ("ORB", "STR"):
            for p, (a, b) in parts.items():
                x = T[(T.piece == piece) & (T.t_in >= pd.Timestamp(a, tz="UTC")) & (T.t_in < pd.Timestamp(b, tz="UTC"))]
                print(f"parity {piece} {p}: {len(x)} trades R {x.R.mean():+.3f}")
        V = pd.read_parquet(HERE.parent / "precursors/vol16_old.parquet")
        T2 = T[T.t_in < SWITCH].assign(year=lambda z: year_of(z.t_in), pc=lambda z: z.piece.map({"ORB": "London ORB",
                                                                                                    "STR": "NY straddle"}))
        for (pc, y), g in V.groupby(["piece", "year"]):
            x = T2[(T2.pc == pc) & (T2.year == y)]
            print(f"parity vol16_old {pc} {y}: theirs {len(g)} R {g.R.mean():+.3f} | mine {len(x)} R {x.R.mean():+.3f}")
        return
    T = pd.read_parquet(path)
    Fd, O = run_folds(T)
    Fd.to_csv(HERE / "out_wf_folds.csv", index=False)
    O.to_parquet(HERE / "wf_oos.parquet")
    pd.set_option("display.width", 250)
    print("=== the folds (choice on the previous 12 months; out-of-sample trades and R per process)")
    for r in Fd.itertuples():
        b = "stand aside" if r.band is None else f"[{r.band[0]:.2f}, {r.band[1]:.2f})"
        print(f"{r.fold} {r.piece}: fit {r.fit_n:3d} | (a) {b:22s} fit {r.band_fit_R:+.3f} ({r.band_fit_n}) | VOL-16 fit "
              f"{r.vol16_fit_R:+.3f} ({r.vol16_fit_n}) {'on' if r.vol16_on else 'off'} | OOS all {r.oos_all:3d}: "
              f"a {r.a_n:3d} {r.a_R:+.3f}  b1 {r.b1_n:3d} {r.b1_R:+.3f}  b0 {r.b0_n:3d} {r.b0_R:+.3f}  c {r.c_n:3d} {r.c_R:+.3f}")
    O["year"] = year_of(O.t_in)
    print("\n=== chained out-of-sample 2022-10 .. 2026-04-17")
    for k, name in (("a", "(a) the chosen band"), ("b1", "(b1) VOL-16 when it fit"), ("b0", "(b0) VOL-16 always"),
                    ("c", "(c) always on")):
        for piece in ("both", "ORB", "STR"):
            x = O[(O.proc == k) & ((O.piece == piece) | (piece == "both"))]
            lo, hi = ci95(x.R.to_numpy())
            yrs = " | ".join(f"{y} {len(g):3d} {g.R.mean():+.3f}" for y, g in x.groupby("year"))
            print(f"{name:26s} {piece:4s}: {len(x):4d} trades R {x.R.mean() if len(x) else np.nan:+.3f} "
                  f"({lo:+.3f} .. {hi:+.3f})  USD {x.pnl.sum():+8.1f} || {yrs}")
    x = O[O.proc == "a"]
    lo, _ = ci95(x.R.to_numpy())
    yr = x.groupby("year").R.mean()
    ok = len(x) and x.R.mean() >= 0.10 and lo > 0 and (yr >= -0.10).all()
    print(f"\nPASS LINE (a): chained R {x.R.mean():+.3f} >= +0.10, 95 % low {lo:+.3f} > 0, worst year {yr.min():+.3f} "
          f">= -0.10 -> {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
