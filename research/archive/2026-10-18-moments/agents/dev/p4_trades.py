"""Task P4: B2 only in the owner's windows (DEV_LOG.md "Task P4 - written before computing"): Asia 07:00 - 09:00 and
London 13:00 - 14:00 on the Thai clock, New York 09:30 - 11:30 New York time, by the entry decision (B2's confirming
close); outside them no trade. W = the core rule, WL = London 12:30 - 14:30 Thai (an assumption), WN = W with the NY
change (written in DEV_LOG.md before it is run).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p4_trades.py [SETTING ...]
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
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, ExamPeriodError  # noqa: E402

WINDOWS = ("Asia", "London", "NY")


class SmallTicks(P2.Ticks):
    """P2's Ticks keeping only the last few days and spans (the streams run in time order; all of them at once do not
    fit in memory)."""

    KEEP = 4

    def day(self, d):
        x = super().day(d)
        while len(self.days) > self.KEEP:
            self.days.pop(next(iter(self.days)))
        return x

    def span(self, t_ns):
        x = super().span(t_ns)
        while len(self.spans) > self.KEEP:
            self.spans.pop(next(iter(self.spans)))
        return x
def ny_after_ten(t_ns: int) -> bool:
    """10:00 - 10:30 New York time (start included, end excluded): the half hour after the 10:00 NY data minute."""
    ny = pd.Timestamp(int(t_ns), tz="UTC").tz_convert("America/New_York")
    m = ny.hour * 60 + ny.minute + ny.second / 60
    return 600 <= m < 630


def no_ny_ten(cands: pd.DataFrame, tfs: dict) -> pd.DataFrame:
    """WN's change: no NY entry decision from 10:00 to 10:30 NY."""
    keep = [not (w == "NY" and ny_after_ten(t)) for w, t in zip(cands.window, cands.t_entry, strict=True)]
    return cands[keep].reset_index(drop=True)


SETTINGS4 = {"W": dict(pad=0), "WL": dict(pad=30), "WN": dict(pad=0, filter=no_ny_ten)}


def window_of(t_ns: int, london_pad: int = 0) -> str | None:
    """The owner's window of a moment: 'Asia' 07:00 - 09:00 Thai, 'London' 13:00 - 14:00 Thai (+- london_pad minutes),
    'NY' 09:30 - 11:30 New York time; start included, end excluded; None outside."""
    t = pd.Timestamp(int(t_ns), tz="UTC")
    th = t.tz_convert("Asia/Bangkok")
    m = th.hour * 60 + th.minute + th.second / 60 + th.microsecond / 6e7
    if 7 * 60 <= m < 9 * 60:
        return "Asia"
    if 13 * 60 - london_pad <= m < 14 * 60 + london_pad:
        return "London"
    ny = t.tz_convert("America/New_York")
    mn = ny.hour * 60 + ny.minute + ny.second / 60 + ny.microsecond / 6e7
    if 9 * 60 + 30 <= mn < 11 * 60 + 30:
        return "NY"
    return None


def in_windows(cands: pd.DataFrame, london_pad: int) -> pd.DataFrame:
    """The candidates whose entry decision is inside a window, with the window's name."""
    if cands.empty:
        return cands.assign(window=pd.Series(dtype=object))
    w = [window_of(t, london_pad) for t in cands.t_entry]
    out = cands.assign(window=w)
    return out[out.window.notna()].reset_index(drop=True)


def run(names: list[str], cands_filter=None) -> pd.DataFrame:
    """Each setting: B2's candidates (P3's engine), only inside the windows, one position at a time, the four news
    costs; cands_filter(cands, tfs) -> cands is a further condition (the NY change)."""
    from m15_trades import part_of  # noqa: PLC0415

    C = pd.read_parquet(HERE / "p_catches.parquet")
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    m = P.load_m1()
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    ticks, news = SmallTicks(), P2.news_times()
    base = T3.candidates3(C, tfs, T3.SETTINGS["B2"])
    out = []
    for name in names:
        s = SETTINGS4[name]
        cands = in_windows(base, s["pad"])
        if s.get("filter") is not None:
            cands = s["filter"](cands, tfs)
        for cost in P2.NEWS_COSTS:
            T = T3.run_stream3(cands, tfs, ticks, news, cost, "structure")
            T["variant"], T["news_cost"], T["exit_mode"] = name, cost, "structure"
            T["part"] = part_of(pd.to_datetime(T.entry_t, utc=True))
            if (T.exit_t >= EXAM_START.value).any():
                raise ExamPeriodError("a trade reached the exam")
            out.append(T)
        print(f"{name}: {len(cands)} candidates in the windows", flush=True)
    A = pd.concat(out, ignore_index=True)
    A["big"] = (A.height > P2.BIG) | (A.risk > P2.BIG)
    M = A[A.news_cost == 0.0]
    why = []
    for r in M.itertuples(index=False):
        if r.pnl < 0:
            t, bid, ask = ticks.span(r.t_entry)
            why.append(f"{P2.reason(t, bid, ask, r._asdict())} x other TF {r.agree}")
        else:
            why.append("")
    A.loc[M.index, "reason"] = why
    return A


def metrics_by_window(A: pd.DataFrame) -> pd.DataFrame:
    """Per setting x part x news cost: all the windows together, then each window."""
    rows = []
    for (v, p, c), G in A.groupby(["variant", "part", "news_cost"], sort=False):
        for w, H in [("all", G)] + [(w, G[G.window == w]) for w in WINDOWS]:
            s = P2.stats(H, p) if len(H) else dict(n=0)
            for e in T3.ORDER:
                s[f"x_{e}"] = int((H.exit == e).sum())
            rows.append(dict(variant=v, part=p, news_cost=c, window=w, **s))
    return pd.DataFrame(rows)


def main() -> None:
    names = sys.argv[1:] or ["W", "WL"]
    A = run(names)
    tag = "_".join(names)
    A.to_parquet(HERE / f"p4_trades_{tag}.parquet")
    M = metrics_by_window(A)
    M.to_csv(HERE / f"p4_metrics_{tag}.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    cols = ["variant", "window", "part", "n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak",
            "streak_usd", "x_stop", "x_target", "x_structure", "x_time", "x_break"]
    print(M[M.news_cost == 0.0][cols].round(3).to_string(index=False))
    for c in P2.NEWS_COSTS[1:]:
        t = M[(M.news_cost == c) & (M.window == "all")]
        print(f"  news +{c:.1f}: " + "; ".join(f"{r.variant} {r.part} R {r.R:+.3f}" for r in t.itertuples()))
    t = M[(M.news_cost == 0.0) & (M.window == "all")]
    print("the smaller part's R: " + "; ".join(f"{v} {g.R.min():+.3f}" for v, g in t.groupby("variant", sort=False)))


if __name__ == "__main__":
    main()
