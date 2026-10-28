"""Checkpoint P5a: L, LEAD, ST and the risk cap (CAP) judged on B2's fixed candidate set - each candidate traded alone
with B2's exit, no one-position rule - then CAP as streams (all hours; the owner's windows W + CAP). The rules: DEV_LOG.md
"Checkpoint P5a - written before computing" (CAP_X from P1's risks only, written before any result).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p5a_filters.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_trades as T3  # noqa: E402  (first: puts the dev folder on the path)
import p2_trades as P2  # noqa: E402
import p4_trades as T4  # noqa: E402
import p5_patterns as F5  # noqa: E402
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, ExamPeriodError  # noqa: E402

CAP_X = 1.90  # the 95th percentile of risk_dec / H1 ATR over B2's P1 trades (1.863), rounded up to 0.05
KEY = ["t_dec", "t_entry", "side", "tf", "family", "name", "stop"]
FILTERS = ("L", "LEAD", "ST", "CAP")
COSTS_ALONE = (0.0, 2.0)


def h1_atr_at(m: pd.DataFrame, t_ns: np.ndarray) -> np.ndarray:
    """The ATR(14) of the last H1 bar complete by each moment t_ns (an H1 bar complete exactly at t counts)."""
    b = P.tf_bars(m, 60)
    return F5.map_to_m1(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, P.atr14(b), np.asarray(t_ns, np.int64))


def member(base: pd.DataFrame, other: pd.DataFrame) -> np.ndarray:
    """For each row of base: is the same candidate (KEY) in other? Equal keys are matched one to one in order."""
    a = base[KEY].assign(_k=base.groupby(KEY, sort=False).cumcount().to_numpy())
    b = other[KEY].assign(_k=other.groupby(KEY, sort=False).cumcount().to_numpy(), _in=True)
    j = a.merge(b, on=[*KEY, "_k"], how="left")
    return j["_in"].eq(True).to_numpy(bool)


def cap_ok(risk_dec: np.ndarray, h1: np.ndarray, x: float = CAP_X) -> np.ndarray:
    """CAP keeps a candidate whose risk at the decision is at most x H1 ATR (no H1 ATR: refused)."""
    risk_dec, h1 = np.asarray(risk_dec, float), np.asarray(h1, float)
    return np.isfinite(h1) & (risk_dec <= x * h1)


def flags(base: pd.DataFrame, sets: dict, h1: np.ndarray) -> pd.DataFrame:
    out = base.assign(h1_atr=h1, CAP=cap_ok(base.risk_dec, h1), window=[T4.window_of(int(t)) for t in base.t_entry])
    for k in ("L", "LEAD", "ST"):
        out[k] = member(base, sets[k])
    return out


def trade_alone(cands: pd.DataFrame, tfs: dict, ticks, news: np.ndarray, costs=COSTS_ALONE,
                trade_fn=T3.one_trade3) -> pd.DataFrame:
    """Every candidate traded on its own (no one-position rule), B2's exit, at each news cost."""
    pivs = {k: P2.last_pivot_prices(tf.piv, len(tf.c)) for k, tf in tfs.items()}
    rows = []
    for i, r in enumerate(cands.itertuples(index=False)):
        t, bid, ask = ticks.span(r.t_entry)
        nt = P2.is_news(r.t_entry, news)
        for cost in costs:
            x = trade_fn(r, tfs[r.tf], *pivs[r.tf], t, bid, ask, cost if nt else 0.0, "structure")
            if x is not None:
                rows.append({**r._asdict(), **x, "news": nt, "news_cost": cost, "cand": i})
    out = pd.DataFrame(rows)
    for k in ("t_be", "t_struct"):
        if k in out:
            out[k] = pd.array([None if v is None or (isinstance(v, float) and np.isnan(v)) else int(v) for v in out[k]],
                              dtype="Int64")
    return out


def judge(T: pd.DataFrame, flag: str) -> list[dict]:
    """Per part: the kept and the refused candidates' trades (n, distinct entry times, win %, R and its 95 % range, USD)."""
    rows = []
    for p, G in T.groupby("part", sort=True):
        for side, H in (("kept", G[G[flag]]), ("refused", G[~G[flag]])):
            s = P2.stats(H, p) if len(H) else dict(n=0)
            rows.append(dict(filter=flag, part=p, group=side, times=int(H.t_entry.nunique()) if len(H) else 0,
                             **{k: s.get(k, np.nan) for k in ("n", "win", "R", "R_lo", "R_hi", "usd")}))
    return rows


