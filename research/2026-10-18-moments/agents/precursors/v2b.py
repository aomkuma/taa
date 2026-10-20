"""Setup OWN V2 as agreed with the owner (2026-10-18 17:02 Thai; restated 2026-10-19: "research the patterns before
price runs 5-10 USD, then let the bot catch a chart whose outline matches a researched pattern and decide whether to
trade"). Rules written before computing: notes.md "Setup OWN V2 as agreed".

At each of the owner's snap times (20 a day) the bot reads the chart of six timeframes in three layers (H4 + H1,
M30 + M15, M5 + M1). A layer matches a pattern of the walk-forward library when >= 80 % of the core attributes are
equal and - with the shape gate on - every timeframe's 120-bar close path correlates >= RHO with the pattern's
(the outline, not only the codes). The pattern's earlier days say how often price ran up / down (10 U within 30
minutes, or 3 U then 10 U before back). When the chosen layers lean one way by >= THETA with >= N_MIN earlier days
each, the bot enters that way at the next M1 open: the entry timeframe is the smallest of M1 / M5 / M15 / M30 whose
ATR covers 5 USD (M30 if none), the stop one entry-TF ATR (at least 5 USD), the target 10 U, out after 12 entry-TF
bars (exit on the timeframe entered). One position at a time; the auditor's costs. The cell (N_MIN, THETA, the
layers, the shape gate) is chosen walk-forward month by month from the previous six months' closed trades.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/v2b.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

TFS = ("H4", "H1", "M30", "M15", "M5", "M1")  # snaps.py's shape blocks, 40 points each
NPTS = 40
LAYER_TFS = {"ctx": ("H4", "H1"), "set": ("M30", "M15"), "trg": ("M5", "M1")}
UP, DN = ("ran_up", "slow_up"), ("ran_dn", "slow_dn")
RHOS = (None, 0.6, 0.8)  # the outline gate: off (codes only), every timeframe's path correlating >= 0.6 / 0.8
SIM_TOL = 1e-6  # similarities are shares k / n (n <= 120); float32 one-hot inputs round by ~1e-7


# ---------------------------------------------------------------- the library with the outline gate
@dataclass
class Pattern:
    pid: int
    created_day: int
    occ_days: list[int] = field(default_factory=list)
    occ_outcomes: list[str] = field(default_factory=list)


class OutlineLibrary:
    """pattern_library.PatternLibrary with an optional outline gate: a moment repeats a pattern only when its codes
    are >= thr alike AND (rho set) each timeframe's close path correlates >= rho with the pattern's first moment."""

    def __init__(self, dim: int, n_tf: int, thr: float = 0.8, rho: float | None = None) -> None:
        self.thr, self.rho = thr, rho
        self.patterns: list[Pattern] = []
        self._L = np.zeros((0, dim))
        self._S = np.zeros((0, n_tf, NPTS))
        self._created = np.zeros(0, np.int64)

    def most_similar(self, vec: np.ndarray, shape: np.ndarray, before_day: int | None = None) -> tuple[int, float]:
        if not self.patterns:
            return -1, np.nan
        sims = np.round((self._L @ vec).astype(float), 9)  # equal shares tie exactly: the earliest pattern wins
        if before_day is not None:
            sims = np.where(self._created < before_day, sims, -np.inf)
        if self.rho is not None:
            corr = np.einsum("ktp,tp->kt", self._S, shape).min(axis=1)  # the worst timeframe's correlation
            sims = np.where(corr >= self.rho - SIM_TOL, sims, -np.inf)
        k = int(np.argmax(sims))
        return (k, float(sims[k])) if np.isfinite(sims[k]) else (-1, np.nan)

    def add(self, vec: np.ndarray, shape: np.ndarray, day: int, outcome: str) -> tuple[int, bool]:
        k, sim = self.most_similar(vec, shape)
        if k >= 0 and sim >= self.thr - SIM_TOL:
            p = self.patterns[k]
            if not p.occ_days or p.occ_days[-1] != day:  # once a day at most
                p.occ_days.append(day)
                p.occ_outcomes.append(outcome)
            return k, False
        self.patterns.append(Pattern(len(self.patterns), day, [day], [outcome]))
        self._L = np.vstack([self._L, vec[None, :].astype(float)])
        self._S = np.concatenate([self._S, shape[None].astype(float)])
        self._created = np.r_[self._created, day]
        return len(self.patterns) - 1, True

    def lean(self, vec: np.ndarray, shape: np.ndarray, day: int) -> tuple[int, float]:
        """What the library knew before `day` about a moment like this: (earlier days of the matched pattern,
        up share - down share); (0, nan) without a match."""
        k, sim = self.most_similar(vec, shape, before_day=day)
        if k < 0 or sim < self.thr - SIM_TOL:
            return 0, np.nan
        o = np.array([x for d, x in zip(self.patterns[k].occ_days, self.patterns[k].occ_outcomes) if d < day])
        if len(o) == 0:
            return 0, np.nan
        return len(o), float(np.isin(o, UP).mean() - np.isin(o, DN).mean())


def decide(leans: dict[str, tuple[int, float]], layers: tuple[str, ...], n_min: int, theta: float) -> int:
    """The side to trade: every chosen layer needs >= n_min earlier days; their leans summed must reach theta."""
    total = 0.0
    for L in layers:
        n, x = leans[L]
        if n < n_min or not np.isfinite(x):
            return 0
        total += x
    return 1 if total >= theta - 1e-9 else (-1 if total <= -theta + 1e-9 else 0)


def plan(atrs: dict[str, float], price: float) -> tuple[str, float, float]:
    """(entry TF, stop distance, target distance): the smallest of M1 / M5 / M15 / M30 whose ATR covers 5 USD
    (M30 if none); the stop one entry-TF ATR, at least 5 USD; the target 10 U (1 U = price / 4100)."""
    etf = next((tf for tf in ("M1", "M5", "M15", "M30") if np.isfinite(atrs[tf]) and atrs[tf] >= 5.0), "M30")
    return etf, max(float(atrs[etf]), 5.0), 10.0 * price / 4100.0


# ---------------------------------------------------------------- the run
def main() -> None:
    import foundation as F  # noqa: PLC0415
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415
    from cluster_fp import onehot  # noqa: PLC0415
    from library_match import LAYERS, attrs  # noqa: PLC0415
    from lvl2 import MINS, NS_MIN, manage  # noqa: PLC0415

    plib.gold.below_normal_priority()
    S = pd.read_parquet(HERE / "snaps.parquet")
    FS = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    SH = np.load(HERE / "snap_shapes.npy").reshape(len(S), len(TFS), NPTS)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((S.S.dt.tz_convert("Asia/Bangkok").dt.normalize() - day0).dt.days).to_numpy()
    order = np.argsort(S.S.to_numpy(), kind="stable")
    cls = S.cls.to_numpy()
    short = {"context (H4+H1)": "ctx", "setup (M30+M15)": "set", "trigger (M5+M1)": "trg"}
    leans: dict[tuple[str, float | None], np.ndarray] = {}
    for layer, tfs in LAYERS.items():
        L = short[layer]
        V = onehot(attrs(FS, S, tfs))
        idx = [TFS.index(tf) for tf in LAYER_TFS[L]]
        for rho in RHOS:
            lib = OutlineLibrary(V.shape[1], len(idx), rho=rho)
            out = np.full((len(S), 2), np.nan)
            for e in order:
                shp = SH[e][idx]
                out[e] = lib.lean(V[e], shp, int(day[e]))
                lib.add(V[e], shp, int(day[e]), str(cls[e]))
            leans[(L, rho)] = out
    for L in ("ctx", "set", "trg"):  # how many snaps find an earlier-day pattern (>= 1 day) per gate
        print(L, {str(r): int((leans[(L, r)][:, 0] >= 1).sum()) for r in RHOS}, "of", len(S), flush=True)
    # the market: M1 with the auditor's costs, ATRs of M1 .. M30 at each snap
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    ot_ns = m.index.tz_convert("UTC").as_unit("ns").asi8
    ny = plib.ny_mask(m.index)
    atr_at = {}
    s_ns = pd.DatetimeIndex(S.S).as_unit("ns").asi8
    for tf, rule in (("M1", None), ("M5", "5min"), ("M15", "15min"), ("M30", "30min")):
        if rule is None:
            hh, ll, cc, av = h, lo, c, ot_ns + NS_MIN
        else:
            b = plib.tf_bars(m, rule)
            hh, ll, cc = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
            av = pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8
        a = F.atr(hh, ll, cc, 14)
        k = np.searchsorted(av, s_ns, side="right") - 1
        atr_at[tf] = np.where(k >= 0, a[np.maximum(k, 0)], np.nan)
    j0s = np.searchsorted(ot_ns, s_ns)  # the first M1 bar opening at or after the snap second
    empty = (np.array([], np.int64), np.array([], float))
    cells = {}
    for layers in (("set",), ("trg",), ("set", "trg"), ("ctx", "set", "trg")):
        for rho in RHOS:
            for n_min in (3, 5):
                for theta in (0.2, 0.4):
                    rows, busy = [], -1
                    for e in order:
                        lv = {L: (int(leans[(L, rho)][e, 0]), leans[(L, rho)][e, 1]) for L in ("ctx", "set", "trg")}
                        side = decide(lv, layers, n_min, theta)
                        j0 = int(j0s[e])
                        if side == 0 or j0 >= len(o) or j0 <= busy or ot_ns[j0] - s_ns[e] > 5 * 60 * 10**9:
                            continue
                        etf, sl, tp = plan({tf: atr_at[tf][e] for tf in atr_at}, c[j0 - 1])
                        ss = 0.20 if ny[j0] else 0.15
                        entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
                        t_end = int(ot_ns[j0] + 12 * MINS[etf] * NS_MIN)
                        x = manage(o, h, lo, c, sp, ot_ns, j0, side, entry, sl, tp, 0.0, *empty, 99.0, t_end, 0.07, ss)
                        rows.append(dict(t=m.index[j0 - 1], j0=j0, side=side, etf=etf, sl=sl, tp=tp, exit=x["exit"],
                                         pnl=x["pnl"], R=x["pnl"] / (sl + ss), xj=x["xj"], snap=S.name.iloc[e]))
                        busy = x["xj"]
                    if rows:
                        T = pd.DataFrame(rows)
                        T["x_t"] = wf.exit_time(m.index, T.xj.to_numpy())
                        name = f"{'+'.join(layers)}_{f'shape{rho}' if rho else 'codes'}_n{n_min}_th{theta}"
                        cells[name] = T
    # the learning half only (the exam per cell is not read): does the outline gate help?
    lrn = []
    for name, T in cells.items():
        x = T[T.t < plib.EXAM_START]
        if len(x):
            gate = name.split("_")[1]
            lrn.append(dict(cell=name, gate=gate, n=len(x), R=x.R.mean(), usd=x.pnl.sum()))
    Lr = pd.DataFrame(lrn)
    Lr.to_csv(HERE / "v2b_cells_learning.csv", index=False)
    print("\nthe cells on the learning half (2025-10-18 .. 2026-04-17), by the outline gate:")
    print(Lr.groupby("gate").agg(cells=("cell", "size"), trades=("n", "sum"), R_mean_of_cells=("R", "mean"),
                                 R_best=("R", "max"), usd=("usd", "sum")).round(3).to_string())
    WF, months = wf.walk_forward(cells, "2025-11", "2026-10")
    WF.to_parquet(HERE / "v2b_wf_trades.parquet")
    months.to_csv(HERE / "v2b_wf_months.csv", index=False)
    pd.set_option("display.width", 250)
    print("cells:", {k: len(v) for k, v in cells.items()})
    print(months.to_string(index=False))
    W = wf.weekly(WF)
    W.to_csv(HERE / "v2b_wf_weeks.csv", index=False)
    print("\nweek by week (Thai weeks, Monday):")
    print(W.to_string(index=False))
    split, end = plib.EXAM_START, plib.EXAM_END
    for name, part, wd in (("2025-10-18 .. 2026-04-17 (learning)", WF[WF.t < split], np.busday_count("2025-10-18", "2026-04-18")),
                           ("2026-04-18 .. 2026-10-16 (the exam)", WF[(WF.t >= split) & (WF.t < end)],
                            np.busday_count("2026-04-18", "2026-10-17"))):
        if part.empty:
            print(f"{name}: no trades")
            continue
        eq = part.pnl.cumsum()
        print(f"{name}: {len(part)} trades ({len(part) / wd:.2f} a weekday), win {(part.exit == 'win').mean():.3f}, "
              f"R {part.R.mean():+.3f}, USD {part.pnl.sum():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, worst "
              f"{part.pnl.min():+.2f}, longest losing streak {wf.longest_run(part.pnl.to_numpy() < 0)}")


if __name__ == "__main__":
    main()
