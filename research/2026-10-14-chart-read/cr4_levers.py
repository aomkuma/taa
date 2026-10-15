"""CR-4 by proxy (2026-10-15): trend levers scored against the key (the blind agent, Claude on the 9 disputed charts)."""
import json, sys
from dataclasses import replace
sys.path.insert(0, "research/2026-10-14-chart-read"); sys.path.insert(0, ".")
from app.indicators.chart_read import ChartReadParams
from eye_check_score import rows, read_at
agent = json.load(open("research/2026-10-14-chart-read/eye_check_agent.json", encoding="utf-8"))["reads"]
truth = {int(k): {v[0]} for k, v in agent.items()}
truth.update({4: {"FLAT"}, 6: {"DOWN"}, 10: {"FLAT"}, 11: {"FLAT"}, 12: {"DOWN"}, 14: {"UP"},
              18: {"FLAT", "BROADENING"}, 19: {"UP"}, 20: {"FLAT", "UP"}})
base = ChartReadParams().for_display()
for brk in (False, True):
    for prov in (False, True):
        for eq in (0.0, 0.1, 0.2):
            p = replace(base, now_by_break=brk, prov_on_break=prov, equal_leg=eq)
            res = []
            for n, sym, tf, end in rows():
                r = read_at(sym, tf, end, p)
                v = (r.structure_now or r.structure).value
                res.append((v in truth[n], n, v))
            print(f"now_by_break {brk!s:5} prov_on_break {prov!s:5} equal_leg {eq}: {sum(o for o, _, _ in res):2}/20  wrong {[(n, v) for o, n, v in res if not o]}")
