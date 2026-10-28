"""Round 3: one rule for the day - buy the dip in an H1 uptrend / sell the rally in a downtrend, at a limit below
(above) the market, with a wide ATR stop and target. London + New York + the US afternoon (no Asia, nothing after
15:30 ET). Development half-years only, real costs."""

from __future__ import annotations

import sys
import warnings

from exp import Lab
from r2 import line
import r2

warnings.filterwarnings("ignore")
L = r2.L
DAY = [("ldn", 7 * 60, 24 * 60)]  # combined below with ny < 15:30 via extra
TDL = dict(feat="dv60", thr=3.0, ses=[1, 2, 3], trend="with", sl=6, tp=6, hold=120, off=1.0, valid=15,
           extra=lambda F, side: (L.B.ny_min < 930) & (L.B.ldn_min >= 420))

VARIANTS = [("base dv60>=3 off1 6/6/120", TDL)]
VARIANTS += [(f"feat {f}>={t}", TDL | dict(feat=f, thr=t)) for f, t in
             (("dv60", 2.0), ("dv60", 4.0), ("dv60", 5.0), ("de50", 3.0), ("de50", 4.0), ("bb20", 2.5),
              ("dv30", 3.0), ("z15", 2.5), ("z30", 2.5))]
VARIANTS += [(f"off {x}", TDL | dict(off=x)) for x in (0.0, 0.5, 1.5, 2.0, 3.0)]
VARIANTS += [(f"sl/tp/hold {a}/{b}/{h}", TDL | dict(sl=a, tp=b, hold=h)) for a, b, h in
             ((4, 4, 90), (6, 8, 180), (8, 8, 180), (8, 6, 180), (5, 8, 180), (10, 10, 240))]
VARIANTS += [("market", {k: v for k, v in TDL.items() if k not in ("off", "valid")}),
             ("no trend", TDL | dict(trend=None)), ("against trend", TDL | dict(trend="against"))]
VARIANTS += [(f"session {s} only", TDL | dict(ses=[s])) for s in (1, 2, 3)]

if __name__ == "__main__":
    sel = sys.argv[1:]
    for name, cfg in VARIANTS:
        if not sel or any(s in name for s in sel):
            line(name, cfg)
    _ = (Lab, DAY)
