"""Every losing trade drawn (owner, 2026-10-19: "from now on capture the price structure with the entry, TP and SL lines
for every losing trade - the entry timeframe; however many dozens, capture them all"). For each loser of a trades file
in a date range: the entry timeframe (M1) from 60 bars before the entry to 15 after the exit, with the entry, the stop,
the target and the exit marked, and the M15 structure of the last 10 hours beside it; then one HTML page with them all.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/loser_charts.py TRADES START END NAME
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

UP, DOWN, ENTRY, STOP, TARGET = "#1a9b77", "#d6492f", "#2f6fd6", "#d6492f", "#1a9b77"


def candles(ax, o, h, lo, c, x0: int = 0) -> None:
    x = np.arange(len(o)) + x0
    up = c >= o
    for mask, col in ((up, UP), (~up, DOWN)):
        ax.vlines(x[mask], lo[mask], h[mask], color=col, linewidth=0.7)
        ax.vlines(x[mask], np.minimum(o, c)[mask], np.maximum(o, c)[mask], color=col, linewidth=2.4)


def levels(side: int, entry: float, r0: float, target_r: float) -> tuple[float, float]:
    """The stop and the target of a trade from its entry, side and risk."""
    return entry - side * r0, entry + side * target_r * r0


def draw(m: pd.DataFrame, sp: np.ndarray, j: int, xj: int, side: int, r0: float, target_r: float, title: str, out: Path) -> None:
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    entry = o[j] + sp[j] + 0.07 if side > 0 else o[j] - 0.07
    stop, target = levels(side, entry, r0, target_r)
    a, b = max(j - 60, 0), min(xj + 15, len(o) - 1)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [2.2, 1]})
    candles(ax1, o[a:b + 1], h[a:b + 1], lo[a:b + 1], c[a:b + 1], a)
    for y, col, lab in ((entry, ENTRY, f"entry {entry:.2f}"), (stop, STOP, f"SL {stop:.2f}"), (target, TARGET, f"TP {target:.2f}")):
        ax1.axhline(y, color=col, linewidth=1.0, linestyle="--")
        ax1.text(b + 0.5, y, lab, color=col, fontsize=7, va="center")
    ax1.axvline(j - 0.5, color=ENTRY, linewidth=0.8, alpha=0.6)
    ax1.axvline(xj + 0.5, color="#555555", linewidth=0.8, alpha=0.6)
    ax1.set_xlim(a - 1, b + 12)
    ticks = list(range(a, b + 1, 15))
    ax1.set_xticks(ticks, [m.index[k].tz_convert("Asia/Bangkok").strftime("%H:%M") for k in ticks], fontsize=7)
    ax1.set_title("M1 (entry timeframe) - Thai time; blue line = entry bar, grey = exit bar", fontsize=8)
    ax1.tick_params(axis="y", labelsize=7)
    # the M15 structure of the last 10 hours up to the entry (closed M15 bars only), the entry price marked
    from indicators import bars  # noqa: PLC0415

    seg = m.iloc[max(j - 600, 0):j]
    b15 = bars(seg, "15min")
    b15 = b15[b15["avail"] <= m.index[j]].tail(40)
    candles(ax2, *(b15[k].to_numpy(float) for k in ("open", "high", "low", "close")))
    ax2.axhline(entry, color=ENTRY, linewidth=0.9, linestyle="--")
    ax2.set_title("M15 before the entry (10 hours)", fontsize=8)
    ax2.set_xticks([])
    ax2.tick_params(axis="y", labelsize=7)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=85)
    plt.close(fig)


def main() -> None:
    import plib  # noqa: PLC0415

    trades, start, end, name = sys.argv[1:5]
    target_r = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
    T = pd.read_parquet(HERE / trades)
    m = plib.load()
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    L = T[(T.pnl < 0) & (T.t >= pd.Timestamp(start, tz="UTC")) & (T.t < pd.Timestamp(end, tz="UTC"))].sort_values("t").reset_index(drop=True)
    outdir = HERE / "charts" / name
    outdir.mkdir(parents=True, exist_ok=True)
    cards = []
    for k, r in L.iterrows():
        j = int(np.searchsorted(m.index, r.t))
        th = pd.Timestamp(r.t).tz_convert("Asia/Bangkok")
        title = (f"#{k + 1}  {th:%Y-%m-%d %H:%M} Thai  {'BUY' if r.side > 0 else 'SELL'}  exit: {r.exit}  "
                 f"{r.pnl:+.2f} USD ({r.R:+.2f} R)  risk {r.r0:.2f} USD")
        f = outdir / f"{k + 1:03d}.png"
        draw(m, sp, j, int(r.xj), int(r.side), float(r.r0), target_r, title, f)
        cards.append((title, base64.b64encode(f.read_bytes()).decode()))
    html = HERE / "charts" / f"{name}.html"
    body = "\n".join(f'<figure><figcaption>{t}</figcaption><img alt="{t}" src="data:image/png;base64,{b64}"></figure>' for t, b64 in cards)
    html.write_text(PAGE.format(name=name, n=len(cards), start=start, end=end, body=body), encoding="utf-8")
    print(f"{len(cards)} losing trades drawn -> {outdir}, page {html}")


PAGE = """<title>Losing Trades Gallery</title>
<style>
:root {{ --bg: #f6f5f2; --fg: #1d2127; --muted: #5b6270; --card: #ffffff; --line: #dcd9d2; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #15171b; --fg: #e8e6e1; --muted: #a2a8b3; --card: #f4f2ee; --line: #30343b; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg: #15171b; --fg: #e8e6e1; --muted: #a2a8b3; --card: #f4f2ee; --line: #30343b; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; margin: 0; padding-inline: 16px; padding-block: 20px; }}
main {{ max-width: 1100px; margin: 0 auto; display: grid; gap: 18px; }}
h1 {{ font-size: 1.3rem; margin: 0; text-wrap: balance; }}
p {{ color: var(--muted); margin: 0; max-width: 65ch; line-height: 1.5; }}
figure {{ margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 8px; display: grid; gap: 6px; }}
figcaption {{ font-size: 0.85rem; color: #1d2127; font-variant-numeric: tabular-nums; }}
img {{ width: 100%; height: auto; display: block; }}
</style>
<main>
<h1>Losing trades - {name}</h1>
<p>{n} losing trades, {start} to {end} (UTC dates). Each: M1, the entry timeframe, with the entry (blue dashed), the stop
(red dashed), the target (green dashed), the entry bar (blue line) and the exit bar (grey line); beside it the M15 bars of
the ten hours before the entry. Times are Thai time. Research charts only.</p>
{body}
</main>
"""


if __name__ == "__main__":
    main()
