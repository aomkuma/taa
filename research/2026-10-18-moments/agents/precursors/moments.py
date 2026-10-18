"""The library's moments (owner, 2026-10-19: "add the snaps of three years"; "if price runs significantly - as far as
our target - add it to the library"): the snaps at the owner's times and the start of every 10 U run (V2's target)
inside the owner's windows, from 2023-11 on. Each moment keeps what the bot sees at its decision (the close of its
M1 bar): the core codes per timeframe (fingerprint + S/R, `library_match.moment_codes`, equal to the snaps' own -
test_evidence_journal), the 120-bar outlines (`snaps.shapes`), the pictures (`picture.features`), and what followed
(a snap's class; a run: ran up / ran down).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/moments.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402

FIRST = pd.Timestamp("2023-11-01", tz="UTC")
TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
RULE = {"H4": "4h", "H1": "1h", "M30": "30min", "M15": "15min", "M5": "5min"}
# the zoom (owner, 2026-10-19: "look at the smaller timeframe - M5 shows the swings"): the timeframe a reading of
# 9 (too few swings) is read from; M1 has nothing smaller and reads its own bars with a finer ZigZag ("M1f")
SMALLER = {"H4": "H1", "H1": "M30", "M30": "M15", "M15": "M5", "M5": "M1", "M1": "M1f"}
M1F_K = 1.5  # M1f's ZigZag reversal in ATRs (the pictures use fingerprint.ZZ_K = 3)


def small_span(big_avail: np.ndarray, small_avail: np.ndarray, bi: int, win: int) -> tuple[int, int]:
    """The bars of the smaller timeframe covering the larger one's window of `win` bars ending at bar bi: from the
    first one completing after the bar before the window completed (0 when the window starts at the first bar) to the
    last one completing with bar bi (its last M1 bar is bar bi's)."""
    a0 = max(bi - win + 1, 0)
    s0 = 0 if a0 == 0 else int(np.searchsorted(small_avail, big_avail[a0 - 1], side="right"))
    s1 = int(np.searchsorted(small_avail, big_avail[bi], side="right")) - 1
    return s0, s1


def zoom_all(f: list[dict], big: dict, sm: dict, win: int) -> np.ndarray:
    """picture.zoom for every moment: a structure or break reading of 9 on the larger timeframe is read from the
    smaller one's swings over the same span, against the larger bar's close. big / sm: R (raw bars: h, lo, c), piv
    (ZigZag swings), avail (completion times); big also bi (every moment's decision bar). Replaces f's entries;
    returns 1 where a reading changed."""
    from picture import zoom  # noqa: PLC0415

    changed = np.zeros(len(f), np.int8)
    for i, fa in enumerate(f):
        if fa["struct"] != 9 and fa["brk"] != 9:
            continue
        b = int(big["bi"][i])
        s0, s1 = small_span(big["avail"], sm["avail"], b, win)
        new = zoom(fa, (sm["R"]["h"], sm["R"]["lo"], float(big["R"]["c"][b]), sm["piv"], s1, s0))
        changed[i] = int((new["struct"], new["brk"]) != (fa["struct"], fa["brk"]))
        f[i] = new
    return changed


def run_starts(C: pd.DataFrame, index: pd.DatetimeIndex, first: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """The runs whose start bar closes inside the owner's windows, first <= start < end: the decision is that bar's close."""
    t = index[C.i.to_numpy()]
    win = plib.window_mask(t).any(axis=1).to_numpy()
    keep = win & np.asarray(t >= first) & np.asarray(t < end)
    out = C[keep].copy()
    out["bar_t"] = t[keep]
    out["cls"] = np.where(out.side > 0, "ran_up", "ran_dn")
    return out.reset_index(drop=True)


def main() -> None:
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415
    from library_match import moment_codes  # noqa: PLC0415
    from picture import WIN, features  # noqa: PLC0415
    from snaps import NPTS, shapes  # noqa: PLC0415

    plib.gold.below_normal_priority()
    m = plib.load()
    S = pd.read_parquet(HERE / "snaps_3y.parquet")
    R = run_starts(pd.read_parquet(HERE / "runs_10.parquet"), m.index, FIRST, plib.EXAM_END)
    print(f"snaps {len(S)}, run starts {len(R)} (up {int((R.side > 0).sum())}, down {int((R.side < 0).sum())})", flush=True)
    # one table: the decision time, the M1 bar, the kind, what followed
    snap_bar = m.index[S.idx.to_numpy()]
    T = pd.concat([pd.DataFrame({"t_dec": S.S, "bar_t": snap_bar, "kind": "snap", "cls": S.cls, "name": S.name}),
                   pd.DataFrame({"t_dec": R.bar_t + pd.Timedelta(minutes=1), "bar_t": R.bar_t, "kind": "run", "cls": R.cls,
                                 "name": ""})], ignore_index=True)
    T = T.sort_values(["t_dec", "kind"], kind="stable").reset_index(drop=True)
    FM, CM = moment_codes(m, pd.DatetimeIndex(T.bar_t))
    # the outlines and the pictures at the last bar closed by each decision
    t_ns = pd.DatetimeIndex(T.t_dec).as_unit("ns").asi8
    SH = np.zeros((len(T), len(TFS), NPTS), np.float32)
    pics, feats = {}, {}
    store = {}  # per timeframe what the zoom needs: bars, swings, completion times, every moment's decision bar
    for k, tf in enumerate(TFS):
        if tf == "M1":
            b = m.reset_index(drop=True).assign(avail=m.index + pd.Timedelta(minutes=1))
        else:
            b = plib.tf_bars(m, RULE[tf])
        Rr = raw(b)
        piv = zigzag(Rr["h"], Rr["lo"], Rr["atr"], ZZ_K)
        avail = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        bi = np.searchsorted(avail, t_ns, side="right") - 1
        sh, _rng = shapes(b.close.to_numpy(float), bi, 120)
        SH[:, k] = sh
        feats[tf] = [features(Rr["h"], Rr["lo"], Rr["c"], Rr["atr"], piv, int(x)) for x in bi]
        store[tf] = dict(R=Rr, piv=piv, avail=avail, bi=bi)
        if tf == "M1":
            store["M1f"] = dict(R=Rr, piv=zigzag(Rr["h"], Rr["lo"], Rr["atr"], M1F_K), avail=avail, bi=bi)
        print(tf, "done", flush=True)
    for tf in TFS:
        big, sm = store[tf], store[SMALLER[tf]]
        # the span's last smaller bar completes with the larger bar (the same last M1 bar): the same close
        s1 = np.searchsorted(sm["avail"], big["avail"][big["bi"]], side="right") - 1
        assert np.array_equal(sm["R"]["c"][s1], big["R"]["c"][big["bi"]]), tf
        zoomed = zoom_all(feats[tf], big, sm, WIN)
        for key in feats[tf][0]:
            pics[f"{tf}_{key}"] = [d[key] for d in feats[tf]]
        pics[f"{tf}_zoomed"] = zoomed
        print(tf, "zoomed", int(zoomed.sum()), flush=True)
    T = pd.concat([T, FM.reset_index(drop=True), CM.reset_index(drop=True), pd.DataFrame(pics)], axis=1)
    T.to_parquet(HERE / "moments_3y.parquet")
    np.save(HERE / "moment_shapes_3y.npy", SH)
    print("saved", T.shape, SH.shape)


if __name__ == "__main__":
    main()
