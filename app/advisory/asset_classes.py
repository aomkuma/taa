"""Asset classes of broker symbols (PLAN §A25, R22; TAA-6A1). Inferred at runtime, never hardcoded per symbol.

Order of evidence, strongest first:

1. **Currency codes:** a precious-metal base (XAU, XAG, XPT, XPD) is METAL; a crypto base (BTC, ETH, ...) is
   CRYPTO.
2. **The terminal's symbol path** (``Forex\\Majors\\EURUSD``, ``Indices\\US30``, ``Stocks\\US\\AAPL``, ...):
   keywords for crypto, metals, energies, indices and stocks.
3. **``trade_calc_mode``:** CFDINDEX is INDEX, exchange stocks are STOCK, the Forex modes are Forex.
4. **Forex split** by the two currencies: the seven USD majors are FOREX_MAJOR, other pairs of G10 currencies
   FOREX_MINOR, anything with a non-G10 currency FOREX_EXOTIC.

Whatever matches nothing is OTHER (never guessed into a tradeable class).
"""

from __future__ import annotations

from enum import StrEnum

from app.broker import mt5_constants as c
from app.market_data.data_models import SymbolSpec


class AssetClass(StrEnum):
    FOREX_MAJOR = "FOREX_MAJOR"
    FOREX_MINOR = "FOREX_MINOR"
    FOREX_EXOTIC = "FOREX_EXOTIC"
    METAL = "METAL"
    INDEX = "INDEX"
    ENERGY = "ENERGY"
    CRYPTO = "CRYPTO"
    STOCK = "STOCK"
    OTHER = "OTHER"

    @property
    def is_forex(self) -> bool:
        return self in (AssetClass.FOREX_MAJOR, AssetClass.FOREX_MINOR, AssetClass.FOREX_EXOTIC)


G10 = frozenset({"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD", "NOK", "SEK"})
MAJORS = frozenset(
    {
        ("EUR", "USD"),
        ("GBP", "USD"),
        ("USD", "JPY"),
        ("USD", "CHF"),
        ("AUD", "USD"),
        ("USD", "CAD"),
        ("NZD", "USD"),
    }
)
METALS = frozenset({"XAU", "XAG", "XPT", "XPD"})
CRYPTO = frozenset(
    {"BTC", "ETH", "LTC", "XRP", "BCH", "ADA", "DOT", "SOL", "DOGE", "BNB", "XLM", "LINK", "AVAX", "TRX"}
)
FIAT_LIKE = 3  # ISO currency codes are three letters

PATH_KEYWORDS: tuple[tuple[tuple[str, ...], AssetClass], ...] = (
    (("crypto",), AssetClass.CRYPTO),
    (("metal",), AssetClass.METAL),
    (("energ", "oil", "gas"), AssetClass.ENERGY),
    (("indic", "index", "indices"), AssetClass.INDEX),
    (("stock", "share", "equit"), AssetClass.STOCK),
)
FOREX_MODES = frozenset({c.SYMBOL_CALC_MODE_FOREX, c.SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE})


def forex_class(base: str, quote: str) -> AssetClass:
    if (base, quote) in MAJORS:
        return AssetClass.FOREX_MAJOR
    if base in G10 and quote in G10:
        return AssetClass.FOREX_MINOR
    return AssetClass.FOREX_EXOTIC


def classify(spec: SymbolSpec) -> AssetClass:
    base, quote = spec.currency_base.upper(), spec.currency_profit.upper()
    if base in METALS:
        return AssetClass.METAL
    if base in CRYPTO:
        return AssetClass.CRYPTO
    path = spec.path.lower()
    for keywords, asset_class in PATH_KEYWORDS:
        if any(k in path for k in keywords):
            return asset_class
    if spec.calc_mode == c.SYMBOL_CALC_MODE_CFDINDEX:
        return AssetClass.INDEX
    if spec.calc_mode in (c.SYMBOL_CALC_MODE_EXCH_STOCKS,):
        return AssetClass.STOCK
    is_pair = len(base) == FIAT_LIKE and len(quote) == FIAT_LIKE and base != quote
    if spec.calc_mode in FOREX_MODES and is_pair:
        return forex_class(base, quote)
    if ("forex" in path or "fx" in path.split("\\")) and is_pair:
        return forex_class(base, quote)
    return AssetClass.OTHER
