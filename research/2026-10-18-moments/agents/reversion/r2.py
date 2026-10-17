"""Round 2: refine the three families on the development half-years with the real costs (sim.COST = REAL).
One line per variant: R by half-year, the coin's mean R, trades a day, USD at 0.01 lot, losers' kinds vs coin."""

from __future__ import annotations

import sys
import warnings

import numpy as np

from exp import Lab

warnings.filterwarnings("ignore")
L = Lab()

NYC = dict(feat="dv15", thr=3.0, ses=[2], trend="with", follow=True, sl=3, tp=3, hold=60, off=1.0, valid=10)
NYB = dict(feat="bb20", thr=2.5, ses=[2], trend="with", sl=6, tp=6, hold=120, off=1.0, valid=15)
PMA = dict(feat="dv60", thr=4.0, ses=[3], win=[("utc", 16 * 60, 20 * 60)], trend="with", sl=6, tp=6, hold=120)


def line(name: str, cfg: dict) -> None:
    o = L.run(cfg, quiet=True, coin_seeds=2)
    rs = " ".join(f"{v:+.3f}" for v in o.R)
    print(f"{name:42} R {rs} | mean {o.R.mean():+.3f} coin {o.cR.mean():+.3f} edge {o.R.mean() - o.cR.mean():+.3f}"
          f" | {o.pd.mean():.2f}/d win {o.win.mean():.2f} USD {o.usd.sum():+7.0f} | k {o.kinds.iloc[-1]} c {o.ck.iloc[-1]}",
          flush=True)


VARIANTS = {
    "nyc": [("base", NYC)]
    + [(f"off {x}", NYC | dict(off=x)) for x in (0.5, 1.5, 2.0)]
    + [(f"thr {x}", NYC | dict(thr=x)) for x in (2.5, 4.0)]
    + [(f"sl/tp {a}/{b} hold {h}", NYC | dict(sl=a, tp=b, hold=h)) for a, b, h in
       ((3, 4, 60), (4, 4, 90), (4, 6, 120), (6, 6, 120), (2, 3, 60), (3, 6, 120))]
    + [("be 0.6", NYC | dict(be=0.6)), ("valid 5", NYC | dict(valid=5)), ("valid 20", NYC | dict(valid=20)),
       ("feat dv30>=3", NYC | dict(feat="dv30")), ("feat z15>=2.5", NYC | dict(feat="z15", thr=2.5)),
       ("no trend", NYC | dict(trend=None)), ("market", {k: v for k, v in NYC.items() if k not in ("off", "valid")})],
    "nyb": [("base", NYB)]
    + [(f"off {x}", NYB | dict(off=x)) for x in (0.0, 0.5, 2.0)]
    + [(f"thr {x}", NYB | dict(thr=x)) for x in (2.0, 3.0)]
    + [(f"sl/tp {a}/{b} hold {h}", NYB | dict(sl=a, tp=b, hold=h)) for a, b, h in
       ((3, 3, 60), (4, 4, 90), (4, 6, 120), (6, 8, 180), (8, 8, 180))]
    + [("be 0.6", NYB | dict(be=0.6)), ("no trend", NYB | dict(trend=None)),
       ("market", {k: v for k, v in NYB.items() if k not in ("off", "valid")})],
    "pma": [("base", PMA)]
    + [(f"limit off {x}", PMA | dict(off=x, valid=15)) for x in (0.5, 1.0, 2.0)]
    + [(f"thr {x}", PMA | dict(thr=x)) for x in (3.0, 5.0, 6.0)]
    + [("feat de50>=4", PMA | dict(feat="de50")), ("feat dv30>=4", PMA | dict(feat="dv30"))]
    + [(f"sl/tp {a}/{b} hold {h}", PMA | dict(sl=a, tp=b, hold=h)) for a, b, h in
       ((4, 4, 90), (4, 6, 120), (8, 8, 180), (6, 4, 120))]
    + [("hours 12:00-15:30 ET", PMA | dict(win=[("ny", 720, 930)])),
       ("be 0.6", PMA | dict(be=0.6)), ("no trend", PMA | dict(trend=None))],
}

if __name__ == "__main__":
    for fam in sys.argv[1:] or list(VARIANTS):
        print(f"\n### {fam}")
        for name, cfg in VARIANTS[fam]:
            line(name, cfg)
    _ = np
