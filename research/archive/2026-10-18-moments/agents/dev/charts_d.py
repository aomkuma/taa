"""Task D: 12 rule-picked trades per rule drawn for the owner (DEV_LOG.md "Task D - written before computing"): D1's core
on the ticks and D2 (trigger 2 U, stop 8 U, held 30 minutes, +0.5 USD); in each part the 3 winners and the 3 losers whose
entry is nearest the part's middle (P1 2025-12-02 12:00 UTC, P2 2026-03-02 12:00 UTC). M1 candles, Thai time.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/dev/charts_d.py
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
NS_MIN = 60 * 10**9
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
MIDDLE = {"P1": pd.Timestamp("2025-12-02 12:00", tz="UTC").value, "P2": pd.Timestamp("2026-03-02 12:00", tz="UTC").value}
INK, MUTED, UP, DOWN = "#1d2127", "#52514e", "#2f7d5b", "#b8453a"
ENTRY, STOP, TARGET, EXIT, BOX = "#2a5ea8", "#b8453a", "#2f7d5b", "#7a4fa3", "#e8dcc4"


def pick12(T: pd.DataFrame) -> list[tuple[pd.Series, str]]:
    """In each part the 3 winners and the 3 losers whose entry is nearest the part's middle (ties: the earlier)."""
    out = []
    for p in ("P1", "P2"):
        G = T[T.part == p].assign(dist=lambda x, p=p: (x.entry_t.astype("int64") - MIDDLE[p]).abs())
        for name, sel in (("winner", G.pnl > 0), ("loser", G.pnl <= 0)):
            H = G[sel].sort_values(["dist", "entry_t"], kind="stable").head(3)
            out += [(r, f"one of the 3 {name}s of {p} nearest its middle") for _, r in H.iterrows()]
    return out


def m1_window(a: int, b: int) -> pd.DataFrame:
    import pyarrow.parquet as pq  # noqa: PLC0415

    if b >= EXAM.value:
        raise RuntimeError("a chart may not reach the exam period")
    f = HERE.parents[3] / "data/history/FBS-Demo/XAUUSD/M1.parquet"
    x = pq.read_table(f, columns=["open_time", "open", "high", "low", "close"],
                      filters=[("open_time", ">=", pd.Timestamp(a, tz="UTC")), ("open_time", "<", pd.Timestamp(b, tz="UTC"))]).to_pandas()
    return x.drop_duplicates("open_time", keep="last").sort_values("open_time").set_index("open_time")


def thai(t_ns: int, fmt: str = "%H:%M") -> str:
    return pd.Timestamp(int(t_ns), tz="UTC").tz_convert("Asia/Bangkok").strftime(fmt)


