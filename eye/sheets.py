"""The hundred moments, and the sheets they are drawn on (eye/METHOD.md).

The moments are chosen by the clock and never by how they look. They alternate between the two readers -
odd ones to Claude, even ones to Codex - so both read the same period, the same session rotation and the
same conditions, and a difference in the results is a difference in the reading, not in the sample.

    python eye/sheets.py moments          # write eye/moments.csv
    python eye/sheets.py sheet <reader> <n>   # draw sheet n (6 panels) for that reader
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TH = "Asia/Bangkok"
BARS = 90  # 7.5 hours of M5 in each panel
HOURS = ("08:00", "14:00", "20:30")  # the owner's windows, in rotation
START = "2026-02-02"
SEEN = (("2026-07-06", "2026-07-09"), ("2026-10-19", "2026-10-27"))  # examined in earlier work


def m5() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/M5.parquet")
    col = next(c for c in df.columns if "time" in c.lower())
    df[col] = pd.to_datetime(df[col], utc=True)
    return df.set_index(col).sort_index()


def moments(bars: pd.DataFrame, count: int = 100) -> list[pd.Timestamp]:
    """Every second trading day from START, the hour rotating through the owner's windows."""
    local = bars.tz_convert(TH)
    days = sorted({d for d in local.index.normalize().unique() if str(d.date()) >= START})
    seen = [(pd.Timestamp(a, tz=TH), pd.Timestamp(b, tz=TH) + pd.Timedelta(days=1)) for a, b in SEEN]
    out: list[pd.Timestamp] = []
    for day in days[::2]:
        if any(a <= day < b for a, b in seen):
            continue
        at = day + pd.Timedelta(hours=int(HOURS[len(out) % 3][:2]), minutes=int(HOURS[len(out) % 3][3:]))
        before = local[local.index < at]
        if len(before) < BARS + 10 or len(local[(local.index >= at)]) < 72:
            continue
        out.append(at.tz_convert("UTC"))
        if len(out) == count:
            break
    return out


def write_moments() -> None:
    at = moments(m5())
    path = HERE / "moments.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "cutoff_utc", "cutoff_thai", "reader", "sheet", "panel"])
        for i, t in enumerate(at, start=1):
            reader = "claude" if i % 2 else "codex"
            n = (i - 1) // 2 // 6 + 1  # six panels a sheet, per reader
            panel = ((i - 1) // 2) % 6 + 1
            w.writerow([i, t.isoformat(), t.tz_convert(TH).strftime("%Y-%m-%d %H:%M"), reader, n, panel])
    print(f"{path}: {len(at)} moments, {at[0].tz_convert(TH):%d/%m/%y} .. {at[-1].tz_convert(TH):%d/%m/%y}")


def panel(ax: plt.Axes, frame: pd.DataFrame, title: str) -> None:
    loc = frame.index.tz_convert(TH)
    for i, (_, b) in enumerate(frame.iterrows()):
        up = b.close >= b.open
        colour = "#10795f" if up else "#a83242"
        ax.plot([i, i], [b.low, b.high], color=colour, linewidth=0.9, zorder=2)
        lo, hi = (b.open, b.close) if up else (b.close, b.open)
        ax.add_patch(
            plt.Rectangle(
                (i - 0.36, lo), 0.72, max(hi - lo, 0.01), facecolor=colour, edgecolor=colour, zorder=3
            )
        )
    step = max(1, len(frame) // 7)
    ax.set_xticks(list(range(0, len(frame), step)))
    ax.set_xticklabels([f"{loc[i]:%d/%m %H:%M}" for i in range(0, len(frame), step)], fontsize=7, rotation=30)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, alpha=0.16, linewidth=0.5)
    ax.set_title(title, fontsize=10)
    ax.margins(x=0.01)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def draw_sheet(reader: str, number: int, reveal: int = 0) -> None:
    rows = [r for r in csv.DictReader((HERE / "moments.csv").open(encoding="utf-8"))
            if r["reader"] == reader and int(r["sheet"]) == number]  # fmt: skip
    if not rows:
        raise SystemExit(f"no panels for {reader} sheet {number}")
    bars = m5()
    fig, axes = plt.subplots(2, 3, figsize=(21, 11), dpi=100)
    for ax, r in zip(axes.ravel(), rows, strict=False):
        cut = pd.Timestamp(r["cutoff_utc"])
        before = bars[bars.index + pd.Timedelta(minutes=5) <= cut].iloc[-BARS:]
        frame = before
        if reveal:
            frame = pd.concat([before, bars[bars.index >= cut].iloc[:reveal]])
        panel(ax, frame, f"#{r['id']}  panel {r['panel']}  to {r['cutoff_thai']} Thai")
        if reveal:
            ax.axvline(len(before) - 0.5, color="#2b6cb0", linewidth=1.4, linestyle="--", zorder=4)
    for ax in axes.ravel()[len(rows):]:  # fmt: skip
        ax.axis("off")
    fig.suptitle(
        f"XAUUSD M5 - {reader} sheet {number}" + (f" + {reveal} bars after" if reveal else " (decide now)"),
        fontsize=13,
    )
    fig.tight_layout()
    out = HERE / "sheets" / f"{reader}_{number:02d}{'_after' if reveal else ''}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out)
    print(f"{out}")
    for r in rows:
        cut = pd.Timestamp(r["cutoff_utc"])
        before = bars[bars.index + pd.Timedelta(minutes=5) <= cut].iloc[-BARS:]
        print(f"  #{r['id']} panel {r['panel']}  {r['cutoff_thai']} Thai   close {before.close.iloc[-1]:.2f}")


if __name__ == "__main__":
    if sys.argv[1] == "moments":
        write_moments()
    else:
        draw_sheet(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 0)
