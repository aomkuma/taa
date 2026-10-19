"""Support / resistance from the larger timeframe - step 1, the zones drawn on the real candles before any count
(notes.md, written before it is computed; owner, 2026-10-19: "trade at the support / resistance of a timeframe larger
than the one you trade on"; "answer only from the real candles and the real chart patterns"). H1 fractal swings (k = 2,
each known when the second bar after it closes), the last 120 H1 bars' swings merged into zones (0.25 x H1 ATR), each
with its touches and kind; on every 12th weekday the first M1 bar after the NY open that reaches a zone, drawn.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/zones.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402

K, WIN, TOL_ATR, TOUCH_ATR, EVERY = 2, 120, 0.25, 0.1, 12


def swings(b: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """The fractal swings of bars b (indicators.bars): bar index, price, kind (+1 a top, -1 a low) and when it is known
    (the avail of the k-th bar after it; a swing without k bars after it yet is not known)."""
    h, lo = b.high.to_numpy(float), b.low.to_numpy(float)
    hi_i, lo_i = F.fractals(h, lo, k)
    av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
    rows = [(i, h[i], 1) for i in hi_i] + [(i, lo[i], -1) for i in lo_i]
    S = pd.DataFrame(rows, columns=["i", "price", "kind"]).sort_values(["i", "kind"]).reset_index(drop=True)
    S = S[S.i + k < len(b)].reset_index(drop=True)
    S["known"] = av[S.i.to_numpy() + k]
    return S


def merge(prices: np.ndarray, kinds: np.ndarray, tol: float) -> pd.DataFrame:
    """foundation.merge_levels' rule (sorted; a price joins the zone while within tol of its FIRST price), keeping the
    kinds: the zone's price (the mean), its touches, its tops and its lows."""
    o = np.argsort(prices, kind="stable")
    v, kd = np.asarray(prices, float)[o], np.asarray(kinds)[o]
    rows, a = [], 0
    for j in range(1, len(v) + 1):
        if j == len(v) or v[j] - v[a] > tol:
            rows.append((float(v[a:j].mean()), j - a, int((kd[a:j] > 0).sum()), int((kd[a:j] < 0).sum())))
            a = j
    return pd.DataFrame(rows, columns=["price", "touches", "tops", "lows"])


def zones_at(S: pd.DataFrame, avail_ns: np.ndarray, atr: np.ndarray, t_ns: int, win: int = WIN) -> tuple[pd.DataFrame, float]:
    """The zones known at t_ns: the swings known by then among the last `win` complete bars, merged with tol = TOL_ATR x
    the last complete bar's ATR. Returns (zones, that ATR)."""
    bi = int(np.searchsorted(avail_ns, t_ns, side="right")) - 1
    if bi < 0 or not np.isfinite(atr[bi]):
        return pd.DataFrame(columns=["price", "touches", "tops", "lows"]), np.nan
    sel = S[(S.known <= t_ns) & (S.i > bi - win)]
    return merge(sel.price.to_numpy(), sel.kind.to_numpy(), TOL_ATR * atr[bi]), float(atr[bi])


def first_touch(m: pd.DataFrame, a: int, b: int, S: pd.DataFrame, avail_ns: np.ndarray, atr: np.ndarray) -> tuple[int, pd.DataFrame, float] | None:
    """The first M1 bar j in [a, b) whose range comes within TOUCH_ATR x H1 ATR of a zone known at its open; returns
    (j, the zones, the ATR) or None."""
    h, lo = m.high.to_numpy(float), m.low.to_numpy(float)
    t_ns = m.index.as_unit("ns").asi8
    for j in range(a, b):
        Z, at = zones_at(S, avail_ns, atr, int(t_ns[j]))
        if Z.empty:
            continue
        d = TOUCH_ATR * at
        if ((Z.price >= lo[j] - d) & (Z.price <= h[j] + d)).any():
            return j, Z, at
    return None


def moments(m: pd.DataFrame, days: pd.DatetimeIndex, S: pd.DataFrame, avail_ns: np.ndarray, atr: np.ndarray) -> list[dict]:
    """On each given day: the first touch from the NY open (09:30 NY) to 3 hours after it."""
    out = []
    for d in days:
        ny = pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=9, minute=30, tz="America/New_York").tz_convert("UTC")
        a = int(np.searchsorted(m.index, ny))
        b = int(np.searchsorted(m.index, ny + pd.Timedelta(hours=3)))
        x = first_touch(m, a, b, S, avail_ns, atr)
        if x is not None:
            out.append(dict(j=x[0], zones=x[1], atr=x[2]))
    return out


