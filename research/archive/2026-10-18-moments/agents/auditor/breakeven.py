"""Auditor check 4: the win rate a setup needs at the measured costs (break-even and the +0.15 R pass bar), against
a coin-flip side's win rate on a driftless walk, for gold (USD at 0.01 lot) and a major (pips).

Outcomes from the fill: a win pays the target; a stop pays -(stop + gap); costs paid at entry are inside the fill
(the spread) or added (commission). R as the harness: USD / (stop + 0.07). Coin: on a driftless mid price the
target lies tp + spread away and the stop sl - spread away -> p0 = (sl - spread) / (tp + sl) (time-outs ignored).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/breakeven.py
"""

from __future__ import annotations

import pandas as pd

pd.set_option("display.width", 220)


def table(tools: list[tuple[float, float]], costs: dict[str, tuple[float, float, float]], unit: str, pad: float) -> pd.DataFrame:
    rows = []
    for name, (spread, gap, comm) in costs.items():
        for tp, sl in tools:
            loss = sl + gap + comm
            win = tp - comm
            p_be = loss / (win + loss)
            p_pass = (loss + 0.15 * (sl + pad)) / (win + loss)
            p0 = (sl - spread) / (tp + sl)
            cost_r = (spread + gap * (1 - p0) + comm) / (sl + pad)
            rows.append({"account / hour": name, f"tool tp/sl {unit}": f"{tp:g}/{sl:g}", "coin win %": 100 * p0,
                         "break-even win %": 100 * p_be, "+0.15R win %": 100 * p_pass,
                         "edge needed (pts, +0.15R)": 100 * (p_pass - p0), "cost a trade (R)": cost_r})
    return pd.DataFrame(rows)


def main() -> None:
    gold_tools = [(3, 3), (5, 4), (5, 6), (8, 6), (10, 8), (15, 10), (20, 12)]
    # (entry spread, stop gap beyond the stop, commission per trade at 0.01 lot), all USD; measured in tick_sim / tick_vs_m1
    gold_costs = {
        "harness (M1 min spread 0.26 + 0.07 slip, gap 0.07)": (0.33, 0.07, 0.0),
        "real, London/NY 2026-04..10 (spread 0.29)": (0.29, 0.17, 0.0),
        "real, all hours average (spread 0.345)": (0.345, 0.17, 0.0),
        "real, Asia / cap (spread 0.39)": (0.39, 0.15, 0.0),
        "raw-type account (spread ~0.10 + 6 USD/lot)": (0.10, 0.17, 0.06),
    }
    g = table(gold_tools, gold_costs, "USD", 0.07)
    print("GOLD (XAUUSD), USD at 0.01 lot")
    print(g.round(1).to_string(index=False))
    g.to_csv("research/2026-10-18-moments/agents/auditor/breakeven_gold.csv", index=False)
    fx_tools = [(3, 3), (5, 5), (8, 6), (10, 8), (15, 10), (20, 15)]
    # pips: EURUSD spread column 0.8 (the minimum); real assumed +0.2 (gold's real/min ratio is ~1.3); stop gap 0.2
    fx_costs = {
        "EURUSD column (0.8, min) + 0 gap": (0.8, 0.0, 0.0),
        "EURUSD assumed real (1.0) + gap 0.2": (1.0, 0.2, 0.0),
        "GBPUSD/USDJPY assumed real (1.2) + gap 0.2": (1.2, 0.2, 0.0),
        "NZDUSD/USDCAD assumed real (1.5) + gap 0.2": (1.5, 0.2, 0.0),
        "rollover 21-22 UTC (3-5)": (4.0, 0.3, 0.0),
    }
    f = table(fx_tools, fx_costs, "pips", 0.2)
    print("\nMAJORS, pips (EURUSD: 1 pip = 0.10 USD at 0.01 lot)")
    print(f.round(1).to_string(index=False))
    f.to_csv("research/2026-10-18-moments/agents/auditor/breakeven_fx.csv", index=False)


if __name__ == "__main__":
    main()
