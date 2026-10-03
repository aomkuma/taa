"""Small statistics helpers without SciPy: Beta quantiles, Wilson intervals, Brier score and log loss.

``betainc`` is the regularized incomplete beta function evaluated with Lentz's continued fraction
(Numerical Recipes §6.4); ``beta_ppf`` inverts it by bisection, which is exact to ~1e-10 and fast enough for
the handful of intervals an opportunity needs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

EPS = 1e-15
TINY = 1e-300


def _betacf(a: float, b: float, x: float, max_iter: int = 300) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > TINY else TINY)
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > TINY else TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > TINY else TINY
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > TINY else TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > TINY else TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta ``I_x(a, b)`` for a, b > 0."""
    if a <= 0 or b <= 0:
        raise ValueError("a and b must be positive")
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(ln_front)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_ppf(q: float, a: float, b: float, *, tol: float = 1e-10) -> float:
    """The *q* quantile of Beta(a, b)."""
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def beta_interval(a: float, b: float, level: float = 0.9) -> tuple[float, float]:
    tail = (1 - level) / 2
    return beta_ppf(tail, a, b), beta_ppf(1 - tail, a, b)


Z90 = 1.6448536269514722


def wilson_interval(hits: float, n: float, z: float = Z90) -> tuple[float, float]:
    """Wilson score interval for a proportion (90% by default); (0, 1) without data."""
    if n <= 0:
        return 0.0, 1.0
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def brier(p: Sequence[float] | np.ndarray, y: Sequence[float] | np.ndarray) -> float:
    pa, ya = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    return float(np.mean((pa - ya) ** 2)) if len(pa) else math.nan


def log_loss(p: Sequence[float] | np.ndarray, y: Sequence[float] | np.ndarray, eps: float = 1e-9) -> float:
    pa = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    ya = np.asarray(y, dtype=float)
    if not len(pa):
        return math.nan
    return float(-np.mean(ya * np.log(pa) + (1 - ya) * np.log(1 - pa)))
