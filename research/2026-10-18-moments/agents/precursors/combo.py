"""Two-state combinations across timeframes (design only, notes.md item 4): the run lift and the side, with a null
that keeps the day-level clustering (labels of whole days swapped within the half-year for the lift; a random sign
per day for the side) to count how many cells pass by chance.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/combo.py [10|5]
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

from plib import HERE

X = int(sys.argv[1]) if len(sys.argv) > 1 else 10
P = f"x{X}"
DH = ["H1", "H2", "H3", "H4", "H5"]
MIN_N, MIN_DAYS = 300, 30


def prepare() -> tuple[pd.DataFrame, list[str]]:
    cols = ["half", "win", "atr15_u", f"{P}_next_up", f"{P}_next_dn", f"{P}_first", "box_brk", "box_now", "sweep",
            "stair", "spike", "day_brk", "yday_brk", "asia_brk", "x72", "M1_atr_pct", "M15_atr_pct", "H1_atr_pct",
            "M5_bbw_pct", "M15_bbw_pct", "H1_bbw_pct", "M15_pos20", "H1_pos20", "H4_pos20", "tvr", "rng30", "mom15",
            "mom60", "pos72"]
    cols += [f"{tf}_{k}" for tf in ("M1", "M5", "M15", "M30", "H1", "H4") for k in ("tide", "struct", "phase", "brk3")]
    D = pd.read_parquet(HERE / "decisions.parquet", columns=cols)
    D = D[D.half.isin(DH)].copy()
    D["run"] = (D[f"{P}_next_up"] | D[f"{P}_next_dn"]).astype(float)
    f = D[f"{P}_first"]
    D["first"] = f.where(f != 0)
    D["day"] = D.index.normalize()
    D["adec"] = D.groupby("half").atr15_u.transform(lambda s: pd.qcut(s.rank(method="first"), 10, labels=False))
    feats = ["win"]
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4"):
        for k in ("tide", "struct", "phase", "brk3"):
            D[f"c_{tf}_{k}"] = D[f"{tf}_{k}"].fillna(0).astype(int)
            feats.append(f"c_{tf}_{k}")
    for k in ("box_brk", "box_now", "sweep", "stair", "spike", "day_brk", "yday_brk", "asia_brk", "x72"):
        D[f"c_{k}"] = D[k].fillna(0).astype(int)
        feats.append(f"c_{k}")
    for k in ("M1_atr_pct", "M15_atr_pct", "H1_atr_pct", "M5_bbw_pct", "M15_bbw_pct", "H1_bbw_pct", "M15_pos20",
              "H1_pos20", "H4_pos20", "tvr", "rng30", "mom15", "mom60", "pos72"):
        q = pd.qcut(D[k].rank(method="first"), 5, labels=False)
        D[f"q_{k}"] = q.fillna(-1).astype(int)
        feats.append(f"q_{k}")
    D["win"] = D["win"].astype("category").cat.codes
    return D, feats


def scan(D: pd.DataFrame, feats: list[str], run: np.ndarray, first: np.ndarray, exp: np.ndarray) -> pd.DataFrame:
    base = pd.DataFrame({"half": D.half.to_numpy(), "day": D.day.to_numpy(), "run": run, "exp": exp,
                         "fup": (first > 0).astype(float), "fok": np.isfinite(first).astype(float)})
    base.loc[base.fok == 0, "fup"] = np.nan
    out = []
    for a, b in itertools.combinations(feats, 2):
        g = base.assign(a=D[a].to_numpy(), b=D[b].to_numpy())
        tot = g.groupby(["a", "b"]).agg(n=("run", "size"), days=("day", "nunique"), run=("run", "mean"), exp=("exp", "mean"),
                                        up=("fup", "mean"), nf=("fup", "count"))
        tot = tot[(tot.n >= MIN_N) & (tot.days >= MIN_DAYS)]
        if tot.empty:
            continue
        ph = g.groupby(["a", "b", "half"]).agg(run=("run", "mean"), exp=("exp", "mean"), up=("fup", "mean"),
                                               n=("run", "size"))
        ph = ph[ph.n >= 30]
        ph["lift"] = ph.run / ph.exp
        lift_up = (ph.lift >= 1.3).groupby(level=[0, 1]).sum()
        side_up = (ph.up >= 0.56).groupby(level=[0, 1]).sum()
        side_dn = (ph.up <= 0.44).groupby(level=[0, 1]).sum()
        tot = tot.join(lift_up.rename("n_lift")).join(side_up.rename("n_up")).join(side_dn.rename("n_dn"))
        tot = tot.fillna(0)
        tot["lift"] = tot.run / tot.exp
        tot["fa"], tot["fb"] = a, b
        halves = ph.lift.unstack("half").reindex(columns=DH)
        uph = ph.up.unstack("half").reindex(columns=DH)
        tot["lift_h"] = [" ".join(f"{v:.2f}" for v in halves.loc[i]) if i in halves.index else "" for i in tot.index]
        tot["up_h"] = [" ".join(f"{v:.2f}" for v in uph.loc[i]) if i in uph.index else "" for i in tot.index]
        out.append(tot.reset_index())
    return pd.concat(out, ignore_index=True)


def null_labels(D: pd.DataFrame, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Whole days' run labels moved to another day of the same half (same window and minute position); the side
    flipped by a random sign per day."""
    pos = D.groupby(["day", "win"]).cumcount().to_numpy()
    key = pd.DataFrame({"half": D.half.to_numpy(), "day": D.day.to_numpy(), "win": D.win.to_numpy(), "pos": pos,
                        "run": D.run.to_numpy()})
    days = key[["half", "day"]].drop_duplicates()
    src = []
    for _h, x in days.groupby("half"):
        src.append(pd.DataFrame({"day": x.day.to_numpy(), "src": rng.permutation(x.day.to_numpy())}))
    m = key.merge(pd.concat(src), on="day", how="left")
    lab = key.rename(columns={"day": "src", "run": "run_src"})[["src", "win", "pos", "run_src"]]
    m = m.merge(lab, on=["src", "win", "pos"], how="left")
    run = m.run_src.to_numpy()
    sign = pd.Series(rng.choice([-1.0, 1.0], size=D.day.nunique()), index=D.day.unique())
    first = D["first"].to_numpy() * sign.reindex(D.day).to_numpy()
    return run, first


