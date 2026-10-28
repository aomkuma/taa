"""NS-1 on the old ticks (notes.md "NS-1"; the same pass line): PLAN-1's straddle at 08:30 NY on the release days of
2021-09 .. 2025-10, from data/ticks_old/XAUUSD (08:20 .. 09:05 NY per day; owner's go-ahead 2026-10-20 18:33 Thai).
The rule as in check_plan1.ny: the reference = the last tick before 08:30:00; a buy stop at its ask + 2, a sell stop
at its bid - 2, live 60 s; the fill at the trigger or past it on a gap; stop 8 USD from the fill; out at the first
tick at / after 08:30 + 30 min; slippage 0; R = pnl / 8.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/ns1_ticks.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C

ROOT = Path(__file__).resolve().parents[4]
OLD = ROOT / "data" / "ticks_old" / "XAUUSD"
NS, MIN = 10**9, 60 * 10**9


def load(day: str):
    f = OLD / f"{day}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f).sort_values("time_utc", kind="stable")
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    return t, x.bid.to_numpy(float), x.ask.to_numpy(float)


def straddle(t, bid, ask, t0: int, slip: float = 0.0) -> dict | None:
    i0 = int(np.searchsorted(t, t0, side="left")) - 1
    if i0 < 0 or t[-1] < t0 + 30 * MIN:
        return None
    up, dn = ask[i0] + 2, bid[i0] - 2
    hit = None
    for j in range(i0 + 1, len(t)):
        if t[j] >= t0 + 60 * NS:
            break
        if ask[j] >= up:
            hit = (j, 1, max(up, ask[j]) + slip)
            break
        if bid[j] <= dn:
            hit = (j, -1, min(dn, bid[j]) - slip)
            break
    if hit is None:
        return None
    j, side, e = hit
    r = C.manage(t, bid, ask, j, e, side, e - side * 8, None, t0 + 30 * MIN)
    if r is None:
        return None
    px, _, kind = r
    return dict(side=side, entry=e, exit_px=px, pnl=(px - e) * side, R=(px - e) * side / 8, exit=kind)


def main() -> None:
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = sorted(set(cal[(cal.time_et == "08:30") & (cal.date >= "2021-09-01") & (cal.date <= "2025-10-17")].date))
    rows, missing = [], []
    for d in rel:
        x = load(d)
        if x is None:
            missing.append(d)
            continue
        t0 = pd.Timestamp(f"{d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        r = straddle(*x, t0)
        if r is not None:
            dd = pd.Timestamp(d)
            yr = dd.year if dd.month >= 10 else dd.year - 1
            rows.append(dict(day=d, year=f"{yr}-{(yr + 1) % 100:02d}", **r))
    T = pd.DataFrame(rows)
    print(f"release days {len(rel)}, with ticks {len(rel) - len(missing)}, trades {len(T)}; missing {missing[:10]}")
    print(T.groupby("year").R.agg(["size", "mean", "sum"]).round(3).to_string())
    print(f"pooled: {len(T)} trades, R {T.R.mean():+.3f} (95 % {T.R.mean() - 1.96 * T.R.std() / np.sqrt(len(T)):+.3f}.."
          f"{T.R.mean() + 1.96 * T.R.std() / np.sqrt(len(T)):+.3f}), win {np.mean(T.pnl > 0):.2f}, exits {T.exit.value_counts().to_dict()}")
    yrs = T.groupby("year").R.mean()
    full = yrs[[y for y in yrs.index if (T.year == y).sum() >= 20]]
    verdict = T.R.mean() >= 0.15 and (full > 0).sum() >= 3
    print(f"pass line (pooled >= +0.15 and > 0 in >= 3 of the 4 full years): {'PASS' if verdict else 'FAIL'}")
    m1 = Path(__file__).with_name("ns1_hold.parquet")
    if m1.exists():
        M = pd.read_parquet(m1)
        J = T.merge(M[M.release][["day", "side", "R"]], on="day", suffixes=("_tick", "_m1"))
        print(f"vs the M1 run, same days {len(J)}: same side {np.mean(J.side_tick == J.side_m1):.2f}; R ticks "
              f"{J.R_tick.mean():+.3f} vs M1 {J.R_m1.mean():+.3f}")
    T.to_parquet(Path(__file__).with_name("ns1_ticks.parquet"))


if __name__ == "__main__":
    main()
