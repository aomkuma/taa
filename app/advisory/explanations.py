"""Explanation texts for advisory results, Thai and English (PLAN §A25).

Results carry a key and parameters; the text is rendered where it is shown (CLI, PWA, push), so the scores and
gates never depend on a language.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

Language = Literal["en", "th"]

TEXTS: dict[str, dict[Language, str]] = {
    "gate.not_evaluated": {
        "en": "Not evaluated: an earlier check failed or data is missing",
        "th": "ยังไม่ได้ประเมิน เพราะการตรวจก่อนหน้าไม่ผ่านหรือข้อมูลไม่ครบ",
    },
    # G1 tradable
    "g1.ok": {"en": "Tradable", "th": "เทรดได้"},
    "g1.trade_disabled": {
        "en": "Trading is disabled for this symbol",
        "th": "สัญลักษณ์นี้ปิดการเทรด",
    },
    "g1.no_direction": {
        "en": "New positions are not allowed in either direction (close only)",
        "th": "เปิดสถานะใหม่ไม่ได้ทั้งฝั่งซื้อและขาย (ปิดได้อย่างเดียว)",
    },
    "g1.spec_invalid": {
        "en": "The broker's symbol specification is invalid",
        "th": "ข้อมูลสเปกของสัญลักษณ์จากโบรกเกอร์ไม่ถูกต้อง",
    },
    "g1.no_filling": {
        "en": "No order filling mode is allowed",
        "th": "ไม่มีรูปแบบการจับคู่คำสั่ง (filling) ที่ใช้ได้",
    },
    "g1.calc_failed": {
        "en": "The broker could not calculate profit or margin for this symbol",
        "th": "โบรกเกอร์คำนวณกำไรขาดทุนหรือมาร์จิ้นของสัญลักษณ์นี้ไม่ได้",
    },
    "g1.spec_inconsistent": {
        "en": "The broker's profit calculation disagrees with its tick value",
        "th": "การคำนวณกำไรขาดทุนของโบรกเกอร์ไม่ตรงกับมูลค่าต่อ tick",
    },
    # G2 min-lot affordability
    "g2.ok": {
        "en": "The minimum lot risks {min_lot_risk} {currency}, within your budget of {budget} {currency}",
        "th": "ล็อตขั้นต่ำเสี่ยง {min_lot_risk} {currency} อยู่ในงบความเสี่ยง {budget} {currency}",
    },
    "g2.min_lot_risk": {
        "en": (
            "The minimum lot risks {min_lot_risk} {currency} vs your budget of {budget} {currency}; "
            "needs equity ≥ {required_equity} {currency}"
        ),
        "th": (
            "ล็อตขั้นต่ำเสี่ยง {min_lot_risk} {currency} เกินงบความเสี่ยง {budget} {currency} "
            "ต้องมีเงินทุน (equity) อย่างน้อย {required_equity} {currency}"
        ),
    },
    "g2.cap": {
        "en": "The minimum lot risks {min_lot_risk} {currency}, above the per-trade cap of {cap} {currency}",
        "th": "ล็อตขั้นต่ำเสี่ยง {min_lot_risk} {currency} เกินเพดานความเสี่ยงต่อไม้ {cap} {currency}",
    },
    # G3 margin
    "g3.ok": {
        "en": "Margin {margin} {currency} (with buffer) fits in the available {available} {currency}",
        "th": "มาร์จิ้น {margin} {currency} (รวมส่วนเผื่อ) อยู่ในวงเงินที่ใช้ได้ {available} {currency}",
    },
    "g3.margin": {
        "en": "Margin {margin} {currency} (with buffer) exceeds the available {available} {currency}",
        "th": "มาร์จิ้น {margin} {currency} (รวมส่วนเผื่อ) เกินวงเงินที่ใช้ได้ {available} {currency}",
    },
    "g3.margin_level": {
        "en": "The margin level after the trade would be {level}% (minimum {minimum}%)",
        "th": "ระดับมาร์จิ้นหลังเปิดไม้จะเหลือ {level}% (ขั้นต่ำ {minimum}%)",
    },
    # G4 cost
    "g4.ok": {
        "en": "Costs are {cost_pct}% of the stop (max {max_pct}%)",
        "th": "ต้นทุนคิดเป็น {cost_pct}% ของระยะ stop (สูงสุด {max_pct}%)",
    },
    "g4.cost": {
        "en": "Costs are {cost_pct}% of the stop, above {max_pct}%",
        "th": "ต้นทุนคิดเป็น {cost_pct}% ของระยะ stop เกิน {max_pct}%",
    },
    # G5 stops level
    "g5.ok": {
        "en": "The broker's minimum stop distance {stops_distance} fits the typical stop {typical_sl}",
        "th": "ระยะ stop ขั้นต่ำของโบรกเกอร์ {stops_distance} เหมาะกับระยะ stop ปกติ {typical_sl}",
    },
    "g5.stops_level": {
        "en": (
            "The broker's minimum stop distance {stops_distance} is too wide for the typical stop "
            "{typical_sl}"
        ),
        "th": "ระยะ stop ขั้นต่ำของโบรกเกอร์ {stops_distance} กว้างเกินไปเมื่อเทียบกับระยะ stop ปกติ {typical_sl}",
    },
    # G6 data
    "g6.ok": {"en": "Data is fresh and sufficient", "th": "ข้อมูลใหม่และเพียงพอ"},
    "g6.no_quote": {"en": "No current quote", "th": "ไม่มีราคาล่าสุด"},
    "g6.stale_quote": {
        "en": "The last quote is {age} s old",
        "th": "ราคาล่าสุดเก่า {age} วินาที",
    },
    "g6.few_candles": {
        "en": "Only {candles} of {required} candles are available",
        "th": "มีแท่งเทียนเพียง {candles} จาก {required} แท่ง",
    },
    "g6.no_atr": {
        "en": "Volatility (ATR) is not available",
        "th": "ยังคำนวณความผันผวน (ATR) ไม่ได้",
    },
}


MONEY_PARAMS = frozenset({"min_lot_risk", "budget", "required_equity", "cap", "margin", "available"})


def explain(key: str, params: Mapping[str, Any] | None = None, language: Language = "en") -> str:
    """The text for *key*; an unknown key renders as itself so nothing is silently hidden."""
    texts = TEXTS.get(key)
    if texts is None:
        return key
    values = {k: f"{v:,.2f}" if k in MONEY_PARAMS else v for k, v in (params or {}).items()}
    return texts[language].format(**values)
