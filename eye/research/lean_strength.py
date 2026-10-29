"""Does a strong H1 move carry on? The owner, 2026-10-29: without the H1 lean, would trading against a very
clear trend lose? Expectation: lean_levels/EXPECTATION.md, test 3. Reads lean_cands.csv's moments again and
the stored bars; the strength = the last 24 closed H1 bars' move in ATR(14) units, at the moment.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from app.indicators.volatility import atr  # noqa: E402
from eye import bot2e  # noqa: E402

OUT = HERE / "lean_levels"
EDGES = (0.0, 1.0, 2.0, 3.0, np.inf)


def main() -> None:
    full = bot2e.load_frames()
    df = pd.read_csv(OUT / "lean_cands.csv")
    strength = []
    for s in df.now_thai:
        now = pd.Timestamp(s, tz=bot2e.TH).tz_convert("UTC")
        h1 = bot2e.cut({"H1": full["H1"]}, now)["H1"]
        a = float(atr(h1.high, h1.low, h1.close, 14).iloc[-1])
        strength.append(float(h1.close.iloc[-1] - h1.close.iloc[-25]) / a)
    df["strength"] = strength
    df.to_csv(OUT / "lean_strength.csv", index=False)
    lines = [f"moments: {len(df)}", ""]
    for kk in ("k0.25", "k0.5"):
        lines.append(f"{kk}: continuation (the move's side) first")
        for lo_, hi_ in pairwise(EDGES):
            g = df[(df.strength.abs() >= lo_) & (df.strength.abs() < hi_) & df[kk].isin(["UP", "DOWN"])]
            cont = ((g.strength > 0) & (g[kk] == "UP")) | ((g.strength < 0) & (g[kk] == "DOWN"))
            months = g.assign(c=cont).groupby(g.now_thai.str[:7]).c.mean()
            lines.append(
                f"  |move| {lo_:g}-{hi_:g} ATR: {cont.mean():.3f} (n {len(g)}, "
                f"days {g.now_thai.str[:10].nunique()},"
                f" months above 0.5 {int((months > 0.5).sum())}/{len(months)})"
            )
        lines.append("")
    sep = df[df.now_thai.str.startswith("2026-09")]
    lines.append(f"September 2026: moments >= 3 ATR {int((sep.strength.abs() >= 3).sum())} of {len(sep)}")
    strong = df[df.strength.abs() >= 3]
    lines.append("days with a >= 3 ATR moment: " + ", ".join(sorted(strong.now_thai.str[:10].unique())))
    text = "\n".join(lines)
    (OUT / "lean_strength_summary.txt").write_bytes(text.encode("utf-8"))
    print(text)


if __name__ == "__main__":
    main()
