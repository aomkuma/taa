"""Each losing walk-forward trade beside the library pattern it was matched with (owner, 2026-10-18: "I still don't
see, for each losing trade, whether it matches a picture in the library"). Per layer - context H4 + H1, setup
M30 + M15, trigger M5 + M1 - the trade's two charts and the pattern's leader (the very moment the trade was compared
with: a pattern is its first moment's fingerprint), with the ZigZag swings the fingerprint counts, the attributes
side by side (a mismatch marked *), the pattern's earlier days and what followed them.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/wf_library_compare.py [trades.parquet]
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
from evidence_journal import SHORT, evidence_patterns  # noqa: E402
from fingerprint import WIN, ZZ_K, raw, zigzag  # noqa: E402
from library import SR_BARS  # noqa: E402
from library_match import LAYERS, attrs, moment_codes  # noqa: E402

TH = "Asia/Bangkok"
RULE = {"H4": "4h", "H1": "1h", "M30": "30min", "M15": "15min", "M5": "5min"}
FUT = {"H4": 0, "H1": 0, "M30": 0, "M15": 2, "M5": 6, "M1": 30}  # bars after the moment, drawn grey
CORE = ["swings", "leg", "peaks", "troughs", "where", "RSI up", "MACD", "EMA"]
WORDS = {
    "swings": ["0-2", "3-5", "6-9", "10+"],
    "leg": ["down", "up", "none"],
    "peaks": ["lower", "equal", "higher", "n/a"],
    "troughs": ["lower", "equal", "higher", "n/a"],
    "where": ["above peak", "below trough", "upper half", "lower third", "n/a"],
    "RSI up": ["no", "yes"],
    "MACD": ["<0 falling", "<0 rising", ">0 falling", ">0 rising"],
    "EMA": ["up", "down", "mixed"],
    "S/R": ["between", "at support", "at resistance", "broke up", "broke down"],
}
UP, DN, FAKE = ("ran_up", "slow_up"), ("ran_dn", "slow_dn"), ("fake_up", "fake_dn")


def names(tfs: tuple[str, ...]) -> list[tuple[str, str]]:
    """(timeframe, attribute) in the order of library_match.attrs."""
    out = []
    for tf in tfs:
        out += [(tf, a) for a in CORE]
        if tf in SR_BARS:
            out.append((tf, "S/R"))
    return out


def word(attr: str, code: int) -> str:
    w = WORDS[attr]
    return w[code] if 0 <= code < len(w) else str(code)


class Charts:
    """Every timeframe's bars over the whole history, their EMAs and the fingerprint's ZigZag swings, once."""

    def __init__(self, m: pd.DataFrame) -> None:
        self.tf = {}
        for tf in ("H4", "H1", "M30", "M15", "M5", "M1"):
            if tf == "M1":
                b = m.reset_index(drop=True).assign(avail=m.index + pd.Timedelta(minutes=1))
            else:
                b = plib.tf_bars(m, RULE[tf])
            R = raw(b)
            piv = zigzag(R["h"], R["lo"], R["atr"], ZZ_K)
            avail = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
            self.tf[tf] = dict(b=b, R=R, piv=piv, avail=avail)

    def panel(self, ax, tf: str, t_dec: pd.Timestamp, label: str) -> None:
        d = self.tf[tf]
        b, R = d["b"], d["R"]
        bi = int(np.searchsorted(d["avail"], pd.Timestamp(t_dec).as_unit("ns").value, side="right")) - 1
        a0 = max(bi - WIN + 1, 0)
        a1 = min(bi + 1 + FUT[tf], len(b))
        x = np.arange(a1 - a0)
        o, h, lo, c = (b[k].to_numpy(float)[a0:a1] for k in ("open", "high", "low", "close"))
        fut = np.arange(a0, a1) > bi
        up = c >= o
        for msk, col in ((up & ~fut, "#1a9b77"), (~up & ~fut, "#d6492f"), (fut, "#bdbdbd")):
            ax.vlines(x[msk], lo[msk], h[msk], color=col, linewidth=0.6)
            ax.vlines(x[msk], np.minimum(o, c)[msk], np.maximum(o, c)[msk], color=col, linewidth=1.8)
        ax.plot(x, R["e20"][a0:a1], color="#3b6fd8", linewidth=0.7)
        ax.plot(x, R["e50"][a0:a1], color="#9a59c9", linewidth=0.7)
        pidx, pval, ptyp, pconf = d["piv"]
        sel = (pconf <= bi) & (pidx >= a0)  # the swings known at the moment, inside the 120 visible bars
        if sel.any():
            px, py = pidx[sel] - a0, pval[sel]
            ax.plot(px, py, color="#333", linewidth=0.8)
            ax.plot([px[-1], bi - a0], [py[-1], R["c"][bi]], color="#333", linewidth=0.8, linestyle=":")
            for xx, yy, tt in zip(px, py, ptyp[sel]):
                ax.plot(xx, yy, "v" if tt > 0 else "^", color="#111", markersize=4)
        ax.axvline(bi - a0 + 0.5, color="k", linestyle="--", linewidth=0.7)
        ax.set_title(f"{label} {tf}", fontsize=8, loc="left")
        ax.tick_params(labelsize=6)
        ax.set_xticks([])


def outcomes(p, day: int) -> dict[str, float]:
    o = np.array([x for d, x in zip(p.occ_days, p.occ_outcomes) if d < day])
    if len(o) == 0:
        return dict(n=0, up=np.nan, dn=np.nan, fake=np.nan, flat=np.nan)
    return dict(n=len(o), up=np.isin(o, UP).mean(), dn=np.isin(o, DN).mean(), fake=np.isin(o, FAKE).mean(),
                flat=(o == "flat").mean())


def main() -> None:
    plib.gold.below_normal_priority()
    f = sys.argv[1] if len(sys.argv) > 1 else "lvl3_wf_trades.parquet"
    T = pd.read_parquet(HERE / f).reset_index(drop=True)
    m = plib.load()
    bars_t = pd.DatetimeIndex(T.t)
    E, libs = evidence_patterns(m, bars_t, T.side.to_numpy())
    for L in SHORT.values():  # the same library record as the walk-forward stored
        for k in ("pid", "count"):
            a, b = E[f"{L}_{k}"].to_numpy(), T[f"ev_{L}_{k}"].to_numpy()
            assert np.array_equal(np.nan_to_num(a, nan=-9), np.nan_to_num(b, nan=-9)), (L, k)
    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    FM, CM = moment_codes(m, bars_t)
    snap_row = {t: i for i, t in enumerate(S.S)}
    trade_row = {t: i for i, t in enumerate(bars_t)}
    day0 = pd.Timestamp("2000-01-01", tz=TH)
    tday = ((bars_t.tz_convert(TH).normalize() - day0).days).to_numpy()
    A_snap = {L: np.column_stack(attrs(FS, S, tfs)).astype(int) for L, tfs in zip(SHORT.values(), LAYERS.values())}
    A_trade = {L: np.column_stack(attrs(FM.reset_index(drop=True), CM.reset_index(drop=True), tfs)).astype(int)
               for L, tfs in zip(SHORT.values(), LAYERS.values())}
    C = Charts(m)
    out = HERE / "png" / "wf_library" / f.replace(".parquet", "")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    losers = np.nonzero(T.pnl.to_numpy() < 0)[0]
    for n, i in enumerate(np.arange(len(T))):
        r = T.iloc[i]
        loser = r.pnl < 0
        if loser:
            fig = plt.figure(figsize=(20, 16))
            gs = fig.add_gridspec(6, 4, height_ratios=[3, 1.0, 3, 1.0, 3, 1.0], hspace=0.32, wspace=0.12)
            axes = np.array([[fig.add_subplot(gs[2 * rr, cc]) for cc in range(4)] for rr in range(3)])
            taxes = [fig.add_subplot(gs[2 * rr + 1, :]) for rr in range(3)]
            for ta in taxes:
                ta.axis("off")
        for row, (layer, tfs) in enumerate(LAYERS.items()):
            L = SHORT[layer]
            pid = int(E[f"{L}_pid"].iloc[i])
            nm = names(tfs)
            mine = A_trade[L][i]
            rec = dict(trade=i, t=r.t, side=int(r.side), exit=r.exit, pnl=r.pnl, R=r.R, loser=bool(loser), layer=L,
                       pid=pid, sim=float(E[f"{L}_sim"].iloc[i]))
            if pid >= 0:
                p = libs[L].patterns[pid]
                kind, ts = p.examples[0][1]
                lead = A_snap[L][snap_row[ts]] if kind == "snap" else A_trade[L][trade_row[ts]]
                eq = mine == lead
                assert abs(eq.mean() - rec["sim"]) < 1e-6, (i, L, eq.mean(), rec["sim"])  # the similarity is the share equal
                lead_out = (S.cls.iloc[snap_row[ts]] if kind == "snap" else E.own_outcome.iloc[trade_row[ts]])
                oc = outcomes(p, int(tday[i]))
                with_, against = (oc["up"], oc["dn"]) if r.side > 0 else (oc["dn"], oc["up"])
                diff = [f"{tf} {a}: {word(a, x)} vs {word(a, y)}" for (tf, a), x, y, e in zip(nm, mine, lead, eq) if not e]
                rec.update(n_attr=len(eq), n_equal=int(eq.sum()), count=oc["n"], with_=with_, against=against,
                           fake=oc["fake"], flat=oc["flat"], leader_kind=kind, leader_t=ts, leader_outcome=lead_out,
                           differs="; ".join(diff))
                t_lead = ts if kind == "snap" else ts + pd.Timedelta(minutes=1)
            else:
                rec.update(n_attr=len(mine), n_equal=np.nan, count=0, with_=np.nan, against=np.nan, fake=np.nan,
                           flat=np.nan, leader_kind="", leader_t=pd.NaT, leader_outcome="", differs="")
            rows.append(rec)
            if not loser:
                continue
            t_dec = r.t + pd.Timedelta(minutes=1)
            for col, tf in enumerate(tfs):
                C.panel(axes[row, col], tf, t_dec, "TRADE")
            if pid >= 0:
                for col, tf in enumerate(tfs):
                    C.panel(axes[row, 2 + col], tf, t_lead, "LIBRARY")
                head = (f"{layer}: pattern #{pid}, {rec['n_equal']} of {rec['n_attr']} attributes equal "
                        f"(similarity {rec['sim']:.2f}); seen on {oc['n']} earlier days - with the trade "
                        f"{with_:.0%}, against {against:.0%}, faked {oc['fake']:.0%}, flat {oc['flat']:.0%}"
                        if oc["n"] else f"{layer}: pattern #{pid} ({rec['n_equal']} of {rec['n_attr']} equal), "
                        "no earlier day yet")
                lead_txt = (f"library picture = the pattern's first moment: {kind} "
                            f"{pd.Timestamp(ts).tz_convert(TH):%Y-%m-%d %H:%M} TH, then: {lead_out}")
                lines = [head, lead_txt]
                for tf in tfs:  # every attribute the bot compared: the trade's value (=/= the library's where it differs)
                    parts = [f"{a} {word(a, x)}" + ("" if e else f" =/= {word(a, y)} *")
                             for (tf_, a), x, y, e in zip(nm, mine, lead, eq) if tf_ == tf]
                    lines.append(f"{tf}: " + " | ".join(parts))
            else:
                for col in (2, 3):
                    axes[row, col].axis("off")
                lines = [f"{layer}: no pattern of earlier days >= 80 % alike (best {rec['sim']:.2f}) - a new pattern; "
                         "the trade starts it"]
                for tf in tfs:
                    lines.append(f"{tf}: " + " | ".join(f"{a} {word(a, x)}" for (tf_, a), x in zip(nm, mine) if tf_ == tf))
            txt = "\n".join("\n".join(textwrap.wrap(ln, 200)) for ln in lines)
            taxes[row].text(0.0, 0.98, txt, transform=taxes[row].transAxes, fontsize=8.5, va="top", ha="left",
                            family="monospace")
        if loser:
            when = r.t.tz_convert(TH)
            fig.suptitle(f"LOSER  {when:%Y-%m-%d %H:%M} TH  {'BUY' if r.side > 0 else 'SELL'}  entry TF {r.etf}  "
                         f"level {r.level:.2f}  exit {r.exit} {r.pnl:+.2f} USD ({r.R:+.2f} R)  |  evidence: "
                         f"{E.evidence.iloc[i]}  |  left: the trade (grey = after), right: the library pattern it matched",
                         fontsize=10)
            fig.subplots_adjust(left=0.03, right=0.99, top=0.95, bottom=0.01)
            fig.savefig(out / f"{int(np.searchsorted(losers, i)):03d}_{when:%Y%m%d_%H%M}.png", dpi=62)
            plt.close(fig)
        if n % 20 == 0:
            print(f"{n} / {len(T)}", flush=True)
    D = pd.DataFrame(rows)
    D.to_csv(out / "compare.csv", index=False)
    pd.set_option("display.width", 220)
    print("\nper layer: losers vs winners - matched a pattern of earlier days, and what that pattern's days did")
    D["matched"] = D.pid >= 0
    D["seen"] = D["count"] >= 1
    D["leans"] = np.where(~D.seen, "no history", np.where(D.with_ > D.against, "with", np.where(D.with_ < D.against,
                                                                                                 "against", "even")))
    g = D.groupby(["layer", "loser"]).agg(trades=("trade", "size"), matched=("matched", "mean"),
                                          seen=("seen", "mean"), days=("count", "mean"), with_=("with_", "mean"),
                                          against=("against", "mean"), fake=("fake", "mean"))
    print(g.round(3).to_string())
    print("\nhow the pattern's earlier days leaned, per layer (count of trades):")
    print(D.pivot_table(index=["layer", "leans"], columns="loser", values="trade", aggfunc="size", fill_value=0)
          .to_string())
    print("pictures:", out)


if __name__ == "__main__":
    main()
