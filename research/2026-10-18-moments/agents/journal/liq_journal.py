"""The liquidity journal of PLAN-1's trades (owner 2026-10-21: "understand how price runs - is this entry likely a
fake, will it really run, set the entry / exit, cut the loss away from the liquidation zone; know why it won or lost").

For each trade of the asked week, from the M1 bars and ticks known at the entry (pools) and after it (the path):
- the pools everyone sees around the entry: yesterday's high / low (server day), the Asia range (00:00-07:00 Thai),
  today's open, the last confirmed M15 swing high / low (a 3-bar fractal), the round numbers (every 10 USD);
- the entry's place: which pool it broke within the last 15 minutes (a pool break) or none;
- the stop's place: the nearest pool between the entry and the stop, and whether the stop sits within 0.25 H1 ATR beyond
  a pool (IN THE SWEEP ZONE: the stops of everyone who used that pool sit there too);
- the H4 ATR's change over the last 24 hours (contracting / expanding, a journal field);
- the path: best / worst R and when; if stopped, the R at the end of the trade's window without the stop (SWEPT = it
  came back and finished > 0, FAKE = it ran on the other way past -1.5 R, SLOW); for a winner, how far it went beyond.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/liq_journal.py 2025-10-20 2025-10-25
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AG / "precursors"))
sys.path.insert(0, str(AG.parent))
import check_plan1 as C  # noqa: E402
import gold  # noqa: E402

TH = "Asia/Bangkok"
MIN = 60 * 10**9
# the trades to read: the learning parts by default; PLAN1_TRADES names another file in dev/ (the exam, read once)
TRADES = AG / "dev" / os.environ.get("PLAN1_TRADES", "plan1_trades_learn_s0_x0.parquet")


def th(ns: int) -> str:
    return pd.Timestamp(int(ns), tz="UTC").tz_convert(TH).strftime("%a %d %H:%M")


def pools(m1: pd.DataFrame, h1atr: float, t: pd.Timestamp) -> dict[str, float]:
    """The pools known at t (bars closed by t)."""
    past = m1[m1.index + pd.Timedelta(minutes=1) <= t]
    srv = past.index.tz_convert("Europe/Athens")
    today = srv[-1].normalize()
    y = past[(srv >= today - pd.Timedelta(days=3)) & (srv < today)]
    ysrv = y.index.tz_convert("Europe/Athens").normalize()
    y = y[ysrv == ysrv.max()] if len(y) else y
    out = {"yday_high": y.high.max(), "yday_low": y.low.min()} if len(y) else {}
    thai = past.index.tz_convert(TH)
    d0 = thai[-1].normalize()
    a = past[(thai >= d0) & (thai < d0 + pd.Timedelta(hours=7))]
    if len(a) and t.tz_convert(TH) >= d0 + pd.Timedelta(hours=7):
        out |= {"asia_high": a.high.max(), "asia_low": a.low.min()}
    tod = past[srv >= today]
    if len(tod):
        out["today_open"] = tod.open.iloc[0]
    m15 = past.resample("15min").agg({"high": "max", "low": "min"}).dropna().iloc[-97:]
    hi, lo = m15.high.to_numpy(), m15.low.to_numpy()
    for k in range(len(m15) - 2, 0, -1):  # the last confirmed 3-bar fractal (its right bar closed)
        if "swing_high" not in out and hi[k] > hi[k - 1] and hi[k] > hi[k + 1]:
            out["swing_high"] = hi[k]
        if "swing_low" not in out and lo[k] < lo[k - 1] and lo[k] < lo[k + 1]:
            out["swing_low"] = lo[k]
        if "swing_high" in out and "swing_low" in out:
            break
    return out


def journal(start: str, end: str) -> pd.DataFrame:
    A = pd.read_parquet(TRADES)
    for c in ("t_in", "t_out", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    W = A[(A.t_in >= pd.Timestamp(start, tz="UTC").value) & (A.t_in < pd.Timestamp(end, tz="UTC").value)].sort_values("t_in")
    m1 = gold.bars("M1", before=pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=2))
    m1 = m1[m1.index >= pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=5)]
    h = gold.bars("H1", before=pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=2))
    pc = h.close.shift(1)
    atr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    h4 = gold.bars("H4", before=pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=2))
    pc4 = h4.close.shift(1)
    atr4 = pd.concat([h4.high - h4.low, (h4.high - pc4).abs(), (h4.low - pc4).abs()], axis=1).max(axis=1).rolling(14).mean()
    rows = []
    for r in W.itertuples():
        t_dec = pd.Timestamp(int(r.t_dec), tz="UTC")
        H = float(atr[atr.index + pd.Timedelta(hours=1) <= t_dec].iloc[-1])
        P = pools(m1, H, t_dec)
        k4 = atr4[atr4.index + pd.Timedelta(hours=4) <= t_dec]  # the H4 ATR's change over the last 24 h (closed bars)
        h4chg = float(k4.iloc[-1] / k4.iloc[-7] - 1)
        rn = [np.floor(r.entry / 10) * 10 + k * 10 for k in (-2, -1, 0, 1, 2)]
        # the entry: a pool broken in the 15 minutes before the decision, in the trade's direction
        pre = m1[(m1.index >= t_dec - pd.Timedelta(minutes=15)) & (m1.index + pd.Timedelta(minutes=1) <= t_dec)]
        # a buy broke a pool the 15 minutes crossed upward (it opened below it and traded above it); a sell, mirrored
        broke = [k for k, v in P.items() if len(pre) and ((r.side > 0 and pre.open.iloc[0] < v < pre.high.max())
                                                         or (r.side < 0 and pre.open.iloc[0] > v > pre.low.min()))]
        # the stop: pools between the entry and the stop; the sweep zone = within 0.25 H beyond a pool
        between = {k: v for k, v in P.items() if (r.entry - v) * r.side > 0 and (v - r.stop) * r.side > 0}
        near = {k: (v - r.stop) * r.side for k, v in between.items()}
        sweep_zone = [k for k, d in near.items() if d <= 0.25 * H]
        rn_between = [x for x in rn if (r.entry - x) * r.side > 0 and (x - r.stop) * r.side >= 0 and (x - r.stop) * r.side <= 0.25 * H]
        # the path, to the trade's own window end
        t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
        f = int(np.searchsorted(t, int(r.t_in)))
        w_end = int(r.t_in) + 60 * MIN if r.piece == "London ORB" else int(r.t_dec) + 30 * MIN if r.piece == "NY straddle" \
            else int(r.t_out)
        e = int(np.searchsorted(t, max(w_end, int(r.t_out)), side="right"))
        px = (bid if r.side > 0 else ask)[f:e]
        Rp = (px - r.entry) * r.side / r.risk
        stop_i = np.flatnonzero(Rp <= -(1 - 1e-9) * (r.entry - r.stop) * r.side / r.risk)
        end_R = float(Rp[-1]) if len(Rp) else np.nan
        cls = "" if r.exit != "stop" else ("SWEPT" if end_R > 0 else "FAKE" if end_R <= -1.5 else "SLOW")
        rows.append(dict(piece=r.piece, side="BUY" if r.side > 0 else "SELL", t_in=th(r.t_in), entry=r.entry, stop=r.stop,
                         risk=r.risk, H1atr=round(H, 1), H4chg=round(100 * h4chg), exit=r.exit, R=round(r.R, 2),
                         best=f"{Rp.max():+.2f}R {th(t[f + int(np.argmax(Rp))])}", worst=f"{Rp.min():+.2f}R",
                         broke=",".join(broke) or "-", stop_beyond=",".join(f"{k}({v:.1f})" for k, v in sorted(near.items(), key=lambda x: x[1])) or "-",
                         sweep_zone=",".join(sweep_zone + [f"round {x:.0f}" for x in rn_between]) or "-",
                         stopped_then=cls + (f" end {end_R:+.2f}R" if cls else ""),
                         pools=" ".join(f"{k}={v:.1f}" for k, v in P.items())))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_colwidth", 80)
    J = journal(sys.argv[1], sys.argv[2])
    for r in J.itertuples():
        print(f"{r.t_in} {r.piece:11s} {r.side} @{r.entry:.2f} stop {r.stop:.2f} risk {r.risk:.1f} | H1ATR {r.H1atr} H4ATR 24h {r.H4chg:+d}% | {r.exit} R {r.R:+.2f}"
              f" | best {r.best} worst {r.worst}\n    broke: {r.broke} | pools between entry and stop (distance beyond): "
              f"{r.stop_beyond} | stop in the sweep zone of: {r.sweep_zone} | {r.stopped_then}\n    pools: {r.pools}")