def draw(m: pd.DataFrame, b1: pd.DataFrame, x: dict, title: str, out: Path) -> None:
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    from loser_charts import candles  # noqa: PLC0415

    j, Z = x["j"], x["zones"]
    t = m.index[j]
    av = pd.DatetimeIndex(b1["avail"])
    bi = int(np.searchsorted(av, t, side="right"))  # the complete H1 bars at the touch
    H = b1.iloc[max(bi - WIN, 0):bi]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1.6, 1]})
    candles(ax1, *(H[k].to_numpy(float) for k in ("open", "high", "low", "close")))
    lo_y, hi_y = H.low.min(), H.high.max()
    for z in Z.itertuples():
        if not lo_y - 5 <= z.price <= hi_y + 5:
            continue
        col = "#7a4fd6" if z.tops and z.lows else "#d6492f" if z.tops else "#1a9b77"
        ax1.axhline(z.price, color=col, linewidth=0.6 + 0.5 * min(z.touches, 4), alpha=0.75)
        ax1.text(len(H) + 0.5, z.price, f"{z.price:.1f} x{z.touches}", color=col, fontsize=7, va="center")
    ax1.axhline(m.close.iloc[j], color="#2f6fd6", linewidth=0.8, linestyle=":")
    ticks = list(range(0, len(H), 24))
    ax1.set_xticks(ticks, [pd.Timestamp(H["last"].iloc[k]).tz_convert("Asia/Bangkok").strftime("%d %b %H:00") for k in ticks], fontsize=7)
    ax1.set_xlim(-1, len(H) + 12)
    ax1.set_title("H1, the last 5 days - the zones known at the touch (red = tops, green = lows, purple = both; x = touches)", fontsize=8)
    ax1.tick_params(axis="y", labelsize=7)
    a, e = max(j - 30, 0), min(j + 60, len(m) - 1)
    M = m.iloc[a:e + 1]
    candles(ax2, *(M[k].to_numpy(float) for k in ("open", "high", "low", "close")), a)
    near = Z[(Z.price >= M.low.min() - 3) & (Z.price <= M.high.max() + 3)]
    for z in near.itertuples():
        col = "#7a4fd6" if z.tops and z.lows else "#d6492f" if z.tops else "#1a9b77"
        ax2.axhline(z.price, color=col, linewidth=1.2, alpha=0.8)
        ax2.text(e + 0.5, z.price, f"x{z.touches}", color=col, fontsize=7, va="center")
    ax2.axvline(j, color="#2f6fd6", linewidth=0.8, alpha=0.6)
    tk = list(range(a, e + 1, 15))
    ax2.set_xticks(tk, [m.index[k].tz_convert("Asia/Bangkok").strftime("%H:%M") for k in tk], fontsize=7)
    ax2.set_xlim(a - 1, e + 8)
    ax2.set_title("M1, 30 min before to 60 min after the touch (blue line) - Thai time", fontsize=8)
    ax2.tick_params(axis="y", labelsize=7)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=85)
    plt.close(fig)


PAGE = """<title>H1 Zone Touches</title>
<style>
:root {{ --bg: #f6f5f2; --fg: #1d2127; --muted: #5b6270; --card: #ffffff; --line: #dcd9d2; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #15171b; --fg: #e8e6e1; --muted: #a2a8b3; --card: #f4f2ee; --line: #30343b; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg: #15171b; --fg: #e8e6e1; --muted: #a2a8b3; --card: #f4f2ee; --line: #30343b; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; margin: 0; padding-inline: 16px; padding-block: 20px; }}
main {{ max-width: 1150px; margin: 0 auto; display: grid; gap: 18px; }}
h1 {{ font-size: 1.3rem; margin: 0; text-wrap: balance; }}
p {{ color: var(--muted); margin: 0; max-width: 70ch; line-height: 1.5; }}
figure {{ margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 8px; display: grid; gap: 6px; }}
figcaption {{ font-size: 0.85rem; color: #1d2127; font-variant-numeric: tabular-nums; }}
img {{ width: 100%; height: auto; display: block; }}
</style>
<main>
<h1>H1 zones at the first touch after the New York open</h1>
<p>{n} real moments, one on every 12th weekday from 2025-10-18 to 2026-04-17 (chosen by that rule, not by eye). Left: the
last 5 days of H1 with the zones known at the touch - H1 swing highs / lows (2 bars each side, counted only once
confirmed) merged within a quarter of the H1 ATR; red = made of tops, green = of lows, purple = both (a flipped level);
x = how many swings the zone holds. Right: M1 around the first bar after 21:30 / 20:30 Thai (09:30 New York) that
reached a zone. Research charts only - to check that these are the levels meant before anything is counted.</p>
{body}
</main>
"""


def main() -> None:
    import plib  # noqa: PLC0415

    from indicators import bars  # noqa: PLC0415
    from m15_trades import PARTS  # noqa: PLC0415

    m = plib.load()
    m = m[(m.index >= pd.Timestamp("2025-09-01", tz="UTC")) & (m.index < pd.Timestamp(PARTS["P2"][1], tz="UTC"))]
    b1 = bars(m, "1h")
    atr = F.atr(b1.high.to_numpy(), b1.low.to_numpy(), b1.close.to_numpy(), 14)
    avail_ns = pd.DatetimeIndex(b1["avail"]).as_unit("ns").asi8
    S = swings(b1)
    days = pd.bdate_range(PARTS["P1"][0], PARTS["P2"][1], inclusive="left", tz="UTC")[::EVERY]
    X = moments(m, days, S, avail_ns, atr)
    outdir = HERE / "charts" / "zones_h1"
    outdir.mkdir(parents=True, exist_ok=True)
    cards = []
    for k, x in enumerate(X):
        t = m.index[x["j"]].tz_convert("Asia/Bangkok")
        Z = x["zones"]
        title = f"#{k + 1}  {t:%Y-%m-%d %H:%M} Thai - {len(Z)} zones known, H1 ATR {x['atr']:.1f} USD"
        f = outdir / f"{k + 1:02d}.png"
        draw(m, b1, x, title, f)
        cards.append((title, base64.b64encode(f.read_bytes()).decode()))
        print(title)
    body = "\n".join(f'<figure><figcaption>{t}</figcaption><img alt="{t}" src="data:image/png;base64,{b64}"></figure>' for t, b64 in cards)
    (HERE / "charts" / "zones_h1.html").write_text(PAGE.format(n=len(cards), body=body), encoding="utf-8")
    print(f"{len(cards)} moments drawn -> charts/zones_h1.html")


if __name__ == "__main__":
    main()
