"""VOL-16's secondary check (CHECKLIST row 55, frozen 2026-10-21 12:05 Thai) on the whole-day ticks 2021-09 .. 2025-09
(D:/taa-data/ticks): PLAN-1's NY 08:30 straddle and London 13:00-Thai ORB, simulated by the measurer's own code
(check_plan1's ORB rule and ns1_ticks.straddle, both equal to dev1's runner on P1 / P2), every weekday; each trade
tagged with the MT5 ATR(14) of the last closed H1 bar at its decision. Reported per year (Oct .. Sep): all trades vs
the band 12 <= ATR < 16. Read once.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/vol16_old.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import check_plan1 as C
import ns1_ticks as N

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # gold.py
TD = Path("D:/taa-data/ticks/XAUUSD")
END = pd.Timestamp("2025-10-01", tz="UTC")
MIN = 60 * 10**9


def ticks(day: pd.Timestamp):
    f = TD / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f).sort_values("time_utc", kind="stable")
    return (pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), x.bid.to_numpy(float),
            x.ask.to_numpy(float))


def main() -> None:
    import gold  # noqa: PLC0415

    m1 = gold.bars("M1", before=END)
    m1 = m1[m1.index >= pd.Timestamp("2021-08-15", tz="UTC")]
    h = gold.bars("H1", before=END)
    pc = h.close.shift(1)
    atr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    a_t, a_v = (h.index + pd.Timedelta(hours=1)).as_unit("ns").asi8, atr.to_numpy()

    def atr_at(t_ns: int) -> float:
        i = int(np.searchsorted(a_t, t_ns, side="right")) - 1
        return float(a_v[i]) if i >= 0 else np.nan

    rows = []
    o = m1.index.as_unit("ns").asi8
    for day in pd.bdate_range("2021-09-01", "2025-09-30", tz="UTC"):
        tk = ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        yr = day.year if day.month >= 10 else day.year - 1
        # London ORB (check_plan1.london's rule, slippage 0)
        t0 = day + pd.Timedelta(hours=6)
        i0, i15, i75 = (int(np.searchsorted(o, (t0 + pd.Timedelta(minutes=k)).value)) for k in (0, 15, 75))
        if i15 > i0 and o[i0] - t0.value <= 5 * MIN:
            rh, rl = m1.high.iloc[i0:i15].max(), m1.low.iloc[i0:i15].min()
            H = atr_at(t0.value)
            if np.isfinite(H) and rh - rl <= 1.5 * H:
                c = m1.close.to_numpy()[i15:i75]
                k = np.flatnonzero((c > rh) | (c < rl))
                if len(k):
                    side = 1 if c[k[0]] > rh else -1
                    t_dec = int(o[i15 + k[0]] + MIN)
                    f = int(np.searchsorted(t, t_dec, side="left"))
                    if f < len(t) and t[f] - t_dec <= 5 * MIN:
                        e = ask[f] if side > 0 else bid[f]
                        stop = rl if side > 0 else rh
                        risk = (e - stop) * side
                        if risk > 0:
                            r = C.manage(t, bid, ask, f, e, side, stop, e + side * 2 * risk, t[f] + 60 * MIN)
                            if r is not None:
                                rows.append(dict(piece="London ORB", year=f"{yr}-{(yr + 1) % 100:02d}", atr=atr_at(t_dec),
                                                 R=(r[0] - e) * side / risk))
        # NY straddle
        tn = pd.Timestamp(f"{day:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        s = N.straddle(t, bid, ask, tn)
        if s is not None:
            rows.append(dict(piece="NY straddle", year=f"{yr}-{(yr + 1) % 100:02d}", atr=atr_at(tn), R=s["R"]))
    T = pd.DataFrame(rows)
    T["band"] = (T.atr >= 12) & (T.atr < 16)
    for piece, g in T.groupby("piece"):
        print(f"\n{piece}")
        for y, x in g.groupby("year"):
            b = x[x.band]
            print(f"  {y}: all {len(x):3d} R {x.R.mean():+.3f} | H1 ATR median {x.atr.median():5.1f} | in band {len(b):3d} "
                  f"R {b.R.mean() if len(b) else float('nan'):+.3f}")
        b = g[g.band]
        print(f"  pooled: all {len(g)} R {g.R.mean():+.3f} | in band {len(b)} R {b.R.mean() if len(b) else float('nan'):+.3f}")
    T.to_parquet(Path(__file__).with_name("vol16_old.parquet"))


if __name__ == "__main__":
    main()
