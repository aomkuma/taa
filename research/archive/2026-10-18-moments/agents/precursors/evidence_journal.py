"""R13 (notes.md): every trade records its library evidence. For each trade's decision bar, the core-formation
fingerprint of the six timeframes is matched against the library snaps of EARLIER days (>= 80 % of the attributes
equal, per layer), and the matches' outcomes are summarised relative to the trade's side.

    from evidence_journal import evidence
    E = evidence(m, decision_bar_times_utc, sides)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cluster_fp import onehot  # noqa: E402
from library_match import LAYERS, attrs, moment_codes  # noqa: E402

SHORT = {"context (H4+H1)": "ctx", "setup (M30+M15)": "set", "trigger (M5+M1)": "trg"}
THR = 0.8


def evidence_label(out: pd.DataFrame, n: str) -> np.ndarray:
    """One word per trade: the layers seen on >= 5 earlier days each add (share with - share against); the sum >= 0.1
    "supports", <= -0.1 "against", else "mixed"; no layer on 5 days: "none"."""
    lean = np.zeros(len(out))
    for L in SHORT.values():
        ok = out[f"{L}_{n}"] >= 5
        lean += np.where(ok, np.nan_to_num(out[f"{L}_with"] - out[f"{L}_against"]), 0.0)
    none = (out[[f"{L}_{n}" for L in SHORT.values()]] < 5).all(axis=1).to_numpy()
    return np.where(none, "none", np.where(lean >= 0.1 - 1e-9, "supports", np.where(lean <= -0.1 + 1e-9, "against", "mixed")))


def match_pool(VP: np.ndarray, day_p: np.ndarray, up: np.ndarray, dn: np.ndarray, fake: np.ndarray, flat: np.ndarray,
               VQ: np.ndarray, day_q: np.ndarray, side_q: np.ndarray, thr: float = THR) -> dict[str, np.ndarray]:
    """Each query against the pool entries of EARLIER days (similarity = one-hot dot >= thr): matches, days, best
    similarity, and the shares of what followed - with the query's side, against it, faked, flat."""
    nq = len(VQ)
    cols = {k: np.full(nq, np.nan) for k in ("n", "days", "best", "with", "against", "fake", "flat")}
    for a in range(0, nq, 400):
        sims = VQ[a:a + 400] @ VP.T
        sims = np.where(day_p[None, :] < day_q[a:a + 400, None], sims, -1.0)
        for r in range(sims.shape[0]):
            i = a + r
            hit = sims[r] >= thr - 1e-6
            n = int(hit.sum())
            cols["n"][i] = n
            cols["best"][i] = float(sims[r].max()) if sims.shape[1] else np.nan
            cols["days"][i] = len(np.unique(day_p[hit])) if n else 0
            if n:
                u, d = up[hit].mean(), dn[hit].mean()
                cols["with"][i] = u if side_q[i] > 0 else d
                cols["against"][i] = d if side_q[i] > 0 else u
                cols["fake"][i] = fake[hit].mean()
                cols["flat"][i] = flat[hit].mean()
    return cols


def evidence(m: pd.DataFrame, bars_t: pd.DatetimeIndex, sides: np.ndarray, grow: bool = True) -> pd.DataFrame:
    """One row per trade: per layer the matches, their days, the best similarity, and what followed them. The library
    = the snaps, and (grow, owner 2026-10-18: "new patterns go into the library too, so a far run is learned") every
    trade moment with its own outcome - both only from days before the trade's day."""
    import snaps  # noqa: PLC0415

    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    FM, CM = moment_codes(m, bars_t)
    snap_day = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize().to_numpy()
    trade_day = bars_t.tz_convert("Asia/Bangkok").normalize().to_numpy()
    cls_snap = S.cls.to_numpy()
    if grow:  # the trade moments' own outcomes, labelled exactly like the snaps (the 30 / 60 minutes after)
        idx = m.index.get_indexer(bars_t)
        Q = pd.DataFrame({"S": bars_t + pd.Timedelta(minutes=1), "idx": idx})
        cats = {xu: pd.read_parquet(HERE / f"runs_{xu}.parquet") for xu in (10, 5)}
        cls_trade = snaps.labels(m, Q, cats).cls.to_numpy()
    out = pd.DataFrame({"t": bars_t, "side": sides})
    for layer, tfs in LAYERS.items():
        a_lib = attrs(FS, S, tfs)
        a_mom = attrs(FM.reset_index(drop=True), CM.reset_index(drop=True), tfs)
        V = onehot([np.r_[x, y] for x, y in zip(a_lib, a_mom)])
        VL, VM = V[:len(S)], V[len(S):]
        if grow:
            VP, day_p, cls_p = np.vstack([VL, VM]), np.r_[snap_day, trade_day], np.r_[cls_snap, cls_trade]
        else:
            VP, day_p, cls_p = VL, snap_day, cls_snap
        cols = match_pool(VP, day_p, np.isin(cls_p, ["ran_up", "slow_up"]), np.isin(cls_p, ["ran_dn", "slow_dn"]),
                          np.isin(cls_p, ["fake_up", "fake_dn"]), cls_p == "flat", VM, trade_day, sides)
        for k, v in cols.items():
            out[f"{SHORT[layer]}_{k}"] = v
    if grow:
        out["own_outcome"] = cls_trade  # what followed this trade's moment - the library's new entry
    out["evidence"] = evidence_label(out, "days")
    return out


