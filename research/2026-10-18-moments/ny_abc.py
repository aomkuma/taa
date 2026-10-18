"""Round 7, iteration 8 (docs/OWN_SETUP_ROUNDS.md): New York, with the H1 tide, after an A-B-C correction on M5 (the bot's
chart-read ZigZag): enter when the M5 close breaks back beyond B; the stop beyond C plus half an M5 ATR.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ny_abc.py [--test]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
import gold  # noqa: E402
from ny_lab import DEV, REF, SLIP, TEST, M1, select  # noqa: E402

from app.indicators.chart_read import ChartReadFrame, ChartReadParams, SwingKind  # noqa: E402

PLAN = dict(tp=None, sl=None, be=0.6, hz=60, pa=True)


def main() -> None:
    test = "--test" in sys.argv
    P = M1()
    m1 = gold.bars("M1")  # the stored M5 covers only 2025-10 .. 2026-10: M5 from M1, indexed by the close time
    m1 = m1[(m1.index >= pd.Timestamp("2023-09-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    m5 = m1.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    m5.index = m5.index + pd.Timedelta(minutes=5)
    depth = int(sys.argv[sys.argv.index("--depth") + 1]) if "--depth" in sys.argv else 12
    fr = ChartReadFrame("M5", m5, 0.01, ChartReadParams(depth=depth, backstep=min(3, depth - 1)))
    atr5 = (m5.high - m5.low).rolling(14).mean().to_numpy()
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[(d.session == 2) & (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0)]
    keep, sls = [], []
    cache: dict[int, object] = {}
    for t, side, e in zip(d.t, d.side, d.e, strict=True):
        pos = fr.pos_at(t)  # the last M5 bar closed by t
        if pos < 1 or fr.index[pos] != t:  # only at the minute an M5 bar has just closed
            keep.append(False)
            sls.append(np.nan)
            continue
        read = cache.get(pos) or fr.at(pos)
        cache[pos] = read
        ok, sl = False, np.nan
        if read is not None and len(read.pivots) >= 4:
            p0, a, b, c = read.pivots[-4:]
            close = float(fr.c[pos])
            prev_close = float(fr.c[pos - 1])
            if side > 0 and (p0.kind, a.kind, b.kind, c.kind) == (SwingKind.HIGH, SwingKind.LOW, SwingKind.HIGH, SwingKind.LOW):
                ok = b.price < p0.price and c.price < a.price and close > b.price >= prev_close
                stop = c.price - 0.5 * atr5[pos]
            elif side < 0 and (p0.kind, a.kind, b.kind, c.kind) == (SwingKind.LOW, SwingKind.HIGH, SwingKind.LOW, SwingKind.HIGH):
                ok = b.price > p0.price and c.price > a.price and close < b.price <= prev_close
                stop = c.price + 0.5 * atr5[pos]
            if ok:
                fill = P.o[e] + (P.sp[e] + SLIP if side > 0 else -SLIP)
                sl = (fill - stop) * side
                k = P.c[e - 1] / REF if t < pd.Timestamp("2025-10-14", tz="UTC") else 1.0
                ok = 3 * k <= sl <= 12 * k
        keep.append(ok)
        sls.append(sl)
    rows = d[np.array(keep, dtype=bool)].assign(pa_sl=np.array(sls)[np.array(keep, dtype=bool)])
    print(f"iteration 8 (A-B-C on M5): {len(rows)} signals")
    print("  window                trades /day  win%  USD/trade    R    USD (0.01 lot) months+ | kinds ours (1/2/3) | coin")
    rng = np.random.default_rng(3)
    for name, a, b, scale in (TEST if test else DEV):
        x = rows[(rows.t >= pd.Timestamp(a, tz="UTC")) & (rows.t < pd.Timestamp(b, tz="UTC"))]
        r = select(x, P, PLAN, scale)
        cn = select(x, P, PLAN, scale, rng)
        days = pd.bdate_range(a, b).size
        if not len(r):
            print(f"  {name}: 0 trades")
            continue
        by_m = r.usd.groupby(r.t.dt.strftime("%Y-%m")).sum()

        def kinds(z: pd.DataFrame) -> str:
            v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
            return f"{100 * v['1']:3.0f}/{100 * v['2']:3.0f}/{100 * v['3']:3.0f}%"

        print(f"  {name:20} {len(r):5} {len(r) / days:4.2f} {100 * (r.exit == 'win').mean():4.0f}  {r.usd.mean():+8.2f}"
              f"  {(r.usd / (r.sl + SLIP)).mean():+.3f}  {r.usd.sum():+9.1f}   {(by_m > 0).sum()}/{len(by_m)}"
              f"   | {kinds(r)} | {kinds(cn)} (coin {cn.usd.sum():+.0f} USD)")


if __name__ == "__main__":
    main()
