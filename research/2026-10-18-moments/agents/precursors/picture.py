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
RETR, RETR_FLOOR, ER_DIFF = 1.6, 1.0, 0.1  # the deepest pullback within 1.6x (both under 1 ATR: alike); smoothness within 0.1
SIM_TOL = 1e-6
SEG_RHO = 0.5  # each third of the window (owner, 2026-10-19): the same way and an outline correlating >= 0.5
SEGS = ((0, 13), (13, 27), (27, 40))  # the thirds of the 40-point outline (120 bars: 0-39, 40-79, 80-119)
EPISODE_DAYS = 7  # the same picture again within 7 days is the same episode, not a repeat (owner's "more repeats")


def struct_brk(h: np.ndarray, lo: np.ndarray, close: float, piv: tuple, bi: int, a0: int) -> tuple[int, int]:
    """The swing structure (1 HH/HL, -1 LH/LL, 0 mixed, 9 too few swings) and the close against the last confirmed top
    and bottom (1 above, -1 below, 0 between, 9 none) from the ZigZag swings of bars a0 .. bi known at bi; the swing
    still forming counts in the structure (owner, 2026-10-19: price already above the last top is a higher top)."""
    pidx, pval, ptyp, pconf = piv
    k = int(np.searchsorted(pconf, bi, side="right")) - 1  # the last swing known at bi (pconf sorted)
    known = np.arange(k + 1)
    known = known[pidx[known] >= a0]
    pk, tr = list(pval[known][ptyp[known] == 1]), list(pval[known][ptyp[known] == -1])
    # after a confirmed trough the running high since it is the newest peak; after a confirmed peak the running low
    if k >= 0 and pidx[k] >= a0:
        if ptyp[k] == -1:
            pk.append(float(np.max(h[pidx[k]:bi + 1])))
        else:
            tr.append(float(np.min(lo[pidx[k]:bi + 1])))
    if len(pk) >= 2 and len(tr) >= 2:
        hh, hl = pk[-1] > pk[-2], tr[-1] > tr[-2]
        struct = 1 if (hh and hl) else (-1 if (not hh and not hl) else 0)  # up / down / mixed
    else:
        struct = 9  # too few swings to say
    ck = known[ptyp[known] == 1]
    tk = known[ptyp[known] == -1]
    if len(ck) and len(tk):
        top, bot = pval[ck[-1]], pval[tk[-1]]
        brk = 1 if close > top else (-1 if close < bot else 0)
    else:
        brk = 9
    return struct, brk


def zoom(fa: dict, small: tuple | None) -> dict:
    """When a timeframe's own swings are too few to read (structure or break 9), read them from the next smaller
    timeframe over the same span (owner, 2026-10-19: "look at the smaller timeframe - M5 shows the swings M15 misses").
    small = (h, lo, close, piv, bi, a0) of the smaller timeframe, a0 its first bar inside the larger window."""
    if small is None or (fa["struct"] != 9 and fa["brk"] != 9):
        return fa
    s, b = struct_brk(*small)
    out = dict(fa)
    if fa["struct"] == 9:
        out["struct"] = s
    if fa["brk"] == 9:
        out["brk"] = b
    return out


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
    # the path's character: the deepest move against the window's way (both ways when flat), in ATRs, and its
    # smoothness (Kaufman: |net| / the path of the closes)
    hh_run, ll_run = np.maximum.accumulate(h[a0:bi + 1]), np.minimum.accumulate(lo[a0:bi + 1])
    down_retr = float(np.max(hh_run - lo[a0:bi + 1])) / a if a > 0 else np.nan  # a fall from a running high
    up_retr = float(np.max(h[a0:bi + 1] - ll_run)) / a if a > 0 else np.nan  # a rise from a running low
    retr = down_retr if net_way > 0 else (up_retr if net_way < 0 else max(down_retr, up_retr))
    path = float(np.sum(np.abs(np.diff(c[a0:bi + 1]))))
    er = abs(c[bi] - c[a0]) / path if path > 0 else 0.0
    pidx, pval, ptyp, pconf = piv
    k = int(np.searchsorted(pconf, bi, side="right")) - 1  # the last swing known at bi (pconf sorted)
    struct, brk = struct_brk(h, lo, float(c[bi]), piv, bi, a0)
    # each third of the window: its own way (close to close, flat within 1 ATR)
    n = bi - a0 + 1
    segs = {}
    for j in range(3):
        s0, s1 = a0 + (j * n) // 3, a0 + ((j + 1) * n) // 3 - 1
        mv = (c[s1] - c[s0]) / a if a > 0 else 0.0
        segs[f"seg{j}"] = 1 if mv >= 1.0 else (-1 if mv <= -1.0 else 0)
    common = dict(size=size, pos=pos, edge=edge, net_way=net_way, struct=struct, brk=brk, retr=retr, er=er, **segs)
    if k < 0 or a <= 0:
        return dict(common, leg_way=0, leg=np.nan)
    move = (c[bi] - pval[k]) / a
    return dict(common, leg_way=int(np.sign(move)), leg=abs(move))


def seg_corr(sa: np.ndarray, sb: np.ndarray, k: int) -> float:
    """The Pearson correlation of two outlines over one third (both flat: 1, one flat: 0)."""
    a, b = sa[SEGS[k][0]:SEGS[k][1]], sb[SEGS[k][0]:SEGS[k][1]]
    a, b = a - a.mean(), b - b.mean()
    na, nb = np.sqrt((a * a).sum()), np.sqrt((b * b).sum())
    if na < 1e-9 or nb < 1e-9:
        return 1.0 if (na < 1e-9 and nb < 1e-9) else 0.0
    return float((a @ b) / (na * nb))


