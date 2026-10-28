"""Task D1: the opening-range break at 13:00 Thai (06:00 UTC) - DEV_LOG.md "Task D - written before computing".
The range = the M1 bars of the first L minutes; skip it if wider than 1.5 H (the H1 ATR at 06:00); the first M1 close
beyond it in the next 60 minutes; the stop at the range's other side, the target k R, out X minutes after the fill. On
the ticks for P1 / P2; on M1 bars for the older years O1 / O2 (checks only) and for a tick-against-M1 comparison.
D1L: no trade when an owner's H1 level lies ahead closer than 2 R. D1S: the season reading ADR20 >= 63.3 USD.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/d1_orb.py
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

NS_MIN = 60 * 10**9
OPEN_UTC = 6  # 13:00 Thai = 06:00 UTC (Thailand has no summer time)
LATE_OPEN = 5 * NS_MIN  # the day counts only when its first M1 bar at / after the open opens within 5 minutes
WIDE_H = 1.5  # skip the day when the range is wider than 1.5 H
ENTRY_WIN = 60  # the entry window: the 60 minutes after the range
LEVEL_K = 2.0  # D1L: a level ahead closer than 2 R refuses the trade
ADR_Y = 63.3  # D1S: the 10th percentile of ADR20 at 06:00 UTC over P1's weekdays (DEV_LOG.md, from P1 only)
GAP = 30 * NS_MIN
PARTS = {"O1": ("2023-10-18", "2024-10-18"), "O2": ("2024-10-18", "2025-10-18"), "P1": ("2025-10-18", "2026-01-16"),
         "P2": ("2026-01-16", "2026-04-18")}
GRID = [(L, k, X) for L in (10, 15, 30) for k in (1.5, 2.0, 3.0) for X in (60, 120)]
CORE = (15, 2.0, 60)


def part_of(t_ns: int) -> str:
    t = pd.Timestamp(int(t_ns), tz="UTC")
    for name, (a, b) in PARTS.items():
        if pd.Timestamp(a, tz="UTC") <= t < pd.Timestamp(b, tz="UTC"):
            return name
    return ""


def weekdays(part: str) -> int:
    a, b = PARTS[part]
    return len(pd.bdate_range(a, b, inclusive="left"))


def at_time(avail: np.ndarray, values: np.ndarray, t_ns: int) -> float:
    """The value of the last bar complete by t_ns (avail <= t_ns); NaN when none."""
    k = int(np.searchsorted(avail, t_ns, side="right")) - 1
    return float(values[k]) if k >= 0 else np.nan


def decide(t_open: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray, t0: int, H: float, L: int) -> dict:
    """The day's decision: status 'late open' / 'no range' / 'wide' / 'no break' / 'trade'; with a trade: side, stop,
    k (the decision bar), t_dec (its close), close, rh / rl (the range)."""
    i0 = int(np.searchsorted(t_open, t0))
    if i0 >= len(t_open) or t_open[i0] - t0 > LATE_OPEN:
        return dict(status="late open")
    iL = int(np.searchsorted(t_open, t0 + L * NS_MIN))
    if iL <= i0:
        return dict(status="no range")
    rh, rl = float(h[i0:iL].max()), float(lo[i0:iL].min())
    if not np.isfinite(H) or rh - rl > WIDE_H * H:
        return dict(status="wide", rh=rh, rl=rl)
    iE = int(np.searchsorted(t_open, t0 + (L + ENTRY_WIN) * NS_MIN))
    for k in range(iL, iE):
        side = 1 if c[k] > rh else -1 if c[k] < rl else 0
        if side:
            return dict(status="trade", side=side, stop=rl if side > 0 else rh, k=k, t_dec=int(t_open[k] + NS_MIN),
                        close=float(c[k]), rh=rh, rl=rl)
    return dict(status="no break", rh=rh, rl=rl)


def tick_trade(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t_dec: int, side: int, stop: float, k_r: float,
               X: int) -> dict | None:
    """On the ticks: the fill within 60 s of the decision (p3_trades.simulate3), the stop, the target k_r x the fill's
    risk (a limit), out at the first tick at / after the fill + X minutes."""
    f = int(np.searchsorted(t, t_dec, side="left"))
    if f >= len(t) or t[f] - t_dec > T3.MAX_LAG_NS:
        return None
    t_limit = int(t[f] + X * NS_MIN)
    x = T3.simulate3(t, bid, ask, t_dec, side, stop, np.nan, None, t_limit)
    if x is None:
        return None
    tgt = x["entry"] + side * k_r * x["risk"]
    x = T3.simulate3(t, bid, ask, t_dec, side, stop, tgt, None, t_limit)
    x.update(target=float(tgt), t_limit=t_limit)
    return x


def m1_trade(t_open: np.ndarray, o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray, spr: np.ndarray,
             k_dec: int, side: int, stop: float, k_r: float, X: int) -> dict | None:
    """On M1 bid bars (ask = bid + spr): the fill at the open of the bar after the decision bar (it must open at the
    decision), a buy at ask + SLIP, a sell at bid - SLIP; the stop (at the stop, or the open when the bar opens past
    it), the target (a limit), both in one bar = the stop; out at the open of the first bar at / after the fill + X
    minutes; a gap > 30 minutes or the data's end first: out at the last bar's close ('break')."""
    i = k_dec + 1
    if i >= len(o) or t_open[i] != t_open[k_dec] + NS_MIN:
        return None
    entry = o[i] + spr[i] + P2.SLIP if side > 0 else o[i] - P2.SLIP
    risk = side * (entry - stop)
    if not risk > 0:
        return None
    tgt = entry + side * k_r * risk
    t_lim = t_open[i] + X * NS_MIN
    a = 0.0 if side > 0 else 1.0  # sells exit on the ask
    for j in range(i, len(o)):
        if j > i and t_open[j] - t_open[j - 1] > GAP:
            px, why, jx = c[j - 1] + a * spr[j - 1], "break", j - 1
            break
        if t_open[j] >= t_lim:
            px, why, jx = o[j] + a * spr[j], "time", j
            break
        oo, hh, ll = o[j] + a * spr[j], h[j] + a * spr[j], lo[j] + a * spr[j]
        if side * ((ll if side > 0 else hh) - stop) <= 0:
            px, why, jx = (min(oo, stop) if side > 0 else max(oo, stop)), "stop", j
            break
        if side * ((hh if side > 0 else ll) - tgt) >= 0:
            px, why, jx = tgt, "target", j
            break
    else:
        jx = len(o) - 1
        px, why = c[jx] + a * spr[jx], "break"
    pnl = side * (px - entry)
    return dict(side=side, entry=float(entry), entry_t=int(t_open[i]), stop=float(stop), risk=float(risk), exit=why,
                exit_px=float(px), exit_t=int(t_open[jx]), pnl=float(pnl), R=float(pnl / risk), target=float(tgt))


def level_in_way(prices: np.ndarray, close: float, side: int, risk_dec: float, k: float = LEVEL_K) -> float:
    """D1L: the nearest level ahead in the trade's way closer than k x risk_dec (0 < side x (L - close) < k x risk);
    NaN when none (the trade is allowed)."""
    d = side * (np.asarray(prices, float) - close)
    ok = (d > 0) & (d < k * risk_dec)
    return float(close + side * d[ok].min()) if ok.any() else np.nan


class Market:
    """M1 bars with H (H1 ATR) and ADR20 (server-day D1) and the owner's H1 levels, all read by time."""

    def __init__(self, m: pd.DataFrame):
        sys.path.insert(0, str(HERE.parent / "precursors"))
        import indicators  # noqa: PLC0415

        self.m = m
        self.t_open = m.index.as_unit("ns").asi8
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.spr = m["spread"].to_numpy(float) * 0.01
        b = P.tf_bars(m, 60)
        self.h1_av, self.h1_atr = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, P.atr14(b)
        d = indicators.bars(m, "1D")
        self.d_av = pd.DatetimeIndex(d["avail"]).as_unit("ns").asi8
        self.adr = pd.Series((d.high - d.low).to_numpy(float)).rolling(20).mean().to_numpy()
        self.Y = None

    def H(self, t_ns: int) -> float:
        return at_time(self.h1_av, self.h1_atr, t_ns)

    def adr20(self, t_ns: int) -> float:
        return at_time(self.d_av, self.adr, t_ns)

    def levels(self, t_ns: int, price: float) -> np.ndarray:
        from zones import levels_at  # noqa: PLC0415

        if self.Y is None:
            self.Y = P.level_inputs(self.m)
        L, _ = levels_at(self.Y, t_ns, price)
        return L.price.to_numpy(float)


