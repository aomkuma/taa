"""V3-2 drawings for the owner's eye (venv-research for matplotlib). Per entry type, the main setting, inside the windows:
- the losers by reason (R10): one per reason - the first loser of that reason in time order;
- a rule-picked sample: the first winner and the first loser of P1 and of P2.
Each chart: M1 candles from 60 minutes before the decision to 30 minutes after the exit (Thai time), the fill, the
initial stop, the target and the exit. Learning bars only (the reader stops before 2026-04-18).

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/dev2/draw_v32.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = HERE / "charts" / "v32"
TH = "Asia/Bangkok"
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
MAIN = {"E1": "tf vol exit a", "E2": "tf vol exit a bias path", "E3": "tf vol stop ext", "E4": "tf vol exit a bias path"}


def m1(a: pd.Timestamp, b: pd.Timestamp) -> pd.DataFrame:
    b = min(b, EXAM)
    d = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet", filters=[("open_time", ">=", a), ("open_time", "<", b)])
    d.index = pd.to_datetime(d.open_time, utc=True)
    return d[~d.index.duplicated(keep="last")].sort_index()


def reason(r) -> str:
    if r.mfe < 0.5 * r.risk:
        return "wrong way"
    if r.after_best >= r.risk:
        return "ran later"
    return "no run"


def draw(r, name: str) -> str:
    t_dec = pd.Timestamp(int(r.t_dec), tz="UTC")
    t_exit = pd.Timestamp(int(r.exit_t), tz="UTC")
    d = m1(t_dec - pd.Timedelta(minutes=60), t_exit + pd.Timedelta(minutes=30))
    x = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(13, 5.5))
    up = d.close >= d.open
    ax.vlines(x, d.low, d.high, color="#555", lw=0.6)
    ax.bar(x[up], (d.close - d.open)[up], bottom=d.open[up], color="#2a9d8f", width=0.7)
    ax.bar(x[~up], (d.open - d.close)[~up], bottom=d.close[~up], color="#e76f51", width=0.7)
    pos = lambda t: int(np.searchsorted(d.index, t))  # noqa: E731
    i0, i1 = pos(t_dec), pos(t_exit)
    ax.axvline(i0, color="#264653", ls=":", lw=1)
    ax.hlines(r.fill, i0, i1, color="#264653", lw=1.4, label=f"fill {r.fill:.2f}")
    ax.hlines(r.stop0, i0, i1, color="#d62828", lw=1.2, ls="--", label=f"stop {r.stop0:.2f}")
    if np.isfinite(r.target):
        ax.hlines(r.target, i0, i1, color="#2b9348", lw=1.2, ls="--", label=f"target {r.target:.2f}")
    ax.plot([i1], [r.exit_px], marker="x", color="k", ms=9, label=f"exit {r.exit} {r.exit_px:.2f}")
    step = max(len(d) // 12, 1)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([t.strftime("%m-%d %H:%M") for t in d.index[::step].tz_convert(TH)], rotation=30, fontsize=8)
    side = "SELL" if r.side < 0 else "BUY"
    ax.set_title(f"{r.etype} {r.setting} | {side} {t_dec.tz_convert(TH):%Y-%m-%d %H:%M} Thai | {r.window} | entry TF {r.tf} | "
                 f"R {r.R:+.2f} pnl {r.pnl:+.2f} USD | {name}", fontsize=9)
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.2)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{r.etype}_{name.replace(' ', '_')}_{t_dec.tz_convert(TH):%Y%m%d_%H%M}.png"
    fig.tight_layout()
    fig.savefig(f, dpi=90)
    plt.close(fig)
    return f.name


def main() -> None:
    T = pd.read_parquet(HERE / "v32_trades.parquet")
    lines = []
    for et, st in MAIN.items():
        M = T[(T.etype == et) & (T.setting == st) & (T.scope == "win")].sort_values("t_fill")
        L = M[M.pnl <= 0].copy()
        L["why"] = [reason(r) for r in L.itertuples(index=False)]
        for why in ("wrong way", "ran later", "no run"):
            x = L[L.why == why]
            if len(x):
                lines.append(f"{et} loser '{why}': {draw(x.iloc[0], 'loser ' + why)}")
        for p in ("P1", "P2"):
            for lab, sel in (("winner", M.pnl > 0), ("loser", M.pnl <= 0)):
                x = M[(M.part == p) & sel]
                if len(x):
                    lines.append(f"{et} sample {p} first {lab}: {draw(x.iloc[0], f'sample {p} {lab}')}")
    (OUT / "index.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
