"""At a level with the volume: the break (notes.md, written before it is computed; owner, 2026-10-19: "trade at support /
resistance, never mid-price except a pullback"; "select the good signals and the setups where we have the edge"). At
each M1 close (m1_features.parquet, closed bars only): support + the volume -> sell the break, resistance + the volume
-> buy it; the trade on the real ticks (surrender.trade), at most 3 a UTC day; the losers sorted by reason.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/sr_break.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from surrender import active, trade  # noqa: E402

TARGET, HOLD_MIN, PER_DAY, LAST_MIN, AFTER_MIN = 10.0, 30, 3, 30, 60
STOPS = (3.0, 5.0)
SURRENDER = ((None, None), (3, 2.0), (5, 3.0))  # (K minutes, Y USD)
SIDES = ("sells", "buys", "both")
HOURS = ("all", "active")
NS_MIN = 60 * 10**9


def edges(P1: pd.DataFrame) -> dict[str, float]:
    """The quintile edges of the learning part P1 (a level = an end fifth, the volume = the top fifth)."""
    q = lambda c, p: float(np.nanquantile(P1[c].to_numpy(float), p))  # noqa: E731
    return dict(m15_lo=q("m15_pos", 0.2), m15_hi=q("m15_pos", 0.8), pdl_lo=q("to_pdl", 0.2), pdh_hi=q("to_pdh", 0.8),
                v1=q("vol1", 0.8), v3=q("vol3", 0.8))


def side(X: pd.DataFrame, E: dict[str, float]) -> np.ndarray:
    """-1 at support with the volume (sell the break), +1 at resistance with the volume (buy it), 0 otherwise or at both."""
    sup = (X.m15_pos <= E["m15_lo"]) | (X.to_pdl <= E["pdl_lo"]) | (X.break60 == -1)
    res = (X.m15_pos >= E["m15_hi"]) | (X.to_pdh >= E["pdh_hi"]) | (X.break60 == 1)
    vol = (X.vol1 >= E["v1"]) | (X.vol3 >= E["v3"])
    return np.where(vol & sup & ~res, -1, np.where(vol & res & ~sup, 1, 0))


def after(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, entry: float, side_: int,
          x: float = TARGET, minutes: int = AFTER_MIN) -> str:
    """What came in the `minutes` after the entry tick, whatever the trade did: 'wrong way' (x against first), 'ran
    later' (x our way first), 'no run' (neither)."""
    f = int(np.searchsorted(t, t0, side="left"))
    end = int(np.searchsorted(t, t[f] + minutes * NS_MIN, side="left")) if f < len(t) else f
    fav = (bid[f + 1:end] - entry) if side_ > 0 else (entry - ask[f + 1:end])
    up, dn = np.nonzero(fav >= x)[0], np.nonzero(fav <= -x)[0]
    a, b = (up[0] if len(up) else len(fav)), (dn[0] if len(dn) else len(fav))
    return "ran later" if a < b else "wrong way" if b < a else "no run"


def reason(kind: str, struct: int, side_: int) -> str:
    """The loser's reason: what came after x the M15 structure at the entry against the side."""
    ctx = "M15 against" if struct == -side_ else "M15 with" if struct == side_ else "M15 none"
    return f"{kind} / {ctx}"


def take(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, D: pd.DataFrame, sd: np.ndarray, day_end: int, stop: float,
         k: int | None, y: float | None) -> list[dict]:
    """One UTC day: the signals in time order, one position at a time, at most PER_DAY trades, none in the day's last
    LAST_MIN minutes."""
    rows, busy = [], -1
    for r, s_ in zip(D.itertuples(), sd):
        if s_ == 0 or len(rows) >= PER_DAY:
            continue
        t0 = pd.Timestamp(r.t).value + NS_MIN  # the next M1 bar's open
        if t0 <= busy or t0 > day_end - LAST_MIN * NS_MIN:
            continue
        x = trade(t, bid, ask, t0, int(s_), k, y, target=TARGET, stop=stop, hold_min=HOLD_MIN)
        if x is None:
            continue
        x.update(t=r.t, t0=t0, part=r.part, R=x["pnl"] / stop, m15_struct=int(r.m15_struct))
        x["after"] = after(t, bid, ask, t0, x["entry"], int(s_))
        rows.append(x)
        busy = x["exit_t"]
    return rows


