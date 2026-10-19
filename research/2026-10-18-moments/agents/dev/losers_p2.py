"""Task P2: the losers by reason, one drawn for each (the loser nearest its reason's median USD - the tested
precursors/loser_charts.one_per_reason), for the variant with the larger smaller-part R (written before computing).
Each picture: the entry TF from 15 bars before the pattern to 15 after the exit, with the level's zone, the pattern's
points, B's pullback low (a B entry), the entry (the fill), the stop, the target, the exit; beside it the other TF.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/dev/losers_p2.py [VARIANT]
"""

from __future__ import annotations

import base64
import html
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "precursors"))
import charts_p as CP  # noqa: E402
import patterns as P  # noqa: E402

NS_MIN = 60 * 10**9
KEY = ["tf", "t_dec", "family", "side"]


def losers_with_patterns(A: pd.DataFrame, C: pd.DataFrame, variant: str) -> pd.DataFrame:
    """The variant's losers (news cost 0) joined to their catches (the pattern's points, level, zone, the other TF)."""
    L = A[(A.variant == variant) & (A.news_cost == 0.0) & (A.pnl < 0)].copy()
    keep = ["start_t", "pts_t", "pts_p", "pts_lab", "neck_t", "neck_p", "box_t", "box_p", "level", "zone", "trigger",
            "variant", "other_pattern", "other_structure", "part"]
    cat = C[KEY + keep].rename(columns={"variant": "pattern_variant", "part": "catch_part"})
    out = L.merge(cat, on=KEY, how="left", validate="many_to_one")
    if out.level.isna().any():
        raise ValueError("a loser without its catch")
    return out.rename(columns={"level_kind": "level_kind"})


def draw(r: pd.Series, tfs: dict, k: int, title: str, out: Path) -> None:
    tf = tfs[r.tf]
    mn = tf.minutes
    t0 = int(r.start_t) - 15 * mn * NS_MIN
    t1 = max(int(r.exit_t), int(r.t_entry)) + 15 * mn * NS_MIN
    sel = (tf.t_open >= t0) & (tf.t_open < t1)
    b = tf.b[sel]
    x = (tf.t_open[sel] - t0) / NS_MIN + mn / 2
    fig, (ax, a2) = plt.subplots(1, 2, figsize=(14, 5.0), gridspec_kw={"width_ratios": [1.8, 1]})
    fig.patch.set_facecolor("#fcfcfb")
    CP.style(ax)
    CP.candles(ax, b, x, 3.0 if mn == 1 else 4.0)
    X = lambda t: (int(t) - t0) / NS_MIN  # noqa: E731
    xr = X(t1)
    ax.axhspan(r.level - r.zone, r.level + r.zone, color=CP.LEVEL, alpha=0.12, linewidth=0)
    ax.axhline(r.level, color=CP.LEVEL, linewidth=1.1)
    ax.text(xr + 0.5, r.level, f"{r.level_kind} {r.level:.2f}", fontsize=7, color=CP.INK, va="center")
    for t, p, lab in zip(r.pts_t, r.pts_p, r.pts_lab, strict=True) if r.family != "base" else ():
        ax.plot([X(t) + mn / 2], [p], marker="o", markersize=6, color=CP.PAT, markeredgecolor="white", zorder=5)
        ax.annotate(lab, (X(t) + mn / 2, p), xytext=(0, -11 if CP.label_below(lab, int(r.side)) else 6),
                    textcoords="offset points", ha="center", fontsize=7, color=CP.INK)
    if r.box_t is not None:
        (ta, tb), (lo_b, hi_b) = r.box_t, r.box_p
        ax.add_patch(plt.Rectangle((X(ta), lo_b), X(tb) + mn - X(ta), hi_b - lo_b, fill=False, edgecolor=CP.PAT, linewidth=1.1))
    ax.axvline(X(r.t_dec), color=CP.MUTED, linewidth=0.7, linestyle=":")
    ax.text(X(r.t_dec), 1.0, " breakout", transform=ax.get_xaxis_transform(), fontsize=7, color=CP.MUTED, va="top")
    if pd.notna(r.pull):
        ax.plot([X(r.t_entry) - mn], [r.pull], marker="^" if r.side > 0 else "v", markersize=7, color=CP.MUTED, zorder=5)
        ax.text(X(r.t_entry) - mn, r.pull, " pullback", fontsize=7, color=CP.INK, va="top" if r.side > 0 else "bottom")
    ax.plot([X(r.entry_t)], [r.entry], marker=">" if r.side > 0 else "<", markersize=9, color=CP.ENTRY, zorder=6)
    ax.hlines(r.stop, X(r.entry_t), xr, color=CP.STOP, linewidth=1.1, linestyle="--")
    ax.text(xr + 0.5, r.stop, f"stop {r.stop:.2f}", fontsize=7, color=CP.INK, va="center")
    if np.isfinite(r.target):
        ax.hlines(r.target, X(r.entry_t), xr, color=CP.NEXT, linewidth=1.1, linestyle="--")
        ax.text(xr + 0.5, r.target, f"target {r.target:.2f}", fontsize=7, color=CP.INK, va="center")
    ax.plot([X(r.exit_t)], [r.exit_px], marker="X", markersize=9, color=CP.INK, zorder=6)
    ax.text(X(r.exit_t), r.exit_px, f"  out: {r.exit}", fontsize=7, color=CP.INK, va="center")
    ys = [b.low.min(), b.high.max(), r.stop, r.level - r.zone, r.level + r.zone] + ([r.target] if np.isfinite(r.target) else [])
    pad = 0.05 * (max(ys) - min(ys))
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_xlim(-0.5, xr * 1.12)
    CP.xaxis(ax, t0, t1, 10 if mn == 1 else 30)
    ax.set_title(f"{r.tf} - the entry TF; orange = the pattern, blue arrow = the fill, X = the exit; Thai time", fontsize=8,
                 color=CP.INK)
    CP.panel_other(a2, tfs["M5" if r.tf == "M1" else "M1"], r, pd.DataFrame(columns=["tf", "side", "level", "t_dec"]))
    fig.suptitle(title, fontsize=8.5, color=CP.INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out, dpi=90, facecolor=fig.get_facecolor())
    plt.close(fig)


