"""Pictures of Setup OWN V2's decisions (owner, 2026-10-19: "show me 6-8 pictures of the price structure the bot saw
and traded on"): for chosen walk-forward trades, each layer the decision used - the chart the bot saw at the snap
(left) and the first moment of the library pattern it matched (right), with the ZigZag swings the fingerprint counts,
the codes compared (the trade's value, =/= the library's where they differ), the outline correlation per timeframe,
the pattern's earlier days and the lean that decided the side; grey bars = after the decision.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/v2b_pictures.py
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
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import jlib  # noqa: E402
import plib  # noqa: E402
from cluster_fp import onehot  # noqa: E402
from library_match import LAYERS, attrs  # noqa: E402
from v2b import LAYER_TFS, NPTS, TFS, UP, DN, OutlineLibrary  # noqa: E402
from wf_library_compare import Charts, names, word  # noqa: E402

TH = "Asia/Bangkok"
SHORT = {"context (H4+H1)": "ctx", "setup (M30+M15)": "set", "trigger (M5+M1)": "trg"}
LONG = {v: k for k, v in SHORT.items()}


def pick(T: pd.DataFrame) -> pd.DataFrame:
    """Two of the biggest winners and two of the biggest losers in each half."""
    out = []
    for half in (T.t < plib.EXAM_START, T.t >= plib.EXAM_START):
        x = T[half]
        out += [x.nlargest(2, "pnl"), x.nsmallest(2, "pnl")]
    return pd.concat(out).sort_values("t")


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    SH = np.load(HERE / "snap_shapes.npy").reshape(len(S), len(TFS), NPTS)
    day0 = pd.Timestamp("2000-01-01", tz=TH)
    day = ((S.S.dt.tz_convert(TH).dt.normalize() - day0).dt.days).to_numpy()
    order = np.argsort(S.S.to_numpy(), kind="stable")
    cls = S.cls.to_numpy()
    T = pd.read_parquet(HERE / "v2b_wf_trades.parquet").reset_index(drop=True)
    P = pick(T)
    m1 = jlib.m1_frame("XAUUSD")
    snap_ns = pd.DatetimeIndex(S.S).as_unit("ns").asi8
    P["e"] = [int(np.searchsorted(snap_ns, m1.index[j].as_unit("ns").value, side="right")) - 1 for j in P.j0]
    want = {e: r for e, r in zip(P.e, P.itertuples())}
    # rebuild each needed (layer, gate) library in time order; record each pattern's first moment and the match
    match = {}
    for L, gate in {(lay, r.cell.split("_")[1]) for r in P.itertuples() for lay in r.cell.split("_")[0].split("+")}:
        rho = None if gate == "codes" else float(gate.replace("shape", ""))
        tfs = LAYER_TFS[L]
        Vc = np.column_stack(attrs(FS, S, LAYERS[LONG[L]])).astype(int)
        V = onehot(list(Vc.T))
        idx = [TFS.index(tf) for tf in tfs]
        lib = OutlineLibrary(V.shape[1], len(idx), rho=rho)
        first = {}
        for e in order:
            shp = SH[e][idx]
            if e in want:
                k, sim = lib.most_similar(V[e], shp, before_day=int(day[e]))
                if k >= 0 and sim >= 0.8 - 1e-6:
                    p = lib.patterns[k]
                    o = np.array([x for d, x in zip(p.occ_days, p.occ_outcomes) if d < day[e]])
                    lead = first[k]
                    corr = [float(np.dot(SH[e][i], SH[lead][i])) for i in idx]
                    match[(L, gate, e)] = dict(k=k, lead=lead, n=len(o), up=np.isin(o, UP).mean(), dn=np.isin(o, DN).mean(),
                                               eq=Vc[e] == Vc[lead], mine=Vc[e], theirs=Vc[lead], corr=corr)
            pid, new = lib.add(V[e], shp, int(day[e]), str(cls[e]))
            if new:
                first[pid] = e
    C = Charts(plib.load())
    o1 = m1.open.to_numpy(float)
    sp1 = m1.spread.to_numpy(float) * 0.01 + 0.08
    out = HERE / "png" / "v2b_decisions"
    out.mkdir(parents=True, exist_ok=True)
    for n, (e, r) in enumerate(sorted(want.items(), key=lambda x: x[1].t)):
        layers, gate = r.cell.split("_")[0].split("+"), r.cell.split("_")[1]
        fig = plt.figure(figsize=(20, 5.6 * len(layers) + 1))
        gs = fig.add_gridspec(2 * len(layers), 4, height_ratios=[3, 1.1] * len(layers), hspace=0.3, wspace=0.12)
        t_snap = S.S.iloc[e]
        total = 0.0
        for row, L in enumerate(layers):
            tfs = LAYER_TFS[L]
            ax = [fig.add_subplot(gs[2 * row, c]) for c in range(4)]
            ta = fig.add_subplot(gs[2 * row + 1, :])
            ta.axis("off")
            # the trade as placed (the same prices as v2b: the next M1 open, the spread and slippage on the entry)
            j0 = int(r.j0)
            entry = o1[j0] + sp1[j0] + 0.07 if r.side > 0 else o1[j0] - 0.07
            for c, tf in enumerate(tfs):
                C.panel(ax[c], tf, t_snap, "BOT SAW")
                ax[c].axhline(entry, color="#333", linewidth=0.9)
                ax[c].axhline(entry + r.side * r.tp, color="#1a9b77", linewidth=1.1, linestyle="--")
                ax[c].axhline(entry - r.side * r.sl, color="#d6492f", linewidth=1.1, linestyle="--")
                ax[c].set_title(f"BOT SAW {tf}  (entry {entry:.2f} black, TP {entry + r.side * r.tp:.2f} green, "
                                f"SL {entry - r.side * r.sl:.2f} red)", fontsize=8, loc="left")
            mt = match.get((L, gate, e))
            nm = names(tfs)
            if mt is None:
                for c in (2, 3):
                    ax[c].axis("off")
                lines = [f"{LONG[L]}: no pattern of earlier days alike (codes >= 80 %"
                         f"{'' if gate == 'codes' else ', outline >= ' + gate.replace('shape', '')})"]
            else:
                for c, tf in enumerate(tfs):
                    C.panel(ax[2 + c], tf, S.S.iloc[mt["lead"]], "LIBRARY")
                lean = mt["up"] - mt["dn"]
                total += lean
                lines = [f"{LONG[L]}: pattern #{mt['k']} - codes {int(mt['eq'].sum())} of {len(mt['eq'])} equal; outline "
                         f"correlation {' / '.join(f'{tf} {x:.2f}' for tf, x in zip(tfs, mt['corr']))}"
                         f"{'' if gate == 'codes' else ' (gate ' + gate.replace('shape', '') + ')'}; seen on {mt['n']} "
                         f"earlier days: up {mt['up']:.0%}, down {mt['dn']:.0%} -> lean {lean:+.2f}",
                         f"library picture = the pattern's first moment: snap {S.S.iloc[mt['lead']].tz_convert(TH):%Y-%m-%d %H:%M} "
                         f"TH ({S.name.iloc[mt['lead']]}), then: {cls[mt['lead']]}"]
                for tf in tfs:
                    parts = [f"{a} {word(a, x)}" + ("" if q else f" =/= {word(a, y)} *")
                             for (tf_, a), x, y, q in zip(nm, mt["mine"], mt["theirs"], mt["eq"]) if tf_ == tf]
                    lines.append(f"{tf}: " + " | ".join(parts))
            ta.text(0, 0.98, "\n".join("\n".join(textwrap.wrap(x, 210)) for x in lines), transform=ta.transAxes,
                    fontsize=8.5, va="top", ha="left", family="monospace")
        when = t_snap.tz_convert(TH)
        fig.suptitle(f"V2 {'BUY' if r.side > 0 else 'SELL'} at the snap {when:%Y-%m-%d %H:%M} TH ({S.name.iloc[e]})  cell "
                     f"{r.cell}: lean {total:+.2f}  |  entry TF {r.etf}, stop {r.sl:.2f}, target {r.tp:.2f} USD -> "
                     f"{r.exit} {r.pnl:+.2f} USD ({r.R:+.2f} R)  |  left: what the bot saw (grey = after), right: the "
                     f"library pattern it matched", fontsize=10)
        fig.subplots_adjust(left=0.03, right=0.99, top=0.93, bottom=0.01)
        f = out / f"{n:02d}_{when:%Y%m%d_%H%M}_{'win' if r.pnl > 0 else 'loss'}.png"
        fig.savefig(f, dpi=62)
        plt.close(fig)
        print(f)


if __name__ == "__main__":
    main()