def summary(T: pd.DataFrame, a: str, b: str) -> str:
    import wf  # noqa: PLC0415

    if T.empty:
        return "no trades"
    eq = T.pnl.cumsum()
    return (f"{len(T)} trades ({len(T) / np.busday_count(a, b):.2f} a weekday), win {(T.exit == 'win').mean():.3f}, R {T.R.mean():+.3f}, "
            f"USD {T.pnl.sum():+.1f}, max DD {(eq.cummax() - eq).max():.1f}, worst {T.pnl.min():+.2f}, streak "
            f"{wf.longest_run(T.pnl.to_numpy() < 0)}, exits {T.exit.value_counts().to_dict()}")


def run(X: pd.DataFrame, E: dict[str, float], configs: list[tuple]) -> dict[tuple, pd.DataFrame]:
    from tick_straddle import day_ticks  # noqa: PLC0415

    base = side(X, E)
    act = active(X)
    days = pd.DatetimeIndex(X.t).normalize()
    rows = {c: [] for c in configs}
    for day in days.unique():  # each day's ticks read once, every setting run on them
        tk = day_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        k_day = days == day
        D = X[k_day]
        day_end = (day + pd.Timedelta(days=1)).value
        for c in configs:
            sname, hours, stop, k, y = c
            sd = base[k_day]
            sd = np.where(sd < 0, sd, 0) if sname == "sells" else np.where(sd > 0, sd, 0) if sname == "buys" else sd
            if hours == "active":
                sd = np.where(act[k_day], sd, 0)
            rows[c] += take(t, bid, ask, D, sd, day_end, stop, k, y)
    return {c: pd.DataFrame(v) for c, v in rows.items()}


def main() -> None:
    import wf  # noqa: PLC0415
    from m15_trades import PARTS  # noqa: PLC0415

    X = pd.read_parquet(HERE / "m1_features.parquet").sort_values("t").reset_index(drop=True)
    E = edges(X[X.part == "P1"])
    print("edges (P1):", {k: round(v, 3) for k, v in E.items()})
    configs = [(s, hr, st, k, y) for s in SIDES for hr in HOURS for st in STOPS for k, y in SURRENDER]
    L = X[X.part.isin(["P1", "P2"])]
    sd = side(L, E)
    print(f"signal minutes: sell {(sd < 0).sum()} / buy {(sd > 0).sum()} of {len(L)}")
    res = run(L, E, configs)
    score = {}
    for c in configs:
        T = res[c]
        for p in ("P1", "P2"):
            Tp = T[T.part == p] if not T.empty else T
            print(f"{c[0]} | {c[1]} | stop {c[2]:.0f} | surrender {c[3]}m / {c[4]} | {p}: {summary(Tp, *PARTS[p])}", flush=True)
        if not T.empty and {"P1", "P2"} <= set(T.part):
            score[c] = min(T[T.part == "P1"].R.mean(), T[T.part == "P2"].R.mean())
    best = max(score, key=score.get)
    print(f"\nbest on the learning parts: {best} (the smaller R of P1 / P2 {score[best]:+.3f})")
    T = res[best]
    T["reason"] = [reason(a, s_, d) for a, s_, d in zip(T["after"], T.m15_struct, T.side)]
    T["cell"] = " ".join(str(v) for v in best)
    T.to_parquet(HERE / "sr_break_trades.parquet")
    Lz = T[T.pnl < 0]
    print(f"\nthe best setting's losers by reason ({len(Lz)} of {len(T)} trades):")
    for p in ("P1", "P2"):
        print(p, Lz[Lz.part == p].reason.value_counts().to_dict())
    print("all trades, by what came after x the M15 structure (count, win, R):")
    print(T.groupby("reason").agg(n=("R", "size"), win=("exit", lambda e: (e == "win").mean()), R=("R", "mean")).round(3).to_string())
    if score[best] <= 0:
        print("\nnothing is positive in both learning parts: the exam is not read")
        return
    if sys.argv[1:] != ["exam"]:
        return
    Xe = X[X.part == "exam"]
    Te = run(Xe, E, [best])[best]
    print(f"THE EXAM, once (ticks to 2026-10-14): {summary(Te, '2026-04-20', '2026-10-15')}")
    Te["cell"] = T.cell.iloc[0]
    pd.set_option("display.width", 220)
    print(wf.weekly(Te).to_string(index=False))
    Te.to_parquet(HERE / "sr_break_exam.parquet")


if __name__ == "__main__":
    main()
