"""The measurer's independent re-derivation of PLAN-1's three pieces from the raw ticks (CHECKLIST row 38).

Written from the frozen PLAN-1 text in CHECKLIST.md, not from the pieces' code: own loaders, own ATR, own fills.
- London: the 13:00-Thai ORB. Range = the M1 bars opening 06:00-06:14 UTC; skipped when the range > 1.5 x the MT5
  ATR(14) of the last H1 bar closed by 06:00 UTC; the first M1 bar opening 06:15-07:14 UTC that closes beyond the range
  decides; the fill is the first tick at / after that bar's close (a buy at the ask + slip, a sell at the bid - slip);
  stop = the range's other side, target 2 R (a limit), out at the first tick at / after the fill + 60 min.
- NY: the 08:30:00 New York straddle. Buy stop = the last ask before 08:30 + 2, sell stop = the last bid - 2, live
  60 s; the first tick that reaches one fills there (or worse, on a gap) +/- slip; stop 8 USD from the fill; out at
  the first tick at / after 08:30 + 30 min.
- Asia B2: the pattern logic is the developer's; the trades are checked for consistency with the ticks: the entry
  price against the tick at the entry time, the exit price against the tick at the exit time, pnl and R from them, and
  no tick beyond the stop (or at the target) before a non-stop (non-target) exit.
Stops and time exits fill on the bid (buy) / ask (sell), gap included. Ticks after the fill tick are scanned.
Learning parts only (P1 2025-10-18 .. 2026-01-15, P2 2026-01-16 .. 2026-04-17); the exam is never loaded.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_plan1.py [trades.parquet] [slip]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
TICKS = ROOT / "data/ticks/XAUUSD"
HIST = ROOT / "data/history/FBS-Demo/XAUUSD"
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
PARTS = {"P1": (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC")),
         "P2": (pd.Timestamp("2026-01-16", tz="UTC"), EXAM)}
MIN = 60 * 10**9


def part(ts: pd.Timestamp) -> str:
    for k, (a, b) in PARTS.items():
        if a <= ts < b:
            return k
    return ""


def bars(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(HIST / f"{tf}.parquet", filters=[("open_time", ">=", pd.Timestamp("2025-09-01", tz="UTC")),
                                                         ("open_time", "<", EXAM)])
    d = d.drop_duplicates("open_time", keep="last").sort_values("open_time").reset_index(drop=True)
    assert d.open_time.max() < EXAM
    return d


def day_ticks(day: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    assert day < EXAM
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f).sort_values("time_utc", kind="stable")
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    return t, x.bid.to_numpy(float), x.ask.to_numpy(float)


def mt5_atr(h: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = h.close.shift(1)
    tr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = h.high.iloc[0] - h.low.iloc[0]
    return tr.rolling(n).mean()


def manage(t, bid, ask, f, entry, side, stop, target, t_end):
    """From the tick after f: the stop (gap included), the target as a limit, the time. -> (exit px, exit ns, kind)."""
    for k in range(f + 1, len(t)):
        px = bid[k] if side > 0 else ask[k]
        if t[k] >= t_end:
            return px, t[k], "time"
        if (px - stop) * side <= 0:
            return px, t[k], "stop"
        if target is not None and (px - target) * side >= 0:
            return target, t[k], "target"
    return None


def london(slip: float) -> pd.DataFrame:
    m1, h1 = bars("M1"), bars("H1")
    h1 = h1.assign(atr=mt5_atr(h1))
    rows = []
    for day in pd.bdate_range("2025-10-20", "2026-04-17", tz="UTC"):
        t0 = day + pd.Timedelta(hours=6)
        if not part(t0):
            continue
        rng = m1[(m1.open_time >= t0) & (m1.open_time < t0 + pd.Timedelta(minutes=15))]
        if rng.empty or rng.open_time.iloc[0] - t0 > pd.Timedelta(minutes=5):
            continue
        done = h1[h1.close_time <= t0]
        atr = done.atr.iloc[-1] if len(done) else np.nan
        rh, rl = rng.high.max(), rng.low.min()
        if not np.isfinite(atr) or rh - rl > 1.5 * atr:
            continue
        nxt = m1[(m1.open_time >= t0 + pd.Timedelta(minutes=15)) & (m1.open_time < t0 + pd.Timedelta(minutes=75))]
        brk = nxt[(nxt.close > rh) | (nxt.close < rl)]
        if brk.empty:
            continue
        b = brk.iloc[0]
        side = 1 if b.close > rh else -1
        tk = day_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        t_dec = pd.Timestamp(b.close_time).value
        f = int(np.searchsorted(t, t_dec, side="left"))
        if f >= len(t) or t[f] - t_dec > 5 * MIN:
            continue
        e = ask[f] + slip if side > 0 else bid[f] - slip
        stop = rl if side > 0 else rh
        risk = (e - stop) * side
        if risk <= 0:
            continue
        r = manage(t, bid, ask, f, e, side, stop, e + side * 2 * risk, t[f] + 60 * MIN)
        if r is None:
            continue
        px, tx, kind = r
        rows.append(dict(piece="London ORB", t_in=pd.Timestamp(int(t[f]), tz="UTC"), t_out=pd.Timestamp(int(tx), tz="UTC"),
                         side=side, entry=e, stop=stop, risk=risk, exit=kind, pnl=(px - e) * side, R=(px - e) * side / risk,
                         part=part(t0)))
    return pd.DataFrame(rows)


def ny(slip: float) -> pd.DataFrame:
    rows = []
    for day in pd.bdate_range("2025-10-20", "2026-04-17"):
        t0 = pd.Timestamp(f"{day:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC")
        if not part(t0):
            continue
        tk = day_ticks(t0.normalize())
        if tk is None:
            continue
        t, bid, ask = tk
        i0 = int(np.searchsorted(t, t0.value, side="left")) - 1
        if i0 < 0 or t0.value + 30 * MIN > t[-1]:
            continue
        up, dn = ask[i0] + 2, bid[i0] - 2
        hit = None
        for j in range(i0 + 1, len(t)):
            if t[j] >= t0.value + 60 * 10**9:
                break
            if ask[j] >= up:
                hit = (j, 1, max(up, ask[j]) + slip)
                break
            if bid[j] <= dn:
                hit = (j, -1, min(dn, bid[j]) - slip)
                break
        if hit is None:
            continue
        j, side, e = hit
        r = manage(t, bid, ask, j, e, side, e - side * 8, None, t0.value + 30 * MIN)
        if r is None:
            continue
        px, tx, kind = r
        rows.append(dict(piece="NY straddle", t_in=pd.Timestamp(int(t[j]), tz="UTC"), t_out=pd.Timestamp(int(tx), tz="UTC"),
                         side=side, entry=e, stop=e - side * 8, risk=8.0, exit=kind, pnl=(px - e) * side,
                         R=(px - e) * side / 8.0, part=part(t0)))
    return pd.DataFrame(rows)


def check_b2(P: pd.DataFrame, slip: float) -> pd.DataFrame:
    """Consistency of the developer's B2 trades with the ticks; one row per trade with the faults found."""
    out = []
    for r in P.itertuples():
        t_in, t_out = pd.Timestamp(int(r.entry_t), tz="UTC"), pd.Timestamp(int(r.exit_t), tz="UTC")
        faults = []
        tk = day_ticks(t_in.normalize())
        if tk is None:
            out.append(dict(t_in=t_in, faults="no ticks"))
            continue
        t, bid, ask = tk
        if t_out.normalize() != t_in.normalize():
            nx = day_ticks(t_out.normalize())
            if nx is not None:
                t, bid, ask = (np.r_[t, nx[0]], np.r_[bid, nx[1]], np.r_[ask, nx[2]])
        f = int(np.searchsorted(t, t_in.value, side="left"))
        if f >= len(t) or t[f] != t_in.value:
            faults.append("entry time is not a tick")
        else:
            want = ask[f] + slip if r.side > 0 else bid[f] - slip
            if abs(want - r.entry) > 0.011:
                faults.append(f"entry {r.entry:.2f} vs tick {want:.2f}")
        x = int(np.searchsorted(t, t_out.value, side="left"))
        if x < len(t) and t[x] == t_out.value and r.exit not in ("target",):
            px = bid[x] if r.side > 0 else ask[x]
            if abs(px - r.exit_px) > 0.011:
                faults.append(f"exit {r.exit_px:.2f} vs tick {px:.2f}")
        if abs((r.exit_px - r.entry) * r.side - r.pnl) > 0.011:
            faults.append("pnl")
        risk = (r.entry - r.stop) * r.side
        if abs(risk - r.risk) > 0.011 or abs(r.pnl / r.risk - r.R) > 1e-6:
            faults.append(f"risk {r.risk:.2f} vs {risk:.2f} / R")
        seg = slice(f + 1, x)
        far = bid[seg] if r.side > 0 else ask[seg]
        if r.exit != "stop" and np.isfinite(r.stop) and len(far) and ((far - r.stop) * r.side <= 0).any():
            faults.append("a tick beyond the stop before the exit")
        if r.exit != "target" and r.target is not None and np.isfinite(r.target) and len(far) and ((far - r.target) * r.side >= 0).any():
            faults.append("a tick at the target before the exit")
        out.append(dict(t_in=t_in, exit=r.exit, R=r.R, faults="; ".join(faults)))
    return pd.DataFrame(out)


