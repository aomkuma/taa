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


ORDER = ("x3+ / flip", "x2", "5d high", "5d low", "PDH", "PDL", "last top", "last low")


def levels_at(Y: dict, t_ns: int, price: float, win: int = WIN) -> tuple[pd.DataFrame, float]:
    """The owner's levels at t_ns (owner, 2026-10-19 - all four kinds picked from the drawn zones): the zones of >= 3
    swings or flipped (tops and lows), of 2 swings, the five-day high / low (the last `win` complete H1 bars), the
    previous server day's high / low, the latest known swing top above `price` and low below it. A level within the
    zone tolerance of a stronger one already kept is dropped (ORDER = strongest first). Y: S, avail, atr, h, lo (H1)
    and d_avail, d_high, d_low (D1)."""
    Z, a = zones_at(Y["S"], Y["avail"], Y["atr"], t_ns, win)
    if not np.isfinite(a):
        return pd.DataFrame(columns=["price", "kind", "touches"]), a
    bi = int(np.searchsorted(Y["avail"], t_ns, side="right")) - 1
    cand = []
    for z in Z.itertuples():
        if z.touches >= 3 or (z.tops and z.lows):
            cand.append((z.price, "x3+ / flip", z.touches))
        elif z.touches == 2:
            cand.append((z.price, "x2", 2))
    a0 = max(bi - win + 1, 0)
    cand += [(float(Y["h"][a0:bi + 1].max()), "5d high", 0), (float(Y["lo"][a0:bi + 1].min()), "5d low", 0)]
    kd = int(np.searchsorted(Y["d_avail"], t_ns, side="right")) - 1
    if kd >= 0:
        cand += [(float(Y["d_high"][kd]), "PDH", 0), (float(Y["d_low"][kd]), "PDL", 0)]
    S = Y["S"]
    known = S[(S.known <= t_ns) & (S.i > bi - win)]
    tops, lows = known[(known.kind == 1) & (known.price > price)], known[(known.kind == -1) & (known.price < price)]
    if len(tops):
        cand.append((float(tops.price.loc[tops.i.idxmax()]), "last top", 1))
    if len(lows):
        cand.append((float(lows.price.loc[lows.i.idxmax()]), "last low", 1))
    cand.sort(key=lambda c: ORDER.index(c[1]))
    kept: list[tuple] = []
    for c in cand:
        if all(abs(c[0] - k[0]) > TOL_ATR * a for k in kept):
            kept.append(c)
    return pd.DataFrame(kept, columns=["price", "kind", "touches"]), a


def first_touch(m: pd.DataFrame, a: int, b: int, at_fn) -> tuple[int, pd.DataFrame, float] | None:
    """The first M1 bar j in [a, b) whose range comes within TOUCH_ATR x H1 ATR of a level known at its open
    (at_fn(t_ns, the bar's open) -> (levels, ATR)); returns (j, the levels, the ATR) or None."""
    h, lo, o = m.high.to_numpy(float), m.low.to_numpy(float), m.open.to_numpy(float)
    t_ns = m.index.as_unit("ns").asi8
    for j in range(a, b):
        Z, at = at_fn(int(t_ns[j]), float(o[j]))
        if Z.empty:
            continue
        d = TOUCH_ATR * at
        if ((Z.price >= lo[j] - d) & (Z.price <= h[j] + d)).any():
            return j, Z, at
    return None


