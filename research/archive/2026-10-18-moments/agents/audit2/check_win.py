"""Item 1 (the measurer's answer, 2026-10-20): "win" = pnl > 0 after costs. What it moves, on the learning parts only.

Every stored precursors trade file with t / pnl / exit is read with a pyarrow row filter t < 2026-04-18 (no exam row is
read). For each:
  A. the win share per part (older < 2025-10-18, P1, P2): old (exit == "win") and new (pnl > 0); the target exits
     not in profit (must be 0: the old share can only rise);
  B. `wf.weekly` of the code at BASE (git) against the working copy, week by week (every week before the exam):
     every week row whose win moves;
     no other column may move;
  C. `wf.walk_forward`'s month rows, re-derived from the stored taken trades (their `month` column): win old / new;
  D. each file over every row before the exam (what a '(learning)' line prints): win old / new.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_win.py
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[4]
PRE = ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"
sys.path.insert(0, str(PRE))
import wf  # noqa: E402 - the working copy (pnl > 0)

BASE = "eeca5a9"  # the commit before item 1 (exit == "win")
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
P1, P2 = pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC")


def base_wf() -> types.ModuleType:
    src = subprocess.run(  # noqa: S603, S607 - git, our own repo
        ["git", "show", f"{BASE}:research/2026-10-18-moments/agents/precursors/wf.py"], cwd=ROOT, capture_output=True,
        text=True, check=True, encoding="utf-8").stdout
    assert 'g.exit.agg(lambda x: (x == "win").mean())' in src
    mod = types.ModuleType("wf_base")
    mod.__file__ = str(PRE / "wf.py")
    exec(compile(src, "wf_base.py", "exec"), mod.__dict__)  # noqa: S102 - the repo's own file at BASE
    return mod


def learning(f: Path) -> pd.DataFrame:
    T = pq.read_table(f, filters=[("t", "<", EXAM.to_pydatetime())]).to_pandas()
    assert T.empty or T.t.max() < EXAM
    return T.sort_values("t").reset_index(drop=True)


def main() -> None:
    old_wf = base_wf()
    pd.set_option("display.width", 250)
    files = [f for f in sorted(PRE.glob("*.parquet")) if {"t", "pnl", "exit"} <= set(pq.read_schema(f).names)]
    rows, weeks, months, wk_tables, whole = [], [], [], [], []
    for f in files:
        T = learning(f)
        whole.append(dict(file=f.name, rows=len(T), first=str(T.t.min())[:10] if len(T) else "",
                          win_old=(T.exit == "win").mean(), win_new=(T.pnl > 0).mean()))
        part = np.where(T.t < P1, "older", np.where(T.t < P2, "P1", "P2"))
        for p in ("older", "P1", "P2"):
            x = T[part == p]
            if len(x):
                rows.append(dict(file=f.name, part=p, trades=len(x), win_old=(x.exit == "win").mean(),
                                 win_new=(x.pnl > 0).mean(), target_not_profit=int(((x.exit == "win") & (x.pnl <= 0)).sum()),
                                 zero_pnl=int((x.pnl == 0).sum())))
        # B: the weekly table over every row before the exam (the older rows are learning for the 3-year runs)
        L = T if "cell" in T else T.assign(cell=f.stem)
        if len(L) and "R" in L:
            Wo, Wn = old_wf.weekly(L), wf.weekly(L)
            other = [c for c in Wo.columns if c != "win"]
            assert Wo[other].equals(Wn[other]), f.name
            ch = Wo.win != Wn.win
            weeks.append(dict(file=f.name, weeks=len(Wo), changed=int(ch.sum()),
                              rise_max=float((Wn.win - Wo.win).max()), fall=int((Wn.win < Wo.win).sum())))
            if "cell" in T and "month" in T:
                wk_tables.append((f.name, Wo.assign(win_new=Wn.win)[["week", "cell", "trades", "win", "win_new", "R",
                                                                     "usd"]]))
        # C: the month rows of a walk-forward file
        if "month" in T:
            g = T.groupby("month")
            for mo, x in g:
                months.append(dict(file=f.name, month=mo + (" (to 04-17)" if mo == "2026-04" else ""), trades=len(x),
                                   win_old=round((x.exit == "win").mean(), 3), win_new=round((x.pnl > 0).mean(), 3)))
    A = pd.DataFrame(rows)
    A["change"] = A.win_new - A.win_old
    lp = A[A.part != "older"]
    print(f"A. stored trade files: {len(files)}; learning-part cells (P1 / P2): {len(lp)}; changed "
          f"{int((lp.change.abs() > 1e-12).sum())}; unchanged {int((lp.change.abs() <= 1e-12).sum())}; every change >= 0: "
          f"{bool((A.change >= -1e-12).all())}; target exits not in profit: {int(A.target_not_profit.sum())}; "
          f"break-even trades (pnl == 0): {int(A.zero_pnl.sum())}")
    print(f"   change in P1 / P2 cells: min {lp.change.min():+.3f} median {lp.change.median():+.3f} max {lp.change.max():+.3f}")
    old = A[A.part == "older"]
    print(f"   older rows (before 2025-10-18): {len(old)} cells, change min {old.change.min():+.3f} median "
          f"{old.change.median():+.3f} max {old.change.max():+.3f}")
    print(lp.sort_values(["change", "file", "part"], ascending=[False, True, True])
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    W = pd.DataFrame(weeks)
    print(f"\nB. wf.weekly ({BASE} against the working copy) on every week before the exam: {len(W)} files, {int(W.weeks.sum())} "
          f"week rows, changed {int(W.changed.sum())}, fallen {int(W.fall.sum())}; every other column equal")
    print(W.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    for name, t in wk_tables:
        print(f"\n   {name}, week by week (every week before the exam):")
        print(t.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    M = pd.DataFrame(months)
    print(f"\nC. walk_forward month rows (every month before the exam, the stored taken trades): {len(M)}, changed "
          f"{int((M.win_old != M.win_new).sum())}")
    print(M.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    D = pd.DataFrame(whole)
    print(f"\nD. each file, every row before the exam (the printed '(learning)' lines): {len(D)} files, changed "
          f"{int((D.win_old != D.win_new).sum())}")
    print(D.to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
