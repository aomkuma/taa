"""Does the H1 lean (BOT_RULES rule 1) point the way price goes next?

The owner, 2026-10-29: "find the answers by testing and proof". Hourly moments inside the owner's windows,
the lean computed exactly as the bot does (eye/bot2e.py h1_lean on the closed H1 bars at the moment). The
outcome, on M5 bars after the moment's close: which comes first within 24 h, price X above or X below the
close, X = k x the median of the last 20 H1 ZigZag legs. Expectation: lean_levels/EXPECTATION.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e  # noqa: E402

OUT = HERE / "lean_levels"
KS = (0.25, 0.5, 1.0)
HORIZON = 288  # M5 bars, 24 h
TIMES = ("07:00", "08:00", "09:00", "13:00", "14:00", "15:00", "19:30", "20:30", "21:30", "22:30")


def first_hit(hi: np.ndarray, lo: np.ndarray, start: int, base: float, x: float) -> str:
    """'UP' / 'DOWN' / 'BOTH' (one bar touched both) / 'NONE' within HORIZON bars from ``start``."""
    for j in range(start, min(start + HORIZON, len(hi))):
        up, dn = hi[j] >= base + x, lo[j] <= base - x
        if up and dn:
            return "BOTH"
        if up:
            return "UP"
        if dn:
            return "DOWN"
    return "NONE"


def main() -> None:
    full = bot2e.load_frames()
    m5 = full["M5"]
    hi, lo, cl = (m5[c].to_numpy(np.float64) for c in ("high", "low", "close"))
    ends = m5.index + pd.Timedelta(minutes=5)
    days = pd.date_range("2025-10-08", "2026-10-27", freq="D", tz=bot2e.TH)
    rows = []
    for d in days:
        if d.weekday() >= 5:
            continue
        for t in TIMES:
            now = pd.Timestamp(f"{d.date()} {t}", tz=bot2e.TH).tz_convert("UTC")
            k = int(ends.searchsorted(now, side="right"))  # M5 bars closed by now
            if k < 1 or ends[k - 1] != now or k >= len(m5):
                continue
            h1 = bot2e.cut({"H1": full["H1"]}, now)["H1"]
            piv = bot2e._zigzag(h1)
            if len(piv) < 21:
                continue
            side, text = bot2e.h1_lean(h1, piv)
            med = float(np.median([abs(b.price - a.price) for a, b in zip(piv[-21:-1], piv[-20:], strict=True)]))
            base = float(cl[k - 1])
            row = {"now_thai": now.tz_convert(bot2e.TH).strftime("%Y-%m-%d %H:%M"), "lean": side or "none",
                   "lean_text": text, "price": base, "med_leg": round(med, 2)}
            for kk in KS:
                row[f"k{kk:g}"] = first_hit(hi, lo, k, base, kk * med)
            rows.append(row)
    df = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    df.to_csv(OUT / "lean_moments.csv", index=False)
    lines = [f"moments: {len(df)}  ({df.now_thai.min()} .. {df.now_thai.max()})", ""]
    for kk in KS:
        col = f"k{kk:g}"
        lines.append(f"X = {kk:g} x median H1 leg")
        allr = df[df[col].isin(["UP", "DOWN"])]
        lines.append(f"  all moments: UP first {np.mean(allr[col] == 'UP'):.3f} (n {len(allr)})")
        for lean in ("BUY", "SELL", "none"):
            s = df[(df.lean == lean) & df[col].isin(["UP", "DOWN"])]
            if len(s) == 0:
                continue
            up = float(np.mean(s[col] == "UP"))
            ci = 1.96 * np.sqrt(up * (1 - up) / len(s))
            right = up if lean == "BUY" else 1 - up if lean == "SELL" else float("nan")
            lines.append(f"  lean {lean:4}: n {len(s):4}  UP first {up:.3f} +/- {ci:.3f}   lean side first {right:.3f}")
        lines.append("")
    by_month = df.assign(m=df.now_thai.str[:7])
    lines.append("by month, X = 0.5: lean side first (n)")
    for m, g in by_month.groupby("m"):
        s = g[g.lean.isin(["BUY", "SELL"]) & g["k0.5"].isin(["UP", "DOWN"])]
        right = ((s.lean == "BUY") & (s["k0.5"] == "UP")) | ((s.lean == "SELL") & (s["k0.5"] == "DOWN"))
        lines.append(f"  {m}: {right.mean():.3f} ({len(s)})   no lean {np.mean(g.lean == 'none'):.2f}")
    text = "\n".join(lines)
    (OUT / "lean_summary.txt").write_bytes(text.encode("utf-8"))
    print(text)


if __name__ == "__main__":
    main()
