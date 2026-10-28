"""Day trade D1, step 1 (owner, 2026-10-15): which intraday trigger pays on M1-M5, following the break or
fading it?

Owner's frame: a new day-trade setup with M1-M5 entries on the 8 symbols, every position closed within the
day. Theory a third, measured behaviour the rest: before any rule is coded, measure on a year of M5 bars
(FBS-Demo, 2025-10 .. 2026-09) three classic intraday triggers and both ways of trading them:

- ``asia_break``: the first M5 close beyond the Asian range (00:00-07:00 UTC) between 07:00 and 12:00 UTC;
- ``pdhl_break``: the first M5 close beyond the previous UTC day's high or low, 07:00-18:00 UTC;
- ``ny_or_break``: the first M5 close beyond the 13:30-14:00 UTC range, 14:00-18:00 UTC.

Each event is traded both ways at the event bar's close plus the spread: ``follow`` (with the break) and
``fade`` (against it). Stops at the M1-M5 scale: ``m5`` = 1.5 × ATR(M5, 14) and ``m15`` = 1 × ATR(M15, 14),
of the last closed bar; target ``RR`` × the stop; flat at 20:45 UTC (before the broker's day roll); a bar that
touches both the stop and the target counts as the stop (pessimistic). Result in R. The spread's share of the
stop (``cost_r``) is reported per symbol: at this scale it decides which symbols can be traded at all.

Splits: the H4 market-map state relative to the trade (with / against / range-transition), the event's UTC
hour, the symbol, and the halves (split 2026-04-09). Rules are chosen on the FIRST HALF only; the second half
and the ladder judge them.

    .venv/Scripts/python research/2026-10-15-day-trade/intraday_study.py
"""

from __future__ import annotations

import json
import sys
from datetime import time

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.indicators.market_map import MapParams, state_frame  # noqa: E402
from app.indicators.volatility import atr  # noqa: E402

H = "data/history/FBS-Demo"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"]
START, END = pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2026-10-01", tz="UTC")
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
FLAT = time(20, 45)
RRS = (1.0, 1.5, 2.0)


def load(sym: str, tf: str) -> pd.DataFrame:
    d = pd.read_parquet(f"{H}/{sym}/{tf}.parquet").sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    return d


def _first_break(win: pd.DataFrame, hi: float, lo: float) -> tuple[pd.Timestamp, int] | None:
    hit = win[(win["close"] > hi) | (win["close"] < lo)]
    if not len(hit):
        return None
    b = hit.iloc[0]
    return b.name, (1 if b["close"] > hi else -1)


def events(m5: pd.DataFrame) -> list[tuple[str, pd.Timestamp, int]]:
    """(trigger, event bar close time, direction +1 up / -1 down)."""
    out: list[tuple[str, pd.Timestamp, int]] = []
    open_t = m5.index - pd.Timedelta(minutes=5)
    frame = m5.assign(day=open_t.floor("D"), t=open_t.time)
    prev_hl: tuple[float, float] | None = None
    for _, g in frame.groupby("day"):
        tt = g["t"]
        asia = g[(tt >= time(0, 0)) & (tt < time(7, 0))]
        if len(asia) >= 60:
            ev = _first_break(g[(tt >= time(7, 0)) & (tt < time(12, 0))], asia["high"].max(), asia["low"].min())
            if ev:
                out.append(("asia_break", *ev))
        if prev_hl is not None:
            ev = _first_break(g[(tt >= time(7, 0)) & (tt < time(18, 0))], *prev_hl)
            if ev:
                out.append(("pdhl_break", *ev))
        orng = g[(tt >= time(13, 30)) & (tt < time(14, 0))]
        if len(orng) == 6:
            ev = _first_break(g[(tt >= time(14, 0)) & (tt < time(18, 0))], orng["high"].max(), orng["low"].min())
            if ev:
                out.append(("ny_or_break", *ev))
        if len(g) >= 200:
            prev_hl = (g["high"].max(), g["low"].min())
    return out


class Bars:
    def __init__(self, m5: pd.DataFrame) -> None:
        self.index = m5.index
        self.h = m5["high"].to_numpy(float)
        self.lo = m5["low"].to_numpy(float)
        self.c = m5["close"].to_numpy(float)


