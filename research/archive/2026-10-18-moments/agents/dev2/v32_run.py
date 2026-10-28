"""V3-2 step 2: every spec simulated on the ticks (tsim32), the settings assembled (entry TF, exits, alignment,
reading), one position at a time inside / outside the windows, and the report (rules R7-R9, 22-24 in DEV_LOG.md).
Reads v32_specs.pkl (v32_build.py). Writes v32_trades.parquet and prints the report.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/v32_run.py > research/2026-10-18-moments/agents/dev2/out_v32.txt
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "precursors"))
import tsim32 as S  # noqa: E402
import v32  # noqa: E402

SLIP = 0.0
TH = "Asia/Bangkok"
WEEKDAYS = {p: int(np.busday_count(a.date(), b.date())) for p, (a, b) in v32.PARTS.items()}


# ------------------------------------------------------------------ simulation
def simulate(df: pd.DataFrame, how: str, tk: S.Ticks) -> pd.DataFrame:
    """One row per spec that fills. how: 'a' / 'b' (R7), 'e3_ext' / 'e3_mirror' (R6), 'base' (#25 in my sim)."""
    rows = []
    for r in df.sort_values("t_dec").itertuples(index=False):
        sp = tk.span(int(r.t_dec))
        if sp is None:
            continue
        kw = dict(t_in=int(r.t_dec), side=int(r.side), t_out=int(r.t_out), slip=SLIP)
        if how == "b":
            kw.update(stop=float(r.stop), cands=r.cands, k_r=1.0, default_r=2.0)
        elif how == "a":
            kw.update(stop=float(r.stop), cands=r.cands, k_r=2.0, default_r=None, trail=r.trail)
        elif how == "e3_ext":
            kw.update(stop=float(r.stop_ext), target_r=1.0)
        elif how == "e3_mirror":
            if r.kind3 == "ii":
                kw.update(mirror_of=float(r.mirror_of), target_r=1.0)
            else:
                kw.update(stop_dist=float(r.mirror_dist), target_r=1.0)
        elif how == "base":
            kw.update(stop=float(r.stop), target_r=2.0)
        res = S.sim(*sp, **kw)
        if res is None:
            continue
        d = {k: v for k, v in r._asdict().items() if k not in ("cands", "trail")}
        d.update(res)
        rows.append(d)
    return pd.DataFrame(rows)


def one_at_a_time(T: pd.DataFrame) -> pd.DataFrame:
    """A trade filling before the previous kept trade's exit is dropped."""
    if not len(T):
        return T
    T = T.sort_values("t_fill")
    keep, busy = [], -1
    for i, a, b in zip(T.index, T.t_fill.to_numpy(), T.exit_t.to_numpy()):
        if a < busy:
            continue
        keep.append(i)
        busy = b
    return T.loc[keep]


def scopes(T: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Rule 23: one position at a time inside the windows (the rule) and outside them (information), apart."""
    if not len(T):
        return {"win": T, "out": T}
    return {"win": one_at_a_time(T[T.window != "other"]), "out": one_at_a_time(T[T.window == "other"])}


# ------------------------------------------------------------------ metrics (and a second computation)
def ci_boot(x: np.ndarray, n_boot: int = 4000, seed: int = 7) -> tuple[float, float]:
    if len(x) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    mm = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(1)
    return float(np.quantile(mm, 0.025)), float(np.quantile(mm, 0.975))


def drawdown(pnl: np.ndarray) -> float:
    eq = np.r_[0.0, np.cumsum(pnl)]
    return float((np.maximum.accumulate(eq) - eq).max())


def streak(pnl: np.ndarray) -> int:
    best = cur = 0
    for x in pnl:
        cur = cur + 1 if x <= 0 else 0
        best = max(best, cur)
    return best


def summ(T: pd.DataFrame, part: str | None = None) -> dict:
    if not len(T):
        return dict(n=0)
    T = T.sort_values("t_fill")
    R, pnl = T.R.to_numpy(float), T.pnl.to_numpy(float)
    lo, hi = ci_boot(R)
    se = R.std(ddof=1) / np.sqrt(len(R)) if len(R) > 1 else np.nan
    wd = WEEKDAYS.get(part, WEEKDAYS["P1"] + WEEKDAYS["P2"]) if part else WEEKDAYS["P1"] + WEEKDAYS["P2"]
    return dict(n=len(T), per_day=len(T) / wd, win=float(np.mean(pnl > 0)), R=float(R.mean()), lo=lo, hi=hi,
                nlo=float(R.mean() - 1.96 * se), nhi=float(R.mean() + 1.96 * se), usd=float(pnl.sum()), dd=drawdown(pnl),
                worst=float(pnl.min()), streak=streak(pnl), exits=T.exit.value_counts().to_dict())


def summ2(T: pd.DataFrame) -> tuple:
    """The second computation: plain loops over the rows."""
    rows = sorted(zip(T.t_fill, T.pnl, T.R))
    n = len(rows)
    s_r = 0.0
    wins = 0
    eq = peak = dd = 0.0
    cur = best = 0
    for _, p, r in rows:
        s_r += r
        wins += p > 0
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        cur = cur + 1 if p <= 0 else 0
        best = max(best, cur)
    return n, s_r / n if n else np.nan, wins / n if n else np.nan, dd, best


CHECKS = {"cells": 0, "equal": 0}


def line(T: pd.DataFrame, part: str | None) -> str:
    s = summ(T, part)
    if s["n"] == 0:
        return "n    0"
    n2, r2, w2, dd2, st2 = summ2(T)
    CHECKS["cells"] += 1
    CHECKS["equal"] += int(n2 == s["n"] and abs(r2 - s["R"]) < 1e-9 and abs(w2 - s["win"]) < 1e-12
                           and abs(dd2 - s["dd"]) < 1e-6 and st2 == s["streak"])
    ex = " ".join(f"{k}:{v}" for k, v in sorted(s["exits"].items()))
    return (f"n {s['n']:4d} ({s['per_day']:.2f}/wd) win {s['win']:.2f} R {s['R']:+.3f} [{s['lo']:+.2f},{s['hi']:+.2f}]"
            f" (norm {s['nlo']:+.2f},{s['nhi']:+.2f}) USD {s['usd']:+8.1f} DD {s['dd']:6.1f} worst {s['worst']:+6.1f}"
            f" streak {s['streak']:2d} | {ex}")


def by_part(T: pd.DataFrame, label: str, indent: str = "  ") -> None:
    for p in ("P1", "P2"):
        print(f"{indent}{label:34s} {p} {line(T[T.part == p], p)}")
    print(f"{indent}{label:34s} P* {line(T, None)}")


def weekly(T: pd.DataFrame) -> pd.DataFrame:
    th = pd.DatetimeIndex(pd.to_datetime(T.t_fill, utc=True)).tz_convert(TH)
    wk = (th.normalize() - pd.to_timedelta(th.dayofweek, unit="D")).tz_localize(None)
    g = T.assign(week=wk.date).groupby("week", sort=True)
    W = pd.DataFrame({"trades": g.size(), "win": g.pnl.agg(lambda x: (x > 0).mean()).round(2), "R_trade": g.R.mean().round(3),
                      "R": g.R.sum().round(2), "usd": g.pnl.sum().round(1), "worst": g.pnl.min().round(1)})
    W["usd_total"] = W.usd.cumsum().round(1)
    return W


def loser_reason(T: pd.DataFrame) -> pd.Series:
    """R10: wrong way (best excursion < 0.5 R before the exit), ran later (1 R our way within 60 min after the exit),
    no run."""
    risk = T.risk.to_numpy(float)
    wrong = T.mfe.to_numpy(float) < 0.5 * risk
    later = T.after_best.to_numpy(float) >= risk
    return pd.Series(np.where(wrong, "wrong way", np.where(later, "ran later", "no run")), index=T.index)


# ------------------------------------------------------------------ assembly
def main() -> None:
    S.idle = None
    t_start = time.time()
    with open(HERE / "v32_specs.pkl", "rb") as f:
        pk = pickle.load(f)
    sp, (q1, q2) = pk["specs"], pk["q"]
    print(f"R2 terciles (P1, in the windows): q1 {q1:.3f}, q2 {q2:.3f}; weekdays P1 {WEEKDAYS['P1']}, P2 {WEEKDAYS['P2']}; slip {SLIP}")
    tk = S.Ticks()
    sims: dict[tuple, pd.DataFrame] = {}
    for key, df in sp.items():
        if key in ("rec", "tur", "levels") or not len(df):
            continue
        hows = ("a", "b") if key[:2] in ("e1", "e2", "e4") else ("e3_ext", "e3_mirror") if key.startswith("e3") else ("base",)
        for how in hows:
            T = simulate(df, how, tk)
            T["key"], T["how"] = key, how
            sims[(key, how)] = T
            print(f"simulated {key:20s} {how:9s} {len(df):5d} specs -> {len(T):5d} fills ({time.time() - t_start:.0f} s)", flush=True)

    def tfset(prefix: str, suffix: str, how: str, tfs: str) -> pd.DataFrame:
        parts = []
        for tf in v32.ENTRY_TFS:
            T = sims.get((f"{prefix}_{tf}{suffix}", how))
            if T is None or not len(T):
                continue
            if tfs == "vol":
                if prefix == "e3":
                    T = T[(T.src == "everyone") | (v32.choose_tf(T.H.to_numpy(float), q1, q2) == tf)]
                else:
                    T = T[v32.choose_tf(T.H.to_numpy(float), q1, q2) == tf]
            elif tfs != tf:
                continue
            parts.append(T)
        if not parts:
            return pd.DataFrame()
        T = pd.concat(parts, ignore_index=True)
        if prefix == "e3" and tfs == "vol":  # an everyone-sees event appears once per TF file: keep one
            T = T.sort_values(["t_dec", "side", "prio"]).drop_duplicates(["t_dec", "side"], keep="first")
        return T

    settings = []
    for tfs in ("vol", "M1", "M5", "M15"):
        for how in ("a", "b"):
            settings.append(("E1", f"tf {tfs} exit {how}", tfset("e1", "", how, tfs)))
        for how in ("a", "b"):
            for what in ("bias", "label"):
                for mode in ("path", "bar"):
                    settings.append(("E2", f"tf {tfs} exit {how} {what} {mode}", tfset("e2", f"_{what}_{mode}", how, tfs)))
                    settings.append(("E4", f"tf {tfs} exit {how} {what} {mode}", tfset("e4", f"_{what}_{mode}", how, tfs)))
        for how in ("e3_ext", "e3_mirror"):
            settings.append(("E3", f"tf {tfs} stop {how[3:]}", tfset("e3", "", how, tfs)))
    MAIN = {"E1": "tf vol exit a", "E2": "tf vol exit a bias path", "E3": "tf vol stop ext", "E4": "tf vol exit a bias path"}
    print(f"\nsettings tried: {len(settings)} (E1 {sum(s[0] == 'E1' for s in settings)}, E2 {sum(s[0] == 'E2' for s in settings)},"
          f" E3 {sum(s[0] == 'E3' for s in settings)}, E4 {sum(s[0] == 'E4' for s in settings)}) + the base rate")

    allT = []
    for etype in ("E1", "E2", "E3", "E4"):
        print(f"\n================ {etype}: every setting, INSIDE the windows (one position at a time) ================")
        for e, name, T in settings:
            if e != etype:
                continue
            sc = scopes(T)
            mark = "  <- main" if name == MAIN[etype] else ""
            for p in ("P1", "P2"):
                x = sc["win"]
                print(f"  {name:30s} {p} {line(x[x.part == p] if len(x) else x, p)}{mark if p == 'P1' else ''}")
            x = sc["win"]
            print(f"  {name:30s} P* {line(x, None)}")
            for scope, x in sc.items():
                if len(x):
                    allT.append(x.assign(etype=etype, setting=name, scope=scope))
        print(f"\n---- {etype}: every setting, OUTSIDE the windows (information; one position at a time among them)")
        for e, name, T in settings:
            if e != etype:
                continue
            x = scopes(T)["out"]
            print(f"  {name:30s} P1 {line(x[x.part == 'P1'] if len(x) else x, 'P1')}")
            print(f"  {name:30s} P2 {line(x[x.part == 'P2'] if len(x) else x, 'P2')}")

    A = pd.concat(allT, ignore_index=True)
    # ---- the main variants in detail
    for etype, name in MAIN.items():
        M = A[(A.etype == etype) & (A.setting == name) & (A.scope == "win")]
        print(f"\n================ {etype} main ({name}), inside the windows: the splits ================")
        by_part(M, "all")
        for w in v32.WINDOWS:
            by_part(M[M.window == w], f"window {w}")
        for b in sorted(x for x in M.bucket.unique() if x):
            by_part(M[M.bucket == b], f"NY open bucket {b}")
        for tf in v32.ENTRY_TFS:
            by_part(M[M.tf == tf], f"entry TF {tf}")
        for col in ("src_side", "src_side_bias", "src_side_bar", "src_side_bias_bar"):
            for v in ("with", "none", "against", "unknown"):
                x = M[M[col] == v]
                if len(x):
                    by_part(x, f"{col} {v}")
        if etype == "E1":
            for col in ("al_label", "al_bias", "al_label_bar", "al_bias_bar", "line", "first"):
                for v in (True, False):
                    by_part(M[M[col] == v], f"{col} {v}")
        if etype == "E2":
            for v in (True, False):
                by_part(M[M.fib == v], f"base on an H1 Fibonacci level {v}")
        if etype == "E3":
            for src in ("box", "everyone"):
                for k3 in ("i", "ii"):
                    by_part(M[(M.src == src) & (M.kind3 == k3)], f"{src} ({k3})")
            O = A[(A.etype == etype) & (A.setting == name) & (A.scope == "out")]
            by_part(O, "OUTSIDE the windows")
        for v in (-1, 1):
            by_part(M[M.side == v], "sell" if v < 0 else "buy")
        L = M[M.pnl <= 0]
        if len(L):
            rs = loser_reason(L)
            print(f"  losers by reason: {rs.value_counts().to_dict()} (of {len(L)})")
        print(f"  week by week (Thai weeks), {etype} main:")
        print(weekly(M).to_string())

    # ---- E1 against the base rate
    print("\n================ E1 against the base rate (#25, the levels everyone sees) ================")
    print("  the strategist: -0.221 / -0.390 (M1 + mlib costs, 41 / 47 trades); ticks spread only -0.218 / -0.380 (PROPOSALS row 39)")
    B = sims.get(("base25", "base"), pd.DataFrame())
    for scope, x in scopes(B).items():
        by_part(x, f"#25 in my simulator, {scope}")
    by_part(B, "#25 in my simulator, all hours, each alone")

    # ---- the four together
    print("\n================ the four main variants together, one position at a time, inside the windows ================")
    parts = [A[(A.etype == e) & (A.setting == n) & (A.scope == "win")] for e, n in MAIN.items()]
    C = one_at_a_time(pd.concat(parts, ignore_index=True))
    by_part(C, "combined")
    for e in MAIN:
        by_part(C[C.etype == e], f"combined: of which {e}")
    print(weekly(C).to_string())

    print(f"\nsecond computation of n / R / win / DD / streak: {CHECKS['equal']} of {CHECKS['cells']} cells equal")
    keep = [c for c in A.columns if A[c].dtype != object or c in ("window", "bucket", "part", "tf", "src", "etype", "setting",
                                                                   "scope", "exit", "kind3", "ev", "lvl", "tag", "how", "key",
                                                                   "align", "mode", "open", "src_side", "src_side_bias",
                                                                   "src_side_bar", "src_side_bias_bar", "src_trend",
                                                                   "src_trend_bias", "src_trend_bar", "src_trend_bias_bar")]
    A[keep].to_parquet(HERE / "v32_trades.parquet")
    B.drop(columns=[c for c in B.columns if B[c].dtype == object and c not in ("window", "part", "exit", "lvl")]).to_parquet(HERE / "v32_base25.parquet")
    print(f"done in {time.time() - t_start:.0f} s")


if __name__ == "__main__":
    main()
