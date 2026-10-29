"""Draw each bot decision of a ledger on its M5 chart, for the owner to judge by eye.

For a row: the M5 bars from a few hours before the Fibo leg to a few hours after the decision; MT5's
ZigZag computed on the bars closed at the decision (what the bot saw); the leg's 0 % / 23.6 / 38.2 / 61.8 /
100 / 161.8 % lines; the order (entry, stop, target); a vertical line at the decision, the bars after it
shaded - what happened next, shown so the reading can be judged against it. Nothing is run or scored: the
ledger is read as written.

    .venv\\Scripts\\python eye/draw_trades.py eye/research/h1L_618_m5/ledger.csv
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from walk import TH, candles, frame, zigzag  # noqa: E402

LEG = re.compile(
    r"Leg low ([\d.]+)@(\d\d/\d\d \d\d:\d\d) \(0 %\), high ([\d.]+)@(\d\d/\d\d \d\d:\d\d) \(100 %\)"
)
# BOT_RULES rule 14's leg (both sides: L0 is the 0 %, H100 the 100 %) and rule 11's range (0 % at the low)
LEG_FIB = re.compile(
    r"Leg: L0 ([\d.]+)@(\d\d/\d\d \d\d:\d\d) \(0 %\), H100 ([\d.]+)@(\d\d/\d\d \d\d:\d\d) \(100 %\)"
)
RANGE = re.compile(r"Range pivots: low ([\d.]+)@(\d\d/\d\d \d\d:\d\d), high ([\d.]+)@(\d\d/\d\d \d\d:\d\d)")
# BOT_RULES rule 11's H1 range, written in the structure while H1 is sideways
H1_RANGE = re.compile(
    r"H1 range LOW ([\d.]+)@\S+ \S+ - HIGH ([\d.]+)@\S+ \S+, (\d+) pivots, legs so far \d+, leg (\d+)"
)
LEVELS = (0.0, 0.236, 0.382, 0.618, 1.0, 1.618)
RANGE_LEVELS = (-0.27, 0.0, 0.12, 0.88, 1.0, 1.27)


def when(year: str, ddmm_hhmm: str) -> pd.Timestamp:
    d, t = ddmm_hhmm.split(" ")
    day, month = d.split("/")
    return pd.Timestamp(f"{year}-{month}-{day} {t}", tz=TH)


def draw(row: dict[str, str], m5: pd.DataFrame, out: Path) -> Path:
    year = row["cutoff_thai"][:4]
    m = LEG.search(row["structure"]) or LEG_FIB.search(row["structure"]) or RANGE.search(row["structure"])
    if not m:
        raise ValueError(f"{row['id']}: no leg in the structure text")
    levels = RANGE_LEVELS if m.re is RANGE else LEVELS
    p0, t0, p100, t100 = float(m[1]), when(year, m[2]), float(m[3]), when(year, m[4])
    decided = pd.Timestamp(f"{row['cutoff_thai'][:10]} {row['decided_at'][-5:]}", tz=TH)
    now = decided + pd.Timedelta(minutes=5)  # the bar labelled decided_at closes here
    first = min(t0, t100) - pd.Timedelta(hours=3)
    last = now + pd.Timedelta(hours=8)
    bars = m5[(m5.index >= first.tz_convert("UTC")) & (m5.index < last.tz_convert("UTC"))]
    seen = m5[m5.index + pd.Timedelta(minutes=5) <= now.tz_convert("UTC")]
    calc = seen.iloc[-1500:]  # the bars the bot saw, with warm-up for the ZigZag
    offset = int(calc.index.get_indexer([bars.index[0]])[0]) if bars.index[0] in calc.index else 0

    fig, ax = plt.subplots(figsize=(16, 8))
    candles(ax, bars, width=0.3, lw=0.8)
    zigzag(ax, calc, offset)
    x_now = int((bars.index + pd.Timedelta(minutes=5) <= now.tz_convert("UTC")).sum()) - 0.5
    ax.axvspan(x_now, len(bars), color="#888888", alpha=0.10, zorder=0)
    ax.axvline(x_now, color="#444444", linewidth=1.0, linestyle=":")
    # The Fibo drawn as on MT5: from the 100 % point to the 0 % point (the top and the bottom of the leg),
    # each level only between those two times, the anchors marked with their price and Thai time.
    leg = p100 - p0
    x0 = int((bars.index < t0.tz_convert("UTC")).sum())
    x100 = int((bars.index < t100.tz_convert("UTC")).sum())
    xa, xb = min(x0, x100), max(x0, x100)
    ax.plot([x100, x0], [p100, p0], "--", color="#b08d00", linewidth=1.2, zorder=4)
    for x, p, t, name in ((x100, p100, t100, "100 %"), (x0, p0, t0, "0 %")):
        ax.plot([x], [p], "o", color="#b08d00", markersize=6, zorder=6)
        ax.annotate(
            f"{name}  {p:.2f}\n{t:%d/%m %H:%M}",
            (x, p),
            xytext=(-6, 0),
            textcoords="offset points",
            fontsize=8,
            color="#806600",
            ha="right",
            va="center",
            fontweight="bold",
        )
    for lv in levels:
        y = p0 + lv * leg
        ax.plot([xa, xb], [y, y], color="#b08d00", linewidth=0.9, zorder=1)
        ax.annotate(
            f"{lv * 100:.1f} %  {y:.2f}", (xb + 1, y), fontsize=7, color="#806600", ha="left", va="center"
        )
    rng = H1_RANGE.search(row["structure"])
    if rng:  # the H1 range's edges and edge zones (-0.27 / 0.12, 0.88 / 1.27), across the whole chart
        lo, hi = float(rng[1]), float(rng[2])
        for lv in (-0.27, 0.0, 0.12, 0.88, 1.0, 1.27):
            y = lo + lv * (hi - lo)
            edge = lv in (0.0, 1.0)
            ax.axhline(
                y, color="#7a3fa0", linewidth=1.2 if edge else 0.7, linestyle="-" if edge else ":", zorder=1
            )
            ax.annotate(
                f"H1 {lv * 100:.0f} %  {y:.2f}" + (f"  ({rng[3]} pivots, leg {rng[4]})" if lv == 1.0 else ""),
                (0, y), fontsize=7, color="#7a3fa0", va="bottom",
            )  # fmt: skip
    for name, key, colour in (
        ("entry", "entry", "#1f5fbf"),
        ("stop", "stop", "#a83242"),
        ("target", "target", "#10795f"),
    ):
        y = float(row[key])
        ax.plot([x_now, len(bars)], [y, y], color=colour, linewidth=1.6, zorder=5)
        ax.annotate(f"{name} {y:.2f}", (x_now + 1, y), fontsize=8, color=colour, va="bottom")
    result = row.get("why", "")
    r = row.get("r_net", "")
    ax.set_title(
        f"{row['id']}  {row['side']}  decided {decided:%d/%m %H:%M} Thai  |  "
        f"{'range' if m.re is RANGE else 'leg'} 0 % {p0:.2f} ({t0:%d/%m %H:%M}) -> "
        f"100 % {p100:.2f} ({t100:%d/%m %H:%M})  |  result: {result} {r}  (shaded = after the decision)",
        fontsize=10,
    )
    fig.tight_layout()
    path = out / f"{row['id']}.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def main() -> None:
    ledger = Path(sys.argv[1])
    out = HERE / "trades" / ledger.parent.name
    out.mkdir(parents=True, exist_ok=True)
    m5 = frame("M5")
    for row in csv.DictReader(ledger.open(encoding="utf-8")):
        print(draw(row, m5, out))


if __name__ == "__main__":
    main()
