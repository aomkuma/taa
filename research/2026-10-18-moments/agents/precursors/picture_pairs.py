"""Pairs for the owner's eye (notes.md '"The same picture" redefined'): every snap's picture per timeframe, the
walk-forward library under the new rule, and drawn pairs - the snap beside the pattern it matched - from the learning
half only: eight the new rule calls the same, four the old rule (codes only) called the same and the new one rejects.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/picture_pairs.py
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from cluster_fp import onehot  # noqa: E402
from library_match import LAYERS, attrs  # noqa: E402
from picture import KEYS, FastPictureLibrary, features, same_tf  # noqa: E402
from v2b import LAYER_TFS, NPTS, TFS, OutlineLibrary  # noqa: E402
from wf_library_compare import Charts  # noqa: E402

TH = "Asia/Bangkok"
SHORT = {"context (H4+H1)": "ctx", "setup (M30+M15)": "set", "trigger (M5+M1)": "trg"}


def snap_features(C: Charts, S: pd.DataFrame) -> list[list[dict]]:
    """Per snap, per timeframe (TFS order), the picture at the last bar closed by the snap second."""
    s_ns = pd.DatetimeIndex(S.S).as_unit("ns").asi8
    per_tf = []
    for tf in TFS:
        d = C.tf[tf]
        R, piv = d["R"], d["piv"]
        bis = np.searchsorted(d["avail"], s_ns, side="right") - 1
        per_tf.append([features(R["h"], R["lo"], R["c"], R["atr"], piv, int(bi)) for bi in bis])
    return [[per_tf[k][i] for k in range(len(TFS))] for i in range(len(S))]


def fmt(f: dict) -> str:
    way = {1: "up", -1: "down", 0: "flat"}
    st = {1: "HH/HL", -1: "LH/LL", 0: "mixed", 9: "few swings"}
    return (f"120 bars {way[int(f['net_way'])]}, {st[int(f['struct'])]}, size {f['size']:.0f} ATR, last leg "
            f"{way.get(int(f['leg_way']), '?')} {f['leg']:.1f} ATR, at {f['pos']:.2f} of the range")


def main() -> None:
    plib.gold.below_normal_priority()
    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    SH = np.load(HERE / "snap_shapes.npy").reshape(len(S), len(TFS), NPTS)
    C = Charts(plib.load())
    feats = snap_features(C, S)
    pd.DataFrame([{f"{tf}_{k}": feats[i][j][k] for j, tf in enumerate(TFS) for k in KEYS} for i in range(len(S))]).to_parquet(
        HERE / "snap_pictures.parquet")
    day0 = pd.Timestamp("2000-01-01", tz=TH)
    day = ((S.S.dt.tz_convert(TH).dt.normalize() - day0).dt.days).to_numpy()
    order = np.argsort(S.S.to_numpy(), kind="stable")
    learn = np.asarray(S.S < plib.EXAM_START)
    new_pairs, rejected = [], []
    for layer, tfs in LAYERS.items():
        L = SHORT[layer]
        idx = [TFS.index(tf) for tf in LAYER_TFS[L]]
        codes = np.column_stack(attrs(FS, S, tfs)).astype(int)
        V = onehot(list(codes.T))
        lay_feats = [[feats[i][j] for j in idx] for i in range(len(S))]
        new = FastPictureLibrary(codes, SH[:, idx], lay_feats)
        old = OutlineLibrary(V.shape[1], len(idx), rho=None)
        old_first = {}
        n_new = n_old = 0
        for e in order:
            k = new.best(int(e), before_day=int(day[e]))
            ko, so = old.most_similar(V[e], SH[e][idx], before_day=int(day[e]))
            if k >= 0:
                n_new += 1
                if learn[e]:
                    new_pairs.append((L, int(e), new.patterns[k].first))
            if ko >= 0 and so >= 0.8 - 1e-6:
                n_old += 1
                lead = old_first[ko]
                if k < 0 and learn[e]:
                    why = [f"{LAYER_TFS[L][j]}: " + "; ".join(w) for j in range(len(idx))
                           if (w := same_tf(feats[e][idx[j]], feats[lead][idx[j]], float(np.dot(SH[e][idx[j]], SH[lead][idx[j]]))))]
                    rejected.append((L, int(e), lead, why))
            new.add(int(e), int(day[e]), str(S.cls.iloc[e]))
            pid, is_new = old.add(V[e], SH[e][idx], int(day[e]), str(S.cls.iloc[e]))
            if is_new:
                old_first[pid] = int(e)
        print(f"{layer}: snaps with an earlier-day pattern - old rule (codes) {n_old}, new rule (the same picture) {n_new} "
              f"of {len(S)}; patterns {len(old.patterns)} -> {len(new.patterns)}", flush=True)
    rng = np.random.default_rng(19)
    out = HERE / "png" / "same_picture"
    out.mkdir(parents=True, exist_ok=True)
    chosen = [("same", x) for x in [new_pairs[i] for i in rng.choice(len(new_pairs), size=min(8, len(new_pairs)), replace=False)]]
    chosen += [("rejected", x) for x in [rejected[i] for i in rng.choice(len(rejected), size=min(4, len(rejected)), replace=False)]]
    for n, (kind, item) in enumerate(chosen):
        L, e, lead = item[0], item[1], item[2]
        tfs = LAYER_TFS[L]
        fig = plt.figure(figsize=(20, 7.2))
        gs = fig.add_gridspec(2, 4, height_ratios=[3, 1.2], hspace=0.25, wspace=0.12)
        ax = [fig.add_subplot(gs[0, c]) for c in range(4)]
        ta = fig.add_subplot(gs[1, :])
        ta.axis("off")
        for c, tf in enumerate(tfs):
            C.panel(ax[c], tf, S.S.iloc[e], "NOW")
            C.panel(ax[2 + c], tf, S.S.iloc[lead], "LIBRARY")
        lines = []
        for tf in tfs:
            j = TFS.index(tf)
            corr = float(np.dot(SH[e][j], SH[lead][j]))
            lines.append(f"{tf} now:     {fmt(feats[e][j])}")
            lines.append(f"{tf} library: {fmt(feats[lead][j])}   (outline correlation {corr:.2f})")
        if kind == "rejected":
            lines.append("the old rule (codes only) called these the same; the new rule says no: " + " | ".join(item[3]))
        else:
            lines.append("the new rule: the same picture on both timeframes")
        ta.text(0, 0.98, "\n".join("\n".join(textwrap.wrap(x, 200)) for x in lines), transform=ta.transAxes, fontsize=9,
                va="top", ha="left", family="monospace")
        fig.suptitle(f"{'THE SAME PICTURE (new rule)' if kind == 'same' else 'REJECTED by the new rule (the old rule matched)'}"
                     f"  -  {L} layer  |  now: snap {S.S.iloc[e].tz_convert(TH):%Y-%m-%d %H:%M} TH  |  library: snap "
                     f"{S.S.iloc[lead].tz_convert(TH):%Y-%m-%d %H:%M} TH", fontsize=11)
        fig.subplots_adjust(left=0.03, right=0.99, top=0.9, bottom=0.01)
        f = out / f"{n:02d}_{kind}_{L}_{S.S.iloc[e].tz_convert(TH):%Y%m%d_%H%M}.png"
        fig.savefig(f, dpi=62)
        plt.close(fig)
        print(f)


if __name__ == "__main__":
    main()
