"""Exact decimal arithmetic for broker-facing quantities (volumes, prices).

Floating point is fine for indicators, but lot sizes and prices sent to a broker must be
aligned exactly to the symbol's volume step and tick size. Rounding volume *up* would
increase risk, so volume is always floored.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_UP, Decimal, InvalidOperation
from typing import Literal

Number = Decimal | float | int | str


def to_decimal(value: Number) -> Decimal:
    """Convert to Decimal via ``str`` so floats keep their shortest repr (0.1 -> '0.1')."""
    if isinstance(value, Decimal):
        return value
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"not a number: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite number: {value!r}")
    return result


def floor_to_step(value: Number, step: Number) -> Decimal:
    """Largest multiple of ``step`` that is <= ``value`` (for non-negative values)."""
    v, s = to_decimal(value), to_decimal(step)
    if s <= 0:
        raise ValueError(f"step must be positive, got {step!r}")
    if v < 0:
        raise ValueError(f"value must be non-negative, got {value!r}")
    multiples = (v / s).to_integral_value(rounding=ROUND_DOWN)
    return (multiples * s).quantize(s)


def round_to_tick(
    price: Number, tick_size: Number, mode: Literal["nearest", "down", "up"] = "nearest"
) -> Decimal:
    """Align a price to the symbol tick size."""
    p, t = to_decimal(price), to_decimal(tick_size)
    if t <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size!r}")
    rounding = {"nearest": ROUND_HALF_EVEN, "down": ROUND_DOWN, "up": ROUND_UP}[mode]
    multiples = (p / t).to_integral_value(rounding=rounding)
    return (multiples * t).quantize(t)


def is_multiple_of(value: Number, step: Number) -> bool:
    v, s = to_decimal(value), to_decimal(step)
    if s <= 0:
        raise ValueError("step must be positive")
    return (v / s) == (v / s).to_integral_value()


def decimals_of(step: Number) -> int:
    """Number of decimal places implied by a step (0.01 -> 2, 1 -> 0)."""
    exponent = to_decimal(step).normalize().as_tuple().exponent
    if not isinstance(exponent, int):  # only NaN/Inf have non-int exponents
        raise ValueError(f"invalid step: {step!r}")
    return max(0, -exponent)