def compare(mine: pd.DataFrame, theirs: pd.DataFrame, name: str) -> None:
    a = mine.assign(k=mine.t_in.dt.floor("min")).set_index("k")
    b = theirs.assign(k=pd.to_datetime(theirs.t_in, utc=True).dt.floor("min")).set_index("k")
    common = a.index.intersection(b.index)
    d = (a.loc[common, "R"] - b.loc[common, "R"]).abs()
    print(f"  {name}: mine {len(a)}, theirs {len(b)}, same minute {len(common)}, only mine {len(a.index.difference(b.index))}, "
          f"only theirs {len(b.index.difference(a.index))}; |dR| max {d.max() if len(d) else float('nan'):.4f}, "
          f"> 0.01 in {(d > 0.01).sum()}")
    for k in list(a.index.difference(b.index))[:5]:
        print(f"     only mine  {k:%Y-%m-%d %H:%M} R {a.loc[k, 'R']:+.3f}")
    for k in list(b.index.difference(a.index))[:5]:
        print(f"     only theirs {k:%Y-%m-%d %H:%M} R {b.loc[k, 'R']:+.3f}")
    for k in list(d[d > 0.01].index)[:5]:
        print(f"     differs    {k:%Y-%m-%d %H:%M} mine {a.loc[k, 'R']:+.3f} theirs {b.loc[k, 'R']:+.3f}")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("combo_trades_slip0.parquet")
    theirs = pd.read_parquet(src)
    print(f"checking {src.name}")
    L = london(0.07)
    N = ny(0.0)
    for name, mine in (("London ORB", L), ("NY straddle", N)):
        for p in ("P1", "P2"):
            g = mine[mine.part == p]
            print(f"  mine {name} {p}: {len(g)} trades, R {g.R.mean():+.3f}, win {(g.pnl > 0).mean():.2f}")
        compare(mine, theirs[theirs.piece == name], name)
    P = pd.read_parquet(Path(__file__).parents[1] / "dev" / "p4_trades_W_WL_WN.parquet")
    P = P[(P.variant == "W") & (P.news_cost == 0.0) & (P.window == "Asia") & P.part.isin(["P1", "P2"])]
    B = check_b2(P, 0.07)
    bad = B[B.faults != ""]
    print(f"  Asia B2: {len(B)} trades checked on the ticks, {len(bad)} with faults")
    for r in bad.head(10).itertuples():
        print(f"     {r.t_in:%Y-%m-%d %H:%M} {r.faults}")


if __name__ == "__main__":
    main()
