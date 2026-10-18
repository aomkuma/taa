import sys
sys.argv = ["tp70.py"]
sys.path.insert(0, "research/2026-10-18-moments/agents/weapon4")
import numpy as np
exec(open("research/2026-10-18-moments/shadow/tp70.py", encoding="utf-8").read().split("days = w.days_in")[0])
days = w.days_in(*per)
# T70 split into its two parts
for name, tp, k in (("TP 5.6 only", 5.6 * u, 1.0), ("stop x1.1 only", 8 * u, 1.1), ("TP 7 U", 7 * u, 1.0)):
    S = S0.copy(); S["tp"], S["sl"] = tp, S0.sl.to_numpy() * k
    print(line(name, w.run(S, P), days))
# L70-5: by which TP it got
S = make("L70-5"); z = w.run(S, P)
r = z.tp / z.u
for lab, m in (("level TP < 8 U", r < 7.99), ("fallback 8 U", (r > 7.99) & (r < 8.01)), ("level TP > 8 U", r > 8.01)):
    x = z[m]
    print(f"  L70-5 {lab:16} {len(x):3} win {(x.exit == 'win').mean():4.0%} R {x.R.mean():+.3f} USD {x.usd.sum():+6.1f} TP med {np.median(x.tp / x.u) if len(x) else 0:.1f}")
b = w.run(make("BASE"), P)
print("  BASE: the move after entry (MFE) of all trades, U:", np.percentile(b.mfe / b.u, [25, 50, 75]).round(1), "| winners' exit:", b.exit.value_counts().to_dict())
for name, be in (("TP 5.6, BE at 4.8 U (old)", 4.8 / 5.6), ("TP 5.6, no BE", 99.0)):
    S = S0.copy(); S["tp"], S["be"] = 5.6 * u, be
    print(line(name, w.run(S, P), days))
