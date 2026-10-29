"""Other readings of the H1 lean, measured as lean_test.py measures rule 1 - the plan in eye/BOT_RESEARCH.md,
"Next - other readings of the H1 lean" (pass bar and expectation written there before this run).

A rule 1 as written; B rule 1 on H1 ZigZag depth 5; C close vs EMA(50) and its slope over 5 bars; D the close
against the close 24 H1 bars before, beyond ATR(14). Every reading uses the closed H1 frame the bot cuts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from lean_test import TIMES, first_hit  # noqa: E402

from app.indicators.chart_read import zigzag_pivots  # noqa: E402
from app.indicators.trend import ema  # noqa: E402
from app.indicators.volatility import atr  # noqa: E402
from eye import bot2e  # noqa: E402

OUT = HERE / "lean_levels"
KS = (0.25, 0.5)


def lean_b(h1: pd.DataFrame) -> str | None:
    piv = zigzag_pivots(
        h1.high.to_numpy(np.float64), h1.low.to_numpy(np.float64), bot2e.POINT, index=list(h1.index),
        depth=5, deviation=5, backstep=3,
    )  # fmt: skip
    return bot2e.h1_lean(h1, piv)[0]


def lean_c(h1: pd.DataFrame) -> str | None:
    e = ema(h1.close, 50)
    c, now, before = float(h1.close.iloc[-1]), float(e.iloc[-1]), float(e.iloc[-6])
    if c > now and now > before:
        return "BUY"
    if c < now and now < before:
        return "SELL"
    return None


def lean_d(h1: pd.DataFrame) -> str | None:
    a = float(atr(h1.high, h1.low, h1.close, 14).iloc[-1])
    move = float(h1.close.iloc[-1] - h1.close.iloc[-25])
    if move > a:
        return "BUY"
    if move < -a:
        return "SELL"
    return None


def main() -> None:
    full = bot2e.load_frames()
    m5 = full["M5"]
    hi, lo, cl = (m5[c].to_numpy(np.float64) for c in ("high", "low", "close"))
    ends = m5.index + pd.Timedelta(minutes=5)
    rows = []
    for d in pd.date_range("2025-10-08", "2026-10-27", freq="D", tz=bot2e.TH):
        if d.weekday() >= 5:
            continue
        for t in TIMES:
            now = pd.Timestamp(f"{d.date()} {t}", tz=bot2e.TH).tz_convert("UTC")
            k = int(ends.searchsorted(now, side="right"))
            if k < 1 or ends[k - 1] != now or k >= len(m5):
                continue
            h1 = bot2e.cut({"H1": full["H1"]}, now)["H1"]
            piv = bot2e._zigzag(h1)
            if len(piv) < 21:
                continue
            med = float(
                np.median([abs(b.price - a.price) for a, b in zip(piv[-21:-1], piv[-20:], strict=True)])
            )
            base = float(cl[k - 1])
            row = {
                "now_thai": now.tz_convert(bot2e.TH).strftime("%Y-%m-%d %H:%M"),
                "A": bot2e.h1_lean(h1, piv)[0] or "none",
                "B": lean_b(h1) or "none",
                "C": lean_c(h1) or "none",
                "D": lean_d(h1) or "none",
            }
            for kk in KS:
                row[f"k{kk:g}"] = first_hit(hi, lo, k, base, kk * med)
            rows.append(row)
    df = pd.DataFrame(rows)
    df["half"] = np.where(df.now_thai < "2026-04", "H1st", "H2nd")
    df["month"] = df.now_thai.str[:7]
    df.to_csv(OUT / "lean_cands.csv", index=False)
    lines = [f"moments: {len(df)}", ""]
    for cand in "ABCD":
        lines.append(f"candidate {cand}: share with a lean {np.mean(df[cand] != 'none'):.2f}")
        ok = True
        for kk in KS:
            col = f"k{kk:g}"
            s = df[df[cand].isin(["BUY", "SELL"]) & df[col].isin(["UP", "DOWN"])].copy()
            s["right"] = ((s[cand] == "BUY") & (s[col] == "UP")) | ((s[cand] == "SELL") & (s[col] == "DOWN"))
            parts = []
            for side in ("BUY", "SELL"):
                g = s[s[cand] == side]
                r = g.right.mean()
                ok &= bool(r >= 0.55 and len(g) >= 300)
                halves = []
                for h in ("H1st", "H2nd"):
                    gh = g[g.half == h]
                    halves.append(f"{gh.right.mean():.3f}/{len(gh)}")
                    ok &= bool(gh.right.mean() >= 0.53 and len(gh) >= 100)
                parts.append(f"{side} {r:.3f} (n {len(g)}; halves {', '.join(halves)})")
            months = s.groupby("month").right.mean()
            above = int((months > 0.5).sum())
            ok &= above >= 9
            lines.append(f"  k {kk:g}: pooled {s.right.mean():.3f} (n {len(s)}); " + "; ".join(parts))
            lines.append(f"         months above 0.5: {above}/{len(months)}")
        lines.append(f"  PASSES: {ok}")
        lines.append("")
    text = "\n".join(lines)
    (OUT / "lean_cands_summary.txt").write_bytes(text.encode("utf-8"))
    print(text)


if __name__ == "__main__":
    main()
