"""Trade server return codes and how TAA treats them (handling matrix in docs/PLAN.md §A12)."""

from __future__ import annotations

from enum import StrEnum


class RetcodeClass(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    RETRY_ONCE = "RETRY_ONCE"  # requote / price changed: one retry with a fresh price
    UNKNOWN = "UNKNOWN"  # outcome unknown: reconcile before anything else
    PERMANENT = "PERMANENT"  # malformed request: never retry
    SYMBOL_RESTRICTED = "SYMBOL_RESTRICTED"
    GLOBAL_HALT = "GLOBAL_HALT"
    BACKOFF = "BACKOFF"
    BROKER_LIMIT = "BROKER_LIMIT"
    ACCOUNT_MODE = "ACCOUNT_MODE"


RETCODES: dict[int, tuple[str, RetcodeClass]] = {
    10004: ("REQUOTE", RetcodeClass.RETRY_ONCE),
    10006: ("REJECT", RetcodeClass.PERMANENT),
    10007: ("CANCEL", RetcodeClass.PERMANENT),
    10008: ("PLACED", RetcodeClass.SUCCESS),
    10009: ("DONE", RetcodeClass.SUCCESS),
    10010: ("DONE_PARTIAL", RetcodeClass.PARTIAL),
    10011: ("ERROR", RetcodeClass.UNKNOWN),
    10012: ("TIMEOUT", RetcodeClass.UNKNOWN),
    10013: ("INVALID", RetcodeClass.PERMANENT),
    10014: ("INVALID_VOLUME", RetcodeClass.PERMANENT),
    10015: ("INVALID_PRICE", RetcodeClass.PERMANENT),
    10016: ("INVALID_STOPS", RetcodeClass.PERMANENT),
    10017: ("TRADE_DISABLED", RetcodeClass.SYMBOL_RESTRICTED),
    10018: ("MARKET_CLOSED", RetcodeClass.SYMBOL_RESTRICTED),
    10019: ("NO_MONEY", RetcodeClass.GLOBAL_HALT),
    10020: ("PRICE_CHANGED", RetcodeClass.RETRY_ONCE),
    10021: ("PRICE_OFF", RetcodeClass.RETRY_ONCE),
    10022: ("INVALID_EXPIRATION", RetcodeClass.PERMANENT),
    10023: ("ORDER_CHANGED", RetcodeClass.UNKNOWN),
    10024: ("TOO_MANY_REQUESTS", RetcodeClass.BACKOFF),
    10025: ("NO_CHANGES", RetcodeClass.SUCCESS),
    10026: ("SERVER_DISABLES_AT", RetcodeClass.GLOBAL_HALT),
    10027: ("CLIENT_DISABLES_AT", RetcodeClass.GLOBAL_HALT),
    10028: ("LOCKED", RetcodeClass.BACKOFF),
    10029: ("FROZEN", RetcodeClass.BACKOFF),
    10030: ("INVALID_FILL", RetcodeClass.PERMANENT),
    10031: ("CONNECTION", RetcodeClass.UNKNOWN),
    10032: ("ONLY_REAL", RetcodeClass.PERMANENT),
    10033: ("LIMIT_ORDERS", RetcodeClass.BROKER_LIMIT),
    10034: ("LIMIT_VOLUME", RetcodeClass.BROKER_LIMIT),
    10035: ("INVALID_ORDER", RetcodeClass.PERMANENT),
    10036: ("POSITION_CLOSED", RetcodeClass.PERMANENT),
    10038: ("INVALID_CLOSE_VOLUME", RetcodeClass.PERMANENT),
    10039: ("CLOSE_ORDER_EXIST", RetcodeClass.UNKNOWN),
    10040: ("LIMIT_POSITIONS", RetcodeClass.BROKER_LIMIT),
    10041: ("REJECT_CANCEL", RetcodeClass.PERMANENT),
    10042: ("LONG_ONLY", RetcodeClass.SYMBOL_RESTRICTED),
    10043: ("SHORT_ONLY", RetcodeClass.SYMBOL_RESTRICTED),
    10044: ("CLOSE_ONLY", RetcodeClass.SYMBOL_RESTRICTED),
    10045: ("FIFO_CLOSE", RetcodeClass.ACCOUNT_MODE),
    10046: ("HEDGE_PROHIBITED", RetcodeClass.ACCOUNT_MODE),
}


def describe(code: int | None) -> str:
    if code is None:
        return "NO_RESULT"
    name = RETCODES.get(code, ("UNKNOWN_RETCODE", RetcodeClass.UNKNOWN))[0]
    return f"{code} {name}"


def classify(code: int | None) -> RetcodeClass:
    """``None`` (order_send returned nothing) is UNKNOWN: the order may or may not exist."""
    if code is None:
        return RetcodeClass.UNKNOWN
    return RETCODES.get(code, ("", RetcodeClass.UNKNOWN))[1]
