"""The moment before the run - part 1 (notes.md, written before it is computed; owner, 2026-10-19: "become an expert at
observing price and catching the moment before it runs; bring in momentum or any other indicator"). At every M1 close
(the decision; the trade would start at the next bar's open), from closed bars only: speed, acceleration, the bar's
expansion, the volume against the same minutes, bars in a row, the break of the last 15 / 60 minutes, M1 RSI / MACD,
the spread, the clock of the big orders, the M15 structure and efficiency. The outcome per bar: from the next open, a
clean 10-USD run up / down within 5 minutes (burst_scan.clean_side).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/m1_features.py
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


def speed(c: np.ndarray, k: int) -> np.ndarray:
    """c[i] - c[i-k] (NaN for the first k bars)."""
    out = np.full(len(c), np.nan)
    out[k:] = c[k:] - c[:-k]
    return out


def in_a_row(c: np.ndarray) -> np.ndarray:
    """Signed count of consecutive closes moving the same way, ending at each bar (+3: three rises in a row)."""
    d = np.sign(np.diff(c, prepend=c[0]))
    out = np.zeros(len(c))
    for i in range(1, len(c)):
        out[i] = (out[i - 1] + d[i] if np.sign(out[i - 1]) == d[i] else d[i]) if d[i] != 0 else 0
    return out


def breaks(h: np.ndarray, lo: np.ndarray, c: np.ndarray, k: int) -> np.ndarray:
    """+1 when c[i] closes above the highest high of the k bars before it, -1 below their lowest low, else 0."""
    hh = pd.Series(h).shift(1).rolling(k).max().to_numpy()
    ll = pd.Series(lo).shift(1).rolling(k).min().to_numpy()
    return np.where(c > hh, 1, np.where(c < ll, -1, 0))


def same_minutes(x: pd.Series, days: int = 20) -> np.ndarray:
    """x against the median of the same UTC minute-of-day over the previous `days` days that had that minute."""
    key = x.index.hour * 60 + x.index.minute
    med = x.groupby(key).transform(lambda s: s.shift(1).rolling(days, min_periods=days // 2).median())
    return (x / med).to_numpy()


def features(m: pd.DataFrame) -> pd.DataFrame:
    from footprints import event_minutes  # noqa: PLC0415
    from indicators import at, bars  # noqa: PLC0415
    from pullback15 import structure  # noqa: PLC0415

    o, h, lo, c, v = (m[k].to_numpy(float) for k in ("open", "high", "low", "close", "tick_volume"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    done = m.index + pd.Timedelta(minutes=1)
    done_ns = done.as_unit("ns").asi8
    b5 = bars(m, "5min")
    a5 = F.atr(b5.high.to_numpy(), b5.low.to_numpy(), b5.close.to_numpy(), 14)
    k5 = at(pd.DatetimeIndex(b5["avail"]).as_unit("ns").asi8, done_ns)
    atr5 = np.where(k5 >= 0, a5[np.maximum(k5, 0)], np.nan)
    X = pd.DataFrame(index=m.index)
    for k in (1, 3, 5, 15):
        X[f"speed{k}"] = speed(c, k) / atr5
    X["accel"] = (speed(c, 3) - pd.Series(speed(c, 3)).shift(3).to_numpy()) / atr5
    rng = h - lo
    X["expand"] = rng / pd.Series(rng).shift(1).rolling(20).mean().to_numpy()
    vs = pd.Series(v, index=m.index)
    X["vol1"] = same_minutes(vs)
    X["vol3"] = same_minutes(vs.rolling(3).sum())
    X["in_a_row"] = in_a_row(c)
    X["break15"] = breaks(h, lo, c, 15)
    X["break60"] = breaks(h, lo, c, 60)
    X["rsi"] = F.rsi(c, 14)
    line, sig = F.macd(c)
    hist = (line - sig) / atr5
    X["macd_hist"] = hist
    X["macd_turn"] = hist - pd.Series(hist).shift(1).to_numpy()
    X["spread"] = sp / pd.Series(sp).rolling(1440, min_periods=200).median().to_numpy()
    for name, zone, minute in (("t_us_data", "America/New_York", 510), ("t_ny_open", "America/New_York", 570),
                               ("t_fix_pm", "Europe/London", 900), ("t_comex", "America/New_York", 500)):
        X[name] = event_minutes(pd.DatetimeIndex(done), zone, minute)
    X["m15_struct"] = structure(m, done_ns)
    b15 = bars(m, "15min")
    c15 = b15.close.to_numpy()
    path = pd.Series(np.abs(np.diff(c15, prepend=c15[0]))).rolling(20).sum().to_numpy()
    er15 = np.abs(c15 - pd.Series(c15).shift(20).to_numpy()) / np.where(path > 0, path, np.nan)
    k15 = at(pd.DatetimeIndex(b15["avail"]).as_unit("ns").asi8, done_ns)
    X["m15_er"] = np.where(k15 >= 0, er15[np.maximum(k15, 0)], np.nan)
    X["hour_utc"] = done.hour + done.minute / 60
    # where price is (owner, 2026-10-19: "trade at support / resistance, never mid-price, except a pullback"):
    # the place in the last 120 M15 / H1 bars' range, the nearest H1 swing level below / above (loc.location, in H1
    # ATRs), the previous server day's high / low and the round 10 / 50 (in M5 ATRs)
    hh15 = pd.Series(b15.high.to_numpy()).rolling(120, min_periods=20).max().to_numpy()
    ll15 = pd.Series(b15.low.to_numpy()).rolling(120, min_periods=20).min().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        pos15 = (c15 - ll15) / (hh15 - ll15)
    X["m15_pos"] = np.where(k15 >= 0, pos15[np.maximum(k15, 0)], np.nan)
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415
    from loc import location_grouped  # noqa: PLC0415

    b1 = bars(m, "1h")
    R1 = raw(b1)
    Y = dict(avail=pd.DatetimeIndex(b1["avail"]).as_unit("ns").asi8, h=R1["h"], lo=R1["lo"], atr=R1["atr"],
             piv=zigzag(R1["h"], R1["lo"], R1["atr"], ZZ_K))
    Lh = location_grouped(done_ns, c, Y)
    X["h1_pos"], X["h1_d_bot"], X["h1_d_top"] = Lh.pos.to_numpy(), Lh.d_bot.to_numpy(), Lh.d_top.to_numpy()
    d = bars(m, "1D")
    kd = at(pd.DatetimeIndex(d["avail"]).as_unit("ns").asi8, done_ns)
    X["to_pdh"] = np.where(kd >= 0, (c - d.high.to_numpy()[np.maximum(kd, 0)]) / atr5, np.nan)
    X["to_pdl"] = np.where(kd >= 0, (c - d.low.to_numpy()[np.maximum(kd, 0)]) / atr5, np.nan)
    X["round10"] = (c - np.round(c / 10) * 10) / atr5
    X["round50"] = (c - np.round(c / 50) * 50) / atr5
    return X


def main() -> None:
    import plib  # noqa: PLC0415

    from burst_scan import clean_side  # noqa: PLC0415

    m = plib.load()
    m = m[m.index >= pd.Timestamp("2025-08-01", tz="UTC")]  # warm-up before P1 (2025-10-18); the exam rows kept, unread
    X = features(m)
    side = clean_side(*(m[k].to_numpy(float) for k in ("open", "high", "low")))
    X["run_next"] = np.r_[side[1:], 0]  # the clean run starting at the NEXT bar's open (the trade's entry)
    X["part"] = np.where(X.index >= pd.Timestamp("2026-04-18", tz="UTC"), "exam",
                         np.where(X.index >= pd.Timestamp("2026-01-16", tz="UTC"), "P2", np.where(X.index >= pd.Timestamp("2025-10-18", tz="UTC"), "P1", "")))
    X = X[X.part != ""]
    X.reset_index(names="t").to_parquet(HERE / "m1_features.parquet")
    L = X[X.part.isin(["P1", "P2"])]
    print(f"{len(X)} M1 closes ({len(L)} learning); a clean 10-USD run up next {(L.run_next > 0).mean():.4f}, down {(L.run_next < 0).mean():.4f}")
    print(L.drop(columns=["part"]).describe().T[["mean", "25%", "50%", "75%"]].round(3).to_string())


if __name__ == "__main__":
    main()
