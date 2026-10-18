"""Round 2: the untouched older sample (gold M1 2021-09 .. 2023-10, the TS store, never used to choose anything in
this folder) as a holdout for the frozen rules A9 / A10 / D1 and the window-informed A11 (notes.md). The R15
catalogue, the turn trigger, the 72-hour break and the adaptive ATR rebuilt for that period with the same code.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/oldcheck.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402  (sets jlib.m1_frame; replaced below)
import rules2  # noqa: E402
import study  # noqa: E402
from catalogue import qualify, runs_of  # noqa: E402
from features import at_close, htf  # noqa: E402

gold, jlib = rules.gold, rules.jlib
A, B = pd.Timestamp("2021-10-01", tz="UTC"), pd.Timestamp("2023-11-01", tz="UTC")
REF = 4100.0
OLD_HALVES = pd.to_datetime(["2021-10-01", "2022-05-01", "2022-11-01", "2023-05-01", "2023-11-01"], utc=True)


def _m1_old(sym: str) -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= pd.Timestamp("2021-09-01", tz="UTC")) & (m.index < pd.Timestamp("2023-11-08", tz="UTC"))]
    m = m[~m.index.duplicated(keep="last")]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


def catalogue_old(P) -> pd.DataFrame:
    ot = P.ot
    o, h, lo, c = P.o, P.h, P.lo, P.c
    tmin = ((ot - ot[0]).total_seconds() // 60).to_numpy().astype(np.int64)
    m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc15 = m15.close.shift(1)
    tr15 = np.maximum(m15.high - m15.low, np.maximum((m15.high - pc15).abs(), (m15.low - pc15).abs()))
    a15 = tr15.rolling(14).mean()
    a15.index = a15.index + pd.Timedelta(minutes=15)
    atr15 = a15.reindex(ot, method="ffill").to_numpy()
    R = 15 * o / REF
    rows = []
    for side in (1, -1):
        ok, tgt = qualify(h, lo, c, tmin, R, side)
        ok &= (ot >= A)
        for i, t, size, xj, endj in runs_of(ok, tgt, h, lo, tmin, R, side):
            endj = min(endj, len(ot) - 1)
            rows.append(dict(R=15.0, side=side, t=ot[i], t_tgt=ot[t], mins_to_R=int(tmin[t] - tmin[i] + 1),
                             start_px=lo[i] if side > 0 else h[i], size=size, dur=int(tmin[xj] - tmin[i] + 1),
                             t_ext=ot[xj], t_end=ot[endj], atr15=atr15[i], size_atr=size / atr15[i]))
    return pd.DataFrame(rows).sort_values("t").reset_index(drop=True)


def adaptive_old(P) -> np.ndarray:
    ats = []
    for tf in (1, 5, 15, 30):
        b = htf(P.m, tf)
        ats.append(at_close(b.atr, b.end, P.ot))
    atr = np.vstack(ats)
    ok = atr >= 5.0
    pick = np.where(ok.any(0), np.argmax(ok, axis=0), 3)
    return atr[pick, np.arange(len(P.ot))]


def main() -> None:
    gold.below_normal_priority()
    jlib.m1_frame = _m1_old
    P = jlib.Instr("XAUUSD")
    G = jlib.Instr("XAUUSD")
    G.gross()
    C = catalogue_old(P)
    AD = adaptive_old(P)
    S = study.turns(P, C)
    ot = P.ot
    h72 = pd.Series(P.h, index=ot).rolling("72h").max().to_numpy()
    l72 = pd.Series(P.lo, index=ot).rolling("72h").min().to_numpy()
    i_s = S.i_s.to_numpy()
    s = S.side.to_numpy()
    L = np.where(s > 0, h72[i_s - 1], l72[i_s - 1])
    ahead = (L - S.start.to_numpy()) * s > 0
    S["lvl_h72"] = np.where(ahead, (S.ext.to_numpy() - L) * s / S.atr15.to_numpy(), np.nan)
    S["age"] = (pd.DatetimeIndex(S.t) - pd.DatetimeIndex(S.run_t)).total_seconds().to_numpy() / 60
    S = S[(S.t >= A) & (S.t < B)]
    days = pd.bdate_range(A, B, inclusive="left").size
    print(f"old sample {A:%Y-%m-%d} .. {B:%Y-%m-%d}: R15 runs {len(C)}, turn signals {len(S)}, weekdays {days}")
    for name in ("A9", "A10", "A11", "D1"):
        cfg = rules2.RULES2[name]
        if cfg["kind"] == "turn":
            x = S[(S.size_atr >= cfg["big"]) & (S.age <= cfg["fresh"]) & (S.lvl_h72 > 0)].sort_values("t")
        else:
            rules2.REF = REF
            Cx = C.copy()
            x = rules2_limit(P, Cx, cfg)
        z = rules2.simulate(P, x, cfg, AD)
        zg = rules2.simulate(G, x, cfg, AD)
        rs = [rules2.simulate(P, x, cfg, AD, np.random.default_rng(100 + k)) for k in range(10)]
        eq = z.pnl.cumsum()
        per = " ".join(f"{str(k.left)[2:7]} {v.R.mean():+.2f}({len(v)})" for k, v in
                       z.groupby(pd.cut(z.t, OLD_HALVES, right=False), observed=True))
        print(f"  {name}: {len(z)} trades ({len(z) / days:.2f}/day), R {z.R.mean():+.3f}, {z.pnl.sum():+.1f} USD at 0.01 lot,"
              f" before costs {zg.R.mean():+.3f}; coin {np.mean([r.R.mean() for r in rs]):+.3f}"
              f" (sd {np.std([r.R.mean() for r in rs]):.3f}); worst {z.pnl.min():.2f}, max DD {(eq.cummax() - eq).max():.1f};"
              f" stop median {z.sl.median():.2f}\n     {per}")
        z.to_parquet(HERE / f"trades_{name}_old.parquet")


def rules2_limit(P, C, cfg) -> pd.DataFrame:
    """rules2.limit_signals on the old catalogue (the same code path, the catalogue passed in)."""
    import simlib

    ot = P.ot
    rows = []
    for r in C.itertuples():
        s = int(r.side)
        i_s = ot.searchsorted(r.t)
        a = ot.searchsorted(r.t_tgt) + 1
        k0 = ot.searchsorted(r.t_end)
        b = min(i_s + 121, k0 + 60, len(ot) - 300)
        if a >= b:
            continue
        x0 = simlib.run_x0(P, i_s, a, s)
        got = simlib.limit_fill(P, a, b, s, r.start_px, cfg["f"], x0)
        if got is None:
            continue
        jf, entry, x = got
        t = ot[jf]
        if t.hour >= 20 or t.dayofweek >= 5 or t < A or t >= B:
            continue
        size = (x - r.start_px) * s
        if size / r.atr15 < cfg["big"]:
            continue
        rows.append(dict(t=t, e=jf, side=s, start=r.start_px, ext=x, run_t=r.t, entry=entry, u=P.o[jf] / REF, size=size))
    return pd.DataFrame(rows).sort_values("t").reset_index(drop=True)


if __name__ == "__main__":
    main()
