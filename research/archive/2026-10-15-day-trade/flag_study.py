"""Owner's question (2026-10-15): after a run up and a sideways box, is a break up more likely than a break down?

XAUUSD M5, the year in data/history (no look-ahead: the box and the run use bars up to the box's last bar only).

- Box: the last ``BOX`` closed bars, height (max high - min low) at most ``TIGHT`` x ATR(14) at its last bar.
- Run before the box: close at the box's first bar minus the close ``RUN`` bars earlier, in ATR: up (>= +K),
  down (<= -K) or none.
- Outcome within ``HORIZON`` bars: which edge an M5 close breaks first (above the box high / below the low).
- Trade with that break (entry the break close, stop the box's other edge, target 1 R; costs: ``SPREAD`` in
  price): win if the target is hit before the stop (bar highs/lows; both in one bar counts as a loss).
- Boxes do not overlap (after one, the next starts after it); split into halves at the middle date.

    .venv/Scripts/python research/2026-10-15-day-trade/flag_study.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

H = "data/history/FBS-Demo/XAUUSD/M5.parquet"
BOX, TIGHT, RUN, K, HORIZON, SPREAD = 12, 2.0, 24, 3.0, 48, 0.30


def atr(d: pd.DataFrame, n: int = 14) -> np.ndarray:
    pc = d["close"].shift()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


def events(d: pd.DataFrame) -> pd.DataFrame:
    hi, lo, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    a = atr(d)
    out = []
    t = BOX + RUN + 20
    while t < len(d) - HORIZON - 1:
        b0 = t - BOX + 1
        top, bot = hi[b0 : t + 1].max(), lo[b0 : t + 1].min()
        if not np.isfinite(a[t]) or top - bot > TIGHT * a[t]:
            t += 1
            continue
        run = (c[b0] - c[b0 - RUN]) / a[t]
        kind = "up" if run >= K else "down" if run <= -K else "none"
        drift = "rising" if c[t] > c[b0] else "falling"
        side, at = None, None
        for j in range(t + 1, t + 1 + HORIZON):
            if c[j] > top:
                side, at = "up", j
                break
            if c[j] < bot:
                side, at = "down", j
                break
        win = None
        if side is not None:
            entry = c[at]
            stop = bot if side == "up" else top
            risk = abs(entry - stop) + SPREAD
            target = entry + risk if side == "up" else entry - risk
            win = False
            for j in range(at + 1, min(at + 1 + HORIZON, len(d))):
                hit_stop = lo[j] <= stop if side == "up" else hi[j] >= stop
                hit_tgt = hi[j] >= target if side == "up" else lo[j] <= target
                if hit_stop:
                    break
                if hit_tgt:
                    win = True
                    break
        out.append({"at": d.index[t], "run": kind, "drift": drift, "side": side, "win": win})
        t += BOX
    return pd.DataFrame(out)


def table(e: pd.DataFrame, label: str) -> None:
    print(f"\n{label}")
    print("| run before the box | boxes | broke up first | broke down first | no break | trade the break: win (1 R) |")
    print("|---|---|---|---|---|---|")
    for kind in ("up", "none", "down"):
        g = e[e["run"] == kind]
        if g.empty:
            continue
        n = len(g)
        up, dn = (g["side"] == "up").sum(), (g["side"] == "down").sum()
        traded = g[g["side"].notna()]
        wins = traded["win"].sum()
        with_run = traded[traded["side"] == kind] if kind != "none" else traded
        wr = f"{wins / len(traded):.0%} ({len(traded)})"
        if kind != "none":
            wr += f"; with the run {with_run['win'].mean():.0%} ({len(with_run)})"
        print(f"| {kind} | {n} | {up / n:.0%} | {dn / n:.0%} | {(n - up - dn) / n:.0%} | {wr} |")


if __name__ == "__main__":
    d = pd.read_parquet(H).sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    e = events(d[["open", "high", "low", "close"]].astype(float))
    mid = e["at"].iloc[len(e) // 2]
    print(f"XAUUSD M5 {d.index[0]:%Y-%m-%d} .. {d.index[-1]:%Y-%m-%d}; box {BOX} bars <= {TIGHT} ATR, run {RUN} bars "
          f">= {K} ATR, horizon {HORIZON} bars, spread {SPREAD}; 1 R wins need > {1 / 2:.0%} to break even")
    table(e, "All")
    table(e[e["at"] < mid], f"1st half (to {mid:%Y-%m-%d})")
    table(e[e["at"] >= mid], "2nd half")
    up_rising = e[(e["run"] == "up") & (e["drift"] == "rising")]
    table(up_rising, "Run up, box drifting up (the owner's picture: sideways up)")
