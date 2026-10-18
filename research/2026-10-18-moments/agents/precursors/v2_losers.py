"""Every V2 window trade (B3, the one window run) traced to the moment: what the bot measured, where it entered in
the move, how it lost, and what came after; losers against winners, and annotated pictures of losers.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/v2_losers.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import plib  # noqa: E402
import v2  # noqa: E402  (puts the journal folder on sys.path)
from v2 import jlib  # noqa: E402
from plib import HERE  # noqa: E402

pd.set_option("display.width", 250)
OUT = HERE / "png" / "v2_losers"


def main() -> None:
    plib.gold.below_normal_priority()
    S = pd.read_parquet(HERE / "snaps.parquet")
    F = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    m = plib.load()
    W = v2.weights(S, F)
    E = v2.entry_tf(m, S)
    P = jlib.Instr("XAUUSD")
    Tg = v2.triggers(P, S)
    T = pd.read_parquet(HERE / "v2_window_B3.parquet")
    k_of = {t: k for k, t in enumerate(S.S)}
    rows = []
    for tr in T.itertuples():
        k = k_of[tr.S]
        j0, side = int(Tg.tj.iloc[k]), int(Tg.tside.iloc[k])
        entry, ref, u = float(Tg.tentry.iloc[k]), float(S.ref.iloc[k]), float(S.u.iloc[k])
        atr = float(E.atr_e.iloc[k])
        xj = int(tr.xj)
        # what happened inside the trade and after it (120 minutes from the entry)
        path = range(j0, min(j0 + 120, len(P.o)))
        fav = np.array([((P.h[q] if side > 0 else P.lo[q] + P.sp[q]) - entry) * side for q in path])
        adv = np.array([(entry - (P.lo[q] if side > 0 else P.h[q] + P.sp[q])) * side for q in path])
        upto = xj - j0 + 1
        other = ref - side * 3 * u  # the straddle's other side
        reached_other = any(((P.lo[q] if side > 0 else P.h[q]) - other) * side <= 0 for q in path)
        pre = (S.ref.iloc[k] - P.c[max(j0 - (j0 - P.ot.searchsorted(S.S.iloc[k])) - 30, 0)]) * side / atr
        rows.append(dict(
            S=tr.S, name=tr.name, side=side, exit=tr.exit, pnl=tr.pnl, kind=tr.kind, etf=tr.etf,
            w_form=float(W.w_form.iloc[k]), base=float(W.base.iloc[k]), n_trig=float(W.n_trigger.iloc[k]),
            ev_side=float((W.cup_trigger.iloc[k] - W.cdn_trigger.iloc[k]) * side),
            lead_min=(P.ot[j0] - S.S.iloc[k]).total_seconds() / 60,
            trig_bar_atr=(P.h[j0] - P.lo[j0]) / atr, gap=(entry - (ref + side * 3 * u)) * side,
            sl=float(tr.sl), tp=float(tr.tp), sl_vs_start=float(tr.sl) / max((entry - ref) * side, 1e-9),
            spread=float(P.sp[j0]), mins_held=(P.ot[xj] - P.ot[j0]).total_seconds() / 60,
            mfe_before=float(fav[:upto].max()) / float(tr.tp), mfe120=float(fav.max()) / float(tr.tp),
            mae120=float(adv.max()) / float(tr.sl), reached_other=reached_other, pre30_with=float(pre),
            stop_in_entry_bar=(tr.exit == "stop") and xj == j0, j0=j0, xj=xj, entry=entry, ref=ref, k=k))
    D = pd.DataFrame(rows)
    D.to_parquet(HERE / "v2_trades_traced.parquet")
    L = D[D.exit == "stop"]
    Wn = D[D.exit == "win"]
    print(f"window B3 trades {len(D)}: wins {len(Wn)}, stops {len(L)}, break-even {(D.exit == 'be').sum()}, "
          f"time {(D.exit == 'time').sum()}")
    cols = ["w_form", "base", "n_trig", "ev_side", "lead_min", "trig_bar_atr", "gap", "sl", "tp", "sl_vs_start",
            "spread", "mins_held", "mfe_before", "mfe120", "mae120", "pre30_with"]
    cmp_ = pd.DataFrame({"stopped (median)": L[cols].median(), "won (median)": Wn[cols].median()})
    print("\n-- what the bot measured / where it entered: stopped vs won --")
    print(cmp_.round(3).to_string())
    print("\n-- traits: share among stopped vs won --")
    traits = {
        "stopped within the entry bar": D.stop_in_entry_bar,
        "stopped within 5 minutes": (D.mins_held <= 5),
        "the stop nearer than the snap price (SL < entry - start)": D.sl_vs_start < 1,
        "the trigger bar >= 1 entry-TF ATR (a spike entry)": D.trig_bar_atr >= 1,
        "entered >= 15 min after the snap": D.lead_min >= 15,
        "the evidence's side against the trade": D.ev_side < 0,
        "few matches (< 30) in the trigger layer": D.n_trig < 30,
        "price then reached the straddle's other side": D.reached_other,
        "the target came within 120 min of the entry": D.mfe120 >= 1,
        "moved against 30 min before the snap": D.pre30_with < -0.5,
        "entry TF M1/M5": D.etf.isin(["M1", "M5"]),
        "a release snap (NY 08:30)": D.name.str.contains("NY0830"),
    }
    t = pd.DataFrame({k: [v[D.exit == "stop"].mean(), v[D.exit == "win"].mean(), int(v[D.exit == "stop"].sum())]
                      for k, v in traits.items()}, index=["stopped", "won", "n stopped"]).T
    t["lift"] = t.stopped / t.won
    print(t.round(3).to_string())
    print("\n-- stopped trades by entry TF and snap time --")
    print(D.groupby("etf").apply(lambda x: pd.Series({"n": len(x), "stop %": (x.exit == "stop").mean(),
                                                      "R": (x.pnl / (x.sl + 0.15)).mean()}), include_groups=False).round(3))
    print(D.groupby("name").apply(lambda x: pd.Series({"n": len(x), "stop %": (x.exit == "stop").mean(),
                                                       "usd": x.pnl.sum()}), include_groups=False).round(2).to_string())
    # pictures of 12 stopped trades: M1 around the trade with the snap, the levels, entry, stop, target, exit
    OUT.mkdir(parents=True, exist_ok=True)
    pick = L.sample(min(12, len(L)), random_state=7).sort_values("S")
    for n, r in enumerate(pick.itertuples()):
        a, b = max(r.j0 - 60, 0), min(r.j0 + 90, len(P.o) - 1)
        x = np.arange(a, b)
        fig, ax = plt.subplots(figsize=(11, 4.2))
        up = P.c[x] >= P.o[x]
        ax.vlines(x[up], P.lo[x][up], P.h[x][up], color="#1a9b77", lw=0.8)
        ax.vlines(x[~up], P.lo[x][~up], P.h[x][~up], color="#d6492f", lw=0.8)
        ax.vlines(x, np.minimum(P.o[x], P.c[x]), np.maximum(P.o[x], P.c[x]), color="#555", lw=2.2, alpha=0.5)
        snap_j = P.ot.searchsorted(r.S)
        ax.axvline(snap_j, color="k", ls="--", lw=0.8)
        ax.axvline(r.j0, color="#3b6fd8", lw=0.8)
        ax.axvline(r.xj, color="#d6492f", lw=0.8)
        ax.axhline(r.ref, color="k", lw=0.6, alpha=0.5)
        ax.axhline(r.entry, color="#3b6fd8", lw=0.8)
        ax.axhline(r.entry - r.side * r.sl, color="#d6492f", lw=0.8)
        ax.axhline(r.entry + r.side * r.tp, color="#1a9b77", lw=0.8)
        th = r.S.tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M")
        ax.set_title(f"{th} TH {r.name}: {'BUY' if r.side > 0 else 'SELL'} on {r.etf}, stop {r.sl:.1f} / target {r.tp:.1f} "
                     f"USD, held {r.mins_held:.0f} min, best {r.mfe_before:.0%} of target, kind {r.kind}; "
                     f"evidence side {r.ev_side:+.2f}, run weight {r.w_form:.2f}", fontsize=8)
        ax.set_xticks([])
        fig.tight_layout()
        fig.savefig(OUT / f"loser_{n:02d}.png", dpi=72)
        plt.close(fig)


if __name__ == "__main__":
    main()
