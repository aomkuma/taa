"""Audit 1(d): the M1 store's UTC alignment through the DST changes.

A. Consistency: the M1 store against the raw tick files (bid OHLC, min spread) on every weekday of the DST-change
   weeks (2025-10-20 .. 2025-11-07: EU 2025-10-26, US 2025-11-02; 2026-03-02 .. 2026-04-10: US 2026-03-08,
   EU 2026-03-29). Both come through the same ServerClock (Europe/Athens), so equality proves consistency, not UTC.
B. The UTC anchor: every US release before the exam (gold.releases() + agents/news/extra_releases.csv, New York
   time, DST-aware): where is the largest M1 range within +-90 minutes of the stated minute? If the broker's clock
   followed US DST dates while we convert with Europe/Athens, the weeks with US DST on and EU DST off (mid-March,
   late October) would put the jump at +60.
C. The daily break by regime: the last bar before the evening gap, in UTC and New York time.

No exam row is read: the NEW store is read with open_time < 2026-04-18.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_dst.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
MOMENTS = ROOT / "research" / "2026-10-18-moments"
sys.path.insert(0, str(MOMENTS))
import gold  # noqa: E402

EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
NY, ATH = ZoneInfo("America/New_York"), ZoneInfo("Europe/Athens")
TICKS = ROOT / "data" / "ticks" / "XAUUSD"
WEEKS = [("2025-10-20", "2025-11-07"), ("2026-03-02", "2026-04-10")]


def m1_before_exam() -> pd.DataFrame:
    old = pd.read_parquet(ROOT / gold.OLD / "M1.parquet")
    new = pd.read_parquet(ROOT / gold.NEW / "M1.parquet", filters=[("open_time", "<", EXAM_START)])
    first_new = new["open_time"].min()
    d = pd.concat([old[old["open_time"] < first_new], new], ignore_index=True)
    d.index = pd.DatetimeIndex(pd.to_datetime(d["open_time"], utc=True)).as_unit("ns")
    return d.sort_index()


def regime(t: pd.Timestamp) -> str:
    us = t.tz_convert(NY).utcoffset() == pd.Timedelta(hours=-4)
    eu = t.tz_convert(ATH).utcoffset() == pd.Timedelta(hours=3)
    return {(True, True): "both summer", (False, False): "both winter", (True, False): "US on, EU off"}.get(
        (us, eu), "US off, EU on"
    )


def part_a(m: pd.DataFrame) -> None:
    print("A. M1 store vs raw ticks, DST-change weeks (bid OHLC exact to the cent; spread column x 0.01 = min spread)")
    for a, b in WEEKS:
        days = [d for d in pd.date_range(a, b, freq="D") if d.dayofweek < 5]
        for wk_start in pd.date_range(a, b, freq="W-MON"):
            wk_days = [d for d in days if wk_start <= d < wk_start + pd.Timedelta(days=7)]
            rows, n_m1_only, n_tick_only, eq = [], 0, 0, np.zeros(5, int)
            for d in wk_days:
                f = TICKS / f"{d.date()}.parquet"
                if not f.exists():
                    continue
                x = pd.read_parquet(f)
                if not len(x):
                    continue
                t = pd.to_datetime(x["time_utc"], utc=True).dt.as_unit("ns")
                order = np.argsort(t.to_numpy(), kind="stable")
                x = x.iloc[order]
                minute = t.iloc[order].dt.floor("min")
                g = pd.DataFrame(
                    {"bid": x["bid"].to_numpy(), "spr": (x["ask"] - x["bid"]).round(2).to_numpy()},
                    index=minute.to_numpy(),
                ).groupby(level=0)
                tk = pd.DataFrame(
                    {"o": g.bid.first(), "h": g.bid.max(), "l": g.bid.min(), "c": g.bid.last(), "s": g.spr.min()}
                )
                tk.index = pd.DatetimeIndex(tk.index).tz_localize("UTC") if tk.index.tz is None else tk.index
                day0 = pd.Timestamp(d.date(), tz="UTC")
                mm = m[(m.index >= day0) & (m.index < day0 + pd.Timedelta(days=1))]
                both = mm.index.intersection(tk.index)
                n_m1_only += len(mm.index.difference(tk.index))
                n_tick_only += len(tk.index.difference(mm.index))
                mb, tb = mm.loc[both], tk.loc[both]
                eq += np.array(
                    [
                        int((mb["open"].round(2) == tb["o"].round(2)).sum()),
                        int((mb["high"].round(2) == tb["h"].round(2)).sum()),
                        int((mb["low"].round(2) == tb["l"].round(2)).sum()),
                        int((mb["close"].round(2) == tb["c"].round(2)).sum()),
                        int(((mb["spread"] * 0.01).round(2) == tb["s"].round(2)).sum()),
                    ]
                )
                rows.append(len(both))
            n = sum(rows)
            if n:
                print(
                    f"  week of {wk_start.date()} ({regime(wk_start.tz_localize('UTC') + pd.Timedelta(days=2))}): "
                    f"{len(rows)} days, {n} minutes in both; equal open {eq[0]} high {eq[1]} low {eq[2]} close "
                    f"{eq[3]} spread {eq[4]}; M1-only {n_m1_only}, tick-only {n_tick_only}"
                )


def events() -> pd.DataFrame:
    r = gold.releases()[["t", "event", "date", "time_et"]]
    x = pd.read_csv(MOMENTS / "agents" / "news" / "extra_releases.csv", dtype=str, keep_default_na=False)
    x["t"] = pd.to_datetime(x["date"] + " " + x["time_et"]).dt.tz_localize(NY).dt.tz_convert("UTC")
    e = pd.concat([r, x[["t", "event", "date", "time_et"]]], ignore_index=True)
    e["t"] = pd.DatetimeIndex(e["t"]).as_unit("ns")
    return e.drop_duplicates(subset=["t"]).sort_values("t").reset_index(drop=True)


def part_b(m: pd.DataFrame) -> pd.DataFrame:
    rng = (m["high"] - m["low"]).astype(float)
    e = events()
    e = e[(e["t"] >= m.index.min() + pd.Timedelta(hours=2)) & (e["t"] < EXAM_START)].copy()
    offs = np.arange(-90, 91)
    out = []
    for _, ev in e.iterrows():
        idx = ev["t"] + pd.to_timedelta(offs, unit="min")
        w = rng.reindex(idx).to_numpy()
        if np.isnan(w).sum() > 60 or np.isnan(w[90]):
            continue
        med = np.nanmedian(w)
        k = int(np.nanargmax(w))
        out.append(
            dict(
                t=ev["t"], event=ev["event"], regime=regime(ev["t"]), peak=int(offs[k]),
                r0=w[90] / med if med > 0 else np.nan,
                r_plus60=(w[150] / med) if med > 0 and not np.isnan(w[150]) else np.nan,
                r_minus60=(w[30] / med) if med > 0 and not np.isnan(w[30]) else np.nan,
            )
        )
    b = pd.DataFrame(out)
    print("\nB. Releases before the exam: the largest M1 range within +-90 min of the stated minute (offset in minutes)")
    for reg, g in b.groupby("regime"):
        at0 = int((g.peak == 0).sum())
        at60 = int((g.peak == 60).sum())
        atm60 = int((g.peak == -60).sum())
        at1 = int((g.peak.abs() == 1).sum())
        print(
            f"  {reg:14}: {len(g):4} events; argmax at 0: {at0}, at +-1: {at1}, at +60: {at60}, at -60: {atm60}, "
            f"elsewhere {len(g) - at0 - at1 - at60 - atm60}; median range ratio at 0 {g.r0.median():.2f}, "
            f"at +60 {g.r_plus60.median():.2f}, at -60 {g.r_minus60.median():.2f}"
        )
    b["utc_hm"] = [f"{t:%H:%M}" for t in b["t"]]
    print("  the 08:30 New York releases by their UTC minute (12:30 = US summer time, 13:30 = US winter time):")
    for hm in ("12:30", "13:30"):
        g = b[b.utc_hm == hm]
        print(
            f"    {hm} UTC: {len(g)} events, peak at 0: {int((g.peak == 0).sum())}, at +-1: "
            f"{int((g.peak.abs() == 1).sum())}, at +60: {int((g.peak == 60).sum())}, at -60: "
            f"{int((g.peak == -60).sum())}; median ratio at 0 {g.r0.median():.2f}, +60 {g.r_plus60.median():.2f}, "
            f"-60 {g.r_minus60.median():.2f}"
        )
    big = b[b.event.isin(["CPI", "NFP", "PPI", "FOMC"])]
    print("  CPI / NFP / PPI / FOMC only, by regime:")
    for reg, g in big.groupby("regime"):
        print(
            f"    {reg:14}: {len(g)} events, peak at 0: {int((g.peak == 0).sum())}, at +-1: "
            f"{int((g.peak.abs() == 1).sum())}, at +-60: {int((g.peak.abs() == 60).sum())}"
        )
    mis = b[b.regime == "US on, EU off"].sort_values("t")
    print("  the US-on / EU-off events one by one (UTC time, event, argmax, ratio at 0 / +60):")
    for _, r in mis.iterrows():
        print(f"    {r.t:%Y-%m-%d %H:%M} {r.event:6} peak {r.peak:+4d}  r0 {r.r0:5.1f}  r+60 {r.r_plus60:5.1f}")
    return b


def part_c(m: pd.DataFrame) -> None:
    print("\nC. The daily break (Mon-Thu): the last bar before the evening gap of >= 30 minutes, by regime")
    t = m.index[(m.index >= pd.Timestamp("2023-09-01", tz="UTC"))]
    gap = pd.Series(t[1:] - t[:-1], index=t[:-1])
    ev = gap[(gap >= pd.Timedelta(minutes=30)) & (gap < pd.Timedelta(hours=3))]
    ev = ev[(ev.index.hour >= 19) & (ev.index.dayofweek < 4)]
    rows = pd.DataFrame(
        {
            "regime": [regime(x) for x in ev.index],
            "utc": [f"{x:%H:%M}" for x in ev.index],
            "ny": [f"{x.tz_convert(NY):%H:%M}" for x in ev.index],
            "server": [f"{x.tz_convert(ATH):%H:%M}" for x in ev.index],
        }
    )
    for reg, g in rows.groupby("regime"):
        print(
            f"  {reg:14}: {len(g)} breaks; last bar UTC {g.utc.value_counts().head(3).to_dict()}, New York "
            f"{g.ny.value_counts().head(3).to_dict()}, Athens {g.server.value_counts().head(3).to_dict()}"
        )
    # the raw server clock of those bars (time_server is MT5's own epoch, wall clock as if UTC)
    srv = pd.to_datetime(m.loc[ev.index, "time_server"].to_numpy(), unit="s")
    rows["raw_server"] = [f"{x:%H:%M}" for x in srv]
    for reg, g in rows.groupby("regime"):
        print(f"  {reg:14}: the raw time_server of the last bar {g.raw_server.value_counts().head(3).to_dict()}")


def main() -> int:
    m = m1_before_exam()
    print(f"M1 before the exam: {len(m)} bars {m.index.min()} .. {m.index.max()}")
    part_a(m)
    part_b(m)
    part_c(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
