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


def correlation(matrix: pd.DataFrame | None, a: str, b: str) -> float | None:
    if a == b:
        return 1.0
    if matrix is None or a not in matrix.index or b not in matrix.columns:
        return None
    value = float(np.asarray(matrix.at[a, b], dtype=float))
    return None if math.isnan(value) else value


def max_correlation(
    matrix: pd.DataFrame | None, symbol: str, others: Iterable[str]
) -> tuple[float | None, str | None]:
    """The largest |correlation| of *symbol* with *others* and which symbol it is (first wins on ties)."""
    best: tuple[float | None, str | None] = (None, None)
    for other in others:
        value = correlation(matrix, symbol, other)
        if value is not None and (best[0] is None or abs(value) > best[0]):
            best = (abs(value), other)
    return best
