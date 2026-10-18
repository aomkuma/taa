"""The same picture (notes.md '"The same picture" redefined'): a timeframe's 120-bar picture as the owner reads it -
its outline, its size in ATRs, the last leg (way and length) and where the close sits - and the rule that two
pictures are the same.

    from picture import features, same_tf, PictureLibrary
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

WIN = 120
RHO, SIZE, LEG, POS, EDGE, FLAT = 0.7, 1.4, 1.6, 0.2, 0.05, 0.1
SIM_TOL = 1e-6


def features(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: np.ndarray, piv: tuple, bi: int) -> dict[str, float]:
    """The picture of the WIN bars ending at bi (bi included): size = range / ATR(bi); pos = the close's place in the
    range (0 low .. 1 high); edge = +1 at a new high (pos >= 1 - EDGE), -1 at a new low, 0 else; the last leg from the
    last ZigZag swing confirmed by bi to the close: its way (+1 up, -1 down) and length in ATRs."""
    a0 = max(bi - WIN + 1, 0)
    hi, lw = float(np.max(h[a0:bi + 1])), float(np.min(lo[a0:bi + 1]))
    a = float(atr[bi])
    size = (hi - lw) / a if a > 0 else np.nan
    pos = (c[bi] - lw) / (hi - lw) if hi > lw else 0.5
    edge = 1 if pos >= 1 - EDGE else (-1 if pos <= EDGE else 0)
    net = (c[bi] - c[a0]) / a if a > 0 else 0.0
    net_way = 1 if net >= 1.0 else (-1 if net <= -1.0 else 0)  # the 120 bars' way, flat within 1 ATR
    pidx, pval, ptyp, pconf = piv
    k = int(np.searchsorted(pconf, bi, side="right")) - 1  # the last swing known at bi (pconf sorted)
    known = np.arange(k + 1)
    known = known[pidx[known] >= a0]
    pk, tr = pval[known][ptyp[known] == 1], pval[known][ptyp[known] == -1]
    if len(pk) >= 2 and len(tr) >= 2:
        hh, hl = pk[-1] > pk[-2], tr[-1] > tr[-2]
        struct = 1 if (hh and hl) else (-1 if (not hh and not hl) else 0)  # up / down / mixed
    else:
        struct = 9  # too few swings to say
    if k < 0 or a <= 0:
        return dict(size=size, pos=pos, edge=edge, leg_way=0, leg=np.nan, net_way=net_way, struct=struct)
    move = (c[bi] - pval[k]) / a
    return dict(size=size, pos=pos, edge=edge, leg_way=int(np.sign(move)), leg=abs(move), net_way=net_way, struct=struct)


def same_tf(fa: dict, fb: dict, corr: float) -> list[str]:
    """Why two pictures of one timeframe are NOT the same (an empty list: the same)."""
    why = []
    if fa["net_way"] != fb["net_way"]:
        why.append(f"the 120 bars' way {fa['net_way']:+d} vs {fb['net_way']:+d}")
    if fa["struct"] != fb["struct"]:
        why.append(f"swing structure {fa['struct']} vs {fb['struct']}")
    if not corr >= RHO - SIM_TOL:
        why.append(f"outline {corr:.2f}")
    if not (np.isfinite(fa["size"]) and np.isfinite(fb["size"])) or max(fa["size"], fb["size"]) > SIZE * min(fa["size"], fb["size"]):
        why.append(f"size {fa['size']:.1f} vs {fb['size']:.1f} ATR")
    la, lb = fa["leg"], fb["leg"]
    if not (np.isfinite(la) and np.isfinite(lb)):
        why.append("no last leg")
    elif not (la < FLAT and lb < FLAT):  # both flat: alike
        if fa["leg_way"] != fb["leg_way"] or max(la, lb) > LEG * min(la, lb):
            why.append(f"last leg {fa['leg_way']:+d} {la:.1f} vs {fb['leg_way']:+d} {lb:.1f} ATR")
    if abs(fa["pos"] - fb["pos"]) > POS + SIM_TOL or fa["edge"] != fb["edge"]:
        why.append(f"position {fa['pos']:.2f} vs {fb['pos']:.2f}")
    return why


@dataclass
class Pattern:
    pid: int
    created_day: int
    first: int  # the row of the moment that started it (its picture is the pattern's picture)
    occ_days: list[int] = field(default_factory=list)
    occ_outcomes: list[str] = field(default_factory=list)


class PictureLibrary:
    """A walk-forward pattern library where a moment repeats a pattern only when its codes are >= thr alike AND every
    timeframe's picture is the same as the pattern's first moment's (same_tf). The best by code similarity among those
    (ties: the earliest pattern)."""

    def __init__(self, codes: np.ndarray, shapes: np.ndarray, feats: list[list[dict]], thr: float = 0.8) -> None:
        self.codes, self.shapes, self.feats, self.thr = codes, shapes, feats, thr  # per row: codes, (n_tf, 40), [dict]
        self.patterns: list[Pattern] = []

    def alike(self, row: int, lead: int) -> tuple[float, list[str]]:
        sim = round(float(np.mean(self.codes[row] == self.codes[lead])), 9)
        why = [] if sim >= self.thr - SIM_TOL else [f"codes {sim:.2f}"]
        for i in range(self.shapes.shape[1]):
            corr = float(np.dot(self.shapes[row][i], self.shapes[lead][i]))
            why += [f"TF{i} " + w for w in same_tf(self.feats[row][i], self.feats[lead][i], corr)]
        return sim, why

    def best(self, row: int, before_day: int | None = None) -> int:
        top, k_top = -1.0, -1
        for p in self.patterns:
            if before_day is not None and p.created_day >= before_day:
                continue
            sim, why = self.alike(row, p.first)
            if not why and sim > top:
                top, k_top = sim, p.pid
        return k_top

    def add(self, row: int, day: int, outcome: str) -> tuple[int, bool]:
        k = self.best(row)
        if k >= 0:
            p = self.patterns[k]
            if not p.occ_days or p.occ_days[-1] != day:
                p.occ_days.append(day)
                p.occ_outcomes.append(outcome)
            return k, False
        self.patterns.append(Pattern(len(self.patterns), day, row, [day], [outcome]))
        return len(self.patterns) - 1, True


# ---------------------------------------------------------------- the same rule over many patterns at once
KEYS = ("size", "pos", "edge", "leg_way", "leg", "net_way", "struct")


def as_arrays(feats: list[list[dict]]) -> dict[str, np.ndarray]:
    """Rows x timeframes arrays of every feature."""
    return {k: np.array([[f[k] for f in row] for row in feats], dtype=float) for k in KEYS}


def same_mask(A: dict[str, np.ndarray], shapes: np.ndarray, row: int, cand: np.ndarray) -> np.ndarray:
    """same_tf for one row against many candidate rows at once: True where every timeframe is the same picture."""
    ok = np.ones((len(cand), A["size"].shape[1]), bool)
    ok &= A["net_way"][cand] == A["net_way"][row]
    ok &= A["struct"][cand] == A["struct"][row]
    corr = np.einsum("ktp,tp->kt", shapes[cand], shapes[row])
    ok &= corr >= RHO - SIM_TOL
    sa, sb = A["size"][cand], A["size"][row]
    with np.errstate(invalid="ignore"):
        ok &= np.isfinite(sa) & np.isfinite(sb) & (np.maximum(sa, sb) <= SIZE * np.minimum(sa, sb))
    la, lb = A["leg"][cand], A["leg"][row]
    fin = np.isfinite(la) & np.isfinite(lb)
    flat = (la < FLAT) & (lb < FLAT)
    with np.errstate(invalid="ignore"):
        legs = (A["leg_way"][cand] == A["leg_way"][row]) & (np.maximum(la, lb) <= LEG * np.minimum(la, lb))
    ok &= fin & (flat | legs)
    ok &= (np.abs(A["pos"][cand] - A["pos"][row]) <= POS + SIM_TOL) & (A["edge"][cand] == A["edge"][row])
    return ok.all(axis=1)


class FastPictureLibrary(PictureLibrary):
    """PictureLibrary with the comparison done over all patterns at once (same answers; tested against it)."""

    def __init__(self, codes: np.ndarray, shapes: np.ndarray, feats: list[list[dict]], thr: float = 0.8) -> None:
        super().__init__(codes, shapes, feats, thr)
        self.A = as_arrays(feats)
        self.firsts = np.zeros(0, int)
        self.created = np.zeros(0, int)

    def best(self, row: int, before_day: int | None = None) -> int:
        if len(self.firsts) == 0:
            return -1
        sim = np.round((self.codes[self.firsts] == self.codes[row]).mean(axis=1), 9)
        ok = (sim >= self.thr - SIM_TOL) & same_mask(self.A, self.shapes, row, self.firsts)
        if before_day is not None:
            ok &= self.created < before_day
        if not ok.any():
            return -1
        sim = np.where(ok, sim, -1.0)
        return int(np.argmax(sim))  # the first of the best: the earliest pattern

    def add(self, row: int, day: int, outcome: str) -> tuple[int, bool]:
        k, new = super().add(row, day, outcome)
        if new:
            self.firsts = np.r_[self.firsts, row]
            self.created = np.r_[self.created, day]
        return k, new