def day_rows(mk: Market, day: pd.Timestamp, cells, ticks=None) -> list[dict]:
    """Every cell's decision and trade on one weekday (ticks: on the ticks, else M1); the core cell also gets the
    level and the season readings."""
    t0 = int((day.tz_convert("UTC").normalize() + pd.Timedelta(hours=OPEN_UTC)).value)
    H = mk.H(t0)
    span = None
    rows = []
    for L, k_r, X in cells:
        dd = decide(mk.t_open, mk.h, mk.lo, mk.c, t0, H, L)
        row = dict(day=day.tz_convert("UTC").normalize(), part=part_of(t0), L=L, k=k_r, X=X, H=H, status=dd["status"],
                   src="ticks" if ticks is not None else "m1")
        if dd["status"] == "trade":
            row.update(side=dd["side"], stop=dd["stop"], t_dec=dd["t_dec"], close=dd["close"], rh=dd["rh"], rl=dd["rl"])
            if ticks is not None:
                if span is None:
                    span = ticks.span(dd["t_dec"])
                x = tick_trade(*span, dd["t_dec"], dd["side"], dd["stop"], k_r, X)
            else:
                x = m1_trade(mk.t_open, mk.o, mk.h, mk.lo, mk.c, mk.spr, dd["k"], dd["side"], dd["stop"], k_r, X)
            if x is not None:
                row.update({k: v for k, v in x.items() if k not in ("t_be", "stop_exit")}, traded=True)
            if (L, k_r, X) == CORE:
                rd = dd["side"] * (dd["close"] - dd["stop"])
                row.update(adr20=mk.adr20(dd["t_dec"]), risk_dec=rd,
                           level_ahead=level_in_way(mk.levels(dd["t_dec"], dd["close"]), dd["close"], dd["side"], rd))
        rows.append(row)
    return rows


