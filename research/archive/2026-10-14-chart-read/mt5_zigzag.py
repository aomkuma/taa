"""Chart read M0b (docs/CHART_READ.md §2): the MT5 standard ZigZag (Depth 12, Deviation 5, Backstep 3; owner,
2026-10-14) ported from MetaQuotes' ZigZag.mq5, then the same measurements as structure_read.py /
structure_trades.py with it.

The port keeps the indicator's two passes:

1. **maps** (per bar ``s``, from bars <= s only): the lowest low of the last ``depth`` bars is a low candidate
   when it is new and the bar's low is within ``deviation`` points of it; a new candidate erases older
   candidates of the last ``backstep`` bars that it beats. Same for highs. A map value is final ``backstep``
   bars later (the backstep may still erase it until then).
2. **cutting** (forward): alternate highs and lows; while searching for a peak a lower low replaces the pending
   low, and the first high candidate fixes the pending low and becomes the pending high (and vice versa).

MT5 redraws its last leg; the bot may not. A pivot is used only once it is **fixed** (the opposite pivot was
registered), and only from ``backstep`` bars after that bar, when the maps it was cut from are final. So the
pivots known at bar t are exactly those a live run would know at t (no look-ahead, no repainting).

    .venv/Scripts/python research/2026-10-14-chart-read/mt5_zigzag.py
"""

from __future__ import annotations

import glob
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from app.indicators.market_map import MapParams, state_frame  # noqa: E402
from app.indicators.price_action import Swing, SwingKind, label_structure, market_structure  # noqa: E402
from app.indicators.volatility import atr  # noqa: E402

H = "data/history/FBS-Demo"
B = "data/backtests/inv/"
FWD = 24
DEPTH, DEVIATION, BACKSTEP = 12, 5, 3


def mt5_zigzag(
    high: np.ndarray, low: np.ndarray, point: float, depth: int = DEPTH, deviation: int = DEVIATION,
    backstep: int = BACKSTEP, index: pd.Index | None = None,
) -> list[Swing]:
    """Fixed MT5 ZigZag pivots; ``confirm_pos`` = the bar from which a live run knows the pivot."""
    n = len(high)
    hmap, lmap = np.zeros(n), np.zeros(n)
    last_low = last_high = 0.0
    dev = deviation * point
    for s in range(depth, n):
        val = float(low[s - depth + 1 : s + 1].min())
        if val == last_low:
            val = 0.0
        else:
            last_low = val
            if low[s] - val > dev:
                val = 0.0
            else:
                for b in range(1, backstep + 1):
                    if lmap[s - b] != 0 and lmap[s - b] > val:
                        lmap[s - b] = 0.0
        lmap[s] = val if low[s] == val else 0.0
        val = float(high[s - depth + 1 : s + 1].max())
        if val == last_high:
            val = 0.0
        else:
            last_high = val
            if val - high[s] > dev:
                val = 0.0
            else:
                for b in range(1, backstep + 1):
                    if hmap[s - b] != 0 and hmap[s - b] < val:
                        hmap[s - b] = 0.0
        hmap[s] = val if high[s] == val else 0.0

    idx = index if index is not None else pd.RangeIndex(n)
    out: list[Swing] = []
    pending: tuple[SwingKind, int, float] | None = None  # the last leg's end, still movable
    for s in range(depth, n):
        h, lo = hmap[s], lmap[s]
        if pending is None:
            if h != 0:
                pending = (SwingKind.HIGH, s, h)
            if lo != 0:
                pending = (SwingKind.LOW, s, lo)
            continue
        kind, pos, price = pending
        if kind is SwingKind.LOW:  # searching for a peak
            if lo != 0 and lo < price and h == 0:
                pending = (SwingKind.LOW, s, lo)
            elif h != 0 and lo == 0:
                if s + backstep < n:  # known from s + backstep; later than the data: not known yet
                    out.append(Swing(kind, price, pos, s + backstep, idx[pos], idx[s + backstep]))
                pending = (SwingKind.HIGH, s, h)
        else:  # searching for a bottom
            if h != 0 and h > price and lo == 0:
                pending = (SwingKind.HIGH, s, h)
            elif lo != 0 and h == 0:
                if s + backstep < n:
                    out.append(Swing(kind, price, pos, s + backstep, idx[pos], idx[s + backstep]))
                pending = (SwingKind.LOW, s, lo)
    return out


def trend_series(swings: list[Swing], n: int) -> list[str | None]:
    ev = label_structure(swings, 0.0)
    cur: dict[SwingKind, str | None] = {SwingKind.HIGH: None, SwingKind.LOW: None}
    out: list[str | None] = [None] * n
    j = 0
    for t in range(n):
        while j < len(ev) and ev[j].swing.confirm_pos <= t:
            if ev[j].label is not None:
                cur[ev[j].swing.kind] = str(ev[j].label.value)
            j += 1
        hh, ll = cur[SwingKind.HIGH], cur[SwingKind.LOW]
        if hh is None or ll is None:
            out[t] = None
        elif (hh, ll) == ("HH", "HL"):
            out[t] = "UP"
        elif (hh, ll) == ("LH", "LL"):
            out[t] = "DOWN"
        elif (hh, ll) == ("LH", "HL"):
            out[t] = "CONTRACTING"
        elif (hh, ll) == ("HH", "LL"):
            out[t] = "BROADENING"
        else:
            out[t] = "FLAT"
    return out