def draw(r: pd.Series, rule: str, k: int, why: str, out: Path) -> str:
    t_anchor = int(r.t_dec) if rule == "D1" else int(r.t0)
    a = (int(pd.Timestamp(int(r.day)).value) + 5 * 60 * NS_MIN + 45 * NS_MIN) if rule == "D1" else t_anchor - 30 * NS_MIN
    b = int(r.exit_t) + 15 * NS_MIN
    m = m1_window(a, b)
    t0 = a
    x = (pd.DatetimeIndex(m.index).as_unit("ns").asi8 - t0) / NS_MIN + 0.5
    fig, ax = plt.subplots(figsize=(12, 4.6))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(color="#e4e2dc", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.5, colors=MUTED)
    o, h, lo, c = (m[q].to_numpy(float) for q in ("open", "high", "low", "close"))
    upm = c >= o
    for mask, col in ((upm, UP), (~upm, DOWN)):
        ax.vlines(x[mask], lo[mask], h[mask], color=col, linewidth=0.8)
        ax.vlines(x[mask], np.minimum(o, c)[mask], np.maximum(o, c)[mask], color=col, linewidth=2.6)
    xm = lambda t: (int(t) - t0) / NS_MIN  # noqa: E731
    end = xm(b)
    if rule == "D1":
        r0 = int(pd.Timestamp(int(r.day)).value) + 6 * 60 * NS_MIN
        ax.add_patch(plt.Rectangle((xm(r0), r.rl), 15, r.rh - r.rl, color=BOX, alpha=0.8, linewidth=0, zorder=0))
        ax.hlines([r.rh, r.rl], xm(r0), end, color=MUTED, linewidth=0.9, linestyle=":")
        ax.text(xm(r0) + 0.3, r.rh, f"range 06:00-06:15 UTC (13:00-13:15 Thai): {r.rh:.2f} / {r.rl:.2f}", fontsize=7,
                color=MUTED, va="bottom")
        if xm(r0 + 75 * NS_MIN) < end:  # the entry window's end, when it is inside the chart
            ax.axvline(xm(r0 + 75 * NS_MIN), color=MUTED, linewidth=0.8, linestyle="--")
            ax.text(xm(r0 + 75 * NS_MIN) + 0.3, 1.0, "entry window ends", transform=ax.get_xaxis_transform(), fontsize=7,
                    color=MUTED, va="top")
    else:
        ax.axvline(xm(r.t0), color=INK, linewidth=0.9, linestyle="--")
        ax.hlines([r.up, r.dn], xm(r.t0), xm(r.t0 + NS_MIN), color=INK, linewidth=1.6)
        ax.text(xm(r.t0) + 0.3, 1.0, f"{r.ny} NY", transform=ax.get_xaxis_transform(), fontsize=7, color=INK, va="top")
        ax.text(xm(r.t0 + NS_MIN) + 0.3, r.up, f"buy stop {r.up:.2f}", fontsize=7, color=INK, va="bottom")
        ax.text(xm(r.t0 + NS_MIN) + 0.3, r.dn, f"sell stop {r.dn:.2f}", fontsize=7, color=INK, va="top")
    ax.hlines(r.stop, xm(r.entry_t), xm(r.exit_t), color=STOP, linewidth=1.1, linestyle="--")
    ax.text(xm(r.exit_t) + 0.3, r.stop, f"stop {r.stop:.2f}", fontsize=7, color=STOP, va="center")
    if rule == "D1" and np.isfinite(r.target):
        ax.hlines(r.target, xm(r.entry_t), xm(r.exit_t), color=TARGET, linewidth=1.1, linestyle="--")
        ax.text(xm(r.exit_t) + 0.3, r.target, f"target {r.target:.2f}", fontsize=7, color=TARGET, va="center")

    def mark(tx: float, py: float, col: str, label: str, dy: int) -> None:
        ax.plot([tx], [py], marker="o", markersize=8, color=col, markeredgecolor="white", markeredgewidth=1.5, zorder=5)
        ax.annotate(label, (tx, py), xytext=(6, dy), textcoords="offset points", fontsize=7.5, color=INK, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, lw=0.9))

    side = int(r.side)
    mark(xm(r.entry_t), r.entry, ENTRY, f"{'BUY' if side > 0 else 'SELL'} {r.entry:.2f} {thai(r.entry_t, '%H:%M:%S')}", 12 * side)
    mark(xm(r.exit_t), r.exit_px, EXIT, f"out ({r.exit}) {r.exit_px:.2f} {thai(r.exit_t, '%H:%M:%S')}", -12 * side)
    ticks = np.arange(0, end + 1, 15)
    ax.set_xticks(ticks, [thai(t0 + v * NS_MIN) for v in ticks])
    ax.set_xlim(-0.5, end + 8)
    ax.set_xlabel("Thai time (UTC+7); M1 candles (bid)", fontsize=7.5, color=MUTED)
    ax.set_ylabel("XAUUSD (USD)", fontsize=7.5, color=MUTED)
    extra = ""
    if rule == "D1":
        lv = "" if pd.isna(r.level_ahead) else f"; a level ahead at {r.level_ahead:.2f} (D1L refuses)"
        extra = f" ADR20 {r.adr20:.1f}{' (D1S refuses)' if r.adr20 < 63.3 else ''}{lv}"
    else:
        extra = f" {r.release}" if r.release else ""
    title = (f"#{k} {rule} {thai(t_anchor, '%Y-%m-%d %H:%M')} Thai - {r.part} - {'BUY' if side > 0 else 'SELL'} - "
             f"{r.exit} - R {r.R:+.2f} ({r.pnl:+.2f} USD at 0.01 lot).{extra}")
    fig.suptitle(title, fontsize=9, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, f"Drawn because: {why}.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out, dpi=90, facecolor=fig.get_facecolor())
    plt.close(fig)
    return title


def main() -> None:
    A = pd.read_parquet(HERE / "d1_trades.parquet")
    T1 = A[(A.src == "ticks") & (A.L == 15) & (A.k == 2.0) & (A.X == 60) & A.traded.fillna(False).astype(bool)].copy()
    T1["day"] = pd.DatetimeIndex(T1.day).as_unit("ns").asi8
    B = pd.read_parquet(HERE / "d2_trades.parquet")
    T2 = B[(B.trig == 2.0) & (B.stop_u == 8.0) & (B.hold == 30) & (B.extra == 0.5)].copy()
    for rule, T in (("D1", T1), ("D2", T2)):
        outdir = HERE / "charts" / f"d_{rule.lower()}"
        outdir.mkdir(parents=True, exist_ok=True)
        cards = []
        for k, (r, why) in enumerate(pick12(T), 1):
            f = outdir / f"{k:02d}.png"
            title = draw(r, rule, k, why, f)
            cards.append((title, why, base64.b64encode(f.read_bytes()).decode()))
            print(f"{rule} #{k} {title}", flush=True)
        body = "\n".join(f'<figure><figcaption><b>{html.escape(t)}</b><br><span class="why">Drawn because: {html.escape(w)}.</span>'
                         f'</figcaption><img alt="{html.escape(t)}" src="data:image/png;base64,{b64}"></figure>' for t, w, b64 in cards)
        name = "Opening Range Trades" if rule == "D1" else "Data Minute Straddles"
        what = ("D1: the 13:00-Thai opening-range break (range 13:00-13:15 Thai; the first M1 close beyond it until 14:15 "
                "Thai; the stop at the other side; target 2 R; out after 60 minutes). On the ticks."
                if rule == "D1" else
                "D2: S2's straddle at the 08:30 / 10:00 New York minute (stops 2 U beyond the last ask / bid, live 60 s; stop "
                "8 U; out 30 minutes after the minute; +0.5 USD at the fill). On the ticks.")
        (HERE / "charts" / f"d_{rule.lower()}.html").write_text(PAGE.format(title=name, what=html.escape(what), n=len(cards), body=body),
                                                               encoding="utf-8")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg: #f6f5f2; --fg: #1d2127; --muted: #52514e; --card: #ffffff; --line: #dcd9d2; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }} }}
:root[data-theme="dark"] {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }}
body {{ background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; margin: 0; padding: 20px 16px; }}
main {{ max-width: 1180px; margin: 0 auto; display: grid; gap: 18px; }}
h1 {{ font-size: 1.3rem; margin: 0; text-wrap: balance; }}
p {{ color: var(--muted); margin: 0; max-width: 75ch; line-height: 1.5; }}
figure {{ margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 8px; display: grid; gap: 6px; }}
figcaption {{ color: #1d2127; font-size: 0.85rem; }}
.why {{ color: #52514e; }}
img {{ width: 100%; height: auto; }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p>{what} {n} trades picked by a rule written before computing: in each learning part, the 3 winners and the 3 losers
whose entry is nearest the part's middle. Nothing here is from the exam period. No claim of profit.</p>
{body}
</main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