def same_tf(fa: dict, fb: dict, sa: np.ndarray, sb: np.ndarray) -> list[str]:
    """Why two pictures of one timeframe are NOT the same (an empty list: the same); sa, sb their 40-point outlines
    (zero mean, unit norm, as snaps.shapes)."""
    corr = float(np.dot(sa, sb))
    why = []
    for j in range(3):
        if fa[f"seg{j}"] != fb[f"seg{j}"]:
            why.append(f"third {j + 1}'s way {fa[f'seg{j}']:+d} vs {fb[f'seg{j}']:+d}")
        cj = seg_corr(sa, sb, j)
        if not cj >= SEG_RHO - SIM_TOL:
            why.append(f"third {j + 1}'s outline {cj:.2f}")
    if fa["net_way"] != fb["net_way"]:
        why.append(f"the 120 bars' way {fa['net_way']:+d} vs {fb['net_way']:+d}")
    if fa["struct"] != fb["struct"]:
        why.append(f"swing structure {fa['struct']} vs {fb['struct']}")
    if fa["brk"] != fb["brk"]:
        why.append(f"against the last top / bottom {fa['brk']} vs {fb['brk']}")
    ra, rb = fa["retr"], fb["retr"]
    if not (ra < RETR_FLOOR and rb < RETR_FLOOR) and not (min(ra, rb) > 0 and max(ra, rb) <= RETR * min(ra, rb)):
        why.append(f"deepest pullback {ra:.1f} vs {rb:.1f} ATR")
    if abs(fa["er"] - fb["er"]) > ER_DIFF + SIM_TOL:
        why.append(f"smoothness {fa['er']:.2f} vs {fb['er']:.2f}")
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
            why += [f"TF{i} " + w for w in same_tf(self.feats[row][i], self.feats[lead][i], self.shapes[row][i],
                                                    self.shapes[lead][i])]
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
            if not p.occ_days or day - p.occ_days[-1] >= EPISODE_DAYS:  # a new episode; within a week: the same one
                p.occ_days.append(day)
                p.occ_outcomes.append(outcome)
            return k, False
        self.patterns.append(Pattern(len(self.patterns), day, row, [day], [outcome]))
        return len(self.patterns) - 1, True


# ---------------------------------------------------------------- the same rule over many patterns at once
KEYS = ("size", "pos", "edge", "leg_way", "leg", "net_way", "struct", "brk", "retr", "er", "seg0", "seg1", "seg2")


def as_arrays(feats: list[list[dict]]) -> dict[str, np.ndarray]:
    """Rows x timeframes arrays of every feature."""
    return {k: np.array([[f[k] for f in row] for row in feats], dtype=float) for k in KEYS}


def same_mask(A: dict[str, np.ndarray], shapes: np.ndarray, row: int, cand: np.ndarray) -> np.ndarray:
    """same_tf for one row against many candidate rows at once: True where every timeframe is the same picture."""
    ok = np.ones((len(cand), A["size"].shape[1]), bool)
    ok &= A["net_way"][cand] == A["net_way"][row]
    ok &= A["struct"][cand] == A["struct"][row]
    ok &= A["brk"][cand] == A["brk"][row]
    ra, rb = A["retr"][cand], A["retr"][row]
    with np.errstate(invalid="ignore"):
        ok &= ((ra < RETR_FLOOR) & (rb < RETR_FLOOR)) | ((np.minimum(ra, rb) > 0) & (np.maximum(ra, rb) <= RETR * np.minimum(ra, rb)))
    ok &= np.abs(A["er"][cand] - A["er"][row]) <= ER_DIFF + SIM_TOL
    corr = np.einsum("ktp,tp->kt", shapes[cand], shapes[row])
    ok &= corr >= RHO - SIM_TOL
    for j, (s0, s1) in enumerate(SEGS):
        ok &= A[f"seg{j}"][cand] == A[f"seg{j}"][row]
        a = shapes[cand][:, :, s0:s1]
        b = shapes[row][:, s0:s1]
        a = a - a.mean(axis=-1, keepdims=True)
        b = b - b.mean(axis=-1, keepdims=True)
        na, nb = np.sqrt((a * a).sum(axis=-1)), np.sqrt((b * b).sum(axis=-1))
        with np.errstate(invalid="ignore", divide="ignore"):
            cj = np.einsum("ktp,tp->kt", a, b) / (na * nb)
        cj = np.where((na < 1e-9) | (nb < 1e-9), np.where((na < 1e-9) & (nb < 1e-9), 1.0, 0.0), cj)
        ok &= cj >= SEG_RHO - SIM_TOL
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


UP_CLS, DN_CLS = ("ran_up", "slow_up"), ("ran_dn", "slow_dn")


def evidence(lib: PictureLibrary, row: int, day: int) -> tuple[int, float, int]:
    """What the library can tell at a decision on `day` about the picture `row`: the same-picture pattern born at least
    EPISODE_DAYS before, and its episodes at least EPISODE_DAYS before - (episodes, up share - down share, the pattern
    id); (0, nan, -1) without one. Bug to 2026-10-19: "earlier calendar days" let a 23:00 snap be evidence at 00:00
    (the same situation an hour earlier, its outcome still running - up to 90 minutes - at the decision)."""
    last_ok = day - EPISODE_DAYS
    k = lib.best(row, before_day=last_ok + 1)
    if k < 0:
        return 0, float("nan"), -1
    p = lib.patterns[k]
    o = np.array([x for d, x in zip(p.occ_days, p.occ_outcomes) if d <= last_ok])
    if len(o) == 0:
        return 0, float("nan"), k
    return len(o), float(np.isin(o, UP_CLS).mean() - np.isin(o, DN_CLS).mean()), k
