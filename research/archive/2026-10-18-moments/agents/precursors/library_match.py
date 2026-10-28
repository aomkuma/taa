"""Which evidence in the library matches a given moment? (owner, 2026-10-18: "the four losing pictures - which library
sets do they match? compare them") For each moment: the core-formation fingerprint of the six timeframes (as the snaps
library), the earlier library snaps (before the moment, other days) with >= 80 % of the attributes equal per layer, and
what followed them.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/library_match.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from cluster_fp import core_cols, onehot  # noqa: E402
from fingerprint import fingerprint, raw  # noqa: E402
from library import SR_BARS, indicators, sr_codes, sr_levels  # noqa: E402

TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
LAYERS = {"context (H4+H1)": ("H4", "H1"), "setup (M30+M15)": ("M30", "M15"), "trigger (M5+M1)": ("M5", "M1")}
MOMENTS = [  # the four losing LV2 trades the owner looked at (Thai time of the decision bar)
    ("1 SELL 2026-03-09 09:29", "2026-03-09 09:29", -1),
    ("2 BUY 2026-04-10 06:59", "2026-04-10 06:59", 1),
    ("3 BUY 2026-04-10 09:09", "2026-04-10 09:09", 1),
    ("4 BUY 2026-02-25 15:04", "2026-02-25 15:04", 1),
]
CLS = ["ran_up", "slow_up", "ran_dn", "slow_dn", "fake_up", "fake_dn", "flat", "drift"]


def moment_codes(m: pd.DataFrame, bars_t: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fingerprints and S/R codes at the close of the given M1 bars, the same way snaps.py / fingerprint.py did."""
    idx = m.index.get_indexer(bars_t)
    assert (idx >= 0).all()
    t_dec = (bars_t + pd.Timedelta(minutes=1)).to_numpy()
    price = m.close.to_numpy(float)[idx]
    F_parts, codes = [], {}
    for tf in TFS:
        if tf == "M1":
            b = m.rename(columns={"tick_volume": "tv"}).assign(avail=m.index + pd.Timedelta(minutes=1)).reset_index(drop=True)
            bi = idx.copy()
        else:
            b = plib.tf_bars(m, RULE[tf])
            bi = np.searchsorted(b["avail"].to_numpy(), t_dec, side="right") - 1
        fp = fingerprint(raw(b), bi)
        fp.columns = [f"{tf}_fp_{x}" for x in fp.columns]
        F_parts.append(fp)
        if tf in SR_BARS:
            _cd, atr, _st = indicators(b)
            lv = sr_levels(b, atr, SR_BARS[tf])
            cl = b.close.to_numpy(float)
            back = np.where(bi >= 3, cl[np.maximum(bi - 3, 0)], np.nan)
            loc, _imp = sr_codes(lv, bi, price, back, atr[bi])
            codes[f"{tf}_sr_loc"] = loc
    return pd.concat(F_parts, axis=1), pd.DataFrame(codes)


def attrs(F: pd.DataFrame, C: pd.DataFrame, tfs) -> list[np.ndarray]:
    cols = []
    for tf in tfs:
        cols += core_cols(F, tf)
        if f"{tf}_sr_loc" in C.columns:
            cols.append(C[f"{tf}_sr_loc"].to_numpy())
    return cols


def main() -> None:
    m = plib.load()
    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    times = pd.DatetimeIndex([pd.Timestamp(x[1], tz="Asia/Bangkok").tz_convert("UTC") for x in MOMENTS])
    FM, CM = moment_codes(m, times)
    print("library: core-formation snaps (20 a day at the owner's times), matched >= 80 % of the attributes, earlier days only\n")
    rows = []
    for k, (name, _t, side) in enumerate(MOMENTS):
        lib = S.S < times[k].normalize()  # the library as it was before that day
        for layer, tfs in LAYERS.items():
            a_lib = attrs(FS[lib.to_numpy()].reset_index(drop=True), S[lib].reset_index(drop=True), tfs)
            a_mom = attrs(FM.iloc[[k]].reset_index(drop=True), CM.iloc[[k]].reset_index(drop=True), tfs)
            V = onehot([np.r_[x, y] for x, y in zip(a_lib, a_mom)])
            sims = V[:-1] @ V[-1]
            hit = S[lib].reset_index(drop=True)[sims >= 0.8 - 1e-6]
            days = hit.S.dt.tz_convert("Asia/Bangkok").dt.normalize().nunique()
            share = hit.cls.value_counts(normalize=True)
            up = share.get("ran_up", 0) + share.get("slow_up", 0)
            dn = share.get("ran_dn", 0) + share.get("slow_dn", 0)
            fake = share.get("fake_up", 0) + share.get("fake_dn", 0)
            with_trade = up if side > 0 else dn
            against = dn if side > 0 else up
            rows.append(dict(trade=name, layer=layer, matches=len(hit), days=days, best_sim=round(float(sims.max()), 2),
                             with_trade=round(with_trade, 2), against=round(against, 2), fake=round(fake, 2),
                             flat=round(share.get("flat", 0), 2),
                             ran10=round(share.get("ran_up", 0) + share.get("ran_dn", 0), 2)))
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(R.to_string(index=False))
    R.to_csv(HERE / "library_match_4losers.csv", index=False)


if __name__ == "__main__":
    main()
