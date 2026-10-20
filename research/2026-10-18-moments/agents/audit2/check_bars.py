"""Audit 2: precursors/indicators.py::bars against MT5's own bars, and its `avail`.

(a) H1 / H4 / D1 built from M1 by `indicators.bars` against data/history/FBS-Demo/XAUUSD/{H1,H4,D1}.parquet (MT5's own
    bars). The match uses MT5's raw `time_server` (its wall clock) for H4 / D1 and the UTC open for H1, not the key
    code under test. Rows: before the exam (2021-09 .. 2026-04-17) and the post-exam days (2026-10-17 .. 2026-10-19
    14:00, complete bars only; alignment only).
(b) How often `avail` (the last M1 minute + 1) is earlier than the bar's end, split into "the market closed after the
    bar's last minute" (the next M1 bar comes 30+ minutes after it: the daily break, a weekend, a holiday) and
    "mid-session" (quiet last minutes: the bar is not known to be complete at `avail`). The learning parts and all
    of the history before the exam.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_bars.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
MOMENTS = ROOT / "research" / "2026-10-18-moments"
sys.path.insert(0, str(MOMENTS))
sys.path.insert(0, str(MOMENTS / "agents" / "precursors"))
import gold  # noqa: E402
import indicators  # noqa: E402

EXAM_START, EXAM_END = pd.Timestamp("2026-04-18", tz="UTC"), pd.Timestamp("2026-10-17", tz="UTC")
LEARN = (pd.Timestamp("2025-10-18", tz="UTC"), EXAM_START)
STORE = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD"
ATH = "Europe/Athens"


def m1(post_exam: bool = False) -> pd.DataFrame:
    if post_exam:
        new = pd.read_parquet(STORE / "M1.parquet", filters=[("open_time", ">=", EXAM_END)])
        d = new
    else:
        old = pd.read_parquet(ROOT / gold.OLD / "M1.parquet")
        new = pd.read_parquet(STORE / "M1.parquet", filters=[("open_time", "<", EXAM_START)])
        d = pd.concat([old[old["open_time"] < new["open_time"].min()], new], ignore_index=True)
    d.index = pd.DatetimeIndex(pd.to_datetime(d["open_time"], utc=True)).as_unit("ns")
    return d.sort_index()[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


def mt5(tf: str, post_exam: bool) -> pd.DataFrame:
    f = [("open_time", ">=", EXAM_END)] if post_exam else [("open_time", "<", EXAM_START)]
    x = pd.read_parquet(STORE / f"{tf}.parquet", filters=f)
    x["server"] = pd.to_datetime(x["time_server"], unit="s")
    x["open_time"] = pd.DatetimeIndex(x["open_time"]).as_unit("ns")
    return x


def server_key(t_utc: pd.Series, rule: str) -> pd.Series:
    return pd.DatetimeIndex(t_utc).tz_convert(ATH).tz_localize(None).floor(rule).to_series(index=t_utc.index)


def compare(m: pd.DataFrame, tf: str, rule: str, post_exam: bool, until: pd.Timestamp | None = None) -> None:
    ours = indicators.bars(m, rule)
    ref = mt5(tf, post_exam)
    if until is not None:
        ref = ref[ref.open_time < until]
    if tf == "H1":
        ours["key"] = pd.DatetimeIndex(ours["last"]).floor("1h")
        ref["key"] = ref["open_time"]
    else:
        ours["key"] = server_key(ours["last"], rule).to_numpy()
        ref["key"] = ref["server"]
    # the common span: whole bars inside both series (the first and last bars of the M1 span may be partial)
    lo = max(ours["key"].iloc[1], ref["key"].min())
    hi = min(ours["key"].iloc[-2], ref["key"].max())
    o = ours[(ours.key >= lo) & (ours.key <= hi)].set_index("key")
    r = ref[(ref.key >= lo) & (ref.key <= hi)].set_index("key")
    both = o.index.intersection(r.index)
    eq = {
        c: int((o.loc[both, c].round(2) == r.loc[both, c].round(2)).sum()) for c in ("open", "high", "low", "close")
    }
    diff = max(float((o.loc[both, c] - r.loc[both, c]).abs().max()) for c in ("open", "high", "low", "close"))
    tag = "post-exam days" if post_exam else "before the exam"
    print(
        f"  {tf} ({tag}) {lo} .. {hi}: ours {len(o)}, MT5 {len(r)}, both {len(both)}; equal open {eq['open']} high "
        f"{eq['high']} low {eq['low']} close {eq['close']}; max |diff| {diff:.5f}; ours only {len(o.index.difference(r.index))}"
        f", MT5 only {len(r.index.difference(o.index))}"
    )
    for k in list(o.index.difference(r.index))[:5]:
        print(f"     ours only: {k}")
    for k in list(r.index.difference(o.index))[:5]:
        print(f"     MT5 only: {k} (tick_volume {int(r.loc[k, 'tick_volume'])})")
    if tf == "D1" and not post_exam:
        print("  D1 around the DST changes (server day | our first M1 bar UTC | MT5 open_time UTC | equal OHLC):")
        first = m.groupby(server_key(m.index.to_series(), "1D").to_numpy()).apply(lambda g: g.index.min())
        for day in pd.to_datetime(["2025-10-24", "2025-10-27", "2025-10-31", "2025-11-03", "2026-03-06", "2026-03-09",
                                   "2026-03-27", "2026-03-30"]):
            if day in both:
                same = all(round(o.loc[day, c], 2) == round(r.loc[day, c], 2) for c in ("open", "high", "low", "close"))
                print(f"     {day:%a %Y-%m-%d} | {first.loc[day]:%Y-%m-%d %H:%M} | {r.loc[day, 'open_time']:%Y-%m-%d %H:%M} | {same}")


def bar_end(ours: pd.DataFrame, rule: str) -> pd.Series:
    """Each bar's end in UTC: the clock bars from the UTC floor of the last minute, H4 / D1 from the server day."""
    last = pd.DatetimeIndex(ours["last"])
    if rule in ("4h", "1D"):
        key = last.tz_convert(ATH).tz_localize(None).floor(rule)
        end = (key + pd.Timedelta(rule)).tz_localize(ATH, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    else:
        end = last.floor(rule) + pd.Timedelta(rule)
    return pd.Series(end, index=ours.index)


def early(m: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp) -> None:
    lm = m[(m.index >= lo) & (m.index < hi)]
    nxt_of = pd.Series(lm.index[1:].append(pd.DatetimeIndex([pd.NaT], tz="UTC")), index=lm.index)
    print(f"\n(b) avail earlier than the bar's end, {lm.index.min():%Y-%m-%d} .. {hi:%Y-%m-%d} ({len(lm)} M1 bars):")
    for tf, rule in (("M5", "5min"), ("M15", "15min"), ("H1", "1h"), ("H4", "4h"), ("D1", "1D")):
        b = indicators.bars(lm, rule)
        end = bar_end(b, rule)
        av = pd.DatetimeIndex(b["avail"])
        is_early = av < pd.DatetimeIndex(end)
        nxt = pd.DatetimeIndex(nxt_of.loc[pd.DatetimeIndex(b["last"])].to_numpy())
        closed = nxt.isna() | (nxt - pd.DatetimeIndex(b["last"]) >= pd.Timedelta(minutes=30))
        mid = is_early & ~closed
        mins = np.asarray((pd.DatetimeIndex(end) - av) / pd.Timedelta(minutes=1))[np.asarray(mid)]
        print(
            f"  {tf:3}: {len(b)} bars; early {int(is_early.sum())} = market closed inside {int((is_early & closed).sum())}"
            f" + mid-session {int(mid.sum())} ({100 * mid.mean():.2f} %); mid-session early minutes: total "
            f"{int(mins.sum())}, median {np.median(mins) if len(mins) else 0:.0f}, max {int(mins.max()) if len(mins) else 0}"
        )
        if tf in ("M5", "M15", "H1") and mid.any():
            for k in np.flatnonzero(np.asarray(mid))[:8]:
                print(f"     {tf} bar ending {pd.DatetimeIndex(end)[k]}: last M1 {b['last'].iloc[k]}, avail {av[k]}, "
                      f"next M1 {nxt[k]}")


def main() -> int:
    m = m1()
    print("(a) indicators.bars against MT5's own bars")
    for tf, rule in (("H1", "1h"), ("H4", "4h"), ("D1", "1D")):
        compare(m, tf, rule, post_exam=False)
    mp = m1(post_exam=True)
    mp = mp[mp.index < pd.Timestamp("2026-10-19 15:00", tz="UTC")]  # MT5's H1 15:00 was stored while forming
    for tf, rule, until in (("H1", "1h", "2026-10-19 15:00"), ("H4", "4h", "2026-10-19 13:00")):
        compare(mp, tf, rule, post_exam=True, until=pd.Timestamp(until, tz="UTC"))
    early(m, *LEARN)
    early(m, m.index.min(), EXAM_START)
    return 0


if __name__ == "__main__":
    sys.exit(main())
