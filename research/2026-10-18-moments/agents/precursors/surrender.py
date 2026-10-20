"""If it does not run, give up (notes.md, written before it is computed; owner, 2026-10-19: "once in, we do not wait
for a price that does not run - if we enter it must run; if it does not run, we surrender"). On the real ticks:
decisions at the M5 / M15 closes in the active hours, three sides, a market entry, the surrender (Y USD our way within
K minutes or out), then the target and the stop 10 USD, out after 60 minutes; one position at a time.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/surrender.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from tick_straddle import span_ticks  # noqa: E402

TARGET, STOP, SLIP = 10.0, 10.0, 0.07
NS_MIN = 60 * 10**9
HOLD_MIN = 60
SURRENDER = [(None, None), (3, 2.0), (3, 3.0), (5, 2.0), (5, 3.0)]  # (K minutes, Y USD)
ORDER = {"stop": 0, "win": 1, "surrender": 2}


def trade(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, side: int, k_min: int | None, y: float | None,
          target: float = TARGET, stop: float = STOP, hold_min: int = HOLD_MIN) -> dict | None:
    """A market entry at the first tick at / after t0; then, tick by tick: the stop (the first tick at / beyond it, its
    gap included), the target (a limit at its level), the surrender (no tick Y our way before K minutes -> out at the
    first tick at / after K), the time (out at the last tick before the hold ends)."""
    f = int(np.searchsorted(t, t0, side="left"))
    if f >= len(t):
        return None
    entry = ask[f] + SLIP if side > 0 else bid[f] - SLIP
    end = int(np.searchsorted(t, t[f] + hold_min * NS_MIN, side="left"))
    seg = slice(f + 1, end)
    fav = (bid[seg] - entry) if side > 0 else (entry - ask[seg])  # what closing at each tick would give
    ks = np.nonzero(fav <= -stop)[0]
    kt = np.nonzero(fav >= target)[0]
    events = []
    if len(ks):
        events.append((int(ks[0]), "stop"))
    if len(kt):
        events.append((int(kt[0]), "win"))
    if k_min is not None:
        ran = np.nonzero(fav >= y)[0]
        k_end = int(np.searchsorted(t[seg], t[f] + k_min * NS_MIN, side="left"))
        if (not len(ran) or ran[0] >= k_end) and k_end < len(fav):
            events.append((k_end, "surrender"))
    if events:
        i, name = min(events, key=lambda e: (e[0], ORDER[e[1]]))
        pnl = target if name == "win" else float(fav[i])
        return dict(side=side, exit=name, pnl=pnl, exit_t=int(t[f + 1 + i]), entry=entry)
    x = max(end - 1, f)
    return dict(side=side, exit="time", pnl=float((bid[x] - entry) if side > 0 else (entry - ask[x])), exit_t=int(t[x]), entry=entry)


def run(X: pd.DataFrame, k_min: int | None, y: float | None) -> pd.DataFrame:
    rows, busy = [], -1
    for day, D in X.groupby(pd.DatetimeIndex(X.t).normalize(), sort=True):
        tk = span_ticks(day)  # the next day joined: a trade open at midnight UTC runs on
        if tk is None:
            continue
        t, bid, ask = tk
        for r in D.itertuples():
            t0 = pd.Timestamp(r.t).value
            if t0 <= busy:
                continue
            x = trade(t, bid, ask, t0, int(r.side), k_min, y)
            if x is None:
                continue
            x["R"] = x["pnl"] / STOP
            rows.append(dict(t=r.t, **x))
            busy = x["exit_t"]
    return pd.DataFrame(rows)


def sides(X: pd.DataFrame) -> dict[str, np.ndarray]:
    way = X.D1_way20.to_numpy()
    fade = np.where(X.M30_pos <= 0.15, 1, np.where(X.M30_pos >= 0.85, -1, 0))
    return {"S1 aligned D1 way": np.where(X.aligned, way, 0), "S2 fade the M30 edge": fade, "S3 D1 way": way}


def active(X: pd.DataFrame) -> np.ndarray:
    return ((X.t_ny_open.abs() <= 60) | (X.t_fix_pm.abs() <= 60) | (X.t_us_data.abs() <= 60) | (X.t_comex.abs() <= 60)).to_numpy()


def summary(T: pd.DataFrame, a: str, b: str) -> str:
    import wf  # noqa: PLC0415

    if T.empty:
        return "no trades"
    eq = T.pnl.cumsum()
    return (f"{len(T)} trades ({len(T) / np.busday_count(a, b):.2f} a weekday), win {(T.exit == 'win').mean():.3f}, R {T.R.mean():+.3f}, "
            f"USD {T.pnl.sum():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, worst {T.pnl.min():+.2f}, streak "
            f"{wf.longest_run(T.pnl.to_numpy() < 0)}, exits {T.exit.value_counts().to_dict()}")


def main() -> None:
    import wf  # noqa: PLC0415
    from entry_tables import aligned_frame  # noqa: PLC0415
    from m15_trades import PARTS, part_of  # noqa: PLC0415

    A = aligned_frame()
    A["part"] = part_of(pd.DatetimeIndex(A.t))
    X = A[(A.part.isin(["P1", "P2"])) & active(A)].sort_values("t").reset_index(drop=True)
    S = sides(X)
    m15 = (pd.DatetimeIndex(X.t).minute % 15 == 0)
    configs = [(tf, sname, k, y) for tf in ("M5", "M15") for sname in S for k, y in SURRENDER]
    rows = {c: [] for c in configs}
    busy = {c: -1 for c in configs}
    days = pd.DatetimeIndex(X.t).normalize()
    for day in days.unique():  # each day's ticks read once, every setting run on them
        tk = span_ticks(day)  # the next day joined: a trade open at midnight UTC runs on
        if tk is None:
            continue
        t, bid, ask = tk
        D = X[days == day]
        for c in configs:
            tf, sname, k, y = c
            sd = S[sname][(days == day)]
            for r, s_, is15 in zip(D.itertuples(), sd, m15[(days == day)]):
                t0 = pd.Timestamp(r.t).value
                if s_ == 0 or (tf == "M15" and not is15) or t0 <= busy[c]:
                    continue
                x = trade(t, bid, ask, t0, int(s_), k, y)
                if x is None:
                    continue
                x["R"] = x["pnl"] / STOP
                rows[c].append(dict(t=r.t, part=r.part, **x))
                busy[c] = x["exit_t"]
    res = {}
    for c in configs:
        T = pd.DataFrame(rows[c])
        for p in ("P1", "P2"):
            Tp = T[T.part == p] if not T.empty else T
            res[(*c, p)] = Tp
            print(f"{c[0]} | {c[1]} | surrender {c[2]}m / {c[3]} | {p}: {summary(Tp, *PARTS[p])}", flush=True)
    keys = {key[:4] for key in res}
    score = {key: min(res[(*key, "P1")].R.mean(), res[(*key, "P2")].R.mean()) for key in keys
             if not res[(*key, "P1")].empty and not res[(*key, "P2")].empty}
    good = {k: v for k, v in score.items() if v > 0}
    if not good:
        print("\nnothing is positive in both learning parts: the exam is not read")
        return
    best = max(good, key=good.get)
    print(f"\nchosen on the learning parts: {best} (min R {good[best]:+.3f})")
    if sys.argv[1:] != ["exam"]:
        return
    tf, sname, k, y = best
    E = A[(A.part == "exam") & active(A)].copy()
    if tf == "M15":
        E = E[pd.DatetimeIndex(E.t).minute % 15 == 0]
    sd = sides(E)[sname]
    T = run(E[sd != 0].assign(side=sd[sd != 0]).sort_values("t"), k, y)
    print(f"THE EXAM, once (ticks to 2026-10-14): {summary(T, '2026-04-20', '2026-10-15')}")
    T["cell"] = f"{tf} {sname} {k}/{y}"
    pd.set_option("display.width", 220)
    print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / "surrender_exam.parquet")


if __name__ == "__main__":
    main()