def load(sym: str, tf: str) -> tuple[pd.DataFrame, float]:
    d = pd.read_parquet(f"{H}/{sym}/{tf}.parquet").sort_values("close_time").reset_index(drop=True)
    point = json.loads(open(f"{H}/{sym}/spec.json", encoding="utf-8").read())["spec"]["point"]
    return d, float(point)


def reads(sym: str, tf: str) -> pd.DataFrame:
    d, point = load(sym, tf)
    hi, lo, cl = (d[k].astype(float) for k in ("high", "low", "close"))
    piv = mt5_zigzag(hi.to_numpy(), lo.to_numpy(), point)
    out = pd.DataFrame(
        {
            "mt5": trend_series(piv, len(d)),
            "map": state_frame(d, MapParams())["state"].astype(str).to_numpy(),
            "fractal": market_structure(hi, lo, 3)["trend"].astype(str).to_numpy(),
            "close": cl.to_numpy(),
            "atr": atr(hi, lo, cl, 14).to_numpy(),
        }
    )
    out.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    out.attrs["pivots"] = len(piv)
    out.attrs["bars"] = len(d)
    return out


def flips(s: pd.Series) -> float:
    x = s[s.isin(["UP", "DOWN"])]
    return float((x != x.shift()).sum() - 1)


def part1() -> None:
    rows = []
    for sym in ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"):
        for tf in ("H1", "H4"):
            r = reads(sym, tf)
            fwd = (r["close"].shift(-FWD) - r["close"]) / r["atr"]
            ok = fwd.notna() & r["atr"].notna()
            sign = r["mt5"].map({"UP": 1, "DOWN": -1}).fillna(0)
            m = ok & (sign != 0)
            phase = r.loc[ok, "mt5"].fillna("NONE").value_counts(normalize=True)
            rows.append(
                {
                    "sym": sym,
                    "tf": tf,
                    "bars/pivot": round(r.attrs["bars"] / max(r.attrs["pivots"], 1), 1),
                    "trend %": round(100 * m.sum() / ok.sum(), 1),
                    "contracting %": round(100 * phase.get("CONTRACTING", 0), 1),
                    "broadening %": round(100 * phase.get("BROADENING", 0), 1),
                    "flips/1000": round(1000 * flips(r.loc[ok, "mt5"]) / ok.sum(), 1),
                    "next 24 its way %": round(100 * ((fwd[m] * sign[m]) > 0).mean(), 1),
                }
            )
            if (sym, tf) == ("XAUUSD", "H1"):
                x = r[ok & r["mt5"].isin(["UP", "DOWN"])]
                print("XAUUSD H1: rows = MT5 zigzag trend, cols = map state (share of the row)")
                print(pd.crosstab(x["mt5"], x["map"], normalize="index").round(2).to_string(), "\n")
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print("\nmean over symbols:")
    print(t.groupby("tf")[[c for c in t.columns if c not in ("sym", "tf")]].mean().round(1).to_string())


def part2() -> None:
    h = pd.read_csv(B + "setup_harmonic_prz_v11y/trades.csv").assign(setup="harmonic V1")
    f = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(B + "setup_breakout_f1_20*/trades.csv"))])
    t = pd.concat([h, f.assign(setup="breakout F1")], ignore_index=True)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t["dir"] = np.where(t["side"] == "BUY", 1, -1)
    cache: dict[tuple[str, str], pd.DataFrame] = {}
    for tf in ("H1", "H4"):
        col = []
        for _, r in t.iterrows():
            key = (r.symbol, tf)
            if key not in cache:
                cache[key] = reads(r.symbol, tf)
            x = cache[key]
            tr = x["mt5"].iloc[x.index.searchsorted(r.entry_time, side="right") - 1]
            if tr in ("UP", "DOWN"):
                col.append("with" if (tr == "UP") == (r.dir > 0) else "against")
            else:
                col.append("mixed" if tr in ("CONTRACTING", "BROADENING", "FLAT") else "none")
        t[f"mt5_{tf}"] = col
    rng = np.random.default_rng(42)
    t["half"] = np.where(t.entry_time < pd.Timestamp("2026-04-09", tz="UTC"), "1st", "2nd")

    def ci(v: pd.Series) -> tuple[float, float]:
        a = v.to_numpy()
        if len(a) < 3:
            return float("nan"), float("nan")
        b = rng.choice(a, (4000, len(a))).mean(axis=1)
        return float(np.quantile(b, 0.05)), float(np.quantile(b, 0.95))

    print(f"\ntrades {len(t)}; split by the MT5 ZigZag(12,5,3) structure at entry, relative to the trade")
    for s, g in t.groupby("setup"):
        print(f"\n== {s}: {len(g)} trades, {g.r_multiple.mean():+.3f} R")
        for tf in ("H1", "H4"):
            for k, x in g.groupby(f"mt5_{tf}"):
                lo, hi = ci(x.r_multiple)
                hv = x.groupby("half").r_multiple.agg(["size", "mean"])
                halves = "  ".join(f"{hh} n{int(v['size'])} {v['mean']:+.3f}" for hh, v in hv.iterrows())
                print(
                    f"  {tf} {k:8} n {len(x):3}  {x.r_multiple.mean():+.3f} R  win {100 * (x.r_multiple > 0).mean():4.1f} %"
                    f"  CI90 [{lo:+.3f}, {hi:+.3f}]  {halves}"
                )
        nm = g[g.mt5_H1 != "mixed"]
        print(f"  without H1 mixed: n {len(nm)}  {nm.r_multiple.mean():+.3f} R  total {nm.r_multiple.sum():+.1f} R"
              f"  (all: {g.r_multiple.sum():+.1f} R)")


if __name__ == "__main__":
    part1()
    part2()