def evidence_patterns(m: pd.DataFrame, bars_t: pd.DatetimeIndex, sides: np.ndarray) -> tuple[pd.DataFrame, dict]:
    """R13 with the pattern library (owner, 2026-10-18): the snaps and the trade moments are counted into patterns in
    time order (a repeat raises a pattern's count; a new picture starts a pattern); each trade records, before it is
    counted itself, its pattern per layer, how many earlier days it occurred and what followed. Returns the per-trade
    record and the libraries (for pictures of the patterns' examples)."""
    import snaps  # noqa: PLC0415
    from pattern_library import PatternLibrary  # noqa: PLC0415

    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    FM, CM = moment_codes(m, bars_t)
    idx = m.index.get_indexer(bars_t)
    cats = {xu: pd.read_parquet(HERE / f"runs_{xu}.parquet") for xu in (10, 5)}
    cls_trade = snaps.labels(m, pd.DataFrame({"S": bars_t + pd.Timedelta(minutes=1), "idx": idx}), cats).cls.to_numpy()
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    snap_day = ((S.S.dt.tz_convert("Asia/Bangkok").dt.normalize() - day0).dt.days).to_numpy()
    trade_day = ((bars_t.tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    # events in time order: snaps at their second, trades at their decision (the bar's close)
    ev_t = np.r_[S.S.to_numpy(), (bars_t + pd.Timedelta(minutes=1)).to_numpy()]
    is_trade = np.r_[np.zeros(len(S), bool), np.ones(len(bars_t), bool)]
    order = np.argsort(ev_t, kind="stable")
    out = pd.DataFrame({"t": bars_t, "side": sides, "own_outcome": cls_trade})
    libs = {}
    for layer, tfs in LAYERS.items():
        a_lib = attrs(FS, S, tfs)
        a_mom = attrs(FM.reset_index(drop=True), CM.reset_index(drop=True), tfs)
        V = onehot([np.r_[x, y] for x, y in zip(a_lib, a_mom)])
        lib = PatternLibrary(V.shape[1])
        rec = {k: np.full(len(bars_t), np.nan) for k in ("pid", "sim", "count", "with", "against", "fake", "flat", "new",
                                                          "joined")}
        for e in order:
            if is_trade[e]:
                i = e - len(S)
                ev = lib.evidence(V[e], int(trade_day[i]), int(sides[i]))
                joined, new = lib.add(V[e], int(trade_day[i]), str(cls_trade[i]), moment=("trade", bars_t[i]))
                # pid = the pattern the evidence came from (created on an earlier day); joined = the one this moment was
                # counted into (it can be a pattern first seen earlier the same day) - bug to 2026-10-18: pid was joined
                rec["pid"][i], rec["joined"][i], rec["sim"][i], rec["count"][i] = ev["pid"], joined, ev["sim"], ev["count"]
                rec["with"][i], rec["against"][i] = ev["with_"], ev["against"]
                rec["fake"][i], rec["flat"][i], rec["new"][i] = ev["fake"], ev["flat"], float(new)
            else:
                lib.add(V[e], int(snap_day[e]), str(S.cls.iloc[e]), moment=("snap", S.S.iloc[e]))
        for k, v in rec.items():
            out[f"{SHORT[layer]}_{k}"] = v
        libs[SHORT[layer]] = lib
    out["evidence"] = evidence_label(out, "count")
    return out, libs
