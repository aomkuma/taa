"""Task P2: where the pattern trades pay and where they do not - every variant split by what was there (the side, the
family, the TF, the family x TF, the level kind, the other TF, big against normal, news, the session of the entry), P1
and P2 side by side (news cost 0), with the count of cells looked at. Descriptive: a cell positive in both parts is a
candidate for a rule to be written down and tested, not a result.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p2_splits.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from p2_trades import stats  # noqa: E402

MIN_N = 20  # a cell with fewer trades in a part is shown but not flagged


def session(t_ns: pd.Series) -> pd.Series:
    """The session of the entry by the UTC hour: Asia 23-07, London 07-12, New York 12-21, late 21-23."""
    h = pd.to_datetime(t_ns, utc=True).dt.hour
    return pd.Series(pd.cut(h, [-1, 6, 11, 20, 22, 23], labels=["Asia", "London", "New York", "late", "Asia "]), index=t_ns.index
                     ).astype(str).str.strip()


def splits(D: pd.DataFrame) -> pd.DataFrame:
    D = D.assign(side_name=D.side.map({1: "buy", -1: "sell"}), fam_tf=D.family + " " + D.tf, session=session(D.entry_t))
    rows = []
    for by in ("side_name", "family", "tf", "fam_tf", "level_kind", "agree", "big", "news", "session"):
        for key, G in D.groupby(by):
            s = {p: stats(G[G.part == p], p) for p in ("P1", "P2")}
            n1, n2 = s["P1"].get("n", 0), s["P2"].get("n", 0)
            r1, r2 = s["P1"].get("R", float("nan")), s["P2"].get("R", float("nan"))
            rows.append(dict(by=by, group=str(key), n_P1=n1, R_P1=r1, n_P2=n2, R_P2=r2, smaller=min(r1, r2),
                             usd=G.pnl.sum(), both=bool(n1 >= MIN_N and n2 >= MIN_N and r1 > 0 and r2 > 0)))
    return pd.DataFrame(rows)


def main() -> None:
    A = pd.read_parquet(HERE / "p2_trades.parquet")
    pd.set_option("display.width", 220)
    total = 0
    for v in ("A", "B1", "B2"):
        S = splits(A[(A.variant == v) & (A.news_cost == 0.0)])
        total += len(S)
        print(f"\n== {v}: {len(S)} cells")
        print(S.round(3).to_string(index=False))
        F = S[S.both]
        print(f"   positive in both parts with >= {MIN_N} trades in each: "
              + ("; ".join(f"{r.by}={r.group} ({r.R_P1:+.3f} / {r.R_P2:+.3f})" for r in F.itertuples()) or "none"))
    print(f"\ncells looked at in all: {total} (3 variants)")
    L = A[(A.news_cost == 0.0) & (A.pnl < 0)]
    print("\n== the losers' reasons: the share of each variant's losers per part")
    R = L.groupby(["variant", "part"]).reason.value_counts(normalize=True).unstack().round(2)
    print(R.to_string())
    print("\n== what came after, all trades (not only the losers): the share that went one risk our way first")
    for (v, p), G in A[A.news_cost == 0.0].groupby(["variant", "part"]):
        win = G[G.pnl > 0]
        print(f"  {v} {p}: losers that ran our way first (exited too early) {int((L[(L.variant == v) & (L.part == p)].reason.str.startswith('ran later')).sum())}"
              f" of {int((G.pnl < 0).sum())}; winners {len(win)}, their mean R {win.R.mean():+.2f}; losers' mean R "
              f"{G[G.pnl < 0].R.mean():+.2f}")


if __name__ == "__main__":
    main()
