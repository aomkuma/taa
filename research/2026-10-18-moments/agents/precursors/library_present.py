"""The library's run-start pictures by eye (owner, 2026-10-19: "the library's pictures must be what the bot sees in
the present - many look as if price has already broken"): run starts whose M1 close sits below its last bottom (an
up run) or above its last top (a down run), drawn as the bot saw them at the start (M5, M1) with the bars that
followed in grey - the break had happened, the run that labels the picture came after it.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/library_present.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from wf_library_compare import Charts  # noqa: E402

TH = "Asia/Bangkok"


def main() -> None:
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    C = Charts(plib.load())
    rng = np.random.default_rng(41)
    learn = np.asarray(pd.DatetimeIndex(T.t_dec) < plib.EXAM_START)
    up = np.nonzero(learn & (T.kind == "run").to_numpy() & (T.cls == "ran_up").to_numpy() & (T.M1_brk == -1).to_numpy())[0]
    dn = np.nonzero(learn & (T.kind == "run").to_numpy() & (T.cls == "ran_dn").to_numpy() & (T.M1_brk == 1).to_numpy())[0]
    out = HERE / "png" / "library_present"
    out.mkdir(parents=True, exist_ok=True)
    for n, e in enumerate(list(rng.choice(up, 2, replace=False)) + list(rng.choice(dn, 2, replace=False))):
        t_dec = pd.Timestamp(T.t_dec.iloc[e])
        fig, axes = plt.subplots(1, 2, figsize=(19, 6.5))
        for ax, tf in zip(axes, ("M5", "M1")):
            C.panel(ax, tf, t_dec, f"{tf} at the run's start (grey: the bars after it)")
        when = t_dec.tz_convert(TH)
        way = "UP" if T.cls.iloc[e] == "ran_up" else "DOWN"
        fig.suptitle(f"Library entry {when:%Y-%m-%d %H:%M} TH - the start of a 10 U run {way}: at this moment M1 had just closed "
                     f"{'BELOW its last bottom' if way == 'UP' else 'ABOVE its last top'} (a break the other way); the run that "
                     "labels the picture came after it", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        f = out / f"{n:02d}_{way.lower()}_{when:%Y%m%d_%H%M}.png"
        fig.savefig(f, dpi=64)
        plt.close(fig)
        print(f, flush=True)


if __name__ == "__main__":
    main()
