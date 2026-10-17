"""Round 0: baselines (market vs limit fade of a 5-minute stretch)."""
from exp import Lab
L = Lab()
base = dict(feat="z5", thr=3.0, sl=3, tp=3, hold=60)
for name, cfg in [
    ("market fade z5>=3 3/3 atr", base),
    ("limit 0.5atr v10", base | dict(off=0.5, valid=10)),
    ("limit 1atr v10", base | dict(off=1.0, valid=10)),
    ("limit 2atr v15", base | dict(off=2.0, valid=15)),
    ("market fade z5>=3 tp floor5 sl=tp", base | dict(tp_floor=5, rr=1.0)),
]:
    print("\n##", name); L.run(cfg)