def simulate(b: Bars, at: pd.Timestamp, side: int, risk: float, rr: float, cost: float) -> float | None:
    """R of one trade entered at the close of bar *at* (side +1 buy / -1 sell)."""
    pos = int(b.index.get_loc(at))
    entry = b.c[pos] + side * cost
    stop, target = entry - side * risk, entry + side * rr * risk
    day_end = (at - pd.Timedelta(minutes=5)).normalize() + pd.Timedelta(hours=FLAT.hour, minutes=FLAT.minute + 5)
    end = int(b.index.searchsorted(day_end, side="right"))
    if end <= pos + 1:
        return None
    hi, lo = b.h[pos + 1 : end], b.lo[pos + 1 : end]
    stop_hit = lo <= stop if side > 0 else hi >= stop
    tgt_hit = hi >= target if side > 0 else lo <= target
    first_stop = int(np.argmax(stop_hit)) if stop_hit.any() else None
    first_tgt = int(np.argmax(tgt_hit)) if tgt_hit.any() else None
    if first_stop is not None and (first_tgt is None or first_stop <= first_tgt):
        return -1.0
    if first_tgt is not None:
        return rr
    return float((b.c[end - 1] - entry) * side / risk)


def main() -> None:
    rows = []
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else SYMBOLS
    out_file = "data/backtests/inv/d1_intraday_study" + ("" if len(sys.argv) <= 1 else "_" + "_".join(only))
    for sym in only:
        m5 = load(sym, "M5")
        m5 = m5[(m5.index >= START - pd.Timedelta(days=2)) & (m5.index < END)]
        m15, h4 = load(sym, "M15"), load(sym, "H4")
        scales = {
            "m5": 1.5 * atr(m5["high"].astype(float), m5["low"].astype(float), m5["close"].astype(float), 14),
            "m15": atr(m15["high"].astype(float), m15["low"].astype(float), m15["close"].astype(float), 14),
        }
        sf = state_frame(h4[["high", "low", "close"]].astype(float), MapParams())
        st, pct = sf["state"], sf["atr_pct"]
        point = float(json.load(open(f"{H}/{sym}/spec.json"))["spec"]["point"])
        cost = float(m5["spread"].median()) * point
        bars = Bars(m5)
        for trig, at, d in events(m5):
            if not (START <= at < END):
                continue
            k4 = st.index.searchsorted(at, side="right") - 1
            if k4 < 0:
                continue
            state = str(st.iloc[k4])
            for scale, series in scales.items():
                k = series.index.searchsorted(at, side="right") - 1
                if k < 0 or not np.isfinite(series.iloc[k]) or series.iloc[k] <= 0:
                    continue
                risk = float(series.iloc[k])
                for way, side in (("follow", d), ("fade", -d)):
                    if state in ("UP", "DOWN"):
                        rel = "with" if (state == "UP") == (side > 0) else "against"
                    else:
                        rel = "range/trans"
                    for rr in RRS:
                        r = simulate(bars, at, side, risk, rr, cost)
                        if r is None:
                            continue
                        rows.append(
                            {"sym": sym, "trig": trig, "stop": scale, "way": way, "rr": rr, "h4": rel,
                             "hour": at.hour, "half": "1st" if at < SPLIT else "2nd", "r": r,
                             "cost_r": cost / risk, "at": at, "h4_atr_pct": float(pct.iloc[k4])}
                        )  # fmt: skip
        print(f"{sym}: done ({len(rows)} rows so far)", flush=True)
    t = pd.DataFrame(rows)
    t.to_parquet(out_file + ".parquet")
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    print("\n== the spread's share of the stop, by symbol (R per trade lost to the spread alone)")
    print(t.groupby(["stop", "sym"]).cost_r.mean().round(3).unstack("sym").to_string())
    f = t[t.half == "1st"]
    print("\n== FIRST HALF: R/trade by trigger, stop and way (all symbols); columns RR; size = trades")
    print(f.groupby(["trig", "stop", "way", "rr"]).r.agg(["size", "mean"]).unstack("rr").round(3).to_string())
    f15 = f[f.rr == 1.5]
    print("\n== FIRST HALF, RR 1.5: by H4 relation")
    print(f15.groupby(["trig", "stop", "way", "h4"]).r.agg(["size", "mean"]).round(3).unstack("h4").to_string())
    print("\n== FIRST HALF, RR 1.5: by symbol")
    print(f15.groupby(["trig", "stop", "way", "sym"]).r.mean().round(3).unstack("sym").to_string())
    print("\n== FIRST HALF, RR 1.5, stop m15: by UTC hour of the event")
    print(f15[f15.stop == "m15"].groupby(["trig", "way", "hour"]).r.mean().round(3).unstack("hour").to_string())


if __name__ == "__main__":
    main()
