"""Task P4, item 3: why the NY window (09:30 - 11:30 NY) loses - W's trades split by what was there, NY against Asia /
London, per part: the paths (MAE / MFE from the fill), the family, the level kind, the M5 and M15 structure at the entry
(with / against the trade), the news minutes (a release in the 60 minutes before the entry; one inside the trade), the
minutes after the open. Descriptive; the change it leads to is written in DEV_LOG.md before it is run.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p4_ny.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_trades as T3  # noqa: E402,F401  (puts the dev folder on the path)
import p2_trades as P2  # noqa: E402
import patterns as P  # noqa: E402
from p3_paths import path_stats  # noqa: E402
from p4_trades import SmallTicks  # noqa: E402

NS_MIN = 60 * 10**9


def rel_struct(structure: str, side: int) -> str:
    """A TF's structure as it stands, relative to the trade: 'with' (up for a buy, down for a sell), 'against', else
    'mixed / none'."""
    if structure in ("up", "down"):
        return "with" if (structure == "up") == (side > 0) else "against"
    return "mixed / none"


def news_flags(t_entry: int, t_limit: int, news: np.ndarray) -> tuple[bool, bool]:
    """(a release minute in the 60 minutes before the entry decision, a release minute after it and before the time
    limit)."""
    before = bool(((news >= t_entry - 60 * NS_MIN) & (news <= t_entry)).any())
    inside = bool(((news > t_entry) & (news < t_limit)).any())
    return before, inside


def main() -> None:
    A = pd.read_parquet(HERE / "p4_trades_W_WL.parquet")
    W = A[(A.variant == "W") & (A.news_cost == 0.0)].reset_index(drop=True)
    m = P.load_m1()
    tf5, tf15 = P.TF(m, 5), P.TF(m, 15)
    news = P2.news_times()
    ticks = SmallTicks()
    rows = []
    for r in W.itertuples(index=False):
        t, bid, ask = ticks.span(r.t_entry)
        ps = path_stats(t, bid, ask, r.entry_t, r.entry, r.side, r.risk, r.t_limit)
        s5 = P.m_structure(tf5.piv, tf5.last_complete(r.t_entry))
        s15 = P.m_structure(tf15.piv, tf15.last_complete(r.t_entry))
        nb, ni = news_flags(r.t_entry, r.t_limit, news)
        ny = pd.Timestamp(int(r.t_entry), tz="UTC").tz_convert("America/New_York")
        after = ny.hour * 60 + ny.minute - (9 * 60 + 30)
        rows.append(dict(**ps, m5=rel_struct(s5, r.side), m15=rel_struct(s15, r.side), news_before=nb, news_inside=ni,
                         after_open=after if r.window == "NY" else np.nan))
    W = pd.concat([W, pd.DataFrame(rows)], axis=1)
    W["open_bucket"] = pd.cut(W.after_open, [-1, 29, 59, 120], labels=["0-30 min", "30-60 min", "60-120 min"]).astype(str)
    W.to_parquet(HERE / "p4_ny_context.parquet")
    pd.set_option("display.width", 220)

    def tab(by: str, D: pd.DataFrame) -> None:
        g = D.groupby(["part", by]).agg(n=("R", "size"), R=("R", "mean"), usd=("pnl", "sum"), win=("pnl", lambda s: (s > 0).mean()))
        print(g.round(3).to_string())

    print("== the paths by window (medians; shares)")
    print(W.groupby(["part", "window"]).agg(n=("R", "size"), R=("R", "mean"), mfe_r=("mfe_r", "median"), mae_r=("mae_r", "median"),
                                              mfe1=("mfe_r", lambda s: (s >= 1).mean()), mae1=("mae_r", lambda s: (s >= 1).mean()),
                                              risk=("risk", "median"), height=("height", "median")).round(2).to_string())
    NY = W[W.window == "NY"]
    rest = W[W.window != "NY"]
    for by in ("family", "level_kind", "m5", "m15", "news_before", "news_inside", "open_bucket", "tf", "side"):
        print(f"\n== NY by {by}")
        tab(by, NY)
        if by in ("m5", "m15", "news_before"):
            print(f"   (Asia + London by {by})")
            tab(by, rest)


if __name__ == "__main__":
    main()
