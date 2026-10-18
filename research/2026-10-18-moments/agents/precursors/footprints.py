"""The footprints of the money that moves gold (notes.md "Why gold runs the way it does", part 2; owner, 2026-10-19: "do
you think the people with the money to move the market toss a coin and then press buy or sell?"). At every moment of
the present library, from the M1 bars complete by it:
- participation: the tick volume of the last 5 minutes against the median of the same 5 minutes of the day over the
  previous 20 days the market traded at that minute;
- the move before: gold's change over the last 15 / 60 minutes, in M15 / H1 ATRs;
- the clock of the big orders: the minutes since (+) / to (-) the LBMA gold fixes (10:30 and 15:00 London), the COMEX
  open (08:20 New York), the US data minute (08:30 New York) and the New York stock open (09:30), each in its own
  zone (DST-aware), clipped at +-240;
- the resting orders: the distance to the previous server day's high and low and to the nearest round 10 and 50,
  in H1 ATRs (above +, below -);
- the dollar and risk: the US dollar against six majors (USDJPY, USDCHF, USDCAD up; EURUSD, GBPUSD, AUDUSD down = the
  dollar up) over 15 / 60 minutes - the mean of the pairs' log changes, each in its own 60-minute standard deviation
  of the last 20 days; US500's change over 15 / 60 minutes in its own M15 ATR.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/footprints.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402
from indicators import at, bars  # noqa: E402

EVENTS = {"fix_am": ("Europe/London", 10 * 60 + 30), "fix_pm": ("Europe/London", 15 * 60), "comex": ("America/New_York", 8 * 60 + 20),
          "us_data": ("America/New_York", 8 * 60 + 30), "ny_open": ("America/New_York", 9 * 60 + 30)}
USD_PAIRS = {"USDJPY": 1, "USDCHF": 1, "USDCAD": 1, "EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1}
CLIP = 240


def last_close(m: pd.DataFrame, t_ns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The close of the last M1 bar complete by each moment, and that bar's position (-1: none)."""
    av = (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8
    j = np.searchsorted(av, t_ns, side="right") - 1
    return np.where(j >= 0, m.close.to_numpy(float)[np.maximum(j, 0)], np.nan), j


def volume_rel(m: pd.DataFrame, t_ns: np.ndarray, days: int = 20) -> np.ndarray:
    """The last 5 M1 bars' tick volume (complete by t) against the median of the same minute-of-day's 5-bar sums over
    the previous `days` days that traded at that minute (today excluded)."""
    v5 = m.tick_volume.rolling(5, min_periods=5).sum()
    key = m.index.hour * 60 + m.index.minute
    med = v5.groupby(key).transform(lambda s: s.shift(1).rolling(days, min_periods=days // 2).median())
    _, j = last_close(m, t_ns)
    ok = j >= 0
    out = np.full(len(t_ns), np.nan)
    out[ok] = (v5.to_numpy()[j[ok]] / med.to_numpy()[j[ok]])
    return out


def change(m: pd.DataFrame, t_ns: np.ndarray, minutes: int) -> np.ndarray:
    """The close now (last M1 complete by t) minus the close of the last M1 complete by t - minutes."""
    now, _ = last_close(m, t_ns)
    then, _ = last_close(m, t_ns - minutes * 60 * 10**9)
    return now - then


def event_minutes(t: pd.DatetimeIndex, zone: str, minute: int) -> np.ndarray:
    """Minutes since (+) / to (-) today's event at `minute` of the local day in `zone`, clipped at +-CLIP."""
    loc = t.tz_convert(zone)
    mod = (loc.hour * 60 + loc.minute).to_numpy()
    return np.clip(mod - minute, -CLIP, CLIP).astype(float)


def round_dist(px: np.ndarray, step: float) -> np.ndarray:
    """The signed distance from the nearest multiple of step (above it +, below -)."""
    return px - np.round(px / step) * step


def features(m: pd.DataFrame, t: pd.DatetimeIndex, others: dict[str, pd.DataFrame]) -> pd.DataFrame:
    t_ns = t.as_unit("ns").asi8
    cols = {"vol_rel": volume_rel(m, t_ns)}
    atr_at = {}
    for tf, rule in (("M15", "15min"), ("H1", "1h")):
        b = bars(m, rule)
        a = F.atr(b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float), 14)
        bi = at(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, t_ns)
        atr_at[tf] = np.where(bi >= 0, a[np.maximum(bi, 0)], np.nan)
    cols["move15"] = change(m, t_ns, 15) / atr_at["M15"]
    cols["move60"] = change(m, t_ns, 60) / atr_at["H1"]
    for name, (zone, minute) in EVENTS.items():
        cols[f"t_{name}"] = event_minutes(t, zone, minute)
    px, _ = last_close(m, t_ns)
    d = bars(m, "1D")
    bi = at(pd.DatetimeIndex(d["avail"]).as_unit("ns").asi8, t_ns)
    ok = bi >= 0
    cols["to_pdh"] = np.where(ok, (px - d.high.to_numpy(float)[np.maximum(bi, 0)]) / atr_at["H1"], np.nan)
    cols["to_pdl"] = np.where(ok, (px - d.low.to_numpy(float)[np.maximum(bi, 0)]) / atr_at["H1"], np.nan)
    cols["round10"] = round_dist(px, 10.0) / atr_at["H1"]
    cols["round50"] = round_dist(px, 50.0) / atr_at["H1"]
    cols |= usd(others, t_ns)
    u = others["US500"]
    ub = bars(u, "15min")
    ua = F.atr(ub.high.to_numpy(float), ub.low.to_numpy(float), ub.close.to_numpy(float), 14)
    ui = at(pd.DatetimeIndex(ub["avail"]).as_unit("ns").asi8, t_ns)
    for minutes in (15, 60):
        cols[f"us500_{minutes}"] = change(u, t_ns, minutes) / np.where(ui >= 0, ua[np.maximum(ui, 0)], np.nan)
    return pd.DataFrame(cols, index=t)


def usd(others: dict[str, pd.DataFrame], t_ns: np.ndarray, scale_rows: int = 20 * 1440) -> dict[str, np.ndarray]:
    """The dollar over 15 / 60 minutes: the mean over the pairs of sign x the log change, each pair in its own standard
    deviation of 60-minute log changes over the last scale_rows M1 bars (known at that bar)."""
    out = {}
    scaled = {}
    for sym in USD_PAIRS:
        lc = np.log(others[sym].close)
        scaled[sym] = (lc - lc.shift(60)).rolling(scale_rows, min_periods=scale_rows // 20).std().to_numpy()
    for minutes in (15, 60):
        parts = []
        for sym, sgn in USD_PAIRS.items():
            o = others[sym]
            now, j = last_close(o, t_ns)
            then, _ = last_close(o, t_ns - minutes * 60 * 10**9)
            with np.errstate(invalid="ignore", divide="ignore"):
                parts.append(sgn * (np.log(now) - np.log(then)) / np.where(j >= 0, scaled[sym][np.maximum(j, 0)], np.nan))
        with np.errstate(invalid="ignore"):
            out[f"usd{minutes}"] = np.nanmean(np.column_stack(parts), axis=1)
    return out


def main() -> None:
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    P = pd.read_parquet(HERE / "present_3y.parquet")
    m = plib.load()
    others = {s: jlib.m1_frame(s) for s in [*USD_PAIRS, "US500"]}
    X = features(m, pd.DatetimeIndex(P.t_dec), others)
    X.reset_index(drop=True).to_parquet(HERE / "footprints_3y.parquet")
    print(f"{len(X)} moments x {X.shape[1]} footprints; missing share:", X.isna().mean().round(4).to_dict())


if __name__ == "__main__":
    main()