def main() -> None:
    D, feats = prepare()
    exp = D.groupby(["half", "win", "adec"]).run.transform("mean").to_numpy()
    R = scan(D, feats, D.run.to_numpy(), D["first"].to_numpy(), exp)
    R.to_parquet(HERE / f"combo_{X}.parquet")
    print(f"=== X = {X} U, two-state cells with n >= {MIN_N} minutes on >= {MIN_DAYS} days: {len(R)} ===")
    pl = R[R.n_lift >= 4]
    ps = R[(R.n_up >= 4) | (R.n_dn >= 4)]
    print(f"real: run lift >= 1.3 in >= 4/5 halves: {len(pl)}; side >= 56 % in >= 4/5: {len(ps)}")
    rng = np.random.default_rng(7)
    for s in range(3):
        run, first = null_labels(D, rng)
        ok = np.isfinite(run)
        Dn = D[ok]
        expn = pd.Series(run[ok]).groupby([Dn.half.to_numpy(), Dn.win.to_numpy(), Dn.adec.to_numpy()]).transform("mean")
        N = scan(Dn, feats, run[ok], first[ok], expn.to_numpy())
        print(f"null {s}: cells {len(N)}; lift passes {int((N.n_lift >= 4).sum())}; side passes "
              f"{int(((N.n_up >= 4) | (N.n_dn >= 4)).sum())}", flush=True)
    cols = ["fa", "a", "fb", "b", "n", "days", "run", "lift", "lift_h", "up", "up_h"]
    print("\n-- real cells passing the run lift (top 40 by lift) --")
    print(pl.sort_values("lift", ascending=False)[cols].head(40).round(3).to_string(index=False))
    print("\n-- real cells passing the side (all) --")
    print(ps.sort_values("up")[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
