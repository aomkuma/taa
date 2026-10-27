"""Where the trend bots' entries actually sit, measured on the price path (journal week 1, 2026-10-27).

The journal's week 1 found the two winning down trades went 0.81 R and 0.38 R *against* the entry before
they ran, which is why a break-even stop destroyed them. That is a statement about the entry, not about
the exit, so this measures the entry itself over the whole history rather than one week:

1. the adverse excursion before a trade works, separately for winners and losers - if winners routinely
   dip most of the way to the stop, the stop is too tight for where the entry is placed;
2. the favourable excursion of the losers - if losers never go anywhere, they are simply wrong and no
   stop width will save them;
3. the counterfactual: the same entry and the same target with a stop k times wider, settled on the real
   M1 path. This answers "widen the stop" with one number per k instead of a parameter sweep.

Every number is split by the window the parameters were fitted on (2025-10-20 .. 2026-10-24) and the
years before it, because a lesson that only holds inside the fit is not a lesson.

    .venv\\Scripts\\python research/2026-10-26-three-bots/geometry.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bots  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIT = (pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-10-24", tz="UTC"))
WIDE = [1.0, 1.25, 1.5, 2.0, 3.0]


def day_end(at: pd.Timestamp) -> pd.Timestamp:
    """``run``'s own deadline for a trade opened at ``at``: 07:00 Bangkok the next morning."""
    th = at.tz_convert(bots.TH)
    return (pd.Timestamp(th.date(), tz=bots.TH) + pd.Timedelta(days=1, hours=7)).tz_convert("UTC")


def path_stats(m1: pd.DataFrame, t: bots.Trade, p: bots.P) -> dict:
    """Walk the real M1 path once and read off everything the entry's geometry needs.

    The counterfactual stops get the SAME DEADLINE the original trade had (07:00 Bangkok the next day,
    and ``max_hours``), not the moment the original happened to exit: the original exited early *because*
    it was stopped, so cutting the wider stop off there would answer the question with itself. The first
    version of this file did exactly that and gave a win rate that did not move with the stop width -
    which is impossible, and is what exposed the mistake.
    """
    x = m1[(m1.index >= t.at) & (m1.index <= t.extra["closed"])]
    if x.empty:
        return {}
    sell = t.side == "SELL"
    risk = abs(t.stop - t.entry)
    hi, lo = x.high.to_numpy(float), x.low.to_numpy(float)
    adverse = (hi.max() - t.entry) if sell else (t.entry - lo.min())
    favour = (t.entry - lo.min()) if sell else (hi.max() - t.entry)
    out = {"mae_r": adverse / risk, "mfe_r": favour / risk, "risk": risk}
    until = day_end(t.at)
    for k in WIDE:
        wider = bots.Trade(
            t.bot, t.side, t.at, t.entry, t.entry + k * risk if sell else t.entry - k * risk, t.tp
        )
        got = bots.settle(m1, wider, until, p)
        out[f"r_x{k}"] = got.r * k  # back into R of the ORIGINAL risk, so the k columns are comparable
        out[f"out_x{k}"] = got.out
    return out


def table(df: pd.DataFrame, title: str) -> None:
    print(f"\n### {title}  ({len(df)} trades)\n")
    if df.empty:
        print("no trades")
        return
    win, lose = df[df.r > 0], df[df.r <= 0]
    print("| group | trades | median MAE (R) | 75th MAE | median MFE (R) | mean R |")
    print("|---|---|---|---|---|---|")
    for name, g in (("winners", win), ("losers", lose), ("all", df)):
        if g.empty:
            continue
        print(
            f"| {name} | {len(g)} | {g.mae_r.median():.2f} | {g.mae_r.quantile(0.75):.2f} | "
            f"{g.mfe_r.median():.2f} | {g.r.mean():+.3f} |"
        )
    print("\n| stop width | mean R a trade | win rate | trades stopped out |")
    print("|---|---|---|---|")
    for k in WIDE:
        col = df[f"r_x{k}"]
        print(f"| x{k} | {col.mean():+.3f} | {(col > 0).mean():.0%} | {(col <= -0.9 * k).sum()} |")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in (Timeframe.M1, Timeframe.H1)}
    m1 = f[Timeframe.M1]
    # exit_mode "tp" for every bot: the stop and the target alone, so the entry is measured without any
    # exit rule layered on top (the configured UP and RANGE bots move to break-even; that is a separate
    # question, and the week-1 journal showed it is the entry that needs answering first).
    p = replace(bots.P(), exit_mode="tp")
    start, end = pd.Timestamp("2023-09-05", tz="UTC"), pd.Timestamp("2026-10-24", tz="UTC")
    trades = bots.run(f, p, start, end)
    rows = []
    for t in trades:
        st = path_stats(m1, t, p)
        if not st:
            continue
        # a stop at x1.0 is the trade run() already settled: if the two disagree this harness is wrong
        if abs(st["r_x1.0"] - t.r) > 1e-6:
            raise SystemExit(
                f"harness disagrees with bots.run on {t.bot} {t.at}: {st['r_x1.0']:+.4f} vs {t.r:+.4f}"
            )
        rows.append({"bot": t.bot, "side": t.side, "at": t.at, "r": t.r, "out": t.out, **st})
    df = pd.DataFrame(rows)
    df["fitted"] = (df["at"] >= FIT[0]) & (df["at"] < FIT[1])  # df.at is pandas own indexer
    print(f"# The entry's geometry, {start.date()} .. {end.date()}\n")
    print(
        f"{len(df)} trades: {int(df.fitted.sum())} inside the fit window, {int((~df.fitted).sum())} outside"
    )
    for bot in ("DOWN", "UP", "RANGE"):
        g = df[df.bot == bot]
        if g.empty:
            continue
        print(f"\n## {bot}")
        table(g[~g.fitted], f"{bot} - never seen")
        table(g[g.fitted], f"{bot} - inside the fit window")
    df.to_csv(Path(__file__).resolve().parent / "geometry_trades.csv", index=False)


if __name__ == "__main__":
    main()
