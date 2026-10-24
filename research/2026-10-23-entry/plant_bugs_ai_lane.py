"""Planted bugs for app/strategy/ai_lane.py against tests/unit/test_strategy_ai_lane.py (plant.main; TAA-1806).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_ai_lane.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("a sell fills below the tolerance", [("if bid >= order.entry - tol:", "if bid >= order.entry - 2 * tol:")]),
    ("a sell fills at the ask", [("return AIEntry(order, at, bid)", "return AIEntry(order, at, ask)")]),
    ("a buy fills above the tolerance", [("if ask <= order.entry + tol:", "if ask <= order.entry + 2 * tol:")]),
    ("the sell's stop checked on the bid", [("if ask >= order.stop:", "if bid >= order.stop:")]),
    ("the buy's stop never drops it", [("        if bid <= order.stop:\n            self._orders.pop(symbol)\n            return None\n", "")]),
    ("no expiry", [("if at > order.valid_until:", "if False:")]),
    ("a filled order stays waiting", [("            if bid >= order.entry - tol:\n                self._orders.pop(symbol)\n", "            if bid >= order.entry - tol:\n")]),
    ("a new order does not replace the waiting one", [("self._orders[symbol] = order", "self._orders.setdefault(symbol, order)")]),
    ("cancel does nothing", [("self._orders.pop(symbol, None)\n\n    def request_exit", "pass\n\n    def request_exit")]),
    ("busy always false", [("return bool(self._orders)", "return False")]),
    ("the sell's geometry upside down", [("return self.stop > price and (self.target is None or self.target < price)", "return self.stop > price")]),
    ("the buy's stop side unchecked", [("return self.stop < price and (self.target is None or self.target > price)", "return self.target is None or self.target > price")]),
    ("the signal at the decided entry, not the quote", [("entry_price=price,", "entry_price=o.entry,")]),
    ("the AI's half size dropped", [("risk_scale=o.risk_scale,", "risk_scale=1.0,")]),
    ("the reasons lost", [('explanation=" | ".join(o.reasons),', 'explanation=o.setup,')]),
    ("the knowledge ids lost", [('Condition("ai_knowledge", True, 1.0, ", ".join(o.kb_ids)),', 'Condition("ai_knowledge", True, 1.0, ""),')]),
    ("the watch prices lost", [('f"above {o.watch_above} / below {o.watch_below}"', 'f"above {o.watch_above}"')]),
    ("the exit applied forever", [("            self._exits.discard(symbol)\n", "")]),
    ("the exit never applied", [("if symbol in self._exits:", "if symbol in self._orders:")]),
]

if __name__ == "__main__":
    main("app.strategy.ai_lane", ROOT / "tests/unit/test_strategy_ai_lane.py", BUGS)
