"""Every layer together (owner, 2026-10-19: "combine every discipline and look at its probability"; notes.md "Research
outside ..."). One row per candidate trade, every feature known at its decision (closed bars only):
- the event: a pierce of the latest swing top / bottom on M5 .. H1 taken two ways (the reversal, the continuation);
  a double bottom / top at its turn and at its neckline; the first touch of an H1 / H4 level from M5 (the reversal);
- the place on H1 and H4 on the trade's side (where in the 120-bar range; the distance to the nearest level the trade
  leans on, in that timeframe's ATRs), the nearest round 50 (ahead of the trade or behind it, in H1 ATRs);
- the flow: H1 / H4 way and swing structure with or against the trade (moments.pictures_at);
- the moment: the session hour, inside the owner's windows; the M5 ATR against its own 20-day median;
and what followed: the 1-ATR first passage the trade's way (the event timeframe's ATR), the furthest way and against.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/combine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# this folder's moments.py before plib (plib puts the research folder first, whose moments.py would shadow it)
from moments import pictures_at  # noqa: E402, I001
import plib  # noqa: E402
from explore import HORIZON, excursions  # noqa: E402
from loc import location  # noqa: E402
from mw import first_passage  # noqa: E402
from touch import touches  # noqa: E402

TFS = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h"}


def side_place(R: pd.DataFrame, tf: str) -> tuple[np.ndarray, np.ndarray]:
    """The place on tf from the trade's side: a buy's own edge is the range low and its level the bottom below; a sell
    the mirror. pos_side 0 = at the trade's own edge, 1 = at the far edge."""
    pos = np.where(R.side > 0, R[f"{tf}_pos"], 1 - R[f"{tf}_pos"])
    lean = np.where(R.side > 0, R[f"{tf}_d_bot"], R[f"{tf}_d_top"])
    return pos, lean


