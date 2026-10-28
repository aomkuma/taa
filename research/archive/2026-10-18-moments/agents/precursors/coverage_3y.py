"""Will the bot find the same picture when it looks (owner, 2026-10-19: "if the bot uses it for real, will it catch
patterns?")? The library of three years (snaps and the starts of 10 U runs, moments.py) under the same-picture rule
(picture.py), walk-forward with evidence from other episodes only (>= 7 days before): at every snap, per layer, is
there a pattern, and how many earlier episodes does it have?

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/coverage_3y.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from picture import FastPictureLibrary, evidence  # noqa: E402
from v2c import layer_inputs  # noqa: E402


def main() -> None:
    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((pd.DatetimeIndex(T.t_dec).tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    snap = (T.kind == "snap").to_numpy()
    half = np.where(pd.DatetimeIndex(T.t_dec) < plib.EXAM_START, "learning", "exam")
    rows = []
    for L in ("ctx", "set", "trg"):
        codes, shp, feats = layer_inputs(T, SH, L)
        lib = FastPictureLibrary(codes, shp, feats)
        n_ep = np.full(len(T), -1)
        for r in range(len(T)):
            if snap[r]:
                n_ep[r] = evidence(lib, r, int(day[r]))[0]
            lib.add(r, int(day[r]), str(T.cls.iloc[r]))
        for hv in ("learning", "exam"):
            sel = snap & (half == hv)
            x = n_ep[sel]
            rows.append(dict(layer=L, half=hv, snaps=int(sel.sum()), with_1=int((x >= 1).sum()), with_3=int((x >= 3).sum()),
                             with_5=int((x >= 5).sum()), patterns=len(lib.patterns)))
        print(rows[-2], rows[-1], flush=True)
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
