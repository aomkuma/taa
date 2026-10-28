"""Round 1: the scan's two families, checked with the full simulator and a seeded coin (3 seeds)."""
import warnings; warnings.filterwarnings("ignore")
from exp import Lab
L = Lab()
A = dict(feat="dv60", thr=3.0, ses=[3], trend="with", sl=6, tp=6, hold=120)
C = dict(feat="dv15", thr=3.0, ses=[2], trend="with", follow=True, sl=3, tp=3, hold=60, off=1.0, valid=10)
for name, cfg in [
    ("A0 US-afternoon fade dv60>=3 with H1, market 6/6 atr 120m", A),
    ("A1 same, limit 1 atr v15", A | dict(off=1.0, valid=15)),
    ("A2 same, no trend filter", A | dict(trend=None)),
    ("C0 NY follow dv15>=3 with H1, limit 1atr v10, 3/3", C),
    ("C1 same, market", {k: v for k, v in C.items() if k not in ("off", "valid")}),
]:
    print("\n##", name); L.run(cfg, coin_seeds=3)