def main() -> None:
    from m15_trades import part_of  # noqa: PLC0415

    C = pd.read_parquet(HERE / "p_catches.parquet")
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    m = P.load_m1()
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    ticks, news = T4.SmallTicks(), P2.news_times()
    base = T3.candidates3(C, tfs, T3.SETTINGS["B2"])
    sets = {k: T3.candidates3(C, tfs, T3.SETTINGS[k]) for k in ("L", "LEAD", "ST")}
    F = flags(base, sets, h1_atr_at(m, base.t_entry.to_numpy(np.int64)))
    print(f"B2 candidates {len(F)}; kept by L {int(F.L.sum())} (P3: {len(sets['L'])}), LEAD {int(F.LEAD.sum())} "
          f"({len(sets['LEAD'])}), ST {int(F.ST.sum())} ({len(sets['ST'])}), CAP {int(F.CAP.sum())}", flush=True)
    A = trade_alone(F, tfs, ticks, news)
    A["part"] = part_of(pd.to_datetime(A.entry_t, utc=True))
    if (A.exit_t >= EXAM_START.value).any():
        raise ExamPeriodError("a trade reached the exam")
    A.to_parquet(HERE / "p5a_fixed.parquet")
    S = []
    for name, cands in (("CAP", F[F.CAP]), ("W+CAP", T4.in_windows(F[F.CAP].drop(columns="window"), 0))):
        for cost in P2.NEWS_COSTS:
            T = T3.run_stream3(cands.reset_index(drop=True), tfs, ticks, news, cost, "structure")
            T["variant"], T["news_cost"], T["exit_mode"] = name, cost, "structure"
            T["part"] = part_of(pd.to_datetime(T.entry_t, utc=True))
            if (T.exit_t >= EXAM_START.value).any():
                raise ExamPeriodError("a trade reached the exam")
            S.append(T)
        print(f"{name}: {len(cands)} candidates", flush=True)
    S = pd.concat(S, ignore_index=True)
    S.to_parquet(HERE / "p5a_streams.parquet")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for cost in COSTS_ALONE:
        X = A[A.news_cost == cost]
        J = pd.DataFrame([r for f in FILTERS for r in judge(X, f)])
        Jw = pd.DataFrame([r for f in FILTERS for r in judge(X[X.window.notna()], f)])
        J.assign(news_cost=cost, scope="all").to_csv(HERE / f"p5a_fixed_{cost:.0f}_all.csv", index=False)
        Jw.assign(news_cost=cost, scope="W").to_csv(HERE / f"p5a_fixed_{cost:.0f}_W.csv", index=False)
        print(f"\nTHE FIXED SET, news cost {cost}: every candidate alone ({X.cand.nunique()} candidates with a trade, "
              f"{X.t_entry.nunique()} distinct entry times)")
        print("all of B2: " + "; ".join(f"{p} n {len(G)} R {G.R.mean():+.3f}" for p, G in X.groupby("part")))
        print(J.round(3).to_string(index=False))
        print("\n  inside the owner's windows (W): " +"; ".join(f"{p} n {len(G)} R {G.R.mean():+.3f}"
                                                                for p, G in X[X.window.notna()].groupby("part")))
        print(Jw.round(3).to_string(index=False))
    M = pd.DataFrame([dict(variant=v, part=p, news_cost=c, **P2.stats(G, p))
                      for (v, p, c), G in S.groupby(["variant", "part", "news_cost"], sort=False)])
    M.to_csv(HERE / "p5a_streams_metrics.csv", index=False)
    cols = ["variant", "part", "n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd",
            "x_stop", "x_target", "x_structure", "x_time", "x_break"]
    print("\nTHE STREAMS (one position at a time), news cost 0")
    print(M[M.news_cost == 0.0][cols].round(3).to_string(index=False))
    for c in P2.NEWS_COSTS[1:]:
        t = M[M.news_cost == c]
        print(f"  news +{c:.1f}: " + "; ".join(f"{r.variant} {r.part} R {r.R:+.3f}" for r in t.itertuples()))
    t = M[M.news_cost == 0.0]
    print("the smaller part's R: " + "; ".join(f"{v} {g.R.min():+.3f}" for v, g in t.groupby("variant", sort=False)))


if __name__ == "__main__":
    main()
