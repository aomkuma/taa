"""Every losing LV trade traced to what the bot saw (owner: "analyse every losing trade down to the picture the bot
really saw"): for each loser, the six-timeframe picture at the decision (closed bars only), a trade picture (H1 trend;
M5 swings, the start T, the level L and the stall bar; M1 entry / stop / target / exit and the two hours after), and a
journal row - what the bot measured, how the trade lost, what price did after - with the losers set against the winners.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/lvl_losers.py \
        lvl_window_stall_0.25_T2.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import jlib  # noqa: E402
import plib  # noqa: E402

TH = "Asia/Bangkok"
pd.set_option("display.width", 250)


def journal(T: pd.DataFrame, m: pd.DataFrame, sp: np.ndarray) -> pd.DataFrame:
    """One row per trade: what the bot measured and what happened (all prices from the same M1 frame)."""
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    T = T.copy()
    if "lkind" not in T:  # LV2: the zone's swings and whether H1 is in it
        T["lkind"] = [f"{int(a)}sw{'+H1' if b else ''}" for a, b in zip(T.swings, T.has_h1)]
    if "kind" not in T:  # the owner's three kinds for stopped trades
        kinds = []
        for r in T.itertuples():
            if r.exit not in ("stop", "close"):
                kinds.append("")
                continue
            s_ = int(r.side)
            later = range(int(r.xj) + 1, min(int(r.j0) + 120, len(o)))
            hit = any(((h[q] if s_ > 0 else lo[q] + sp[q]) - r.entry) * s_ >= r.tp for q in later)
            kinds.append("3" if hit else ("2" if r.mfe >= 0.5 * r.tp else "1"))
        T["kind"] = kinds
    b5 = plib.tf_bars(m, "5min")
    av5 = pd.DatetimeIndex(b5["avail"])
    rows = []
    for r in T.itertuples():
        s, a, j0, xj = int(r.side), float(r.atr), int(r.j0), int(r.xj)
        t_dec = r.t + pd.Timedelta(minutes=1)
        i5 = int(av5.searchsorted(t_dec, side="right")) - 1
        bar = b5.iloc[i5]
        reach = (r.level - bar.high) / a if s < 0 else (bar.low - r.level) / a  # how near the stall bar came (ATR)
        after = range(j0, min(j0 + 120, len(o)))
        fav = np.array([((h[q] if s > 0 else lo[q] + sp[q]) - r.entry) * s for q in after])
        adv = np.array([(r.entry - (lo[q] if s > 0 else h[q] + sp[q])) * s for q in after])
        cl = c[j0:min(j0 + 120, len(o))]
        broke = np.nonzero((cl - r.level) * -s > 0.25 * a)[0]  # a close beyond the level after the entry
        back_to_start = np.nonzero([((lo[q] if s < 0 else h[q]) - r.start) * s <= 0 for q in after])[0]
        held = xj - j0 + 1
        rows.append(dict(
            t=r.t, j0=j0, xj=xj, when_th=r.t.tz_convert(TH).strftime("%Y-%m-%d %H:%M"), side=s, etf=r.etf, A=a,
            lkind=r.lkind,
            level=r.level, start=r.start, entry=r.entry, sl=r.sl, tp=r.tp, exit=r.exit, pnl=r.pnl, kind=r.kind,
            bounce_A=(r.entry - r.start) * -s / a, level_from_start_A=(r.level - r.start) * -s / a,
            entry_to_level_A=(r.level - r.entry) * -s / a, stall_reach_A=reach, held_min=held,
            best_before_exit=fav[:held].max() / r.tp if held else np.nan, worst_120=adv.max() / r.sl,
            best_120=fav.max() / r.tp, level_broke_min=int(broke[0]) if len(broke) else -1,
            start_reached_min=int(back_to_start[0]) if len(back_to_start) else -1))
    J = pd.DataFrame(rows)
    J["cause"] = np.select(
        [J.exit.eq("close") & (J.kind == "3"), J.exit.eq("close"),
         J.exit.eq("stop") & (J.level_broke_min >= 0) & (J.level_broke_min <= J.held_min) & (J.kind == "1"),
         J.exit.eq("stop") & (J.kind == "3"),
         J.exit.eq("stop") & (J.kind == "2"),
         J.exit.eq("stop") & (J.kind == "1"),
         J.exit.eq("time") & (J.pnl < 0),
         J.exit.eq("be")],
        ["closed through the level, then the target came anyway", "closed through the level (out at the next open)",
         "the level broke (price closed through it, the stop followed)", "shaken out (stopped, then the target came)",
         "fell short (half way or more, then back to the stop)", "wrong way without a close through the level",
         "time exit at a loss", "break-even (0.6 of the target, then back)"], "won / other")
    return J


def picture_bars(sl_: pd.DataFrame, t_dec: pd.Timestamp, rule: str | None, back: pd.Timedelta | None,
                 fwd: pd.Timedelta) -> tuple[pd.DataFrame, pd.Series, pd.DatetimeIndex, np.ndarray]:
    """The bars one panel draws: H1 (back None) the last 120 bars closed by the decision, as the bot had them; else the
    bars from `back` before to `fwd` after it. Returns the bars, their open times (Thai), when each was complete, and
    which are the future (complete after the decision: drawn grey)."""
    if rule:
        b = plib.tf_bars(sl_, rule)
        if back is None:  # H1: the last 120 closed bars, one screen
            b = b[b["avail"] <= t_dec].tail(120).reset_index(drop=True)
        else:
            b = b[(b["last"] >= t_dec - back) & (b["last"] < t_dec + fwd)].reset_index(drop=True)
        start_t = (b["last"].dt.floor(rule)).dt.tz_convert(TH)
        done = pd.DatetimeIndex(b["avail"])
    else:
        b = sl_[(sl_.index >= t_dec - back) & (sl_.index < t_dec + fwd)]
        start_t = pd.Series(b.index.tz_convert(TH))
        done = b.index + pd.Timedelta(minutes=1)
        b = b.reset_index(drop=True)
    return b, start_t, done, np.asarray(done > t_dec)


def trade_picture(m: pd.DataFrame, r: pd.Series, path: Path) -> None:
    import matplotlib  # noqa: PLC0415  (drawing only; the bar selection is tested without it)

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    t_dec = r.t + pd.Timedelta(minutes=1)
    sl_ = m[(m.index >= t_dec - pd.Timedelta(days=14)) & (m.index <= t_dec + pd.Timedelta(hours=3))]
    fig, axes = plt.subplots(1, 3, figsize=(20, 5.5), gridspec_kw={"width_ratios": [1.5, 1.3, 1.4]})
    for ax, rule, back, fwd, w in ((axes[0], "1h", None, pd.Timedelta(0), 1.6),
                                   (axes[1], "5min", pd.Timedelta(hours=9), pd.Timedelta(hours=2), 1.6),
                                   (axes[2], None, pd.Timedelta(hours=1.5), pd.Timedelta(hours=2), 1.1)):
        b, start_t, done, future = picture_bars(sl_, t_dec, rule, back, fwd)
        x = np.arange(len(b))
        o, h, lo, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        up = c >= o
        for msk, col in ((up & ~future, "#1a9b77"), (~up & ~future, "#d6492f"), (future, "#b9b9b9")):
            ax.vlines(x[msk], lo[msk], h[msk], color=col, lw=0.7)
            ax.vlines(x[msk], np.minimum(o, c)[msk], np.maximum(o, c)[msk], color=col, lw=w)
        cut = int(np.sum(~future))
        ax.axvline(cut - 0.5, color="k", ls="--", lw=0.8)
        ax.axhline(r.level, color="#d6492f", lw=1.0)
        ax.axhline(r.start, color="#3b6fd8", lw=0.9, ls=":")
        if rule == "5min":
            ax.axvspan(cut - 1.5, cut - 0.5, color="#f2c14e", alpha=0.35)  # the last closed M5 bar (the stall bar on M5)
        if rule is None:
            ax.axhline(r.entry, color="#444", lw=0.8)
            ax.axhline(r.entry - r.side * r.sl, color="#d6492f", lw=0.8, ls="--")
            ax.axhline(r.entry + r.side * r.tp, color="#1a9b77", lw=0.8, ls="--")
            ent = int(np.searchsorted(done, m.index[int(r.j0)] + pd.Timedelta(minutes=1)))
            ext = int(np.searchsorted(done, m.index[int(r.xj)] + pd.Timedelta(minutes=1)))
            ax.axvline(ent, color="#444", lw=0.7)
            ax.axvline(ext, color="#9a59c9", lw=0.9)
        ticks = np.linspace(0, len(b) - 1, 7).astype(int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([start_t.iloc[k].strftime("%d %H:%M") for k in ticks], fontsize=6)
        ax.tick_params(labelsize=6)
        ax.set_title({"1h": "H1 - the trend (the last 120 bars)", "5min": "M5 - start T (blue dotted), level L (red), the stall bar (yellow)",
                      None: "M1 - entry (grey), stop (red dashed), target (green dashed), exit (purple); grey = after"}[rule],
                     fontsize=8, loc="left")
    fig.suptitle(f"{r.when_th} TH  {'SELL' if r.side < 0 else 'BUY'}  level {r.lkind} {r.level:.2f} (start {r.start:.2f}); "
                 f"entry TF {r.etf}, ATR {r.A:.1f}; stop {r.sl:.1f} / target {r.tp:.1f} USD -> {r.exit} {r.pnl:+.2f}  |  "
                 f"{r.cause}", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)


def main() -> None:
    import render  # noqa: PLC0415

    f = sys.argv[1]
    T = pd.read_parquet(HERE / f)
    m = jlib.m1_frame("XAUUSD")
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    J = journal(T, m, sp)
    # R13 and the walk-forward: each trade's library evidence at entry and the settings that traded it
    extra = [c for c in T.columns if c.startswith("ev_") or c in ("cell", "legs")]
    if extra:
        J = J.merge(T[["j0", *extra]], on="j0", how="left")
    out = HERE / "png" / "lvl_losers" / f.replace(".parquet", "")
    out.mkdir(parents=True, exist_ok=True)
    J.to_csv(out / "journal.csv", index=False)
    L = J[J.pnl < 0]
    Wn = J[J.exit == "win"]
    print(f"{f}: {len(J)} trades, {len(Wn)} wins, {len(L)} losing (stop {int((L.exit == 'stop').sum())}, "
          f"break-even {int((L.exit == 'be').sum())}, time {int((L.exit == 'time').sum())})")
    print("\n-- the losers' causes --")
    print(L.cause.value_counts().to_string())
    cols = ["bounce_A", "level_from_start_A", "entry_to_level_A", "stall_reach_A", "A", "sl", "tp", "best_before_exit",
            "best_120", "worst_120"]
    print("\n-- what the bot measured / what followed: losers vs winners (medians) --")
    print(pd.DataFrame({"losers": L[cols].median(), "winners": Wn[cols].median()}).round(3).to_string())
    print("\n-- by level kind, side, entry TF, snap time --")
    for g in [x for x in ("lkind", "side", "etf", "cell", "ev_evidence") if x in J]:
        print(J.groupby(g).apply(lambda x: pd.Series({"n": len(x), "win": (x.exit == "win").mean(), "usd": x.pnl.sum()}),
                                 include_groups=False).round(2).to_string())
    print("\n-- the journal of every losing trade --")
    show = ["when_th", "side", "lkind", "etf", "A", "bounce_A", "stall_reach_A", "sl", "tp", "exit", "pnl",
            "best_before_exit", "level_broke_min", "best_120", "cause"]
    show += [c for c in ("ev_evidence", "ev_ctx_count", "ev_set_count", "ev_trg_count", "ev_trg_with", "ev_trg_against")
             if c in J]
    print(L[show].round(2).to_string(index=False))
    if len(sys.argv) > 2 and sys.argv[2] == "nopics":
        return
    mf = plib.load()
    for i, r in enumerate(L.itertuples()):
        render.draw(mf, r.t, out / f"{i:02d}_bot_view.png",
                    f"WHAT THE BOT SAW at {r.when_th} TH (decision at this M1 close; grey = after)")
        trade_picture(m, pd.Series(r._asdict()), out / f"{i:02d}_trade.png")
    print("pictures:", out)


if __name__ == "__main__":
    main()
