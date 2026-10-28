"""The three bots' edge by market condition, on the knowledge base's own split (P25).

The owner, 2026-10-27: *"we should have known long ago that we must pick the trades well - the conditions
where we have the edge."* They are right, and they said so on 2026-10-25 (P25, R08): record the edge **by
market condition**, never "it won in this period and lost in that one". The knowledge base already holds
the finding this touches:

    F20 / the bull-regime finding: in a BULL REGIME (D1 over a rising 50-day mean) an M5 SELL is at a
    disadvantage - every sell tested lost there. R08, the draft brake, became the shadow S11: bull regime
    -> no M5 sell except the surest.

The three bots never saw that brake. Week 1's three losers were sells into a rising gold market. So this
does not invent a new split: it is P25's fixed split - side x the D1 regime x the owner's session windows
- applied to the 248 trades `geometry.py` settled, so the cells compare with every other KB table.

Regime, exactly as the knowledge base defines it, read from the last D1 bar CLOSED before the entry:
  bull  = close over a 50-day mean that is rising
  bear  = close under a 50-day mean that is falling
  mixed = anything else

    .venv\\Scripts\\python research/2026-10-26-three-bots/edge_by_condition.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import bots  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

FIT = (pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-10-24", tz="UTC"))
MEAN_DAYS = 50


def regimes(h1: pd.DataFrame) -> pd.DataFrame:
    """One row per CLOSED D1 bar: its close, the 50-day mean, and the regime label.

    ``to_frame`` indexes a bar by its OPEN, so nothing is shifted here; an earlier version subtracted an
    hour as if the frames were close-stamped and put the day buckets an hour out. ``bear`` is strictly
    under a strictly falling mean - "not rising" swept a flat mean and an exact touch into bear instead
    of mixed (both found by the developer session, 2026-10-27).
    """
    d1 = h1.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    d1["mean50"] = d1.close.rolling(MEAN_DAYS).mean()
    slope = d1.mean50.diff()
    d1["rising"] = slope > 0
    over = d1.close > d1.mean50
    d1["regime"] = "mixed"
    d1.loc[over & d1.rising, "regime"] = "bull"
    d1.loc[(d1.close < d1.mean50) & (slope < 0), "regime"] = "bear"
    d1.loc[d1.mean50.isna(), "regime"] = "unknown"
    d1["closed_at"] = d1.index + pd.Timedelta(days=1)  # the bar is readable only after it closes
    return d1


def label(d1: pd.DataFrame, at: pd.Timestamp) -> str:
    usable = d1[d1.closed_at <= at]
    return str(usable.regime.iloc[-1]) if len(usable) else "unknown"


def window_of(at: pd.Timestamp) -> str:
    th = at.tz_convert(bots.TH)
    ny = at.tz_convert(bots.NY)
    if pd.Timestamp("07:00").time() < th.time() <= pd.Timestamp("09:00").time():
        return "Asia 07-09"
    if pd.Timestamp("13:00").time() < th.time() <= pd.Timestamp("15:00").time():
        return "London 13-15"
    if pd.Timestamp("08:00").time() < ny.time() <= pd.Timestamp("11:30").time():
        return "NY open"
    return "other"


def cells(df: pd.DataFrame, by: list[str], title: str, least: int = 8) -> None:
    print(f"\n### {title}\n")
    print(f"| {' | '.join(by)} | trades | win | R a trade | total R | in fit / unseen R |")
    print(f"|{'---|' * (len(by) + 5)}")
    for key, g in df.groupby(by):
        if len(g) < least:
            continue
        keys = key if isinstance(key, tuple) else (key,)
        fit, uns = g[g.fitted], g[~g.fitted]
        both = (
            f"{fit.r.mean():+.3f} ({len(fit)}) / {uns.r.mean():+.3f} ({len(uns)})"
            if len(fit) and len(uns)
            else "-"
        )
        print(
            f"| {' | '.join(str(k) for k in keys)} | {len(g)} | {(g.r > 0).mean():.0%} | "
            f"{g.r.mean():+.3f} | {g.r.sum():+.1f} | {both} |"
        )
    small = sum(len(g) for _, g in df.groupby(by) if len(g) < least)
    if small:
        print(f"\n({small} trades sit in cells under {least} trades and are left out)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    path = HERE / "geometry_trades.csv"
    if not path.exists():
        raise SystemExit("run geometry.py first: it writes geometry_trades.csv")
    df = pd.read_csv(path, parse_dates=["at"])
    df["at"] = pd.to_datetime(df["at"], utc=True)
    hs = ParquetHistoryStore(ROOT / "data/history")
    h1 = to_frame(hs.load("FBS-Demo", "XAUUSD", Timeframe.H1, None, None))
    d1 = regimes(h1)
    df["regime"] = [label(d1, t) for t in df["at"]]
    df["window"] = [window_of(t) for t in df["at"]]
    # the real side of each trade, saved by geometry.py - RANGE breaks either way (Codex, 2026-10-27:
    # labelling every RANGE trade "both" made its alignment unmeasurable)
    print("# The three bots' edge by market condition (P25's split)\n")
    print(f"{len(df)} trades, 2023-09 .. 2026-10; exits are stop and target only, so this reads the entry.\n")
    print(
        "Regime days behind the trades: " + ", ".join(f"{k} {v}" for k, v in df.regime.value_counts().items())
    )
    cells(df, ["bot", "regime"], "Each bot by the D1 regime")
    cells(df, ["bot", "window"], "Each bot by the owner's session windows")
    cells(df, ["bot", "regime", "window"], "Both together", least=6)
    df.to_csv(HERE / "edge_trades.csv", index=False)


if __name__ == "__main__":
    main()
