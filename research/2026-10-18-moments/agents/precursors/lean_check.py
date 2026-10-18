"""Is the trigger layer's lean real? (rarity_lean.py: the M5+M1 situation leaned the way of the next 10 U run in both
halves.) Three checks before any trade test:
1. an independent recount - the matching days and the lean of 300 snaps per half at levels 3 and 6, re-derived from
   the rule's text with its own code (no picture.py / rarity.py), equal to rarity_lean_snaps.parquet;
2. the error with each day's snaps counted as one (one run often follows several snaps of an hour);
3. placebos - the same lean against what followed the same snap time on the trading day before and after (a trend
   of several days would lean there too; the moment's own information would not).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/lean_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402

LEVELS = {"3 +last top/bottom": ("smooth", "pullback", "break"),
          "6 +position": ("smooth", "pullback", "break", "way", "size", "position")}


def recount(T: pd.DataFrame, day: np.ndarray, r: int, parts: tuple[str, ...]) -> tuple[int, float]:
    """The rule's text, M5 and M1 both: smoothness within 0.1; the deepest pullbacks both under 1 ATR or within a factor
    1.6; the same close against the last top / bottom; the same 120-bar way; sizes within a factor 1.4; positions
    within 0.2 and the same edge. Earlier moments >= 7 days before; one per day (its first); up - down share."""
    ok = pd.Series(day <= day[r] - 7, index=T.index)
    for tf in ("M5", "M1"):
        col = {k: T[f"{tf}_{k}"] for k in ("er", "retr", "brk", "net_way", "size", "pos", "edge")}
        me = {k: v.iloc[r] for k, v in col.items()}
        if "smooth" in parts:
            ok &= (col["er"] - me["er"]).abs() <= 0.1 + 1e-6
        if "pullback" in parts:
            lo_ = np.minimum(col["retr"], me["retr"])
            hi_ = np.maximum(col["retr"], me["retr"])
            ok &= ((col["retr"] < 1.0) & (me["retr"] < 1.0)) | ((lo_ > 0) & (hi_ <= 1.6 * lo_))
        if "break" in parts:
            ok &= col["brk"] == me["brk"]
        if "way" in parts:
            ok &= col["net_way"] == me["net_way"]
        if "size" in parts:
            lo_ = np.minimum(col["size"], me["size"])
            hi_ = np.maximum(col["size"], me["size"])
            ok &= np.isfinite(col["size"]) & np.isfinite(me["size"]) & (hi_ <= 1.4 * lo_)
        if "position" in parts:
            ok &= ((col["pos"] - me["pos"]).abs() <= 0.2 + 1e-6) & (col["edge"] == me["edge"])
    hit = T[ok.to_numpy()]
    if hit.empty:
        return 0, float("nan")
    first = hit.groupby(day[ok.to_numpy()], sort=True).head(1)  # rows are in decision order: each day's first
    up = first.cls.isin(["ran_up", "slow_up"]).mean()
    dn = first.cls.isin(["ran_dn", "slow_dn"]).mean()
    return len(first), float(up - dn)


def clustered(d: np.ndarray, g: np.ndarray) -> float:
    """The standard error of mean(d) with the observations of one group (day) counted together."""
    m = d.mean()
    s = pd.Series(d - m).groupby(g).sum().to_numpy()
    return float(np.sqrt((s**2).sum()) / len(d))


def main() -> None:
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    D = pd.read_parquet(HERE / "rarity_lean_snaps.parquet")
    D["level"] = D.level.str.strip()  # rarity_lean pads the level number
    t = pd.DatetimeIndex(T.t_dec)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((t.tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    cls = T.cls.to_numpy().astype(str)
    # 1. the independent recount
    rng = np.random.default_rng(3)
    for level, parts in LEVELS.items():
        for half in ("learn", "exam "):
            sub = D[(D.layer == "trg") & (D.half == half) & (D.level == level)]
            pick = sub.iloc[np.sort(rng.choice(len(sub), size=300, replace=False))]
            bad = 0
            for row, n, lean in zip(pick.row, pick.n_days, pick.lean):
                n2, lean2 = recount(T, day, int(row), parts)
                same = n2 == n and ((np.isnan(lean) and np.isnan(lean2)) or abs(lean - lean2) < 1e-12)
                bad += int(not same)
            print(f"recount trigger '{level}' {half}: {300 - bad} of 300 snaps equal", flush=True)
    # 2. and 3. the error by day and the placebos
    snap = np.nonzero((T.kind == "snap").to_numpy())[0]
    S = pd.DataFrame({"row": snap, "day": day[snap], "name": T.name.to_numpy()[snap], "cls": cls[snap]})
    days = np.sort(S.day.unique())
    nxt = dict(zip(days[:-1], days[1:]))
    prv = dict(zip(days[1:], days[:-1]))
    by = S.set_index(["day", "name"]).cls
    for level in ("3 +last top/bottom", "6 +position"):
        for half in ("learn", "exam "):
            sub = D[(D.layer == "trg") & (D.half == half) & (D.level == level)]
            pu, pdn = np.mean(cls[sub.row] == "ran_up"), np.mean(cls[sub.row] == "ran_dn")
            go = sub[(sub.n_days >= 5) & (sub.lean.abs() >= 0.2)]
            side = np.sign(go.lean.to_numpy())
            base = np.where(side > 0, pu - pdn, pdn - pu)
            g = day[go.row]
            out = []
            for what, act in (("what followed", cls[go.row]),
                              ("placebo: the trading day after", [by.get((nxt.get(d, -1), nm), "none") for d, nm in
                                                                  zip(g, T.name.to_numpy()[go.row])]),
                              ("placebo: the trading day before", [by.get((prv.get(d, -1), nm), "none") for d, nm in
                                                                   zip(g, T.name.to_numpy()[go.row])])):
                act = np.asarray(act)
                have = act != "none"
                way = np.where(side > 0, act == "ran_up", act == "ran_dn")[have]
                oth = np.where(side > 0, act == "ran_dn", act == "ran_up")[have]
                d = way.astype(float) - oth - base[have]
                out.append(f"{what}: n {int(have.sum())}, edge {d.mean():+.3f} (se {d.std(ddof=1) / np.sqrt(len(d)):.3f}, "
                           f"by day {clustered(d, g[have]):.3f}, {len(np.unique(g[have]))} days)")
            print(f"\ntrigger '{level}' {half}:\n  " + "\n  ".join(out), flush=True)
    print("\n(the exam's snaps are all of the half; the learning half's are a sample of 3,000; base rates per half)",
          plib.EXAM_START.date())


if __name__ == "__main__":
    main()
