"""Pre-listed filters on a backtest's own trades, each judged on both halves and the hold-out symbols
(SETUP_REVIEW §15.2 for harmonic; §16 for setup_breakout).

Every trade of ``trades.csv`` (``app.cli backtest``, a joined year from ``combine_periods.py``) gets, at its
entry (no look-ahead: the last closed bar before or at the entry):

- ``h4``/``h1``/``m15`` and ``phase``: the three screens of ``three_screens.py``;
- ``ny``: the New York time bucket (``pre_run.py``: rollover, asia, london_open, london, pre_ny, ny_open,
  ny_late);
- ``rr``: the planned reward-to-risk (|TP - entry| / |entry - SL|);
- ``cost_share``: the M5 spread at the entry as a share of the stop distance;
- ``sl_atr``: the stop distance in M15 ATR(14);
- ``h4_*`` / ``d1_*``: the H4/D1 market map at the entry (``MapBook``, as the backtester builds it; the
  ``ctx:`` features of ``signal_features``): ``room_r`` (to the nearest opposing demand/supply zone, in R),
  ``zone_before_tp`` (an opposing zone between the entry and the target), ``zone_with`` (the entry sits on a
  zone of its own side), ``range_pos`` (where in the H4/D1 range box, 1 = the far edge in the trade's
  direction), ``compression``;
- ``trigger`` (breakout setups): which detector fired on the decision bar, recomputed with the same causal
  detectors and default parameters (``donchian``, ``asian``, ``open_london``, ``open_new_york``; ``?`` when
  none matches). An inverted trade's trigger points the other way.

Each filter prints n, trades a year, mean R, both halves, the hold-out symbols and the max drawdown in R. The
filters are fixed in ``FILTERS`` before a run is read; a filter only counts when it holds in both halves and on
the hold-out symbols, and must then be coded and backtested again.

    .venv/Scripts/python research/2026-10-11-pre-run/filters.py data/backtests/inv/setup_breakout_1y [--csv out.csv]
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.config import load_app_config
from app.core.enums import Timeframe
from app.evidence.framework import Direction, EvidenceContext
from app.evidence.sessions_ranges import AsianParams, AsianRangeBreakout, OpenRangeBreakout, OpenRangeParams
from app.evidence.volatility import DonchianBreakout, DonchianParams
from app.indicators.market_map import signal_features
from app.strategy.market_maps import MapBook, candle_frame
from three_screens import phase, relative, states  # type: ignore[import-not-found]
from two_worlds import max_dd_r  # type: ignore[import-not-found]

HIST = Path("data/history/FBS-Demo")
HOLDOUT = {"AUDUSD", "XAUUSD"}
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
YEAR_DAYS = 355  # 2025-10-15 .. 2026-10-05
POINT = {"XAUUSD": 0.01, "USDJPY": 0.001}
NY = ZoneInfo("America/New_York")
BUCKETS = [  # New York minutes from midnight, [start, end); as pre_run.py
    (17 * 60, 20 * 60, "rollover"),
    (20 * 60, 24 * 60, "asia"),
    (0, 2 * 60, "asia"),
    (2 * 60, 4 * 60, "london_open"),
    (4 * 60, 8 * 60, "london"),
    (8 * 60, 9 * 60 + 30, "pre_ny"),
    (9 * 60 + 30, 11 * 60 + 30, "ny_open"),
    (11 * 60 + 30, 17 * 60, "ny_late"),
]
_m15: dict[str, pd.DataFrame] = {}
_ctx: dict[tuple[str, Timeframe], pd.DataFrame] = {}
BOOK = MapBook.from_config(load_app_config("data/research/config_bo_w1f.yaml"))  # market-map settings only
CTX_KEYS = ("room_r", "zone_before_tp", "zone_with", "range_pos", "compression")
_m5: dict[str, pd.DataFrame] = {}


def m15(symbol: str) -> pd.DataFrame:
    if symbol not in _m15:
        df = pd.read_parquet(HIST / symbol / "M15.parquet").sort_values("close_time").reset_index(drop=True)
        prev = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1)
        df["atr"] = tr.max(axis=1).rolling(14).mean()
        _m15[symbol] = df
    return _m15[symbol]


def spread_points(symbol: str, at: pd.Timestamp) -> float:
    if symbol not in _m5:
        _m5[symbol] = pd.read_parquet(HIST / symbol / "M5.parquet").sort_values("open_time")
    bars = _m5[symbol]
    i = max(0, int(pd.DatetimeIndex(bars["open_time"]).searchsorted(at, side="right")) - 1)
    return float(bars["spread"].iloc[i])


def ny_bucket(at: pd.Timestamp) -> str:
    local = at.tz_convert(NY)
    minute = local.hour * 60 + local.minute
    return next(name for lo, hi, name in BUCKETS if lo <= minute < hi)


def breakout_triggers(symbol: str) -> dict[tuple[pd.Timestamp, str], str]:
    """(bar close time, BULL/BEAR) -> trigger name, for the three breakout detectors on the whole M15 frame."""
    ctx = EvidenceContext(symbol, Timeframe.M15, m15(symbol).drop(columns=["atr"]))
    best: dict[tuple[pd.Timestamp, str], tuple[float, str, str]] = {}
    scans = [
        ("donchian", DonchianBreakout(), DonchianParams()),
        ("asian", AsianRangeBreakout(), AsianParams()),
        ("open", OpenRangeBreakout(), OpenRangeParams()),
    ]
    for name, detector, params in scans:
        for ev in detector.scan(ctx, params):
            key = (pd.Timestamp(ev.detected_at), ev.direction.value)
            label = name
            if name == "open":
                label = "open_" + ev.i18n_key.rsplit(".", 1)[-1]
            # as EvidenceSetup.evaluate: the best quality wins, a tie goes to the smaller detector id
            rank = (-ev.quality, ev.detector_id, label)
            if key not in best or rank < best[key]:
                best[key] = rank
    return {key: rank[2] for key, rank in best.items()}


def htf_features(r: pd.Series) -> dict[str, float]:
    """The ``ctx:h4_*`` / ``ctx:d1_*`` features of one trade (H4/D1 map at the last bar closed before entry)."""
    assert BOOK is not None
    candles = {}
    for tf in BOOK.timeframes:
        if (r["symbol"], tf) not in _ctx:
            _ctx[(r["symbol"], tf)] = candle_frame(pd.read_parquet(HIST / r["symbol"] / f"{tf.value}.parquet"))
        candles[tf] = _ctx[(r["symbol"], tf)]
    m = BOOK.at(r["symbol"], candles, r["entry_time"].to_pydatetime())
    if m is None:
        return {}
    f = signal_features(
        m, buy=r["side"] == "BUY", entry=r["entry_price"], stop=r["sl_initial"], target=r["tp_initial"]
    )
    return {k.removeprefix("ctx:"): v for k, v in f.items() if k.split("_", 1)[1] in CTX_KEYS}


def tag(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t["exit_time"] = pd.to_datetime(t["exit_time"], utc=True)
    risk = (t["entry_price"] - t["sl_initial"]).abs()
    t["rr"] = (t["tp_initial"] - t["entry_price"]).abs() / risk
    t["ny"] = [ny_bucket(a) for a in t["entry_time"]]
    screens, cost, sl_atr = [], [], []
    for _, r in t.iterrows():
        rel = []
        for tf in ("H4", "H1", "M15"):
            s = states(r["symbol"], tf)
            i = s.index.searchsorted(r["entry_time"], side="right") - 1
            rel.append(relative(s.iloc[i], r["side"]) if i >= 0 else "TRANS")
        screens.append((*rel, phase(*rel)))
        point = POINT.get(r["symbol"], 0.00001)
        stop = abs(r["entry_price"] - r["sl_initial"])
        cost.append(spread_points(r["symbol"], r["entry_time"]) * point / stop if stop > 0 else np.nan)
        bars = m15(r["symbol"])
        j = int(pd.DatetimeIndex(bars["close_time"]).searchsorted(r["entry_time"], side="right")) - 1
        atr = float(bars["atr"].iloc[j]) if j >= 0 else np.nan
        sl_atr.append(stop / atr if atr > 0 else np.nan)
    t[["h4", "h1", "m15", "phase"]] = pd.DataFrame(screens, index=t.index)
    t["cost_share"] = cost
    t["sl_atr"] = sl_atr
    ctx = pd.DataFrame([htf_features(r) for _, r in t.iterrows()], index=t.index)
    for tf in ("h4", "d1"):
        for k in CTX_KEYS:
            t[f"{tf}_{k}"] = ctx[f"{tf}_{k}"] if f"{tf}_{k}" in ctx else np.nan
    if t["strategy"].str.contains("breakout").all():
        triggers: list[str] = []
        cache: dict[str, dict[tuple[pd.Timestamp, str], str]] = {}
        for _, r in t.iterrows():
            if r["symbol"] not in cache:
                cache[r["symbol"]] = breakout_triggers(r["symbol"])
            buy = r["side"] == "BUY"
            if str(r["strategy"]).endswith("_inverted"):
                buy = not buy  # the inverted trade takes the other side of its trigger
            direction = (Direction.BULL if buy else Direction.BEAR).value
            triggers.append(cache[r["symbol"]].get((r["entry_time"], direction), "?"))
        t["trigger"] = triggers
    return t


Filter = Callable[[pd.DataFrame], pd.Series]

# Fixed on 2026-10-13 before the setup_breakout year was read (SETUP_REVIEW §16): the triggers, the textbook
# phase for breakouts (a range turning into a trend), the New York open (§14: breaks fail less there), the
# cost share (§14: the recurring best rule of the inverted breakout family), the R:R ceiling (harmonic V1) and
# the stop size.
FILTERS: list[tuple[str, Filter]] = [
    ("all", lambda t: t["r_multiple"].notna()),
    ("trigger donchian", lambda t: t["trigger"] == "donchian"),
    ("trigger asian (London morning)", lambda t: t["trigger"] == "asian"),
    ("trigger open london", lambda t: t["trigger"] == "open_london"),
    ("trigger open new_york", lambda t: t["trigger"] == "open_new_york"),
    ("triggers: sessions only", lambda t: t["trigger"].isin(["asian", "open_london", "open_new_york"])),
    ("phase aligned (H4+H1 with)", lambda t: t["phase"] == "aligned"),
    ("phase pullback", lambda t: t["phase"] == "pullback"),
    ("phase H4 range", lambda t: t["phase"].isin(["range_h1_with", "range_h1_other"])),
    ("phase range_h1_with", lambda t: t["phase"] == "range_h1_with"),
    ("phase against_h4", lambda t: t["phase"] == "against_h4"),
    ("phase other (transitions)", lambda t: t["phase"] == "other"),
    ("H4 with the trade", lambda t: t["h4"] == "WITH"),
    ("H4 against or range", lambda t: t["h4"].isin(["AGAINST", "RANGE"])),
    ("skip against_h4", lambda t: t["phase"] != "against_h4"),
    ("NY london_open+london (02-08)", lambda t: t["ny"].isin(["london_open", "london"])),
    ("NY pre_ny (08-09:30)", lambda t: t["ny"] == "pre_ny"),
    ("NY ny_open (09:30-11:30)", lambda t: t["ny"] == "ny_open"),
    ("NY ny_late (11:30-17)", lambda t: t["ny"] == "ny_late"),
    ("cost share <= 0.03", lambda t: t["cost_share"] <= 0.03),
    ("cost share <= 0.05", lambda t: t["cost_share"] <= 0.05),
    ("cost share > 0.10", lambda t: t["cost_share"] > 0.10),
    ("R:R <= 3", lambda t: t["rr"] <= 3.0),
    ("R:R <= 2", lambda t: t["rr"] <= 2.0),
    ("R:R >= 2", lambda t: t["rr"] >= 2.0),
    ("stop >= 1 ATR", lambda t: t["sl_atr"] >= 1.0),
    ("stop < 1 ATR", lambda t: t["sl_atr"] < 1.0),
    # demand/supply and the range box (owner, 2026-10-13), fixed before the year's features were read
    ("H4 no opposing zone before TP", lambda t: t["h4_zone_before_tp"] == 0),
    ("H4 opposing zone before TP", lambda t: t["h4_zone_before_tp"] == 1),
    ("H4 room to opposing zone >= 2R", lambda t: t["h4_room_r"] >= 2.0),
    ("H4 room to opposing zone < 1R", lambda t: t["h4_room_r"] < 1.0),
    ("D1 no opposing zone before TP", lambda t: t["d1_zone_before_tp"] == 0),
    ("D1 room to opposing zone >= 2R", lambda t: t["d1_room_r"] >= 2.0),
    ("H4+D1 no opposing zone before TP", lambda t: (t["h4_zone_before_tp"] == 0) & (t["d1_zone_before_tp"] == 0)),
    ("on an H4 zone of its own side", lambda t: t["h4_zone_with"] == 1),
    ("H4 compression", lambda t: t["h4_compression"] == 1),
    ("beyond the H4 range box edge", lambda t: t["h4_range_pos"] > 1.0),
    ("inside the H4 range box", lambda t: t["h4_range_pos"].between(0.0, 1.0)),
    ("H4 range + no zone before TP", lambda t: (t["h4"] == "RANGE") & (t["h4_zone_before_tp"] == 0)),
    ("H4 with + no zone before TP", lambda t: (t["h4"] == "WITH") & (t["h4_zone_before_tp"] == 0)),
    # the coded gates of SETUP_REVIEW §16 (textbook triple screen + demand/supply), as T1 trades them
    ("T1 screens: H4 with/range, H1 not against", lambda t: t["h4"].isin(["WITH", "RANGE"]) & (t["h1"] != "AGAINST")),
    ("T1 zones: no H4/D1 zone before TP", lambda t: (t["h4_zone_before_tp"] != 1) & (t["d1_zone_before_tp"] != 1)),
    (
        "T1 screens + zones",
        lambda t: t["h4"].isin(["WITH", "RANGE"])
        & (t["h1"] != "AGAINST")
        & (t["h4_zone_before_tp"] != 1)
        & (t["d1_zone_before_tp"] != 1),
    ),
]


def line(name: str, g: pd.DataFrame) -> str:
    g = g.sort_values("exit_time")
    r = g["r_multiple"].to_numpy(dtype=float)
    first = g.loc[g["entry_time"] < SPLIT, "r_multiple"].mean()
    second = g.loc[g["entry_time"] >= SPLIT, "r_multiple"].mean()
    hold = g.loc[g["symbol"].isin(HOLDOUT), "r_multiple"].mean()
    per_year = len(g) * 365 / YEAR_DAYS
    return (
        f"{name:34} n={len(g):>5} ({per_year:>5.0f}/yr)  mean {np.mean(r) if len(r) else np.nan:+.3f}  "
        f"halves {first:+.3f}/{second:+.3f}  hold-out {hold:+.3f}  total {r.sum():+7.1f} R  "
        f"maxDD {max_dd_r(r):5.1f} R"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--csv", help="write the tagged trades here")
    args = ap.parse_args()
    t = tag(pd.read_csv(Path(args.folder) / "trades.csv"))
    if args.csv:
        t.to_csv(args.csv, index=False)
    print(f"=== filters on {args.folder}: {len(t)} trades ===")
    for name, f in FILTERS:
        if "trigger" in name and "trigger" not in t:
            continue
        print(line(name, t[f(t).fillna(False).astype(bool)]))
    for col in ("trigger", "phase", "ny"):
        if col in t:
            g = t.groupby(col)["r_multiple"].agg(["count", "mean"]).round(3)
            print(f"\nby {col}:\n{g.to_string()}")
    print("\nby H4 x H1 (n, mean):\n" + t.groupby(["h4", "h1"])["r_multiple"].agg(["count", "mean"]).round(3).to_string())


if __name__ == "__main__":
    main()