def main() -> None:
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415

    plib.gold.below_normal_priority()
    mm = plib.load()
    m = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), l=mm.low.to_numpy(float), ot=mm.index.as_unit("ns").asi8)
    m_av = (mm.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8
    cl = mm.close.to_numpy(float)
    bars, Ys = {}, {}
    for tf, rule in {**TFS, "H4": "4h"}.items():
        b = plib.tf_bars(mm, rule)
        R = raw(b)
        bars[tf] = dict(avail=pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, h=R["h"], lo=R["lo"], c=R["c"], atr=R["atr"],
                        piv=zigzag(R["h"], R["lo"], R["atr"], ZZ_K))
    Ys = {tf: bars[tf] for tf in ("H1", "H4")}
    rows = []
    # pierces both ways, doubles at both entries (explore.py, located by loc.py)
    Pi = pd.read_parquet(HERE / "explore_pierces.parquet")
    for play, sgn in (("pierce_reversal", 1), ("pierce_continuation", -1)):
        x = Pi.copy()
        x["side"] = x.side * sgn
        x["kind"] = play
        rows.append(x)
    Do = pd.read_parquet(HERE / "explore_doubles.parquet")
    Do["kind"] = "double_" + Do.entry
    rows.append(Do)
    # the first touches of H1 / H4 levels from M5
    m5 = bars["M5"]
    for ytf, Y in Ys.items():
        T = touches(m5["h"], m5["lo"], m5["avail"], Y)
        T["t"] = pd.to_datetime(m5["avail"][T.i.to_numpy()], utc=True)
        T["tf"], T["kind"] = "M5", f"touch_{ytf}"
        rows.append(T)
    A = pd.concat(rows, ignore_index=True)
    A = A[A.t >= pd.Timestamp("2023-11-01", tz="UTC")].reset_index(drop=True)
    t = pd.DatetimeIndex(A.t).as_unit("ns").asi8
    A["j0"] = np.searchsorted(m["ot"], t)
    A = A[A.j0 < len(m["o"])].reset_index(drop=True)
    t = pd.DatetimeIndex(A.t).as_unit("ns").asi8
    A["px"] = cl[np.searchsorted(m_av, t, side="right") - 1]  # the last M1 close at the decision
    # the event timeframe's ATR at the decision, the outcomes on the trade's side
    atr_ev = np.full(len(A), np.nan)
    for tf in TFS:
        k = (A.tf == tf).to_numpy()
        bi = np.searchsorted(bars[tf]["avail"], t[k], side="right") - 1
        atr_ev[k] = bars[tf]["atr"][bi]
    A["atr_ev"] = atr_ev
    fav, adv = excursions(m["o"], m["h"], m["l"], A.j0.to_numpy(), A.side.to_numpy(), HORIZON)
    A["fav"], A["adv"] = fav / atr_ev, adv / atr_ev
    A["fp1"] = [first_passage(m["o"], m["h"], m["l"], int(j), int(s), float(a), HORIZON * 4) for j, s, a in zip(A.j0, A.side, atr_ev)]
    # the same outcome as explore.py's for the pierces' reversal (the same first passage on the same side)
    chk = A[A.kind == "pierce_reversal"].merge(Pi[["t", "tf", "side", "level", "fp1", "fav"]], on=["t", "tf", "side", "level"], suffixes=("", "_x"))
    assert len(chk) == len(Pi) and (chk.fp1 == chk.fp1_x).all() and np.allclose(chk.fav, chk.fav_x, equal_nan=True), "outcomes differ"
    print("outcomes done", len(A), "| the pierces' reversal equal to explore.py's:", len(chk), flush=True)
    # the place on H1 / H4
    for tf, Y in Ys.items():
        L = location(t, A.px.to_numpy(), Y)
        for c in L.columns:
            A[f"{tf}_{c}"] = L[c].to_numpy()
        A[f"{tf}_pos_side"], A[f"{tf}_lean"] = side_place(A, tf)
    # the nearest round 50 in H1 ATRs, ahead of the trade (+) or behind it (-)
    h1_atr = Ys["H1"]["atr"][np.searchsorted(Ys["H1"]["avail"], t, side="right") - 1]
    r50 = np.round(A.px / 50.0) * 50.0
    A["round50"] = (r50 - A.px) * A.side / h1_atr
    # the flow: H1 / H4 way and structure with the trade (+1), against (-1), flat / mixed (0)
    uniq, inv = np.unique(t, return_inverse=True)
    pics, _sh = pictures_at(mm, uniq, log=False)
    for tf in ("H1", "H4"):
        A[f"{tf}_way"] = pics[f"{tf}_net_way"].to_numpy()[inv] * A.side
        st = pics[f"{tf}_struct"].to_numpy()[inv]
        A[f"{tf}_struct"] = np.where(np.isin(st, [1, -1]), st * A.side, 0)
    # the moment
    A["hour_utc"] = pd.DatetimeIndex(A.t).hour
    A["inwin"] = plib.window_mask(pd.DatetimeIndex(A.t)).any(axis=1).to_numpy()
    m5_atr = pd.Series(bars["M5"]["atr"], index=pd.to_datetime(bars["M5"]["avail"], utc=True))
    med = m5_atr.rolling("20D").median()  # trailing: known at each bar
    ai = np.searchsorted(bars["M5"]["avail"], t, side="right") - 1
    A["atr_rel"] = bars["M5"]["atr"][ai] / med.to_numpy()[ai]
    A["half"] = np.where(pd.DatetimeIndex(A.t) >= plib.EXAM_START, "exam", "learn")
    keep = ["t", "half", "kind", "tf", "side", "depth", "closed_back", "second_share", "gap", "H1_pos_side", "H1_lean",
            "H4_pos_side", "H4_lean", "round50", "H1_way", "H1_struct", "H4_way", "H4_struct", "hour_utc", "inwin", "atr_rel",
            "fp1", "fav", "adv", "j0", "px", "atr_ev"]
    A[keep].to_parquet(HERE / "combined_events.parquet")
    print("saved", len(A), A.kind.value_counts().to_dict(), flush=True)


if __name__ == "__main__":
    main()