TIMES = ("t_dec", "entry_t", "exit_t", "t_limit")


def with_times(rows: list[dict]) -> pd.DataFrame:
    """The rows as a table, the ns times as integers with a missing value (Int64) - never floats, which round them by
    up to 256 ns at 1.76e18 (a day without a trade has no times)."""
    T = pd.DataFrame(rows)
    for k in TIMES:
        if k in T:
            T[k] = pd.array([None if r.get(k) is None or (isinstance(r.get(k), float) and np.isnan(r[k])) else int(r[k])
                             for r in rows], dtype="Int64")
    return T


def run(part: str, ticks_ok: bool, cells=GRID, m: pd.DataFrame | None = None) -> pd.DataFrame:
    a, b = (pd.Timestamp(x, tz="UTC") for x in PARTS[part])
    if b > EXAM_START:
        raise ExamPeriodError("a part reaches the exam")
    if m is None:
        m = P.load_m1(a - pd.Timedelta(days=45), b)
    mk = Market(m)
    ticks = P2.Ticks() if ticks_ok else None
    rows = []
    for day in pd.bdate_range(a, b, inclusive="left", tz="UTC"):
        rows += day_rows(mk, day, cells, ticks)
        if ticks is not None:  # one day's span at a time (memory)
            ticks.days.clear()
            ticks.spans.clear()
    T = with_times(rows)
    if "exit_t" in T and (T.exit_t.dropna() >= EXAM_START.value).any():
        raise ExamPeriodError("a trade reached the exam")
    return T


def stats(G: pd.DataFrame, part: str | None) -> dict:
    s = P2.stats(G, None)
    if part:
        s["per_day"] = s.get("n", 0) / weekdays(part) if part in PARTS else np.nan
    return s


def main() -> None:
    out = []
    for part in ("P1", "P2"):
        out.append(run(part, True))
        out.append(run(part, False, [CORE]))
        print(f"{part}: done", flush=True)
    for part in ("O1", "O2"):
        out.append(run(part, False))
        print(f"{part}: done", flush=True)
    A = pd.concat(out, ignore_index=True)
    A.to_parquet(HERE / "d1_trades.parquet")
    print(f"rows {len(A)}; traded {int(A.traded.fillna(False).sum())}")


if __name__ == "__main__":
    main()