def moments(m: pd.DataFrame, days: pd.DatetimeIndex, at_fn) -> list[dict]:
    """On each given day: the first touch from the NY open (09:30 NY) to 3 hours after it."""
    out = []
    for d in days:
        ny = pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=9, minute=30, tz="America/New_York").tz_convert("UTC")
        a = int(np.searchsorted(m.index, ny))
        b = int(np.searchsorted(m.index, ny + pd.Timedelta(hours=3)))
        x = first_touch(m, a, b, at_fn)
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
        col, lw, ls = STYLE[z.kind]
        ax1.axhline(z.price, color=col, linewidth=lw, linestyle=ls, alpha=0.85)
        ax1.text(len(H) + 0.5, z.price, f"{z.price:.1f} {z.kind}", color=col, fontsize=7, va="center")
    ax1.axhline(m.close.iloc[j], color="#2f6fd6", linewidth=0.8, linestyle=":")
    ticks = list(range(0, len(H), 24))
    ax1.set_xticks(ticks, [pd.Timestamp(H["last"].iloc[k]).tz_convert("Asia/Bangkok").strftime("%d %b %H:00") for k in ticks], fontsize=7)
    ax1.set_xlim(-1, len(H) + 12)
    ax1.set_title("H1, the last 5 days - the owner's levels known at the touch", fontsize=8)
    ax1.tick_params(axis="y", labelsize=7)
    a, e = max(j - 30, 0), min(j + 60, len(m) - 1)
    M = m.iloc[a:e + 1]
    candles(ax2, *(M[k].to_numpy(float) for k in ("open", "high", "low", "close")), a)
    near = Z[(Z.price >= M.low.min() - 3) & (Z.price <= M.high.max() + 3)]
    for z in near.itertuples():
        col, lw, ls = STYLE[z.kind]
        ax2.axhline(z.price, color=col, linewidth=max(lw, 1.0), linestyle=ls, alpha=0.9)
        ax2.text(e + 0.5, z.price, z.kind, color=col, fontsize=7, va="center")
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


STYLE = {"x3+ / flip": ("#7a4fd6", 2.4, "-"), "x2": ("#d97a1a", 1.6, "-"), "5d high": ("#555555", 1.2, "--"),
         "5d low": ("#555555", 1.2, "--"), "PDH": ("#1d2127", 1.2, "-."), "PDL": ("#1d2127", 1.2, "-."),
         "last top": ("#2f6fd6", 1.0, ":"), "last low": ("#2f6fd6", 1.0, ":")}


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
<h1>The owner's H1 levels at the first touch after the New York open</h1>
<p>{n} real moments, one on every 12th weekday from 2025-10-18 to 2026-04-17 (chosen by that rule, not by eye). Left: the
last 5 days of H1 with the levels known at the touch, the four kinds the owner picked: zones of 3+ H1 swings or flipped
(purple, thick), of 2 swings (orange), the five-day high / low (grey dashed), the previous day's high / low (black
dash-dot), the latest swing top above / low below the price (blue dotted). H1 swings: 2 bars each side, counted only
once confirmed; merged within a quarter of the H1 ATR. Right: M1 around the first bar after 21:30 / 20:30 Thai (09:30
New York) that reached a level. <strong>Not entry points:</strong> the first touch after the New York open, drawn to check the levels - no entry rule has been applied. Research charts only.</p>
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
    d1 = bars(m, "1D")
    Y = dict(S=swings(b1), avail=avail_ns, atr=atr, h=b1.high.to_numpy(float), lo=b1.low.to_numpy(float),
             d_avail=pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8, d_high=d1.high.to_numpy(float), d_low=d1.low.to_numpy(float))
    days = pd.bdate_range(PARTS["P1"][0], PARTS["P2"][1], inclusive="left", tz="UTC")[::EVERY]
    X = moments(m, days, lambda t, p: levels_at(Y, t, p))
    outdir = HERE / "charts" / "zones_h1"
    outdir.mkdir(parents=True, exist_ok=True)
    cards = []
    for k, x in enumerate(X):
        t = m.index[x["j"]].tz_convert("Asia/Bangkok")
        Z = x["zones"]
        title = f"#{k + 1}  {t:%Y-%m-%d %H:%M} Thai - {len(Z)} levels known, H1 ATR {x['atr']:.1f} USD"
        f = outdir / f"{k + 1:02d}.png"
        draw(m, b1, x, title, f)
        cards.append((title, base64.b64encode(f.read_bytes()).decode()))
        print(title)
    body = "\n".join(f'<figure><figcaption>{t}</figcaption><img alt="{t}" src="data:image/png;base64,{b64}"></figure>' for t, b64 in cards)
    (HERE / "charts" / "zones_h1.html").write_text(PAGE.format(n=len(cards), body=body), encoding="utf-8")
    print(f"{len(cards)} moments drawn -> charts/zones_h1.html")


if __name__ == "__main__":
    main()
