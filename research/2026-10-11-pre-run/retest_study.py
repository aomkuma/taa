"""Retest behaviour after M15 Donchian breaks, per symbol (owner, 2026-10-14: "on small timeframes price often
retests; use theory only 30-40 %, study each symbol's behaviour for the rest").

Definitions (fixed before the run):

- **break**: the first M15 close beyond the highest high (lowest low) of the previous 20 bars, bar close 07:00-20:00
  UTC on weekdays, 2025-10-15 .. 2026-10-05; ``L`` = the broken channel level, ``C`` = the break bar's close,
  ``A`` = ATR(14) at the break bar. Every break counts (no position limits, no cooldown).
- **retest** (read on M5 after the break bar): price trades back to ``L + 0.1 A`` (BUY; mirrored for SELL) within
  1 / 2 / 4 / 8 M15 bars; **depth** = how far beyond ``L`` it went within 8 bars, in ATR.
- **entries**, each a 2R target and resolved on M5 for up to 96 M15 bars (a bar touching both levels counts the
  stop; still open: closed at the last close); the M5 spread at the fill is charged once:
  - ``A market``: at ``C``, stop ``C - 1.5 A``;
  - ``B retest, stop 1 ATR``: a limit at ``L + 0.1 A`` within 8 bars, stop ``L - 1.0 A``;
  - ``C retest, stop 1.5 ATR``: the same limit, stop ``L - 1.5 A``;
  - added after the first run (the stop hunt: 84-88 % retest, median 0.9 ATR back inside the range): ``D``/``E``/
    ``F`` limits *beyond* the level (``L - 0.5 A`` / ``L - 0.9 A``) with the stop 2 / 2.5 ATR beyond it.
  R per break (an unfilled limit counts 0) and R per filled trade, by symbol and half; hold-out AUDUSD, XAUUSD.

    .venv/Scripts/python research/2026-10-11-pre-run/retest_study.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HIST = Path("data/history/FBS-Demo")
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"]
POINT = {"XAUUSD": 0.01, "USDJPY": 0.001}
START, END = pd.Timestamp("2025-10-15", tz="UTC"), pd.Timestamp("2026-10-05", tz="UTC")
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
N, WAIT, HOLD, TOL = 20, 8, 96, 0.1
ENTRIES = {
    "A market": (None, 1.5),
    "B retest, stop 1 ATR": (TOL, 1.0),
    "C retest, stop 1.5 ATR": (TOL, 1.5),
    # after the first run (owner, 2026-10-14: the stop hunt): wait for the sweep beyond the level, stop past it
    "D sweep 0.5, stop 2 ATR": (-0.5, 2.0),
    "E sweep 0.9, stop 2 ATR": (-0.9, 2.0),
    "F sweep 0.9, stop 2.5 ATR": (-0.9, 2.5),
    # after the second run: breaks that do not come back win 62-74 % -> wait k bars, enter only if none came back
    "G held 1 bar, stop 1.5 ATR": ("held", 1),
    "H held 2 bars, stop 1.5 ATR": ("held", 2),
}


def load(symbol: str, tf: str) -> pd.DataFrame:
    df = pd.read_parquet(HIST / symbol / f"{tf}.parquet").sort_values("open_time").reset_index(drop=True)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
    return df


def breaks(m15: pd.DataFrame) -> pd.DataFrame:
    prev = m15["close"].shift(1)
    tr = pd.concat([m15["high"] - m15["low"], (m15["high"] - prev).abs(), (m15["low"] - prev).abs()], axis=1)
    atr = tr.max(axis=1).rolling(14).mean()
    hh = m15["high"].rolling(N).max().shift(1)
    ll = m15["low"].rolling(N).min().shift(1)
    c, pc = m15["close"], m15["close"].shift(1)
    up = (c > hh) & (pc <= hh.shift(1))
    dn = (c < ll) & (pc >= ll.shift(1))
    t = m15["close_time"]
    ok = (t >= START) & (t < END) & (t.dt.weekday < 5) & (t.dt.hour >= 7) & (t.dt.hour < 20) & atr.notna()
    out = []
    for side, mask, level in (("BUY", up & ok, hh), ("SELL", dn & ok, ll)):
        sel = m15[mask]
        out.append(pd.DataFrame({"at": t[mask], "side": side, "L": level[mask], "C": sel["close"], "A": atr[mask]}))
    return pd.concat(out).sort_values("at").reset_index(drop=True)


def resolve(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray, sign: int, entry: float, stop: float, tp: float) -> float:
    """R of a trade from bar 0 of the arrays (a bar touching both: the stop)."""
    risk = abs(entry - stop)
    for h, low in zip(hi, lo, strict=True):
        adverse = low if sign > 0 else h
        favour = h if sign > 0 else low
        if (adverse - stop) * sign <= 0:
            return -1.0
        if (favour - tp) * sign >= 0:
            return (tp - entry) * sign / risk
    return (cl[-1] - entry) * sign / risk if len(cl) else 0.0


def study(symbol: str) -> pd.DataFrame:
    m15, m5 = load(symbol, "M15"), load(symbol, "M5")
    point = POINT.get(symbol, 0.00001)
    t5 = m5["open_time"].dt.tz_convert(None).to_numpy()
    hi, lo, cl = (m5[c].to_numpy(dtype=float) for c in ("high", "low", "close"))
    sp = m5["spread"].to_numpy(dtype=float) * point
    rows = []
    for b in breaks(m15).itertuples():
        sign = 1 if b.side == "BUY" else -1
        i0 = int(np.searchsorted(t5, b.at.tz_convert(None).to_datetime64(), side="left"))  # first M5 bar after the break bar
        if i0 + WAIT * 3 + HOLD * 3 > len(t5):
            continue
        w_hi, w_lo = hi[i0 : i0 + WAIT * 3], lo[i0 : i0 + WAIT * 3]
        back = (w_lo if sign > 0 else w_hi) - b.L
        back = back * sign  # distance above the level (BUY): <= TOL*A means a retest
        touched = np.flatnonzero(back <= TOL * b.A)
        row = {"symbol": symbol, "at": b.at, "side": b.side, "A": b.A}
        for k in (1, 2, 4, 8):
            row[f"retest_{k}"] = bool(len(touched)) and touched[0] < k * 3
        row["depth_atr"] = max(0.0, -float(back.min()) / b.A)
        for name, (tol, stop_atr) in ENTRIES.items():
            if tol is None:
                j, entry = i0, b.C
                stop = b.C - sign * stop_atr * b.A
            elif tol == "held":
                k = int(stop_atr)
                if len(touched) and touched[0] < k * 3:
                    row[name] = np.nan  # came back within k bars: no trade
                    continue
                j = i0 + k * 3  # the next M5 bar after k M15 bars; enter at the close of the k-th bar
                entry = cl[j - 1]
                stop = entry - sign * 1.5 * b.A
            else:
                fill = np.flatnonzero(back <= tol * b.A)  # the limit at L + tol*A, within WAIT bars
                if not len(fill):
                    row[name] = np.nan
                    continue
                j = i0 + int(fill[0])
                entry = b.L + sign * tol * b.A
                stop = b.L - sign * stop_atr * b.A
            risk = abs(entry - stop)
            tp = entry + sign * 2 * risk
            # a limit fill bar: the stop may be hit inside it; start resolving on the fill bar itself
            r = resolve(hi[j : j + HOLD * 3], lo[j : j + HOLD * 3], cl[j : j + HOLD * 3], sign, entry, stop, tp)
            row[name] = r - sp[j] / risk
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    t = pd.concat([study(s) for s in SYMBOLS], ignore_index=True)
    t["half"] = np.where(t["at"] < SPLIT, "1st", "2nd")
    print(f"=== M15 Donchian-{N} breaks, 8 symbols, {START:%Y-%m-%d}..{END:%Y-%m-%d}: {len(t)} breaks ===\n")
    print("retest of the broken level (share of breaks) and depth beyond it within 8 bars (ATR):")
    g = t.groupby("symbol")
    tab = pd.DataFrame(
        {
            "breaks": g.size(),
            **{f"<= {k} bar": g[f"retest_{k}"].mean().round(2) for k in (1, 2, 4, 8)},
            "depth p50": g["depth_atr"].median().round(2),
            "depth p75": g["depth_atr"].quantile(0.75).round(2),
        }
    )
    print(tab.to_string())
    print("\nR per break (unfilled = 0) | R per filled trade, net of the spread:")
    for name in ENTRIES:
        filled = t[name].notna()
        per_break = t[name].fillna(0.0)
        print(f"\n  {name}: fill {filled.mean():.0%}")
        print(
            f"    all       per break {per_break.mean():+.3f}  per trade {t.loc[filled, name].mean():+.3f}  "
            f"halves {per_break[t.half == '1st'].mean():+.3f} / {per_break[t.half == '2nd'].mean():+.3f}  "
            f"hold-out {per_break[t.symbol.isin(['AUDUSD', 'XAUUSD'])].mean():+.3f}"
        )
        for sym, s in t.groupby("symbol"):
            pb = s[name].fillna(0.0)
            print(
                f"    {sym:7}  per break {pb.mean():+.3f}  per trade {s[name].mean():+.3f}  "
                f"halves {pb[s.half == '1st'].mean():+.3f} / {pb[s.half == '2nd'].mean():+.3f}"
            )
    print("\nafter a retest within 8 bars vs none: share of breaks that reach C + 2 ATR before C - 1.5 ATR (A market):")
    t["won_A"] = t["A market"] > 0
    t["retested"] = t["retest_8"]
    print(t.groupby(["symbol", "retested"])["won_A"].mean().unstack().round(2).to_string())


if __name__ == "__main__":
    main()
