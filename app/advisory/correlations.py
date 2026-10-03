"""H1 return correlations for the ranking's diversification score (PLAN §A25, S7).

Returns are log returns of closed H1 bars, aligned on bar open time; a pair needs ``min_overlap`` common
returns, otherwise its correlation is unknown (NaN) and never counts. Direction is unknown to the ranking, so
the absolute correlation is used: a hedge and a doubling of risk both concentrate the account on one driver.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd


def log_returns(closes: Mapping[str, pd.Series]) -> pd.DataFrame:
    """One column per symbol, indexed by bar open time (outer join, so gaps stay NaN)."""
    frames = {
        symbol: pd.Series(np.log(series.to_numpy(dtype=float)), index=series.index).diff()
        for symbol, series in closes.items()
        if len(series) > 1 and bool((series > 0).all())  # log returns need positive prices
    }
    if not frames:
        return pd.DataFrame()
    return pd.DataFrame(frames).sort_index()


def return_correlations(closes: Mapping[str, pd.Series], min_overlap: int = 100) -> pd.DataFrame:
    returns = log_returns(closes)
    if returns.empty:
        return returns
    return returns.corr(min_periods=min_overlap)


class CorrelationLookup:
    """Fast pairwise access to a correlation matrix (``DataFrame.at`` is too slow for the ranking's loops)."""

    def __init__(self, matrix: pd.DataFrame | None) -> None:
        if matrix is None or matrix.empty:
            self._pos: dict[str, int] = {}
            self._values = np.empty((0, 0))
        else:
            self._pos = {str(name): i for i, name in enumerate(matrix.index)}
            self._values = matrix.reindex(columns=matrix.index).to_numpy(dtype=float)

    def get(self, a: str, b: str) -> float | None:
        if a == b:
            return 1.0
        i, j = self._pos.get(a), self._pos.get(b)
        if i is None or j is None:
            return None
        value = float(self._values[i, j])
        return None if math.isnan(value) else value


Correlations = pd.DataFrame | CorrelationLookup | None


def _lookup(matrix: Correlations) -> CorrelationLookup:
    return matrix if isinstance(matrix, CorrelationLookup) else CorrelationLookup(matrix)


def correlation(matrix: Correlations, a: str, b: str) -> float | None:
    return _lookup(matrix).get(a, b)


def max_correlation(
    matrix: Correlations, symbol: str, others: Iterable[str]
) -> tuple[float | None, str | None]:
    """The largest |correlation| of *symbol* with *others* and which symbol it is (first wins on ties)."""
    lookup = _lookup(matrix)
    best: tuple[float | None, str | None] = (None, None)
    for other in others:
        value = lookup.get(symbol, other)
        if value is not None and (best[0] is None or abs(value) > best[0]):
            best = (abs(value), other)
    return best