def title_of(k: int, r: pd.Series, n_all: int) -> str:
    side = "BUY" if r.side > 0 else "SELL"
    return (f"#{k} {r.reason} ({r.n_reason} of {n_all} losers) - {CP.thai(r.entry_t, '%Y-%m-%d %H:%M')} Thai - {r.part} - "
            f"{r.tf} {r['name']} at {r.level_kind} {r.level:.2f} - {side} in {r.entry:.2f}, stop {r.stop:.2f}, out "
            f"{r.exit} {r.exit_px:.2f}: {r.pnl:+.2f} USD ({r.R:+.2f} R)")


def main() -> None:
    from loser_charts import one_per_reason  # noqa: PLC0415

    variant = sys.argv[1] if len(sys.argv) > 1 else "B2"
    A = pd.read_parquet(HERE / "p2_trades.parquet")
    C = pd.read_parquet(HERE / "p_catches.parquet")
    L = losers_with_patterns(A, C, variant).sort_values("entry_t").reset_index(drop=True)
    picks = one_per_reason(L)
    m = P.load_m1()
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    outdir = HERE / "charts" / f"p2_losers_{variant}"
    outdir.mkdir(parents=True, exist_ok=True)
    cards = []
    for k, r in picks.iterrows():
        t = title_of(k + 1, r, len(L))
        f = outdir / f"{k + 1:02d}.png"
        draw(r, tfs, k + 1, t, f)
        cards.append((t, base64.b64encode(f.read_bytes()).decode()))
        print(t, flush=True)
    rows = "\n".join(f"<tr><td>{html.escape(r.reason)}</td><td>{r.n_reason}</td></tr>" for r in picks.itertuples())
    body = "\n".join(f'<figure><figcaption>{html.escape(t)}</figcaption><img alt="{html.escape(t)}" '
                     f'src="data:image/png;base64,{b}"></figure>' for t, b in cards)
    (HERE / "charts" / f"p2_losers_{variant}.html").write_text(
        PAGE.format(variant=variant, n=len(L), k=len(cards), rows=rows, body=body), encoding="utf-8")
    print(f"{len(cards)} drawn -> charts/p2_losers_{variant}.html")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pattern Trade Losers</title>
<style>
:root {{ --bg: #f6f5f2; --fg: #1d2127; --muted: #52514e; --card: #ffffff; --line: #dcd9d2; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }} }}
:root[data-theme="dark"] {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }}
body {{ background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; margin: 0; padding: 20px 16px; }}
main {{ max-width: 1240px; margin: 0 auto; display: grid; gap: 18px; }}
h1 {{ font-size: 1.3rem; margin: 0; text-wrap: balance; }}
p {{ color: var(--muted); margin: 0; max-width: 80ch; line-height: 1.5; }}
table {{ border-collapse: collapse; font-size: 0.85rem; font-variant-numeric: tabular-nums; }}
td, th {{ border-bottom: 1px solid var(--line); padding: 4px 8px; text-align: left; }}
figure {{ margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 8px; display: grid; gap: 6px; }}
figcaption {{ font-size: 0.85rem; color: #1d2127; line-height: 1.4; }}
img {{ width: 100%; height: auto; display: block; }}
</style>
</head>
<body>
<main>
<h1>Pattern trades ({variant}) - the losers by reason</h1>
<p>{n} losing trades of variant {variant} in P1 and P2 (2025-10-18 .. 2026-04-17), one drawn for each of their {k}
reasons - the loser nearest its reason's median USD. The reason = what came after the entry within the trade's own time
limit (wrong way: one risk against first; ran later: one risk our way first; no run: neither) x the other TF at the
decision (with / against / mixed or none). Left: the entry TF with the owner's H1 level (purple band), the pattern
(orange), the breakout (dotted), the pullback low of a B entry, the fill (blue arrow), the stop (red), the target
(green), the exit (X). Right: the other TF. Thai time. Research charts only.</p>
<table><tr><th>reason</th><th>losers</th></tr>
{rows}
</table>
{body}
</main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
