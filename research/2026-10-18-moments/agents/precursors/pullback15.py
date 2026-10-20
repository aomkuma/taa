"""The direction from M15 as it stands, the entry on M1, only when gold runs (notes.md, written before it is computed;
owner, 2026-10-19). pullback.py's signal and trade with the trend from the M15 swing structure (instead of H1 / H4),
decisions only within 60 minutes of the New York open / the London PM fix / the US data / the COMEX open.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/pullback15.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from pullback import manage, signals  # noqa: E402

ACTIVE_MIN = 60
EVENTS = (("America/New_York", 9 * 60 + 30), ("Europe/London", 15 * 60), ("America/New_York", 8 * 60 + 30), ("America/New_York", 8 * 60 + 20))


def structure(m: pd.DataFrame, t_ns: np.ndarray, rule: str = "15min") -> np.ndarray:
    """The swing structure of the timeframe's last 120 complete bars at each time (+1 HH / HL, -1 LH / LL, 0 mixed or
    too few swings) - picture.struct_brk on the 3-ATR ZigZag, the swing still forming counted."""
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415
    from picture import WIN, struct_brk  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415

    b = bars(m, rule)
    R = raw(b)
    piv = zigzag(R["h"], R["lo"], R["atr"], ZZ_K)
    st = np.array([struct_brk(R["h"], R["lo"], float(R["c"][i]), piv, i, max(i - WIN + 1, 0))[0] for i in range(len(b))])
    st = np.where(st == 9, 0, st)
    bi = at(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, t_ns)
    return np.where(bi >= 0, st[np.maximum(bi, 0)], 0)


def active(t: pd.DatetimeIndex, minutes: int = ACTIVE_MIN) -> np.ndarray:
    """Within `minutes` of any of the events (each in its own zone, DST-aware)."""
    out = np.zeros(len(t), bool)
    for zone, minute in EVENTS:
        loc = t.tz_convert(zone)
        mod = (loc.hour * 60 + loc.minute).to_numpy()
        out |= np.abs(mod - minute) <= minutes
    return out


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415
    from m15_trades import PARTS  # noqa: PLC0415

    m = plib.load()
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    ny = plib.ny_mask(m.index)
    done = m.index + pd.Timedelta(minutes=1)  # each M1 bar's close
    done_ns = done.as_unit("ns").asi8
    exam = "exam" in sys.argv[1:]
    a, b = (PARTS["exam"] if exam else (PARTS["P1"][0], PARTS["P2"][1]))
    first = int(np.searchsorted(m.index, pd.Timestamp(a, tz="UTC")))
    last = int(np.searchsorted(m.index, pd.Timestamp(b, tz="UTC")))
    lo_i = first - 400
    trend = structure(m, done_ns[lo_i:last])
    trend = np.where(active(done[lo_i:last]), trend, 0)  # only when gold runs
    b5 = bars(m, "5min")
    a5 = F.atr(b5.high.to_numpy(), b5.low.to_numpy(), b5.close.to_numpy(), 14)
    k5 = at(pd.DatetimeIndex(b5["avail"]).as_unit("ns").asi8, done_ns[lo_i:last])
    atr5 = np.where(k5 >= 0, a5[np.maximum(k5, 0)], np.nan)
    S = signals(h[lo_i:last], lo[lo_i:last], c[lo_i:last], trend, atr5)
    S["i"] += lo_i
    S = S[S.i >= first].reset_index(drop=True)
    rows, busy = [], -1
    for r in S.itertuples():
        j = int(r.i) + 1
        if j <= busy or j >= len(o):
            continue
        x = manage(o, h, lo, c, sp, ny, j, int(r.side), float(r.extreme))
        if x is None:
            continue
        rows.append(dict(t=m.index[j], side=int(r.side), R=x["pnl"] / x["r0"], **x))
        busy = x["xj"]
    T = pd.DataFrame(rows)
    if exam:
        T["part"] = "exam"
        parts = ("exam",)
    else:
        T["part"] = np.where(T.t < pd.Timestamp(PARTS["P2"][0], tz="UTC"), "P1", "P2")
        parts = ("P1", "P2")
    print(f"signals {len(S)}; trades {len(T)}")
    for p in parts:
        D = T[T.part == p]
        eq = D.pnl.cumsum()
        print(f"{p}: {len(D)} trades ({len(D) / np.busday_count(*PARTS[p]):.2f} a weekday), win {(D.pnl > 0).mean():.3f}, R {D.R.mean():+.3f}, "
              f"USD {D.pnl.sum():+.1f}, risk median {D.r0.median():.2f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, worst {D.pnl.min():+.2f}, "
              f"streak {wf.longest_run(D.pnl.to_numpy() < 0)}, exits {D.exit.value_counts().to_dict()}, buys {int((D.side > 0).sum())} / "
              f"sells {int((D.side < 0).sum())}")
    if exam:
        T["cell"] = "pullback15"
        pd.set_option("display.width", 220)
        print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / f"pullback15_trades{'_exam' if exam else ''}.parquet")


if __name__ == "__main__":
    main()
